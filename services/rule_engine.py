"""
Indian Patent Analyzer
Rule Engine V3

Purpose
-------
Deterministic, auditable patent-rule evaluation.

This module deliberately separates:
    1. Legal/rule signals
    2. Evidence
    3. AI interpretation

It does NOT make a final legal determination.

The engine identifies potential issues that require human review.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence


RULE_ENGINE_VERSION = "3.0.0"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def _stable_id(prefix: str, value: str) -> str:
    digest = hashlib.sha256(
        _clean(value).lower().encode("utf-8")
    ).hexdigest()[:16]

    return f"{prefix}-{digest}"


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


def _contains_any(
    text: str,
    terms: Sequence[str],
) -> bool:

    text = text.lower()

    return any(
        term.lower() in text
        for term in terms
    )


def _count_words(text: str) -> int:
    return len(
        re.findall(
            r"\b\w+\b",
            text,
        )
    )


# ---------------------------------------------------------------------------
# Rule model
# ---------------------------------------------------------------------------

@dataclass
class PatentRule:
    rule_id: str
    section: str
    title: str
    description: str
    category: str

    severity: str = "review"

    keywords: List[str] = field(
        default_factory=list
    )

    claim_categories: List[str] = field(
        default_factory=list
    )

    enabled: bool = True

    source: str = (
        "Indian Patents Act / Rules / "
        "Manual — verify against current official source"
    )

    source_reference: str = ""

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class RuleFinding:
    finding_id: str

    rule_id: str
    section: str
    title: str

    status: str
    severity: str

    message: str

    evidence: List[Dict[str, Any]] = field(
        default_factory=list
    )

    affected_claims: List[str] = field(
        default_factory=list
    )

    matched_terms: List[str] = field(
        default_factory=list
    )

    confidence: float = 0.0

    human_review_required: bool = True

    source: str = ""

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


# ---------------------------------------------------------------------------
# Default rules
# ---------------------------------------------------------------------------

DEFAULT_RULES = [
    PatentRule(
        rule_id="SEC10-CLAIM-SUPPORT",
        section="10",
        title="Claim support review",
        description=(
            "Claims should be examined for adequate support "
            "in the specification."
        ),
        category="claim_support",
        severity="high",
        keywords=[
            "claim",
            "supported",
            "specification",
            "embodiment",
        ],
    ),

    PatentRule(
        rule_id="SEC10-CLARITY",
        section="10",
        title="Claim clarity review",
        description=(
            "Claims should be reviewed for clarity, "
            "conciseness and proper definition."
        ),
        category="clarity",
        severity="medium",
        keywords=[
            "substantially",
            "approximately",
            "etc.",
            "as appropriate",
            "suitable",
            "configured",
        ],
    ),

    PatentRule(
        rule_id="SEC10-SUFFICIENCY",
        section="10",
        title="Specification sufficiency review",
        description=(
            "The specification should be reviewed for "
            "adequate disclosure of the invention."
        ),
        category="sufficiency",
        severity="high",
        keywords=[
            "algorithm",
            "controller",
            "configured",
            "machine learning",
            "processing",
        ],
    ),

    PatentRule(
        rule_id="SEC3-K",
        section="3(k)",
        title="Computer-program-related subject matter",
        description=(
            "Claims containing software/computer-program "
            "related subject matter may require Section 3(k) review."
        ),
        category="section_3",
        severity="high",
        keywords=[
            "software",
            "computer program",
            "computer-readable",
            "processor",
            "algorithm",
            "machine learning",
            "artificial intelligence",
        ],
    ),

    PatentRule(
        rule_id="SEC3-I",
        section="3(i)",
        title="Treatment-related subject matter",
        description=(
            "Claims relating to treatment or diagnostic "
            "methods may require Section 3(i) review."
        ),
        category="section_3",
        severity="high",
        keywords=[
            "treating",
            "treatment",
            "therapy",
            "therapeutic",
            "diagnosing",
            "diagnosis",
            "patient",
        ],
    ),

    PatentRule(
        rule_id="SEC3-D",
        section="3(d)",
        title="Known-substance / derivative review",
        description=(
            "Certain claims relating to known substances "
            "or derivatives may require Section 3(d) review."
        ),
        category="section_3",
        severity="high",
        keywords=[
            "derivative",
            "salt",
            "ester",
            "polymorph",
            "isomer",
            "known compound",
        ],
    ),

    PatentRule(
        rule_id="SEC3-P",
        section="3(p)",
        title="Traditional knowledge review",
        description=(
            "Claims potentially derived from traditional "
            "knowledge should receive additional review."
        ),
        category="section_3",
        severity="high",
        keywords=[
            "traditional knowledge",
            "traditional use",
            "ayurvedic",
            "herbal",
            "indigenous",
        ],
    ),

    PatentRule(
        rule_id="SEC59-AMENDMENT",
        section="59",
        title="Amendment / new-matter review",
        description=(
            "Amendments should be compared with the "
            "original disclosure and claims."
        ),
        category="amendment",
        severity="high",
        keywords=[
            "amended",
            "amendment",
            "added",
            "new matter",
            "replacement",
        ],
    ),
]


# ---------------------------------------------------------------------------
# Rule registry
# ---------------------------------------------------------------------------

class RuleRegistry:
    """
    Central rule registry.

    Rules can later be loaded from:
        data/patent_rules.json
        database
        versioned legal knowledge base
    """

    def __init__(
        self,
        rules: Optional[
            Sequence[PatentRule]
        ] = None,
    ):

        self.rules = list(
            rules
            if rules is not None
            else DEFAULT_RULES
        )

    def all(self) -> List[PatentRule]:
        return list(self.rules)

    def get(
        self,
        rule_id: str,
    ) -> Optional[PatentRule]:

        for rule in self.rules:
            if rule.rule_id == rule_id:
                return rule

        return None

    def by_section(
        self,
        section: str,
    ) -> List[PatentRule]:

        section = _clean(section).lower()

        return [
            rule
            for rule in self.rules
            if rule.section.lower() == section
        ]

    def by_category(
        self,
        category: str,
    ) -> List[PatentRule]:

        category = _clean(category).lower()

        return [
            rule
            for rule in self.rules
            if rule.category.lower()
            == category
        ]


# ---------------------------------------------------------------------------
# Text extraction
# ---------------------------------------------------------------------------

def extract_claim_text(
    claim: Dict[str, Any],
) -> str:

    return _clean(
        claim.get(
            "text",
            claim.get(
                "claim_text",
                "",
            ),
        )
    )


def extract_claim_number(
    claim: Dict[str, Any],
    index: int,
) -> str:

    value = claim.get(
        "claim_number",
        claim.get(
            "number",
            index,
        ),
    )

    return str(value)


def extract_claim_category(
    claim: Dict[str, Any],
) -> str:

    category = claim.get(
        "category",
        claim.get(
            "type",
            "",
        ),
    )

    return _clean(category).lower()


def extract_limitation_texts(
    claim: Dict[str, Any],
) -> List[str]:

    limitations = claim.get(
        "limitations",
        claim.get(
            "elements",
            [],
        ),
    )

    if not isinstance(
        limitations,
        list,
    ):
        return []

    output = []

    for limitation in limitations:

        if isinstance(
            limitation,
            str,
        ):
            output.append(
                _clean(limitation)
            )

        elif isinstance(
            limitation,
            dict,
        ):
            output.append(
                _clean(
                    limitation.get(
                        "text",
                        limitation.get(
                            "limitation",
                            "",
                        ),
                    )
                )
            )

    return [
        value
        for value in output
        if value
    ]


# ---------------------------------------------------------------------------
# Rule matching
# ---------------------------------------------------------------------------

def match_rule(
    rule: PatentRule,
    text: str,
) -> Dict[str, Any]:

    text = _clean(text)

    matched_terms = []

    for keyword in rule.keywords:

        if keyword.lower() in text.lower():

            matched_terms.append(
                keyword
            )

    matched_terms = _unique(
        matched_terms
    )

    if not matched_terms:

        return {
            "matched": False,
            "matched_terms": [],
            "confidence": 0.0,
        }

    # Conservative deterministic score.
    #
    # This is a signal score, NOT a probability that
    # the legal provision actually applies.

    confidence = min(
        1.0,
        0.45
        + 0.10 * len(matched_terms),
    )

    return {
        "matched": True,
        "matched_terms": matched_terms,
        "confidence": round(
            confidence,
            3,
        ),
    }


# ---------------------------------------------------------------------------
# Finding creation
# ---------------------------------------------------------------------------

def create_finding(
    rule: PatentRule,
    message: str,
    *,
    evidence: Optional[
        Sequence[Dict[str, Any]]
    ] = None,
    affected_claims: Optional[
        Sequence[str]
    ] = None,
    matched_terms: Optional[
        Sequence[str]
    ] = None,
    confidence: float = 0.0,
    status: str = "REVIEW",
) -> RuleFinding:

    evidence = list(
        evidence
        or []
    )

    affected_claims = _unique(
        affected_claims
        or []
    )

    matched_terms = _unique(
        matched_terms
        or []
    )

    finding_seed = "|".join(
        [
            rule.rule_id,
            message,
            ",".join(
                affected_claims
            ),
            ",".join(
                matched_terms
            ),
        ]
    )

    return RuleFinding(
        finding_id=_stable_id(
            "FINDING",
            finding_seed,
        ),
        rule_id=rule.rule_id,
        section=rule.section,
        title=rule.title,
        status=status,
        severity=rule.severity,
        message=message,
        evidence=evidence,
        affected_claims=affected_claims,
        matched_terms=matched_terms,
        confidence=round(
            max(
                0.0,
                min(
                    1.0,
                    confidence,
                ),
            ),
            3,
        ),
        human_review_required=True,
        source=rule.source,
        metadata={
            "rule_engine_version":
                RULE_ENGINE_VERSION,
            "generated_at":
                _now_utc(),
            "source_reference":
                rule.source_reference,
        },
    )


# ---------------------------------------------------------------------------
# Claim checks
# ---------------------------------------------------------------------------

def check_claims(
    claims: Sequence[Dict[str, Any]],
    registry: Optional[
        RuleRegistry
    ] = None,
) -> List[RuleFinding]:

    registry = registry or RuleRegistry()

    findings = []

    for index, claim in enumerate(
        claims,
        start=1,
    ):

        claim_number = (
            extract_claim_number(
                claim,
                index,
            )
        )

        claim_text = (
            extract_claim_text(
                claim
            )
        )

        limitations = (
            extract_limitation_texts(
                claim
            )
        )

        searchable_text = " ".join(
            [
                claim_text,
                *limitations,
            ]
        )

        if not searchable_text:
            continue

        for rule in registry.all():

            if not rule.enabled:
                continue

            match = match_rule(
                rule,
                searchable_text,
            )

            if not match["matched"]:
                continue

            message = (
                f"Potential {rule.section} "
                f"review signal detected in "
                f"claim {claim_number}. "
                f"Matched terms: "
                f"{', '.join(match['matched_terms'])}."
            )

            findings.append(
                create_finding(
                    rule,
                    message,
                    affected_claims=[
                        claim_number
                    ],
                    matched_terms=match[
                        "matched_terms"
                    ],
                    confidence=match[
                        "confidence"
                    ],
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Specification checks
# ---------------------------------------------------------------------------

def check_specification(
    specification_text: str,
    claims: Sequence[Dict[str, Any]],
    registry: Optional[
        RuleRegistry
    ] = None,
) -> List[RuleFinding]:

    registry = registry or RuleRegistry()

    text = _clean(
        specification_text
    )

    findings = []

    if not text:
        return findings

    word_count = _count_words(
        text
    )

    # This is intentionally only a review signal.
    if word_count < 100:

        rule = registry.get(
            "SEC10-SUFFICIENCY"
        )

        if rule:

            findings.append(
                create_finding(
                    rule,
                    (
                        "The extracted specification "
                        "is unusually short. Review "
                        "whether the available disclosure "
                        "is complete and sufficient."
                    ),
                    confidence=0.75,
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Claim support checks
# ---------------------------------------------------------------------------

def check_claim_support(
    claims: Sequence[Dict[str, Any]],
    specification_text: str,
    registry: Optional[
        RuleRegistry
    ] = None,
) -> List[RuleFinding]:

    registry = registry or RuleRegistry()

    rule = registry.get(
        "SEC10-CLAIM-SUPPORT"
    )

    if rule is None:
        return []

    specification_text = _clean(
        specification_text
    ).lower()

    findings = []

    for index, claim in enumerate(
        claims,
        start=1,
    ):

        claim_number = (
            extract_claim_number(
                claim,
                index,
            )
        )

        limitations = (
            extract_limitation_texts(
                claim
            )
        )

        if not limitations:
            continue

        unsupported = []

        for limitation in limitations:

            tokens = [
                token
                for token in _unique(
                    re.findall(
                        r"\b[a-zA-Z]{5,}\b",
                        limitation.lower(),
                    )
                )
            ]

            if not tokens:
                continue

            matches = sum(
                1
                for token in tokens
                if token in specification_text
            )

            coverage = (
                matches / len(tokens)
            )

            if coverage < 0.35:
                unsupported.append(
                    limitation
                )

        if unsupported:

            findings.append(
                create_finding(
                    rule,
                    (
                        f"Potential specification-support "
                        f"gap detected for claim "
                        f"{claim_number}. "
                        f"{len(unsupported)} limitation(s) "
                        f"had low lexical support in the "
                        f"available specification text."
                    ),
                    affected_claims=[
                        claim_number
                    ],
                    confidence=0.60,
                    metadata={
                        "unsupported_limitations":
                            unsupported,
                    },
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Clarity checks
# ---------------------------------------------------------------------------

def check_claim_clarity(
    claims: Sequence[Dict[str, Any]],
    registry: Optional[
        RuleRegistry
    ] = None,
) -> List[RuleFinding]:

    registry = registry or RuleRegistry()

    rule = registry.get(
        "SEC10-CLARITY"
    )

    if rule is None:
        return []

    findings = []

    vague_terms = [
        "substantially",
        "approximately",
        "about",
        "suitable",
        "appropriate",
        "etc.",
        "and the like",
        "similar",
        "optimized",
    ]

    for index, claim in enumerate(
        claims,
        start=1,
    ):

        claim_number = (
            extract_claim_number(
                claim,
                index,
            )
        )

        text = extract_claim_text(
            claim
        )

        matched = [
            term
            for term in vague_terms
            if term in text.lower()
        ]

        if not matched:
            continue

        findings.append(
            create_finding(
                rule,
                (
                    f"Potential clarity review "
                    f"signal in claim {claim_number}. "
                    f"Vague/relative expression(s): "
                    f"{', '.join(matched)}."
                ),
                affected_claims=[
                    claim_number
                ],
                matched_terms=matched,
                confidence=0.68,
            )
        )

    return findings


# ---------------------------------------------------------------------------
# Section 3 screening
# ---------------------------------------------------------------------------

def check_section_3(
    claims: Sequence[Dict[str, Any]],
    registry: Optional[
        RuleRegistry
    ] = None,
) -> List[RuleFinding]:

    registry = registry or RuleRegistry()

    findings = []

    section3_rules = [
        rule
        for rule in registry.all()
        if rule.category == "section_3"
    ]

    for index, claim in enumerate(
        claims,
        start=1,
    ):

        claim_number = (
            extract_claim_number(
                claim,
                index,
            )
        )

        text = extract_claim_text(
            claim
        )

        if not text:
            continue

        for rule in section3_rules:

            match = match_rule(
                rule,
                text,
            )

            if not match["matched"]:
                continue

            findings.append(
                create_finding(
                    rule,
                    (
                        f"Potential {rule.section} "
                        f"review signal in claim "
                        f"{claim_number}. This is a "
                        f"screening flag and not a legal "
                        f"determination."
                    ),
                    affected_claims=[
                        claim_number
                    ],
                    matched_terms=match[
                        "matched_terms"
                    ],
                    confidence=match[
                        "confidence"
                    ],
                )
            )

    return findings


# ---------------------------------------------------------------------------
# Amendment / Section 59 screening
# ---------------------------------------------------------------------------

def check_amendment(
    original_text: str,
    amended_text: str,
    registry: Optional[
        RuleRegistry
    ] = None,
) -> List[RuleFinding]:

    registry = registry or RuleRegistry()

    rule = registry.get(
        "SEC59-AMENDMENT"
    )

    if rule is None:
        return []

    original = _clean(
        original_text
    )

    amended = _clean(
        amended_text
    )

    if not original or not amended:
        return []

    original_words = set(
        re.findall(
            r"\b[a-zA-Z]{4,}\b",
            original.lower(),
        )
    )

    amended_words = set(
        re.findall(
            r"\b[a-zA-Z]{4,}\b",
            amended.lower(),
        )
    )

    added_terms = sorted(
        amended_words
        - original_words
    )

    if not added_terms:
        return []

    return [
        create_finding(
            rule,
            (
                "The amended text contains "
                "terminology not identified in "
                "the original text. Review the "
                "original disclosure and claims "
                "for support before relying on "
                "the amendment."
            ),
            matched_terms=added_terms[:30],
            confidence=0.72,
            metadata={
                "added_terms":
                    added_terms[:100],
            },
        )
    ]


# ---------------------------------------------------------------------------
# Full analysis
# ---------------------------------------------------------------------------

def run_rule_engine(
    *,
    claims: Optional[
        Sequence[Dict[str, Any]]
    ] = None,
    specification_text: str = "",
    original_text: str = "",
    amended_text: str = "",
    rules: Optional[
        Sequence[PatentRule]
    ] = None,
) -> Dict[str, Any]:

    registry = RuleRegistry(
        rules
    )

    claims = list(
        claims or []
    )

    findings = []

    findings.extend(
        check_claims(
            claims,
            registry,
        )
    )

    findings.extend(
        check_claim_support(
            claims,
            specification_text,
            registry,
        )
    )

    findings.extend(
        check_claim_clarity(
            claims,
            registry,
        )
    )

    findings.extend(
        check_section_3(
            claims,
            registry,
        )
    )

    findings.extend(
        check_specification(
            specification_text,
            claims,
            registry,
        )
    )

    if original_text and amended_text:

        findings.extend(
            check_amendment(
                original_text,
                amended_text,
                registry,
            )
        )

    finding_dicts = [
        asdict(finding)
        for finding in findings
    ]

    summary = {
        "total_findings": len(
            finding_dicts
        ),
        "high": sum(
            1
            for finding in finding_dicts
            if finding["severity"]
            == "high"
        ),
        "medium": sum(
            1
            for finding in finding_dicts
            if finding["severity"]
            == "medium"
        ),
        "low": sum(
            1
            for finding in finding_dicts
            if finding["severity"]
            == "low"
        ),
        "review": sum(
            1
            for finding in finding_dicts
            if finding["status"]
            == "REVIEW"
        ),
    }

    return {
        "rule_engine_version":
            RULE_ENGINE_VERSION,

        "generated_at":
            _now_utc(),

        "rule_count":
            len(registry.all()),

        "summary":
            summary,

        "findings":
            finding_dicts,

        "human_review_required":
            bool(findings),

        "legal_conclusion":
            False,

        "disclaimer": (
            "Rule-engine results are screening signals "
            "for professional review. They do not by "
            "themselves establish patentability, "
            "validity, infringement, or compliance."
        ),
    }


# ---------------------------------------------------------------------------
# Backward-compatible API
# ---------------------------------------------------------------------------

def evaluate_rules(
    claims: Optional[
        Sequence[Dict[str, Any]]
    ] = None,
    specification_text: str = "",
) -> Dict[str, Any]:

    return run_rule_engine(
        claims=claims,
        specification_text=specification_text,
    )


def get_rules() -> List[Dict[str, Any]]:

    return [
        asdict(rule)
        for rule in RuleRegistry().all()
    ]


__all__ = [
    "RULE_ENGINE_VERSION",
    "PatentRule",
    "RuleFinding",
    "RuleRegistry",
    "DEFAULT_RULES",
    "extract_claim_text",
    "extract_claim_number",
    "extract_claim_category",
    "extract_limitation_texts",
    "match_rule",
    "check_claims",
    "check_specification",
    "check_claim_support",
    "check_claim_clarity",
    "check_section_3",
    "check_amendment",
    "run_rule_engine",
    "evaluate_rules",
    "get_rules",
]
