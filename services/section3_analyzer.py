"""
Indian Patents Act Section 3 Analyzer V3
========================================

Purpose
-------
Technical screening for possible Section 3(a)–3(p) issues.

Pipeline
--------
Patent Document
      ↓
Claims / Description
      ↓
Technical concept extraction
      ↓
Section 3 trigger detection
      ↓
Evidence passages
      ↓
Reviewer-oriented findings

Important
---------
This module does NOT determine whether Section 3 actually applies.

It identifies textual and technical indicators that may justify
professional review.

Legal conclusions must be made from the current statutory text,
applicable rules/guidelines, case law where relevant, and the
complete application record.

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


SECTION3_ANALYZER_VERSION = "3.0.0"


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


def _token_overlap(
    text_a: str,
    text_b: str,
) -> float:

    a = set(
        _normalize(
            text_a
        ).split()
    )

    b = set(
        _normalize(
            text_b
        ).split()
    )

    if not a or not b:
        return 0.0

    return len(
        a.intersection(b)
    ) / len(
        a.union(b)
    )


# ---------------------------------------------------------------------
# Data structure
# ---------------------------------------------------------------------

@dataclass
class Section3Finding:

    finding_id: str
    section: str
    title: str
    trigger_terms: List[str]
    evidence: List[str]
    claims: List[int]
    confidence: float
    status: str
    explanation: str
    review_questions: List[str]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------
# Section 3 knowledge
# ---------------------------------------------------------------------

SECTION3_RULES: Dict[str, Dict[str, Any]] = {

    "3(a)": {
        "title":
            "Frivolous invention / contrary to natural laws",

        "patterns": [
            "perpetual motion",
            "perpetual energy",
            "free energy",
            "infinite energy",
            "creates energy from nothing",
            "violates conservation of energy",
            "violates laws of thermodynamics",
            "without any energy input",
            "zero energy input",
        ],

        "concepts": [
            "natural law",
            "thermodynamics",
            "energy conservation",
            "perpetual motion",
        ],

        "questions": [
            "Does the claimed operation depend on an asserted "
            "violation of an established physical principle?",

            "Is the apparent contradiction merely a wording issue "
            "that can be resolved from the complete specification?",

            "What experimental evidence supports the claimed operation?",
        ],
    },

    "3(b)": {
        "title":
            "Public order / morality / harmful subject matter",

        "patterns": [
            "human cloning",
            "human embryo",
            "embryo cloning",
            "illegal activity",
            "criminal use",
            "terrorist use",
            "weapon for prohibited use",
        ],

        "concepts": [
            "public order",
            "morality",
            "harmful use",
            "human embryo",
        ],

        "questions": [
            "What specific claimed use or subject matter triggers "
            "the concern?",

            "Is the identified use actually part of the claim or "
            "only mentioned as a possible use in the description?",

            "What statutory exclusion is being considered?",
        ],
    },

    "3(c)": {
        "title":
            "Mere discovery of scientific principle / abstract theory",

        "patterns": [
            "discovery of a law",
            "discovery of a scientific principle",
            "new scientific principle",
            "fundamental law of nature",
            "mathematical truth",
            "abstract theory",
            "discovery of a natural phenomenon",
            "naturally occurring substance",
        ],

        "concepts": [
            "scientific principle",
            "abstract theory",
            "natural phenomenon",
            "discovery",
        ],

        "questions": [
            "Is the claim directed only to the discovery itself?",

            "Does the claim include a technical implementation "
            "beyond the discovery?",

            "Which claimed technical features distinguish the "
            "application from a mere discovery?",
        ],
    },

    "3(d)": {
        "title":
            "Known substance / new form / new property / new use",

        "patterns": [
            "new form of",
            "new polymorph",
            "new salt of",
            "new ester of",
            "new derivative of",
            "new crystal form",
            "new property of known",
            "new use of known",
            "known substance",
            "known compound",
            "enhanced efficacy",
            "therapeutic efficacy",
        ],

        "concepts": [
            "known substance",
            "new form",
            "polymorph",
            "salt",
            "derivative",
            "new use",
            "efficacy",
        ],

        "questions": [
            "Is the claimed substance already known?",

            "What structural or technical difference is claimed?",

            "What evidence supports the claimed technical effect?",

            "Is the claim directed to a new form, property or use "
            "of a known substance?",
        ],
    },

    "3(e)": {
        "title":
            "Mere admixture",

        "patterns": [
            "mixture of known substances",
            "mixture of known compounds",
            "mere admixture",
            "physical mixture",
            "simple mixture",
            "composition comprising",
            "combination of known ingredients",
            "blend of known materials",
        ],

        "concepts": [
            "mixture",
            "composition",
            "admixture",
            "combination",
        ],

        "questions": [
            "Do the components produce a combined technical effect?",

            "Is there evidence of interaction between the components?",

            "Are the claimed properties merely the aggregate "
            "properties of the individual components?",
        ],
    },

    "3(f)": {
        "title":
            "Mere arrangement / re-arrangement of known devices",

        "patterns": [
            "arrangement of known devices",
            "rearrangement of known devices",
            "known device connected to",
            "known components arranged",
            "combination of known devices",
            "known devices arranged",
        ],

        "concepts": [
            "known device",
            "arrangement",
            "rearrangement",
            "combination",
        ],

        "questions": [
            "Are the individual devices already known?",

            "Does each component perform its known function "
            "independently?",

            "Does the arrangement produce a technical interaction "
            "beyond the individual functions?",
        ],
    },

    "3(g)": {
        "title":
            "Agricultural / horticultural methods",

        "patterns": [
            "method of agriculture",
            "agricultural method",
            "cultivating",
            "cultivation method",
            "method of horticulture",
            "horticultural method",
            "growing plants",
            "crop cultivation",
            "crop production method",
        ],

        "concepts": [
            "agriculture",
            "horticulture",
            "cultivation",
            "crop",
        ],

        "questions": [
            "Is the claimed subject matter a method of agriculture "
            "or horticulture?",

            "Which exact steps are recited in the claim?",

            "Is the relevant activity actually claimed rather than "
            "merely described as an application?",
        ],
    },

    "3(h)": {
        "title":
            "Methods of treatment of humans or animals",

        "patterns": [
            "method of treating a human",
            "method of treating a patient",
            "method of treating an animal",
            "treating a patient",
            "treating a human",
            "treating an animal",
            "treatment of disease",
            "therapeutic treatment",
        ],

        "concepts": [
            "medical treatment",
            "patient",
            "treatment",
            "animal treatment",
        ],

        "questions": [
            "Does the claim itself recite treatment steps?",

            "Is the claimed subject matter directed to a method "
            "performed on a human or animal?",

            "Is the treatment language merely background information?",
        ],
    },

    "3(i)": {
        "title":
            "Diagnostic / therapeutic / surgical processes",

        "patterns": [
            "diagnosing a disease",
            "diagnosis of",
            "diagnostic method",
            "diagnostic process",
            "therapeutic method",
            "surgical method",
            "surgical procedure",
            "detecting disease in a patient",
            "determining a disease",
        ],

        "concepts": [
            "diagnostic",
            "therapeutic",
            "surgical",
            "disease detection",
        ],

        "questions": [
            "Does the claim recite a diagnostic, therapeutic or "
            "surgical process?",

            "Which steps constitute the alleged diagnostic process?",

            "Is the claimed subject matter instead directed to a "
            "device, reagent or technical apparatus?",
        ],
    },

    "3(j)": {
        "title":
            "Plants / animals / biological processes",

        "patterns": [
            "plant",
            "animal",
            "seed",
            "plant variety",
            "animal variety",
            "species",
            "biological process",
            "essentially biological process",
            "breeding",
            "cross breeding",
            "selective breeding",
        ],

        "concepts": [
            "plant",
            "animal",
            "biological process",
            "breeding",
            "seed",
        ],

        "questions": [
            "Does the claim cover a plant or animal as such?",

            "Is the process biological or essentially biological?",

            "Does the claimed subject matter fall within a statutory "
            "exception or exclusion?",
        ],
    },

    "3(k)": {
        "title":
            "Mathematical method / business method / computer program "
            "per se / algorithm",

        "patterns": [
            "mathematical method",
            "mathematical formula",
            "algorithm",
            "computer program",
            "computer programme",
            "software",
            "software module",
            "business method",
            "business process",
            "financial transaction",
            "data processing",
            "machine learning algorithm",
            "artificial intelligence algorithm",
            "neural network",
        ],

        "concepts": [
            "software",
            "algorithm",
            "computer program",
            "business method",
            "mathematical method",
            "ai",
            "machine learning",
        ],

        "questions": [
            "What technical hardware or technical implementation "
            "is recited in the claim?",

            "Is the claim directed primarily to an algorithm, "
            "computer program, business method or mathematical method?",

            "Does the claim describe a technical system or process "
            "beyond the underlying abstract computation?",

            "Which technical effect, if any, is explicitly supported "
            "by the specification?",
        ],
    },

    "3(l)": {
        "title":
            "Literary / dramatic / musical / artistic works",

        "patterns": [
            "literary work",
            "dramatic work",
            "musical work",
            "artistic work",
            "poem",
            "music composition",
            "painting",
            "artwork",
        ],

        "concepts": [
            "literary",
            "dramatic",
            "musical",
            "artistic",
        ],

        "questions": [
            "Is the claimed subject matter itself the artistic or "
            "literary work?",

            "Is the artistic material merely an input to a technical "
            "system?",
        ],
    },

    "3(m)": {
        "title":
            "Scheme / rule / method of performing mental act or game",

        "patterns": [
            "method of playing a game",
            "game method",
            "rules of a game",
            "mental act",
            "method of performing a mental act",
            "mental process",
            "scheme",
            "rules of play",
        ],

        "concepts": [
            "game",
            "mental act",
            "scheme",
            "rules",
        ],

        "questions": [
            "Does the claim primarily define rules or mental steps?",

            "Are there technical system features beyond the rules?",

            "Which features are actually necessary to perform the "
            "claimed process?",
        ],
    },

    "3(n)": {
        "title":
            "Presentation of information",

        "patterns": [
            "presentation of information",
            "displaying information",
            "display information",
            "displaying data",
            "visualizing information",
            "information display",
            "presenting data",
            "graphical presentation",
        ],

        "concepts": [
            "information presentation",
            "display",
            "visualization",
            "data presentation",
        ],

        "questions": [
            "Is the claim directed primarily to the content or "
            "presentation of information?",

            "What technical processing or system feature is claimed "
            "beyond presentation?",
        ],
    },

    "3(o)": {
        "title":
            "Topography of integrated circuits",

        "patterns": [
            "integrated circuit topography",
            "semiconductor layout",
            "circuit layout",
            "layout design of integrated circuit",
            "mask layout",
        ],

        "concepts": [
            "integrated circuit",
            "topography",
            "semiconductor layout",
        ],

        "questions": [
            "Does the claim concern the topography or layout itself?",

            "Is the claimed subject matter instead directed to a "
            "technical circuit structure?",
        ],
    },

    "3(p)": {
        "title":
            "Traditional knowledge",

        "patterns": [
            "traditional knowledge",
            "traditional medicinal knowledge",
            "traditional medicine",
            "ayurvedic knowledge",
            "known traditional use",
            "traditional use",
            "ethnobotanical knowledge",
            "traditionally known",
        ],

        "concepts": [
            "traditional knowledge",
            "traditional medicine",
            "traditional use",
        ],

        "questions": [
            "Is the claimed property or use already traditionally known?",

            "What evidence establishes the source and nature of the "
            "traditional knowledge?",

            "Does the claim merely aggregate known traditional "
            "properties?",
        ],
    },
}


# ---------------------------------------------------------------------
# Claim extraction
# ---------------------------------------------------------------------

def _extract_claim_number(
    claim: Dict[str, Any],
    fallback: int,
) -> int:

    value = claim.get(
        "claim_number",
        claim.get(
            "number",
            fallback,
        ),
    )

    try:
        return int(value)
    except Exception:
        return fallback


def normalize_claims(
    claims: Iterable[Any],
) -> List[Dict[str, Any]]:

    result = []

    for index, claim in enumerate(
        claims,
        start=1,
    ):

        if isinstance(
            claim,
            dict,
        ):

            text = _clean(
                claim.get(
                    "text",
                    claim.get(
                        "claim_text",
                        "",
                    ),
                )
            )

            number = _extract_claim_number(
                claim,
                index,
            )

        else:

            text = _clean(
                claim
            )

            number = index

        result.append(
            {
                "claim_number":
                    number,

                "text":
                    text,
            }
        )

    return result


# ---------------------------------------------------------------------
# Evidence extraction
# ---------------------------------------------------------------------

def split_evidence(
    text: str,
    *,
    chunk_size: int = 500,
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

    chunks = []

    for paragraph in paragraphs:

        paragraph = _clean(
            paragraph
        )

        if not paragraph:
            continue

        if len(paragraph) <= chunk_size:

            chunks.append(
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
                <= chunk_size
            ):

                current = (
                    current
                    + " "
                    + sentence
                ).strip()

            else:

                if current:
                    chunks.append(
                        current
                    )

                current = sentence

        if current:
            chunks.append(
                current
            )

    return chunks


# ---------------------------------------------------------------------
# Trigger matching
# ---------------------------------------------------------------------

def find_triggers(
    text: str,
    patterns: Iterable[str],
) -> List[str]:

    normalized = _normalize(
        text
    )

    matches = []

    for pattern in patterns:

        normalized_pattern = _normalize(
            pattern
        )

        if (
            normalized_pattern
            and normalized_pattern
            in normalized
        ):

            matches.append(
                pattern
            )

    return matches


def find_trigger_evidence(
    text: str,
    patterns: Iterable[str],
    max_items: int = 8,
) -> List[str]:

    chunks = split_evidence(
        text
    )

    evidence = []

    for chunk in chunks:

        if find_triggers(
            chunk,
            patterns,
        ):

            evidence.append(
                chunk
            )

        if len(evidence) >= max_items:
            break

    return evidence


# ---------------------------------------------------------------------
# Technical concept screening
# ---------------------------------------------------------------------

def calculate_section_score(
    claim_text: str,
    specification_text: str,
    rule: Dict[str, Any],
) -> Tuple[float, List[str]]:

    claim_triggers = find_triggers(
        claim_text,
        rule.get(
            "patterns",
            [],
        ),
    )

    specification_triggers = find_triggers(
        specification_text,
        rule.get(
            "patterns",
            [],
        ),
    )

    all_triggers = sorted(
        set(
            claim_triggers
            + specification_triggers
        )
    )

    score = 0.0

    # Claim evidence receives more weight because the legal analysis
    # generally concerns the claimed subject matter.

    if claim_triggers:

        score += min(
            0.70,
            0.20
            * len(
                claim_triggers
            ),
        )

    if specification_triggers:

        score += min(
            0.30,
            0.05
            * len(
                specification_triggers
            ),
        )

    return (
        min(
            1.0,
            score,
        ),
        all_triggers,
    )


# ---------------------------------------------------------------------
# Section 3 analyzer
# ---------------------------------------------------------------------

class Section3Analyzer:

    def __init__(
        self,
        rules: Optional[
            Dict[str, Dict[str, Any]]
        ] = None,
    ):

        self.rules = (
            rules
            if rules is not None
            else SECTION3_RULES
        )

    # -----------------------------------------------------------------
    # Analyze one claim
    # -----------------------------------------------------------------

    def analyze_claim(
        self,
        claim_number: int,
        claim_text: str,
        specification_text: str = "",
    ) -> List[Section3Finding]:

        findings = []

        for section, rule in self.rules.items():

            score, triggers = (
                calculate_section_score(
                    claim_text,
                    specification_text,
                    rule,
                )
            )

            if score <= 0:
                continue

            evidence = (
                find_trigger_evidence(
                    claim_text,
                    rule.get(
                        "patterns",
                        [],
                    ),
                )
            )

            # If claim has no direct trigger but specification does,
            # include specification evidence.

            if not evidence:

                evidence = (
                    find_trigger_evidence(
                        specification_text,
                        rule.get(
                            "patterns",
                            [],
                        ),
                    )
                )

            if score >= 0.70:

                status = (
                    "STRONG_REVIEW_SIGNAL"
                )

            elif score >= 0.40:

                status = (
                    "REVIEW_SIGNAL"
                )

            else:

                status = (
                    "WEAK_REVIEW_SIGNAL"
                )

            explanation = (
                f"Language associated with "
                f"Section {section} was detected. "
                f"This is a screening signal only; "
                f"the statutory provision must be evaluated "
                f"against the complete claim, specification, "
                f"applicable law and relevant guidance."
            )

            findings.append(
                Section3Finding(
                    finding_id=_stable_id(
                        "S3",
                        f"{section}|"
                        f"{claim_number}|"
                        f"{claim_text}",
                    ),
                    section=section,
                    title=rule.get(
                        "title",
                        "",
                    ),
                    trigger_terms=triggers,
                    evidence=evidence,
                    claims=[
                        claim_number
                    ],
                    confidence=round(
                        score,
                        4,
                    ),
                    status=status,
                    explanation=explanation,
                    review_questions=list(
                        rule.get(
                            "questions",
                            [],
                        )
                    ),
                )
            )

        return findings

    # -----------------------------------------------------------------
    # Analyze document
    # -----------------------------------------------------------------

    def analyze(
        self,
        claims: Iterable[Any],
        specification_text: str = "",
    ) -> Dict[str, Any]:

        normalized_claims = (
            normalize_claims(
                claims
            )
        )

        all_findings = []

        for claim in normalized_claims:

            findings = self.analyze_claim(
                claim_number=claim[
                    "claim_number"
                ],
                claim_text=claim[
                    "text"
                ],
                specification_text=(
                    specification_text
                ),
            )

            all_findings.extend(
                findings
            )

        section_counts: Dict[
            str,
            int
        ] = {}

        for finding in all_findings:

            section = finding.section

            section_counts[
                section
            ] = (
                section_counts.get(
                    section,
                    0,
                )
                + 1
            )

        claim_counts: Dict[
            int,
            int
        ] = {}

        for finding in all_findings:

            for claim_number in (
                finding.claims
            ):

                claim_counts[
                    claim_number
                ] = (
                    claim_counts.get(
                        claim_number,
                        0,
                    )
                    + 1
                )

        return {
            "success":
                True,

            "section3_analyzer_version":
                SECTION3_ANALYZER_VERSION,

            "generated_at":
                _utc_now(),

            "claim_count":
                len(
                    normalized_claims
                ),

            "finding_count":
                len(
                    all_findings
                ),

            "findings": [
                item.to_dict()
                for item
                in all_findings
            ],

            "section_counts":
                section_counts,

            "claim_counts":
                claim_counts,

            "review_notice":
                (
                    "Section 3 findings are automated screening "
                    "signals and do not establish that any "
                    "statutory exclusion applies."
                ),
        }


# ---------------------------------------------------------------------
# Section-specific helpers
# ---------------------------------------------------------------------

def analyze_section_3k(
    claims: Iterable[Any],
    specification_text: str = "",
) -> Dict[str, Any]:

    analyzer = (
        Section3Analyzer()
    )

    result = analyzer.analyze(
        claims,
        specification_text,
    )

    findings = [
        finding
        for finding in result[
            "findings"
        ]
        if finding.get(
            "section"
        ) == "3(k)"
    ]

    return {
        "section":
            "3(k)",

        "finding_count":
            len(findings),

        "findings":
            findings,
    }


def analyze_section_3d(
    claims: Iterable[Any],
    specification_text: str = "",
) -> Dict[str, Any]:

    analyzer = (
        Section3Analyzer()
    )

    result = analyzer.analyze(
        claims,
        specification_text,
    )

    findings = [
        finding
        for finding in result[
            "findings"
        ]
        if finding.get(
            "section"
        ) == "3(d)"
    ]

    return {
        "section":
            "3(d)",

        "finding_count":
            len(findings),

        "findings":
            findings,
    }


# ---------------------------------------------------------------------
# Evidence mapping
# ---------------------------------------------------------------------

def build_section3_evidence_map(
    analysis: Dict[str, Any],
) -> List[Dict[str, Any]]:

    mapping = []

    for finding in _as_list(
        analysis.get(
            "findings",
            [],
        )
    ):

        if not isinstance(
            finding,
            dict,
        ):
            continue

        for evidence in _as_list(
            finding.get(
                "evidence",
                [],
            )
        ):

            mapping.append(
                {
                    "finding_id":
                        finding.get(
                            "finding_id",
                            "",
                        ),

                    "section":
                        finding.get(
                            "section",
                            "",
                        ),

                    "claims":
                        finding.get(
                            "claims",
                            [],
                        ),

                    "evidence":
                        evidence,

                    "status":
                        finding.get(
                            "status",
                            "",
                        ),

                    "confidence":
                        finding.get(
                            "confidence",
                            0.0,
                        ),
                }
            )

    return mapping


# ---------------------------------------------------------------------
# Section 3 dashboard
# ---------------------------------------------------------------------

def build_section3_dashboard(
    analysis: Dict[str, Any],
) -> Dict[str, Any]:

    findings = [
        item
        for item in _as_list(
            analysis.get(
                "findings",
                [],
            )
        )
        if isinstance(
            item,
            dict,
        )
    ]

    strong = [
        item
        for item in findings
        if item.get(
            "status"
        ) == "STRONG_REVIEW_SIGNAL"
    ]

    review = [
        item
        for item in findings
        if item.get(
            "status"
        ) == "REVIEW_SIGNAL"
    ]

    weak = [
        item
        for item in findings
        if item.get(
            "status"
        ) == "WEAK_REVIEW_SIGNAL"
    ]

    sections = {}

    for finding in findings:

        section = finding.get(
            "section",
            "",
        )

        sections.setdefault(
            section,
            [],
        ).append(
            finding
        )

    return {
        "total_findings":
            len(findings),

        "strong_review_signals":
            len(strong),

        "review_signals":
            len(review),

        "weak_review_signals":
            len(weak),

        "sections":
            sections,

        "evidence_map":
            build_section3_evidence_map(
                analysis
            ),
    }


# ---------------------------------------------------------------------
# Human-readable summary
# ---------------------------------------------------------------------

def summarize_section3(
    analysis: Dict[str, Any],
) -> str:

    counts = analysis.get(
        "section_counts",
        {},
    )

    if not counts:

        return (
            "No Section 3 screening signals were detected "
            "by the configured technical trigger rules."
        )

    parts = [
        f"{section}: {count}"
        for section, count
        in sorted(
            counts.items()
        )
    ]

    return (
        "Section 3 screening identified the following "
        "technical-language signals: "
        + ", ".join(parts)
        + ". These signals require review against the "
        "complete application and applicable law."
    )


# ---------------------------------------------------------------------
# Backward-compatible functions
# ---------------------------------------------------------------------

def analyze_section3(
    claims: Iterable[Any],
    specification_text: str = "",
) -> Dict[str, Any]:

    return (
        Section3Analyzer()
        .analyze(
            claims,
            specification_text,
        )
    )


def check_section3(
    claims: Iterable[Any],
    specification_text: str = "",
) -> Dict[str, Any]:

    return analyze_section3(
        claims,
        specification_text,
    )


def detect_section3_issues(
    text: str,
) -> Dict[str, Any]:

    # Useful for older app code that supplies a single text blob.

    return analyze_section3(
        claims=[
            {
                "claim_number":
                    1,

                "text":
                    text,
            }
        ],
        specification_text=text,
    )


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

__all__ = [
    "SECTION3_ANALYZER_VERSION",
    "SECTION3_RULES",
    "Section3Finding",
    "Section3Analyzer",
    "normalize_claims",
    "split_evidence",
    "find_triggers",
    "find_trigger_evidence",
    "calculate_section_score",
    "analyze_section3",
    "check_section3",
    "detect_section3_issues",
    "analyze_section_3k",
    "analyze_section_3d",
    "build_section3_evidence_map",
    "build_section3_dashboard",
    "summarize_section3",
]
