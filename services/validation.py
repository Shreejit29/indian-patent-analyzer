"""
services/validation.py

Indian Patent Analyzer
Pipeline validation and consistency-checking layer.

Version: 3.0.0

Purpose
-------
Validate analysis inputs and outputs before they reach the final report.

Checks include:
    - document integrity
    - claim numbering
    - claim dependencies
    - limitation references
    - evidence references
    - prior-art references
    - finding references
    - score ranges
    - provenance references
    - knowledge-graph consistency
    - pipeline stage consistency
    - orphan objects
    - duplicate identifiers

Design principles
-----------------
1. Validation detects problems; it does not silently repair them.
2. Warnings and errors are kept separate.
3. Validation never makes legal conclusions.
4. Unknown/missing data is different from contradictory data.
5. The validator is deterministic.
6. The validator can operate on the complete pipeline result or individual
   analysis components.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set


VALIDATION_VERSION = "3.0.0"


# ---------------------------------------------------------------------------
# Severity constants
# ---------------------------------------------------------------------------

SEVERITY_ERROR = "error"
SEVERITY_WARNING = "warning"
SEVERITY_INFO = "info"


# ---------------------------------------------------------------------------
# Validation categories
# ---------------------------------------------------------------------------

CATEGORY_DOCUMENT = "document"
CATEGORY_CLAIMS = "claims"
CATEGORY_LIMITATIONS = "limitations"
CATEGORY_EVIDENCE = "evidence"
CATEGORY_PRIOR_ART = "prior_art"
CATEGORY_FINDINGS = "findings"
CATEGORY_SCORES = "scores"
CATEGORY_PROVENANCE = "provenance"
CATEGORY_GRAPH = "knowledge_graph"
CATEGORY_PIPELINE = "pipeline"
CATEGORY_AI = "ai"
CATEGORY_SCHEMA = "schema"


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class ValidationIssue:
    """
    One validation issue.
    """

    issue_id: str
    severity: str
    category: str
    code: str

    message: str

    path: str = ""
    artifact_id: str = ""

    expected: Any = None
    actual: Any = None

    remediation: str = ""

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ValidationResult:
    """
    Complete validation output.
    """

    validation_id: str

    valid: bool

    errors: List[ValidationIssue] = field(
        default_factory=list
    )

    warnings: List[ValidationIssue] = field(
        default_factory=list
    )

    info: List[ValidationIssue] = field(
        default_factory=list
    )

    checked_components: List[str] = field(
        default_factory=list
    )

    statistics: Dict[str, Any] = field(
        default_factory=dict
    )

    created_at: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "validation_id": self.validation_id,
            "valid": self.valid,
            "errors": [
                issue.to_dict()
                for issue in self.errors
            ],
            "warnings": [
                issue.to_dict()
                for issue in self.warnings
            ],
            "info": [
                issue.to_dict()
                for issue in self.info
            ],
            "checked_components": list(
                self.checked_components
            ),
            "statistics": dict(
                self.statistics
            ),
            "created_at": self.created_at,
        }


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(str(value).split()).strip()


def _normalize(value: Any) -> str:
    return _clean(value).lower()


def _stable_id(
    prefix: str,
    *parts: Any,
) -> str:

    payload = "||".join(
        _normalize(part)
        for part in parts
    )

    digest = hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()[:16]

    return f"{prefix.upper()}-{digest}"


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _is_number(value: Any) -> bool:
    return isinstance(
        value,
        (int, float),
    ) and not isinstance(
        value,
        bool,
    )


def _in_range(
    value: Any,
    minimum: float,
    maximum: float,
) -> bool:

    if not _is_number(value):
        return False

    value = float(value)

    return (
        math.isfinite(value)
        and minimum <= value <= maximum
    )


def _as_list(value: Any) -> List[Any]:

    if value is None:
        return []

    if isinstance(
        value,
        list,
    ):
        return value

    if isinstance(
        value,
        tuple,
    ):
        return list(value)

    return [value]


def _as_mapping(
    value: Any,
) -> Mapping[str, Any]:

    if isinstance(
        value,
        Mapping,
    ):
        return value

    return {}


def _get(
    obj: Any,
    *keys: str,
    default: Any = None,
) -> Any:

    if not isinstance(
        obj,
        Mapping,
    ):
        return default

    for key in keys:

        if key in obj:
            return obj[key]

    return default


def _iter_dicts(
    value: Any,
) -> Iterable[Mapping[str, Any]]:

    if isinstance(
        value,
        Mapping,
    ):
        yield value

    elif isinstance(
        value,
        (list, tuple),
    ):

        for item in value:

            if isinstance(
                item,
                Mapping,
            ):
                yield item


# ---------------------------------------------------------------------------
# Validator
# ---------------------------------------------------------------------------


class PatentAnalysisValidator:
    """
    Main deterministic validation engine.
    """

    def __init__(
        self,
        strict: bool = False,
    ) -> None:

        self.strict = strict

        self.issues: List[
            ValidationIssue
        ] = []

        self.checked_components: List[
            str
        ] = []

    # ------------------------------------------------------------------
    # Issue handling
    # ------------------------------------------------------------------

    def add_issue(
        self,
        severity: str,
        category: str,
        code: str,
        message: str,
        path: str = "",
        artifact_id: str = "",
        expected: Any = None,
        actual: Any = None,
        remediation: str = "",
        metadata: Optional[
            Mapping[str, Any]
        ] = None,
    ) -> ValidationIssue:

        issue = ValidationIssue(
            issue_id=_stable_id(
                "VAL",
                severity,
                category,
                code,
                path,
                message,
            ),
            severity=severity,
            category=category,
            code=code,
            message=message,
            path=path,
            artifact_id=artifact_id,
            expected=expected,
            actual=actual,
            remediation=remediation,
            metadata=dict(
                metadata or {}
            ),
        )

        self.issues.append(issue)

        return issue

    def error(
        self,
        category: str,
        code: str,
        message: str,
        **kwargs: Any,
    ) -> ValidationIssue:

        return self.add_issue(
            SEVERITY_ERROR,
            category,
            code,
            message,
            **kwargs,
        )

    def warning(
        self,
        category: str,
        code: str,
        message: str,
        **kwargs: Any,
    ) -> ValidationIssue:

        return self.add_issue(
            SEVERITY_WARNING,
            category,
            code,
            message,
            **kwargs,
        )

    def info(
        self,
        category: str,
        code: str,
        message: str,
        **kwargs: Any,
    ) -> ValidationIssue:

        return self.add_issue(
            SEVERITY_INFO,
            category,
            code,
            message,
            **kwargs,
        )

    def mark_component(
        self,
        name: str,
    ) -> None:

        if name not in self.checked_components:
            self.checked_components.append(
                name
            )

    # ------------------------------------------------------------------
    # Document validation
    # ------------------------------------------------------------------

    def validate_document(
        self,
        document: Any,
    ) -> None:

        self.mark_component(
            CATEGORY_DOCUMENT
        )

        if not isinstance(
            document,
            Mapping,
        ):
            self.error(
                CATEGORY_DOCUMENT,
                "DOC-NOT-MAPPING",
                "Document object is not a mapping.",
                path="document",
                remediation=(
                    "Pass the parsed document dictionary or "
                    "a compatible mapping."
                ),
            )
            return

        document_id = _clean(
            _get(
                document,
                "document_id",
                "id",
            )
        )

        if not document_id:
            self.error(
                CATEGORY_DOCUMENT,
                "DOC-MISSING-ID",
                "Document has no document_id.",
                path="document.document_id",
                remediation=(
                    "Assign a stable document identifier."
                ),
            )

        document_hash = _clean(
            _get(
                document,
                "sha256",
                "document_hash",
                "hash",
            )
        )

        if not document_hash:
            self.warning(
                CATEGORY_DOCUMENT,
                "DOC-MISSING-HASH",
                "Document has no SHA-256 hash.",
                path="document.sha256",
                remediation=(
                    "Calculate and retain the source document hash."
                ),
            )
        elif not re.fullmatch(
            r"[0-9a-fA-F]{32,128}",
            document_hash,
        ):
            self.warning(
                CATEGORY_DOCUMENT,
                "DOC-HASH-FORMAT",
                "Document hash does not look like a hexadecimal digest.",
                path="document.sha256",
                actual=document_hash,
                remediation=(
                    "Store the canonical SHA-256 hexadecimal digest."
                ),
            )

        claims = _get(
            document,
            "claims",
            default=[],
        )

        if claims is None:
            self.warning(
                CATEGORY_DOCUMENT,
                "DOC-CLAIMS-NONE",
                "Document claims collection is null.",
                path="document.claims",
            )

    # ------------------------------------------------------------------
    # Claim validation
    # ------------------------------------------------------------------

    def validate_claims(
        self,
        claims: Any,
    ) -> None:

        self.mark_component(
            CATEGORY_CLAIMS
        )

        claim_items = list(
            _iter_dicts(claims)
        )

        if claims is None:
            self.warning(
                CATEGORY_CLAIMS,
                "CLAIMS-NONE",
                "Claims collection is missing.",
                path="claims",
            )
            return

        if not isinstance(
            claims,
            (list, tuple),
        ):
            self.warning(
                CATEGORY_CLAIMS,
                "CLAIMS-NOT-LIST",
                "Claims collection is not a list-like structure.",
                path="claims",
            )

        if not claim_items:
            self.warning(
                CATEGORY_CLAIMS,
                "CLAIMS-EMPTY",
                "No structured claims were found.",
                path="claims",
                remediation=(
                    "Run the document claim parser or inspect "
                    "the input document."
                ),
            )
            return

        numbers: List[int] = []
        claim_ids: Set[str] = set()

        for index, claim in enumerate(
            claim_items
        ):

            path = f"claims[{index}]"

            number = _get(
                claim,
                "claim_number",
                "number",
                "claim_no",
            )

            if number is None:
                self.error(
                    CATEGORY_CLAIMS,
                    "CLAIM-MISSING-NUMBER",
                    "Claim has no claim number.",
                    path=path,
                    remediation=(
                        "Assign the parsed claim number."
                    ),
                )
            else:

                try:
                    number_int = int(number)
                    numbers.append(
                        number_int
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    self.error(
                        CATEGORY_CLAIMS,
                        "CLAIM-INVALID-NUMBER",
                        "Claim number is not an integer.",
                        path=f"{path}.claim_number",
                        actual=number,
                    )

            claim_id = _clean(
                _get(
                    claim,
                    "claim_id",
                    "id",
                )
            )

            if claim_id:

                if claim_id in claim_ids:
                    self.error(
                        CATEGORY_CLAIMS,
                        "CLAIM-DUPLICATE-ID",
                        "Duplicate claim_id detected.",
                        path=f"{path}.claim_id",
                        artifact_id=claim_id,
                    )

                claim_ids.add(
                    claim_id
                )

            text = _clean(
                _get(
                    claim,
                    "text",
                    "claim_text",
                    "content",
                )
            )

            if not text:
                self.error(
                    CATEGORY_CLAIMS,
                    "CLAIM-EMPTY-TEXT",
                    "Claim has no text.",
                    path=f"{path}.text",
                    artifact_id=claim_id,
                )

            claim_type = _normalize(
                _get(
                    claim,
                    "claim_type",
                    "type",
                )
            )

            if claim_type and claim_type not in {
                "independent",
                "dependent",
                "unknown",
                "independent claim",
                "dependent claim",
            }:
                self.warning(
                    CATEGORY_CLAIMS,
                    "CLAIM-UNKNOWN-TYPE",
                    "Claim has an unrecognized claim type.",
                    path=f"{path}.claim_type",
                    actual=claim_type,
                )

        duplicates = {
            number
            for number in numbers
            if numbers.count(number) > 1
        }

        for number in sorted(
            duplicates
        ):
            self.error(
                CATEGORY_CLAIMS,
                "CLAIM-DUPLICATE-NUMBER",
                f"Duplicate claim number detected: {number}.",
                path="claims",
                actual=number,
                remediation=(
                    "Check claim parsing and numbering."
                ),
            )

    # ------------------------------------------------------------------
    # Dependency validation
    # ------------------------------------------------------------------

    def validate_dependencies(
        self,
        claims: Any,
    ) -> None:

        self.mark_component(
            "dependencies"
        )

        claim_items = list(
            _iter_dicts(claims)
        )

        claim_numbers: Set[int] = set()

        for claim in claim_items:

            number = _get(
                claim,
                "claim_number",
                "number",
            )

            try:
                claim_numbers.add(
                    int(number)
                )
            except (
                TypeError,
                ValueError,
            ):
                pass

        for index, claim in enumerate(
            claim_items
        ):

            dependencies = _get(
                claim,
                "dependencies",
                "dependent_on",
                "depends_on",
                default=[],
            )

            if isinstance(
                dependencies,
                (int, str),
            ):
                dependencies = [
                    dependencies
                ]

            for dependency in _as_list(
                dependencies
            ):

                try:
                    dep_number = int(
                        dependency
                    )
                except (
                    TypeError,
                    ValueError,
                ):
                    self.warning(
                        CATEGORY_CLAIMS,
                        "DEP-INVALID",
                        "Claim dependency is not numeric.",
                        path=(
                            f"claims[{index}]"
                            ".dependencies"
                        ),
                        actual=dependency,
                    )
                    continue

                if dep_number not in claim_numbers:
                    self.error(
                        CATEGORY_CLAIMS,
                        "DEP-MISSING-CLAIM",
                        (
                            f"Claim depends on missing "
                            f"claim {dep_number}."
                        ),
                        path=(
                            f"claims[{index}]"
                            ".dependencies"
                        ),
                        actual=dep_number,
                        remediation=(
                            "Check dependent-claim parsing."
                        ),
                    )

    # ------------------------------------------------------------------
    # Limitation validation
    # ------------------------------------------------------------------

    def validate_limitations(
        self,
        claims: Any,
    ) -> None:

        self.mark_component(
            CATEGORY_LIMITATIONS
        )

        for claim_index, claim in enumerate(
            _iter_dicts(claims)
        ):

            limitations = _get(
                claim,
                "limitations",
                "claim_limitations",
                default=[],
            )

            if limitations is None:
                self.warning(
                    CATEGORY_LIMITATIONS,
                    "LIMITATIONS-NONE",
                    "Claim has no limitation collection.",
                    path=(
                        f"claims[{claim_index}]"
                        ".limitations"
                    ),
                )
                continue

            limitation_ids: Set[str] = set()

            for limitation_index, limitation in enumerate(
                _iter_dicts(limitations)
            ):

                path = (
                    f"claims[{claim_index}]"
                    f".limitations[{limitation_index}]"
                )

                limitation_id = _clean(
                    _get(
                        limitation,
                        "limitation_id",
                        "id",
                    )
                )

                if not limitation_id:
                    self.warning(
                        CATEGORY_LIMITATIONS,
                        "LIMITATION-MISSING-ID",
                        "Limitation has no limitation_id.",
                        path=path,
                    )
                elif limitation_id in limitation_ids:
                    self.error(
                        CATEGORY_LIMITATIONS,
                        "LIMITATION-DUPLICATE-ID",
                        "Duplicate limitation_id in claim.",
                        path=path,
                        artifact_id=limitation_id,
                    )
                else:
                    limitation_ids.add(
                        limitation_id
                    )

                text = _clean(
                    _get(
                        limitation,
                        "text",
                        "limitation",
                        "content",
                    )
                )

                if not text:
                    self.error(
                        CATEGORY_LIMITATIONS,
                        "LIMITATION-EMPTY",
                        "Limitation has no text.",
                        path=f"{path}.text",
                        artifact_id=limitation_id,
                    )

    # ------------------------------------------------------------------
    # Evidence validation
    # ------------------------------------------------------------------

    def validate_evidence(
        self,
        evidence: Any,
        claims: Any = None,
    ) -> None:

        self.mark_component(
            CATEGORY_EVIDENCE
        )

        evidence_items = list(
            _iter_dicts(evidence)
        )

        if evidence is None:
            return

        evidence_ids: Set[str] = set()

        claim_numbers: Set[int] = set()

        for claim in _iter_dicts(
            claims
        ):

            number = _get(
                claim,
                "claim_number",
                "number",
            )

            try:
                claim_numbers.add(
                    int(number)
                )
            except (
                TypeError,
                ValueError,
            ):
                pass

        for index, item in enumerate(
            evidence_items
        ):

            path = f"evidence[{index}]"

            evidence_id = _clean(
                _get(
                    item,
                    "evidence_id",
                    "id",
                )
            )

            if not evidence_id:
                self.error(
                    CATEGORY_EVIDENCE,
                    "EVIDENCE-MISSING-ID",
                    "Evidence item has no evidence_id.",
                    path=path,
                )
            elif evidence_id in evidence_ids:
                self.error(
                    CATEGORY_EVIDENCE,
                    "EVIDENCE-DUPLICATE-ID",
                    "Duplicate evidence_id detected.",
                    path=path,
                    artifact_id=evidence_id,
                )
            else:
                evidence_ids.add(
                    evidence_id
                )

            text = _clean(
                _get(
                    item,
                    "text",
                    "passage",
                    "content",
                    "snippet",
                )
            )

            if not text:
                self.warning(
                    CATEGORY_EVIDENCE,
                    "EVIDENCE-EMPTY-TEXT",
                    "Evidence item has no text.",
                    path=f"{path}.text",
                    artifact_id=evidence_id,
                )

            url = _clean(
                _get(
                    item,
                    "source_url",
                    "url",
                )
            )

            if not url:
                self.warning(
                    CATEGORY_EVIDENCE,
                    "EVIDENCE-NO-URL",
                    "Evidence has no source URL.",
                    path=f"{path}.source_url",
                    artifact_id=evidence_id,
                )

            claim_number = _get(
                item,
                "claim_number",
            )

            if claim_number is not None:

                try:
                    claim_number = int(
                        claim_number
                    )

                    if (
                        claim_numbers
                        and claim_number
                        not in claim_numbers
                    ):
                        self.warning(
                            CATEGORY_EVIDENCE,
                            "EVIDENCE-CLAIM-REF",
                            (
                                "Evidence references a claim "
                                "number not present in the input."
                            ),
                            path=f"{path}.claim_number",
                            actual=claim_number,
                        )

                except (
                    TypeError,
                    ValueError,
                ):
                    self.warning(
                        CATEGORY_EVIDENCE,
                        "EVIDENCE-INVALID-CLAIM",
                        "Evidence claim_number is not numeric.",
                        path=f"{path}.claim_number",
                    )

            score = _get(
                item,
                "score",
                "relevance_score",
                "retrieval_score",
            )

            if score is not None:

                if not _in_range(
                    _safe_float(score),
                    0.0,
                    1.0,
                ):
                    self.warning(
                        CATEGORY_EVIDENCE,
                        "EVIDENCE-SCORE-RANGE",
                        "Evidence score is outside [0, 1].",
                        path=f"{path}.score",
                        actual=score,
                    )

    # ------------------------------------------------------------------
    # Prior-art validation
    # ------------------------------------------------------------------

    def validate_prior_art(
        self,
        prior_art: Any,
    ) -> None:

        self.mark_component(
            CATEGORY_PRIOR_ART
        )

        documents = list(
            _iter_dicts(prior_art)
        )

        seen: Set[str] = set()

        for index, document in enumerate(
            documents
        ):

            path = f"prior_art[{index}]"

            document_id = _clean(
                _get(
                    document,
                    "document_id",
                    "id",
                )
            )

            publication_number = _clean(
                _get(
                    document,
                    "publication_number",
                    "patent_number",
                )
            )

            key = (
                document_id
                or publication_number
            )

            if not key:
                self.warning(
                    CATEGORY_PRIOR_ART,
                    "PRIOR-ART-MISSING-ID",
                    "Prior-art document has no stable identifier.",
                    path=path,
                )
            elif key in seen:
                self.warning(
                    CATEGORY_PRIOR_ART,
                    "PRIOR-ART-DUPLICATE",
                    "Duplicate prior-art document detected.",
                    path=path,
                    artifact_id=key,
                )
            else:
                seen.add(
                    key
                )

            title = _clean(
                _get(
                    document,
                    "title",
                    "document_title",
                )
            )

            if not title:
                self.warning(
                    CATEGORY_PRIOR_ART,
                    "PRIOR-ART-NO-TITLE",
                    "Prior-art document has no title.",
                    path=f"{path}.title",
                )

            url = _clean(
                _get(
                    document,
                    "url",
                    "source_url",
                )
            )

            if not url:
                self.warning(
                    CATEGORY_PRIOR_ART,
                    "PRIOR-ART-NO-URL",
                    "Prior-art document has no source URL.",
                    path=f"{path}.url",
                )

    # ------------------------------------------------------------------
    # Findings validation
    # ------------------------------------------------------------------

    def validate_findings(
        self,
        findings: Any,
        claims: Any = None,
    ) -> None:

        self.mark_component(
            CATEGORY_FINDINGS
        )

        finding_items = list(
            _iter_dicts(findings)
        )

        claim_numbers: Set[int] = set()

        for claim in _iter_dicts(
            claims
        ):

            number = _get(
                claim,
                "claim_number",
                "number",
            )

            try:
                claim_numbers.add(
                    int(number)
                )
            except (
                TypeError,
                ValueError,
            ):
                pass

        finding_ids: Set[str] = set()

        for index, finding in enumerate(
            finding_items
        ):

            path = f"findings[{index}]"

            finding_id = _clean(
                _get(
                    finding,
                    "finding_id",
                    "id",
                )
            )

            if not finding_id:
                self.warning(
                    CATEGORY_FINDINGS,
                    "FINDING-MISSING-ID",
                    "Finding has no finding_id.",
                    path=path,
                )
            elif finding_id in finding_ids:
                self.error(
                    CATEGORY_FINDINGS,
                    "FINDING-DUPLICATE-ID",
                    "Duplicate finding_id detected.",
                    path=path,
                    artifact_id=finding_id,
                )
            else:
                finding_ids.add(
                    finding_id
                )

            confidence = _get(
                finding,
                "confidence",
            )

            if confidence is not None:

                if not _in_range(
                    _safe_float(
                        confidence
                    ),
                    0.0,
                    1.0,
                ):
                    self.error(
                        CATEGORY_FINDINGS,
                        "FINDING-CONFIDENCE-RANGE",
                        "Finding confidence is outside [0, 1].",
                        path=f"{path}.confidence",
                        actual=confidence,
                    )

            claim_number = _get(
                finding,
                "claim_number",
            )

            if claim_number is not None:

                try:
                    claim_number = int(
                        claim_number
                    )

                    if (
                        claim_numbers
                        and claim_number
                        not in claim_numbers
                    ):
                        self.warning(
                            CATEGORY_FINDINGS,
                            "FINDING-CLAIM-REF",
                            (
                                "Finding references a claim "
                                "not present in the input."
                            ),
                            path=f"{path}.claim_number",
                            actual=claim_number,
                        )

                except (
                    TypeError,
                    ValueError,
                ):
                    self.warning(
                        CATEGORY_FINDINGS,
                        "FINDING-INVALID-CLAIM",
                        "Finding claim_number is not numeric.",
                        path=f"{path}.claim_number",
                    )

    # ------------------------------------------------------------------
    # Score validation
    # ------------------------------------------------------------------

    def validate_scores(
        self,
        scoring: Any,
    ) -> None:

        self.mark_component(
            CATEGORY_SCORES
        )

        if scoring is None:
            return

        if not isinstance(
            scoring,
            Mapping,
        ):
            self.warning(
                CATEGORY_SCORES,
                "SCORE-NOT-MAPPING",
                "Scoring output is not a mapping.",
                path="scoring",
            )
            return

        score_fields = {
            "overall_score",
            "risk_score",
            "confidence",
            "coverage",
            "evidence_coverage",
            "overall_confidence",
            "novelty_score",
            "inventive_step_score",
        }

        for field_name in score_fields:

            if field_name not in scoring:
                continue

            value = scoring[
                field_name
            ]

            if not _is_number(value):
                self.warning(
                    CATEGORY_SCORES,
                    "SCORE-NOT-NUMERIC",
                    (
                        f"Score field '{field_name}' "
                        "is not numeric."
                    ),
                    path=f"scoring.{field_name}",
                    actual=value,
                )
                continue

            if not math.isfinite(
                float(value)
            ):
                self.error(
                    CATEGORY_SCORES,
                    "SCORE-NOT-FINITE",
                    (
                        f"Score field '{field_name}' "
                        "is not finite."
                    ),
                    path=f"scoring.{field_name}",
                    actual=value,
                )
                continue

            if not 0.0 <= float(value) <= 1.0:
                self.warning(
                    CATEGORY_SCORES,
                    "SCORE-OUT-OF-RANGE",
                    (
                        f"Score field '{field_name}' "
                        "is outside [0, 1]."
                    ),
                    path=f"scoring.{field_name}",
                    actual=value,
                )

    # ------------------------------------------------------------------
    # Provenance validation
    # ------------------------------------------------------------------

    def validate_provenance(
        self,
        provenance: Any,
    ) -> None:

        self.mark_component(
            CATEGORY_PROVENANCE
        )

        if provenance is None:
            self.warning(
                CATEGORY_PROVENANCE,
                "PROVENANCE-MISSING",
                "No provenance object was supplied.",
                path="provenance",
            )
            return

        if not isinstance(
            provenance,
            Mapping,
        ):
            self.error(
                CATEGORY_PROVENANCE,
                "PROVENANCE-NOT-MAPPING",
                "Provenance output is not a mapping.",
                path="provenance",
            )
            return

        manifest = _as_mapping(
            provenance.get(
                "manifest"
            )
        )

        if not manifest:
            self.warning(
                CATEGORY_PROVENANCE,
                "PROVENANCE-NO-MANIFEST",
                "Provenance snapshot has no manifest.",
                path="provenance.manifest",
            )

        sources = _as_list(
            provenance.get(
                "sources",
                [],
            )
        )

        artifacts = _as_list(
            provenance.get(
                "artifacts",
                [],
            )
        )

        events = _as_list(
            provenance.get(
                "events",
                [],
            )
        )

        source_ids = {
            _clean(
                _get(
                    source,
                    "source_id",
                    "id",
                )
            )
            for source in _iter_dicts(
                sources
            )
        }

        artifact_ids = {
            _clean(
                _get(
                    artifact,
                    "artifact_id",
                    "id",
                )
            )
            for artifact in _iter_dicts(
                artifacts
            )
        }

        for artifact in _iter_dicts(
            artifacts
        ):

            artifact_id = _clean(
                _get(
                    artifact,
                    "artifact_id",
                    "id",
                )
            )

            for source_id in _as_list(
                _get(
                    artifact,
                    "source_ids",
                    default=[],
                )
            ):

                if (
                    source_id
                    and source_id
                    not in source_ids
                ):
                    self.error(
                        CATEGORY_PROVENANCE,
                        "PROVENANCE-MISSING-SOURCE",
                        (
                            "Artifact references a source "
                            "that does not exist."
                        ),
                        path=(
                            f"artifact[{artifact_id}]"
                            ".source_ids"
                        ),
                        actual=source_id,
                    )

            for parent_id in _as_list(
                _get(
                    artifact,
                    "parent_ids",
                    default=[],
                )
            ):

                if (
                    parent_id
                    and parent_id
                    not in artifact_ids
                ):
                    self.warning(
                        CATEGORY_PROVENANCE,
                        "PROVENANCE-MISSING-PARENT",
                        (
                            "Artifact references a parent "
                            "that does not exist."
                        ),
                        path=(
                            f"artifact[{artifact_id}]"
                            ".parent_ids"
                        ),
                        actual=parent_id,
                    )

        for event in _iter_dicts(
            events
        ):

            event_id = _clean(
                _get(
                    event,
                    "event_id",
                    "id",
                )
            )

            artifact_id = _clean(
                _get(
                    event,
                    "artifact_id"
                )
            )

            if (
                artifact_id
                and artifact_id
                not in artifact_ids
            ):
                self.warning(
                    CATEGORY_PROVENANCE,
                    "PROVENANCE-EVENT-ARTIFACT",
                    (
                        "Provenance event references "
                        "a missing artifact."
                    ),
                    path=f"event[{event_id}].artifact_id",
                    actual=artifact_id,
                )

    # ------------------------------------------------------------------
    # Knowledge graph validation
    # ------------------------------------------------------------------

    def validate_graph(
        self,
        graph: Any,
    ) -> None:

        self.mark_component(
            CATEGORY_GRAPH
        )

        if graph is None:
            return

        if not isinstance(
            graph,
            Mapping,
        ):
            self.warning(
                CATEGORY_GRAPH,
                "GRAPH-NOT-MAPPING",
                "Knowledge graph is not a mapping.",
                path="graph",
            )
            return

        nodes = _as_list(
            graph.get(
                "nodes",
                [],
            )
        )

        edges = _as_list(
            graph.get(
                "edges",
                [],
            )
        )

        node_ids: Set[str] = set()

        for node in _iter_dicts(
            nodes
        ):

            node_id = _clean(
                _get(
                    node,
                    "node_id",
                    "id",
                )
            )

            if not node_id:
                self.error(
                    CATEGORY_GRAPH,
                    "GRAPH-NODE-ID",
                    "Graph node has no node_id.",
                    path="graph.nodes",
                )
                continue

            if node_id in node_ids:
                self.error(
                    CATEGORY_GRAPH,
                    "GRAPH-DUPLICATE-NODE",
                    "Duplicate graph node ID.",
                    artifact_id=node_id,
                    path="graph.nodes",
                )

            node_ids.add(
                node_id
            )

        for edge in _iter_dicts(
            edges
        ):

            source = _clean(
                _get(
                    edge,
                    "source",
                    "source_id",
                )
            )

            target = _clean(
                _get(
                    edge,
                    "target",
                    "target_id",
                )
            )

            if source and source not in node_ids:
                self.error(
                    CATEGORY_GRAPH,
                    "GRAPH-MISSING-SOURCE",
                    "Graph edge references missing source node.",
                    path="graph.edges",
                    actual=source,
                )

            if target and target not in node_ids:
                self.error(
                    CATEGORY_GRAPH,
                    "GRAPH-MISSING-TARGET",
                    "Graph edge references missing target node.",
                    path="graph.edges",
                    actual=target,
                )

    # ------------------------------------------------------------------
    # Pipeline validation
    # ------------------------------------------------------------------

    def validate_pipeline(
        self,
        pipeline: Any,
    ) -> None:

        self.mark_component(
            CATEGORY_PIPELINE
        )

        if pipeline is None:
            return

        if not isinstance(
            pipeline,
            Mapping,
        ):
            self.error(
                CATEGORY_PIPELINE,
                "PIPELINE-NOT-MAPPING",
                "Pipeline output is not a mapping.",
                path="pipeline",
            )
            return

        stages = _as_list(
            pipeline.get(
                "stages",
                [],
            )
        )

        stage_names: List[str] = []

        for index, stage in enumerate(
            _iter_dicts(stages)
        ):

            name = _clean(
                _get(
                    stage,
                    "name",
                    "stage",
                    "stage_name",
                )
            )

            if not name:
                self.warning(
                    CATEGORY_PIPELINE,
                    "PIPELINE-STAGE-NAME",
                    "Pipeline stage has no name.",
                    path=f"pipeline.stages[{index}]",
                )
            else:
                stage_names.append(
                    name
                )

            status = _normalize(
                _get(
                    stage,
                    "status",
                )
            )

            if status and status not in {
                "pending",
                "running",
                "completed",
                "failed",
                "skipped",
                "success",
                "warning",
            }:
                self.warning(
                    CATEGORY_PIPELINE,
                    "PIPELINE-STATUS",
                    "Unknown pipeline stage status.",
                    path=f"pipeline.stages[{index}].status",
                    actual=status,
                )

        if len(stage_names) != len(
            set(
                stage_names
            )
        ):
            self.warning(
                CATEGORY_PIPELINE,
                "PIPELINE-DUPLICATE-STAGE",
                "Duplicate pipeline stage names detected.",
                path="pipeline.stages",
            )

    # ------------------------------------------------------------------
    # AI validation
    # ------------------------------------------------------------------

    def validate_ai(
        self,
        ai_output: Any,
    ) -> None:

        self.mark_component(
            CATEGORY_AI
        )

        if ai_output is None:
            return

        for index, item in enumerate(
            _iter_dicts(ai_output)
        ):

            model = _clean(
                _get(
                    item,
                    "model",
                    "model_name",
                )
            )

            if not model:
                self.warning(
                    CATEGORY_AI,
                    "AI-MISSING-MODEL",
                    "AI output has no model identifier.",
                    path=f"ai[{index}].model",
                )

            prompt_hash = _clean(
                _get(
                    item,
                    "prompt_hash",
                )
            )

            if not prompt_hash:
                self.warning(
                    CATEGORY_AI,
                    "AI-NO-PROMPT-HASH",
                    (
                        "AI output has no prompt hash; "
                        "reproducibility is reduced."
                    ),
                    path=f"ai[{index}].prompt_hash",
                )

            generated = _get(
                item,
                "ai_generated",
            )

            if generated is False:
                self.warning(
                    CATEGORY_AI,
                    "AI-FLAG-FALSE",
                    (
                        "Object appears in the AI output collection "
                        "but ai_generated is false."
                    ),
                    path=f"ai[{index}].ai_generated",
                )

    # ------------------------------------------------------------------
    # Complete analysis validation
    # ------------------------------------------------------------------

    def validate_analysis(
        self,
        analysis: Mapping[str, Any],
    ) -> ValidationResult:

        self.issues = []
        self.checked_components = []

        if not isinstance(
            analysis,
            Mapping,
        ):
            self.error(
                CATEGORY_SCHEMA,
                "ANALYSIS-NOT-MAPPING",
                "Analysis result must be a mapping.",
                path="analysis",
            )

            return self.result()

        document = analysis.get(
            "document"
        )

        claims = analysis.get(
            "claims"
        )

        if claims is None and isinstance(
            document,
            Mapping,
        ):
            claims = document.get(
                "claims"
            )

        self.validate_document(
            document
        )

        self.validate_claims(
            claims
        )

        self.validate_dependencies(
            claims
        )

        self.validate_limitations(
            claims
        )

        self.validate_evidence(
            analysis.get(
                "evidence"
            ),
            claims=claims,
        )

        self.validate_prior_art(
            analysis.get(
                "prior_art"
            )
        )

        findings = self._collect_findings(
            analysis
        )

        self.validate_findings(
            findings,
            claims=claims,
        )

        self.validate_scores(
            analysis.get(
                "scoring"
            )
            or analysis.get(
                "score"
            )
        )

        self.validate_provenance(
            analysis.get(
                "provenance"
            )
        )

        self.validate_graph(
            analysis.get(
                "knowledge_graph"
            )
            or analysis.get(
                "graph"
            )
        )

        self.validate_pipeline(
            analysis.get(
                "pipeline"
            )
        )

        self.validate_ai(
            analysis.get(
                "ai"
            )
        )

        return self.result()

    # ------------------------------------------------------------------
    # Finding collector
    # ------------------------------------------------------------------

    def _collect_findings(
        self,
        analysis: Mapping[str, Any],
    ) -> List[Mapping[str, Any]]:

        findings: List[
            Mapping[str, Any]
        ] = []

        for key in (
            "findings",
            "rule_findings",
            "section3_findings",
            "novelty_findings",
            "inventive_step_findings",
            "amendment_findings",
            "prosecution_issues",
            "issues",
        ):

            value = analysis.get(
                key
            )

            if isinstance(
                value,
                Mapping,
            ):

                for nested_key in (
                    "findings",
                    "issues",
                    "results",
                    "items",
                ):

                    nested = value.get(
                        nested_key
                    )

                    if isinstance(
                        nested,
                        list,
                    ):
                        findings.extend(
                            item
                            for item in nested
                            if isinstance(
                                item,
                                Mapping,
                            )
                        )

            elif isinstance(
                value,
                list,
            ):

                findings.extend(
                    item
                    for item in value
                    if isinstance(
                        item,
                        Mapping,
                    )
                )

        return findings

    # ------------------------------------------------------------------
    # Result
    # ------------------------------------------------------------------

    def result(self) -> ValidationResult:

        errors = [
            issue
            for issue in self.issues
            if issue.severity
            == SEVERITY_ERROR
        ]

        warnings = [
            issue
            for issue in self.issues
            if issue.severity
            == SEVERITY_WARNING
        ]

        info = [
            issue
            for issue in self.issues
            if issue.severity
            == SEVERITY_INFO
        ]

        valid = len(errors) == 0

        if self.strict and warnings:
            valid = False

        validation_id = _stable_id(
            "VALIDATION",
            _utc_now(),
            len(
                self.issues
            ),
        )

        return ValidationResult(
            validation_id=validation_id,
            valid=valid,
            errors=errors,
            warnings=warnings,
            info=info,
            checked_components=list(
                self.checked_components
            ),
            statistics={
                "total_issues": len(
                    self.issues
                ),
                "error_count": len(
                    errors
                ),
                "warning_count": len(
                    warnings
                ),
                "info_count": len(
                    info
                ),
                "component_count": len(
                    self.checked_components
                ),
            },
            created_at=_utc_now(),
        )


# ---------------------------------------------------------------------------
# Standalone validators
# ---------------------------------------------------------------------------


def validate_analysis(
    analysis: Mapping[str, Any],
    strict: bool = False,
) -> ValidationResult:

    validator = PatentAnalysisValidator(
        strict=strict
    )

    return validator.validate_analysis(
        analysis
    )


def validate_document(
    document: Any,
) -> ValidationResult:

    validator = PatentAnalysisValidator()

    validator.validate_document(
        document
    )

    return validator.result()


def validate_claims(
    claims: Any,
) -> ValidationResult:

    validator = PatentAnalysisValidator()

    validator.validate_claims(
        claims
    )

    validator.validate_dependencies(
        claims
    )

    validator.validate_limitations(
        claims
    )

    return validator.result()


def validate_evidence(
    evidence: Any,
    claims: Any = None,
) -> ValidationResult:

    validator = PatentAnalysisValidator()

    validator.validate_evidence(
        evidence,
        claims=claims,
    )

    return validator.result()


def validate_provenance(
    provenance: Any,
) -> ValidationResult:

    validator = PatentAnalysisValidator()

    validator.validate_provenance(
        provenance
    )

    return validator.result()


def validate_knowledge_graph(
    graph: Any,
) -> ValidationResult:

    validator = PatentAnalysisValidator()

    validator.validate_graph(
        graph
    )

    return validator.result()


# ---------------------------------------------------------------------------
# Validation summaries
# ---------------------------------------------------------------------------


def validation_statistics(
    result: ValidationResult,
) -> Dict[str, Any]:

    return {
        "version": VALIDATION_VERSION,
        "validation_id": result.validation_id,
        "valid": result.valid,
        "errors": len(
            result.errors
        ),
        "warnings": len(
            result.warnings
        ),
        "info": len(
            result.info
        ),
        "components_checked": len(
            result.checked_components
        ),
        "component_names": list(
            result.checked_components
        ),
    }


def get_validation_errors(
    result: ValidationResult,
) -> List[ValidationIssue]:

    return list(
        result.errors
    )


def get_validation_warnings(
    result: ValidationResult,
) -> List[ValidationIssue]:

    return list(
        result.warnings
    )


def has_validation_errors(
    result: ValidationResult,
) -> bool:

    return bool(
        result.errors
    )


def requires_manual_review(
    result: ValidationResult,
) -> bool:

    if result.errors:
        return True

    for issue in result.warnings:

        if issue.category in {
            CATEGORY_EVIDENCE,
            CATEGORY_PROVENANCE,
            CATEGORY_FINDINGS,
            CATEGORY_GRAPH,
        }:
            return True

    return False


def validation_to_dict(
    result: ValidationResult,
) -> Dict[str, Any]:

    return result.to_dict()


# ---------------------------------------------------------------------------
# Pipeline gate
# ---------------------------------------------------------------------------


class ValidationGate:
    """
    Gate used before report generation.

    The gate does not decide whether a patent is patentable.

    It only decides whether the computational result is internally
    consistent enough to continue.
    """

    def __init__(
        self,
        strict: bool = False,
    ) -> None:

        self.strict = strict

    def check(
        self,
        analysis: Mapping[str, Any],
    ) -> ValidationResult:

        return validate_analysis(
            analysis,
            strict=self.strict,
        )

    def allow_report_generation(
        self,
        result: ValidationResult,
    ) -> bool:

        if result.errors:
            return False

        if self.strict and result.warnings:
            return False

        return True

    def get_blocking_issues(
        self,
        result: ValidationResult,
    ) -> List[ValidationIssue]:

        if self.strict:
            return [
                *result.errors,
                *result.warnings,
            ]

        return list(
            result.errors
        )


# ---------------------------------------------------------------------------
# Quick consistency checks
# ---------------------------------------------------------------------------


def check_claim_numbers(
    claims: Any,
) -> Dict[str, Any]:

    numbers: List[int] = []

    for claim in _iter_dicts(
        claims
    ):

        value = _get(
            claim,
            "claim_number",
            "number",
        )

        try:
            numbers.append(
                int(value)
            )
        except (
            TypeError,
            ValueError,
        ):
            continue

    duplicates = sorted(
        {
            number
            for number in numbers
            if numbers.count(
                number
            ) > 1
        }
    )

    return {
        "valid": not duplicates,
        "claim_count": len(
            numbers
        ),
        "claim_numbers": sorted(
            numbers
        ),
        "duplicates": duplicates,
    }


def check_score_fields(
    scoring: Any,
) -> Dict[str, Any]:

    invalid: Dict[
        str,
        Any,
    ] = {}

    if not isinstance(
        scoring,
        Mapping,
    ):
        return {
            "valid": False,
            "invalid": {
                "scoring": (
                    "not a mapping"
                )
            },
        }

    for key, value in scoring.items():

        if not isinstance(
            key,
            str,
        ):
            continue

        if (
            "score" not in key.lower()
            and "confidence" not in key.lower()
            and "coverage" not in key.lower()
        ):
            continue

        if _is_number(value):

            if not (
                math.isfinite(
                    float(value)
                )
                and 0.0
                <= float(value)
                <= 1.0
            ):
                invalid[
                    key
                ] = value

    return {
        "valid": not invalid,
        "invalid": invalid,
    }


# ---------------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------------


Validator = PatentAnalysisValidator
AnalysisValidator = PatentAnalysisValidator
ValidationReport = ValidationResult


def run_validation(
    analysis: Mapping[str, Any],
    strict: bool = False,
) -> ValidationResult:

    return validate_analysis(
        analysis,
        strict=strict,
    )


def validate_pipeline_output(
    analysis: Mapping[str, Any],
    strict: bool = False,
) -> ValidationResult:

    return validate_analysis(
        analysis,
        strict=strict,
    )


def check_analysis_integrity(
    analysis: Mapping[str, Any],
) -> ValidationResult:

    return validate_analysis(
        analysis
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


__all__ = [
    "VALIDATION_VERSION",

    "SEVERITY_ERROR",
    "SEVERITY_WARNING",
    "SEVERITY_INFO",

    "CATEGORY_DOCUMENT",
    "CATEGORY_CLAIMS",
    "CATEGORY_LIMITATIONS",
    "CATEGORY_EVIDENCE",
    "CATEGORY_PRIOR_ART",
    "CATEGORY_FINDINGS",
    "CATEGORY_SCORES",
    "CATEGORY_PROVENANCE",
    "CATEGORY_GRAPH",
    "CATEGORY_PIPELINE",
    "CATEGORY_AI",
    "CATEGORY_SCHEMA",

    "ValidationIssue",
    "ValidationResult",

    "PatentAnalysisValidator",
    "ValidationGate",

    "validate_analysis",
    "validate_document",
    "validate_claims",
    "validate_evidence",
    "validate_provenance",
    "validate_knowledge_graph",

    "validation_statistics",
    "get_validation_errors",
    "get_validation_warnings",
    "has_validation_errors",
    "requires_manual_review",
    "validation_to_dict",

    "check_claim_numbers",
    "check_score_fields",

    "Validator",
    "AnalysisValidator",
    "ValidationReport",
    "run_validation",
    "validate_pipeline_output",
    "check_analysis_integrity",
]
