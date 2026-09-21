"""
Evidence Engine V3
==================

Purpose
-------
Build a traceable evidence graph connecting:

    Claim
      ↓
    Limitation
      ↓
    Prior-art document
      ↓
    Evidence passage
      ↓
    Retrieval / disclosure strength
      ↓
    Reviewer decision

The engine can consume:
    - claim_analyzer output
    - document_parser output
    - prior_art output
    - semantic_search output
    - claim_chart output

Important
---------
This engine identifies and ranks evidence.

It does NOT independently determine:
    - novelty
    - inventive step
    - patentability
    - infringement
    - validity
    - legal anticipation

A human/legal review layer remains necessary.

Version
-------
3.0.0
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence


EVIDENCE_ENGINE_VERSION = "3.0.0"


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
    text = _clean(
        value
    ).lower()

    text = re.sub(
        r"[^a-z0-9\s\-/\.]",
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


def _tokenize(
    text: str,
) -> List[str]:

    normalized = _normalize(
        text
    )

    if not normalized:
        return []

    return normalized.split()


def _meaningful_tokens(
    text: str,
) -> List[str]:

    stop_words = {
        "the",
        "and",
        "or",
        "of",
        "to",
        "a",
        "an",
        "in",
        "on",
        "for",
        "with",
        "by",
        "from",
        "is",
        "are",
        "was",
        "were",
        "be",
        "being",
        "been",
        "as",
        "at",
        "that",
        "this",
        "it",
        "its",
        "wherein",
        "said",
        "comprising",
        "including",
        "having",
    }

    return [
        token
        for token in _tokenize(
            text
        )
        if token not in stop_words
        and len(token) > 2
    ]


def _token_overlap(
    text_a: str,
    text_b: str,
) -> float:

    a = set(
        _meaningful_tokens(
            text_a
        )
    )

    b = set(
        _meaningful_tokens(
            text_b
        )
    )

    if not a or not b:
        return 0.0

    return len(
        a.intersection(b)
    ) / len(
        a.union(b)
    )


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:
        return float(value)
    except Exception:
        return default


def _clamp(
    value: float,
    low: float = 0.0,
    high: float = 1.0,
) -> float:

    return max(
        low,
        min(
            high,
            value,
        ),
    )


# ---------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------

@dataclass
class EvidencePassage:

    evidence_id: str
    document_id: str
    passage: str
    source: str = ""
    page: Optional[int] = None
    paragraph_id: str = ""
    semantic_score: float = 0.0
    lexical_score: float = 0.0
    combined_score: float = 0.0
    disclosure_status: str = "UNCERTAIN"
    rationale: str = ""

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(
            self
        )


@dataclass
class LimitationEvidence:

    limitation_id: str
    limitation_text: str
    evidence: List[EvidencePassage]
    best_score: float
    coverage: float
    status: str

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        data = asdict(
            self
        )

        data["evidence"] = [
            item.to_dict()
            if isinstance(
                item,
                EvidencePassage,
            )
            else item
            for item in self.evidence
        ]

        return data


@dataclass
class ClaimEvidence:

    claim_number: int
    claim_text: str
    limitations: List[LimitationEvidence]
    claim_coverage: float
    evidence_count: int
    status: str

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        data = asdict(
            self
        )

        data["limitations"] = [
            item.to_dict()
            if isinstance(
                item,
                LimitationEvidence,
            )
            else item
            for item in self.limitations
        ]

        return data


# ---------------------------------------------------------------------
# Document normalization
# ---------------------------------------------------------------------

def normalize_documents(
    documents: Iterable[Any],
) -> List[Dict[str, Any]]:

    normalized = []

    for index, document in enumerate(
        documents,
        start=1,
    ):

        if isinstance(
            document,
            dict,
        ):

            document_id = _clean(
                document.get(
                    "document_id",
                    document.get(
                        "id",
                        "",
                    ),
                )
            )

            title = _clean(
                document.get(
                    "title",
                    document.get(
                        "name",
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

            source = _clean(
                document.get(
                    "source",
                    document.get(
                        "url",
                        "",
                    ),
                )
            )

            metadata = document.get(
                "metadata",
                {},
            )

            if not isinstance(
                metadata,
                dict,
            ):
                metadata = {}

            if not document_id:

                document_id = _stable_id(
                    "DOC",
                    f"{title}|{text}|{index}",
                )

            normalized.append(
                {
                    "document_id":
                        document_id,

                    "title":
                        title,

                    "text":
                        text,

                    "source":
                        source,

                    "metadata":
                        metadata,
                }
            )

        else:

            text = _clean(
                document
            )

            if not text:
                continue

            normalized.append(
                {
                    "document_id":
                        _stable_id(
                            "DOC",
                            f"{index}|{text}",
                        ),

                    "title":
                        "",

                    "text":
                        text,

                    "source":
                        "",

                    "metadata":
                        {},
                }
            )

    return [
        item
        for item
        in normalized
        if item.get(
            "text"
        )
    ]


# ---------------------------------------------------------------------
# Limitation normalization
# ---------------------------------------------------------------------

def normalize_limitations(
    claim: Any,
) -> List[Dict[str, Any]]:

    if isinstance(
        claim,
        dict,
    ):

        limitations = claim.get(
            "limitations",
            []
        )

        if limitations:

            result = []

            for index, limitation in enumerate(
                limitations,
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
                                "limitation",
                                limitation.get(
                                    "description",
                                    "",
                                ),
                            ),
                        )
                    )

                    limitation_id = _clean(
                        limitation.get(
                            "limitation_id",
                            limitation.get(
                                "id",
                                "",
                            ),
                        )
                    )

                    if not limitation_id:

                        limitation_id = _stable_id(
                            "L",
                            f"{index}|{text}",
                        )

                    result.append(
                        {
                            "limitation_id":
                                limitation_id,

                            "text":
                                text,

                            "type":
                                limitation.get(
                                    "type",
                                    "",
                                ),
                        }
                    )

                else:

                    text = _clean(
                        limitation
                    )

                    result.append(
                        {
                            "limitation_id":
                                _stable_id(
                                    "L",
                                    f"{index}|{text}",
                                ),

                            "text":
                                text,

                            "type":
                                "",
                        }
                    )

            return [
                item
                for item
                in result
                if item["text"]
            ]

        claim_text = _clean(
            claim.get(
                "text",
                claim.get(
                    "claim_text",
                    "",
                ),
            )
        )

    else:

        claim_text = _clean(
            claim
        )

    if not claim_text:
        return []

    # Conservative fallback limitation splitting.
    parts = re.split(
        r";|\n|(?<=\.)\s+(?=(?:wherein|where|comprising|including|configured|having)\b)",
        claim_text,
        flags=re.IGNORECASE,
    )

    parts = [
        _clean(part)
        for part in parts
        if _clean(part)
    ]

    if not parts:
        parts = [
            claim_text
        ]

    return [
        {
            "limitation_id":
                _stable_id(
                    "L",
                    f"{index}|{part}",
                ),

            "text":
                part,

            "type":
                "",
        }
        for index, part
        in enumerate(
            parts,
            start=1,
        )
    ]


# ---------------------------------------------------------------------
# Evidence passage extraction
# ---------------------------------------------------------------------

def split_passages(
    text: str,
    max_length: int = 700,
) -> List[str]:

    text = _clean(
        text
    )

    if not text:
        return []

    paragraphs = re.split(
        r"\n{2,}",
        text,
    )

    passages = []

    for paragraph in paragraphs:

        paragraph = _clean(
            paragraph
        )

        if not paragraph:
            continue

        if len(paragraph) <= max_length:

            passages.append(
                paragraph
            )

            continue

        sentences = re.split(
            r"(?<=[.!?])\s+",
            paragraph,
        )

        current = ""

        for sentence in sentences:

            sentence = _clean(
                sentence
            )

            if not sentence:
                continue

            if (
                len(current)
                + len(sentence)
                + 1
                <= max_length
            ):

                current = (
                    current
                    + " "
                    + sentence
                ).strip()

            else:

                if current:
                    passages.append(
                        current
                    )

                current = sentence

        if current:
            passages.append(
                current
            )

    return passages


# ---------------------------------------------------------------------
# Passage scoring
# ---------------------------------------------------------------------

def score_passage(
    limitation_text: str,
    passage: str,
) -> Dict[str, Any]:

    lexical_score = (
        _token_overlap(
            limitation_text,
            passage,
        )
    )

    # A lightweight phrase-level signal.
    limitation_tokens = (
        _meaningful_tokens(
            limitation_text
        )
    )

    passage_normalized = _normalize(
        passage
    )

    phrase_hits = 0

    if limitation_tokens:

        # Check adjacent pairs for stronger evidence.
        for index in range(
            len(limitation_tokens) - 1
        ):

            phrase = (
                limitation_tokens[index]
                + " "
                + limitation_tokens[
                    index + 1
                ]
            )

            if phrase in passage_normalized:

                phrase_hits += 1

    phrase_bonus = min(
        0.20,
        phrase_hits * 0.05,
    )

    combined = _clamp(
        lexical_score
        + phrase_bonus
    )

    return {
        "lexical_score":
            lexical_score,

        "phrase_bonus":
            phrase_bonus,

        "combined_score":
            combined,
    }


def classify_evidence(
    score: float,
) -> str:

    score = _clamp(
        score
    )

    if score >= 0.80:
        return "EXPLICIT"

    if score >= 0.60:
        return "STRONG_MATCH"

    if score >= 0.40:
        return "PARTIAL"

    if score >= 0.20:
        return "WEAK_MATCH"

    return "UNCERTAIN"


def build_evidence_rationale(
    limitation_text: str,
    passage: str,
    score: float,
) -> str:

    terms = sorted(
        set(
            _meaningful_tokens(
                limitation_text
            )
        ).intersection(
            set(
                _meaningful_tokens(
                    passage
                )
            )
        )
    )

    if not terms:

        return (
            "No strong shared technical terms were identified. "
            "The passage should not be treated as substantive "
            "disclosure without further review."
        )

    if score >= 0.80:

        return (
            "The passage contains substantial textual overlap "
            "with the limitation. Review the full document and "
            "context before characterizing the disclosure."
        )

    if score >= 0.60:

        return (
            "The passage contains strong terminology overlap "
            "with the limitation but requires contextual review."
        )

    if score >= 0.40:

        return (
            "The passage contains partial terminology overlap. "
            "Additional evidence may be required."
        )

    return (
        "Only limited terminology overlap was identified."
    )


# ---------------------------------------------------------------------
# Evidence extraction
# ---------------------------------------------------------------------

def extract_evidence_for_limitation(
    limitation_id: str,
    limitation_text: str,
    document: Dict[str, Any],
    top_k: int = 5,
) -> List[EvidencePassage]:

    passages = split_passages(
        document.get(
            "text",
            "",
        )
    )

    scored = []

    for index, passage in enumerate(
        passages,
        start=1,
    ):

        scores = score_passage(
            limitation_text,
            passage,
        )

        scored.append(
            (
                scores[
                    "combined_score"
                ],
                scores[
                    "lexical_score"
                ],
                passage,
                index,
            )
        )

    scored.sort(
        key=lambda item: (
            item[0],
            item[1],
        ),
        reverse=True,
    )

    evidence = []

    for combined, lexical, passage, index in scored[
        :max(1, top_k)
    ]:

        evidence_id = _stable_id(
            "E",
            (
                f"{document.get('document_id')}|"
                f"{limitation_id}|"
                f"{index}|"
                f"{passage}"
            ),
        )

        evidence.append(
            EvidencePassage(
                evidence_id=evidence_id,
                document_id=document.get(
                    "document_id",
                    "",
                ),
                passage=passage,
                source=document.get(
                    "source",
                    "",
                ),
                page=_extract_page(
                    document,
                    index,
                ),
                paragraph_id=(
                    f"{document.get('document_id', '')}-P{index}"
                ),
                semantic_score=0.0,
                lexical_score=round(
                    lexical,
                    6,
                ),
                combined_score=round(
                    combined,
                    6,
                ),
                disclosure_status=(
                    classify_evidence(
                        combined
                    )
                ),
                rationale=(
                    build_evidence_rationale(
                        limitation_text,
                        passage,
                        combined,
                    )
                ),
            )
        )

    return evidence


def _extract_page(
    document: Dict[str, Any],
    passage_index: int,
) -> Optional[int]:

    metadata = document.get(
        "metadata",
        {},
    )

    if isinstance(
        metadata,
        dict,
    ):

        pages = metadata.get(
            "pages"
        )

        if isinstance(
            pages,
            list,
        ) and passage_index <= len(
            pages
        ):

            try:
                return int(
                    pages[
                        passage_index - 1
                    ]
                )
            except Exception:
                pass

        page = metadata.get(
            "page"
        )

        if page is not None:

            try:
                return int(
                    page
                )
            except Exception:
                pass

    return None


# ---------------------------------------------------------------------
# Semantic result integration
# ---------------------------------------------------------------------

def attach_semantic_scores(
    evidence: List[EvidencePassage],
    semantic_results: Iterable[Any],
) -> List[EvidencePassage]:

    semantic_map = {}

    for item in semantic_results:

        if hasattr(
            item,
            "to_dict",
        ):

            item = item.to_dict()

        if not isinstance(
            item,
            dict,
        ):
            continue

        document_id = _clean(
            item.get(
                "document_id",
                item.get(
                    "id",
                    "",
                ),
            )
        )

        if not document_id:
            continue

        semantic_map[
            document_id
        ] = _safe_float(
            item.get(
                "score",
                0.0,
            )
        )

    for item in evidence:

        semantic_score = (
            semantic_map.get(
                item.document_id,
                0.0,
            )
        )

        item.semantic_score = (
            semantic_score
        )

        # Combine semantic and lexical evidence.
        item.combined_score = round(
            0.65
            * semantic_score
            + 0.35
            * item.lexical_score,
            6,
        )

        item.disclosure_status = (
            classify_evidence(
                item.combined_score
            )
        )

    return evidence


# ---------------------------------------------------------------------
# Limitation evidence
# ---------------------------------------------------------------------

def build_limitation_evidence(
    limitation: Dict[str, Any],
    documents: Iterable[Dict[str, Any]],
    top_documents: Optional[int] = None,
    evidence_per_document: int = 3,
) -> LimitationEvidence:

    limitation_id = _clean(
        limitation.get(
            "limitation_id",
            "",
        )
    )

    limitation_text = _clean(
        limitation.get(
            "text",
            "",
        )
    )

    all_evidence = []

    docs = list(
        documents
    )

    if top_documents:
        docs = docs[
            :max(
                1,
                top_documents,
            )
        ]

    for document in docs:

        evidence = (
            extract_evidence_for_limitation(
                limitation_id,
                limitation_text,
                document,
                top_k=evidence_per_document,
            )
        )

        all_evidence.extend(
            evidence
        )

    all_evidence.sort(
        key=lambda item: (
            item.combined_score,
            item.semantic_score,
            item.lexical_score,
        ),
        reverse=True,
    )

    # Keep the strongest evidence while preventing one document
    # from overwhelming the limitation record.
    selected = []

    document_counts = {}

    for evidence in all_evidence:

        count = document_counts.get(
            evidence.document_id,
            0,
        )

        if count >= 3:
            continue

        selected.append(
            evidence
        )

        document_counts[
            evidence.document_id
        ] = count + 1

        if len(selected) >= 10:
            break

    best_score = (
        selected[0].combined_score
        if selected
        else 0.0
    )

    if best_score >= 0.80:
        status = "STRONG_EVIDENCE"

    elif best_score >= 0.60:
        status = "SUBSTANTIAL_EVIDENCE"

    elif best_score >= 0.40:
        status = "PARTIAL_EVIDENCE"

    elif best_score >= 0.20:
        status = "WEAK_EVIDENCE"

    else:
        status = "NO_STRONG_EVIDENCE"

    coverage = (
        1.0
        if best_score >= 0.60
        else best_score
    )

    return LimitationEvidence(
        limitation_id=limitation_id,
        limitation_text=limitation_text,
        evidence=selected,
        best_score=round(
            best_score,
            6,
        ),
        coverage=round(
            _clamp(
                coverage
            ),
            6,
        ),
        status=status,
    )


# ---------------------------------------------------------------------
# Claim evidence
# ---------------------------------------------------------------------

def build_claim_evidence(
    claim: Any,
    documents: Iterable[Dict[str, Any]],
    top_documents: Optional[int] = None,
) -> ClaimEvidence:

    if isinstance(
        claim,
        dict,
    ):

        claim_number = claim.get(
            "claim_number",
            claim.get(
                "number",
                1,
            ),
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

    else:

        claim_number = 1
        claim_text = _clean(
            claim
        )

    try:
        claim_number = int(
            claim_number
        )
    except Exception:
        claim_number = 1

    limitations = (
        normalize_limitations(
            claim
        )
    )

    limitation_results = []

    for limitation in limitations:

        result = (
            build_limitation_evidence(
                limitation,
                documents,
                top_documents=top_documents,
            )
        )

        limitation_results.append(
            result
        )

    if limitation_results:

        claim_coverage = sum(
            item.coverage
            for item
            in limitation_results
        ) / len(
            limitation_results
        )

    else:

        claim_coverage = 0.0

    if claim_coverage >= 0.80:
        status = "HIGH_EVIDENCE_COVERAGE"

    elif claim_coverage >= 0.60:
        status = "MODERATE_EVIDENCE_COVERAGE"

    elif claim_coverage >= 0.40:
        status = "PARTIAL_EVIDENCE_COVERAGE"

    else:
        status = "LOW_EVIDENCE_COVERAGE"

    evidence_count = sum(
        len(item.evidence)
        for item
        in limitation_results
    )

    return ClaimEvidence(
        claim_number=claim_number,
        claim_text=claim_text,
        limitations=limitation_results,
        claim_coverage=round(
            claim_coverage,
            6,
        ),
        evidence_count=evidence_count,
        status=status,
    )


# ---------------------------------------------------------------------
# Full evidence engine
# ---------------------------------------------------------------------

class EvidenceEngine:

    def __init__(
        self,
        semantic_engine: Any = None,
    ):

        self.semantic_engine = (
            semantic_engine
        )

    def build(
        self,
        claims: Iterable[Any],
        documents: Iterable[Any],
    ) -> Dict[str, Any]:

        normalized_documents = (
            normalize_documents(
                documents
            )
        )

        claims = list(
            claims
        )

        claim_results = []

        for claim in claims:

            result = (
                build_claim_evidence(
                    claim,
                    normalized_documents,
                )
            )

            # Optional semantic augmentation.
            if self.semantic_engine:

                try:

                    semantic_results = (
                        self.semantic_engine.search_claim(
                            claim,
                            normalized_documents,
                            top_k=10,
                        )
                    )

                    semantic_items = []

                    for result_item in (
                        semantic_results
                    ):

                        if hasattr(
                            result_item,
                            "to_dict",
                        ):

                            semantic_items.append(
                                result_item.to_dict()
                            )

                        elif isinstance(
                            result_item,
                            dict,
                        ):

                            semantic_items.append(
                                result_item
                            )

                    for limitation in (
                        result.limitations
                    ):

                        attach_semantic_scores(
                            limitation.evidence,
                            semantic_items,
                        )

                        if limitation.evidence:

                            limitation.evidence.sort(
                                key=lambda item: (
                                    item.combined_score,
                                    item.semantic_score,
                                    item.lexical_score,
                                ),
                                reverse=True,
                            )

                            limitation.best_score = (
                                limitation.evidence[
                                    0
                                ].combined_score
                            )

                            limitation.coverage = (
                                _clamp(
                                    limitation.best_score
                                )
                            )

                except Exception:
                    # Semantic augmentation must never break
                    # deterministic evidence generation.
                    pass

            claim_results.append(
                result
            )

        graph = build_evidence_graph(
            claim_results
        )

        statistics = calculate_evidence_statistics(
            claim_results
        )

        return {
            "success":
                True,

            "evidence_engine_version":
                EVIDENCE_ENGINE_VERSION,

            "generated_at":
                _utc_now(),

            "claims":
                [
                    item.to_dict()
                    for item
                    in claim_results
                ],

            "graph":
                graph,

            "statistics":
                statistics,

            "review_notice":
                (
                    "Evidence coverage is a retrieval and "
                    "traceability measure. It is not a legal "
                    "determination of anticipation, novelty, "
                    "inventive step, validity or infringement."
                ),
        }


# ---------------------------------------------------------------------
# Evidence graph
# ---------------------------------------------------------------------

def build_evidence_graph(
    claim_results: Iterable[Any],
) -> Dict[str, Any]:

    nodes = []
    edges = []

    node_ids = set()

    def add_node(
        node_id: str,
        node_type: str,
        label: str,
        data: Optional[Dict[str, Any]] = None,
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

                "data":
                    data or {},
            }
        )

    def add_edge(
        source: str,
        target: str,
        relation: str,
        score: float = 0.0,
    ):

        edges.append(
            {
                "source":
                    source,

                "target":
                    target,

                "relation":
                    relation,

                "score":
                    round(
                        score,
                        6,
                    ),
            }
        )

    for claim in claim_results:

        if isinstance(
            claim,
            ClaimEvidence,
        ):

            claim_data = claim.to_dict()

        else:

            claim_data = claim

        claim_number = claim_data.get(
            "claim_number",
            1,
        )

        claim_id = (
            f"CLAIM-{claim_number}"
        )

        add_node(
            claim_id,
            "claim",
            f"Claim {claim_number}",
            {
                "claim_text":
                    claim_data.get(
                        "claim_text",
                        "",
                    )
            },
        )

        for limitation in claim_data.get(
            "limitations",
            [],
        ):

            limitation_id = _clean(
                limitation.get(
                    "limitation_id",
                    "",
                )
            )

            if not limitation_id:
                continue

            add_node(
                limitation_id,
                "limitation",
                limitation.get(
                    "limitation_text",
                    "",
                ),
                {
                    "status":
                        limitation.get(
                            "status",
                            "",
                        ),

                    "coverage":
                        limitation.get(
                            "coverage",
                            0.0,
                        ),
                },
            )

            add_edge(
                claim_id,
                limitation_id,
                "HAS_LIMITATION",
                limitation.get(
                    "coverage",
                    0.0,
                ),
            )

            for evidence in limitation.get(
                "evidence",
                [],
            ):

                evidence_id = _clean(
                    evidence.get(
                        "evidence_id",
                        "",
                    )
                )

                document_id = _clean(
                    evidence.get(
                        "document_id",
                        "",
                    )
                )

                if not evidence_id:
                    continue

                if document_id:

                    add_node(
                        document_id,
                        "document",
                        document_id,
                    )

                    add_edge(
                        limitation_id,
                        document_id,
                        "SUPPORTED_BY_DOCUMENT",
                        evidence.get(
                            "combined_score",
                            0.0,
                        ),
                    )

                add_node(
                    evidence_id,
                    "evidence",
                    evidence.get(
                        "passage",
                        "",
                    ),
                    {
                        "source":
                            evidence.get(
                                "source",
                                "",
                            ),

                        "page":
                            evidence.get(
                                "page",
                            ),

                        "status":
                            evidence.get(
                                "disclosure_status",
                                "",
                            ),

                        "score":
                            evidence.get(
                                "combined_score",
                                0.0,
                            ),
                    },
                )

                if document_id:

                    add_edge(
                        document_id,
                        evidence_id,
                        "CONTAINS_PASSAGE",
                        evidence.get(
                            "combined_score",
                            0.0,
                        ),
                    )

                add_edge(
                    limitation_id,
                    evidence_id,
                    "SUPPORTED_BY_EVIDENCE",
                    evidence.get(
                        "combined_score",
                        0.0,
                    ),
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
# Statistics
# ---------------------------------------------------------------------

def calculate_evidence_statistics(
    claim_results: Iterable[Any],
) -> Dict[str, Any]:

    claims = list(
        claim_results
    )

    limitations = []
    evidence_count = 0

    for claim in claims:

        if isinstance(
            claim,
            ClaimEvidence,
        ):

            claim_dict = claim.to_dict()

        else:

            claim_dict = claim

        for limitation in claim_dict.get(
            "limitations",
            [],
        ):

            limitations.append(
                limitation
            )

            evidence_count += len(
                limitation.get(
                    "evidence",
                    [],
                )
            )

    if limitations:

        average_coverage = (
            sum(
                _safe_float(
                    item.get(
                        "coverage",
                        0.0,
                    )
                )
                for item
                in limitations
            )
            / len(
                limitations
            )
        )

    else:

        average_coverage = 0.0

    strong = sum(
        1
        for item
        in limitations
        if _safe_float(
            item.get(
                "coverage",
                0.0,
            )
        ) >= 0.60
    )

    return {
        "claim_count":
            len(claims),

        "limitation_count":
            len(limitations),

        "evidence_count":
            evidence_count,

        "average_limitation_coverage":
            round(
                average_coverage,
                6,
            ),

        "limitations_with_substantial_evidence":
            strong,

        "limitation_coverage_rate":
            round(
                (
                    strong
                    / len(limitations)
                )
                if limitations
                else 0.0,
                6,
            ),
    }


# ---------------------------------------------------------------------
# Evidence matrix
# ---------------------------------------------------------------------

def build_evidence_matrix(
    analysis: Dict[str, Any],
) -> List[Dict[str, Any]]:

    matrix = []

    for claim in analysis.get(
        "claims",
        [],
    ):

        claim_number = claim.get(
            "claim_number"
        )

        for limitation in claim.get(
            "limitations",
            [],
        ):

            evidence = limitation.get(
                "evidence",
                [],
            )

            best = (
                evidence[0]
                if evidence
                else {}
            )

            matrix.append(
                {
                    "claim_number":
                        claim_number,

                    "limitation_id":
                        limitation.get(
                            "limitation_id",
                            "",
                        ),

                    "limitation":
                        limitation.get(
                            "limitation_text",
                            "",
                        ),

                    "best_document":
                        best.get(
                            "document_id",
                            "",
                        ),

                    "best_evidence":
                        best.get(
                            "passage",
                            "",
                        ),

                    "score":
                        limitation.get(
                            "best_score",
                            0.0,
                        ),

                    "status":
                        limitation.get(
                            "status",
                            "",
                        ),
                }
            )

    return matrix


# ---------------------------------------------------------------------
# Reviewer-oriented summary
# ---------------------------------------------------------------------

def summarize_evidence(
    analysis: Dict[str, Any],
) -> Dict[str, Any]:

    statistics = analysis.get(
        "statistics",
        {},
    )

    claims = analysis.get(
        "claims",
        [],
    )

    high_coverage_claims = []

    for claim in claims:

        coverage = _safe_float(
            claim.get(
                "claim_coverage",
                0.0,
            )
        )

        if coverage >= 0.60:

            high_coverage_claims.append(
                claim.get(
                    "claim_number"
                )
            )

    return {
        "average_limitation_coverage":
            statistics.get(
                "average_limitation_coverage",
                0.0,
            ),

        "limitation_coverage_rate":
            statistics.get(
                "limitation_coverage_rate",
                0.0,
            ),

        "high_coverage_claims":
            high_coverage_claims,

        "review_note":
            (
                "High retrieval coverage means that the system "
                "found technically similar passages. It does "
                "not by itself establish that every claim "
                "limitation is disclosed in a legally relevant "
                "manner."
            ),
    }


# ---------------------------------------------------------------------
# Convenience API
# ---------------------------------------------------------------------

def build_evidence_engine(
    semantic_engine: Any = None,
) -> EvidenceEngine:

    return EvidenceEngine(
        semantic_engine=semantic_engine
    )


def analyze_evidence(
    claims: Iterable[Any],
    documents: Iterable[Any],
    semantic_engine: Any = None,
) -> Dict[str, Any]:

    engine = EvidenceEngine(
        semantic_engine=semantic_engine
    )

    return engine.build(
        claims,
        documents,
    )


def generate_evidence_graph(
    analysis: Dict[str, Any],
) -> Dict[str, Any]:

    return analysis.get(
        "graph",
        {
            "nodes": [],
            "edges": [],
        },
    )


# ---------------------------------------------------------------------
# Backward-compatible functions
# ---------------------------------------------------------------------

def create_evidence_map(
    claims: Iterable[Any],
    documents: Iterable[Any],
) -> Dict[str, Any]:

    return analyze_evidence(
        claims,
        documents,
    )


def build_evidence_map(
    claims: Iterable[Any],
    documents: Iterable[Any],
) -> Dict[str, Any]:

    return analyze_evidence(
        claims,
        documents,
    )


def calculate_evidence_coverage(
    analysis: Dict[str, Any],
) -> float:

    statistics = analysis.get(
        "statistics",
        {},
    )

    return _safe_float(
        statistics.get(
            "average_limitation_coverage",
            0.0,
        )
    )


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

__all__ = [
    "EVIDENCE_ENGINE_VERSION",
    "EvidencePassage",
    "LimitationEvidence",
    "ClaimEvidence",
    "EvidenceEngine",
    "normalize_documents",
    "normalize_limitations",
    "split_passages",
    "score_passage",
    "classify_evidence",
    "build_evidence_rationale",
    "extract_evidence_for_limitation",
    "attach_semantic_scores",
    "build_limitation_evidence",
    "build_claim_evidence",
    "build_evidence_graph",
    "calculate_evidence_statistics",
    "build_evidence_matrix",
    "summarize_evidence",
    "build_evidence_engine",
    "analyze_evidence",
    "generate_evidence_graph",
    "create_evidence_map",
    "build_evidence_map",
    "calculate_evidence_coverage",
]
