"""
Prior-Art Intelligence Engine
Indian Patent Analyzer V3

Responsibilities:
- Extract technical concepts from claims
- Generate expanded prior-art queries
- Generate searches for major patent databases
- Build limitation-aware search plans
- Normalize candidate prior-art records
- Deduplicate candidate records
- Preserve search provenance
- Prepare candidates for future semantic/claim-chart analysis

Important:
This module does NOT determine legal novelty or inventive step.
It produces search candidates and evidence structures for human review.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import quote_plus


ANALYZER_VERSION = "3.0.0"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class SearchQuery:
    query_id: str
    text: str
    source: str
    purpose: str
    limitation_ids: List[str] = field(default_factory=list)
    concepts: List[str] = field(default_factory=list)


@dataclass
class PriorArtCandidate:
    candidate_id: str
    title: str
    publication_number: str = ""
    application_number: str = ""
    priority_date: str = ""
    publication_date: str = ""
    filing_date: str = ""
    assignee: str = ""
    inventors: List[str] = field(default_factory=list)
    source: str = ""
    url: str = ""
    family_id: str = ""
    cpc_codes: List[str] = field(default_factory=list)
    ipc_codes: List[str] = field(default_factory=list)
    matched_terms: List[str] = field(default_factory=list)
    matched_limitation_ids: List[str] = field(default_factory=list)
    relevance_score: float = 0.0
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""

    value = str(value)
    value = re.sub(r"\s+", " ", value)
    return value.strip()


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(
        _clean_text(value).lower().encode("utf-8")
    ).hexdigest()[:16]

    return f"{prefix}-{digest}"


def _tokenize(text: str) -> List[str]:
    text = _clean_text(text).lower()

    tokens = re.findall(
        r"[a-zA-Z][a-zA-Z0-9\-]{2,}",
        text,
    )

    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "into",
        "configured",
        "wherein",
        "comprising",
        "including",
        "having",
        "thereof",
        "therein",
        "said",
        "one",
        "more",
        "least",
        "each",
        "based",
        "using",
        "system",
        "method",
        "device",
        "apparatus",
    }

    return [
        token
        for token in tokens
        if token not in stopwords
    ]


def _unique(values: Iterable[str]) -> List[str]:
    result = []
    seen = set()

    for value in values:
        value = _clean_text(value)

        if not value:
            continue

        key = value.lower()

        if key not in seen:
            seen.add(key)
            result.append(value)

    return result


# ---------------------------------------------------------------------------
# Technical concept extraction
# ---------------------------------------------------------------------------

def extract_technical_concepts(
    text: str,
    max_concepts: int = 20,
) -> List[str]:
    """
    Extract candidate technical concepts from claim text.

    This is intentionally deterministic. A future semantic model can be
    layered on top without changing this interface.
    """

    text = _clean_text(text)

    if not text:
        return []

    phrases = []

    # Multi-word technical phrases.
    phrase_patterns = [
        r"\b(?:machine learning|deep learning|neural network)\b",
        r"\b(?:lithium ion|lithium-ion|zinc ion|zinc-ion)\b",
        r"\b(?:battery management system|battery management)\b",
        r"\b(?:remaining useful life|state of health|state of charge)\b",
        r"\b(?:failure detection|fault detection|anomaly detection)\b",
        r"\b(?:data processing|signal processing)\b",
        r"\b(?:thermal management|thermal control)\b",
        r"\b(?:wireless communication|wireless transmission)\b",
        r"\b(?:control circuit|control system)\b",
    ]

    lowered = text.lower()

    for pattern in phrase_patterns:
        for match in re.findall(pattern, lowered):
            phrases.append(match)

    # Technical noun candidates.
    tokens = _tokenize(text)

    # Preserve moderately long technical terms.
    long_terms = [
        token
        for token in tokens
        if len(token) >= 6
    ]

    concepts = _unique(
        phrases + long_terms
    )

    return concepts[:max_concepts]


# ---------------------------------------------------------------------------
# Query expansion
# ---------------------------------------------------------------------------

SYNONYMS = {
    "failure": [
        "failure",
        "fault",
        "malfunction",
        "degradation",
        "abnormality",
    ],
    "detection": [
        "detection",
        "identification",
        "diagnosis",
        "monitoring",
    ],
    "prediction": [
        "prediction",
        "forecasting",
        "estimation",
        "prognosis",
    ],
    "battery": [
        "battery",
        "cell",
        "electrochemical cell",
        "rechargeable cell",
    ],
    "sensor": [
        "sensor",
        "detector",
        "measurement device",
    ],
    "controller": [
        "controller",
        "control unit",
        "processor",
        "control module",
    ],
    "temperature": [
        "temperature",
        "thermal",
        "heat",
    ],
    "communication": [
        "communication",
        "transmission",
        "data transfer",
        "wireless communication",
    ],
}


def expand_term(term: str) -> List[str]:
    """
    Expand one technical term using a conservative synonym dictionary.
    """

    term = _clean_text(term).lower()

    if not term:
        return []

    if term in SYNONYMS:
        return SYNONYMS[term]

    expansions = [term]

    for key, values in SYNONYMS.items():
        if key in term:
            expansions.extend(values)

    return _unique(expansions)


def expand_concepts(
    concepts: Sequence[str],
    max_terms: int = 40,
) -> List[str]:

    expanded = []

    for concept in concepts:
        expanded.extend(expand_term(concept))

    return _unique(expanded)[:max_terms]


# ---------------------------------------------------------------------------
# Limitation handling
# ---------------------------------------------------------------------------

def _normalise_limitation(
    limitation: Any,
    index: int,
) -> Dict[str, Any]:

    if isinstance(limitation, str):
        return {
            "id": f"L{index}",
            "text": limitation,
            "type": "unknown",
        }

    if isinstance(limitation, dict):
        return {
            "id": limitation.get(
                "id",
                f"L{index}",
            ),
            "text": _clean_text(
                limitation.get(
                    "text",
                    limitation.get(
                        "limitation",
                        "",
                    ),
                )
            ),
            "type": limitation.get(
                "type",
                "unknown",
            ),
        }

    return {
        "id": f"L{index}",
        "text": _clean_text(limitation),
        "type": "unknown",
    }


def extract_claim_limitations(
    claim: Dict[str, Any],
) -> List[Dict[str, Any]]:

    limitations = claim.get(
        "limitations",
        claim.get(
            "elements",
            [],
        ),
    )

    if not isinstance(limitations, list):
        return []

    return [
        _normalise_limitation(item, index)
        for index, item in enumerate(
            limitations,
            start=1,
        )
    ]


# ---------------------------------------------------------------------------
# Query construction
# ---------------------------------------------------------------------------

def build_limitation_query(
    limitation: Dict[str, Any],
) -> SearchQuery:

    limitation_id = limitation.get(
        "id",
        "L1",
    )

    text = _clean_text(
        limitation.get(
            "text",
            "",
        )
    )

    concepts = extract_technical_concepts(
        text
    )

    if not concepts:
        concepts = _tokenize(text)[:8]

    expanded = expand_concepts(
        concepts,
        max_terms=12,
    )

    # Prefer the original concepts in the main query.
    query_terms = concepts[:6]

    query_text = " ".join(
        f'"{term}"'
        for term in query_terms
    )

    return SearchQuery(
        query_id=_stable_id(
            "Q",
            limitation_id + "|" + query_text,
        ),
        text=query_text,
        source="generated",
        purpose="limitation_search",
        limitation_ids=[limitation_id],
        concepts=expanded,
    )


def build_claim_search_queries(
    claim: Dict[str, Any],
    max_queries: int = 20,
) -> List[SearchQuery]:

    limitations = extract_claim_limitations(
        claim
    )

    queries = []

    # Individual limitation searches.
    for limitation in limitations:
        queries.append(
            build_limitation_query(
                limitation
            )
        )

    # Whole-claim concept query.
    claim_text = _clean_text(
        claim.get(
            "text",
            claim.get(
                "claim_text",
                "",
            ),
        )
    )

    concepts = extract_technical_concepts(
        claim_text
    )

    if concepts:
        main_query = " ".join(
            f'"{term}"'
            for term in concepts[:8]
        )

        queries.append(
            SearchQuery(
                query_id=_stable_id(
                    "Q",
                    "whole-claim|" + main_query,
                ),
                text=main_query,
                source="generated",
                purpose="whole_claim_search",
                limitation_ids=[
                    item["id"]
                    for item in limitations
                ],
                concepts=expand_concepts(
                    concepts
                ),
            )
        )

    return queries[:max_queries]


# ---------------------------------------------------------------------------
# Database URL generation
# ---------------------------------------------------------------------------

def google_patents_url(query: str) -> str:
    return (
        "https://patents.google.com/"
        "?q="
        + quote_plus(query)
    )


def espacenet_url(query: str) -> str:
    return (
        "https://worldwide.espacenet.com/"
        "patent/search?q="
        + quote_plus(query)
    )


def wipo_patentscope_url(query: str) -> str:
    return (
        "https://patentscope.wipo.int/"
        "search/en/result.jsf?query="
        + quote_plus(query)
    )


def generate_database_links(
    query: SearchQuery,
) -> Dict[str, str]:

    return {
        "google_patents": google_patents_url(
            query.text
        ),
        "espacenet": espacenet_url(
            query.text
        ),
        "wipo_patentscope": wipo_patentscope_url(
            query.text
        ),
    }


# ---------------------------------------------------------------------------
# Search plan
# ---------------------------------------------------------------------------

def build_search_plan(
    claims: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:

    all_queries = []

    for claim_index, claim in enumerate(
        claims,
        start=1,
    ):

        claim_number = claim.get(
            "claim_number",
            claim.get(
                "number",
                claim_index,
            ),
        )

        queries = build_claim_search_queries(
            claim
        )

        for query in queries:

            query_dict = asdict(query)

            query_dict["claim_number"] = (
                claim_number
            )

            query_dict["database_links"] = (
                generate_database_links(query)
            )

            all_queries.append(
                query_dict
            )

    return {
        "analyzer_version": ANALYZER_VERSION,
        "generated_at": _utc_now(),
        "query_count": len(all_queries),
        "queries": all_queries,
    }


# ---------------------------------------------------------------------------
# Candidate normalization
# ---------------------------------------------------------------------------

def normalize_candidate(
    candidate: Dict[str, Any],
    source: str = "",
) -> PriorArtCandidate:

    publication_number = _clean_text(
        candidate.get(
            "publication_number",
            candidate.get(
                "publication",
                candidate.get(
                    "publicationNumber",
                    "",
                ),
            ),
        )
    )

    title = _clean_text(
        candidate.get(
            "title",
            "",
        )
    )

    url = _clean_text(
        candidate.get(
            "url",
            candidate.get(
                "link",
                "",
            ),
        )
    )

    candidate_key = (
        publication_number
        or url
        or title
    )

    candidate_id = _stable_id(
        "PA",
        candidate_key,
    )

    inventors = candidate.get(
        "inventors",
        [],
    )

    if isinstance(inventors, str):
        inventors = [
            item.strip()
            for item in inventors.split(",")
            if item.strip()
        ]

    if not isinstance(inventors, list):
        inventors = []

    cpc_codes = candidate.get(
        "cpc_codes",
        candidate.get(
            "cpc",
            [],
        ),
    )

    ipc_codes = candidate.get(
        "ipc_codes",
        candidate.get(
            "ipc",
            [],
        ),
    )

    if isinstance(cpc_codes, str):
        cpc_codes = [cpc_codes]

    if isinstance(ipc_codes, str):
        ipc_codes = [ipc_codes]

    return PriorArtCandidate(
        candidate_id=candidate_id,
        title=title,
        publication_number=publication_number,
        application_number=_clean_text(
            candidate.get(
                "application_number",
                "",
            )
        ),
        priority_date=_clean_text(
            candidate.get(
                "priority_date",
                "",
            )
        ),
        publication_date=_clean_text(
            candidate.get(
                "publication_date",
                "",
            )
        ),
        filing_date=_clean_text(
            candidate.get(
                "filing_date",
                "",
            )
        ),
        assignee=_clean_text(
            candidate.get(
                "assignee",
                "",
            )
        ),
        inventors=inventors,
        source=source
        or _clean_text(
            candidate.get(
                "source",
                "",
            )
        ),
        url=url,
        family_id=_clean_text(
            candidate.get(
                "family_id",
                "",
            )
        ),
        cpc_codes=_unique(cpc_codes),
        ipc_codes=_unique(ipc_codes),
        matched_terms=_unique(
            candidate.get(
                "matched_terms",
                [],
            )
        ),
        matched_limitation_ids=_unique(
            candidate.get(
                "matched_limitation_ids",
                [],
            )
        ),
        relevance_score=float(
            candidate.get(
                "relevance_score",
                0.0,
            ) or 0.0
        ),
        evidence=candidate.get(
            "evidence",
            [],
        ) or [],
        metadata={
            **(
                candidate.get(
                    "metadata",
                    {},
                )
                or {}
            ),
            "normalized_at": _utc_now(),
            "analyzer_version": ANALYZER_VERSION,
        },
    )


# ---------------------------------------------------------------------------
# Candidate deduplication
# ---------------------------------------------------------------------------

def deduplicate_candidates(
    candidates: Sequence[PriorArtCandidate],
) -> List[PriorArtCandidate]:

    result = []
    seen = set()

    for candidate in candidates:

        key = (
            candidate.family_id
            or candidate.publication_number
            or candidate.url
            or candidate.title.lower()
        )

        if not key:
            continue

        if key in seen:
            continue

        seen.add(key)
        result.append(candidate)

    return result


# ---------------------------------------------------------------------------
# Candidate relevance scoring
# ---------------------------------------------------------------------------

def score_candidate(
    candidate: PriorArtCandidate,
    query_terms: Sequence[str],
) -> float:

    if not query_terms:
        return 0.0

    searchable_text = " ".join(
        [
            candidate.title,
            candidate.assignee,
            " ".join(candidate.matched_terms),
            " ".join(candidate.cpc_codes),
            " ".join(candidate.ipc_codes),
        ]
    ).lower()

    terms = [
        _clean_text(term).lower()
        for term in query_terms
        if _clean_text(term)
    ]

    if not terms:
        return 0.0

    matches = sum(
        1
        for term in terms
        if term in searchable_text
    )

    return round(
        min(
            1.0,
            matches / len(terms),
        ),
        4,
    )


# ---------------------------------------------------------------------------
# Claim-level prior-art analysis preparation
# ---------------------------------------------------------------------------

def prepare_prior_art_analysis(
    claim: Dict[str, Any],
    candidates: Sequence[Dict[str, Any]],
) -> Dict[str, Any]:

    queries = build_claim_search_queries(
        claim
    )

    normalized = [
        normalize_candidate(
            candidate,
            source=candidate.get(
                "source",
                "",
            )
            if isinstance(candidate, dict)
            else "",
        )
        for candidate in candidates
    ]

    normalized = deduplicate_candidates(
        normalized
    )

    all_terms = []

    for query in queries:
        all_terms.extend(
            query.concepts
        )

    for candidate in normalized:
        candidate.relevance_score = score_candidate(
            candidate,
            all_terms,
        )

    normalized.sort(
        key=lambda item: item.relevance_score,
        reverse=True,
    )

    return {
        "analyzer_version": ANALYZER_VERSION,
        "generated_at": _utc_now(),
        "claim_number": claim.get(
            "claim_number",
            claim.get(
                "number",
                "",
            ),
        ),
        "queries": [
            asdict(query)
            for query in queries
        ],
        "candidate_count": len(
            normalized
        ),
        "candidates": [
            asdict(candidate)
            for candidate in normalized
        ],
        "human_review_required": True,
        "legal_conclusion": False,
    }


# ---------------------------------------------------------------------------
# Backward-compatible public functions
# ---------------------------------------------------------------------------

def generate_search_queries(
    claims: Sequence[Any],
) -> List[str]:
    """
    Backward-compatible helper.

    Accepts:
        ["claim text", ...]

    or:
        [{"text": "...", "limitations": [...]}]
    """

    queries = []

    for item in claims:

        if isinstance(item, str):
            claim = {
                "text": item,
                "limitations": [],
            }
        else:
            claim = item

        for query in build_claim_search_queries(
            claim
        ):
            if query.text:
                queries.append(
                    query.text
                )

    return _unique(queries)


def generate_prior_art_links(
    query: str,
) -> Dict[str, str]:
    """
    Backward-compatible database-link helper.
    """

    return {
        "Google Patents": google_patents_url(
            query
        ),
        "Espacenet": espacenet_url(
            query
        ),
        "WIPO PATENTSCOPE": wipo_patentscope_url(
            query
        ),
    }


def analyze_prior_art(
    claims: Sequence[Dict[str, Any]],
    candidates: Optional[
        Sequence[Dict[str, Any]]
    ] = None,
) -> Dict[str, Any]:
    """
    Main entry point.

    If candidates are not supplied, this function generates a search plan.

    It intentionally does not claim that a patent is novel/non-novel or
    patentable/non-patentable.
    """

    candidates = candidates or []

    plan = build_search_plan(
        claims
    )

    candidate_records = [
        normalize_candidate(
            candidate
        )
        for candidate in candidates
    ]

    candidate_records = deduplicate_candidates(
        candidate_records
    )

    return {
        "analyzer_version": ANALYZER_VERSION,
        "generated_at": _utc_now(),
        "search_plan": plan,
        "candidate_count": len(
            candidate_records
        ),
        "candidates": [
            asdict(candidate)
            for candidate in candidate_records
        ],
        "human_review_required": True,
        "legal_conclusion": False,
    }


__all__ = [
    "ANALYZER_VERSION",
    "SearchQuery",
    "PriorArtCandidate",
    "extract_technical_concepts",
    "expand_term",
    "expand_concepts",
    "build_limitation_query",
    "build_claim_search_queries",
    "build_search_plan",
    "google_patents_url",
    "espacenet_url",
    "wipo_patentscope_url",
    "generate_database_links",
    "normalize_candidate",
    "deduplicate_candidates",
    "score_candidate",
    "prepare_prior_art_analysis",
    "generate_search_queries",
    "generate_prior_art_links",
    "analyze_prior_art",
]
