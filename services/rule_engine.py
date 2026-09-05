import json
import re
from pathlib import Path


# ---------------------------------------------------------
# RULE DATABASE
# ---------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent.parent
RULES_FILE = BASE_DIR / "data" / "form2_rules.json"


def load_form2_rules() -> list:
    """
    Load Form 2 rules from the JSON knowledge base.
    """

    if not RULES_FILE.exists():
        raise FileNotFoundError(
            f"Rule database not found: {RULES_FILE}"
        )

    with open(
        RULES_FILE,
        "r",
        encoding="utf-8"
    ) as file:

        return json.load(file)


# ---------------------------------------------------------
# TEXT UTILITIES
# ---------------------------------------------------------

def normalize_text(text: str) -> str:
    """
    Normalize whitespace while preserving the text.
    """

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


def count_words(text: str) -> int:
    """
    Count words in text.
    """

    if not text:
        return 0

    return len(
        re.findall(
            r"\b[\w'-]+\b",
            text
        )
    )


# ---------------------------------------------------------
# SECTION DETECTION
# ---------------------------------------------------------

SECTION_PATTERNS = {

    "title": [
        r"\btitle\b",
        r"title of the invention"
    ],

    "field": [
        r"\bfield of invention\b",
        r"\bfield of the invention\b"
    ],

    "background": [
        r"\bbackground\b",
        r"\bbackground of the invention\b"
    ],

    "prior_art": [
        r"\bprior art\b",
        r"\bprior-art\b",
        r"\bexisting technology\b"
    ],

    "objects": [
        r"\bobjects of the invention\b",
        r"\bobject of the invention\b"
    ],

    "summary": [
        r"\bsummary\b",
        r"\bsummary of the invention\b"
    ],

    "detailed_description": [
        r"\bdetailed description\b",
        r"\bdetailed description of the invention\b"
    ],

    "drawings": [
        r"\bbrief description of drawings\b",
        r"\bdescription of drawings\b",
        r"\bdrawings\b"
    ],

    "claims": [
        r"\bclaims\b",
        r"\bclaims section\b"
    ],

    "abstract": [
        r"\babstract\b"
    ]
}


def detect_sections(text: str) -> dict:
    """
    Detect commonly used patent specification sections.
    """

    normalized = normalize_text(text).lower()

    detected = {}

    for section, patterns in SECTION_PATTERNS.items():

        detected[section] = any(
            re.search(
                pattern,
                normalized,
                flags=re.IGNORECASE
            )
            for pattern in patterns
        )

    return detected


# ---------------------------------------------------------
# TITLE DETECTION
# ---------------------------------------------------------

def extract_title(text: str) -> str:
    """
    Attempt to identify the patent title.

    This is intentionally conservative.
    """

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip()
    ]

    for index, line in enumerate(lines):

        if re.search(
            r"^title\s*(of the invention)?\s*:?\s*$",
            line,
            flags=re.IGNORECASE
        ):

            if index + 1 < len(lines):
                return lines[index + 1].strip()

        match = re.match(
            r"^title\s*(of the invention)?\s*:\s*(.+)$",
            line,
            flags=re.IGNORECASE
        )

        if match:
            return match.group(2).strip()

    return ""


# ---------------------------------------------------------
# ABSTRACT EXTRACTION
# ---------------------------------------------------------

def extract_abstract(text: str) -> str:
    """
    Extract text between ABSTRACT and the next major heading.
    """

    pattern = re.compile(
        r"\babstract\b\s*:?\s*(.*?)(?="
        r"\n\s*(?:claims?|field of invention|"
        r"background|summary|detailed description|"
        r"brief description of drawings)\b"
        r"|$)",
        flags=re.IGNORECASE | re.DOTALL
    )

    match = pattern.search(text)

    if not match:
        return ""

    return match.group(1).strip()


# ---------------------------------------------------------
# CLAIM EXTRACTION
# ---------------------------------------------------------

def extract_claims(text: str) -> list:
    """
    Extract numbered claims from a patent document.

    Returns a list of dictionaries.
    """

    claims_section_pattern = re.compile(
        r"\bclaims?\b\s*:?\s*(.*)",
        flags=re.IGNORECASE | re.DOTALL
    )

    match = claims_section_pattern.search(text)

    if not match:
        return []

    claims_text = match.group(1)

    claim_pattern = re.compile(
        r"(?:^|\n)\s*(\d+)\.\s*(.*?)(?="
        r"\n\s*\d+\.\s*|\Z)",
        flags=re.DOTALL
    )

    claims = []

    for claim_match in claim_pattern.finditer(
        claims_text
    ):

        number = int(
            claim_match.group(1)
        )

        claim_text = normalize_text(
            claim_match.group(2)
        )

        if claim_text:

            claims.append(
                {
                    "number": number,
                    "text": claim_text
                }
            )

    return claims


# ---------------------------------------------------------
# CLAIM TYPE
# ---------------------------------------------------------

def determine_claim_type(
    claim_text: str
) -> str:

    dependency_pattern = re.compile(
        r"\b(claim|claims)\s+\d+",
        flags=re.IGNORECASE
    )

    if dependency_pattern.search(
        claim_text
    ):

        return "dependent"

    return "independent"


# ---------------------------------------------------------
# REFERENCE NUMERALS
# ---------------------------------------------------------

def extract_reference_numerals(
    text: str
) -> list:

    """
    Extract common patent reference numerals.

    Examples:
        sensor (102)
        controller 104
        106
    """

    patterns = [
        r"\(([0-9]{1,4})\)",
        r"\b(?:reference numeral|reference sign)\s*([0-9]{1,4})\b"
    ]

    numbers = set()

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        for match in matches:

            try:
                numbers.add(
                    int(match)
                )
            except ValueError:
                pass

    return sorted(numbers)


# ---------------------------------------------------------
# OBJECTIVE RULE CHECKS
# ---------------------------------------------------------

def check_title_word_count(
    title: str,
    rules: list
) -> dict | None:

    if not title:
        return None

    word_count = count_words(title)

    rule = next(
        (
            item for item in rules
            if item["rule_id"] == "FORM2-013"
        ),
        None
    )

    if not rule:
        return None

    if word_count > 15:

        return {
            "rule_id": rule["rule_id"],
            "category": "Title",
            "severity": rule["severity"],
            "status": "ISSUE",
            "finding": (
                f"Title contains {word_count} words, "
                "which exceeds the normally stated "
                "15-word limit."
            ),
            "evidence": title,
            "recommendation": rule["recommendation"],
            "source": (
                f'{rule["source_name"]} — '
                f'{rule["provision"]}'
            )
        }

    return {
        "rule_id": rule["rule_id"],
        "category": "Title",
        "severity": rule["severity"],
        "status": "PASS",
        "finding": (
            f"Title contains {word_count} words."
        ),
        "evidence": title,
        "recommendation": "",
        "source": (
            f'{rule["source_name"]} — '
            f'{rule["provision"]}'
        )
    }


def check_abstract_word_count(
    abstract: str,
    rules: list
) -> dict | None:

    if not abstract:
        return None

    word_count = count_words(
        abstract
    )

    rule = next(
        (
            item for item in rules
            if item["rule_id"] == "FORM2-015"
        ),
        None
    )

    if not rule:
        return None

    if word_count > 150:

        return {
            "rule_id": rule["rule_id"],
            "category": "Abstract",
            "severity": rule["severity"],
            "status": "ISSUE",
            "finding": (
                f"Abstract contains {word_count} words, "
                "which exceeds 150 words."
            ),
            "evidence": abstract,
            "recommendation": rule["recommendation"],
            "source": (
                f'{rule["source_name"]} — '
                f'{rule["provision"]}'
            )
        }

    return {
        "rule_id": rule["rule_id"],
        "category": "Abstract",
        "severity": rule["severity"],
        "status": "PASS",
        "finding": (
            f"Abstract contains {word_count} words."
        ),
        "evidence": abstract,
        "recommendation": "",
        "source": (
            f'{rule["source_name"]} — '
            f'{rule["provision"]}'
        )
    }


# ---------------------------------------------------------
# REQUIRED SECTION CHECKS
# ---------------------------------------------------------

def check_required_sections(
    sections: dict,
    rules: list
) -> list:

    issues = []

    required_checks = [
        (
            "claims",
            "FORM2-005",
            "Claims"
        ),
        (
            "abstract",
            "FORM2-006",
            "Abstract"
        )
    ]

    for section, rule_id, label in required_checks:

        if sections.get(section):
            continue

        rule = next(
            (
                item for item in rules
                if item["rule_id"] == rule_id
            ),
            None
        )

        if not rule:
            continue

        issues.append(
            {
                "rule_id": rule["rule_id"],
                "category": label,
                "severity": rule["severity"],
                "status": "ISSUE",
                "finding": (
                    f"{label} section could not "
                    "be detected."
                ),
                "evidence": "",
                "recommendation": (
                    rule["recommendation"]
                ),
                "source": (
                    f'{rule["source_name"]} — '
                    f'{rule["provision"]}'
                )
            }
        )

    return issues


# ---------------------------------------------------------
# COMPLETE FORM 2 ANALYSIS
# ---------------------------------------------------------

def analyze_form2_document(
    text: str
) -> dict:

    rules = load_form2_rules()

    sections = detect_sections(
        text
    )

    title = extract_title(
        text
    )

    abstract = extract_abstract(
        text
    )

    claims = extract_claims(
        text
    )

    reference_numerals = (
        extract_reference_numerals(
            text
        )
    )

    issues = []

    # Required sections
    issues.extend(
        check_required_sections(
            sections,
            rules
        )
    )

    # Title
    title_result = check_title_word_count(
        title,
        rules
    )

    if title_result:
        issues.append(
            title_result
        )

    # Abstract
    abstract_result = check_abstract_word_count(
        abstract,
        rules
    )

    if abstract_result:
        issues.append(
            abstract_result
        )

    # Claim classification
    claim_analysis = []

    for claim in claims:

        claim_type = determine_claim_type(
            claim["text"]
        )

        claim_analysis.append(
            {
                "number": claim["number"],
                "type": claim_type,
                "text": claim["text"]
            }
        )

    # Summary
    return {
        "sections": sections,
        "title": title,
        "abstract": abstract,
        "claims": claim_analysis,
        "reference_numerals": reference_numerals,
        "issues": issues,
        "statistics": {
            "claim_count": len(claim_analysis),
            "independent_claims": sum(
                1
                for claim in claim_analysis
                if claim["type"] == "independent"
            ),
            "dependent_claims": sum(
                1
                for claim in claim_analysis
                if claim["type"] == "dependent"
            ),
            "reference_numeral_count": len(
                reference_numerals
            ),
            "abstract_word_count": count_words(
                abstract
            ),
            "title_word_count": count_words(
                title
            )
        }
    }
