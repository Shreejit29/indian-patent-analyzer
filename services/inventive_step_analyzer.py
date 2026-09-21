"""
Inventive Step Analyzer V3
==========================

Purpose
-------
Structured screening of inventive-step / obviousness issues.

The analyzer separates:

    1. Claim limitations
    2. Single-reference disclosure
    3. Differences between claim and references
    4. Potential combinations of references
    5. Technical relationships between missing features
    6. Motivation / rationale signals
    7. Evidence strength
    8. Reviewer questions

Important
---------
This is a screening and evidence-organization engine.

It does NOT make a definitive legal conclusion that an invention
does or does not involve an inventive step.

A formal analysis may require:
    - applicable statutory provisions
    - examination guidelines
    - relevant case law
    - claim construction
    - identification of the appropriate starting reference
    - technical problem
    - differences
    - technical effects
    - common general knowledge
    - motivation to combine
    - hindsight analysis
    - date/publication verification
    - expert evidence

Version
-------
3.0.0
"""

from __future__ import annotations

import hashlib
import itertools
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


INVENTIVE_STEP_ANALYZER_VERSION = "3.0.0"


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


def _unique(
    values: Iterable[str],
) -> List[str]:

    seen = set()
    result = []

    for value in values:

        value = _clean(
            value
        )

        if not value:
            continue

        key = value.lower()

        if key in seen:
            continue

        seen.add(
            key
        )

        result.append(
            value
        )

    return result


# ---------------------------------------------------------------------
# Token similarity
# ---------------------------------------------------------------------

STOP_WORDS = {
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
    "configured",
}


def _tokens(
    text: str,
) -> set:

    normalized = _normalize(
        text
    )

    return {
        token
        for token in normalized.split()
        if token
        and token not in STOP_WORDS
        and len(token) > 2
    }


def lexical_similarity(
    text_a: str,
    text_b: str,
) -> float:

    a = _tokens(
        text_a
    )

    b = _tokens(
        text_b
    )

    if not a or not b:
        return 0.0

    intersection = a & b
    union = a | b

    return (
        len(intersection)
        / len(union)
    )


def overlap_terms(
    text_a: str,
    text_b: str,
) -> List[str]:

    return sorted(
        _tokens(
            text_a
        )
        & _tokens(
            text_b
        )
    )


# ---------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------

@dataclass
class FeatureDifference:

    limitation_id: str
    limitation_text: str

    reference_ids: List[str]

    best_reference_id: str
    best_reference_score: float

    disclosure_status: str

    difference_type: str

    technical_significance: str

    evidence: List[Dict[str, Any]]

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(
            self
        )


@dataclass
class ReferenceCombination:

    combination_id: str

    reference_ids: List[str]
    reference_titles: List[str]

    covered_limitation_ids: List[str]
    missing_limitation_ids: List[str]

    coverage: float

    complementarity: float
    overlap: float

    combination_signal: str

    rationale: str

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(
            self
        )


@dataclass
class InventiveStepFinding:

    claim_number: int
    claim_text: str

    starting_reference_id: str
    starting_reference_title: str

    differences: List[
        FeatureDifference
    ]

    combinations: List[
        ReferenceCombination
    ]

    technical_problem_signals: List[str]
    technical_effect_signals: List[str]
    motivation_signals: List[str]

    evidence_strength: float

    status: str

    reasoning: str

    review_questions: List[str]

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        data = asdict(
            self
        )

        data["differences"] = [
            item.to_dict()
            if isinstance(
                item,
                FeatureDifference,
            )
            else item
            for item
            in self.differences
        ]

        data["combinations"] = [
            item.to_dict()
            if isinstance(
                item,
                ReferenceCombination,
            )
            else item
            for item
            in self.combinations
        ]

        return data


# ---------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------

FEATURE_DISCLOSURE_THRESHOLD = 0.60
STRONG_FEATURE_THRESHOLD = 0.80

COMBINATION_COVERAGE_THRESHOLD = 0.75
STRONG_COMBINATION_THRESHOLD = 0.90

TECHNICAL_PROBLEM_THRESHOLD = 0.45
TECHNICAL_EFFECT_THRESHOLD = 0.45
MOTIVATION_THRESHOLD = 0.50


# ---------------------------------------------------------------------
# Claim normalization
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

            text_value = _clean(
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

            limitation_type = _clean(
                limitation.get(
                    "type",
                    "",
                )
            )

        else:

            limitation_id = ""
            text_value = _clean(
                limitation
            )
            limitation_type = ""

        if not limitation_id:

            limitation_id = _stable_id(
                "L",
                f"{number}|{index}|{text_value}",
            )

        if text_value:

            normalized_limitations.append(
                {
                    "limitation_id":
                        limitation_id,

                    "text":
                        text_value,

                    "type":
                        limitation_type,
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


# ---------------------------------------------------------------------
# Evidence normalization
# ---------------------------------------------------------------------

def normalize_evidence_claim(
    evidence_claim: Dict[str, Any],
) -> Dict[str, Any]:

    if not isinstance(
        evidence_claim,
        dict,
    ):

        return {
            "limitations": []
        }

    result = {
        "claim_number":
            evidence_claim.get(
                "claim_number",
                1,
            ),

        "claim_text":
            _clean(
                evidence_claim.get(
                    "claim_text",
                    "",
                )
            ),

        "limitations": [],
    }

    for limitation in evidence_claim.get(
        "limitations",
        [],
    ):

        if not isinstance(
            limitation,
            dict,
        ):
            continue

        result[
            "limitations"
        ].append(
            limitation
        )

    return result


def _evidence_score(
    evidence: Dict[str, Any],
) -> float:

    return _safe_float(
        evidence.get(
            "combined_score",
            evidence.get(
                "score",
                0.0,
            ),
        )
    )


# ---------------------------------------------------------------------
# Reference normalization
# ---------------------------------------------------------------------

def normalize_references(
    documents: Iterable[Any],
) -> Dict[str, Dict[str, Any]]:

    result = {}

    for index, document in enumerate(
        documents,
        start=1,
    ):

        if not isinstance(
            document,
            dict,
        ):

            document = {
                "text":
                    _clean(
                        document
                    )
            }

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

            "text":
                _clean(
                    document.get(
                        "text",
                        document.get(
                            "content",
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
                        "",
                    )
                ),

            "priority_date":
                _clean(
                    document.get(
                        "priority_date",
                        "",
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

            "metadata":
                document.get(
                    "metadata",
                    {},
                ),
        }

    return result


# ---------------------------------------------------------------------
# Difference analysis
# ---------------------------------------------------------------------

def find_limitation_evidence(
    limitation: Dict[str, Any],
    evidence_claim: Optional[
        Dict[str, Any]
    ] = None,
) -> List[Dict[str, Any]]:

    limitation_id = _clean(
        limitation.get(
            "limitation_id",
            "",
        )
    )

    if not evidence_claim:

        return []

    for candidate in evidence_claim.get(
        "limitations",
        [],
    ):

        if not isinstance(
            candidate,
            dict,
        ):
            continue

        candidate_id = _clean(
            candidate.get(
                "limitation_id",
                "",
            )
        )

        if candidate_id == limitation_id:

            evidence = candidate.get(
                "evidence",
                [],
            )

            if isinstance(
                evidence,
                list,
            ):

                return [
                    item
                    for item
                    in evidence
                    if isinstance(
                        item,
                        dict,
                    )
                ]

    return []


def build_feature_difference(
    limitation: Dict[str, Any],
    evidence_claim: Optional[
        Dict[str, Any]
    ],
    references: Dict[str, Dict[str, Any]],
) -> FeatureDifference:

    limitation_id = _clean(
        limitation.get(
            "limitation_id",
            "",
        )
    )

    limitation_text = _clean(
        limitation.get(
            "text",
            limitation.get(
                "limitation_text",
                "",
            ),
        )
    )

    evidence = find_limitation_evidence(
        limitation,
        evidence_claim,
    )

    grouped = {}

    for item in evidence:

        document_id = _clean(
            item.get(
                "document_id",
                "",
            )
        )

        if not document_id:
            continue

        grouped.setdefault(
            document_id,
            [],
        ).append(
            item
        )

    best_reference_id = ""
    best_score = 0.0

    for document_id, items in grouped.items():

        score = max(
            _evidence_score(
                item
            )
            for item
            in items
        )

        if score > best_score:

            best_score = score
            best_reference_id = (
                document_id
            )

    reference_ids = sorted(
        grouped.keys()
    )

    if best_score >= STRONG_FEATURE_THRESHOLD:

        disclosure_status = (
            "STRONG_DISCLOSURE"
        )

        difference_type = (
            "NOT_DISTINCTLY_DIFFERENT"
        )

        technical_significance = (
            "The feature appears strongly represented "
            "in the retrieved evidence."
        )

    elif best_score >= FEATURE_DISCLOSURE_THRESHOLD:

        disclosure_status = (
            "SUBSTANTIAL_DISCLOSURE"
        )

        difference_type = (
            "POSSIBLY_DISCLOSED"
        )

        technical_significance = (
            "The feature has substantial retrieved support "
            "but requires contextual technical review."
        )

    elif best_score >= 0.40:

        disclosure_status = (
            "PARTIAL_DISCLOSURE"
        )

        difference_type = (
            "POTENTIAL_DIFFERENCE"
        )

        technical_significance = (
            "Only partial evidence was identified; this "
            "feature may represent a relevant difference."
        )

    else:

        disclosure_status = (
            "WEAK_OR_NO_DISCLOSURE"
        )

        difference_type = (
            "POTENTIAL_DISTINGUISHING_FEATURE"
        )

        technical_significance = (
            "The retrieved evidence does not strongly "
            "support disclosure of this feature."
        )

    return FeatureDifference(
        limitation_id=limitation_id,
        limitation_text=limitation_text,
        reference_ids=reference_ids,
        best_reference_id=best_reference_id,
        best_reference_score=round(
            best_score,
            6,
        ),
        disclosure_status=disclosure_status,
        difference_type=difference_type,
        technical_significance=technical_significance,
        evidence=evidence[:10],
    )


# ---------------------------------------------------------------------
# Technical relationship analysis
# ---------------------------------------------------------------------

def identify_technical_relationship(
    limitation_text: str,
) -> Dict[str, Any]:

    text = _normalize(
        limitation_text
    )

    signals = []

    relationship_patterns = {
        "causal":
            [
                "causes",
                "causing",
                "responsive to",
                "in response to",
                "based on",
                "determines",
                "determining",
            ],

        "feedback":
            [
                "feedback",
                "closed loop",
                "adjusts based on",
                "controls based on",
                "iteratively",
            ],

        "physical_interaction":
            [
                "coupled",
                "connected",
                "interacts",
                "electrically connected",
                "mechanically coupled",
                "thermally coupled",
            ],

        "temporal":
            [
                "before",
                "after",
                "subsequently",
                "simultaneously",
                "during",
                "while",
            ],

        "optimization":
            [
                "optimize",
                "optimizing",
                "minimize",
                "maximize",
                "improve efficiency",
                "reduce energy",
                "reduce error",
            ],

        "technical_effect":
            [
                "reduces noise",
                "reduces power",
                "improves accuracy",
                "improves efficiency",
                "reduces temperature",
                "increases capacity",
                "improves stability",
                "improves signal",
            ],
    }

    for category, patterns in (
        relationship_patterns.items()
    ):

        matched = []

        for pattern in patterns:

            if _normalize(
                pattern
            ) in text:

                matched.append(
                    pattern
                )

        if matched:

            signals.append(
                {
                    "type":
                        category,

                    "terms":
                        matched,
                }
            )

    return {
        "signals":
            signals,

        "has_technical_relationship":
            bool(signals),
    }


# ---------------------------------------------------------------------
# Technical problem / effect extraction
# ---------------------------------------------------------------------

def extract_technical_problem_signals(
    claim_text: str,
    specification_text: str = "",
) -> List[str]:

    text = _normalize(
        claim_text
        + " "
        + specification_text
    )

    patterns = [
        "reduce",
        "reduces",
        "reduction",
        "improve",
        "improves",
        "improvement",
        "increase",
        "increases",
        "stability",
        "efficiency",
        "accuracy",
        "noise",
        "power consumption",
        "energy consumption",
        "temperature",
        "degradation",
        "reliability",
        "latency",
        "error",
        "failure",
        "wear",
        "capacity",
        "performance",
    ]

    return [
        pattern
        for pattern
        in patterns
        if pattern in text
    ]


def extract_technical_effect_signals(
    claim_text: str,
    specification_text: str = "",
) -> List[str]:

    text = _normalize(
        claim_text
        + " "
        + specification_text
    )

    patterns = [
        "improved efficiency",
        "improved accuracy",
        "reduced power",
        "reduced energy",
        "reduced temperature",
        "reduced noise",
        "improved stability",
        "increased capacity",
        "reduced degradation",
        "improved reliability",
        "reduced latency",
        "improved signal",
        "reduced error",
        "increased performance",
    ]

    return [
        pattern
        for pattern
        in patterns
        if pattern in text
    ]


# ---------------------------------------------------------------------
# Motivation-to-combine signals
# ---------------------------------------------------------------------

def detect_motivation_signals(
    reference_text: str,
    target_feature_text: str,
) -> List[str]:

    text = _normalize(
        reference_text
    )

    target = _normalize(
        target_feature_text
    )

    signals = []

    explicit_patterns = [
        "combine",
        "combining",
        "may be combined",
        "can be combined",
        "in combination with",
        "alternative embodiment",
        "another embodiment",
        "optionally",
        "compatible with",
        "adapted for use with",
        "configured to work with",
        "improve performance",
        "reduce cost",
        "reduce power",
        "improve efficiency",
    ]

    for pattern in explicit_patterns:

        if _normalize(
            pattern
        ) in text:

            signals.append(
                pattern
            )

    target_terms = _tokens(
        target
    )

    reference_terms = _tokens(
        text
    )

    shared = (
        target_terms
        & reference_terms
    )

    if len(shared) >= 3:

        signals.append(
            "shared_technical_vocabulary"
        )

    return _unique(
        signals
    )


def calculate_motivation_score(
    signals: Sequence[str],
) -> float:

    if not signals:
        return 0.0

    score = min(
        1.0,
        len(signals)
        * 0.15,
    )

    if (
        "may be combined"
        in signals
        or "can be combined"
        in signals
        or "in combination with"
        in signals
    ):

        score += 0.25

    return _clamp(
        score
    )


# ---------------------------------------------------------------------
# Reference combination
# ---------------------------------------------------------------------

def build_reference_combination(
    reference_a: Dict[str, Any],
    reference_b: Dict[str, Any],
    limitations: List[Dict[str, Any]],
    evidence_claim: Optional[
        Dict[str, Any]
    ],
) -> ReferenceCombination:

    id_a = reference_a[
        "document_id"
    ]

    id_b = reference_b[
        "document_id"
    ]

    evidence_map = {}

    for limitation in (
        evidence_claim.get(
            "limitations",
            [],
        )
        if evidence_claim
        else []
    ):

        limitation_id = _clean(
            limitation.get(
                "limitation_id",
                "",
            )
        )

        if not limitation_id:
            continue

        document_scores = {}

        for evidence in (
            limitation.get(
                "evidence",
                [],
            )
        ):

            document_id = _clean(
                evidence.get(
                    "document_id",
                    "",
                )
            )

            if document_id:

                document_scores[
                    document_id
                ] = max(
                    document_scores.get(
                        document_id,
                        0.0,
                    ),
                    _evidence_score(
                        evidence
                    ),
                )

        evidence_map[
            limitation_id
        ] = document_scores

    covered_a = set()
    covered_b = set()

    for limitation in limitations:

        limitation_id = limitation[
            "limitation_id"
        ]

        scores = evidence_map.get(
            limitation_id,
            {},
        )

        if scores.get(
            id_a,
            0.0,
        ) >= FEATURE_DISCLOSURE_THRESHOLD:

            covered_a.add(
                limitation_id
            )

        if scores.get(
            id_b,
            0.0,
        ) >= FEATURE_DISCLOSURE_THRESHOLD:

            covered_b.add(
                limitation_id
            )

    union = (
        covered_a
        | covered_b
    )

    intersection = (
        covered_a
        & covered_b
    )

    total = len(
        limitations
    )

    coverage = (
        len(union)
        / total
        if total
        else 0.0
    )

    # Complementarity measures how much each reference contributes
    # something not already covered by the other.
    unique_a = (
        covered_a
        - covered_b
    )

    unique_b = (
        covered_b
        - covered_a
    )

    if total:

        complementarity = (
            len(
                unique_a
            )
            + len(
                unique_b
            )
        ) / total

        overlap = (
            len(
                intersection
            )
            / total
        )

    else:

        complementarity = 0.0
        overlap = 0.0

    target_missing = [
        limitation
        for limitation
        in limitations
        if limitation[
            "limitation_id"
        ]
        not in union
    ]

    missing_ids = [
        limitation[
            "limitation_id"
        ]
        for limitation
        in target_missing
    ]

    technical_relationships = []

    for limitation in target_missing:

        relationship = (
            identify_technical_relationship(
                limitation[
                    "text"
                ]
            )
        )

        if relationship[
            "has_technical_relationship"
        ]:

            technical_relationships.extend(
                relationship[
                    "signals"
                ]
            )

    signals_a = detect_motivation_signals(
        reference_a.get(
            "text",
            "",
        ),
        " ".join(
            limitation[
                "text"
            ]
            for limitation
            in target_missing
        ),
    )

    signals_b = detect_motivation_signals(
        reference_b.get(
            "text",
            "",
        ),
        " ".join(
            limitation[
                "text"
            ]
            for limitation
            in target_missing
        ),
    )

    motivation_score = (
        calculate_motivation_score(
            _unique(
                signals_a
                + signals_b
            )
        )
    )

    if (
        coverage >= STRONG_COMBINATION_THRESHOLD
        and motivation_score
        >= MOTIVATION_THRESHOLD
    ):

        signal = (
            "STRONG_COMBINATION_REVIEW_SIGNAL"
        )

        rationale = (
            "The two references collectively cover most or all "
            "analyzed limitations and contain some textual signals "
            "that may warrant investigating whether a skilled "
            "person would have had a reason to combine them."
        )

    elif (
        coverage
        >= COMBINATION_COVERAGE_THRESHOLD
    ):

        signal = (
            "COMBINATION_REVIEW_SIGNAL"
        )

        rationale = (
            "The references collectively cover a substantial "
            "portion of the claim. A separate technical and "
            "legal analysis of motivation to combine is required."
        )

    else:

        signal = (
            "WEAK_COMBINATION_SIGNAL"
        )

        rationale = (
            "The selected references do not collectively provide "
            "strong coverage of the analyzed limitations."
        )

    return ReferenceCombination(
        combination_id=_stable_id(
            "COMBO",
            f"{id_a}|{id_b}",
        ),
        reference_ids=[
            id_a,
            id_b,
        ],
        reference_titles=[
            reference_a.get(
                "title",
                "",
            ),
            reference_b.get(
                "title",
                "",
            ),
        ],
        covered_limitation_ids=sorted(
            union
        ),
        missing_limitation_ids=sorted(
            missing_ids
        ),
        coverage=round(
            _clamp(
                coverage
            ),
            6,
        ),
        complementarity=round(
            _clamp(
                complementarity
            ),
            6,
        ),
        overlap=round(
            _clamp(
                overlap
            ),
            6,
        ),
        combination_signal=signal,
        rationale=rationale,
    )


# ---------------------------------------------------------------------
# Candidate reference selection
# ---------------------------------------------------------------------

def select_candidate_references(
    evidence_claim: Dict[str, Any],
    references: Dict[str, Dict[str, Any]],
    max_references: int = 8,
) -> List[str]:

    scores = {}

    for limitation in evidence_claim.get(
        "limitations",
        [],
    ):

        for evidence in (
            limitation.get(
                "evidence",
                [],
            )
        ):

            document_id = _clean(
                evidence.get(
                    "document_id",
                    "",
                )
            )

            if not document_id:
                continue

            score = _evidence_score(
                evidence
            )

            scores[
                document_id
            ] = max(
                scores.get(
                    document_id,
                    0.0,
                ),
                score,
            )

    ranked = sorted(
        scores.items(),
        key=lambda item: item[
            1
        ],
        reverse=True,
    )

    return [
        document_id
        for document_id, _
        in ranked[
            :max_references
        ]
        if document_id
        in references
    ]


# ---------------------------------------------------------------------
# Claim-level inventive-step analysis
# ---------------------------------------------------------------------

def analyze_claim_inventive_step(
    claim: Dict[str, Any],
    evidence_claim: Dict[str, Any],
    references: Dict[str, Dict[str, Any]],
    specification_text: str = "",
) -> InventiveStepFinding:

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

    limitations = claim.get(
        "limitations",
        [],
    )

    differences = []

    for limitation in limitations:

        difference = (
            build_feature_difference(
                limitation,
                evidence_claim,
                references,
            )
        )

        differences.append(
            difference
        )

    # Select the reference with the broadest evidence coverage
    # as a candidate starting reference.
    reference_scores = {}

    for difference in differences:

        for evidence in difference.evidence:

            document_id = _clean(
                evidence.get(
                    "document_id",
                    "",
                )
            )

            if not document_id:
                continue

            reference_scores[
                document_id
            ] = max(
                reference_scores.get(
                    document_id,
                    0.0,
                ),
                _evidence_score(
                    evidence
                ),
            )

    starting_reference_id = ""
    starting_reference_title = ""

    if reference_scores:

        starting_reference_id = max(
            reference_scores,
            key=reference_scores.get,
        )

        starting_reference_title = (
            references.get(
                starting_reference_id,
                {},
            ).get(
                "title",
                "",
            )
        )

    # Generate candidate combinations.
    candidate_ids = (
        select_candidate_references(
            evidence_claim,
            references,
        )
    )

    combinations = []

    for id_a, id_b in itertools.combinations(
        candidate_ids,
        2,
    ):

        combination = (
            build_reference_combination(
                references[id_a],
                references[id_b],
                limitations,
                evidence_claim,
            )
        )

        combinations.append(
            combination
        )

    combinations.sort(
        key=lambda item: (
            item.coverage,
            item.complementarity,
            item.overlap,
        ),
        reverse=True,
    )

    combinations = combinations[
        :10
    ]

    technical_problem_signals = (
        extract_technical_problem_signals(
            claim_text,
            specification_text,
        )
    )

    technical_effect_signals = (
        extract_technical_effect_signals(
            claim_text,
            specification_text,
        )
    )

    motivation_signals = []

    for combination in combinations:

        ids = combination.reference_ids

        if len(ids) != 2:
            continue

        for document_id in ids:

            document = references.get(
                document_id,
                {},
            )

            signals = (
                detect_motivation_signals(
                    document.get(
                        "text",
                        "",
                    ),
                    " ".join(
                        difference.limitation_text
                        for difference
                        in differences
                        if difference.difference_type
                        == "POTENTIAL_DISTINGUISHING_FEATURE"
                    ),
                )
            )

            motivation_signals.extend(
                signals
            )

    motivation_signals = _unique(
        motivation_signals
    )

    # Evidence strength.
    if differences:

        average_feature_score = (
            sum(
                difference.best_reference_score
                for difference
                in differences
            )
            / len(
                differences
            )
        )

    else:

        average_feature_score = 0.0

    best_combination_coverage = (
        combinations[0].coverage
        if combinations
        else 0.0
    )

    motivation_score = (
        calculate_motivation_score(
            motivation_signals
        )
    )

    evidence_strength = _clamp(
        0.50
        * average_feature_score
        + 0.30
        * best_combination_coverage
        + 0.20
        * motivation_score
    )

    distinguishing_features = [
        difference
        for difference
        in differences
        if difference.difference_type
        in {
            "POTENTIAL_DIFFERENCE",
            "POTENTIAL_DISTINGUISHING_FEATURE",
        }
    ]

    # -------------------------------------------------------------
    # Screening status
    # -------------------------------------------------------------

    if (
        not distinguishing_features
        and average_feature_score
        >= FEATURE_DISCLOSURE_THRESHOLD
    ):

        status = (
            "LOW_DIFFERENCE_SIGNAL"
        )

        reasoning = (
            "The retrieved references provide substantial "
            "coverage of the analyzed limitations and few "
            "distinctive feature gaps were identified. "
            "Further technical and legal review remains necessary."
        )

    elif (
        best_combination_coverage
        >= COMBINATION_COVERAGE_THRESHOLD
        and motivation_score
        >= MOTIVATION_THRESHOLD
        and distinguishing_features
    ):

        status = (
            "COMBINATION_REVIEW_SIGNAL"
        )

        reasoning = (
            "The evidence contains a potentially relevant "
            "combination of references covering many claim "
            "features, together with textual motivation signals. "
            "The technical relationship, problem, effect and "
            "actual motivation to combine require focused review."
        )

    elif distinguishing_features:

        status = (
            "DISTINGUISHING_FEATURE_SIGNAL"
        )

        reasoning = (
            "One or more claim limitations remain insufficiently "
            "supported by the retrieved references. These features "
            "should be investigated for their technical significance "
            "and relationship to the cited prior art."
        )

    else:

        status = (
            "INCONCLUSIVE"
        )

        reasoning = (
            "The available evidence does not provide enough "
            "structured information for a strong inventive-step "
            "screening signal."
        )

    review_questions = [
        "What is the closest technically relevant reference?",
        "Which exact claim limitations distinguish the claim "
        "from that reference?",
        "What technical problem is solved by those differences?",
        "What technical effect is actually supported by the "
        "specification?",
        "Would the skilled person have had a reason to modify "
        "the starting reference?",
        "Is there evidence of a teaching, suggestion or motivation "
        "toward the claimed combination?",
        "Would the proposed combination require hindsight?",
        "Are the references legally available prior art for the "
        "relevant date?",
        "Are common-general-knowledge considerations required?",
    ]

    return InventiveStepFinding(
        claim_number=claim_number,
        claim_text=claim_text,
        starting_reference_id=(
            starting_reference_id
        ),
        starting_reference_title=(
            starting_reference_title
        ),
        differences=differences,
        combinations=combinations,
        technical_problem_signals=(
            technical_problem_signals
        ),
        technical_effect_signals=(
            technical_effect_signals
        ),
        motivation_signals=(
            motivation_signals
        ),
        evidence_strength=round(
            evidence_strength,
            6,
        ),
        status=status,
        reasoning=reasoning,
        review_questions=review_questions,
    )


# ---------------------------------------------------------------------
# Full analyzer
# ---------------------------------------------------------------------

class InventiveStepAnalyzer:

    def __init__(
        self,
        max_candidate_references: int = 8,
    ):

        self.max_candidate_references = (
            max_candidate_references
        )

    def analyze(
        self,
        claims: Iterable[Any],
        evidence_analysis: Dict[str, Any],
        documents: Iterable[Any],
        specification_text: str = "",
    ) -> Dict[str, Any]:

        references = normalize_references(
            documents
        )

        evidence_claims = {}

        for item in evidence_analysis.get(
            "claims",
            [],
        ):

            if not isinstance(
                item,
                dict,
            ):
                continue

            try:

                claim_number = int(
                    item.get(
                        "claim_number",
                        1,
                    )
                )

            except Exception:

                continue

            evidence_claims[
                claim_number
            ] = normalize_evidence_claim(
                item
            )

        findings = []

        for index, raw_claim in enumerate(
            claims,
            start=1,
        ):

            claim = normalize_claim(
                raw_claim,
                index,
            )

            claim_number = (
                claim[
                    "claim_number"
                ]
            )

            evidence_claim = (
                evidence_claims.get(
                    claim_number
                )
            )

            if evidence_claim is None:

                evidence_claim = {
                    "claim_number":
                        claim_number,

                    "claim_text":
                        claim[
                            "text"
                        ],

                    "limitations":
                        claim[
                            "limitations"
                        ],
                }

            finding = (
                analyze_claim_inventive_step(
                    claim,
                    evidence_claim,
                    references,
                    specification_text,
                )
            )

            findings.append(
                finding
            )

        statistics = (
            calculate_inventive_step_statistics(
                findings
            )
        )

        return {
            "success":
                True,

            "inventive_step_analyzer_version":
                INVENTIVE_STEP_ANALYZER_VERSION,

            "generated_at":
                _utc_now(),

            "claims": [
                item.to_dict()
                for item
                in findings
            ],

            "statistics":
                statistics,

            "review_notice":
                (
                    "Inventive-step results are structured "
                    "screening signals. They do not constitute "
                    "a definitive legal conclusion regarding "
                    "obviousness or inventive step."
                ),
        }


# ---------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------

def calculate_inventive_step_statistics(
    findings: Iterable[Any],
) -> Dict[str, Any]:

    findings = list(
        findings
    )

    counts = {
        "LOW_DIFFERENCE_SIGNAL":
            0,

        "COMBINATION_REVIEW_SIGNAL":
            0,

        "DISTINGUISHING_FEATURE_SIGNAL":
            0,

        "INCONCLUSIVE":
            0,
    }

    for finding in findings:

        status = (
            finding.status
            if hasattr(
                finding,
                "status",
            )
            else finding.get(
                "status",
                "INCONCLUSIVE",
            )
        )

        if status not in counts:
            counts[
                "INCONCLUSIVE"
            ] += 1

        else:
            counts[
                status
            ] += 1

    if findings:

        average_strength = (
            sum(
                (
                    finding.evidence_strength
                    if hasattr(
                        finding,
                        "evidence_strength",
                    )
                    else _safe_float(
                        finding.get(
                            "evidence_strength",
                            0.0,
                        )
                    )
                )
                for finding
                in findings
            )
            / len(
                findings
            )
        )

    else:

        average_strength = 0.0

    return {
        "claim_count":
            len(findings),

        "low_difference_signals":
            counts[
                "LOW_DIFFERENCE_SIGNAL"
            ],

        "combination_review_signals":
            counts[
                "COMBINATION_REVIEW_SIGNAL"
            ],

        "distinguishing_feature_signals":
            counts[
                "DISTINGUISHING_FEATURE_SIGNAL"
            ],

        "inconclusive":
            counts[
                "INCONCLUSIVE"
            ],

        "average_evidence_strength":
            round(
                average_strength,
                6,
            ),
    }


# ---------------------------------------------------------------------
# Difference report
# ---------------------------------------------------------------------

def build_difference_report(
    claim_finding: Dict[str, Any],
) -> Dict[str, Any]:

    differences = []

    for difference in claim_finding.get(
        "differences",
        [],
    ):

        differences.append(
            {
                "limitation_id":
                    difference.get(
                        "limitation_id",
                        "",
                    ),

                "limitation":
                    difference.get(
                        "limitation_text",
                        "",
                    ),

                "best_reference":
                    difference.get(
                        "best_reference_id",
                        "",
                    ),

                "best_reference_score":
                    difference.get(
                        "best_reference_score",
                        0.0,
                    ),

                "status":
                    difference.get(
                        "difference_type",
                        "",
                    ),

                "technical_significance":
                    difference.get(
                        "technical_significance",
                        "",
                    ),
            }
        )

    return {
        "claim_number":
            claim_finding.get(
                "claim_number",
                1,
            ),

        "differences":
            differences,

        "technical_problem_signals":
            claim_finding.get(
                "technical_problem_signals",
                [],
            ),

        "technical_effect_signals":
            claim_finding.get(
                "technical_effect_signals",
                [],
            ),
    }


# ---------------------------------------------------------------------
# Combination report
# ---------------------------------------------------------------------

def rank_combinations(
    claim_finding: Dict[str, Any],
    top_k: int = 10,
) -> List[Dict[str, Any]]:

    combinations = []

    for combination in claim_finding.get(
        "combinations",
        [],
    ):

        if hasattr(
            combination,
            "to_dict",
        ):

            combination = (
                combination.to_dict()
            )

        if isinstance(
            combination,
            dict,
        ):

            combinations.append(
                combination
            )

    combinations.sort(
        key=lambda item: (
            _safe_float(
                item.get(
                    "coverage",
                    0.0,
                )
            ),
            _safe_float(
                item.get(
                    "complementarity",
                    0.0,
                )
            ),
            _safe_float(
                item.get(
                    "overlap",
                    0.0,
                )
            ),
        ),
        reverse=True,
    )

    for rank, item in enumerate(
        combinations[:top_k],
        start=1,
    ):

        item[
            "review_rank"
        ] = rank

    return combinations[
        :top_k
    ]


# ---------------------------------------------------------------------
# Hindsight / caution signals
# ---------------------------------------------------------------------

def detect_hindsight_risk(
    claim_text: str,
    combination: Dict[str, Any],
) -> Dict[str, Any]:

    # This does not determine hindsight. It identifies situations
    # where a reviewer should be especially careful.

    missing = combination.get(
        "missing_limitation_ids",
        [],
    )

    complementarity = _safe_float(
        combination.get(
            "complementarity",
            0.0,
        )
    )

    overlap = _safe_float(
        combination.get(
            "overlap",
            0.0,
        )
    )

    signals = []

    if missing:

        signals.append(
            "combination_requires_feature_mapping"
        )

    if complementarity > 0.60:

        signals.append(
            "references_contribute_distinct_feature_sets"
        )

    if overlap < 0.20:

        signals.append(
            "limited_overlap_between_references"
        )

    return {
        "signals":
            signals,

        "review_required":
            bool(signals),

        "note":
            (
                "Combining technically distinct references "
                "requires a separate analysis of whether the "
                "combination would have been apparent to the "
                "skilled person without hindsight."
            ),
    }


# ---------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------

def summarize_inventive_step(
    analysis: Dict[str, Any],
) -> str:

    statistics = analysis.get(
        "statistics",
        {},
    )

    claims = statistics.get(
        "claim_count",
        0,
    )

    combinations = statistics.get(
        "combination_review_signals",
        0,
    )

    differences = statistics.get(
        "distinguishing_feature_signals",
        0,
    )

    return (
        f"Inventive-step screening analyzed {claims} claim(s). "
        f"{differences} claim(s) contain distinguishing-feature "
        f"signals and {combinations} contain reference-combination "
        f"signals requiring further technical and legal review."
    )


# ---------------------------------------------------------------------
# Convenience API
# ---------------------------------------------------------------------

def analyze_inventive_step(
    claims: Iterable[Any],
    evidence_analysis: Dict[str, Any],
    documents: Iterable[Any],
    specification_text: str = "",
) -> Dict[str, Any]:

    analyzer = (
        InventiveStepAnalyzer()
    )

    return analyzer.analyze(
        claims=claims,
        evidence_analysis=evidence_analysis,
        documents=documents,
        specification_text=specification_text,
    )


def screen_inventive_step(
    claims: Iterable[Any],
    evidence_analysis: Dict[str, Any],
    documents: Iterable[Any],
    specification_text: str = "",
) -> Dict[str, Any]:

    return analyze_inventive_step(
        claims,
        evidence_analysis,
        documents,
        specification_text,
    )


# ---------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------

def check_inventive_step(
    claims: Iterable[Any],
    evidence_analysis: Dict[str, Any],
    documents: Iterable[Any],
    specification_text: str = "",
) -> Dict[str, Any]:

    return analyze_inventive_step(
        claims,
        evidence_analysis,
        documents,
        specification_text,
    )


def analyze_obviousness(
    claims: Iterable[Any],
    evidence_analysis: Dict[str, Any],
    documents: Iterable[Any],
    specification_text: str = "",
) -> Dict[str, Any]:

    return analyze_inventive_step(
        claims,
        evidence_analysis,
        documents,
        specification_text,
    )


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

__all__ = [
    "INVENTIVE_STEP_ANALYZER_VERSION",
    "FeatureDifference",
    "ReferenceCombination",
    "InventiveStepFinding",
    "InventiveStepAnalyzer",
    "normalize_claim",
    "normalize_evidence_claim",
    "normalize_references",
    "lexical_similarity",
    "overlap_terms",
    "find_limitation_evidence",
    "build_feature_difference",
    "identify_technical_relationship",
    "extract_technical_problem_signals",
    "extract_technical_effect_signals",
    "detect_motivation_signals",
    "calculate_motivation_score",
    "build_reference_combination",
    "select_candidate_references",
    "analyze_claim_inventive_step",
    "calculate_inventive_step_statistics",
    "build_difference_report",
    "rank_combinations",
    "detect_hindsight_risk",
    "summarize_inventive_step",
    "analyze_inventive_step",
    "screen_inventive_step",
    "check_inventive_step",
    "analyze_obviousness",
]
