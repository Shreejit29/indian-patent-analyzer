"""
Novelty Analyzer V3
===================

Purpose
-------
Perform structured, limitation-by-limitation novelty screening.

Architecture
------------

Claim
  |
  +-- Limitation 1
  |      |
  |      +-- Document A -> evidence
  |      +-- Document B -> evidence
  |
  +-- Limitation 2
  |      |
  |      +-- Document A -> evidence
  |      +-- Document C -> evidence
  |
  +-- Limitation 3
         |
         +-- Document A -> evidence

                 |
                 v

        Same-document analysis
                 |
                 v
       Novelty screening result


Important
---------
This module is a technical/legal-analysis aid.

It does NOT make a definitive legal conclusion regarding novelty,
anticipation, validity, or patentability.

A novelty determination may depend on the applicable statutory
standard, publication/priority dates, claim construction,
enablement, inherent disclosure, and the complete prior-art record.

Version
-------
3.0.0
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


NOVELTY_ANALYZER_VERSION = "3.0.0"


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
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


# ---------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------

@dataclass
class NoveltyLimitationFinding:

    limitation_id: str
    limitation_text: str

    best_document_id: str
    best_document_title: str

    evidence_score: float
    disclosure_status: str

    evidence_passages: List[Dict[str, Any]]

    reasoning: str

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(
            self
        )


@dataclass
class NoveltyDocumentFinding:

    document_id: str
    document_title: str

    limitation_count: int
    supported_limitation_count: int

    coverage: float
    weakest_limitation_score: float
    average_limitation_score: float

    status: str

    limitations: List[
        NoveltyLimitationFinding
    ]

    reasoning: str

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
                NoveltyLimitationFinding,
            )
            else item
            for item
            in self.limitations
        ]

        return data


@dataclass
class NoveltyClaimFinding:

    claim_number: int
    claim_text: str

    limitation_count: int
    supported_limitation_count: int

    best_document_id: str
    best_document_title: str

    coverage: float

    status: str

    document_findings: List[
        NoveltyDocumentFinding
    ]

    reasoning: str

    review_questions: List[str]

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        data = asdict(
            self
        )

        data["document_findings"] = [
            item.to_dict()
            if isinstance(
                item,
                NoveltyDocumentFinding,
            )
            else item
            for item
            in self.document_findings
        ]

        return data


# ---------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------

# These thresholds control technical screening only.
# They are NOT legal thresholds.

STRONG_DISCLOSURE_THRESHOLD = 0.80
SUBSTANTIAL_DISCLOSURE_THRESHOLD = 0.60
PARTIAL_DISCLOSURE_THRESHOLD = 0.40

HIGH_COVERAGE_THRESHOLD = 0.90
SUBSTANTIAL_COVERAGE_THRESHOLD = 0.75
PARTIAL_COVERAGE_THRESHOLD = 0.50


# ---------------------------------------------------------------------
# Normalization helpers
# ---------------------------------------------------------------------

def normalize_claim(
    claim: Any,
    fallback_number: int = 1,
) -> Dict[str, Any]:

    if isinstance(
        claim,
        dict,
    ):

        number = claim.get(
            "claim_number",
            claim.get(
                "number",
                fallback_number,
            ),
        )

        text = _clean(
            claim.get(
                "text",
                claim.get(
                    "claim_text",
                    "",
                ),
            )
        )

        limitations = claim.get(
            "limitations",
            [],
        )

    else:

        number = fallback_number
        text = _clean(
            claim
        )
        limitations = []

    try:
        number = int(
            number
        )
    except Exception:
        number = fallback_number

    normalized_limitations = []

    for index, limitation in enumerate(
        limitations,
        start=1,
    ):

        if isinstance(
            limitation,
            dict,
        ):

            limitation_id = _clean(
                limitation.get(
                    "limitation_id",
                    limitation.get(
                        "id",
                        "",
                    ),
                )
            )

            limitation_text = _clean(
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

        else:

            limitation_text = _clean(
                limitation
            )

            limitation_id = ""

        if not limitation_id:

            limitation_id = _stable_id(
                "L",
                f"{number}|{index}|{limitation_text}",
            )

        if limitation_text:

            normalized_limitations.append(
                {
                    "limitation_id":
                        limitation_id,

                    "text":
                        limitation_text,
                }
            )

    return {
        "claim_number":
            number,

        "text":
            text,

        "limitations":
            normalized_limitations,
    }


def normalize_evidence_analysis(
    analysis: Any,
) -> Dict[str, Any]:

    if not isinstance(
        analysis,
        dict,
    ):
        return {
            "claims": []
        }

    return analysis


# ---------------------------------------------------------------------
# Evidence classification
# ---------------------------------------------------------------------

def classify_disclosure_score(
    score: float,
) -> str:

    score = _clamp(
        score
    )

    if score >= STRONG_DISCLOSURE_THRESHOLD:

        return "STRONG_DISCLOSURE"

    if score >= SUBSTANTIAL_DISCLOSURE_THRESHOLD:

        return "SUBSTANTIAL_DISCLOSURE"

    if score >= PARTIAL_DISCLOSURE_THRESHOLD:

        return "PARTIAL_DISCLOSURE"

    return "WEAK_OR_UNCERTAIN"


def is_supported_limitation(
    score: float,
) -> bool:

    return (
        _safe_float(
            score
        )
        >= SUBSTANTIAL_DISCLOSURE_THRESHOLD
    )


# ---------------------------------------------------------------------
# Evidence extraction
# ---------------------------------------------------------------------

def _extract_evidence_items(
    limitation: Dict[str, Any],
) -> List[Dict[str, Any]]:

    evidence = limitation.get(
        "evidence",
        [],
    )

    if not isinstance(
        evidence,
        list,
    ):
        return []

    result = []

    for item in evidence:

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

        result.append(
            item
        )

    return result


def group_evidence_by_document(
    limitation: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:

    grouped: Dict[
        str,
        List[Dict[str, Any]]
    ] = {}

    for evidence in (
        _extract_evidence_items(
            limitation
        )
    ):

        document_id = _clean(
            evidence.get(
                "document_id",
                evidence.get(
                    "source_document_id",
                    "",
                ),
            )
        )

        if not document_id:
            continue

        grouped.setdefault(
            document_id,
            [],
        ).append(
            evidence
        )

    return grouped


# ---------------------------------------------------------------------
# Document metadata
# ---------------------------------------------------------------------

def normalize_document_metadata(
    documents: Iterable[Any],
) -> Dict[str, Dict[str, Any]]:

    result = {}

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

            if not document_id:

                document_id = _stable_id(
                    "DOC",
                    f"{index}|{document}",
                )

            result[
                document_id
            ] = {
                "document_id":
                    document_id,

                "title":
                    _clean(
                        document.get(
                            "title",
                            document.get(
                                "name",
                                "",
                            ),
                        )
                    ),

                "source":
                    _clean(
                        document.get(
                            "source",
                            document.get(
                                "url",
                                "",
                            ),
                        )
                    ),

                "publication_number":
                    _clean(
                        document.get(
                            "publication_number",
                            document.get(
                                "patent_number",
                                "",
                            ),
                        )
                    ),

                "publication_date":
                    _clean(
                        document.get(
                            "publication_date",
                            document.get(
                                "published_date",
                                "",
                            ),
                        )
                    ),

                "priority_date":
                    _clean(
                        document.get(
                            "priority_date",
                            "",
                        )
                    ),

                "metadata":
                    document.get(
                        "metadata",
                        {},
                    ),
            }

        else:

            document_id = _stable_id(
                "DOC",
                f"{index}|{document}",
            )

            result[
                document_id
            ] = {
                "document_id":
                    document_id,

                "title":
                    "",

                "source":
                    "",

                "publication_number":
                    "",

                "publication_date":
                    "",

                "priority_date":
                    "",

                "metadata":
                    {},
            }

    return result


# ---------------------------------------------------------------------
# Limitation analysis
# ---------------------------------------------------------------------

def analyze_limitation_against_document(
    limitation: Dict[str, Any],
    document_id: str,
    document_title: str = "",
) -> NoveltyLimitationFinding:

    limitation_id = _clean(
        limitation.get(
            "limitation_id",
            "",
        )
    )

    limitation_text = _clean(
        limitation.get(
            "limitation_text",
            limitation.get(
                "text",
                "",
            ),
        )
    )

    evidence = [
        item
        for item
        in _extract_evidence_items(
            limitation
        )
        if _clean(
            item.get(
                "document_id",
                "",
            )
        )
        == document_id
    ]

    if evidence:

        evidence.sort(
            key=lambda item: (
                _safe_float(
                    item.get(
                        "combined_score",
                        item.get(
                            "score",
                            0.0,
                        ),
                    )
                ),
                _safe_float(
                    item.get(
                        "semantic_score",
                        0.0,
                    )
                ),
                _safe_float(
                    item.get(
                        "lexical_score",
                        0.0,
                    )
                ),
            ),
            reverse=True,
        )

        best_score = _safe_float(
            evidence[0].get(
                "combined_score",
                evidence[0].get(
                    "score",
                    0.0,
                ),
            )
        )

    else:

        best_score = 0.0

    status = classify_disclosure_score(
        best_score
    )

    if best_score >= STRONG_DISCLOSURE_THRESHOLD:

        reasoning = (
            "Strong textual/semantic evidence was retrieved "
            "for this limitation from the document. The full "
            "reference should still be reviewed for context "
            "and legally relevant disclosure."
        )

    elif best_score >= SUBSTANTIAL_DISCLOSURE_THRESHOLD:

        reasoning = (
            "Substantial evidence was retrieved for this "
            "limitation. Additional contextual review is "
            "required before relying on it in a novelty analysis."
        )

    elif best_score >= PARTIAL_DISCLOSURE_THRESHOLD:

        reasoning = (
            "The document contains partial evidence for the "
            "limitation, but the retrieved material does not "
            "provide strong support on its own."
        )

    else:

        reasoning = (
            "The retrieved evidence does not provide strong "
            "support for this limitation."
        )

    return NoveltyLimitationFinding(
        limitation_id=limitation_id,
        limitation_text=limitation_text,
        best_document_id=document_id,
        best_document_title=document_title,
        evidence_score=round(
            best_score,
            6,
        ),
        disclosure_status=status,
        evidence_passages=evidence[:5],
        reasoning=reasoning,
    )


# ---------------------------------------------------------------------
# Same-document completeness
# ---------------------------------------------------------------------

def analyze_document_for_claim(
    claim: Dict[str, Any],
    document_id: str,
    document_title: str = "",
) -> NoveltyDocumentFinding:

    limitations = claim.get(
        "limitations",
        [],
    )

    findings = []

    for limitation in limitations:

        finding = (
            analyze_limitation_against_document(
                limitation,
                document_id,
                document_title,
            )
        )

        findings.append(
            finding
        )

    limitation_count = len(
        findings
    )

    supported_count = sum(
        1
        for finding
        in findings
        if is_supported_limitation(
            finding.evidence_score
        )
    )

    if limitation_count:

        coverage = (
            supported_count
            / limitation_count
        )

        average_score = (
            sum(
                finding.evidence_score
                for finding
                in findings
            )
            / limitation_count
        )

        weakest_score = min(
            finding.evidence_score
            for finding
            in findings
        )

    else:

        coverage = 0.0
        average_score = 0.0
        weakest_score = 0.0

    # The same-document requirement is deliberately strict.
    if (
        limitation_count > 0
        and coverage >= HIGH_COVERAGE_THRESHOLD
        and weakest_score
        >= SUBSTANTIAL_DISCLOSURE_THRESHOLD
    ):

        status = (
            "HIGH_COMPLETENESS_REVIEW"
        )

        reasoning = (
            "A single document contains substantial evidence "
            "for essentially all analyzed claim limitations. "
            "This is a high-priority reference for human review; "
            "it is not itself a legal conclusion of anticipation."
        )

    elif (
        limitation_count > 0
        and coverage >= SUBSTANTIAL_COVERAGE_THRESHOLD
    ):

        status = (
            "SUBSTANTIAL_SAME_DOCUMENT_COVERAGE"
        )

        reasoning = (
            "One document contains evidence for most analyzed "
            "limitations. The remaining limitation(s) and the "
            "full disclosure should be reviewed carefully."
        )

    elif (
        limitation_count > 0
        and coverage >= PARTIAL_COVERAGE_THRESHOLD
    ):

        status = (
            "PARTIAL_SAME_DOCUMENT_COVERAGE"
        )

        reasoning = (
            "The document covers a meaningful subset of the "
            "claim limitations but does not provide strong "
            "same-document coverage of the complete analyzed claim."
        )

    else:

        status = (
            "INSUFFICIENT_SAME_DOCUMENT_COVERAGE"
        )

        reasoning = (
            "The document does not provide substantial "
            "same-document coverage of the analyzed limitations."
        )

    return NoveltyDocumentFinding(
        document_id=document_id,
        document_title=document_title,
        limitation_count=limitation_count,
        supported_limitation_count=supported_count,
        coverage=round(
            coverage,
            6,
        ),
        weakest_limitation_score=round(
            weakest_score,
            6,
        ),
        average_limitation_score=round(
            average_score,
            6,
        ),
        status=status,
        limitations=findings,
        reasoning=reasoning,
    )


# ---------------------------------------------------------------------
# Claim-level novelty screening
# ---------------------------------------------------------------------

def analyze_claim_novelty(
    claim: Dict[str, Any],
    evidence_claim: Optional[Dict[str, Any]] = None,
    document_metadata: Optional[
        Dict[str, Dict[str, Any]]
    ] = None,
) -> NoveltyClaimFinding:

    claim_number = int(
        claim.get(
            "claim_number",
            1,
        )
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

    if evidence_claim is None:

        evidence_claim = {
            "claim_number":
                claim_number,

            "claim_text":
                claim_text,

            "limitations":
                claim.get(
                    "limitations",
                    [],
                ),
        }

    limitations = []

    for limitation in evidence_claim.get(
        "limitations",
        [],
    ):

        if not isinstance(
            limitation,
            dict,
        ):
            continue

        limitations.append(
            limitation
        )

    # Determine every document that has evidence for at least
    # one limitation.
    candidate_document_ids = set()

    for limitation in limitations:

        for evidence in (
            _extract_evidence_items(
                limitation
            )
        ):

            document_id = _clean(
                evidence.get(
                    "document_id",
                    "",
                )
            )

            if document_id:

                candidate_document_ids.add(
                    document_id
                )

    document_metadata = (
        document_metadata
        or {}
    )

    document_findings = []

    for document_id in sorted(
        candidate_document_ids
    ):

        metadata = document_metadata.get(
            document_id,
            {},
        )

        finding = (
            analyze_document_for_claim(
                evidence_claim,
                document_id,
                metadata.get(
                    "title",
                    "",
                ),
            )
        )

        document_findings.append(
            finding
        )

    document_findings.sort(
        key=lambda item: (
            item.coverage,
            item.weakest_limitation_score,
            item.average_limitation_score,
        ),
        reverse=True,
    )

    best_document_id = ""
    best_document_title = ""
    best_coverage = 0.0

    if document_findings:

        best = document_findings[0]

        best_document_id = (
            best.document_id
        )

        best_document_title = (
            best.document_title
        )

        best_coverage = (
            best.coverage
        )

    limitation_count = len(
        limitations
    )

    supported_count = sum(
        1
        for limitation in limitations
        if _best_limitation_score(
            limitation
        )
        >= SUBSTANTIAL_DISCLOSURE_THRESHOLD
    )

    # Claim-level status.
    #
    # "POTENTIAL_ANTICIPATION_REFERENCE" means that one document
    # has enough technical coverage to warrant focused review.
    # It intentionally avoids declaring the claim legally anticipated.

    if (
        best_coverage
        >= HIGH_COVERAGE_THRESHOLD
        and document_findings
        and document_findings[0]
        .weakest_limitation_score
        >= SUBSTANTIAL_DISCLOSURE_THRESHOLD
    ):

        status = (
            "POTENTIAL_ANTICIPATION_REFERENCE"
        )

        reasoning = (
            "A single reference shows substantial evidence "
            "covering essentially all analyzed limitations. "
            "This reference should receive priority in a "
            "formal novelty review."
        )

    elif (
        best_coverage
        >= SUBSTANTIAL_COVERAGE_THRESHOLD
    ):

        status = (
            "STRONG_SAME_DOCUMENT_SIGNAL"
        )

        reasoning = (
            "A single reference covers most analyzed "
            "limitations, but further review is required "
            "for the remaining limitations and context."
        )

    elif (
        best_coverage
        >= PARTIAL_COVERAGE_THRESHOLD
    ):

        status = (
            "PARTIAL_NOVELTY_SIGNAL"
        )

        reasoning = (
            "References contain meaningful evidence for "
            "subsets of the claim, but no sufficiently "
            "complete same-document coverage was identified "
            "by this screening layer."
        )

    else:

        status = (
            "NO_STRONG_SAME_DOCUMENT_SIGNAL"
        )

        reasoning = (
            "The retrieved evidence does not currently show "
            "strong same-document coverage of the analyzed "
            "claim."
        )

    review_questions = [
        "Does the identified reference disclose every required "
        "claim limitation?",
        "Is the disclosure direct and technically sufficient "
        "for the claimed subject matter?",
        "Are the relevant dates and publication status of the "
        "reference established?",
        "Does claim construction affect the apparent correspondence?",
        "Should additional databases or references be searched?",
    ]

    return NoveltyClaimFinding(
        claim_number=claim_number,
        claim_text=claim_text,
        limitation_count=limitation_count,
        supported_limitation_count=supported_count,
        best_document_id=best_document_id,
        best_document_title=best_document_title,
        coverage=round(
            best_coverage,
            6,
        ),
        status=status,
        document_findings=document_findings,
        reasoning=reasoning,
        review_questions=review_questions,
    )


def _best_limitation_score(
    limitation: Dict[str, Any],
) -> float:

    evidence = _extract_evidence_items(
        limitation
    )

    if not evidence:
        return 0.0

    return max(
        _safe_float(
            item.get(
                "combined_score",
                item.get(
                    "score",
                    0.0,
                ),
            )
        )
        for item
        in evidence
    )


# ---------------------------------------------------------------------
# Full analyzer
# ---------------------------------------------------------------------

class NoveltyAnalyzer:

    def __init__(
        self,
        same_document_only: bool = True,
    ):

        self.same_document_only = (
            same_document_only
        )

    def analyze(
        self,
        claims: Iterable[Any],
        evidence_analysis: Dict[str, Any],
        documents: Optional[
            Iterable[Any]
        ] = None,
    ) -> Dict[str, Any]:

        evidence_analysis = (
            normalize_evidence_analysis(
                evidence_analysis
            )
        )

        document_metadata = (
            normalize_document_metadata(
                documents or []
            )
        )

        evidence_claim_map = {}

        for evidence_claim in (
            evidence_analysis.get(
                "claims",
                [],
            )
        ):

            if not isinstance(
                evidence_claim,
                dict,
            ):
                continue

            claim_number = evidence_claim.get(
                "claim_number",
                1,
            )

            try:
                claim_number = int(
                    claim_number
                )
            except Exception:
                continue

            evidence_claim_map[
                claim_number
            ] = evidence_claim

        claim_findings = []

        for index, claim in enumerate(
            claims,
            start=1,
        ):

            normalized_claim = (
                normalize_claim(
                    claim,
                    index,
                )
            )

            claim_number = (
                normalized_claim[
                    "claim_number"
                ]
            )

            evidence_claim = (
                evidence_claim_map.get(
                    claim_number
                )
            )

            # If the evidence engine already has limitations,
            # prefer those because they contain actual evidence.
            if evidence_claim is None:

                evidence_claim = {
                    "claim_number":
                        claim_number,

                    "claim_text":
                        normalized_claim[
                            "text"
                        ],

                    "limitations":
                        normalized_claim[
                            "limitations"
                        ],
                }

            finding = (
                analyze_claim_novelty(
                    normalized_claim,
                    evidence_claim,
                    document_metadata,
                )
            )

            claim_findings.append(
                finding
            )

        statistics = (
            calculate_novelty_statistics(
                claim_findings
            )
        )

        return {
            "success":
                True,

            "novelty_analyzer_version":
                NOVELTY_ANALYZER_VERSION,

            "generated_at":
                _utc_now(),

            "same_document_only":
                self.same_document_only,

            "claims": [
                item.to_dict()
                for item
                in claim_findings
            ],

            "statistics":
                statistics,

            "review_notice":
                (
                    "Novelty results are automated screening "
                    "signals. A high-coverage reference is not "
                    "by itself a legal conclusion of anticipation "
                    "or lack of novelty."
                ),
        }


# ---------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------

def calculate_novelty_statistics(
    claim_findings: Iterable[Any],
) -> Dict[str, Any]:

    findings = list(
        claim_findings
    )

    total = len(
        findings
    )

    potential = sum(
        1
        for item
        in findings
        if (
            item.status
            == "POTENTIAL_ANTICIPATION_REFERENCE"
        )
    )

    strong = sum(
        1
        for item
        in findings
        if (
            item.status
            == "STRONG_SAME_DOCUMENT_SIGNAL"
        )
    )

    partial = sum(
        1
        for item
        in findings
        if (
            item.status
            == "PARTIAL_NOVELTY_SIGNAL"
        )
    )

    no_signal = sum(
        1
        for item
        in findings
        if (
            item.status
            == "NO_STRONG_SAME_DOCUMENT_SIGNAL"
        )
    )

    if findings:

        average_coverage = (
            sum(
                item.coverage
                for item
                in findings
            )
            / total
        )

    else:

        average_coverage = 0.0

    return {
        "claim_count":
            total,

        "potential_anticipation_references":
            potential,

        "strong_same_document_signals":
            strong,

        "partial_signals":
            partial,

        "no_strong_same_document_signal":
            no_signal,

        "average_best_document_coverage":
            round(
                average_coverage,
                6,
            ),
    }


# ---------------------------------------------------------------------
# Reference ranking
# ---------------------------------------------------------------------

def rank_novelty_references(
    claim_finding: Dict[str, Any],
    top_k: int = 10,
) -> List[Dict[str, Any]]:

    documents = claim_finding.get(
        "document_findings",
        [],
    )

    ranked = []

    for item in documents:

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

        ranked.append(
            item
        )

    ranked.sort(
        key=lambda item: (
            _safe_float(
                item.get(
                    "coverage",
                    0.0,
                )
            ),
            _safe_float(
                item.get(
                    "weakest_limitation_score",
                    0.0,
                )
            ),
            _safe_float(
                item.get(
                    "average_limitation_score",
                    0.0,
                )
            ),
        ),
        reverse=True,
    )

    for rank, item in enumerate(
        ranked[:top_k],
        start=1,
    ):

        item[
            "review_rank"
        ] = rank

    return ranked[
        :top_k
    ]


# ---------------------------------------------------------------------
# Limitation gap analysis
# ---------------------------------------------------------------------

def identify_limitation_gaps(
    claim_finding: Dict[str, Any],
) -> List[Dict[str, Any]]:

    documents = claim_finding.get(
        "document_findings",
        [],
    )

    gaps = {}

    for document in documents:

        for limitation in document.get(
            "limitations",
            [],
        ):

            score = _safe_float(
                limitation.get(
                    "evidence_score",
                    0.0,
                )
            )

            if score >= SUBSTANTIAL_DISCLOSURE_THRESHOLD:
                continue

            limitation_id = limitation.get(
                "limitation_id",
                "",
            )

            if not limitation_id:
                continue

            current = gaps.get(
                limitation_id
            )

            if current is None:

                gaps[
                    limitation_id
                ] = {
                    "limitation_id":
                        limitation_id,

                    "limitation_text":
                        limitation.get(
                            "limitation_text",
                            "",
                        ),

                    "best_score":
                        score,

                    "documents_checked":
                        1,
                }

            else:

                current[
                    "best_score"
                ] = max(
                    current[
                        "best_score"
                    ],
                    score,
                )

                current[
                    "documents_checked"
                ] += 1

    return sorted(
        gaps.values(),
        key=lambda item: item[
            "best_score"
        ],
    )


# ---------------------------------------------------------------------
# Claim chart integration
# ---------------------------------------------------------------------

def build_novelty_claim_chart(
    claim_finding: Dict[str, Any],
) -> List[Dict[str, Any]]:

    rows = []

    for document in claim_finding.get(
        "document_findings",
        [],
    ):

        document_id = document.get(
            "document_id",
            "",
        )

        for limitation in document.get(
            "limitations",
            [],
        ):

            rows.append(
                {
                    "claim_number":
                        claim_finding.get(
                            "claim_number",
                            1,
                        ),

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

                    "document_id":
                        document_id,

                    "document_title":
                        document.get(
                            "document_title",
                            "",
                        ),

                    "score":
                        limitation.get(
                            "evidence_score",
                            0.0,
                        ),

                    "disclosure_status":
                        limitation.get(
                            "disclosure_status",
                            "",
                        ),

                    "evidence":
                        limitation.get(
                            "evidence_passages",
                            [],
                        ),
                }
            )

    return rows


# ---------------------------------------------------------------------
# Human-readable summary
# ---------------------------------------------------------------------

def summarize_novelty(
    analysis: Dict[str, Any],
) -> str:

    statistics = analysis.get(
        "statistics",
        {},
    )

    potential = statistics.get(
        "potential_anticipation_references",
        0,
    )

    strong = statistics.get(
        "strong_same_document_signals",
        0,
    )

    partial = statistics.get(
        "partial_signals",
        0,
    )

    claims = statistics.get(
        "claim_count",
        0,
    )

    return (
        f"Novelty screening analyzed {claims} claim(s). "
        f"{potential} claim(s) have a high-priority same-document "
        f"reference signal, {strong} have strong but incomplete "
        f"same-document signals, and {partial} have partial "
        f"signals. These are evidence-screening results rather "
        f"than definitive legal conclusions."
    )


# ---------------------------------------------------------------------
# Convenience API
# ---------------------------------------------------------------------

def analyze_novelty(
    claims: Iterable[Any],
    evidence_analysis: Dict[str, Any],
    documents: Optional[
        Iterable[Any]
    ] = None,
) -> Dict[str, Any]:

    analyzer = NoveltyAnalyzer()

    return analyzer.analyze(
        claims=claims,
        evidence_analysis=evidence_analysis,
        documents=documents,
    )


def screen_novelty(
    claims: Iterable[Any],
    evidence_analysis: Dict[str, Any],
    documents: Optional[
        Iterable[Any]
    ] = None,
) -> Dict[str, Any]:

    return analyze_novelty(
        claims,
        evidence_analysis,
        documents,
    )


# ---------------------------------------------------------------------
# Backward-compatible functions
# ---------------------------------------------------------------------

def check_novelty(
    claims: Iterable[Any],
    evidence_analysis: Dict[str, Any],
    documents: Optional[
        Iterable[Any]
    ] = None,
) -> Dict[str, Any]:

    return analyze_novelty(
        claims,
        evidence_analysis,
        documents,
    )


def analyze_claim_novelty_screening(
    claim: Dict[str, Any],
    evidence_claim: Dict[str, Any],
) -> Dict[str, Any]:

    finding = analyze_claim_novelty(
        claim,
        evidence_claim,
        {},
    )

    return finding.to_dict()


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

__all__ = [
    "NOVELTY_ANALYZER_VERSION",
    "NoveltyLimitationFinding",
    "NoveltyDocumentFinding",
    "NoveltyClaimFinding",
    "NoveltyAnalyzer",
    "normalize_claim",
    "normalize_evidence_analysis",
    "normalize_document_metadata",
    "classify_disclosure_score",
    "is_supported_limitation",
    "group_evidence_by_document",
    "analyze_limitation_against_document",
    "analyze_document_for_claim",
    "analyze_claim_novelty",
    "calculate_novelty_statistics",
    "rank_novelty_references",
    "identify_limitation_gaps",
    "build_novelty_claim_chart",
    "summarize_novelty",
    "analyze_novelty",
    "screen_novelty",
    "check_novelty",
    "analyze_claim_novelty_screening",
]
