"""
FER / Prosecution Intelligence Engine V3
=========================================

Purpose
-------
Analyze Indian patent First Examination Reports (FERs), examination
reports, office objections, and prosecution correspondence.

Architecture
------------
FER text
   ↓
Deterministic extraction
   ↓
Objections
   ↓
Claims / sections / citations / deadlines
   ↓
Response mapping
   ↓
Optional Gemini explanation
   ↓
Human-reviewable prosecution intelligence

Important
---------
This module does NOT provide a legal opinion.

It extracts and organizes information from the supplied document and
creates review signals. Legal interpretation must be verified by a
qualified patent professional.

Version
-------
3.0.0
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Tuple


FER_ANALYZER_VERSION = "3.0.0"


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def _stable_id(
    prefix: str,
    text: str,
) -> str:

    digest = hashlib.sha256(
        _clean_text(text).encode(
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
class FERObjection:

    objection_id: str
    category: str
    title: str
    text: str
    claims: List[int]
    statutory_sections: List[str]
    cited_documents: List[str]
    confidence: float = 0.80

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FERCitation:

    citation_id: str
    reference: str
    context: str = ""
    citation_type: str = "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FERDeadline:

    deadline_id: str
    date_text: str
    context: str
    confidence: float = 0.70

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class FERAction:

    action_id: str
    action: str
    related_objection_id: str = ""
    claims: List[int] | None = None
    priority: str = "review"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------
# Category patterns
# ---------------------------------------------------------------------

OBJECTION_PATTERNS: Dict[str, List[str]] = {

    "novelty": [
        "not novel",
        "lack of novelty",
        "novelty",
        "newness",
        "anticipated by",
        "anticipated under",
    ],

    "inventive_step": [
        "inventive step",
        "lack of inventive step",
        "obvious",
        "obviousness",
        "obvious to a person skilled",
        "does not involve an inventive step",
    ],

    "section_3": [
        "section 3",
        "section 3(a)",
        "section 3(b)",
        "section 3(c)",
        "section 3(d)",
        "section 3(e)",
        "section 3(f)",
        "section 3(g)",
        "section 3(h)",
        "section 3(i)",
        "section 3(j)",
        "section 3(k)",
        "section 3(l)",
        "section 3(m)",
        "section 3(n)",
        "section 3(o)",
        "section 3(p)",
    ],

    "clarity": [
        "clarity",
        "clear",
        "unclear",
        "ambiguous",
        "indefinite",
        "lack of clarity",
        "clear and concise",
    ],

    "support": [
        "supported by the description",
        "support in the description",
        "lack of support",
        "not supported",
        "support",
    ],

    "sufficiency": [
        "sufficiency",
        "insufficient disclosure",
        "sufficiently disclose",
        "enabling disclosure",
        "enablement",
        "complete specification",
    ],

    "unity": [
        "unity of invention",
        "lack of unity",
        "unity",
    ],

    "amendment": [
        "amendment",
        "amended claims",
        "amend the claims",
        "amendments",
        "amended specification",
    ],

    "formal": [
        "formal requirements",
        "formality",
        "formal objection",
        "prescribed form",
        "requirements of the act",
    ],

    "drawings": [
        "drawings",
        "figure",
        "figures",
        "reference numerals",
    ],

    "sequence": [
        "sequence listing",
        "sequence",
        "nucleotide",
        "amino acid",
    ],

    "abstract": [
        "abstract",
    ],

    "title": [
        "title of the invention",
    ],
}


SECTION_PATTERN = re.compile(
    r"\b(?:section|sec\.?)\s*"
    r"(3\s*\([a-p]\)|10|57|59|11|13|14|15|21|25|53|54|55)"
    r"\b",
    flags=re.IGNORECASE,
)


CLAIM_PATTERN = re.compile(
    r"\bclaims?\s*"
    r"(?:nos?\.?|numbers?)?\s*"
    r"((?:\d+\s*(?:-|–|to)\s*)?\d+(?:\s*,\s*\d+)*)",
    flags=re.IGNORECASE,
)


CLAIM_RANGE_PATTERN = re.compile(
    r"\b(?:claims?|claim nos?\.?)\s*"
    r"(\d+)\s*(?:-|–|to)\s*(\d+)",
    flags=re.IGNORECASE,
)


PATENT_NUMBER_PATTERNS = [

    re.compile(
        r"\b(?:IN|Indian)?\s*"
        r"\d{5,12}\b",
        flags=re.IGNORECASE,
    ),

    re.compile(
        r"\b[A-Z]{2}\d{4,}"
        r"(?:[A-Z]\d?)?\b",
        flags=re.IGNORECASE,
    ),

    re.compile(
        r"\bWO\s*\d{4}/\d{4,}\b",
        flags=re.IGNORECASE,
    ),

    re.compile(
        r"\bEP\s*\d{6,}\b",
        flags=re.IGNORECASE,
    ),
]


DATE_PATTERNS = [

    re.compile(
        r"\b\d{1,2}[/-]\d{1,2}[/-]\d{2,4}\b"
    ),

    re.compile(
        r"\b\d{1,2}\s+"
        r"(?:January|February|March|April|May|June|"
        r"July|August|September|October|November|December)"
        r"\s+\d{4}\b",
        flags=re.IGNORECASE,
    ),

    re.compile(
        r"\b(?:January|February|March|April|May|June|"
        r"July|August|September|October|November|December)"
        r"\s+\d{1,2},?\s+\d{4}\b",
        flags=re.IGNORECASE,
    ),
]


# ---------------------------------------------------------------------
# Claim extraction
# ---------------------------------------------------------------------

def extract_claim_numbers(
    text: str,
) -> List[int]:

    text = _clean_text(text)

    claims: List[int] = []

    # Ranges first

    for match in CLAIM_RANGE_PATTERN.finditer(
        text
    ):

        start = int(match.group(1))
        end = int(match.group(2))

        if end >= start and end - start <= 100:

            claims.extend(
                range(
                    start,
                    end + 1,
                )
            )

    # Explicit comma-separated claims

    for match in CLAIM_PATTERN.finditer(
        text
    ):

        value = match.group(1)

        if not value:
            continue

        value = value.replace(
            "–",
            "-",
        )

        if re.match(
            r"^\d+\s*-\s*\d+$",
            value,
        ):
            continue

        for number in re.findall(
            r"\d+",
            value,
        ):

            try:
                claims.append(
                    int(number)
                )
            except ValueError:
                pass

    return sorted(
        set(
            claim
            for claim in claims
            if claim > 0
        )
    )


# ---------------------------------------------------------------------
# Section extraction
# ---------------------------------------------------------------------

def extract_statutory_sections(
    text: str,
) -> List[str]:

    sections = []

    for match in SECTION_PATTERN.finditer(
        text
    ):

        value = _clean_text(
            match.group(1)
        )

        value = re.sub(
            r"\s+",
            "",
            value,
        )

        value = value.upper()

        if value.startswith("3"):
            value = "Section 3" + value[1:]

        else:
            value = "Section " + value

        sections.append(
            value
        )

    return _unique(
        sections
    )


# ---------------------------------------------------------------------
# Citation extraction
# ---------------------------------------------------------------------

def extract_citations(
    text: str,
) -> List[FERCitation]:

    citations = []

    for pattern in PATENT_NUMBER_PATTERNS:

        for match in pattern.finditer(
            text
        ):

            reference = _clean_text(
                match.group(0)
            )

            if not reference:
                continue

            context_start = max(
                0,
                match.start() - 180,
            )

            context_end = min(
                len(text),
                match.end() + 180,
            )

            context = _clean_text(
                text[
                    context_start:
                    context_end
                ]
            )

            upper = reference.upper()

            if upper.startswith("WO"):
                citation_type = "WO"

            elif upper.startswith("EP"):
                citation_type = "EP"

            elif upper.startswith("IN"):
                citation_type = "Indian"

            else:
                citation_type = "patent_document"

            citations.append(
                FERCitation(
                    citation_id=_stable_id(
                        "CIT",
                        reference + context,
                    ),
                    reference=reference,
                    context=context,
                    citation_type=citation_type,
                )
            )

    # Deduplicate

    unique = {}

    for citation in citations:

        key = citation.reference.lower()

        if key not in unique:
            unique[key] = citation

    return list(
        unique.values()
    )


# ---------------------------------------------------------------------
# Deadline extraction
# ---------------------------------------------------------------------

def extract_deadlines(
    text: str,
) -> List[FERDeadline]:

    deadlines = []

    deadline_keywords = [
        "deadline",
        "within",
        "respond",
        "response",
        "reply",
        "time limit",
        "period",
        "days",
        "months",
        "due",
        "on or before",
    ]

    for pattern in DATE_PATTERNS:

        for match in pattern.finditer(
            text
        ):

            date_text = _clean_text(
                match.group(0)
            )

            start = max(
                0,
                match.start() - 250,
            )

            end = min(
                len(text),
                match.end() + 250,
            )

            context = _clean_text(
                text[start:end]
            )

            lower = context.lower()

            if not any(
                keyword in lower
                for keyword in deadline_keywords
            ):
                continue

            deadlines.append(
                FERDeadline(
                    deadline_id=_stable_id(
                        "DL",
                        date_text + context,
                    ),
                    date_text=date_text,
                    context=context,
                    confidence=0.85,
                )
            )

    unique = {}

    for deadline in deadlines:

        key = (
            deadline.date_text.lower()
            + "|"
            + deadline.context.lower()
        )

        if key not in unique:
            unique[key] = deadline

    return list(
        unique.values()
    )


# ---------------------------------------------------------------------
# Objection classification
# ---------------------------------------------------------------------

def _match_categories(
    text: str,
) -> List[str]:

    lower = text.lower()

    categories = []

    for category, patterns in (
        OBJECTION_PATTERNS.items()
    ):

        if any(
            pattern.lower() in lower
            for pattern in patterns
        ):
            categories.append(
                category
            )

    return categories


def _extract_objection_blocks(
    text: str,
) -> List[str]:

    """
    Split FER into reasonably useful objection blocks.

    Handles headings such as:

        Novelty
        Inventive Step
        Objection under Section 3(k)
        Claims 1-5
        Examination Report
    """

    lines = text.splitlines()

    blocks = []

    current: List[str] = []

    heading_pattern = re.compile(
        r"^\s*(?:"
        r"\d+[\.\)]\s*"
        r"|[A-Z][A-Z\s\-]{4,}:?"
        r"|(?:objection|novelty|inventive|"
        r"clarity|support|sufficiency|"
        r"unity|section)\b"
        r")",
        flags=re.IGNORECASE,
    )

    for line in lines:

        clean = _clean_text(line)

        if not clean:
            continue

        is_heading = bool(
            heading_pattern.match(
                clean
            )
        )

        if (
            is_heading
            and current
        ):

            block = _clean_text(
                " ".join(current)
            )

            if len(block) >= 30:
                blocks.append(block)

            current = []

        current.append(clean)

    if current:

        block = _clean_text(
            " ".join(current)
        )

        if len(block) >= 30:
            blocks.append(block)

    return blocks


def extract_objections(
    text: str,
) -> List[FERObjection]:

    blocks = _extract_objection_blocks(
        text
    )

    objections = []

    for block in blocks:

        categories = _match_categories(
            block
        )

        if not categories:
            continue

        claims = extract_claim_numbers(
            block
        )

        sections = extract_statutory_sections(
            block
        )

        citations = [
            citation.reference
            for citation in extract_citations(
                block
            )
        ]

        # Pick a primary category

        category_priority = [
            "section_3",
            "novelty",
            "inventive_step",
            "sufficiency",
            "support",
            "clarity",
            "unity",
            "amendment",
            "formal",
            "drawings",
            "sequence",
            "abstract",
            "title",
        ]

        category = next(
            (
                item
                for item in category_priority
                if item in categories
            ),
            categories[0],
        )

        title_map = {
            "novelty": "Novelty-related objection",
            "inventive_step": "Inventive-step objection",
            "section_3": "Section 3-related objection",
            "clarity": "Clarity-related objection",
            "support": "Support-related objection",
            "sufficiency": "Sufficiency-related objection",
            "unity": "Unity-related objection",
            "amendment": "Amendment-related issue",
            "formal": "Formal requirement",
            "drawings": "Drawing-related issue",
            "sequence": "Sequence-listing issue",
            "abstract": "Abstract-related issue",
            "title": "Title-related issue",
        }

        title = title_map.get(
            category,
            "Examination objection",
        )

        objection = FERObjection(
            objection_id=_stable_id(
                "OBJ",
                block,
            ),
            category=category,
            title=title,
            text=block,
            claims=claims,
            statutory_sections=sections,
            cited_documents=_unique(
                citations
            ),
            confidence=0.80,
        )

        objections.append(
            objection
        )

    return objections


# ---------------------------------------------------------------------
# Response action generation
# ---------------------------------------------------------------------

def generate_response_actions(
    objections: List[FERObjection],
) -> List[FERAction]:

    actions = []

    for objection in objections:

        if objection.category == "novelty":

            action = (
                "Review each cited document against every "
                "identified claim limitation and verify the "
                "specific disclosure relied upon."
            )

        elif objection.category == "inventive_step":

            action = (
                "Review the cited references, technical "
                "differences, combination rationale, and "
                "supporting evidence before preparing a response."
            )

        elif objection.category == "section_3":

            action = (
                "Identify the exact Section 3 provision cited "
                "and verify the factual and statutory basis of "
                "the objection."
            )

        elif objection.category == "clarity":

            action = (
                "Review the identified claim language for "
                "ambiguity, antecedent basis, terminology, "
                "relationships, and consistency with the "
                "specification."
            )

        elif objection.category == "support":

            action = (
                "Map the affected claim limitations to explicit "
                "supporting passages in the complete specification."
            )

        elif objection.category == "sufficiency":

            action = (
                "Review whether the specification provides "
                "sufficient technical disclosure for the claimed "
                "subject matter."
            )

        elif objection.category == "unity":

            action = (
                "Review the identified inventions and their "
                "technical relationships to determine the "
                "appropriate prosecution response."
            )

        elif objection.category == "amendment":

            action = (
                "Compare proposed or requested amendments with "
                "the original disclosure and create an amendment "
                "support map."
            )

        else:

            action = (
                "Review the objection and identify the specific "
                "documentary evidence required for response."
            )

        actions.append(
            FERAction(
                action_id=_stable_id(
                    "ACT",
                    objection.objection_id
                    + action,
                ),
                action=action,
                related_objection_id=(
                    objection.objection_id
                ),
                claims=(
                    objection.claims
                    or []
                ),
                priority=(
                    "high"
                    if objection.category
                    in {
                        "novelty",
                        "inventive_step",
                        "section_3",
                    }
                    else "review"
                ),
            )
        )

    return actions


# ---------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------

def analyze_fer(
    text: str,
    *,
    filename: str = "",
) -> Dict[str, Any]:

    text = _clean_text(text)

    if not text:

        return {
            "success": False,
            "error": "FER text is empty.",
            "fer_analyzer_version":
                FER_ANALYZER_VERSION,
            "timestamp": _utc_now(),
        }

    objections = extract_objections(
        text
    )

    citations = extract_citations(
        text
    )

    deadlines = extract_deadlines(
        text
    )

    sections = extract_statutory_sections(
        text
    )

    actions = generate_response_actions(
        objections
    )

    claim_numbers = extract_claim_numbers(
        text
    )

    sha256 = hashlib.sha256(
        text.encode(
            "utf-8"
        )
    ).hexdigest()

    category_counts: Dict[
        str,
        int
    ] = {}

    for objection in objections:

        category_counts[
            objection.category
        ] = (
            category_counts.get(
                objection.category,
                0,
            )
            + 1
        )

    return {

        "success": True,

        "fer_analyzer_version":
            FER_ANALYZER_VERSION,

        "timestamp":
            _utc_now(),

        "filename":
            filename,

        "sha256":
            sha256,

        "document_statistics": {
            "characters":
                len(text),

            "words":
                len(
                    text.split()
                ),

            "claims_referenced":
                len(claim_numbers),

            "objections":
                len(objections),

            "citations":
                len(citations),

            "deadlines":
                len(deadlines),
        },

        "claims_referenced":
            claim_numbers,

        "statutory_sections":
            sections,

        "objections": [
            item.to_dict()
            for item in objections
        ],

        "citations": [
            item.to_dict()
            for item in citations
        ],

        "deadlines": [
            item.to_dict()
            for item in deadlines
        ],

        "response_actions": [
            item.to_dict()
            for item in actions
        ],

        "category_counts":
            category_counts,

        "provenance": {
            "source_filename":
                filename,

            "text_sha256":
                sha256,

            "analyzer_version":
                FER_ANALYZER_VERSION,

            "generated_at":
                _utc_now(),
        },
    }


# ---------------------------------------------------------------------
# Claim-specific objection map
# ---------------------------------------------------------------------

def build_claim_objection_map(
    analysis: Dict[str, Any],
) -> Dict[str, List[Dict[str, Any]]]:

    result: Dict[
        str,
        List[Dict[str, Any]]
    ] = {}

    objections = _as_list(
        analysis.get(
            "objections",
            [],
        )
    )

    for objection in objections:

        if not isinstance(
            objection,
            dict,
        ):
            continue

        claims = _as_list(
            objection.get(
                "claims",
                [],
            )
        )

        for claim in claims:

            key = str(
                claim
            )

            result.setdefault(
                key,
                [],
            )

            result[key].append(
                objection
            )

    return result


# ---------------------------------------------------------------------
# Prosecution dashboard
# ---------------------------------------------------------------------

def build_prosecution_dashboard(
    analysis: Dict[str, Any],
) -> Dict[str, Any]:

    objections = _as_list(
        analysis.get(
            "objections",
            [],
        )
    )

    citations = _as_list(
        analysis.get(
            "citations",
            [],
        )
    )

    deadlines = _as_list(
        analysis.get(
            "deadlines",
            [],
        )
    )

    actions = _as_list(
        analysis.get(
            "response_actions",
            [],
        )
    )

    high_priority = [
        item
        for item in actions
        if isinstance(
            item,
            dict,
        )
        and item.get(
            "priority"
        ) == "high"
    ]

    return {

        "objection_count":
            len(objections),

        "citation_count":
            len(citations),

        "deadline_count":
            len(deadlines),

        "response_action_count":
            len(actions),

        "high_priority_actions":
            len(high_priority),

        "categories":
            analysis.get(
                "category_counts",
                {},
            ),

        "claim_objection_map":
            build_claim_objection_map(
                analysis
            ),
    }


# ---------------------------------------------------------------------
# FER response matrix
# ---------------------------------------------------------------------

def build_response_matrix(
    analysis: Dict[str, Any],
) -> List[Dict[str, Any]]:

    matrix = []

    objections = _as_list(
        analysis.get(
            "objections",
            [],
        )
    )

    actions = _as_list(
        analysis.get(
            "response_actions",
            [],
        )
    )

    actions_by_objection = {}

    for action in actions:

        if not isinstance(
            action,
            dict,
        ):
            continue

        objection_id = action.get(
            "related_objection_id",
            "",
        )

        actions_by_objection.setdefault(
            objection_id,
            [],
        ).append(
            action
        )

    for objection in objections:

        if not isinstance(
            objection,
            dict,
        ):
            continue

        objection_id = objection.get(
            "objection_id",
            "",
        )

        matrix.append(
            {
                "objection_id":
                    objection_id,

                "category":
                    objection.get(
                        "category",
                        "",
                    ),

                "claims":
                    objection.get(
                        "claims",
                        [],
                    ),

                "statutory_sections":
                    objection.get(
                        "statutory_sections",
                        [],
                    ),

                "cited_documents":
                    objection.get(
                        "cited_documents",
                        [],
                    ),

                "objection":
                    objection.get(
                        "text",
                        "",
                    ),

                "response_actions":
                    actions_by_objection.get(
                        objection_id,
                        [],
                    ),

                "status":
                    "REVIEW_REQUIRED",
            }
        )

    return matrix


# ---------------------------------------------------------------------
# Text summary
# ---------------------------------------------------------------------

def summarize_fer(
    analysis: Dict[str, Any],
) -> str:

    if not analysis.get(
        "success",
        False,
    ):
        return (
            "FER analysis could not be completed."
        )

    stats = analysis.get(
        "document_statistics",
        {},
    )

    categories = analysis.get(
        "category_counts",
        {},
    )

    objections = stats.get(
        "objections",
        0,
    )

    citations = stats.get(
        "citations",
        0,
    )

    deadlines = stats.get(
        "deadlines",
        0,
    )

    category_text = ", ".join(
        f"{key}: {value}"
        for key, value
        in categories.items()
    )

    if not category_text:
        category_text = "None detected"

    return (
        f"FER analysis identified "
        f"{objections} objection(s), "
        f"{citations} citation(s), and "
        f"{deadlines} potential deadline reference(s). "
        f"Objection categories: {category_text}. "
        "All automatically extracted items require "
        "verification against the original prosecution document."
    )


# ---------------------------------------------------------------------
# Backward-compatible helpers
# ---------------------------------------------------------------------

def parse_fer(
    text: str,
    filename: str = "",
) -> Dict[str, Any]:

    return analyze_fer(
        text,
        filename=filename,
    )


def analyze_examination_report(
    text: str,
    filename: str = "",
) -> Dict[str, Any]:

    return analyze_fer(
        text,
        filename=filename,
    )


def extract_objection_details(
    text: str,
) -> List[Dict[str, Any]]:

    return [
        item.to_dict()
        for item in extract_objections(
            text
        )
    ]


def extract_fer_citations(
    text: str,
) -> List[Dict[str, Any]]:

    return [
        item.to_dict()
        for item in extract_citations(
            text
        )
    ]


def extract_fer_deadlines(
    text: str,
) -> List[Dict[str, Any]]:

    return [
        item.to_dict()
        for item in extract_deadlines(
            text
        )
    ]


# ---------------------------------------------------------------------
# Optional Gemini integration
# ---------------------------------------------------------------------

def enrich_with_gemini(
    analysis: Dict[str, Any],
    gemini_service: Optional[Any] = None,
) -> Dict[str, Any]:

    """
    Optional AI enrichment.

    Gemini receives the deterministic FER analysis rather than the
    responsibility of extracting the underlying facts.

    This preserves the architecture:

        deterministic extraction
                ↓
        structured FER model
                ↓
             Gemini
                ↓
        explanation only
    """

    if not analysis.get(
        "success",
        False,
    ):
        return analysis

    if gemini_service is None:

        try:

            from .gemini_service import (
                get_gemini_service
            )

            gemini_service = (
                get_gemini_service()
            )

        except Exception:

            return analysis

    try:

        import json

        prompt = f"""
Explain the following deterministic FER analysis.

Do not invent objections, citations, dates, claims, or legal provisions.

Identify:

1. Main prosecution issues
2. Objections requiring immediate review
3. Claims affected
4. Evidence that should be verified
5. Response-planning considerations
6. Missing information

Return concise professional prose.

DETERMINISTIC ANALYSIS:

{json.dumps(
    analysis,
    ensure_ascii=False,
    indent=2,
    default=str,
)}
"""

        response = gemini_service.generate(
            prompt=prompt,
            system_instruction="""
You are a patent prosecution analysis assistant.

The supplied structured FER analysis is the source of truth.

Do not create facts.

Do not provide a final legal opinion.

Clearly distinguish extracted facts from analytical suggestions.
""",
            temperature=0.05,
            max_output_tokens=5000,
        )

        if response.success:

            analysis = dict(
                analysis
            )

            analysis[
                "ai_interpretation"
            ] = response.text

            analysis[
                "ai_model"
            ] = response.model

            analysis[
                "ai_used"
            ] = True

    except Exception as exc:

        analysis = dict(
            analysis
        )

        analysis[
            "ai_error"
        ] = str(exc)

    return analysis


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

__all__ = [
    "FER_ANALYZER_VERSION",
    "FERObjection",
    "FERCitation",
    "FERDeadline",
    "FERAction",
    "extract_claim_numbers",
    "extract_statutory_sections",
    "extract_citations",
    "extract_deadlines",
    "extract_objections",
    "generate_response_actions",
    "analyze_fer",
    "parse_fer",
    "analyze_examination_report",
    "build_claim_objection_map",
    "build_prosecution_dashboard",
    "build_response_matrix",
    "summarize_fer",
    "extract_objection_details",
    "extract_fer_citations",
    "extract_fer_deadlines",
    "enrich_with_gemini",
]
