"""
Indian Patent Analyzer
Scoring & Risk Engine V3

Purpose
-------
Convert structured analysis findings into transparent, explainable
signals.

IMPORTANT:
These scores are NOT:
    - patentability scores
    - legal validity scores
    - probability of grant
    - novelty determinations
    - infringement opinions

They are internal prioritization signals intended to help a human
reviewer decide what deserves attention first.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence


SCORING_VERSION = "3.0.0"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clamp(
    value: float,
    minimum: float = 0.0,
    maximum: float = 1.0,
) -> float:

    return max(
        minimum,
        min(
            maximum,
            float(value),
        ),
    )


def _clean(value: Any) -> str:
    if value is None:
        return ""

    return str(value).strip()


def _unique(values: Iterable[str]) -> List[str]:

    result = []
    seen = set()

    for value in values:

        value = _clean(value)

        if not value:
            continue

        key = value.lower()

        if key not in seen:
            seen.add(key)
            result.append(value)

    return result


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class RiskSignal:

    signal_id: str

    category: str

    title: str

    level: str

    score: float

    explanation: str

    affected_claims: List[str] = field(
        default_factory=list
    )

    evidence_ids: List[str] = field(
        default_factory=list
    )

    rule_ids: List[str] = field(
        default_factory=list
    )

    confidence: float = 0.0

    human_review_required: bool = True

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


# ---------------------------------------------------------------------------
# Severity mapping
# ---------------------------------------------------------------------------

SEVERITY_WEIGHTS = {
    "critical": 1.00,
    "high": 0.80,
    "medium": 0.55,
    "low": 0.30,
    "info": 0.10,
    "review": 0.45,
}


def severity_weight(
    severity: str,
) -> float:

    return SEVERITY_WEIGHTS.get(
        _clean(severity).lower(),
        0.45,
    )


# ---------------------------------------------------------------------------
# Finding normalization
# ---------------------------------------------------------------------------

def normalize_finding(
    finding: Dict[str, Any],
) -> Dict[str, Any]:

    severity = _clean(
        finding.get(
            "severity",
            "review",
        )
    ).lower()

    confidence = _clamp(
        float(
            finding.get(
                "confidence",
                0.0,
            )
            or 0.0
        )
    )

    return {
        "finding_id": _clean(
            finding.get(
                "finding_id",
                finding.get(
                    "id",
                    "",
                ),
            )
        ),
        "rule_id": _clean(
            finding.get(
                "rule_id",
                "",
            )
        ),
        "section": _clean(
            finding.get(
                "section",
                "",
            )
        ),
        "title": _clean(
            finding.get(
                "title",
                "Patent issue",
            )
        ),
        "severity": severity,
        "message": _clean(
            finding.get(
                "message",
                "",
            )
        ),
        "affected_claims": _unique(
            finding.get(
                "affected_claims",
                [],
            )
            or []
        ),
        "evidence": finding.get(
            "evidence",
            [],
        )
        or [],
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Finding score
# ---------------------------------------------------------------------------

def score_finding(
    finding: Dict[str, Any],
) -> float:
    """
    Produce a transparent internal prioritization score.

    Formula:

        score =
            severity_weight
            × confidence
            × evidence_factor

    Evidence increases confidence in the signal but does NOT prove
    the legal proposition.
    """

    finding = normalize_finding(
        finding
    )

    severity = severity_weight(
        finding["severity"]
    )

    confidence = finding[
        "confidence"
    ]

    evidence = finding[
        "evidence"
    ]

    evidence_factor = 1.0

    if evidence:
        evidence_factor = min(
            1.0,
            0.60
            + 0.10 * len(evidence),
        )

    return round(
        _clamp(
            severity
            * confidence
            * evidence_factor
        ),
        4,
    )


# ---------------------------------------------------------------------------
# Risk level
# ---------------------------------------------------------------------------

def risk_level(
    score: float,
) -> str:

    score = _clamp(
        score
    )

    if score >= 0.80:
        return "HIGH"

    if score >= 0.55:
        return "MEDIUM"

    if score >= 0.30:
        return "LOW"

    return "INFO"


# ---------------------------------------------------------------------------
# Convert rule findings to signals
# ---------------------------------------------------------------------------

def finding_to_signal(
    finding: Dict[str, Any],
) -> RiskSignal:

    normalized = normalize_finding(
        finding
    )

    score = score_finding(
        normalized
    )

    level = risk_level(
        score
    )

    finding_id = normalized[
        "finding_id"
    ]

    if not finding_id:
        finding_id = (
            "finding-"
            + str(
                abs(
                    hash(
                        normalized[
                            "message"
                        ]
                    )
                )
            )
        )

    return RiskSignal(
        signal_id=f"SIG-{finding_id}",
        category=(
            normalized["section"]
            or "general"
        ),
        title=normalized[
            "title"
        ],
        level=level,
        score=score,
        explanation=normalized[
            "message"
        ],
        affected_claims=normalized[
            "affected_claims"
        ],
        evidence_ids=[
            _clean(
                item.get(
                    "evidence_id",
                    item.get(
                        "id",
                        "",
                    ),
                )
            )
            for item in normalized[
                "evidence"
            ]
            if isinstance(
                item,
                dict,
            )
        ],
        rule_ids=(
            [normalized["rule_id"]]
            if normalized["rule_id"]
            else []
        ),
        confidence=normalized[
            "confidence"
        ],
        human_review_required=True,
        metadata={
            "scoring_version":
                SCORING_VERSION,
            "generated_at":
                _now_utc(),
        },
    )


# ---------------------------------------------------------------------------
# Aggregate risk
# ---------------------------------------------------------------------------

def aggregate_risk(
    signals: Sequence[
        RiskSignal
    ],
) -> Dict[str, Any]:

    if not signals:
        return {
            "overall_signal": 0.0,
            "level": "INFO",
            "signal_count": 0,
            "high_count": 0,
            "medium_count": 0,
            "low_count": 0,
        }

    # We deliberately do not simply average all signals.
    # Multiple independent issues should increase reviewer attention,
    # but the result is still an internal prioritization metric.

    weighted_sum = sum(
        signal.score
        for signal in signals
    )

    overall = _clamp(
        weighted_sum
        / max(
            1.0,
            len(signals) * 0.75,
        )
    )

    high_count = sum(
        signal.level == "HIGH"
        for signal in signals
    )

    medium_count = sum(
        signal.level == "MEDIUM"
        for signal in signals
    )

    low_count = sum(
        signal.level == "LOW"
        for signal in signals
    )

    return {
        "overall_signal":
            round(
                overall,
                4,
            ),
        "level":
            risk_level(
                overall
            ),
        "signal_count":
            len(signals),
        "high_count":
            high_count,
        "medium_count":
            medium_count,
        "low_count":
            low_count,
    }


# ---------------------------------------------------------------------------
# Claim-level risk
# ---------------------------------------------------------------------------

def aggregate_claim_risk(
    signals: Sequence[
        RiskSignal
    ],
) -> Dict[str, Dict[str, Any]]:

    claims: Dict[
        str,
        List[RiskSignal],
    ] = {}

    for signal in signals:

        for claim in (
            signal.affected_claims
        ):

            claims.setdefault(
                str(claim),
                [],
            ).append(
                signal
            )

    output = {}

    for claim_number, claim_signals in (
        claims.items()
    ):

        aggregate = aggregate_risk(
            claim_signals
        )

        output[
            claim_number
        ] = {
            **aggregate,
            "signals": [
                signal.signal_id
                for signal in claim_signals
            ],
        }

    return output


# ---------------------------------------------------------------------------
# Category-level risk
# ---------------------------------------------------------------------------

def aggregate_category_risk(
    signals: Sequence[
        RiskSignal
    ],
) -> Dict[str, Dict[str, Any]]:

    categories: Dict[
        str,
        List[RiskSignal],
    ] = {}

    for signal in signals:

        categories.setdefault(
            signal.category,
            [],
        ).append(
            signal
        )

    output = {}

    for category, category_signals in (
        categories.items()
    ):

        output[
            category
        ] = aggregate_risk(
            category_signals
        )

    return output


# ---------------------------------------------------------------------------
# Priority queue
# ---------------------------------------------------------------------------

def prioritize_signals(
    signals: Sequence[
        RiskSignal
    ],
) -> List[RiskSignal]:

    return sorted(
        signals,
        key=lambda signal: (
            signal.score,
            signal.confidence,
        ),
        reverse=True,
    )


# ---------------------------------------------------------------------------
# Full scoring pipeline
# ---------------------------------------------------------------------------

def score_analysis(
    findings: Optional[
        Sequence[Dict[str, Any]]
    ] = None,
) -> Dict[str, Any]:

    findings = list(
        findings or []
    )

    signals = [
        finding_to_signal(
            finding
        )
        for finding in findings
    ]

    signals = prioritize_signals(
        signals
    )

    overall = aggregate_risk(
        signals
    )

    claims = aggregate_claim_risk(
        signals
    )

    categories = aggregate_category_risk(
        signals
    )

    return {
        "scoring_version":
            SCORING_VERSION,

        "generated_at":
            _now_utc(),

        "overall":
            overall,

        "claim_risk":
            claims,

        "category_risk":
            categories,

        "signals": [
            asdict(signal)
            for signal in signals
        ],

        "human_review_required":
            bool(signals),

        "legal_conclusion":
            False,

        "disclaimer": (
            "Scores are internal evidence-prioritization "
            "signals. They are not legal opinions, "
            "patentability probabilities, novelty scores, "
            "validity scores, or predictions of grant."
        ),
    }


# ---------------------------------------------------------------------------
# Evidence coverage
# ---------------------------------------------------------------------------

def calculate_evidence_coverage(
    expected_items: Sequence[str],
    supported_items: Sequence[str],
) -> Dict[str, Any]:

    expected = set(
        _clean(item).lower()
        for item in expected_items
        if _clean(item)
    )

    supported = set(
        _clean(item).lower()
        for item in supported_items
        if _clean(item)
    )

    if not expected:

        return {
            "coverage":
                0.0,
            "expected":
                0,
            "supported":
                0,
            "unsupported":
                0,
        }

    covered = (
        expected
        & supported
    )

    return {
        "coverage":
            round(
                len(covered)
                / len(expected),
                4,
            ),
        "expected":
            len(expected),
        "supported":
            len(covered),
        "unsupported":
            len(
                expected
                - supported
            ),
    }


# ---------------------------------------------------------------------------
# Backward-compatible functions
# ---------------------------------------------------------------------------

def calculate_score(
    findings: Optional[
        Sequence[Dict[str, Any]]
    ] = None,
) -> float:
    """
    Backward-compatible scalar.

    Returns an internal prioritization signal between 0 and 1.
    """

    result = score_analysis(
        findings
    )

    return result[
        "overall"
    ][
        "overall_signal"
    ]


def get_risk_level(
    score: float,
) -> str:

    return risk_level(
        score
    )


__all__ = [
    "SCORING_VERSION",
    "RiskSignal",
    "severity_weight",
    "normalize_finding",
    "score_finding",
    "risk_level",
    "finding_to_signal",
    "aggregate_risk",
    "aggregate_claim_risk",
    "aggregate_category_risk",
    "prioritize_signals",
    "score_analysis",
    "calculate_evidence_coverage",
    "calculate_score",
    "get_risk_level",
]
