"""
Prosecution Analyzer V3
=======================

Purpose
-------
Unify patent prosecution analysis across:

    FER
    ↓
    Objections
    ↓
    Claims
    ↓
    Section 3 screening
    ↓
    Novelty screening
    ↓
    Inventive-step screening
    ↓
    Amendments
    ↓
    Evidence
    ↓
    Reviewer action map

This module is an orchestration layer.

It does NOT independently determine:
    - legal validity
    - patentability
    - allowance
    - grant probability
    - whether an objection is legally correct

It organizes existing deterministic findings into a
prosecution-review dashboard.

Version
-------
3.0.0
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


PROSECUTION_ANALYZER_VERSION = "3.0.0"


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


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:

    try:
        return int(value)
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
class ProsecutionIssue:

    issue_id: str
    issue_type: str
    source: str

    claim_numbers: List[int]

    title: str
    description: str

    severity: str
    confidence: float

    evidence: List[Dict[str, Any]]

    suggested_review_action: str

    status: str = "OPEN"

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(
            self
        )


@dataclass
class ProsecutionClaimStatus:

    claim_number: int

    claim_text: str

    fer_objections: int
    section3_findings: int
    novelty_signals: int
    inventive_step_signals: int
    amendment_changes: int

    open_issue_count: int

    status: str

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(
            self
        )


@dataclass
class ProsecutionDashboard:

    application_status: str

    issue_count: int
    open_issue_count: int

    affected_claim_count: int

    high_priority_issue_count: int

    claims: List[
        ProsecutionClaimStatus
    ]

    issues: List[
        ProsecutionIssue
    ]

    action_items: List[
        Dict[str, Any]
    ]

    timeline: List[
        Dict[str, Any]
    ]

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        data = asdict(
            self
        )

        data["claims"] = [
            item.to_dict()
            if isinstance(
                item,
                ProsecutionClaimStatus,
            )
            else item
            for item
            in self.claims
        ]

        data["issues"] = [
            item.to_dict()
            if isinstance(
                item,
                ProsecutionIssue,
            )
            else item
            for item
            in self.issues
        ]

        return data


# ---------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------

def _iter_dicts(
    value: Any,
) -> List[Dict[str, Any]]:

    if value is None:
        return []

    if isinstance(
        value,
        dict,
    ):
        return [
            value
        ]

    if not isinstance(
        value,
        list,
    ):
        return []

    return [
        item
        for item
        in value
        if isinstance(
            item,
            dict,
        )
    ]


def _claim_numbers_from_item(
    item: Dict[str, Any],
) -> List[int]:

    values = []

    direct = item.get(
        "claim_numbers"
    )

    if direct is not None:

        if not isinstance(
            direct,
            list,
        ):
            direct = [
                direct
            ]

        for value in direct:

            try:
                values.append(
                    int(value)
                )
            except Exception:
                pass

    for key in (
        "claim_number",
        "claim",
        "number",
    ):

        if key not in item:
            continue

        value = item.get(
            key
        )

        if isinstance(
            value,
            list,
        ):

            for element in value:

                try:
                    values.append(
                        int(element)
                    )
                except Exception:
                    pass

        else:

            try:
                values.append(
                    int(value)
                )
            except Exception:
                pass

    return sorted(
        set(values)
    )


# ---------------------------------------------------------------------
# FER integration
# ---------------------------------------------------------------------

def extract_fer_issues(
    fer_analysis: Optional[
        Dict[str, Any]
    ],
) -> List[ProsecutionIssue]:

    if not fer_analysis:
        return []

    objections = (
        fer_analysis.get(
            "objections",
            fer_analysis.get(
                "findings",
                [],
            ),
        )
    )

    issues = []

    for index, objection in enumerate(
        _iter_dicts(
            objections
        ),
        start=1,
    ):

        claim_numbers = (
            _claim_numbers_from_item(
                objection
            )
        )

        category = _clean(
            objection.get(
                "category",
                objection.get(
                    "type",
                    "formal",
                ),
            )
        )

        title = _clean(
            objection.get(
                "title",
                objection.get(
                    "heading",
                    category,
                ),
            )
        )

        description = _clean(
            objection.get(
                "description",
                objection.get(
                    "text",
                    objection.get(
                        "objection",
                        "",
                    ),
                ),
            )
        )

        severity = _clean(
            objection.get(
                "severity",
                "MEDIUM",
            )
        ).upper()

        confidence = _safe_float(
            objection.get(
                "confidence",
                0.70,
            ),
            0.70,
        )

        evidence = objection.get(
            "evidence",
            [],
        )

        if not isinstance(
            evidence,
            list,
        ):
            evidence = []

        issue_id = _clean(
            objection.get(
                "objection_id",
                objection.get(
                    "finding_id",
                    "",
                ),
            )
        )

        if not issue_id:

            issue_id = _stable_id(
                "FER",
                f"{index}|{category}|{description}",
            )

        issues.append(
            ProsecutionIssue(
                issue_id=issue_id,
                issue_type="FER_OBJECTION",
                source="FER",
                claim_numbers=claim_numbers,
                title=title,
                description=description,
                severity=severity,
                confidence=_clamp(
                    confidence
                ),
                evidence=evidence,
                suggested_review_action=(
                    "Review the FER objection against "
                    "the cited claim/specification passages "
                    "and prepare an evidence-supported response."
                ),
            )
        )

    return issues


# ---------------------------------------------------------------------
# Section 3 integration
# ---------------------------------------------------------------------

def extract_section3_issues(
    section3_analysis: Optional[
        Dict[str, Any]
    ],
) -> List[ProsecutionIssue]:

    if not section3_analysis:
        return []

    findings = section3_analysis.get(
        "findings",
        [],
    )

    issues = []

    for finding in _iter_dicts(
        findings
    ):

        section = _clean(
            finding.get(
                "section",
                "",
            )
        )

        if not section:
            continue

        claims = _claim_numbers_from_item(
            finding
        )

        title = _clean(
            finding.get(
                "title",
                f"Section {section}",
            )
        )

        explanation = _clean(
            finding.get(
                "explanation",
                "",
            )
        )

        status = _clean(
            finding.get(
                "status",
                "REVIEW_SIGNAL",
            )
        )

        confidence = _safe_float(
            finding.get(
                "confidence",
                0.50,
            ),
            0.50,
        )

        evidence = finding.get(
            "evidence",
            [],
        )

        if not isinstance(
            evidence,
            list,
        ):
            evidence = []

        issue_id = _clean(
            finding.get(
                "finding_id",
                "",
            )
        )

        if not issue_id:

            issue_id = _stable_id(
                "S3",
                f"{section}|{claims}|{explanation}",
            )

        if status == "STRONG_REVIEW_SIGNAL":

            severity = "HIGH"

        elif status == "REVIEW_SIGNAL":

            severity = "MEDIUM"

        else:

            severity = "LOW"

        issues.append(
            ProsecutionIssue(
                issue_id=issue_id,
                issue_type="SECTION_3",
                source="SECTION_3_ANALYZER",
                claim_numbers=claims,
                title=(
                    f"{section}: {title}"
                ),
                description=explanation,
                severity=severity,
                confidence=_clamp(
                    confidence
                ),
                evidence=[
                    {
                        "text":
                            item
                    }
                    if isinstance(
                        item,
                        str,
                    )
                    else item
                    for item
                    in evidence
                ],
                suggested_review_action=(
                    f"Review the claim against the "
                    f"requirements associated with Section "
                    f"{section}; verify the complete statutory "
                    f"context before relying on this signal."
                ),
            )
        )

    return issues


# ---------------------------------------------------------------------
# Novelty integration
# ---------------------------------------------------------------------

def extract_novelty_issues(
    novelty_analysis: Optional[
        Dict[str, Any]
    ],
) -> List[ProsecutionIssue]:

    if not novelty_analysis:
        return []

    issues = []

    for claim in _iter_dicts(
        novelty_analysis.get(
            "claims",
            [],
        )
    ):

        claim_number = _safe_int(
            claim.get(
                "claim_number",
                0,
            )
        )

        status = _clean(
            claim.get(
                "status",
                "",
            )
        )

        if status not in {
            "POTENTIAL_ANTICIPATION_REFERENCE",
            "STRONG_SAME_DOCUMENT_SIGNAL",
            "PARTIAL_NOVELTY_SIGNAL",
        }:
            continue

        coverage = _safe_float(
            claim.get(
                "coverage",
                0.0,
            )
        )

        document_id = _clean(
            claim.get(
                "best_document_id",
                "",
            )
        )

        title = _clean(
            claim.get(
                "best_document_title",
                "",
            )
        )

        if status == (
            "POTENTIAL_ANTICIPATION_REFERENCE"
        ):

            severity = "HIGH"

        elif status == (
            "STRONG_SAME_DOCUMENT_SIGNAL"
        ):

            severity = "MEDIUM"

        else:

            severity = "LOW"

        issues.append(
            ProsecutionIssue(
                issue_id=_stable_id(
                    "NOV",
                    f"{claim_number}|{document_id}|{status}",
                ),
                issue_type="NOVELTY",
                source="NOVELTY_ANALYZER",
                claim_numbers=[
                    claim_number
                ]
                if claim_number
                else [],
                title=(
                    f"Novelty review signal "
                    f"for Claim {claim_number}"
                ),
                description=(
                    f"The screening engine identified "
                    f"same-document evidence coverage of "
                    f"{coverage:.1%}."
                ),
                severity=severity,
                confidence=_clamp(
                    coverage
                ),
                evidence=[
                    {
                        "document_id":
                            document_id,

                        "title":
                            title,

                        "coverage":
                            coverage,
                    }
                ],
                suggested_review_action=(
                    "Review the cited reference limitation-by-"
                    "limitation and verify publication/priority "
                    "dates and legally relevant disclosure."
                ),
            )
        )

    return issues


# ---------------------------------------------------------------------
# Inventive-step integration
# ---------------------------------------------------------------------

def extract_inventive_step_issues(
    inventive_step_analysis: Optional[
        Dict[str, Any]
    ],
) -> List[ProsecutionIssue]:

    if not inventive_step_analysis:
        return []

    issues = []

    for claim in _iter_dicts(
        inventive_step_analysis.get(
            "claims",
            [],
        )
    ):

        claim_number = _safe_int(
            claim.get(
                "claim_number",
                0,
            )
        )

        status = _clean(
            claim.get(
                "status",
                "",
            )
        )

        if status not in {
            "COMBINATION_REVIEW_SIGNAL",
            "DISTINGUISHING_FEATURE_SIGNAL",
            "LOW_DIFFERENCE_SIGNAL",
        }:
            continue

        evidence_strength = _safe_float(
            claim.get(
                "evidence_strength",
                0.0,
            )
        )

        starting_reference = _clean(
            claim.get(
                "starting_reference_id",
                "",
            )
        )

        starting_title = _clean(
            claim.get(
                "starting_reference_title",
                "",
            )
        )

        if status == (
            "COMBINATION_REVIEW_SIGNAL"
        ):

            severity = "HIGH"

        elif status == (
            "DISTINGUISHING_FEATURE_SIGNAL"
        ):

            severity = "MEDIUM"

        else:

            severity = "LOW"

        issues.append(
            ProsecutionIssue(
                issue_id=_stable_id(
                    "IS",
                    f"{claim_number}|{starting_reference}|{status}",
                ),
                issue_type="INVENTIVE_STEP",
                source="INVENTIVE_STEP_ANALYZER",
                claim_numbers=[
                    claim_number
                ]
                if claim_number
                else [],
                title=(
                    f"Inventive-step review signal "
                    f"for Claim {claim_number}"
                ),
                description=_clean(
                    claim.get(
                        "reasoning",
                        "",
                    )
                ),
                severity=severity,
                confidence=_clamp(
                    evidence_strength
                ),
                evidence=[
                    {
                        "starting_reference":
                            starting_reference,

                        "title":
                            starting_title,

                        "evidence_strength":
                            evidence_strength,

                        "differences":
                            claim.get(
                                "differences",
                                [],
                            ),

                        "combinations":
                            claim.get(
                                "combinations",
                                [],
                            ),
                    }
                ],
                suggested_review_action=(
                    "Review the closest technical reference, "
                    "claim differences, technical problem/effect, "
                    "and any alleged motivation to combine without "
                    "relying on hindsight."
                ),
            )
        )

    return issues


# ---------------------------------------------------------------------
# Amendment integration
# ---------------------------------------------------------------------

def extract_amendment_issues(
    amendment_analysis: Optional[
        Dict[str, Any]
    ],
) -> List[ProsecutionIssue]:

    if not amendment_analysis:
        return []

    issues = []

    comparisons = amendment_analysis.get(
        "comparisons",
        amendment_analysis.get(
            "claims",
            [],
        ),
    )

    for comparison in _iter_dicts(
        comparisons
    ):

        claim_number = _safe_int(
            comparison.get(
                "claim_number",
                comparison.get(
                    "new_claim_number",
                    0,
                ),
            )
        )

        added = comparison.get(
            "added_limitations",
            comparison.get(
                "added",
                [],
            ),
        )

        modified = comparison.get(
            "modified_limitations",
            comparison.get(
                "modified",
                [],
            ),
        )

        deleted = comparison.get(
            "deleted_limitations",
            comparison.get(
                "deleted",
                [],
            ),
        )

        changed_count = (
            len(
                added
            )
            + len(
                modified
            )
            + len(
                deleted
            )
        )

        if changed_count == 0:
            continue

        status = _clean(
            comparison.get(
                "status",
                "AMENDED",
            )
        )

        issues.append(
            ProsecutionIssue(
                issue_id=_stable_id(
                    "AMD",
                    f"{claim_number}|{changed_count}|{status}",
                ),
                issue_type="AMENDMENT",
                source="AMENDMENT_ANALYZER",
                claim_numbers=[
                    claim_number
                ]
                if claim_number
                else [],
                title=(
                    f"Claim {claim_number} amendment"
                ),
                description=(
                    f"The amendment analysis identified "
                    f"{changed_count} limitation-level change(s)."
                ),
                severity="MEDIUM",
                confidence=0.90,
                evidence=[
                    {
                        "added":
                            added,

                        "modified":
                            modified,

                        "deleted":
                            deleted,
                    }
                ],
                suggested_review_action=(
                    "Trace each added or modified limitation "
                    "to the original disclosure and prosecution "
                    "record. Do not infer statutory amendment "
                    "compliance from the textual difference alone."
                ),
            )
        )

    return issues


# ---------------------------------------------------------------------
# Issue consolidation
# ---------------------------------------------------------------------

def collect_prosecution_issues(
    *,
    fer_analysis: Optional[
        Dict[str, Any]
    ] = None,
    section3_analysis: Optional[
        Dict[str, Any]
    ] = None,
    novelty_analysis: Optional[
        Dict[str, Any]
    ] = None,
    inventive_step_analysis: Optional[
        Dict[str, Any]
    ] = None,
    amendment_analysis: Optional[
        Dict[str, Any]
    ] = None,
) -> List[ProsecutionIssue]:

    issues = []

    issues.extend(
        extract_fer_issues(
            fer_analysis
        )
    )

    issues.extend(
        extract_section3_issues(
            section3_analysis
        )
    )

    issues.extend(
        extract_novelty_issues(
            novelty_analysis
        )
    )

    issues.extend(
        extract_inventive_step_issues(
            inventive_step_analysis
        )
    )

    issues.extend(
        extract_amendment_issues(
            amendment_analysis
        )
    )

    # Deduplicate.
    unique = {}

    for issue in issues:

        unique[
            issue.issue_id
        ] = issue

    return list(
        unique.values()
    )


# ---------------------------------------------------------------------
# Claim status
# ---------------------------------------------------------------------

def build_claim_statuses(
    claims: Iterable[Any],
    issues: Iterable[
        ProsecutionIssue
    ],
) -> List[ProsecutionClaimStatus]:

    normalized_claims = []

    for index, claim in enumerate(
        claims,
        start=1,
    ):

        if isinstance(
            claim,
            dict,
        ):

            number = _safe_int(
                claim.get(
                    "claim_number",
                    claim.get(
                        "number",
                        index,
                    ),
                ),
                index,
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

        else:

            number = index
            text = _clean(
                claim
            )

        normalized_claims.append(
            (
                number,
                text,
            )
        )

    issue_list = list(
        issues
    )

    statuses = []

    for number, text in normalized_claims:

        claim_issues = [
            issue
            for issue
            in issue_list
            if number
            in issue.claim_numbers
        ]

        fer_count = sum(
            1
            for issue
            in claim_issues
            if issue.issue_type
            == "FER_OBJECTION"
        )

        section3_count = sum(
            1
            for issue
            in claim_issues
            if issue.issue_type
            == "SECTION_3"
        )

        novelty_count = sum(
            1
            for issue
            in claim_issues
            if issue.issue_type
            == "NOVELTY"
        )

        inventive_count = sum(
            1
            for issue
            in claim_issues
            if issue.issue_type
            == "INVENTIVE_STEP"
        )

        amendment_count = sum(
            1
            for issue
            in claim_issues
            if issue.issue_type
            == "AMENDMENT"
        )

        open_count = sum(
            1
            for issue
            in claim_issues
            if issue.status
            == "OPEN"
        )

        high_count = sum(
            1
            for issue
            in claim_issues
            if issue.severity
            == "HIGH"
        )

        if high_count:

            status = (
                "HIGH_PRIORITY_REVIEW"
            )

        elif open_count:

            status = (
                "REVIEW_REQUIRED"
            )

        else:

            status = (
                "NO_OPEN_SIGNAL"
            )

        statuses.append(
            ProsecutionClaimStatus(
                claim_number=number,
                claim_text=text,
                fer_objections=fer_count,
                section3_findings=section3_count,
                novelty_signals=novelty_count,
                inventive_step_signals=inventive_count,
                amendment_changes=amendment_count,
                open_issue_count=open_count,
                status=status,
            )
        )

    return statuses


# ---------------------------------------------------------------------
# Action items
# ---------------------------------------------------------------------

def build_action_items(
    issues: Iterable[
        ProsecutionIssue
    ],
) -> List[Dict[str, Any]]:

    actions = []

    for issue in issues:

        if issue.severity == "HIGH":

            priority = "P1"

        elif issue.severity == "MEDIUM":

            priority = "P2"

        else:

            priority = "P3"

        action = {
            "action_id":
                _stable_id(
                    "ACT",
                    issue.issue_id,
                ),

            "priority":
                priority,

            "issue_id":
                issue.issue_id,

            "issue_type":
                issue.issue_type,

            "title":
                issue.title,

            "claim_numbers":
                issue.claim_numbers,

            "action":
                issue.suggested_review_action,

            "status":
                "OPEN",
        }

        actions.append(
            action
        )

    priority_order = {
        "P1": 1,
        "P2": 2,
        "P3": 3,
    }

    actions.sort(
        key=lambda item: (
            priority_order.get(
                item["priority"],
                9,
            ),
            item["issue_type"],
            item["title"],
        )
    )

    return actions


# ---------------------------------------------------------------------
# Timeline
# ---------------------------------------------------------------------

def build_prosecution_timeline(
    fer_analysis: Optional[
        Dict[str, Any]
    ] = None,
    amendment_analysis: Optional[
        Dict[str, Any]
    ] = None,
) -> List[Dict[str, Any]]:

    timeline = []

    if fer_analysis:

        deadlines = fer_analysis.get(
            "deadlines",
            [],
        )

        for deadline in _iter_dicts(
            deadlines
        ):

            timeline.append(
                {
                    "event_type":
                        "FER_DEADLINE",

                    "date":
                        _clean(
                            deadline.get(
                                "date",
                                deadline.get(
                                    "deadline",
                                    "",
                                ),
                            )
                        ),

                    "title":
                        _clean(
                            deadline.get(
                                "title",
                                "FER Deadline",
                            )
                        ),

                    "status":
                        _clean(
                            deadline.get(
                                "status",
                                "",
                            )
                        ),
                }
            )

        dates = fer_analysis.get(
            "dates",
            [],
        )

        for date_item in _iter_dicts(
            dates
        ):

            timeline.append(
                {
                    "event_type":
                        "FER_DATE",

                    "date":
                        _clean(
                            date_item.get(
                                "date",
                                "",
                            )
                        ),

                    "title":
                        _clean(
                            date_item.get(
                                "title",
                                date_item.get(
                                    "type",
                                    "FER Event",
                                ),
                            )
                        ),

                    "status":
                        _clean(
                            date_item.get(
                                "status",
                                "",
                            )
                        ),
                }
            )

    if amendment_analysis:

        amendment_date = _clean(
            amendment_analysis.get(
                "amendment_date",
                "",
            )
        )

        if amendment_date:

            timeline.append(
                {
                    "event_type":
                        "AMENDMENT",

                    "date":
                        amendment_date,

                    "title":
                        "Claim amendment",

                    "status":
                        "RECORDED",
                }
            )

    timeline.sort(
        key=lambda item: item.get(
            "date",
            ""
        )
    )

    return timeline


# ---------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------

def build_prosecution_dashboard(
    *,
    claims: Iterable[Any],
    fer_analysis: Optional[
        Dict[str, Any]
    ] = None,
    section3_analysis: Optional[
        Dict[str, Any]
    ] = None,
    novelty_analysis: Optional[
        Dict[str, Any]
    ] = None,
    inventive_step_analysis: Optional[
        Dict[str, Any]
    ] = None,
    amendment_analysis: Optional[
        Dict[str, Any]
    ] = None,
) -> Dict[str, Any]:

    issues = collect_prosecution_issues(
        fer_analysis=fer_analysis,
        section3_analysis=section3_analysis,
        novelty_analysis=novelty_analysis,
        inventive_step_analysis=(
            inventive_step_analysis
        ),
        amendment_analysis=amendment_analysis,
    )

    claim_statuses = build_claim_statuses(
        claims,
        issues,
    )

    actions = build_action_items(
        issues
    )

    timeline = build_prosecution_timeline(
        fer_analysis,
        amendment_analysis,
    )

    open_issues = [
        issue
        for issue
        in issues
        if issue.status
        == "OPEN"
    ]

    high_priority = [
        issue
        for issue
        in open_issues
        if issue.severity
        == "HIGH"
    ]

    affected_claims = set()

    for issue in issues:

        affected_claims.update(
            issue.claim_numbers
        )

    if high_priority:

        application_status = (
            "HIGH_PRIORITY_REVIEW"
        )

    elif open_issues:

        application_status = (
            "REVIEW_REQUIRED"
        )

    else:

        application_status = (
            "NO_OPEN_SCREENING_SIGNAL"
        )

    dashboard = ProsecutionDashboard(
        application_status=application_status,
        issue_count=len(
            issues
        ),
        open_issue_count=len(
            open_issues
        ),
        affected_claim_count=len(
            affected_claims
        ),
        high_priority_issue_count=len(
            high_priority
        ),
        claims=claim_statuses,
        issues=issues,
        action_items=actions,
        timeline=timeline,
    )

    return {
        "success":
            True,

        "prosecution_analyzer_version":
            PROSECUTION_ANALYZER_VERSION,

        "generated_at":
            _utc_now(),

        "dashboard":
            dashboard.to_dict(),

        "summary":
            {
                "application_status":
                    application_status,

                "issue_count":
                    len(
                        issues
                    ),

                "open_issue_count":
                    len(
                        open_issues
                    ),

                "affected_claim_count":
                    len(
                        affected_claims
                    ),

                "high_priority_issue_count":
                    len(
                        high_priority
                    ),
            },

        "review_notice":
            (
                "The prosecution dashboard consolidates "
                "automated screening signals. It is not a "
                "legal opinion and does not determine the "
                "outcome of prosecution."
            ),
    }


# ---------------------------------------------------------------------
# Response matrix
# ---------------------------------------------------------------------

def build_response_matrix(
    dashboard: Dict[str, Any],
) -> List[Dict[str, Any]]:

    result = []

    dashboard_data = dashboard.get(
        "dashboard",
        dashboard,
    )

    for issue in _iter_dicts(
        dashboard_data.get(
            "issues",
            [],
        )
    ):

        result.append(
            {
                "issue_id":
                    issue.get(
                        "issue_id",
                        "",
                    ),

                "issue_type":
                    issue.get(
                        "issue_type",
                        "",
                    ),

                "claim_numbers":
                    issue.get(
                        "claim_numbers",
                        [],
                    ),

                "objection":
                    issue.get(
                        "title",
                        "",
                    ),

                "evidence":
                    issue.get(
                        "evidence",
                        [],
                    ),

                "suggested_action":
                    issue.get(
                        "suggested_review_action",
                        "",
                    ),

                "response":
                    "",

                "amendment":
                    "",

                "status":
                    issue.get(
                        "status",
                        "OPEN",
                    ),
            }
        )

    return result


# ---------------------------------------------------------------------
# Claim issue map
# ---------------------------------------------------------------------

def build_claim_issue_map(
    dashboard: Dict[str, Any],
) -> Dict[int, List[Dict[str, Any]]]:

    dashboard_data = dashboard.get(
        "dashboard",
        dashboard,
    )

    result: Dict[
        int,
        List[Dict[str, Any]]
    ] = {}

    for issue in _iter_dicts(
        dashboard_data.get(
            "issues",
            [],
        )
    ):

        for claim_number in (
            issue.get(
                "claim_numbers",
                [],
            )
        ):

            try:
                claim_number = int(
                    claim_number
                )
            except Exception:
                continue

            result.setdefault(
                claim_number,
                [],
            ).append(
                issue
            )

    return result


# ---------------------------------------------------------------------
# Issue filtering
# ---------------------------------------------------------------------

def filter_issues(
    dashboard: Dict[str, Any],
    *,
    issue_type: Optional[str] = None,
    severity: Optional[str] = None,
    claim_number: Optional[int] = None,
    status: Optional[str] = None,
) -> List[Dict[str, Any]]:

    dashboard_data = dashboard.get(
        "dashboard",
        dashboard,
    )

    result = []

    for issue in _iter_dicts(
        dashboard_data.get(
            "issues",
            [],
        )
    ):

        if (
            issue_type
            and issue.get(
                "issue_type"
            )
            != issue_type
        ):
            continue

        if (
            severity
            and issue.get(
                "severity"
            )
            != severity
        ):
            continue

        if (
            status
            and issue.get(
                "status"
            )
            != status
        ):
            continue

        if claim_number is not None:

            if (
                claim_number
                not in issue.get(
                    "claim_numbers",
                    [],
                )
            ):
                continue

        result.append(
            issue
        )

    return result


# ---------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------

def summarize_prosecution(
    dashboard: Dict[str, Any],
) -> str:

    summary = dashboard.get(
        "summary",
        {},
    )

    return (
        f"Prosecution screening contains "
        f"{summary.get('issue_count', 0)} issue(s), "
        f"of which {summary.get('open_issue_count', 0)} "
        f"remain open. "
        f"{summary.get('affected_claim_count', 0)} "
        f"claim(s) are associated with at least one "
        f"screening issue."
    )


# ---------------------------------------------------------------------
# Convenience API
# ---------------------------------------------------------------------

def analyze_prosecution(
    *,
    claims: Iterable[Any],
    fer_analysis: Optional[
        Dict[str, Any]
    ] = None,
    section3_analysis: Optional[
        Dict[str, Any]
    ] = None,
    novelty_analysis: Optional[
        Dict[str, Any]
    ] = None,
    inventive_step_analysis: Optional[
        Dict[str, Any]
    ] = None,
    amendment_analysis: Optional[
        Dict[str, Any]
    ] = None,
) -> Dict[str, Any]:

    return build_prosecution_dashboard(
        claims=claims,
        fer_analysis=fer_analysis,
        section3_analysis=section3_analysis,
        novelty_analysis=novelty_analysis,
        inventive_step_analysis=(
            inventive_step_analysis
        ),
        amendment_analysis=amendment_analysis,
    )


def create_prosecution_dashboard(
    *,
    claims: Iterable[Any],
    fer_analysis: Optional[
        Dict[str, Any]
    ] = None,
    section3_analysis: Optional[
        Dict[str, Any]
    ] = None,
    novelty_analysis: Optional[
        Dict[str, Any]
    ] = None,
    inventive_step_analysis: Optional[
        Dict[str, Any]
    ] = None,
    amendment_analysis: Optional[
        Dict[str, Any]
    ] = None,
) -> Dict[str, Any]:

    return analyze_prosecution(
        claims=claims,
        fer_analysis=fer_analysis,
        section3_analysis=section3_analysis,
        novelty_analysis=novelty_analysis,
        inventive_step_analysis=(
            inventive_step_analysis
        ),
        amendment_analysis=amendment_analysis,
    )


# ---------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------

def analyze_prosecution_history(
    *,
    claims: Iterable[Any],
    fer_analysis: Optional[
        Dict[str, Any]
    ] = None,
    section3_analysis: Optional[
        Dict[str, Any]
    ] = None,
    novelty_analysis: Optional[
        Dict[str, Any]
    ] = None,
    inventive_step_analysis: Optional[
        Dict[str, Any]
    ] = None,
    amendment_analysis: Optional[
        Dict[str, Any]
    ] = None,
) -> Dict[str, Any]:

    return analyze_prosecution(
        claims=claims,
        fer_analysis=fer_analysis,
        section3_analysis=section3_analysis,
        novelty_analysis=novelty_analysis,
        inventive_step_analysis=(
            inventive_step_analysis
        ),
        amendment_analysis=amendment_analysis,
    )


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

__all__ = [
    "PROSECUTION_ANALYZER_VERSION",
    "ProsecutionIssue",
    "ProsecutionClaimStatus",
    "ProsecutionDashboard",
    "extract_fer_issues",
    "extract_section3_issues",
    "extract_novelty_issues",
    "extract_inventive_step_issues",
    "extract_amendment_issues",
    "collect_prosecution_issues",
    "build_claim_statuses",
    "build_action_items",
    "build_prosecution_timeline",
    "build_prosecution_dashboard",
    "build_response_matrix",
    "build_claim_issue_map",
    "filter_issues",
    "summarize_prosecution",
    "analyze_prosecution",
    "create_prosecution_dashboard",
    "analyze_prosecution_history",
]
