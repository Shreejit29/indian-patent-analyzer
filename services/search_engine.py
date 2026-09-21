"""
Patent Search Engine V3
=======================

Purpose
-------
Search orchestration and normalization layer for the patent analyzer.

Architecture
------------

    Claim
      │
      ▼
    Search Plan
      │
      ├── Exact limitation queries
      ├── Technical concept queries
      ├── Synonym-expanded queries
      └── Database-specific queries
      │
      ▼
    Search Providers
      │
      ├── Google Patents
      ├── Espacenet
      ├── WIPO PATENTSCOPE
      └── Future API providers
      │
      ▼
    Raw Results
      │
      ▼
    Normalization
      │
      ▼
    Deduplication
      │
      ▼
    Relevance Ranking
      │
      ▼
    Prior-Art Candidates
      │
      ▼
    Evidence / Claim Chart

Important
---------
This module does NOT make a legal determination of novelty or
inventive step.

Search relevance is a retrieval signal only.

A search result is not automatically prior art against a patent.
Publication dates, priority dates, jurisdiction, family members,
and other legal requirements must be separately reviewed.

The module can operate without internet access when supplied with
provider results manually.

Version
-------
3.0.0
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
from urllib.parse import quote_plus


SEARCH_ENGINE_VERSION = "3.0.0"


# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

PROVIDER_GOOGLE_PATENTS = "google_patents"
PROVIDER_ESPACENET = "espacenet"
PROVIDER_WIPO = "wipo_patentscope"
PROVIDER_MANUAL = "manual"
PROVIDER_API = "api"

DEFAULT_MAX_RESULTS = 50


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _clean(
    value: Any,
) -> str:

    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def _normalize(
    value: Any,
) -> str:

    text = _clean(value).lower()

    text = re.sub(
        r"[^a-z0-9\s\-]",
        " ",
        text,
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def _stable_id(
    prefix: str,
    value: Any,
) -> str:

    if not isinstance(
        value,
        str,
    ):

        value = json.dumps(
            value,
            sort_keys=True,
            default=str,
        )

    digest = hashlib.sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()[:16]

    return f"{prefix}-{digest}"


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:
        return float(value)

    except Exception:
        return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:

    try:
        return int(value)

    except Exception:
        return default


def _tokenize(
    text: str,
) -> List[str]:

    return re.findall(
        r"\b[a-zA-Z0-9][a-zA-Z0-9\-]{2,}\b",
        _normalize(text),
    )


def _unique(
    values: Iterable[Any],
) -> List[Any]:

    result = []

    seen = set()

    for value in values:

        key = (
            _normalize(value)
            if isinstance(
                value,
                str,
            )
            else str(value)
        )

        if not key:
            continue

        if key in seen:
            continue

        seen.add(key)

        result.append(
            value
        )

    return result


def _to_dict(
    value: Any,
) -> Dict[str, Any]:

    if value is None:
        return {}

    if isinstance(
        value,
        dict,
    ):
        return value

    if hasattr(
        value,
        "to_dict",
    ):

        try:

            result = value.to_dict()

            if isinstance(
                result,
                dict,
            ):
                return result

        except Exception:
            pass

    if hasattr(
        value,
        "__dict__",
    ):

        return dict(
            value.__dict__
        )

    return {}


# ---------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------

@dataclass
class PatentSearchQuery:

    query_id: str

    claim_number: int

    query: str

    query_type: str

    limitation_ids: List[str] = field(
        default_factory=list
    )

    concepts: List[str] = field(
        default_factory=list
    )

    provider: str = PROVIDER_GOOGLE_PATENTS

    priority: float = 0.5

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    created_at: str = field(
        default_factory=_utc_now
    )

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(
            self
        )


@dataclass
class PatentSearchResult:

    result_id: str

    provider: str

    title: str = ""

    publication_number: str = ""

    application_number: str = ""

    patent_number: str = ""

    publication_date: str = ""

    filing_date: str = ""

    priority_date: str = ""

    inventors: List[str] = field(
        default_factory=list
    )

    applicants: List[str] = field(
        default_factory=list
    )

    assignees: List[str] = field(
        default_factory=list
    )

    abstract: str = ""

    claims: str = ""

    description: str = ""

    url: str = ""

    family_id: str = ""

    family_members: List[str] = field(
        default_factory=list
    )

    classifications: List[str] = field(
        default_factory=list
    )

    matched_queries: List[str] = field(
        default_factory=list
    )

    matched_terms: List[str] = field(
        default_factory=list
    )

    relevance_score: float = 0.0

    lexical_score: float = 0.0

    technical_score: float = 0.0

    metadata_score: float = 0.0

    retrieval_score: float = 0.0

    source_metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    retrieved_at: str = field(
        default_factory=_utc_now
    )

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(
            self
        )


@dataclass
class SearchBatch:

    batch_id: str

    queries: List[
        PatentSearchQuery
    ] = field(
        default_factory=list
    )

    results: List[
        PatentSearchResult
    ] = field(
        default_factory=list
    )

    provider_status: Dict[
        str,
        str
    ] = field(
        default_factory=dict
    )

    warnings: List[str] = field(
        default_factory=list
    )

    errors: List[str] = field(
        default_factory=list
    )

    created_at: str = field(
        default_factory=_utc_now
    )

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return {
            "batch_id":
                self.batch_id,

            "queries": [
                q.to_dict()
                for q in self.queries
            ],

            "results": [
                r.to_dict()
                for r in self.results
            ],

            "provider_status":
                self.provider_status,

            "warnings":
                self.warnings,

            "errors":
                self.errors,

            "created_at":
                self.created_at,
        }


# ---------------------------------------------------------------------
# Query builder
# ---------------------------------------------------------------------

class PatentSearchQueryBuilder:

    """
    Converts claim limitations and search plans into normalized
    patent-search queries.
    """

    def __init__(
        self,
        *,
        max_query_terms: int = 12,
    ):

        self.max_query_terms = max_query_terms

    def _extract_limitations(
        self,
        claim: Dict[str, Any],
    ) -> List[Dict[str, Any]]:

        limitations = claim.get(
            "limitations",
            [],
        )

        result = []

        for index, item in enumerate(
            limitations,
            start=1,
        ):

            limitation = _to_dict(
                item
            )

            if not limitation:

                limitation = {
                    "text":
                        _clean(item),

                    "limitation_id":
                        _stable_id(
                            "LIM",
                            f"{claim.get('claim_number', 0)}|{index}|{item}",
                        ),
                }

            limitation.setdefault(
                "limitation_id",
                _stable_id(
                    "LIM",
                    limitation,
                ),
            )

            result.append(
                limitation
            )

        return result

    def _technical_terms(
        self,
        text: str,
    ) -> List[str]:

        tokens = _tokenize(
            text
        )

        # Remove generic legal / drafting terms.
        stopwords = {
            "wherein",
            "comprising",
            "including",
            "configured",
            "adapted",
            "said",
            "thereof",
            "therein",
            "method",
            "system",
            "device",
            "apparatus",
            "claim",
            "using",
            "providing",
            "having",
            "based",
            "according",
            "further",
            "plurality",
            "first",
            "second",
            "third",
        }

        terms = [
            token
            for token in tokens
            if token
            not in stopwords
        ]

        return terms[
            : self.max_query_terms
        ]

    def build_for_claim(
        self,
        claim: Dict[str, Any],
    ) -> List[
        PatentSearchQuery
    ]:

        claim_number = _safe_int(
            claim.get(
                "claim_number",
                1,
            ),
            1,
        )

        claim_text = _clean(
            claim.get(
                "text",
                claim.get(
                    "claim_text",
                    "",
                ),
            )
        )

        limitations = (
            self._extract_limitations(
                claim
            )
        )

        queries = []

        # ---------------------------------------------------------
        # Claim-level query
        # ---------------------------------------------------------

        claim_terms = (
            self._technical_terms(
                claim_text
            )
        )

        if claim_terms:

            query = " ".join(
                f'"{term}"'
                for term
                in claim_terms[
                    :8
                ]
            )

            queries.append(
                PatentSearchQuery(
                    query_id=_stable_id(
                        "Q",
                        f"{claim_number}|claim|{query}",
                    ),
                    claim_number=claim_number,
                    query=query,
                    query_type="CLAIM_CONCEPT",
                    concepts=claim_terms,
                    priority=0.8,
                )
            )

        # ---------------------------------------------------------
        # Limitation queries
        # ---------------------------------------------------------

        for index, limitation in enumerate(
            limitations,
            start=1,
        ):

            text = _clean(
                limitation.get(
                    "text",
                    limitation.get(
                        "description",
                        "",
                    ),
                )
            )

            terms = self._technical_terms(
                text
            )

            if not terms:
                continue

            query = " ".join(
                f'"{term}"'
                for term
                in terms[:8]
            )

            queries.append(
                PatentSearchQuery(
                    query_id=_stable_id(
                        "Q",
                        f"{claim_number}|limitation|{index}|{query}",
                    ),
                    claim_number=claim_number,
                    query=query,
                    query_type="LIMITATION",
                    limitation_ids=[
                        limitation.get(
                            "limitation_id",
                            "",
                        )
                    ],
                    concepts=terms,
                    priority=max(
                        0.5,
                        1.0
                        - (
                            index
                            * 0.05
                        ),
                    ),
                )
            )

        # ---------------------------------------------------------
        # Phrase query
        # ---------------------------------------------------------

        if len(
            limitations
        ) >= 2:

            important = []

            for limitation in limitations:

                text = _clean(
                    limitation.get(
                        "text",
                        "",
                    )
                )

                terms = self._technical_terms(
                    text
                )

                if terms:

                    important.append(
                        " ".join(
                            terms[:4]
                        )
                    )

            if important:

                combined = (
                    " ".join(
                        important[
                            :4
                        ]
                    )
                )

                queries.append(
                    PatentSearchQuery(
                        query_id=_stable_id(
                            "Q",
                            f"{claim_number}|combined|{combined}",
                        ),
                        claim_number=claim_number,
                        query=combined,
                        query_type="COMBINED_LIMITATIONS",
                        concepts=_unique(
                            self._technical_terms(
                                combined
                            )
                        ),
                        priority=0.9,
                    )
                )

        return queries

    def build(
        self,
        claims: Iterable[Any],
    ) -> List[
        PatentSearchQuery
    ]:

        result = []

        for claim in claims:

            claim_dict = _to_dict(
                claim
            )

            if not claim_dict:
                continue

            result.extend(
                self.build_for_claim(
                    claim_dict
                )
            )

        # Deterministic ordering.
        result.sort(
            key=lambda item: (
                -item.priority,
                item.claim_number,
                item.query,
            )
        )

        return result


# ---------------------------------------------------------------------
# Provider URL builders
# ---------------------------------------------------------------------

class PatentProviderLinks:

    @staticmethod
    def google_patents(
        query: str,
    ) -> str:

        return (
            "https://patents.google.com/"
            "?q="
            + quote_plus(
                query
            )
        )

    @staticmethod
    def espacenet(
        query: str,
    ) -> str:

        return (
            "https://worldwide.espacenet.com/"
            "patent/search/"
            "?q="
            + quote_plus(
                query
            )
        )

    @staticmethod
    def wipo(
        query: str,
    ) -> str:

        return (
            "https://patentscope.wipo.int/"
            "search/en/result.jsf"
            "?query="
            + quote_plus(
                query
            )
        )

    @classmethod
    def build(
        cls,
        query: str,
    ) -> Dict[str, str]:

        return {
            PROVIDER_GOOGLE_PATENTS:
                cls.google_patents(
                    query
                ),

            PROVIDER_ESPACENET:
                cls.espacenet(
                    query
                ),

            PROVIDER_WIPO:
                cls.wipo(
                    query
                ),
        }


# ---------------------------------------------------------------------
# Provider abstraction
# ---------------------------------------------------------------------

class SearchProvider:

    name = "base"

    def search(
        self,
        query: str,
        *,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> List[
        Dict[str, Any]
    ]:

        raise NotImplementedError


class ManualSearchProvider(
    SearchProvider
):

    """
    Offline provider.

    Useful for:
    - testing
    - manually pasted search results
    - API integration
    - unit tests
    """

    name = PROVIDER_MANUAL

    def __init__(
        self,
        results: Optional[
            Iterable[
                Dict[str, Any]
            ]
        ] = None,
    ):

        self.results = [
            _to_dict(item)
            for item
            in (
                results
                or []
            )
        ]

    def search(
        self,
        query: str,
        *,
        max_results: int = DEFAULT_MAX_RESULTS,
    ) -> List[
        Dict[str, Any]
    ]:

        query_norm = _normalize(
            query
        )

        if not query_norm:

            return []

        query_tokens = set(
            _tokenize(
                query_norm
            )
        )

        scored = []

        for item in self.results:

            text = " ".join(
                [
                    _clean(
                        item.get(
                            "title",
                            "",
                        )
                    ),
                    _clean(
                        item.get(
                            "abstract",
                            "",
                        )
                    ),
                    _clean(
                        item.get(
                            "claims",
                            "",
                        )
                    ),
                    _clean(
                        item.get(
                            "description",
                            "",
                        )
                    ),
                ]
            )

            result_tokens = set(
                _tokenize(
                    text
                )
            )

            overlap = (
                len(
                    query_tokens
                    & result_tokens
                )
                / max(
                    len(
                        query_tokens
                    ),
                    1,
                )
            )

            scored.append(
                (
                    overlap,
                    item,
                )
            )

        scored.sort(
            key=lambda item: -item[0]
        )

        return [
            item
            for _, item
            in scored[
                :max_results
            ]
        ]


# ---------------------------------------------------------------------
# Normalization
# ---------------------------------------------------------------------

class PatentResultNormalizer:

    @staticmethod
    def _publication_number(
        item: Dict[str, Any],
    ) -> str:

        return _clean(
            item.get(
                "publication_number",
                item.get(
                    "publicationNumber",
                    item.get(
                        "publication",
                        item.get(
                            "patent_number",
                            "",
                        ),
                    ),
                ),
            )
        )

    @staticmethod
    def _title(
        item: Dict[str, Any],
    ) -> str:

        return _clean(
            item.get(
                "title",
                item.get(
                    "name",
                    "",
                ),
            )
        )

    @staticmethod
    def _abstract(
        item: Dict[str, Any],
    ) -> str:

        return _clean(
            item.get(
                "abstract",
                item.get(
                    "summary",
                    "",
                ),
            )
        )

    @staticmethod
    def normalize(
        item: Dict[str, Any],
        *,
        provider: str,
        query: Optional[
            PatentSearchQuery
        ] = None,
    ) -> PatentSearchResult:

        publication_number = (
            PatentResultNormalizer
            ._publication_number(
                item
            )
        )

        title = (
            PatentResultNormalizer
            ._title(
                item
            )
        )

        abstract = (
            PatentResultNormalizer
            ._abstract(
                item
            )
        )

        result_key = (
            publication_number
            or _stable_id(
                "RAW",
                (
                    title
                    + "|"
                    + abstract
                ),
            )
        )

        result_id = _stable_id(
            "RESULT",
            (
                provider
                + "|"
                + result_key
            ),
        )

        inventors = item.get(
            "inventors",
            [],
        )

        if isinstance(
            inventors,
            str,
        ):

            inventors = [
                inventors
            ]

        applicants = item.get(
            "applicants",
            item.get(
                "applicant",
                [],
            ),
        )

        if isinstance(
            applicants,
            str,
        ):

            applicants = [
                applicants
            ]

        classifications = item.get(
            "classifications",
            item.get(
                "ipc",
                [],
            ),
        )

        if isinstance(
            classifications,
            str,
        ):

            classifications = [
                classifications
            ]

        return PatentSearchResult(
            result_id=result_id,
            provider=provider,
            title=title,
            publication_number=publication_number,
            application_number=_clean(
                item.get(
                    "application_number",
                    item.get(
                        "applicationNumber",
                        "",
                    ),
                )
            ),
            patent_number=_clean(
                item.get(
                    "patent_number",
                    "",
                )
            ),
            publication_date=_clean(
                item.get(
                    "publication_date",
                    item.get(
                        "publicationDate",
                        "",
                    ),
                )
            ),
            filing_date=_clean(
                item.get(
                    "filing_date",
                    item.get(
                        "filingDate",
                        "",
                    ),
                )
            ),
            priority_date=_clean(
                item.get(
                    "priority_date",
                    item.get(
                        "priorityDate",
                        "",
                    ),
                )
            ),
            inventors=[
                _clean(x)
                for x
                in inventors
                if _clean(x)
            ],
            applicants=[
                _clean(x)
                for x
                in applicants
                if _clean(x)
            ],
            assignees=[
                _clean(x)
                for x
                in _listify(
                    item.get(
                        "assignees",
                        [],
                    )
                )
                if _clean(x)
            ],
            abstract=abstract,
            claims=_clean(
                item.get(
                    "claims",
                    "",
                )
            ),
            description=_clean(
                item.get(
                    "description",
                    "",
                )
            ),
            url=_clean(
                item.get(
                    "url",
                    item.get(
                        "link",
                        "",
                    ),
                )
            ),
            family_id=_clean(
                item.get(
                    "family_id",
                    item.get(
                        "familyId",
                        "",
                    ),
                )
            ),
            family_members=[
                _clean(x)
                for x
                in _listify(
                    item.get(
                        "family_members",
                        [],
                    )
                )
                if _clean(x)
            ],
            classifications=[
                _clean(x)
                for x
                in classifications
                if _clean(x)
            ],
            matched_queries=(
                [query.query]
                if query
                else []
            ),
            source_metadata={
                "raw_provider":
                    provider,

                "raw_id":
                    _clean(
                        item.get(
                            "id",
                            "",
                        )
                    ),
            },
        )


# ---------------------------------------------------------------------
# Relevance scoring
# ---------------------------------------------------------------------

class PatentRelevanceScorer:

    def __init__(
        self,
        *,
        lexical_weight: float = 0.50,
        technical_weight: float = 0.35,
        metadata_weight: float = 0.15,
    ):

        self.lexical_weight = (
            lexical_weight
        )

        self.technical_weight = (
            technical_weight
        )

        self.metadata_weight = (
            metadata_weight
        )

    def _lexical_score(
        self,
        query: str,
        result: PatentSearchResult,
    ) -> float:

        query_tokens = set(
            _tokenize(
                query
            )
        )

        if not query_tokens:
            return 0.0

        result_text = " ".join(
            [
                result.title,
                result.abstract,
                result.claims,
                result.description,
            ]
        )

        result_tokens = set(
            _tokenize(
                result_text
            )
        )

        if not result_tokens:
            return 0.0

        return (
            len(
                query_tokens
                & result_tokens
            )
            / len(
                query_tokens
            )
        )

    def _technical_score(
        self,
        query: PatentSearchQuery,
        result: PatentSearchResult,
    ) -> float:

        concepts = set(
            _normalize(
                concept
            )
            for concept
            in query.concepts
            if _normalize(
                concept
            )
        )

        if not concepts:
            return 0.0

        text = _normalize(
            " ".join(
                [
                    result.title,
                    result.abstract,
                    result.claims,
                    result.description,
                ]
            )
        )

        matched = 0

        for concept in concepts:

            if concept in text:

                matched += 1

        return (
            matched
            / len(
                concepts
            )
        )

    def _metadata_score(
        self,
        result: PatentSearchResult,
    ) -> float:

        score = 0.0

        if result.publication_number:

            score += 0.30

        if result.publication_date:

            score += 0.20

        if result.priority_date:

            score += 0.20

        if result.url:

            score += 0.15

        if result.classifications:

            score += 0.15

        return min(
            score,
            1.0,
        )

    def score(
        self,
        query: PatentSearchQuery,
        result: PatentSearchResult,
    ) -> PatentSearchResult:

        lexical = self._lexical_score(
            query.query,
            result,
        )

        technical = (
            self._technical_score(
                query,
                result,
            )
        )

        metadata = (
            self._metadata_score(
                result
            )
        )

        retrieval = (
            (
                lexical
                * self.lexical_weight
            )
            + (
                technical
                * self.technical_weight
            )
            + (
                metadata
                * self.metadata_weight
            )
        )

        result.lexical_score = round(
            lexical,
            6,
        )

        result.technical_score = round(
            technical,
            6,
        )

        result.metadata_score = round(
            metadata,
            6,
        )

        result.retrieval_score = round(
            retrieval,
            6,
        )

        result.relevance_score = round(
            retrieval,
            6,
        )

        result.matched_queries = _unique(
            result.matched_queries
            + [
                query.query
            ]
        )

        result.matched_terms = _unique(
            result.matched_terms
            + [
                concept
                for concept
                in query.concepts
                if _normalize(
                    concept
                )
                in _normalize(
                    " ".join(
                        [
                            result.title,
                            result.abstract,
                            result.claims,
                            result.description,
                        ]
                    )
                )
            ]
        )

        return result


# ---------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------

class PatentResultDeduplicator:

    @staticmethod
    def _key(
        result: PatentSearchResult,
    ) -> str:

        if result.publication_number:

            return (
                "PUB:"
                + _normalize(
                    result.publication_number
                )
            )

        if result.family_id:

            return (
                "FAM:"
                + _normalize(
                    result.family_id
                )
            )

        return (
            "TEXT:"
            + _normalize(
                result.title
                + "|"
                + result.abstract
            )
        )

    @classmethod
    def deduplicate(
        cls,
        results: Iterable[
            PatentSearchResult
        ],
    ) -> List[
        PatentSearchResult
    ]:

        grouped = {}

        for result in results:

            key = cls._key(
                result
            )

            existing = grouped.get(
                key
            )

            if existing is None:

                grouped[
                    key
                ] = result

                continue

            # Keep the result with stronger retrieval
            # evidence while preserving all query matches.
            if (
                result.relevance_score
                > existing.relevance_score
            ):

                winner = result
                loser = existing

            else:

                winner = existing
                loser = result

            winner.matched_queries = _unique(
                winner.matched_queries
                + loser.matched_queries
            )

            winner.matched_terms = _unique(
                winner.matched_terms
                + loser.matched_terms
            )

            if (
                not winner.url
                and loser.url
            ):

                winner.url = loser.url

            if (
                not winner.abstract
                and loser.abstract
            ):

                winner.abstract = (
                    loser.abstract
                )

            if (
                not winner.priority_date
                and loser.priority_date
            ):

                winner.priority_date = (
                    loser.priority_date
                )

            grouped[
                key
            ] = winner

        return list(
            grouped.values()
        )


# ---------------------------------------------------------------------
# Search engine
# ---------------------------------------------------------------------

class PatentSearchEngine:

    def __init__(
        self,
        *,
        providers: Optional[
            Dict[
                str,
                SearchProvider
            ]
        ] = None,
        max_results_per_query: int = 20,
        min_relevance: float = 0.05,
    ):

        self.providers = (
            providers
            or {}
        )

        self.max_results_per_query = (
            max_results_per_query
        )

        self.min_relevance = (
            min_relevance
        )

        self.query_builder = (
            PatentSearchQueryBuilder()
        )

        self.scorer = (
            PatentRelevanceScorer()
        )

        self.deduplicator = (
            PatentResultDeduplicator()
        )

    # -------------------------------------------------------------
    # Provider management
    # -------------------------------------------------------------

    def register_provider(
        self,
        provider: SearchProvider,
    ):

        self.providers[
            provider.name
        ] = provider

    def get_provider(
        self,
        name: str,
    ) -> Optional[
        SearchProvider
    ]:

        return self.providers.get(
            name
        )

    # -------------------------------------------------------------
    # Search
    # -------------------------------------------------------------

    def search_query(
        self,
        query: PatentSearchQuery,
        *,
        providers: Optional[
            Sequence[str]
        ] = None,
    ) -> List[
        PatentSearchResult
    ]:

        provider_names = list(
            providers
            or self.providers.keys()
        )

        results = []

        for provider_name in provider_names:

            provider = self.providers.get(
                provider_name
            )

            if provider is None:
                continue

            try:

                raw_results = (
                    provider.search(
                        query.query,
                        max_results=(
                            self.max_results_per_query
                        ),
                    )
                )

            except Exception:

                continue

            for raw in raw_results:

                if not isinstance(
                    raw,
                    dict,
                ):
                    continue

                normalized = (
                    PatentResultNormalizer
                    .normalize(
                        raw,
                        provider=provider_name,
                        query=query,
                    )
                )

                normalized = (
                    self.scorer.score(
                        query,
                        normalized,
                    )
                )

                if (
                    normalized.relevance_score
                    >= self.min_relevance
                ):

                    results.append(
                        normalized
                    )

        return self.deduplicator.deduplicate(
            results
        )

    def search_claim(
        self,
        claim: Dict[str, Any],
        *,
        providers: Optional[
            Sequence[str]
        ] = None,
    ) -> List[
        PatentSearchResult
    ]:

        queries = (
            self.query_builder
            .build_for_claim(
                claim
            )
        )

        results = []

        for query in queries:

            results.extend(
                self.search_query(
                    query,
                    providers=providers,
                )
            )

        results = (
            self.deduplicator
            .deduplicate(
                results
            )
        )

        results.sort(
            key=lambda item:
                -item.relevance_score
        )

        return results

    def search_claims(
        self,
        claims: Iterable[Any],
        *,
        providers: Optional[
            Sequence[str]
        ] = None,
    ) -> SearchBatch:

        claims = list(
            claims
        )

        queries = (
            self.query_builder
            .build(
                claims
            )
        )

        all_results = []

        provider_status = {}

        for provider_name in (
            providers
            or self.providers.keys()
        ):

            if (
                provider_name
                not in self.providers
            ):

                provider_status[
                    provider_name
                ] = "NOT_REGISTERED"

            else:

                provider_status[
                    provider_name
                ] = "AVAILABLE"

        for query in queries:

            all_results.extend(
                self.search_query(
                    query,
                    providers=providers,
                )
            )

        deduplicated = (
            self.deduplicator
            .deduplicate(
                all_results
            )
        )

        deduplicated.sort(
            key=lambda item:
                -item.relevance_score
        )

        return SearchBatch(
            batch_id=_stable_id(
                "SEARCH",
                (
                    f"{_utc_now()}|"
                    f"{len(queries)}"
                ),
            ),
            queries=queries,
            results=deduplicated,
            provider_status=provider_status,
        )

    # -------------------------------------------------------------
    # Search plan integration
    # -------------------------------------------------------------

    def execute_search_plan(
        self,
        search_plan: Dict[str, Any],
        *,
        providers: Optional[
            Sequence[str]
        ] = None,
    ) -> SearchBatch:

        queries = []

        raw_queries = search_plan.get(
            "queries",
            []
        )

        for item in raw_queries:

            if isinstance(
                item,
                PatentSearchQuery,
            ):

                queries.append(
                    item
                )

                continue

            item = _to_dict(
                item
            )

            if not item:
                continue

            query_text = _clean(
                item.get(
                    "query",
                    item.get(
                        "text",
                        "",
                    ),
                )
            )

            if not query_text:
                continue

            query = PatentSearchQuery(
                query_id=_clean(
                    item.get(
                        "query_id",
                        _stable_id(
                            "Q",
                            query_text,
                        ),
                    )
                ),
                claim_number=_safe_int(
                    item.get(
                        "claim_number",
                        0,
                    )
                ),
                query=query_text,
                query_type=_clean(
                    item.get(
                        "query_type",
                        "SEARCH_PLAN",
                    )
                ),
                limitation_ids=[
                    _clean(x)
                    for x
                    in _listify(
                        item.get(
                            "limitation_ids",
                            [],
                        )
                    )
                    if _clean(x)
                ],
                concepts=[
                    _clean(x)
                    for x
                    in _listify(
                        item.get(
                            "concepts",
                            [],
                        )
                    )
                    if _clean(x)
                ],
                priority=_safe_float(
                    item.get(
                        "priority",
                        0.5,
                    ),
                    0.5,
                ),
                metadata=item.get(
                    "metadata",
                    {},
                ),
            )

            queries.append(
                query
            )

        all_results = []

        for query in queries:

            all_results.extend(
                self.search_query(
                    query,
                    providers=providers,
                )
            )

        all_results = (
            self.deduplicator
            .deduplicate(
                all_results
            )
        )

        all_results.sort(
            key=lambda item:
                -item.relevance_score
        )

        return SearchBatch(
            batch_id=_stable_id(
                "PLAN",
                search_plan,
            ),
            queries=queries,
            results=all_results,
        )


# ---------------------------------------------------------------------
# Search result -> prior-art format
# ---------------------------------------------------------------------

def convert_search_results_to_prior_art(
    results: Iterable[
        PatentSearchResult
    ],
) -> List[
    Dict[str, Any]
]:

    output = []

    for result in results:

        output.append(
            {
                "document_id":
                    result.result_id,

                "title":
                    result.title,

                "publication_number":
                    result.publication_number,

                "application_number":
                    result.application_number,

                "publication_date":
                    result.publication_date,

                "filing_date":
                    result.filing_date,

                "priority_date":
                    result.priority_date,

                "inventors":
                    result.inventors,

                "applicants":
                    result.applicants,

                "assignees":
                    result.assignees,

                "abstract":
                    result.abstract,

                "claims":
                    result.claims,

                "description":
                    result.description,

                "url":
                    result.url,

                "family_id":
                    result.family_id,

                "family_members":
                    result.family_members,

                "classifications":
                    result.classifications,

                "matched_queries":
                    result.matched_queries,

                "matched_terms":
                    result.matched_terms,

                "relevance_score":
                    result.relevance_score,

                "lexical_score":
                    result.lexical_score,

                "technical_score":
                    result.technical_score,

                "metadata_score":
                    result.metadata_score,

                "retrieval_score":
                    result.retrieval_score,

                "source":
                    result.provider,

                "source_metadata":
                    result.source_metadata,

                "retrieved_at":
                    result.retrieved_at,

                "review_notice":
                    (
                        "Search relevance does not "
                        "establish legal prior-art status."
                    ),
            }
        )

    return output


# ---------------------------------------------------------------------
# Evidence candidate generation
# ---------------------------------------------------------------------

def build_evidence_candidates(
    results: Iterable[
        PatentSearchResult
    ],
    *,
    claim_number: Optional[int] = None,
) -> List[
    Dict[str, Any]
]:

    candidates = []

    for result in results:

        candidate = {
            "document_id":
                result.result_id,

            "claim_number":
                claim_number,

            "title":
                result.title,

            "publication_number":
                result.publication_number,

            "source":
                result.provider,

            "url":
                result.url,

            "abstract":
                result.abstract,

            "claims":
                result.claims,

            "description":
                result.description,

            "relevance_score":
                result.relevance_score,

            "matched_terms":
                result.matched_terms,

            "matched_queries":
                result.matched_queries,

            "priority_date":
                result.priority_date,

            "publication_date":
                result.publication_date,

            "evidence_status":
                "CANDIDATE",

            "review_required":
                True,

            "reason":
                (
                    "Retrieved because of "
                    "technical/query similarity; "
                    "substantive disclosure must be "
                    "verified."
                ),
        }

        candidates.append(
            candidate
        )

    return candidates


# ---------------------------------------------------------------------
# Database links
# ---------------------------------------------------------------------

def generate_database_links(
    query: str,
) -> Dict[str, str]:

    return PatentProviderLinks.build(
        query
    )


# ---------------------------------------------------------------------
# High-level API
# ---------------------------------------------------------------------

def create_search_engine(
    *,
    manual_results: Optional[
        Iterable[
            Dict[str, Any]
        ]
    ] = None,
) -> PatentSearchEngine:

    engine = PatentSearchEngine()

    if manual_results is not None:

        engine.register_provider(
            ManualSearchProvider(
                manual_results
            )
        )

    return engine


def search_patent_documents(
    claims: Iterable[Any],
    *,
    manual_results: Optional[
        Iterable[
            Dict[str, Any]
        ]
    ] = None,
    providers: Optional[
        Sequence[str]
    ] = None,
    max_results_per_query: int = 20,
) -> Dict[str, Any]:

    engine = PatentSearchEngine(
        max_results_per_query=(
            max_results_per_query
        )
    )

    if manual_results is not None:

        engine.register_provider(
            ManualSearchProvider(
                manual_results
            )
        )

    batch = engine.search_claims(
        claims,
        providers=(
            providers
            or [
                PROVIDER_MANUAL
            ]
        ),
    )

    return batch.to_dict()


# ---------------------------------------------------------------------
# Query inspection
# ---------------------------------------------------------------------

def build_search_queries(
    claims: Iterable[Any],
) -> List[
    Dict[str, Any]
]:

    builder = (
        PatentSearchQueryBuilder()
    )

    return [
        query.to_dict()
        for query
        in builder.build(
            claims
        )
    ]


def inspect_query_links(
    query: str,
) -> Dict[str, str]:

    return generate_database_links(
        query
    )


# ---------------------------------------------------------------------
# Search statistics
# ---------------------------------------------------------------------

def search_statistics(
    batch: Dict[str, Any],
) -> Dict[str, Any]:

    results = batch.get(
        "results",
        []
    )

    queries = batch.get(
        "queries",
        []
    )

    providers = {}

    for result in results:

        provider = result.get(
            "provider",
            "unknown",
        )

        providers[
            provider
        ] = (
            providers.get(
                provider,
                0,
            )
            + 1
        )

    scores = [
        _safe_float(
            result.get(
                "relevance_score",
                0.0,
            )
        )
        for result in results
    ]

    return {
        "query_count":
            len(queries),

        "result_count":
            len(results),

        "provider_counts":
            providers,

        "average_relevance":
            (
                sum(scores)
                / len(scores)
                if scores
                else 0.0
            ),

        "highest_relevance":
            (
                max(scores)
                if scores
                else 0.0
            ),

        "unique_publications":
            len(
                {
                    _normalize(
                        result.get(
                            "publication_number",
                            "",
                        )
                    )
                    for result
                    in results
                    if result.get(
                        "publication_number",
                        "",
                    )
                }
            ),

        "review_required":
            True,

        "legal_status_note":
            (
                "Search retrieval and relevance "
                "scores do not determine legal "
                "prior-art status."
            ),
    }


# ---------------------------------------------------------------------
# Backward-compatible helpers
# ---------------------------------------------------------------------

def generate_search_queries(
    claims: Iterable[Any],
) -> List[str]:

    return [
        query.query
        for query
        in PatentSearchQueryBuilder()
        .build(
            claims
        )
    ]


def normalize_search_results(
    results: Iterable[
        Dict[str, Any]
    ],
    *,
    provider: str = PROVIDER_MANUAL,
) -> List[
    Dict[str, Any]
]:

    normalized = []

    for item in results:

        result = (
            PatentResultNormalizer
            .normalize(
                _to_dict(item),
                provider=provider,
            )
        )

        normalized.append(
            result.to_dict()
        )

    return normalized


def rank_search_results(
    results: Iterable[
        Dict[str, Any]
    ],
    query: str,
) -> List[
    Dict[str, Any]
]:

    search_query = PatentSearchQuery(
        query_id=_stable_id(
            "Q",
            query,
        ),
        claim_number=0,
        query=query,
        query_type="MANUAL",
        concepts=_tokenize(
            query
        ),
    )

    scorer = (
        PatentRelevanceScorer()
    )

    normalized = []

    for item in results:

        result = (
            PatentResultNormalizer
            .normalize(
                _to_dict(item),
                provider=(
                    item.get(
                        "provider",
                        PROVIDER_MANUAL,
                    )
                    if isinstance(
                        item,
                        dict,
                    )
                    else PROVIDER_MANUAL
                ),
                query=search_query,
            )
        )

        result = scorer.score(
            search_query,
            result,
        )

        normalized.append(
            result
        )

    normalized.sort(
        key=lambda item:
            -item.relevance_score
    )

    return [
        item.to_dict()
        for item
        in normalized
    ]


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

__all__ = [
    "SEARCH_ENGINE_VERSION",

    "PROVIDER_GOOGLE_PATENTS",
    "PROVIDER_ESPACENET",
    "PROVIDER_WIPO",
    "PROVIDER_MANUAL",
    "PROVIDER_API",

    "PatentSearchQuery",
    "PatentSearchResult",
    "SearchBatch",

    "PatentSearchQueryBuilder",
    "PatentProviderLinks",

    "SearchProvider",
    "ManualSearchProvider",

    "PatentResultNormalizer",
    "PatentRelevanceScorer",
    "PatentResultDeduplicator",

    "PatentSearchEngine",

    "convert_search_results_to_prior_art",
    "build_evidence_candidates",

    "generate_database_links",

    "create_search_engine",
    "search_patent_documents",

    "build_search_queries",
    "inspect_query_links",

    "search_statistics",

    "generate_search_queries",
    "normalize_search_results",
    "rank_search_results",
]
