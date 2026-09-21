"""
Patent Amendment Intelligence Engine V3
========================================

Purpose
-------
Compare different versions of patent claims and identify:

    - Added claims
    - Deleted claims
    - Modified claims
    - Unchanged claims
    - Added limitations
    - Removed limitations
    - Modified limitations
    - Claim renumbering
    - Dependency changes
    - Claim-category changes
    - Potential support-review items

Architecture
------------
Original Claims
       |
       v
Claim Normalization
       |
       v
Claim-to-Claim Matching
       |
       v
Text / Limitation Diff
       |
       v
Amendment Map
       |
       v
Support Mapping
       |
       v
Human Review

Important
---------
This module identifies textual and structural changes.

It does NOT determine whether an amendment is legally allowable,
whether it adds new matter, or whether it complies with Section 59.

Those are legal determinations requiring professional review.

Version
-------
3.0.0
"""

from __future__ import annotations

import difflib
import hashlib
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple


AMENDMENT_ANALYZER_VERSION = "3.0.0"


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


def _normalize_text(value: Any) -> str:
    text = _clean(value).lower()

    text = re.sub(
        r"[^\w\s\-\.%\/]",
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


def _unique(
    values: Iterable[Any],
) -> List[Any]:

    result = []
    seen = set()

    for value in values:

        key = str(value).strip().lower()

        if not key or key in seen:
            continue

        seen.add(key)
        result.append(value)

    return result


def _as_list(
    value: Any,
) -> List[Any]:

    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


# ---------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------

@dataclass
class LimitationChange:

    change_id: str
    change_type: str
    old_text: str
    new_text: str
    old_limitation_id: str = ""
    new_limitation_id: str = ""
    similarity: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ClaimAmendment:

    amendment_id: str
    old_claim_number: Optional[int]
    new_claim_number: Optional[int]
    change_type: str
    old_text: str
    new_text: str
    similarity: float
    old_claim_type: str = ""
    new_claim_type: str = ""
    old_category: str = ""
    new_category: str = ""
    old_dependencies: List[int] | None = None
    new_dependencies: List[int] | None = None
    limitation_changes: List[Dict[str, Any]] | None = None
    review_flags: List[str] | None = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AmendmentComparison:

    comparison_id: str
    compared_at: str
    old_version: str
    new_version: str
    unchanged_claims: List[int]
    added_claims: List[int]
    deleted_claims: List[int]
    modified_claims: List[int]
    renumbered_claims: List[Dict[str, Any]]
    claim_changes: List[Dict[str, Any]]
    statistics: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


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

            "claim_type":
                "",

            "category":
                "",

            "dependencies":
                [],

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

            "claim_type":
                "",

            "category":
                "",

            "dependencies":
                [],

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

    try:
        if number is not None:
            number = int(number)
    except Exception:
        pass

    dependencies = claim.get(
        "dependencies",
        claim.get(
            "depends_on",
            [],
        ),
    )

    normalized_dependencies = []

    for dependency in _as_list(
        dependencies
    ):

        try:
            normalized_dependencies.append(
                int(dependency)
            )
        except Exception:
            pass

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

            limitation_text = _clean(
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

            limitation_text = _clean(
                limitation
            )

            limitation_id = ""

            limitation_type = ""

        if not limitation_id:

            limitation_id = _stable_id(
                "L",
                f"{number}|{index}|{limitation_text}",
            )

        limitations.append(
            {
                "id":
                    limitation_id,

                "text":
                    limitation_text,

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

        "claim_type":
            _clean(
                claim.get(
                    "claim_type",
                    claim.get(
                        "type",
                        "",
                    ),
                )
            ),

        "category":
            _clean(
                claim.get(
                    "category",
                    claim.get(
                        "claim_category",
                        "",
                    ),
                )
            ),

        "dependencies":
            sorted(
                set(
                    normalized_dependencies
                )
            ),

        "limitations":
            limitations,
    }


def normalize_claims(
    claims: Iterable[Any],
) -> List[Dict[str, Any]]:

    result = []

    for index, claim in enumerate(
        claims,
        start=1,
    ):

        result.append(
            normalize_claim(
                claim,
                fallback_number=index,
            )
        )

    return result


# ---------------------------------------------------------------------
# Text similarity
# ---------------------------------------------------------------------

def text_similarity(
    text_a: str,
    text_b: str,
) -> float:

    a = _normalize_text(text_a)
    b = _normalize_text(text_b)

    if not a or not b:
        return 0.0

    return round(
        difflib.SequenceMatcher(
            None,
            a,
            b,
        ).ratio(),
        4,
    )


def token_similarity(
    text_a: str,
    text_b: str,
) -> float:

    a = set(
        _normalize_text(
            text_a
        ).split()
    )

    b = set(
        _normalize_text(
            text_b
        ).split()
    )

    if not a or not b:
        return 0.0

    intersection = len(
        a.intersection(b)
    )

    union = len(
        a.union(b)
    )

    if union == 0:
        return 0.0

    return round(
        intersection / union,
        4,
    )


# ---------------------------------------------------------------------
# Claim matching
# ---------------------------------------------------------------------

def _claim_match_score(
    old_claim: Dict[str, Any],
    new_claim: Dict[str, Any],
) -> float:

    text_score = text_similarity(
        old_claim.get(
            "text",
            "",
        ),
        new_claim.get(
            "text",
            "",
        ),
    )

    token_score = token_similarity(
        old_claim.get(
            "text",
            "",
        ),
        new_claim.get(
            "text",
            "",
        ),
    )

    old_limitations = " ".join(
        item.get(
            "text",
            "",
        )
        for item in old_claim.get(
            "limitations",
            [],
        )
        if isinstance(
            item,
            dict,
        )
    )

    new_limitations = " ".join(
        item.get(
            "text",
            "",
        )
        for item in new_claim.get(
            "limitations",
            [],
        )
        if isinstance(
            item,
            dict,
        )
    )

    limitation_score = text_similarity(
        old_limitations,
        new_limitations,
    )

    score = (
        0.55 * text_score
        + 0.25 * token_score
        + 0.20 * limitation_score
    )

    return round(
        score,
        4,
    )


def match_claim_versions(
    old_claims: List[Dict[str, Any]],
    new_claims: List[Dict[str, Any]],
    threshold: float = 0.55,
) -> List[Dict[str, Any]]:

    matches = []

    used_old = set()
    used_new = set()

    candidates = []

    for old_index, old_claim in enumerate(
        old_claims
    ):

        for new_index, new_claim in enumerate(
            new_claims
        ):

            score = _claim_match_score(
                old_claim,
                new_claim,
            )

            candidates.append(
                (
                    score,
                    old_index,
                    new_index,
                )
            )

    candidates.sort(
        reverse=True
    )

    for score, old_index, new_index in candidates:

        if score < threshold:
            continue

        if old_index in used_old:
            continue

        if new_index in used_new:
            continue

        used_old.add(
            old_index
        )

        used_new.add(
            new_index
        )

        matches.append(
            {
                "old_index":
                    old_index,

                "new_index":
                    new_index,

                "score":
                    score,

                "old_claim":
                    old_claims[
                        old_index
                    ],

                "new_claim":
                    new_claims[
                        new_index
                    ],
            }
        )

    return matches


# ---------------------------------------------------------------------
# Limitation extraction
# ---------------------------------------------------------------------

def _get_limitation_texts(
    claim: Dict[str, Any],
) -> List[Dict[str, Any]]:

    limitations = []

    for limitation in _as_list(
        claim.get(
            "limitations",
            [],
        )
    ):

        if isinstance(
            limitation,
            dict,
        ):

            limitations.append(
                {
                    "id":
                        _clean(
                            limitation.get(
                                "id",
                                limitation.get(
                                    "limitation_id",
                                    "",
                                ),
                            )
                        ),

                    "text":
                        _clean(
                            limitation.get(
                                "text",
                                limitation.get(
                                    "limitation_text",
                                    "",
                                ),
                            )
                        ),

                    "type":
                        _clean(
                            limitation.get(
                                "type",
                                limitation.get(
                                    "limitation_type",
                                    "",
                                ),
                            )
                        ),
                }
            )

        else:

            limitations.append(
                {
                    "id": "",
                    "text":
                        _clean(
                            limitation
                        ),
                    "type": "",
                }
            )

    return [
        item
        for item in limitations
        if item["text"]
    ]


# ---------------------------------------------------------------------
# Limitation matching
# ---------------------------------------------------------------------

def compare_limitations(
    old_claim: Dict[str, Any],
    new_claim: Dict[str, Any],
) -> List[LimitationChange]:

    old_limits = _get_limitation_texts(
        old_claim
    )

    new_limits = _get_limitation_texts(
        new_claim
    )

    changes: List[
        LimitationChange
    ] = []

    if not old_limits and not new_limits:
        return changes

    candidates = []

    for old_index, old_limitation in enumerate(
        old_limits
    ):

        for new_index, new_limitation in enumerate(
            new_limits
        ):

            sequence_score = text_similarity(
                old_limitation["text"],
                new_limitation["text"],
            )

            token_score = token_similarity(
                old_limitation["text"],
                new_limitation["text"],
            )

            score = (
                0.65 * sequence_score
                + 0.35 * token_score
            )

            candidates.append(
                (
                    score,
                    old_index,
                    new_index,
                )
            )

    candidates.sort(
        reverse=True
    )

    used_old = set()
    used_new = set()

    for score, old_index, new_index in candidates:

        if old_index in used_old:
            continue

        if new_index in used_new:
            continue

        old_limitation = old_limits[
            old_index
        ]

        new_limitation = new_limits[
            new_index
        ]

        # Strong match = same limitation
        if score >= 0.90:

            used_old.add(
                old_index
            )

            used_new.add(
                new_index
            )

            changes.append(
                LimitationChange(
                    change_id=_stable_id(
                        "LC",
                        old_limitation["text"]
                        + "|"
                        + new_limitation["text"],
                    ),
                    change_type="unchanged",
                    old_text=old_limitation["text"],
                    new_text=new_limitation["text"],
                    old_limitation_id=old_limitation["id"],
                    new_limitation_id=new_limitation["id"],
                    similarity=score,
                )
            )

        # Medium match = modified
        elif score >= 0.45:

            used_old.add(
                old_index
            )

            used_new.add(
                new_index
            )

            changes.append(
                LimitationChange(
                    change_id=_stable_id(
                        "LC",
                        old_limitation["text"]
                        + "|"
                        + new_limitation["text"],
                    ),
                    change_type="modified",
                    old_text=old_limitation["text"],
                    new_text=new_limitation["text"],
                    old_limitation_id=old_limitation["id"],
                    new_limitation_id=new_limitation["id"],
                    similarity=score,
                )
            )

    # Removed limitations

    for old_index, limitation in enumerate(
        old_limits
    ):

        if old_index in used_old:
            continue

        changes.append(
            LimitationChange(
                change_id=_stable_id(
                    "LC-DEL",
                    limitation["text"],
                ),
                change_type="removed",
                old_text=limitation["text"],
                new_text="",
                old_limitation_id=limitation["id"],
                new_limitation_id="",
                similarity=0.0,
            )
        )

    # Added limitations

    for new_index, limitation in enumerate(
        new_limits
    ):

        if new_index in used_new:
            continue

        changes.append(
            LimitationChange(
                change_id=_stable_id(
                    "LC-ADD",
                    limitation["text"],
                ),
                change_type="added",
                old_text="",
                new_text=limitation["text"],
                old_limitation_id="",
                new_limitation_id=limitation["id"],
                similarity=0.0,
            )
        )

    return changes


# ---------------------------------------------------------------------
# Word-level diff
# ---------------------------------------------------------------------

def word_diff(
    old_text: str,
    new_text: str,
) -> List[Dict[str, Any]]:

    old_words = _clean(
        old_text
    ).split()

    new_words = _clean(
        new_text
    ).split()

    matcher = difflib.SequenceMatcher(
        None,
        old_words,
        new_words,
    )

    result = []

    for tag, i1, i2, j1, j2 in matcher.get_opcodes():

        if tag == "equal":

            continue

        result.append(
            {
                "operation":
                    tag,

                "old_text":
                    " ".join(
                        old_words[i1:i2]
                    ),

                "new_text":
                    " ".join(
                        new_words[j1:j2]
                    ),
            }
        )

    return result


# ---------------------------------------------------------------------
# Claim amendment classification
# ---------------------------------------------------------------------

def classify_claim_change(
    old_claim: Dict[str, Any],
    new_claim: Dict[str, Any],
    similarity: float,
    limitation_changes: List[LimitationChange],
) -> str:

    old_text = _normalize_text(
        old_claim.get(
            "text",
            "",
        )
    )

    new_text = _normalize_text(
        new_claim.get(
            "text",
            "",
        )
    )

    if old_text == new_text:

        if (
            old_claim.get(
                "dependencies",
                [],
            )
            ==
            new_claim.get(
                "dependencies",
                [],
            )
        ):
            return "unchanged"

    if (
        old_claim.get(
            "claim_type",
            "",
        ).lower()
        !=
        new_claim.get(
            "claim_type",
            "",
        ).lower()
    ):
        return "modified"

    if (
        old_claim.get(
            "category",
            "",
        ).lower()
        !=
        new_claim.get(
            "category",
            "",
        ).lower()
    ):
        return "modified"

    change_types = {
        item.change_type
        for item in limitation_changes
    }

    if "added" in change_types:
        return "modified"

    if "removed" in change_types:
        return "modified"

    if "modified" in change_types:
        return "modified"

    if similarity >= 0.95:
        return "unchanged"

    return "modified"


# ---------------------------------------------------------------------
# Review flags
# ---------------------------------------------------------------------

def generate_review_flags(
    old_claim: Dict[str, Any],
    new_claim: Dict[str, Any],
    limitation_changes: List[LimitationChange],
) -> List[str]:

    flags = []

    change_types = {
        item.change_type
        for item in limitation_changes
    }

    if "added" in change_types:

        flags.append(
            "New limitation(s) detected; "
            "map each added limitation to the "
            "original disclosure for human review."
        )

    if "removed" in change_types:

        flags.append(
            "Limitation(s) removed; review the "
            "effect on claim scope and dependencies."
        )

    if "modified" in change_types:

        flags.append(
            "Existing limitation language changed; "
            "verify technical meaning and specification support."
        )

    old_dependencies = old_claim.get(
        "dependencies",
        [],
    )

    new_dependencies = new_claim.get(
        "dependencies",
        [],
    )

    if old_dependencies != new_dependencies:

        flags.append(
            "Claim dependency changed; "
            "review resulting claim structure."
        )

    if (
        old_claim.get(
            "category",
            "",
        ).lower()
        !=
        new_claim.get(
            "category",
            "",
        ).lower()
    ):

        flags.append(
            "Claim category changed; "
            "verify intended claim scope."
        )

    if (
        old_claim.get(
            "claim_type",
            "",
        ).lower()
        !=
        new_claim.get(
            "claim_type",
            "",
        ).lower()
    ):

        flags.append(
            "Claim type changed; "
            "review structural and prosecution implications."
        )

    return flags


# ---------------------------------------------------------------------
# Individual claim comparison
# ---------------------------------------------------------------------

def compare_claim(
    old_claim: Dict[str, Any],
    new_claim: Dict[str, Any],
    similarity: Optional[float] = None,
) -> ClaimAmendment:

    if similarity is None:

        similarity = _claim_match_score(
            old_claim,
            new_claim,
        )

    limitation_changes = (
        compare_limitations(
            old_claim,
            new_claim,
        )
    )

    change_type = classify_claim_change(
        old_claim,
        new_claim,
        similarity,
        limitation_changes,
    )

    flags = generate_review_flags(
        old_claim,
        new_claim,
        limitation_changes,
    )

    return ClaimAmendment(
        amendment_id=_stable_id(
            "AM",
            str(
                old_claim.get(
                    "claim_number",
                    "",
                )
            )
            + "|"
            + str(
                new_claim.get(
                    "claim_number",
                    "",
                )
            )
            + "|"
            + old_claim.get(
                "text",
                "",
            )
            + "|"
            + new_claim.get(
                "text",
                "",
            ),
        ),
        old_claim_number=old_claim.get(
            "claim_number"
        ),
        new_claim_number=new_claim.get(
            "claim_number"
        ),
        change_type=change_type,
        old_text=old_claim.get(
            "text",
            "",
        ),
        new_text=new_claim.get(
            "text",
            "",
        ),
        similarity=similarity,
        old_claim_type=old_claim.get(
            "claim_type",
            "",
        ),
        new_claim_type=new_claim.get(
            "claim_type",
            "",
        ),
        old_category=old_claim.get(
            "category",
            "",
        ),
        new_category=new_claim.get(
            "category",
            "",
        ),
        old_dependencies=old_claim.get(
            "dependencies",
            [],
        ),
        new_dependencies=new_claim.get(
            "dependencies",
            [],
        ),
        limitation_changes=[
            item.to_dict()
            for item in limitation_changes
        ],
        review_flags=flags,
    )


# ---------------------------------------------------------------------
# Main comparison
# ---------------------------------------------------------------------

def compare_claim_versions(
    old_claims: Iterable[Any],
    new_claims: Iterable[Any],
    *,
    old_version: str = "original",
    new_version: str = "amended",
    match_threshold: float = 0.55,
) -> Dict[str, Any]:

    old_normalized = normalize_claims(
        old_claims
    )

    new_normalized = normalize_claims(
        new_claims
    )

    matches = match_claim_versions(
        old_normalized,
        new_normalized,
        threshold=match_threshold,
    )

    matched_old = {
        item["old_index"]
        for item in matches
    }

    matched_new = {
        item["new_index"]
        for item in matches
    }

    claim_changes = []

    unchanged_claims = []

    modified_claims = []

    added_claims = []

    deleted_claims = []

    renumbered_claims = []

    # Matched claims

    for match in matches:

        old_claim = match[
            "old_claim"
        ]

        new_claim = match[
            "new_claim"
        ]

        comparison = compare_claim(
            old_claim,
            new_claim,
            similarity=match["score"],
        )

        claim_changes.append(
            comparison.to_dict()
        )

        old_number = old_claim.get(
            "claim_number"
        )

        new_number = new_claim.get(
            "claim_number"
        )

        if (
            old_number is not None
            and new_number is not None
            and old_number != new_number
        ):

            renumbered_claims.append(
                {
                    "old_claim_number":
                        old_number,

                    "new_claim_number":
                        new_number,

                    "similarity":
                        match["score"],
                }
            )

        if (
            comparison.change_type
            == "unchanged"
        ):

            if old_number is not None:
                unchanged_claims.append(
                    old_number
                )

        else:

            if new_number is not None:
                modified_claims.append(
                    new_number
                )

    # Added claims

    for index, claim in enumerate(
        new_normalized
    ):

        if index in matched_new:
            continue

        number = claim.get(
            "claim_number"
        )

        if number is not None:

            added_claims.append(
                number
            )

        claim_changes.append(
            ClaimAmendment(
                amendment_id=_stable_id(
                    "AM-ADD",
                    claim.get(
                        "text",
                        "",
                    ),
                ),
                old_claim_number=None,
                new_claim_number=number,
                change_type="added",
                old_text="",
                new_text=claim.get(
                    "text",
                    "",
                ),
                similarity=0.0,
                new_claim_type=claim.get(
                    "claim_type",
                    "",
                ),
                new_category=claim.get(
                    "category",
                    "",
                ),
                new_dependencies=claim.get(
                    "dependencies",
                    [],
                ),
                limitation_changes=[
                    LimitationChange(
                        change_id=_stable_id(
                            "LC-ADD",
                            item.get(
                                "text",
                                "",
                            ),
                        ),
                        change_type="added",
                        old_text="",
                        new_text=item.get(
                            "text",
                            "",
                        ),
                        new_limitation_id=item.get(
                            "id",
                            "",
                        ),
                        similarity=0.0,
                    ).to_dict()
                    for item in claim.get(
                        "limitations",
                        [],
                    )
                ],
                review_flags=[
                    "New claim detected; "
                    "map the complete claim to "
                    "the relevant original disclosure."
                ],
            ).to_dict()
        )

    # Deleted claims

    for index, claim in enumerate(
        old_normalized
    ):

        if index in matched_old:
            continue

        number = claim.get(
            "claim_number"
        )

        if number is not None:

            deleted_claims.append(
                number
            )

        claim_changes.append(
            ClaimAmendment(
                amendment_id=_stable_id(
                    "AM-DEL",
                    claim.get(
                        "text",
                        "",
                    ),
                ),
                old_claim_number=number,
                new_claim_number=None,
                change_type="deleted",
                old_text=claim.get(
                    "text",
                    "",
                ),
                new_text="",
                similarity=0.0,
                old_claim_type=claim.get(
                    "claim_type",
                    "",
                ),
                old_category=claim.get(
                    "category",
                    "",
                ),
                old_dependencies=claim.get(
                    "dependencies",
                    [],
                ),
                limitation_changes=[
                    LimitationChange(
                        change_id=_stable_id(
                            "LC-DEL",
                            item.get(
                                "text",
                                "",
                            ),
                        ),
                        change_type="removed",
                        old_text=item.get(
                            "text",
                            "",
                        ),
                        new_text="",
                        old_limitation_id=item.get(
                            "id",
                            "",
                        ),
                        similarity=0.0,
                    ).to_dict()
                    for item in claim.get(
                        "limitations",
                        [],
                    )
                ],
                review_flags=[
                    "Claim removed from the compared version."
                ],
            ).to_dict()
        )

    unchanged_claims = sorted(
        set(
            unchanged_claims
        )
    )

    modified_claims = sorted(
        set(
            modified_claims
        )
    )

    added_claims = sorted(
        set(
            added_claims
        )
    )

    deleted_claims = sorted(
        set(
            deleted_claims
        )
    )

    comparison_id = _stable_id(
        "CMP",
        old_version
        + "|"
        + new_version
        + "|"
        + str(
            old_normalized
        )
        + "|"
        + str(
            new_normalized
        ),
    )

    comparison = AmendmentComparison(
        comparison_id=comparison_id,
        compared_at=_utc_now(),
        old_version=old_version,
        new_version=new_version,
        unchanged_claims=unchanged_claims,
        added_claims=added_claims,
        deleted_claims=deleted_claims,
        modified_claims=modified_claims,
        renumbered_claims=renumbered_claims,
        claim_changes=claim_changes,
        statistics={
            "old_claim_count":
                len(old_normalized),

            "new_claim_count":
                len(new_normalized),

            "unchanged_count":
                len(unchanged_claims),

            "modified_count":
                len(modified_claims),

            "added_count":
                len(added_claims),

            "deleted_count":
                len(deleted_claims),

            "renumbered_count":
                len(renumbered_claims),
        },
    )

    return comparison.to_dict()


# ---------------------------------------------------------------------
# Section 59 review map
# ---------------------------------------------------------------------

def build_amendment_review_map(
    comparison: Dict[str, Any],
) -> Dict[str, Any]:

    """
    Build a review-oriented map for amendment analysis.

    This does NOT determine Section 59 compliance.

    It highlights where a human reviewer should examine:

        - added matter
        - deleted matter
        - modified language
        - dependencies
        - claim restructuring
    """

    claim_changes = _as_list(
        comparison.get(
            "claim_changes",
            [],
        )
    )

    review_items = []

    for change in claim_changes:

        if not isinstance(
            change,
            dict,
        ):
            continue

        change_type = change.get(
            "change_type",
            "",
        )

        flags = _as_list(
            change.get(
                "review_flags",
                [],
            )
        )

        limitations = _as_list(
            change.get(
                "limitation_changes",
                [],
            )
        )

        added_limitations = [
            item
            for item in limitations
            if isinstance(
                item,
                dict,
            )
            and item.get(
                "change_type"
            ) == "added"
        ]

        modified_limitations = [
            item
            for item in limitations
            if isinstance(
                item,
                dict,
            )
            and item.get(
                "change_type"
            ) == "modified"
        ]

        removed_limitations = [
            item
            for item in limitations
            if isinstance(
                item,
                dict,
            )
            and item.get(
                "change_type"
            ) == "removed"
        ]

        if (
            change_type
            in {
                "added",
                "modified",
            }
            or added_limitations
            or modified_limitations
        ):

            review_items.append(
                {
                    "amendment_id":
                        change.get(
                            "amendment_id",
                            "",
                        ),

                    "old_claim":
                        change.get(
                            "old_claim_number",
                        ),

                    "new_claim":
                        change.get(
                            "new_claim_number",
                        ),

                    "review_type":
                        "SUPPORT_MAPPING",

                    "added_limitations":
                        len(
                            added_limitations
                        ),

                    "modified_limitations":
                        len(
                            modified_limitations
                        ),

                    "removed_limitations":
                        len(
                            removed_limitations
                        ),

                    "review_flags":
                        flags,

                    "status":
                        "REVIEW_REQUIRED",
                }
            )

    return {
        "comparison_id":
            comparison.get(
                "comparison_id",
                "",
            ),

        "review_items":
            review_items,

        "review_count":
            len(review_items),

        "notice":
            (
                "This map identifies amendments requiring "
                "support review. It does not determine "
                "whether an amendment adds new matter or "
                "satisfies any statutory requirement."
            ),
    }


# ---------------------------------------------------------------------
# Support mapping
# ---------------------------------------------------------------------

def map_added_limitations_to_evidence(
    comparison: Dict[str, Any],
    evidence: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    """
    Lightweight deterministic support search.

    This is intentionally conservative.

    It searches added/modified limitations against supplied evidence
    using token overlap. It does not establish legal support.
    """

    evidence_items = [
        item
        for item in _as_list(
            evidence
        )
        if isinstance(
            item,
            dict,
        )
    ]

    results = []

    for claim_change in _as_list(
        comparison.get(
            "claim_changes",
            [],
        )
    ):

        if not isinstance(
            claim_change,
            dict,
        ):
            continue

        for limitation in _as_list(
            claim_change.get(
                "limitation_changes",
                [],
            )
        ):

            if not isinstance(
                limitation,
                dict,
            ):
                continue

            if limitation.get(
                "change_type"
            ) not in {
                "added",
                "modified",
            }:
                continue

            limitation_text = limitation.get(
                "new_text",
                "",
            )

            candidates = []

            for evidence_item in evidence_items:

                evidence_text = _clean(
                    evidence_item.get(
                        "text",
                        evidence_item.get(
                            "content",
                            "",
                        ),
                    )
                )

                score = token_similarity(
                    limitation_text,
                    evidence_text,
                )

                if score >= 0.15:

                    candidates.append(
                        {
                            "evidence_id":
                                evidence_item.get(
                                    "evidence_id",
                                    evidence_item.get(
                                        "id",
                                        "",
                                    ),
                                ),

                            "score":
                                score,

                            "text":
                                evidence_text,
                        }
                    )

            candidates.sort(
                key=lambda item:
                    item["score"],
                reverse=True,
            )

            results.append(
                {
                    "amendment_id":
                        claim_change.get(
                            "amendment_id",
                            "",
                        ),

                    "limitation_id":
                        limitation.get(
                            "new_limitation_id",
                            "",
                        ),

                    "limitation_text":
                        limitation_text,

                    "evidence_candidates":
                        candidates[:10],

                    "status":
                        (
                            "CANDIDATE_SUPPORT_FOUND"
                            if candidates
                            else
                            "NO_CANDIDATE_SUPPORT"
                        ),
                }
            )

    return results


# ---------------------------------------------------------------------
# Human-readable summary
# ---------------------------------------------------------------------

def summarize_amendments(
    comparison: Dict[str, Any],
) -> str:

    stats = comparison.get(
        "statistics",
        {},
    )

    return (
        f"Compared {stats.get('old_claim_count', 0)} "
        f"claims in '{comparison.get('old_version', '')}' "
        f"with {stats.get('new_claim_count', 0)} claims in "
        f"'{comparison.get('new_version', '')}'. "
        f"Detected {stats.get('modified_count', 0)} "
        f"modified claim(s), "
        f"{stats.get('added_count', 0)} added claim(s), "
        f"{stats.get('deleted_count', 0)} deleted claim(s), "
        f"and {stats.get('renumbered_count', 0)} "
        f"potential renumbering event(s). "
        "Changes requiring support review should be checked "
        "against the original disclosure."
    )


# ---------------------------------------------------------------------
# Backward-compatible functions
# ---------------------------------------------------------------------

def analyze_amendments(
    old_claims: Iterable[Any],
    new_claims: Iterable[Any],
    old_version: str = "original",
    new_version: str = "amended",
) -> Dict[str, Any]:

    return compare_claim_versions(
        old_claims,
        new_claims,
        old_version=old_version,
        new_version=new_version,
    )


def compare_claims(
    old_claim: Any,
    new_claim: Any,
) -> Dict[str, Any]:

    old_normalized = normalize_claim(
        old_claim
    )

    new_normalized = normalize_claim(
        new_claim
    )

    return compare_claim(
        old_normalized,
        new_normalized,
    ).to_dict()


def diff_claim_text(
    old_text: str,
    new_text: str,
) -> List[Dict[str, Any]]:

    return word_diff(
        old_text,
        new_text,
    )


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

__all__ = [
    "AMENDMENT_ANALYZER_VERSION",
    "LimitationChange",
    "ClaimAmendment",
    "AmendmentComparison",
    "normalize_claim",
    "normalize_claims",
    "text_similarity",
    "token_similarity",
    "match_claim_versions",
    "compare_limitations",
    "word_diff",
    "compare_claim",
    "compare_claim_versions",
    "build_amendment_review_map",
    "map_added_limitations_to_evidence",
    "summarize_amendments",
    "analyze_amendments",
    "compare_claims",
    "diff_claim_text",
]
