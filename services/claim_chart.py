"""
Patent Claim Chart Engine V3
============================

Purpose
-------
Build evidence-grounded claim charts connecting:

    Patent Claim
        ↓
    Claim Limitations
        ↓
    Prior-Art Candidates
        ↓
    Evidence
        ↓
    Disclosure Status
        ↓
    Human Review

The engine is intentionally conservative.

It does NOT determine legal novelty or infringement.

It identifies technical overlap and maps supplied evidence to
individual claim limitations.

Version
-------
3.0.0
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


CLAIM_CHART_VERSION = "3.0.0"


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def _normalize(value: Any) -> str:
    text = _clean(value).lower()

    text = re.sub(
        r"[^\w\s.%/\-]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def _stable_id(
    prefix: str,
    value: str,
) -> str:

    digest = hashlib.sha256(
        _clean(value).encode(
            "utf-8"
        )
    ).hexdigest()[:12]

    return f"{prefix}-{digest}"


def _as_list(
    value: Any,
) -> List[Any]:

    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def _tokenize(
    text: str,
) -> List[str]:

    return [
        token
        for token in _normalize(
            text
        ).split()
        if len(token) >= 2
    ]


def _token_set(
    text: str,
) -> set:

    return set(
        _tokenize(text)
    )


def _token_overlap(
    text_a: str,
    text_b: str,
) -> float:

    a = _token_set(text_a)
    b = _token_set(text_b)

    if not a or not b:
        return 0.0

    return len(
        a.intersection(b)
    ) / len(
        a.union(b)
    )


def _keyword_overlap(
    limitation: str,
    evidence: str,
) -> List[str]:

    limitation_tokens = _token_set(
        limitation
    )

    evidence_tokens = _token_set(
        evidence
    )

    return sorted(
        limitation_tokens
        .intersection(
            evidence_tokens
        )
    )


# ---------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------

@dataclass
class ChartEvidence:

    evidence_id: str
    source: str
    text: str
    page: Any = ""
    section: str = ""
    score: float = 0.0
    matched_terms: List[str] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LimitationChartRow:

    row_id: str
    claim_number: Any
    limitation_id: str
    limitation_text: str
    limitation_type: str
    document_id: str
    document_title: str
    publication_number: str
    disclosure_status: str
    similarity: float
    evidence: List[Dict[str, Any]]
    matched_terms: List[str]
    reasoning: str
    confidence: float
    review_required: bool = True

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------
# Disclosure states
# ---------------------------------------------------------------------

EXPLICIT = "EXPLICIT"
PARTIAL = "PARTIAL"
INFERRED = "INFERRED"
NOT_FOUND = "NOT_FOUND"
UNCERTAIN = "UNCERTAIN"


# ---------------------------------------------------------------------
# Claim normalization
# ---------------------------------------------------------------------

def normalize_claim(
    claim: Any,
    fallback_number: Optional[int] = None,
) -> Dict[str, Any]:

    if isinstance(
        claim,
        str,
    ):

        return {
            "claim_number":
                fallback_number,

            "text":
                _clean(claim),

            "limitations":
                [],
        }

    if not isinstance(
        claim,
        dict,
    ):

        return {
            "claim_number":
                fallback_number,

            "text":
                _clean(claim),

            "limitations":
                [],
        }

    number = claim.get(
        "claim_number",
        claim.get(
            "number",
            fallback_number,
        ),
    )

    limitations = []

    for index, limitation in enumerate(
        _as_list(
            claim.get(
                "limitations",
                [],
            )
        ),
        start=1,
    ):

        if isinstance(
            limitation,
            dict,
        ):

            text = _clean(
                limitation.get(
                    "text",
                    limitation.get(
                        "limitation_text",
                        "",
                    ),
                )
            )

            limitation_id = _clean(
                limitation.get(
                    "id",
                    limitation.get(
                        "limitation_id",
                        "",
                    ),
                )
            )

            limitation_type = _clean(
                limitation.get(
                    "type",
                    limitation.get(
                        "limitation_type",
                        "",
                    ),
                )
            )

        else:

            text = _clean(
                limitation
            )

            limitation_id = ""

            limitation_type = ""

        if not limitation_id:

            limitation_id = _stable_id(
                "L",
                f"{number}|{index}|{text}",
            )

        limitations.append(
            {
                "id":
                    limitation_id,

                "text":
                    text,

                "type":
                    limitation_type,
            }
        )

    return {
        "claim_number":
            number,

        "text":
            _clean(
                claim.get(
                    "text",
                    claim.get(
                        "claim_text",
                        "",
                    ),
                )
            ),

        "limitations":
            limitations,
    }


def normalize_claims(
    claims: Iterable[Any],
) -> List[Dict[str, Any]]:

    return [
        normalize_claim(
            claim,
            fallback_number=index,
        )
        for index, claim
        in enumerate(
            claims,
            start=1,
        )
    ]


# ---------------------------------------------------------------------
# Document normalization
# ---------------------------------------------------------------------

def normalize_prior_art(
    document: Any,
    fallback_id: Optional[str] = None,
) -> Dict[str, Any]:

    if isinstance(
        document,
        str,
    ):

        return {
            "document_id":
                fallback_id
                or _stable_id(
                    "DOC",
                    document,
                ),

            "title":
                "",

            "publication_number":
                "",

            "text":
                document,

            "evidence":
                [],
        }

    if not isinstance(
        document,
        dict,
    ):

        document = {
            "text":
                _clean(document)
        }

    document_id = _clean(
        document.get(
            "document_id",
            document.get(
                "candidate_id",
                document.get(
                    "id",
                    fallback_id
                    or "",
                ),
            ),
        )
    )

    title = _clean(
        document.get(
            "title",
            "",
        )
    )

    publication = _clean(
        document.get(
            "publication_number",
            document.get(
                "publication",
                "",
            ),
        )
    )

    text = _clean(
        document.get(
            "text",
            document.get(
                "content",
                document.get(
                    "abstract",
                    "",
                ),
            ),
        )
    )

    evidence = _as_list(
        document.get(
            "evidence",
            document.get(
                "evidence_items",
                [],
            ),
        )
    )

    if not document_id:

        document_id = _stable_id(
            "DOC",
            title
            + "|"
            + publication
            + "|"
            + text,
        )

    normalized_evidence = []

    for index, item in enumerate(
        evidence,
        start=1,
    ):

        if isinstance(
            item,
            dict,
        ):

            evidence_text = _clean(
                item.get(
                    "text",
                    item.get(
                        "content",
                        "",
                    ),
                )
            )

            evidence_id = _clean(
                item.get(
                    "evidence_id",
                    item.get(
                        "id",
                        "",
                    ),
                )
            )

            source = _clean(
                item.get(
                    "source",
                    title
                    or publication,
                )
            )

            page = item.get(
                "page",
                item.get(
                    "page_number",
                    "",
                ),
            )

            section = _clean(
                item.get(
                    "section",
                    "",
                )
            )

        else:

            evidence_text = _clean(
                item
            )

            evidence_id = ""

            source = (
                title
                or publication
            )

            page = ""

            section = ""

        if not evidence_id:

            evidence_id = _stable_id(
                "E",
                f"{document_id}|{index}|{evidence_text}",
            )

        normalized_evidence.append(
            {
                "evidence_id":
                    evidence_id,

                "source":
                    source,

                "text":
                    evidence_text,

                "page":
                    page,

                "section":
                    section,
            }
        )

    return {
        "document_id":
            document_id,

        "title":
            title,

        "publication_number":
            publication,

        "text":
            text,

        "evidence":
            normalized_evidence,
    }


# ---------------------------------------------------------------------
# Evidence extraction
# ---------------------------------------------------------------------

def create_evidence_from_document(
    document: Dict[str, Any],
) -> List[Dict[str, Any]]:

    existing = _as_list(
        document.get(
            "evidence",
            [],
        )
    )

    if existing:
        return [
            item
            for item in existing
            if isinstance(
                item,
                dict,
            )
        ]

    text = _clean(
        document.get(
            "text",
            "",
        )
    )

    if not text:
        return []

    # Paragraph-level evidence
    chunks = re.split(
        r"\n{2,}|(?<=[.!?])\s+(?=[A-Z])",
        text,
    )

    evidence = []

    for index, chunk in enumerate(
        chunks,
        start=1,
    ):

        chunk = _clean(
            chunk
        )

        if not chunk:
            continue

        evidence.append(
            {
                "evidence_id":
                    _stable_id(
                        "E",
                        document["document_id"]
                        + "|"
                        + str(index)
                        + "|"
                        + chunk,
                    ),

                "source":
                    document.get(
                        "title",
                        document.get(
                            "publication_number",
                            document[
                                "document_id"
                            ],
                        ),
                    ),

                "text":
                    chunk,

                "page":
                    "",

                "section":
                    "",
            }
        )

    return evidence


# ---------------------------------------------------------------------
# Limitation matching
# ---------------------------------------------------------------------

def rank_evidence(
    limitation_text: str,
    evidence_items: Iterable[Dict[str, Any]],
    top_k: int = 10,
) -> List[ChartEvidence]:

    candidates = []

    for item in evidence_items:

        if not isinstance(
            item,
            dict,
        ):
            continue

        evidence_text = _clean(
            item.get(
                "text",
                item.get(
                    "content",
                    "",
                ),
            )
        )

        if not evidence_text:
            continue

        overlap = _token_overlap(
            limitation_text,
            evidence_text,
        )

        matched_terms = _keyword_overlap(
            limitation_text,
            evidence_text,
        )

        # Small boost when the limitation's important phrase
        # occurs directly in the evidence.

        normalized_limitation = _normalize(
            limitation_text
        )

        normalized_evidence = _normalize(
            evidence_text
        )

        phrase_bonus = 0.0

        if (
            normalized_limitation
            and normalized_limitation
            in normalized_evidence
        ):
            phrase_bonus = 0.40

        score = min(
            1.0,
            overlap + phrase_bonus,
        )

        candidates.append(
            ChartEvidence(
                evidence_id=_clean(
                    item.get(
                        "evidence_id",
                        item.get(
                            "id",
                            "",
                        ),
                    )
                ),
                source=_clean(
                    item.get(
                        "source",
                        "",
                    )
                ),
                text=evidence_text,
                page=item.get(
                    "page",
                    "",
                ),
                section=_clean(
                    item.get(
                        "section",
                        "",
                    )
                ),
                score=round(
                    score,
                    4,
                ),
                matched_terms=matched_terms,
            )
        )

    candidates.sort(
        key=lambda item:
            item.score,
        reverse=True,
    )

    return candidates[:top_k]


# ---------------------------------------------------------------------
# Disclosure classification
# ---------------------------------------------------------------------

def classify_disclosure(
    evidence: List[ChartEvidence],
) -> Tuple[str, float]:

    if not evidence:
        return (
            NOT_FOUND,
            0.0,
        )

    top_score = evidence[0].score

    if top_score >= 0.85:

        return (
            EXPLICIT,
            min(
                0.98,
                top_score,
            ),
        )

    if top_score >= 0.60:

        return (
            PARTIAL,
            top_score,
        )

    if top_score >= 0.35:

        return (
            INFERRED,
            top_score,
        )

    if top_score >= 0.15:

        return (
            UNCERTAIN,
            top_score,
        )

    return (
        NOT_FOUND,
        top_score,
    )


# ---------------------------------------------------------------------
# Reasoning
# ---------------------------------------------------------------------

def build_reasoning(
    limitation_text: str,
    status: str,
    evidence: List[ChartEvidence],
) -> str:

    if status == EXPLICIT:

        return (
            "The supplied evidence contains substantial "
            "technical-term overlap with the limitation. "
            "The exact disclosure should still be verified "
            "against the source document."
        )

    if status == PARTIAL:

        return (
            "The evidence appears to disclose part of the "
            "limitation, but one or more aspects require "
            "additional verification."
        )

    if status == INFERRED:

        return (
            "The evidence has related technical terminology, "
            "but the limitation is not established directly "
            "from the available text."
        )

    if status == UNCERTAIN:

        return (
            "The available evidence contains limited overlap. "
            "A human reviewer should inspect the source document "
            "before relying on this mapping."
        )

    return (
        "No sufficiently relevant evidence was identified "
        "in the supplied material."
    )


# ---------------------------------------------------------------------
# Single limitation chart row
# ---------------------------------------------------------------------

def build_limitation_row(
    claim_number: Any,
    limitation: Dict[str, Any],
    document: Dict[str, Any],
    top_k: int = 5,
) -> LimitationChartRow:

    limitation_text = _clean(
        limitation.get(
            "text",
            "",
        )
    )

    evidence_items = (
        create_evidence_from_document(
            document
        )
    )

    evidence = rank_evidence(
        limitation_text,
        evidence_items,
        top_k=top_k,
    )

    status, confidence = (
        classify_disclosure(
            evidence
        )
    )

    matched_terms = sorted(
        {
            term
            for item in evidence
            for term in (
                item.matched_terms
                or []
            )
        }
    )

    return LimitationChartRow(
        row_id=_stable_id(
            "ROW",
            str(
                claim_number
            )
            + "|"
            + limitation.get(
                "id",
                "",
            )
            + "|"
            + document.get(
                "document_id",
                "",
            ),
        ),
        claim_number=claim_number,
        limitation_id=_clean(
            limitation.get(
                "id",
                "",
            )
        ),
        limitation_text=limitation_text,
        limitation_type=_clean(
            limitation.get(
                "type",
                "",
            )
        ),
        document_id=_clean(
            document.get(
                "document_id",
                "",
            )
        ),
        document_title=_clean(
            document.get(
                "title",
                "",
            )
        ),
        publication_number=_clean(
            document.get(
                "publication_number",
                "",
            )
        ),
        disclosure_status=status,
        similarity=(
            evidence[0].score
            if evidence
            else 0.0
        ),
        evidence=[
            item.to_dict()
            for item in evidence
        ],
        matched_terms=matched_terms,
        reasoning=build_reasoning(
            limitation_text,
            status,
            evidence,
        ),
        confidence=round(
            confidence,
            4,
        ),
        review_required=True,
    )


# ---------------------------------------------------------------------
# Full claim chart
# ---------------------------------------------------------------------

def build_claim_chart(
    claims: Iterable[Any],
    prior_art: Iterable[Any],
    *,
    top_k_evidence: int = 5,
) -> Dict[str, Any]:

    normalized_claims = normalize_claims(
        claims
    )

    normalized_documents = [
        normalize_prior_art(
            item,
            fallback_id=f"DOC-{index}",
        )
        for index, item
        in enumerate(
            prior_art,
            start=1,
        )
    ]

    rows = []

    for claim in normalized_claims:

        claim_number = claim.get(
            "claim_number"
        )

        limitations = _as_list(
            claim.get(
                "limitations",
                [],
            )
        )

        # If no structured limitations exist,
        # treat the complete claim as one review unit.

        if not limitations:

            limitations = [
                {
                    "id":
                        _stable_id(
                            "L",
                            claim.get(
                                "text",
                                "",
                            ),
                        ),

                    "text":
                        claim.get(
                            "text",
                            "",
                        ),

                    "type":
                        "claim",
                }
            ]

        for document in normalized_documents:

            for limitation in limitations:

                row = build_limitation_row(
                    claim_number,
                    limitation,
                    document,
                    top_k=top_k_evidence,
                )

                rows.append(
                    row.to_dict()
                )

    return {
        "success": True,

        "claim_chart_version":
            CLAIM_CHART_VERSION,

        "generated_at":
            _utc_now(),

        "claim_count":
            len(
                normalized_claims
            ),

        "document_count":
            len(
                normalized_documents
            ),

        "row_count":
            len(rows),

        "rows":
            rows,

        "statistics":
            calculate_chart_statistics(
                rows
            ),

        "notice":
            (
                "Disclosure mappings are evidence-review signals. "
                "They do not constitute a legal novelty, validity, "
                "infringement, or patentability determination."
            ),
    }


# ---------------------------------------------------------------------
# Chart statistics
# ---------------------------------------------------------------------

def calculate_chart_statistics(
    rows: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:

    rows = [
        row
        for row in rows
        if isinstance(
            row,
            dict,
        )
    ]

    status_counts = {
        EXPLICIT: 0,
        PARTIAL: 0,
        INFERRED: 0,
        NOT_FOUND: 0,
        UNCERTAIN: 0,
    }

    for row in rows:

        status = row.get(
            "disclosure_status",
            UNCERTAIN,
        )

        if status not in status_counts:

            status = UNCERTAIN

        status_counts[
            status
        ] += 1

    total = len(
        rows
    )

    supported = (
        status_counts[
            EXPLICIT
        ]
        + status_counts[
            PARTIAL
        ]
    )

    return {
        "total_rows":
            total,

        "explicit":
            status_counts[
                EXPLICIT
            ],

        "partial":
            status_counts[
                PARTIAL
            ],

        "inferred":
            status_counts[
                INFERRED
            ],

        "uncertain":
            status_counts[
                UNCERTAIN
            ],

        "not_found":
            status_counts[
                NOT_FOUND
            ],

        "supported_or_partially_supported":
            supported,

        "coverage_ratio":
            round(
                supported / total,
                4,
            )
            if total
            else 0.0,
    }


# ---------------------------------------------------------------------
# Claim-level coverage
# ---------------------------------------------------------------------

def calculate_claim_coverage(
    chart: Dict[str, Any],
) -> Dict[str, Any]:

    rows = _as_list(
        chart.get(
            "rows",
            [],
        )
    )

    claims: Dict[
        str,
        List[Dict[str, Any]]
    ] = {}

    for row in rows:

        if not isinstance(
            row,
            dict,
        ):
            continue

        claim_number = str(
            row.get(
                "claim_number",
                "",
            )
        )

        claims.setdefault(
            claim_number,
            [],
        ).append(
            row
        )

    result = {}

    for claim_number, claim_rows in claims.items():

        total = len(
            claim_rows
        )

        explicit = sum(
            row.get(
                "disclosure_status"
            ) == EXPLICIT
            for row in claim_rows
        )

        partial = sum(
            row.get(
                "disclosure_status"
            ) == PARTIAL
            for row in claim_rows
        )

        not_found = sum(
            row.get(
                "disclosure_status"
            ) == NOT_FOUND
            for row in claim_rows
        )

        result[
            claim_number
        ] = {
            "limitation_count":
                total,

            "explicit":
                explicit,

            "partial":
                partial,

            "not_found":
                not_found,

            "coverage":
                round(
                    (
                        explicit
                        + partial
                    )
                    / total,
                    4,
                )
                if total
                else 0.0,
        }

    return result


# ---------------------------------------------------------------------
# Best document per claim
# ---------------------------------------------------------------------

def rank_documents_for_claim(
    chart: Dict[str, Any],
    claim_number: Any,
) -> List[Dict[str, Any]]:

    target = str(
        claim_number
    )

    rows = [
        row
        for row in _as_list(
            chart.get(
                "rows",
                [],
            )
        )
        if isinstance(
            row,
            dict,
        )
        and str(
            row.get(
                "claim_number",
                "",
            )
        ) == target
    ]

    documents: Dict[
        str,
        Dict[str, Any]
    ] = {}

    for row in rows:

        document_id = row.get(
            "document_id",
            "",
        )

        if document_id not in documents:

            documents[
                document_id
            ] = {
                "document_id":
                    document_id,

                "title":
                    row.get(
                        "document_title",
                        "",
                    ),

                "publication_number":
                    row.get(
                        "publication_number",
                        "",
                    ),

                "rows":
                    [],

                "explicit":
                    0,

                "partial":
                    0,

                "inferred":
                    0,

                "uncertain":
                    0,

                "not_found":
                    0,
            }

        documents[
            document_id
        ]["rows"].append(
            row
        )

        status = row.get(
            "disclosure_status",
            UNCERTAIN,
        )

        if status == EXPLICIT:
            documents[
                document_id
            ]["explicit"] += 1

        elif status == PARTIAL:
            documents[
                document_id
            ]["partial"] += 1

        elif status == INFERRED:
            documents[
                document_id
            ]["inferred"] += 1

        elif status == UNCERTAIN:
            documents[
                document_id
            ]["uncertain"] += 1

        elif status == NOT_FOUND:
            documents[
                document_id
            ]["not_found"] += 1

    for document in documents.values():

        total = len(
            document["rows"]
        )

        document[
            "coverage"
        ] = round(
            (
                document["explicit"]
                + 0.5
                * document["partial"]
            )
            / total,
            4,
        ) if total else 0.0

    return sorted(
        documents.values(),
        key=lambda item:
            item["coverage"],
        reverse=True,
    )


# ---------------------------------------------------------------------
# Evidence graph
# ---------------------------------------------------------------------

def build_evidence_graph(
    chart: Dict[str, Any],
) -> Dict[str, Any]:

    nodes = []
    edges = []

    node_ids = set()

    def add_node(
        node_id: str,
        node_type: str,
        label: str,
        metadata: Optional[
            Dict[str, Any]
        ] = None,
    ):

        if node_id in node_ids:
            return

        node_ids.add(
            node_id
        )

        nodes.append(
            {
                "id":
                    node_id,

                "type":
                    node_type,

                "label":
                    label,

                "metadata":
                    metadata
                    or {},
            }
        )

    for row in _as_list(
        chart.get(
            "rows",
            [],
        )
    ):

        if not isinstance(
            row,
            dict,
        ):
            continue

        claim_id = (
            "CLAIM-"
            + str(
                row.get(
                    "claim_number",
                    "",
                )
            )
        )

        limitation_id = (
            row.get(
                "limitation_id",
                "",
            )
            or _stable_id(
                "L",
                row.get(
                    "limitation_text",
                    "",
                ),
            )
        )

        document_id = row.get(
            "document_id",
            "",
        )

        add_node(
            claim_id,
            "claim",
            f"Claim {row.get('claim_number', '')}",
        )

        add_node(
            limitation_id,
            "limitation",
            row.get(
                "limitation_text",
                "",
            ),
            {
                "type":
                    row.get(
                        "limitation_type",
                        "",
                    )
            },
        )

        add_node(
            document_id,
            "prior_art",
            row.get(
                "document_title",
                document_id,
            ),
            {
                "publication_number":
                    row.get(
                        "publication_number",
                        "",
                    )
            },
        )

        edges.append(
            {
                "source":
                    claim_id,

                "target":
                    limitation_id,

                "relationship":
                    "HAS_LIMITATION",
            }
        )

        edges.append(
            {
                "source":
                    limitation_id,

                "target":
                    document_id,

                "relationship":
                    row.get(
                        "disclosure_status",
                        UNCERTAIN,
                    ),

                "confidence":
                    row.get(
                        "confidence",
                        0.0,
                    ),
            }
        )

        for evidence in _as_list(
            row.get(
                "evidence",
                [],
            )
        ):

            if not isinstance(
                evidence,
                dict,
            ):
                continue

            evidence_id = evidence.get(
                "evidence_id",
                "",
            )

            if not evidence_id:
                continue

            add_node(
                evidence_id,
                "evidence",
                evidence.get(
                    "text",
                    "",
                ),
                {
                    "page":
                        evidence.get(
                            "page",
                            "",
                        ),

                    "section":
                        evidence.get(
                            "section",
                            "",
                        ),

                    "source":
                        evidence.get(
                            "source",
                            "",
                        ),
                },
            )

            edges.append(
                {
                    "source":
                        limitation_id,

                    "target":
                        evidence_id,

                    "relationship":
                        "SUPPORTED_BY",

                    "score":
                        evidence.get(
                            "score",
                            0.0,
                        ),
                }
            )

    return {
        "nodes":
            nodes,

        "edges":
            edges,

        "node_count":
            len(nodes),

        "edge_count":
            len(edges),
    }


# ---------------------------------------------------------------------
# Export-friendly table
# ---------------------------------------------------------------------

def flatten_claim_chart(
    chart: Dict[str, Any],
) -> List[Dict[str, Any]]:

    rows = []

    for item in _as_list(
        chart.get(
            "rows",
            [],
        )
    ):

        if not isinstance(
            item,
            dict,
        ):
            continue

        evidence = _as_list(
            item.get(
                "evidence",
                [],
            )
        )

        best_evidence = (
            evidence[0]
            if evidence
            and isinstance(
                evidence[0],
                dict,
            )
            else {}
        )

        rows.append(
            {
                "Claim":
                    item.get(
                        "claim_number",
                        "",
                    ),

                "Limitation ID":
                    item.get(
                        "limitation_id",
                        "",
                    ),

                "Limitation":
                    item.get(
                        "limitation_text",
                        "",
                    ),

                "Prior Art":
                    item.get(
                        "document_title",
                        "",
                    ),

                "Publication":
                    item.get(
                        "publication_number",
                        "",
                    ),

                "Disclosure":
                    item.get(
                        "disclosure_status",
                        "",
                    ),

                "Similarity":
                    item.get(
                        "similarity",
                        0.0,
                    ),

                "Evidence":
                    best_evidence.get(
                        "text",
                        "",
                    ),

                "Page":
                    best_evidence.get(
                        "page",
                        "",
                    ),

                "Confidence":
                    item.get(
                        "confidence",
                        0.0,
                    ),
            }
        )

    return rows


# ---------------------------------------------------------------------
# Human-readable summary
# ---------------------------------------------------------------------

def summarize_claim_chart(
    chart: Dict[str, Any],
) -> str:

    stats = chart.get(
        "statistics",
        {},
    )

    return (
        f"The claim chart contains "
        f"{stats.get('total_rows', 0)} limitation-to-document "
        f"mapping(s). "
        f"{stats.get('explicit', 0)} are classified as explicit, "
        f"{stats.get('partial', 0)} as partial, "
        f"{stats.get('inferred', 0)} as inferred, "
        f"{stats.get('uncertain', 0)} as uncertain, and "
        f"{stats.get('not_found', 0)} as not found. "
        "These classifications are evidence-review signals and "
        "require verification against the source documents."
    )


# ---------------------------------------------------------------------
# Backward-compatible helpers
# ---------------------------------------------------------------------

def create_claim_chart(
    claims: Iterable[Any],
    prior_art: Iterable[Any],
) -> Dict[str, Any]:

    return build_claim_chart(
        claims,
        prior_art,
    )


def generate_claim_chart(
    claims: Iterable[Any],
    prior_art: Iterable[Any],
) -> Dict[str, Any]:

    return build_claim_chart(
        claims,
        prior_art,
    )


def build_chart(
    claims: Iterable[Any],
    prior_art: Iterable[Any],
) -> Dict[str, Any]:

    return build_claim_chart(
        claims,
        prior_art,
    )


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

__all__ = [
    "CLAIM_CHART_VERSION",
    "EXPLICIT",
    "PARTIAL",
    "INFERRED",
    "NOT_FOUND",
    "UNCERTAIN",
    "ChartEvidence",
    "LimitationChartRow",
    "normalize_claim",
    "normalize_claims",
    "normalize_prior_art",
    "create_evidence_from_document",
    "rank_evidence",
    "classify_disclosure",
    "build_reasoning",
    "build_limitation_row",
    "build_claim_chart",
    "calculate_chart_statistics",
    "calculate_claim_coverage",
    "rank_documents_for_claim",
    "build_evidence_graph",
    "flatten_claim_chart",
    "summarize_claim_chart",
    "create_claim_chart",
    "generate_claim_chart",
    "build_chart",
]
