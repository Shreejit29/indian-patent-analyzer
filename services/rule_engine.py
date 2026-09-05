import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

FORM2_RULES_FILE = (
    BASE_DIR / "data" / "form2_rules.json"
)

PATENT_RULES_FILE = (
    BASE_DIR / "data" / "patent_rules.json"
)


# ============================================================
# BASIC UTILITIES
# ============================================================

def normalize_text(text: str) -> str:
    """
    Normalize extracted patent text for deterministic analysis.
    """

    if not text:
        return ""

    text = text.replace("\r\n", "\n")
    text = text.replace("\r", "\n")

    # Normalize spaces while retaining paragraphs.
    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def load_rules(
    file_path: Path,
) -> List[Dict[str, Any]]:
    """
    Load a rule database.

    Supports:
        [...]
    or:
        {"rules": [...]}
    """

    if not file_path.exists():
        return []

    try:

        with open(
            file_path,
            "r",
            encoding="utf-8",
        ) as file:

            data = json.load(file)

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            rules = data.get("rules", [])

            if isinstance(rules, list):
                return rules

    except Exception:
        return []

    return []


def load_form2_rules() -> List[Dict[str, Any]]:
    """
    Load Form 2-specific rules.
    """

    return load_rules(
        FORM2_RULES_FILE
    )


def load_patent_rules() -> List[Dict[str, Any]]:
    """
    Load broader Indian patent rules.
    """

    return load_rules(
        PATENT_RULES_FILE
    )


# ============================================================
# SECTION DETECTION
# ============================================================

SECTION_PATTERNS = {
    "title": [
        r"\btitle\s+of\s+the\s+invention\b",
        r"\binvention\s+title\b",
    ],

    "field_of_invention": [
        r"\bfield\s+of\s+the\s+invention\b",
        r"\bfield\s+of\s+invention\b",
    ],

    "background": [
        r"\bbackground\s+of\s+the\s+invention\b",
        r"\bbackground\b",
        r"\bprior\s+art\b",
    ],

    "objects": [
        r"\bobject\s+of\s+the\s+invention\b",
        r"\bobjects\s+of\s+the\s+invention\b",
        r"\bobjectives?\b",
    ],

    "summary": [
        r"\bsummary\s+of\s+the\s+invention\b",
        r"\bsummary\b",
    ],

    "detailed_description": [
        r"\bdetailed\s+description\b",
        r"\bdetailed\s+description\s+of\s+the\s+invention\b",
        r"\bdescription\s+of\s+the\s+invention\b",
    ],

    "claims": [
        r"\bclaims?\b",
        r"\bwhat\s+is\s+claimed\s+is\b",
        r"\bwe\s+claim\b",
    ],

    "abstract": [
        r"\babstract\b",
    ],

    "drawings": [
        r"\bbrief\s+description\s+of\s+drawings\b",
        r"\bdescription\s+of\s+drawings\b",
        r"\bdrawings?\b",
    ],
}


def detect_sections(
    text: str,
) -> Dict[str, Dict[str, Any]]:
    """
    Detect major patent specification sections.

    This is a heuristic detector and should not be treated
    as a legal determination.
    """

    normalized = normalize_text(text)

    results = {}

    for section, patterns in SECTION_PATTERNS.items():

        matches = []

        for pattern in patterns:

            for match in re.finditer(
                pattern,
                normalized,
                re.IGNORECASE | re.MULTILINE,
            ):

                matches.append(
                    {
                        "start": match.start(),
                        "end": match.end(),
                        "matched_text": match.group(0),
                    }
                )

        if matches:

            matches.sort(
                key=lambda item: item["start"]
            )

            results[section] = {
                "present": True,
                "first_position": matches[0]["start"],
                "matched_heading": matches[0]["matched_text"],
            }

        else:

            results[section] = {
                "present": False,
                "first_position": None,
                "matched_heading": "",
            }

    return results


# ============================================================
# TITLE
# ============================================================

def extract_title(
    text: str,
) -> str:
    """
    Extract a probable invention title.
    """

    normalized = normalize_text(text)

    patterns = [
        r"title\s+of\s+the\s+invention\s*[:\-]?\s*(.+)",
        r"invention\s+title\s*[:\-]?\s*(.+)",
    ]

    for pattern in patterns:

        match = re.search(
            pattern,
            normalized,
            re.IGNORECASE,
        )

        if match:

            title = match.group(1).strip()

            title = title.split("\n")[0].strip()

            if title:
                return title

    # Fallback: inspect beginning of document.
    first_lines = [
        line.strip()
        for line in normalized.splitlines()
        if line.strip()
    ][:20]

    for line in first_lines:

        if (
            3 <= len(line.split()) <= 15
            and len(line) < 180
            and not re.search(
                r"^(field|background|abstract|claims?)\b",
                line,
                re.IGNORECASE,
            )
        ):
            return line

    return ""


# ============================================================
# ABSTRACT
# ============================================================

def extract_abstract(
    text: str,
) -> str:
    """
    Extract probable abstract text.
    """

    normalized = normalize_text(text)

    match = re.search(
        r"\babstract\b\s*[:\-]?\s*(.*?)(?="
        r"\n\s*(?:claims?|what\s+is\s+claimed|"
        r"brief\s+description\s+of\s+drawings|"
        r"drawings?|references?|signature)\b"
        r"|$)",
        normalized,
        re.IGNORECASE | re.DOTALL,
    )

    if match:

        return match.group(1).strip()

    return ""


# ============================================================
# CLAIMS
# ============================================================

def extract_claims(
    text: str,
) -> List[Dict[str, Any]]:
    """
    Extract numbered claims from a patent document.

    This is intentionally conservative.
    """

    normalized = normalize_text(text)

    start = None

    heading_patterns = [
        r"\bwhat\s+is\s+claimed\s+is\b",
        r"\bwe\s+claim\b",
        r"^\s*claims?\s*[:\-]?\s*$",
    ]

    for pattern in heading_patterns:

        match = re.search(
            pattern,
            normalized,
            re.IGNORECASE | re.MULTILINE,
        )

        if match:

            start = match.end()
            break

    if start is None:
        return []

    claims_text = normalized[start:]

    # Stop before likely following sections.
    stop_patterns = [
        r"\n\s*abstract\b",
        r"\n\s*brief\s+description\s+of\s+drawings\b",
        r"\n\s*drawings?\b",
        r"\n\s*references?\b",
        r"\n\s*signature\b",
    ]

    stop_positions = []

    for pattern in stop_patterns:

        match = re.search(
            pattern,
            claims_text,
            re.IGNORECASE,
        )

        if match:
            stop_positions.append(
                match.start()
            )

    if stop_positions:

        claims_text = claims_text[
            :min(stop_positions)
        ]

    # Numbered claims.
    pattern = re.compile(
        r"(?:^|\n)"
        r"\s*(\d+)"
        r"\s*[\.\)]"
        r"\s*(.*?)"
        r"(?=\n\s*\d+\s*[\.\)]|\Z)",
        re.IGNORECASE | re.DOTALL,
    )

    matches = pattern.findall(
        claims_text
    )

    claims = []

    for number, claim_text in matches:

        cleaned = re.sub(
            r"\s+",
            " ",
            claim_text,
        ).strip()

        if cleaned:

            claims.append(
                {
                    "claim_number": int(number),
                    "claim_text": cleaned,
                }
            )

    return claims


# ============================================================
# REFERENCE NUMERALS
# ============================================================

def extract_reference_numerals(
    text: str,
) -> List[str]:
    """
    Extract probable reference numerals such as:

        sensor (102)
        processor 104
        module (205)
    """

    if not text:
        return []

    numerals = set()

    # Parenthesized numerals.
    for match in re.findall(
        r"\((\d{1,4})\)",
        text,
    ):

        numerals.add(
            match
        )

    # Terms followed by numerals.
    for match in re.findall(
        r"\b(?:sensor|module|processor|controller|"
        r"unit|device|system|component|element|"
        r"circuit|memory|interface|detector|"
        r"housing|chamber|layer|terminal|"
        r"apparatus|assembly)\s+(\d{1,4})\b",
        text,
        re.IGNORECASE,
    ):

        numerals.add(
            match
        )

    return sorted(
        numerals,
        key=lambda value: int(value),
    )


# ============================================================
# WORD COUNT
# ============================================================

def word_count(
    text: str,
) -> int:
    """
    Count words using a simple deterministic method.
    """

    if not text:
        return 0

    return len(
        re.findall(
            r"\b[\w'-]+\b",
            text,
        )
    )


# ============================================================
# CLAIM DEPENDENCY
# ============================================================

def get_claim_dependencies(
    claim_text: str,
) -> List[int]:
    """
    Detect references such as:

        claim 1
        claims 1 and 2
        claim 1 or 2
    """

    if not claim_text:
        return []

    dependencies = []

    pattern = re.compile(
        r"\bclaims?\s+"
        r"((?:\d+\s*(?:,|and|or)?\s*)+)",
        re.IGNORECASE,
    )

    for match in pattern.findall(
        claim_text
    ):

        numbers = re.findall(
            r"\d+",
            match,
        )

        for number in numbers:

            number_int = int(number)

            if number_int not in dependencies:

                dependencies.append(
                    number_int
                )

    return dependencies


# ============================================================
# CLAIM TYPE
# ============================================================

def classify_claim(
    claim_text: str,
) -> str:
    """
    Basic deterministic claim categorization.
    """

    text = claim_text.lower()

    if re.search(
        r"\bmethod\b|\bprocess\b|\bsteps?\b",
        text,
    ):
        return "method/process"

    if re.search(
        r"\bapparatus\b|\bdevice\b|\bsystem\b|"
        r"\bmachine\b|\bassembly\b",
        text,
    ):
        return "apparatus/system/device"

    if re.search(
        r"\bcomposition\b|\bformulation\b|\bcompound\b",
        text,
    ):
        return "composition/formulation"

    if re.search(
        r"\bkit\b",
        text,
    ):
        return "kit"

    if re.search(
        r"\bcircuit\b|\bprocessor\b|\bcontroller\b|"
        r"\bcomputer\b|\bsoftware\b",
        text,
    ):
        return "computer/electronic"

    return "other"


# ============================================================
# CLAIM ANALYSIS
# ============================================================

def analyze_claim_structure(
    claims: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Deterministic structural analysis of claims.
    """

    results = []

    claim_numbers = {
        claim.get("claim_number")
        for claim in claims
    }

    independent_count = 0
    dependent_count = 0

    for claim in claims:

        number = claim.get(
            "claim_number"
        )

        text = claim.get(
            "claim_text",
            "",
        ).strip()

        dependencies = (
            get_claim_dependencies(
                text
            )
        )

        if dependencies:

            claim_type = "dependent"
            dependent_count += 1

        else:

            claim_type = "independent"
            independent_count += 1

        issues = []

        # ----------------------------------------------------
        # Dependency validation
        # ----------------------------------------------------

        for dependency in dependencies:

            if dependency >= number:

                issues.append(
                    {
                        "type": "invalid_dependency_order",
                        "severity": "high",
                        "message": (
                            f"Claim {number} refers to "
                            f"claim {dependency}, which is "
                            "not an earlier claim."
                        ),
                    }
                )

            elif dependency not in claim_numbers:

                issues.append(
                    {
                        "type": "missing_dependency",
                        "severity": "high",
                        "message": (
                            f"Claim {number} refers to "
                            f"claim {dependency}, but that "
                            "claim was not detected."
                        ),
                    }
                )

        # ----------------------------------------------------
        # Basic claim quality heuristics
        # ----------------------------------------------------

        if len(text) < 8:

            issues.append(
                {
                    "type": "very_short_claim",
                    "severity": "medium",
                    "message": (
                        f"Claim {number} is unusually short "
                        "and should be manually reviewed."
                    ),
                }
            )

        if not re.search(
            r"\bcomprising\b|\bconsisting\b|\bincluding\b|"
            r"\bwherein\b|\bconfigured\b|\bcomprises\b",
            text,
            re.IGNORECASE,
        ):

            issues.append(
                {
                    "type": "claim_structure_review",
                    "severity": "low",
                    "message": (
                        f"Claim {number} does not contain "
                        "common structural claim language. "
                        "This is only a heuristic and requires "
                        "manual review."
                    ),
                }
            )

        results.append(
            {
                "claim_number": number,
                "claim_text": text,
                "claim_type": claim_type,
                "category": classify_claim(text),
                "dependencies": dependencies,
                "word_count": word_count(text),
                "issues": issues,
            }
        )

    return {
        "status": "completed",
        "total_claims": len(claims),
        "independent_claims": independent_count,
        "dependent_claims": dependent_count,
        "claims": results,
    }


# ============================================================
# SECTION CONTENT CHECKS
# ============================================================

def check_required_sections(
    sections: Dict[str, Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Check whether important specification sections
    are detectable.

    This does NOT mean that every section is legally
    mandatory in exactly this heading format.
    """

    issues = []

    important_sections = [
        "title",
        "detailed_description",
        "claims",
        "abstract",
    ]

    for section in important_sections:

        info = sections.get(
            section,
            {},
        )

        if not info.get(
            "present",
            False,
        ):

            issues.append(
                {
                    "type": "missing_section",
                    "severity": "high"
                    if section in {
                        "claims",
                        "abstract",
                    }
                    else "medium",
                    "section": section,
                    "message": (
                        f"The application could not "
                        f"deterministically identify a "
                        f"{section.replace('_', ' ')} section."
                    ),
                }
            )

    return issues


# ============================================================
# TITLE CHECKS
# ============================================================

def analyze_title(
    title: str,
) -> Dict[str, Any]:
    """
    Analyze title length and basic quality.
    """

    count = word_count(
        title
    )

    issues = []

    if not title:

        issues.append(
            {
                "type": "missing_title",
                "severity": "high",
                "message": (
                    "No invention title could be "
                    "reliably identified."
                ),
            }
        )

    elif count > 15:

        issues.append(
            {
                "type": "title_word_count",
                "severity": "medium",
                "message": (
                    f"The detected title contains "
                    f"{count} words. The application should "
                    "verify compliance with the applicable "
                    "Rule 13 requirements."
                ),
            }
        )

    return {
        "title": title,
        "word_count": count,
        "issues": issues,
    }


# ============================================================
# ABSTRACT CHECKS
# ============================================================

def analyze_abstract(
    abstract: str,
) -> Dict[str, Any]:
    """
    Analyze abstract using deterministic checks.
    """

    count = word_count(
        abstract
    )

    issues = []

    if not abstract:

        issues.append(
            {
                "type": "missing_abstract",
                "severity": "high",
                "message": (
                    "No abstract could be reliably identified."
                ),
            }
        )

    elif count > 150:

        issues.append(
            {
                "type": "abstract_word_count",
                "severity": "medium",
                "message": (
                    f"The detected abstract contains "
                    f"{count} words, exceeding the "
                    "150-word threshold associated with "
                    "Rule 13(7)(c). Verify against the "
                    "current applicable Rules."
                ),
            }
        )

    return {
        "abstract": abstract,
        "word_count": count,
        "issues": issues,
    }


# ============================================================
# REFERENCE NUMERAL ANALYSIS
# ============================================================

def analyze_reference_numerals(
    text: str,
    claims: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Analyze reference numeral usage.

    This is a heuristic consistency check.
    """

    numerals = extract_reference_numerals(
        text
    )

    claims_text = " ".join(
        claim.get(
            "claim_text",
            "",
        )
        for claim in claims
    )

    claim_numerals = extract_reference_numerals(
        claims_text
    )

    unused = [
        numeral
        for numeral in numerals
        if numeral not in claim_numerals
    ]

    return {
        "detected_numerals": numerals,
        "claim_numerals": claim_numerals,
        "unused_in_claims": unused,
    }


# ============================================================
# SECTION 3 KEYWORD SCREENING
# ============================================================

SECTION_3_PATTERNS = {
    "Section 3(a)":
        [
            r"\bfrivolous\b",
            r"\bcontrary\s+to\s+well[- ]established"
            r"\bscientific\s+principles?\b",
        ],

    "Section 3(b)":
        [
            r"\bpublic\s+order\b",
            r"\bmorality\b",
        ],

    "Section 3(c)":
        [
            r"\bdiscovery\s+of\s+a\s+scientific\b",
            r"\bdiscovery\s+of\s+a\s+new\s+property\b",
        ],

    "Section 3(d)":
        [
            r"\bnew\s+form\s+of\s+a\s+known\s+substance\b",
            r"\bnew\s+use\s+of\s+a\s+known\s+substance\b",
        ],

    "Section 3(e)":
        [
            r"\bmixture\b",
            r"\badmixture\b",
            r"\bmere\s+mixture\b",
        ],

    "Section 3(f)":
        [
            r"\barrangement\b",
            r"\bre[- ]arrangement\b",
            r"\bduplication\b",
        ],

    "Section 3(g)":
        [
            r"\bagriculture\b",
            r"\bhorticulture\b",
        ],

    "Section 3(h)":
        [
            r"\bmethod\s+of\s+agriculture\b",
            r"\bmethod\s+of\s+horticulture\b",
        ],

    "Section 3(i)":
        [
            r"\bdiagnostic\b",
            r"\btreatment\b",
            r"\btherapeutic\b",
            r"\bsurgical\b",
        ],

    "Section 3(j)":
        [
            r"\bplant\b",
            r"\banimal\b",
            r"\bseed\b",
            r"\bvariety\b",
        ],

    "Section 3(k)":
        [
            r"\bcomputer\s+programme\b",
            r"\bcomputer\s+program\b",
            r"\bsoftware\b",
            r"\bsource\s+code\b",
            r"\balgorithm\b",
        ],

    "Section 3(l)":
        [
            r"\bliterary\b",
            r"\bartistic\b",
            r"\bmusical\s+work\b",
        ],

    "Section 3(m)":
        [
            r"\bmental\s+act\b",
            r"\bbusiness\s+method\b",
        ],

    "Section 3(n)":
        [
            r"\bpresentation\s+of\s+information\b",
        ],

    "Section 3(o)":
        [
            r"\bintegrated\s+circuit\b",
            r"\blayout\b",
            r"\btopography\b",
        ],

    "Section 3(p)":
        [
            r"\btraditional\s+knowledge\b",
            r"\btraditional\s+use\b",
        ],
}


def screen_section_3(
    text: str,
) -> List[Dict[str, Any]]:
    """
    Keyword-based Section 3 screening.

    IMPORTANT:
    This does NOT determine that an invention falls
    within a Section 3 exclusion.

    It only identifies areas requiring review.
    """

    issues = []

    normalized = normalize_text(
        text
    )

    for provision, patterns in SECTION_3_PATTERNS.items():

        matched_terms = []

        for pattern in patterns:

            if re.search(
                pattern,
                normalized,
                re.IGNORECASE,
            ):

                matched_terms.append(
                    pattern
                )

        if matched_terms:

            issues.append(
                {
                    "type": "section_3_screening",
                    "severity": "medium",
                    "provision": provision,
                    "message": (
                        f"Potential {provision} relevance "
                        "detected by keyword screening. "
                        "This is not a finding that the "
                        "invention is excluded."
                    ),
                    "matched_patterns": matched_terms,
                }
            )

    return issues


# ============================================================
# SECTION 10 SCREENING
# ============================================================

def screen_section_10(
    text: str,
    claims: List[Dict[str, Any]],
    abstract: str,
) -> List[Dict[str, Any]]:
    """
    Deterministic preliminary screening against major
    Section 10 specification concepts.

    These are not legal conclusions.
    """

    issues = []

    normalized = normalize_text(
        text
    )

    # --------------------------------------------------------
    # Description
    # --------------------------------------------------------

    if len(normalized) < 500:

        issues.append(
            {
                "type": "section_10_description",
                "severity": "medium",
                "message": (
                    "The extracted specification is unusually "
                    "short. Sufficiency of disclosure should "
                    "be reviewed manually."
                ),
            }
        )

    # --------------------------------------------------------
    # Claims
    # --------------------------------------------------------

    if not claims:

        issues.append(
            {
                "type": "section_10_claims",
                "severity": "high",
                "message": (
                    "No claims were reliably detected. "
                    "Verify the complete specification."
                ),
            }
        )

    # --------------------------------------------------------
    # Abstract
    # --------------------------------------------------------

    if not abstract:

        issues.append(
            {
                "type": "section_10_abstract",
                "severity": "high",
                "message": (
                    "No abstract was reliably detected."
                ),
            }
        )

    # --------------------------------------------------------
    # Best method indicators
    # --------------------------------------------------------

    best_method_terms = [
        "best method",
        "preferred embodiment",
        "preferred embodiment of the invention",
        "best mode",
    ]

    if not any(
        term in normalized.lower()
        for term in best_method_terms
    ):

        issues.append(
            {
                "type": "best_method_review",
                "severity": "low",
                "message": (
                    "No explicit best-method terminology was "
                    "detected. This does not establish "
                    "non-compliance; review the disclosure "
                    "for the applicable requirement."
                ),
            }
        )

    return issues


# ============================================================
# UNITY SCREENING
# ============================================================

def screen_unity(
    claims: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Very preliminary unity screening based on claim
    categories.

    This is NOT a legal unity determination.
    """

    if len(claims) < 2:
        return []

    categories = {}

    for claim in claims:

        category = classify_claim(
            claim.get(
                "claim_text",
                "",
            )
        )

        categories.setdefault(
            category,
            [],
        ).append(
            claim.get(
                "claim_number"
            )
        )

    if len(categories) >= 3:

        return [
            {
                "type": "unity_review",
                "severity": "medium",
                "message": (
                    "Claims appear to span several different "
                    "technical categories. Consider reviewing "
                    "unity/single-invention requirements. "
                    "This heuristic does not determine lack "
                    "of unity."
                ),
                "claim_categories": categories,
            }
        ]

    return []


# ============================================================
# DRAWING / REFERENCE SCREENING
# ============================================================

def screen_drawings(
    text: str,
) -> List[Dict[str, Any]]:
    """
    Screen for drawing references.
    """

    issues = []

    normalized = normalize_text(
        text
    )

    drawing_mentions = re.findall(
        r"\bfig(?:ure)?\.?\s*\d+\b",
        normalized,
        re.IGNORECASE,
    )

    drawing_section = bool(
        re.search(
            r"\b(?:brief\s+description\s+of\s+)?drawings?\b",
            normalized,
            re.IGNORECASE,
        )
    )

    if drawing_mentions and not drawing_section:

        issues.append(
            {
                "type": "drawing_section_review",
                "severity": "low",
                "message": (
                    "Figure references were detected, but "
                    "a drawing section could not be reliably "
                    "identified."
                ),
            }
        )

    return issues


# ============================================================
# MAIN FORM 2 ANALYZER
# ============================================================

def analyze_form2_document(
    text: str,
) -> Dict[str, Any]:
    """
    Perform deterministic preliminary analysis of an
    Indian patent specification.

    The function intentionally avoids making final legal
    conclusions.
    """

    normalized = normalize_text(
        text
    )

    # --------------------------------------------------------
    # Basic extraction
    # --------------------------------------------------------

    sections = detect_sections(
        normalized
    )

    title = extract_title(
        normalized
    )

    abstract = extract_abstract(
        normalized
    )

    claims = extract_claims(
        normalized
    )

    # --------------------------------------------------------
    # Basic checks
    # --------------------------------------------------------

    section_issues = (
        check_required_sections(
            sections
        )
    )

    title_analysis = (
        analyze_title(
            title
        )
    )

    abstract_analysis = (
        analyze_abstract(
            abstract
        )
    )

    # --------------------------------------------------------
    # Claims
    # --------------------------------------------------------

    claim_analysis = (
        analyze_claim_structure(
            claims
        )
    )

    # --------------------------------------------------------
    # Reference numerals
    # --------------------------------------------------------

    reference_analysis = (
        analyze_reference_numerals(
            normalized,
            claims,
        )
    )

    # --------------------------------------------------------
    # Section 3
    # --------------------------------------------------------

    section_3_issues = (
        screen_section_3(
            normalized
        )
    )

    # --------------------------------------------------------
    # Section 10
    # --------------------------------------------------------

    section_10_issues = (
        screen_section_10(
            normalized,
            claims,
            abstract,
        )
    )

    # --------------------------------------------------------
    # Unity
    # --------------------------------------------------------

    unity_issues = (
        screen_unity(
            claims
        )
    )

    # --------------------------------------------------------
    # Drawings
    # --------------------------------------------------------

    drawing_issues = (
        screen_drawings(
            normalized
        )
    )

    # --------------------------------------------------------
    # Combine issues
    # --------------------------------------------------------

    all_issues = (
        section_issues
        + title_analysis.get(
            "issues",
            [],
        )
        + abstract_analysis.get(
            "issues",
            [],
        )
        + section_3_issues
        + section_10_issues
        + unity_issues
        + drawing_issues
    )

    # --------------------------------------------------------
    # Status
    # --------------------------------------------------------

    if all_issues:

        status = "issues_detected"

    else:

        status = "preliminary_no_issues_detected"

    # --------------------------------------------------------
    # Final result
    # --------------------------------------------------------

    return {
        "status": status,

        "title": title,

        "title_analysis": title_analysis,

        "abstract": abstract,

        "abstract_analysis": abstract_analysis,

        "claims": claims,

        "claim_analysis": claim_analysis,

        "reference_numeral_analysis": reference_analysis,

        "sections": sections,

        "issues": all_issues,

        "section_3_screening": section_3_issues,

        "section_10_screening": section_10_issues,

        "unity_screening": unity_issues,

        "drawing_screening": drawing_issues,

        "document_statistics": {
            "characters": len(normalized),
            "words": word_count(normalized),
            "paragraphs": len(
                [
                    paragraph
                    for paragraph in normalized.split(
                        "\n\n"
                    )
                    if paragraph.strip()
                ]
            ),
        },

        "disclaimer": (
            "This deterministic analysis is a preliminary "
            "software-assisted screening. It does not "
            "constitute legal advice or a final determination "
            "of compliance, patentability, validity, or "
            "grantability."
        ),
    }


# ============================================================
# GENERAL PATENT RULE LOOKUP
# ============================================================

def find_relevant_rules(
    query: str,
    max_results: int = 10,
) -> List[Dict[str, Any]]:
    """
    Search the local patent rule database using simple
    keyword matching.

    This function is available for future modules and
    does not alter the deterministic result above.
    """

    if not query:
        return []

    rules = (
        load_patent_rules()
    )

    query_words = set(
        re.findall(
            r"\b[a-zA-Z0-9]{3,}\b",
            query.lower(),
        )
    )

    scored = []

    for rule in rules:

        searchable = " ".join(
            str(
                rule.get(
                    key,
                    "",
                )
            )
            for key in [
                "provision",
                "category",
                "title",
                "requirement",
                "analysis_type",
                "source_reference",
            ]
        ).lower()

        rule_words = set(
            re.findall(
                r"\b[a-zA-Z0-9]{3,}\b",
                searchable,
            )
        )

        overlap = query_words.intersection(
            rule_words
        )

        if overlap:

            scored.append(
                {
                    **rule,
                    "match_score": len(
                        overlap
                    ),
                }
            )

    scored.sort(
        key=lambda item: item.get(
            "match_score",
            0,
        ),
        reverse=True,
    )

    return scored[
        :max_results
    ]
