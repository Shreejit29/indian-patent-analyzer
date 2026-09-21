"""
services/evidence_verifier.py

Indian Patent Analyzer
Evidence verification and provenance validation layer.

Version: 3.0.0

Purpose
-------
Verify whether retrieved evidence actually supports a patent claim
limitation before that evidence is used by downstream analysis.

Design principles
-----------------
1. Retrieval is not verification.
2. Lexical similarity alone is insufficient.
3. Every verified item retains provenance.
4. Contradictory evidence is explicitly represented.
5. Missing evidence is different from negative evidence.
6. Verification scores are evidence-quality signals, NOT legal conclusions.
7. No automatic novelty, inventive-step, validity, or infringement conclusion.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


EVIDENCE_VERIFIER_VERSION = "3.0.0"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATUS_VERIFIED = "verified"
STATUS_PARTIALLY_VERIFIED = "partially_verified"
STATUS_UNVERIFIED = "unverified"
STATUS_CONTRADICTED = "contradicted"
STATUS_NOT_FOUND = "not_found"

SUPPORT_EXPLICIT = "explicit"
SUPPORT_PARTIAL = "partial"
SUPPORT_CONTEXTUAL = "contextual"
SUPPORT_WEAK = "weak"
SUPPORT_NONE = "none"

SOURCE_CLAIM = "claim"
SOURCE_ABSTRACT = "abstract"
SOURCE_DESCRIPTION = "description"
SOURCE_PARAGRAPH = "paragraph"
SOURCE_SECTION = "section"
SOURCE_METADATA = "metadata"
SOURCE_UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class VerificationEvidence:
    """
    A normalized evidence passage supplied for verification.
    """

    evidence_id: str
    document_id: str = ""
    limitation_id: str = ""
    claim_number: Optional[int] = None

    text: str = ""
    source_type: str = SOURCE_UNKNOWN

    source_url: str = ""
    publication_number: str = ""
    title: str = ""

    page: Optional[int] = None
    paragraph_id: str = ""
    section: str = ""

    publication_date: str = ""
    priority_date: str = ""

    retrieval_score: float = 0.0
    provenance_score: float = 0.0

    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class VerificationResult:
    """
    Verification decision for one evidence item.
    """

    verification_id: str
    evidence_id: str

    limitation_id: str = ""
    claim_number: Optional[int] = None

    status: str = STATUS_UNVERIFIED
    support_type: str = SUPPORT_NONE

    confidence: float = 0.0
    lexical_score: float = 0.0
    phrase_score: float = 0.0
    context_score: float = 0.0
    provenance_score: float = 0.0
    contradiction_score: float = 0.0

    matched_terms: List[str] = field(default_factory=list)
    missing_terms: List[str] = field(default_factory=list)
    contradictory_terms: List[str] = field(default_factory=list)

    reasoning: str = ""
    verification_notes: List[str] = field(default_factory=list)

    source_url: str = ""
    publication_number: str = ""
    source_type: str = ""

    verified_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LimitationVerification:
    """
    Aggregated verification for one claim limitation.
    """

    limitation_id: str
    claim_number: Optional[int] = None
    limitation_text: str = ""

    status: str = STATUS_NOT_FOUND

    confidence: float = 0.0
    coverage: float = 0.0

    verified_evidence_ids: List[str] = field(default_factory=list)
    partial_evidence_ids: List[str] = field(default_factory=list)
    contradicted_evidence_ids: List[str] = field(default_factory=list)

    missing_terms: List[str] = field(default_factory=list)

    reasoning: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class EvidenceVerificationReport:
    """
    Complete verification report.
    """

    verification_id: str
    limitation_verifications: List[LimitationVerification] = field(
        default_factory=list
    )
    evidence_results: List[VerificationResult] = field(
        default_factory=list
    )

    verified_count: int = 0
    partial_count: int = 0
    contradicted_count: int = 0
    unverified_count: int = 0

    overall_coverage: float = 0.0
    overall_confidence: float = 0.0

    warnings: List[str] = field(default_factory=list)

    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "limitation_verifications": [
                item.to_dict()
                for item in self.limitation_verifications
            ],
            "evidence_results": [
                item.to_dict()
                for item in self.evidence_results
            ],
            "verified_count": self.verified_count,
            "partial_count": self.partial_count,
            "contradicted_count": self.contradicted_count,
            "unverified_count": self.unverified_count,
            "overall_coverage": self.overall_coverage,
            "overall_confidence": self.overall_confidence,
            "warnings": self.warnings,
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(str(value).split()).strip()


def _normalize(value: Any) -> str:
    text = _clean(value).lower()

    text = re.sub(
        r"[^a-z0-9\s\-\/\.]",
        " ",
        text,
    )

    text = re.sub(r"\s+", " ", text)

    return text.strip()


def _stable_id(prefix: str, *parts: Any) -> str:
    payload = "||".join(
        _normalize(part)
        for part in parts
    )

    digest = hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()[:16]

    return f"{prefix}-{digest}"


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:
    return max(
        minimum,
        min(maximum, value),
    )


def _unique(items: Iterable[str]) -> List[str]:
    result: List[str] = []
    seen = set()

    for item in items:
        cleaned = _clean(item)

        if not cleaned:
            continue

        key = cleaned.lower()

        if key not in seen:
            seen.add(key)
            result.append(cleaned)

    return result


def _tokenize(text: str) -> List[str]:
    normalized = _normalize(text)

    return [
        token
        for token in normalized.split()
        if len(token) >= 3
    ]


def _token_set(text: str) -> set:
    return set(_tokenize(text))


def _ngrams(tokens: Sequence[str], n: int) -> set:
    if len(tokens) < n:
        return set()

    return {
        " ".join(tokens[index:index + n])
        for index in range(len(tokens) - n + 1)
    }


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Evidence normalization
# ---------------------------------------------------------------------------


class EvidenceNormalizer:
    """
    Converts evidence objects from different pipeline stages into a common
    verification representation.
    """

    def normalize(
        self,
        evidence: Any,
        limitation_id: str = "",
        claim_number: Optional[int] = None,
    ) -> VerificationEvidence:

        if isinstance(evidence, VerificationEvidence):
            return evidence

        if not isinstance(evidence, Mapping):
            evidence = {
                "text": _clean(evidence),
            }

        evidence_id = _clean(
            evidence.get("evidence_id")
            or evidence.get("id")
            or _stable_id(
                "EVID",
                evidence.get("document_id", ""),
                evidence.get("text", ""),
                evidence.get("source_url", ""),
            )
        )

        source_type = _clean(
            evidence.get("source_type")
            or evidence.get("source")
            or evidence.get("section_type")
            or SOURCE_UNKNOWN
        ).lower()

        return VerificationEvidence(
            evidence_id=evidence_id,
            document_id=_clean(
                evidence.get("document_id")
                or evidence.get("doc_id")
            ),
            limitation_id=_clean(
                evidence.get("limitation_id")
                or limitation_id
            ),
            claim_number=(
                evidence.get("claim_number")
                if evidence.get("claim_number") is not None
                else claim_number
            ),
            text=_clean(
                evidence.get("text")
                or evidence.get("passage")
                or evidence.get("content")
                or evidence.get("snippet")
            ),
            source_type=source_type,
            source_url=_clean(
                evidence.get("source_url")
                or evidence.get("url")
            ),
            publication_number=_clean(
                evidence.get("publication_number")
                or evidence.get("patent_number")
            ),
            title=_clean(
                evidence.get("title")
                or evidence.get("document_title")
            ),
            page=evidence.get("page"),
            paragraph_id=_clean(
                evidence.get("paragraph_id")
                or evidence.get("paragraph")
            ),
            section=_clean(
                evidence.get("section")
            ),
            publication_date=_clean(
                evidence.get("publication_date")
            ),
            priority_date=_clean(
                evidence.get("priority_date")
            ),
            retrieval_score=_safe_float(
                evidence.get("retrieval_score")
                or evidence.get("score")
            ),
            provenance_score=_safe_float(
                evidence.get("provenance_score")
            ),
            raw=dict(evidence),
        )


# ---------------------------------------------------------------------------
# Limitation extraction
# ---------------------------------------------------------------------------


class LimitationVerifier:
    """
    Performs deterministic comparison between a limitation and an evidence
    passage.
    """

    STOPWORDS = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "where",
        "which",
        "having",
        "comprising",
        "including",
        "said",
        "thereof",
        "therein",
        "each",
        "one",
        "two",
        "method",
        "system",
        "device",
        "apparatus",
    }

    CONTRADICTION_PATTERNS = (
        r"\bnot\b",
        r"\bwithout\b",
        r"\babsence of\b",
        r"\babsent\b",
        r"\bdoes not\b",
        r"\bdo not\b",
        r"\bnever\b",
        r"\binstead of\b",
        r"\bopposite\b",
        r"\bexclusive of\b",
    )

    def __init__(
        self,
        explicit_threshold: float = 0.72,
        partial_threshold: float = 0.45,
        contextual_threshold: float = 0.25,
    ) -> None:
        self.explicit_threshold = explicit_threshold
        self.partial_threshold = partial_threshold
        self.contextual_threshold = contextual_threshold

    def verify(
        self,
        limitation_text: str,
        evidence: VerificationEvidence,
    ) -> VerificationResult:

        limitation = _normalize(limitation_text)
        passage = _normalize(evidence.text)

        verification_id = _stable_id(
            "VER",
            evidence.evidence_id,
            limitation_text,
        )

        if not limitation or not passage:
            return VerificationResult(
                verification_id=verification_id,
                evidence_id=evidence.evidence_id,
                limitation_id=evidence.limitation_id,
                claim_number=evidence.claim_number,
                status=STATUS_UNVERIFIED,
                support_type=SUPPORT_NONE,
                confidence=0.0,
                reasoning="Limitation or evidence passage is empty.",
                verification_notes=[
                    "Insufficient text for deterministic verification."
                ],
                source_url=evidence.source_url,
                publication_number=evidence.publication_number,
                source_type=evidence.source_type,
                verified_at=_utc_now(),
            )

        limitation_tokens = [
            token
            for token in _tokenize(limitation)
            if token not in self.STOPWORDS
        ]

        evidence_tokens = _token_set(passage)

        matched_terms = [
            token
            for token in limitation_tokens
            if token in evidence_tokens
        ]

        missing_terms = [
            token
            for token in limitation_tokens
            if token not in evidence_tokens
        ]

        if limitation_tokens:
            lexical_score = (
                len(matched_terms)
                / len(limitation_tokens)
            )
        else:
            lexical_score = 0.0

        limitation_bigrams = _ngrams(
            limitation_tokens,
            2,
        )

        evidence_bigrams = _ngrams(
            _tokenize(passage),
            2,
        )

        if limitation_bigrams:
            phrase_score = (
                len(
                    limitation_bigrams
                    & evidence_bigrams
                )
                / len(limitation_bigrams)
            )
        else:
            phrase_score = 0.0

        context_score = self._context_score(
            limitation,
            passage,
        )

        contradiction_terms = self._find_contradictions(
            limitation,
            passage,
        )

        contradiction_score = min(
            1.0,
            len(contradiction_terms) * 0.25,
        )

        provenance_score = self._provenance_score(
            evidence
        )

        combined_score = (
            0.50 * lexical_score
            + 0.20 * phrase_score
            + 0.15 * context_score
            + 0.15 * provenance_score
        )

        combined_score *= (
            1.0 - 0.50 * contradiction_score
        )

        combined_score = _clamp(combined_score)

        support_type = self._classify_support(
            combined_score,
            lexical_score,
            phrase_score,
        )

        status = self._classify_status(
            support_type=support_type,
            contradiction_score=contradiction_score,
        )

        reasoning = self._build_reasoning(
            support_type=support_type,
            lexical_score=lexical_score,
            phrase_score=phrase_score,
            context_score=context_score,
            provenance_score=provenance_score,
            contradiction_score=contradiction_score,
            matched_terms=matched_terms,
            missing_terms=missing_terms,
        )

        notes = self._verification_notes(
            evidence=evidence,
            support_type=support_type,
            contradiction_score=contradiction_score,
        )

        return VerificationResult(
            verification_id=verification_id,
            evidence_id=evidence.evidence_id,
            limitation_id=evidence.limitation_id,
            claim_number=evidence.claim_number,
            status=status,
            support_type=support_type,
            confidence=combined_score,
            lexical_score=lexical_score,
            phrase_score=phrase_score,
            context_score=context_score,
            provenance_score=provenance_score,
            contradiction_score=contradiction_score,
            matched_terms=matched_terms,
            missing_terms=missing_terms,
            contradictory_terms=contradiction_terms,
            reasoning=reasoning,
            verification_notes=notes,
            source_url=evidence.source_url,
            publication_number=evidence.publication_number,
            source_type=evidence.source_type,
            verified_at=_utc_now(),
        )

    def _context_score(
        self,
        limitation: str,
        passage: str,
    ) -> float:

        limitation_tokens = _token_set(limitation)
        passage_tokens = _token_set(passage)

        if not limitation_tokens:
            return 0.0

        technical_tokens = {
            token
            for token in limitation_tokens
            if len(token) >= 5
        }

        if not technical_tokens:
            return 0.0

        overlap = (
            technical_tokens
            & passage_tokens
        )

        return _clamp(
            len(overlap)
            / len(technical_tokens)
        )

    def _provenance_score(
        self,
        evidence: VerificationEvidence,
    ) -> float:

        score = 0.0

        if evidence.source_url:
            score += 0.25

        if evidence.publication_number:
            score += 0.20

        if evidence.document_id:
            score += 0.15

        if evidence.source_type in {
            SOURCE_CLAIM,
            SOURCE_ABSTRACT,
            SOURCE_DESCRIPTION,
            SOURCE_PARAGRAPH,
        }:
            score += 0.20

        if evidence.page is not None:
            score += 0.05

        if evidence.paragraph_id:
            score += 0.05

        if evidence.section:
            score += 0.05

        supplied = evidence.provenance_score

        if supplied > 0:
            score = (
                0.5 * score
                + 0.5 * _clamp(supplied)
            )

        return _clamp(score)

    def _find_contradictions(
        self,
        limitation: str,
        passage: str,
    ) -> List[str]:

        contradictions = []

        for pattern in self.CONTRADICTION_PATTERNS:
            if re.search(pattern, passage):
                contradictions.append(
                    re.sub(
                        r"\\b|\\",
                        "",
                        pattern,
                    )
                )

        return _unique(contradictions)

    def _classify_support(
        self,
        combined_score: float,
        lexical_score: float,
        phrase_score: float,
    ) -> str:

        if (
            combined_score >= self.explicit_threshold
            and lexical_score >= 0.60
        ):
            return SUPPORT_EXPLICIT

        if (
            combined_score >= self.partial_threshold
            and lexical_score >= 0.40
        ):
            return SUPPORT_PARTIAL

        if combined_score >= self.contextual_threshold:
            return SUPPORT_CONTEXTUAL

        if lexical_score > 0:
            return SUPPORT_WEAK

        return SUPPORT_NONE

    def _classify_status(
        self,
        support_type: str,
        contradiction_score: float,
    ) -> str:

        if contradiction_score >= 0.50:
            return STATUS_CONTRADICTED

        if support_type == SUPPORT_EXPLICIT:
            return STATUS_VERIFIED

        if support_type == SUPPORT_PARTIAL:
            return STATUS_PARTIALLY_VERIFIED

        if support_type in {
            SUPPORT_CONTEXTUAL,
            SUPPORT_WEAK,
        }:
            return STATUS_UNVERIFIED

        return STATUS_NOT_FOUND

    def _build_reasoning(
        self,
        support_type: str,
        lexical_score: float,
        phrase_score: float,
        context_score: float,
        provenance_score: float,
        contradiction_score: float,
        matched_terms: Sequence[str],
        missing_terms: Sequence[str],
    ) -> str:

        parts = [
            f"Support classification: {support_type}.",
            f"Lexical overlap={lexical_score:.2f}.",
            f"Phrase overlap={phrase_score:.2f}.",
            f"Context score={context_score:.2f}.",
            f"Provenance score={provenance_score:.2f}.",
        ]

        if contradiction_score > 0:
            parts.append(
                f"Potential contradiction signal="
                f"{contradiction_score:.2f}."
            )

        if matched_terms:
            parts.append(
                "Matched terms: "
                + ", ".join(matched_terms[:12])
                + "."
            )

        if missing_terms:
            parts.append(
                "Missing terms: "
                + ", ".join(missing_terms[:12])
                + "."
            )

        return " ".join(parts)

    def _verification_notes(
        self,
        evidence: VerificationEvidence,
        support_type: str,
        contradiction_score: float,
    ) -> List[str]:

        notes: List[str] = []

        if not evidence.source_url:
            notes.append(
                "No source URL supplied; source verification is limited."
            )

        if not evidence.publication_number:
            notes.append(
                "No publication number supplied."
            )

        if evidence.source_type in {
            SOURCE_METADATA,
            SOURCE_UNKNOWN,
        }:
            notes.append(
                "Evidence is not from a substantive patent text section."
            )

        if support_type in {
            SUPPORT_CONTEXTUAL,
            SUPPORT_WEAK,
        }:
            notes.append(
                "Evidence should be manually reviewed before being "
                "used for substantive patent analysis."
            )

        if contradiction_score > 0:
            notes.append(
                "Potential negation or contradiction language detected."
            )

        return notes


# ---------------------------------------------------------------------------
# Evidence verifier
# ---------------------------------------------------------------------------


class EvidenceVerifier:
    """
    High-level evidence verification engine.
    """

    def __init__(
        self,
        limitation_verifier: Optional[LimitationVerifier] = None,
        normalizer: Optional[EvidenceNormalizer] = None,
    ) -> None:

        self.limitation_verifier = (
            limitation_verifier
            or LimitationVerifier()
        )

        self.normalizer = (
            normalizer
            or EvidenceNormalizer()
        )

    def verify_evidence(
        self,
        limitation_text: str,
        evidence: Any,
        limitation_id: str = "",
        claim_number: Optional[int] = None,
    ) -> VerificationResult:

        normalized = self.normalizer.normalize(
            evidence=evidence,
            limitation_id=limitation_id,
            claim_number=claim_number,
        )

        return self.limitation_verifier.verify(
            limitation_text=limitation_text,
            evidence=normalized,
        )

    def verify_limitation(
        self,
        limitation_text: str,
        evidence_items: Sequence[Any],
        limitation_id: str = "",
        claim_number: Optional[int] = None,
    ) -> LimitationVerification:

        normalized_items = [
            self.normalizer.normalize(
                evidence=item,
                limitation_id=limitation_id,
                claim_number=claim_number,
            )
            for item in evidence_items
        ]

        results = [
            self.limitation_verifier.verify(
                limitation_text=limitation_text,
                evidence=item,
            )
            for item in normalized_items
        ]

        return self._aggregate_limitation(
            limitation_id=limitation_id,
            limitation_text=limitation_text,
            claim_number=claim_number,
            results=results,
        )

    def verify_claim(
        self,
        limitations: Sequence[Any],
        evidence: Sequence[Any],
        claim_number: Optional[int] = None,
    ) -> EvidenceVerificationReport:

        limitation_items = self._normalize_limitations(
            limitations,
            claim_number=claim_number,
        )

        evidence_items = [
            self.normalizer.normalize(
                item,
                claim_number=claim_number,
            )
            for item in evidence
        ]

        limitation_verifications: List[
            LimitationVerification
        ] = []

        evidence_results: List[VerificationResult] = []

        for limitation_id, limitation_text in limitation_items:

            related = [
                item
                for item in evidence_items
                if (
                    not item.limitation_id
                    or item.limitation_id == limitation_id
                )
            ]

            verification = self.verify_limitation(
                limitation_text=limitation_text,
                evidence_items=related,
                limitation_id=limitation_id,
                claim_number=claim_number,
            )

            limitation_verifications.append(
                verification
            )

            for item in related:
                evidence_results.append(
                    self.limitation_verifier.verify(
                        limitation_text=limitation_text,
                        evidence=item,
                    )
                )

        return self._build_report(
            limitation_verifications=limitation_verifications,
            evidence_results=evidence_results,
        )

    def verify(
        self,
        limitation_text: str,
        evidence: Sequence[Any],
        limitation_id: str = "",
        claim_number: Optional[int] = None,
    ) -> LimitationVerification:

        return self.verify_limitation(
            limitation_text=limitation_text,
            evidence_items=evidence,
            limitation_id=limitation_id,
            claim_number=claim_number,
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _normalize_limitations(
        self,
        limitations: Sequence[Any],
        claim_number: Optional[int] = None,
    ) -> List[Tuple[str, str]]:

        output: List[Tuple[str, str]] = []

        for index, item in enumerate(limitations, start=1):

            if isinstance(item, Mapping):
                limitation_id = _clean(
                    item.get("limitation_id")
                    or item.get("id")
                    or f"L{index}"
                )

                text = _clean(
                    item.get("text")
                    or item.get("limitation")
                    or item.get("content")
                )

            else:
                limitation_id = f"L{index}"
                text = _clean(item)

            if text:
                output.append(
                    (
                        limitation_id,
                        text,
                    )
                )

        return output

    def _aggregate_limitation(
        self,
        limitation_id: str,
        limitation_text: str,
        claim_number: Optional[int],
        results: Sequence[VerificationResult],
    ) -> LimitationVerification:

        if not results:
            return LimitationVerification(
                limitation_id=limitation_id,
                claim_number=claim_number,
                limitation_text=limitation_text,
                status=STATUS_NOT_FOUND,
                confidence=0.0,
                coverage=0.0,
                reasoning=(
                    "No evidence passages were available "
                    "for verification."
                ),
            )

        verified = [
            item
            for item in results
            if item.status == STATUS_VERIFIED
        ]

        partial = [
            item
            for item in results
            if item.status == STATUS_PARTIALLY_VERIFIED
        ]

        contradicted = [
            item
            for item in results
            if item.status == STATUS_CONTRADICTED
        ]

        ranked = sorted(
            results,
            key=lambda item: item.confidence,
            reverse=True,
        )

        best = ranked[0]

        if verified:
            status = STATUS_VERIFIED
        elif partial:
            status = STATUS_PARTIALLY_VERIFIED
        elif contradicted:
            status = STATUS_CONTRADICTED
        else:
            status = STATUS_UNVERIFIED

        confidence = best.confidence

        coverage = self._calculate_coverage(
            results
        )

        missing_terms = _unique(
            term
            for result in results
            for term in result.missing_terms
        )

        reasoning = (
            f"{len(verified)} verified evidence item(s), "
            f"{len(partial)} partially verified item(s), "
            f"{len(contradicted)} contradicted item(s). "
            f"Best verification confidence={confidence:.2f}; "
            f"coverage={coverage:.2f}."
        )

        return LimitationVerification(
            limitation_id=limitation_id,
            claim_number=claim_number,
            limitation_text=limitation_text,
            status=status,
            confidence=confidence,
            coverage=coverage,
            verified_evidence_ids=[
                item.evidence_id
                for item in verified
            ],
            partial_evidence_ids=[
                item.evidence_id
                for item in partial
            ],
            contradicted_evidence_ids=[
                item.evidence_id
                for item in contradicted
            ],
            missing_terms=missing_terms,
            reasoning=reasoning,
        )

    def _calculate_coverage(
        self,
        results: Sequence[VerificationResult],
    ) -> float:

        if not results:
            return 0.0

        best = max(
            result.confidence
            for result in results
        )

        return _clamp(best)

    def _build_report(
        self,
        limitation_verifications: Sequence[
            LimitationVerification
        ],
        evidence_results: Sequence[
            VerificationResult
        ],
    ) -> EvidenceVerificationReport:

        verified_count = sum(
            1
            for item in evidence_results
            if item.status == STATUS_VERIFIED
        )

        partial_count = sum(
            1
            for item in evidence_results
            if item.status == STATUS_PARTIALLY_VERIFIED
        )

        contradicted_count = sum(
            1
            for item in evidence_results
            if item.status == STATUS_CONTRADICTED
        )

        unverified_count = sum(
            1
            for item in evidence_results
            if item.status in {
                STATUS_UNVERIFIED,
                STATUS_NOT_FOUND,
            }
        )

        if limitation_verifications:
            overall_coverage = sum(
                item.coverage
                for item in limitation_verifications
            ) / len(limitation_verifications)

            overall_confidence = sum(
                item.confidence
                for item in limitation_verifications
            ) / len(limitation_verifications)

        else:
            overall_coverage = 0.0
            overall_confidence = 0.0

        warnings: List[str] = []

        if unverified_count:
            warnings.append(
                f"{unverified_count} evidence item(s) were not "
                f"strongly verified."
            )

        if contradicted_count:
            warnings.append(
                f"{contradicted_count} evidence item(s) contain "
                f"potential contradiction signals."
            )

        if overall_coverage < 0.50:
            warnings.append(
                "Overall evidence coverage is below 0.50; "
                "manual verification is recommended."
            )

        verification_id = _stable_id(
            "VREPORT",
            _utc_now(),
            len(limitation_verifications),
            len(evidence_results),
        )

        return EvidenceVerificationReport(
            verification_id=verification_id,
            limitation_verifications=list(
                limitation_verifications
            ),
            evidence_results=list(evidence_results),
            verified_count=verified_count,
            partial_count=partial_count,
            contradicted_count=contradicted_count,
            unverified_count=unverified_count,
            overall_coverage=_clamp(overall_coverage),
            overall_confidence=_clamp(overall_confidence),
            warnings=warnings,
            created_at=_utc_now(),
        )


# ---------------------------------------------------------------------------
# Claim-level convenience functions
# ---------------------------------------------------------------------------


def verify_evidence(
    limitation_text: str,
    evidence: Any,
    limitation_id: str = "",
    claim_number: Optional[int] = None,
) -> VerificationResult:

    verifier = EvidenceVerifier()

    return verifier.verify_evidence(
        limitation_text=limitation_text,
        evidence=evidence,
        limitation_id=limitation_id,
        claim_number=claim_number,
    )


def verify_limitation(
    limitation_text: str,
    evidence: Sequence[Any],
    limitation_id: str = "",
    claim_number: Optional[int] = None,
) -> LimitationVerification:

    verifier = EvidenceVerifier()

    return verifier.verify_limitation(
        limitation_text=limitation_text,
        evidence_items=evidence,
        limitation_id=limitation_id,
        claim_number=claim_number,
    )


def verify_claim(
    limitations: Sequence[Any],
    evidence: Sequence[Any],
    claim_number: Optional[int] = None,
) -> EvidenceVerificationReport:

    verifier = EvidenceVerifier()

    return verifier.verify_claim(
        limitations=limitations,
        evidence=evidence,
        claim_number=claim_number,
    )


# ---------------------------------------------------------------------------
# Evidence quality utilities
# ---------------------------------------------------------------------------


def calculate_verification_coverage(
    verification: Any,
) -> float:

    if isinstance(
        verification,
        EvidenceVerificationReport,
    ):
        return verification.overall_coverage

    if isinstance(
        verification,
        LimitationVerification,
    ):
        return verification.coverage

    if isinstance(
        verification,
        VerificationResult,
    ):
        return verification.confidence

    if isinstance(verification, Mapping):
        for key in (
            "overall_coverage",
            "coverage",
            "confidence",
        ):
            if key in verification:
                return _clamp(
                    _safe_float(
                        verification[key]
                    )
                )

    return 0.0


def get_verified_evidence(
    results: Sequence[VerificationResult],
) -> List[VerificationResult]:

    return [
        result
        for result in results
        if result.status == STATUS_VERIFIED
    ]


def get_partial_evidence(
    results: Sequence[VerificationResult],
) -> List[VerificationResult]:

    return [
        result
        for result in results
        if result.status == STATUS_PARTIALLY_VERIFIED
    ]


def get_contradicted_evidence(
    results: Sequence[VerificationResult],
) -> List[VerificationResult]:

    return [
        result
        for result in results
        if result.status == STATUS_CONTRADICTED
    ]


def get_unverified_evidence(
    results: Sequence[VerificationResult],
) -> List[VerificationResult]:

    return [
        result
        for result in results
        if result.status in {
            STATUS_UNVERIFIED,
            STATUS_NOT_FOUND,
        }
    ]


def evidence_verification_statistics(
    report: EvidenceVerificationReport,
) -> Dict[str, Any]:

    total = (
        report.verified_count
        + report.partial_count
        + report.contradicted_count
        + report.unverified_count
    )

    return {
        "version": EVIDENCE_VERIFIER_VERSION,
        "verification_id": report.verification_id,
        "total_evidence_items": total,
        "verified_count": report.verified_count,
        "partial_count": report.partial_count,
        "contradicted_count": report.contradicted_count,
        "unverified_count": report.unverified_count,
        "overall_coverage": report.overall_coverage,
        "overall_confidence": report.overall_confidence,
        "warning_count": len(report.warnings),
    }


# ---------------------------------------------------------------------------
# Evidence packet
# ---------------------------------------------------------------------------


def build_verified_evidence_packet(
    report: EvidenceVerificationReport,
) -> Dict[str, Any]:
    """
    Build a compact evidence packet for downstream novelty/inventive-step
    analysis.

    Important:
        This packet contains evidence quality information. It does not
        itself establish any legal conclusion.
    """

    verified = get_verified_evidence(
        report.evidence_results
    )

    partial = get_partial_evidence(
        report.evidence_results
    )

    contradicted = get_contradicted_evidence(
        report.evidence_results
    )

    return {
        "version": EVIDENCE_VERIFIER_VERSION,
        "verification_id": report.verification_id,
        "verified_evidence": [
            item.to_dict()
            for item in verified
        ],
        "partial_evidence": [
            item.to_dict()
            for item in partial
        ],
        "contradicted_evidence": [
            item.to_dict()
            for item in contradicted
        ],
        "limitation_verifications": [
            item.to_dict()
            for item in report.limitation_verifications
        ],
        "coverage": report.overall_coverage,
        "confidence": report.overall_confidence,
        "warnings": report.warnings,
        "review_required": bool(
            report.warnings
            or contradicted
            or report.overall_coverage < 0.70
        ),
    }


# ---------------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------------


EvidenceVerifierEngine = EvidenceVerifier
EvidenceVerification = VerificationResult
EvidenceReport = EvidenceVerificationReport


def verify_retrieved_evidence(
    limitation_text: str,
    evidence: Any,
    **kwargs: Any,
) -> VerificationResult:
    return verify_evidence(
        limitation_text=limitation_text,
        evidence=evidence,
        **kwargs,
    )


def verify_limitation_evidence(
    limitation_text: str,
    evidence: Sequence[Any],
    **kwargs: Any,
) -> LimitationVerification:
    return verify_limitation(
        limitation_text=limitation_text,
        evidence=evidence,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


__all__ = [
    "EVIDENCE_VERIFIER_VERSION",

    "STATUS_VERIFIED",
    "STATUS_PARTIALLY_VERIFIED",
    "STATUS_UNVERIFIED",
    "STATUS_CONTRADICTED",
    "STATUS_NOT_FOUND",

    "SUPPORT_EXPLICIT",
    "SUPPORT_PARTIAL",
    "SUPPORT_CONTEXTUAL",
    "SUPPORT_WEAK",
    "SUPPORT_NONE",

    "SOURCE_CLAIM",
    "SOURCE_ABSTRACT",
    "SOURCE_DESCRIPTION",
    "SOURCE_PARAGRAPH",
    "SOURCE_SECTION",
    "SOURCE_METADATA",
    "SOURCE_UNKNOWN",

    "VerificationEvidence",
    "VerificationResult",
    "LimitationVerification",
    "EvidenceVerificationReport",

    "EvidenceNormalizer",
    "LimitationVerifier",
    "EvidenceVerifier",

    "verify_evidence",
    "verify_limitation",
    "verify_claim",

    "calculate_verification_coverage",
    "get_verified_evidence",
    "get_partial_evidence",
    "get_contradicted_evidence",
    "get_unverified_evidence",

    "evidence_verification_statistics",
    "build_verified_evidence_packet",

    "EvidenceVerifierEngine",
    "EvidenceVerification",
    "EvidenceReport",

    "verify_retrieved_evidence",
    "verify_limitation_evidence",
]
