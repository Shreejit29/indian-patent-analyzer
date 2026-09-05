import re
from typing import Any


# ---------------------------------------------------------
# BASIC TEXT UTILITIES
# ---------------------------------------------------------

def normalize_claim_text(text: str) -> str:
    """Normalize whitespace in a claim."""

    if not text:
        return ""

    return re.sub(
        r"\s+",
        " ",
        text
    ).strip()


# ---------------------------------------------------------
# CLAIM DEPENDENCY
# ---------------------------------------------------------

def extract_claim_dependencies(
    claim_text: str
) -> list[int]:
    """
    Identify claims referenced by a dependent claim.

    Examples:
        "The apparatus of claim 1..."
        "The method as claimed in claims 1 or 2..."
    """

    if not claim_text:
        return []

    pattern = re.compile(
        r"\bclaims?\s+"
        r"((?:\d+\s*(?:,|and|or)?\s*)+)",
        flags=re.IGNORECASE
    )

    dependencies = []

    for match in pattern.finditer(
        claim_text
    ):

        numbers = re.findall(
            r"\d+",
            match.group(1)
        )

        for number in numbers:

            number_int = int(number)

            if number_int not in dependencies:
                dependencies.append(
                    number_int
                )

    return sorted(
        dependencies
    )


# ---------------------------------------------------------
# CLAIM TYPE
# ---------------------------------------------------------

def identify_claim_type(
    claim_text: str
) -> str:
    """
    Classify a claim as independent or dependent.

    This is a preliminary rule-based classification.
    """

    dependencies = extract_claim_dependencies(
        claim_text
    )

    if dependencies:
        return "dependent"

    return "independent"


# ---------------------------------------------------------
# CLAIM OPENING
# ---------------------------------------------------------

def identify_claim_category(
    claim_text: str
) -> str:
    """
    Identify the likely category of a claim.

    This is only a preliminary classification.
    """

    text = claim_text.lower()

    if re.search(
        r"\bcomputer[- ]implemented\b",
        text
    ):
        return "computer-implemented"

    if re.search(
        r"\bmethod\b|\bprocess\b",
        text
    ):
        return "method/process"

    if re.search(
        r"\bsystem\b|\bapparatus\b|\bdevice\b",
        text
    ):
        return "apparatus/system/device"

    if re.search(
        r"\bcomposition\b|\bformulation\b",
        text
    ):
        return "composition/formulation"

    if re.search(
        r"\bkit\b",
        text
    ):
        return "kit"

    return "other"


# ---------------------------------------------------------
# ELEMENT EXTRACTION
# ---------------------------------------------------------

def extract_claim_elements(
    claim_text: str
) -> list[str]:
    """
    Extract likely technical elements from a claim.

    This is intentionally conservative.
    Gemini will perform the deeper semantic analysis later.
    """

    if not claim_text:
        return []

    text = normalize_claim_text(
        claim_text
    )

    elements = []

    # Common structural connectors
    patterns = [
        r"\ba\s+([A-Za-z][A-Za-z0-9_-]{2,50})",
        r"\ban\s+([A-Za-z][A-Za-z0-9_-]{2,50})",
        r"\bthe\s+([A-Za-z][A-Za-z0-9_-]{2,50})"
    ]

    for pattern in patterns:

        matches = re.findall(
            pattern,
            text,
            flags=re.IGNORECASE
        )

        for match in matches:

            cleaned = match.strip(
                " ,.;:"
            )

            if (
                len(cleaned) > 2
                and cleaned.lower()
                not in {
                    "method",
                    "system",
                    "device",
                    "apparatus",
                    "step",
                    "first",
                    "second",
                    "third"
                }
            ):

                if cleaned not in elements:

                    elements.append(
                        cleaned
                    )

    return elements[:50]


# ---------------------------------------------------------
# ANTECEDENT BASIS
# ---------------------------------------------------------

def check_antecedent_basis(
    claim_text: str
) -> list[dict[str, Any]]:
    """
    Identify possible antecedent-basis issues.

    This is a heuristic check and must be reviewed by
    the semantic AI layer.
    """

    if not claim_text:
        return []

    issues = []

    # Capture phrases such as:
    # "the controller"
    # "the sensor"
    # "said controller"

    definite_terms = re.findall(
        r"\b(?:the|said)\s+"
        r"([A-Za-z][A-Za-z0-9_-]{2,50})",
        claim_text,
        flags=re.IGNORECASE
    )

    indefinite_terms = re.findall(
        r"\b(?:a|an)\s+"
        r"([A-Za-z][A-Za-z0-9_-]{2,50})",
        claim_text,
        flags=re.IGNORECASE
    )

    introduced = {
        term.lower()
        for term in indefinite_terms
    }

    checked = set()

    for term in definite_terms:

        term_lower = term.lower()

        if term_lower in checked:
            continue

        checked.add(
            term_lower
        )

        # Ignore common non-component words
        if term_lower in {
            "method",
            "system",
            "apparatus",
            "device",
            "step",
            "first",
            "second",
            "third",
            "one",
            "more",
            "response",
            "accordance"
        }:
            continue

        if term_lower not in introduced:

            issues.append(
                {
                    "type": "possible_antecedent_basis",
                    "term": term,
                    "finding": (
                        f'The term "{term}" is used with '
                        "definite wording but no clear "
                        "earlier indefinite introduction "
                        "was detected by the rule-based check."
                    ),
                    "severity": "MEDIUM"
                }
            )

    return issues


# ---------------------------------------------------------
# DEPENDENCY VALIDATION
# ---------------------------------------------------------

def validate_claim_dependencies(
    claims: list[dict]
) -> list[dict[str, Any]]:
    """
    Check whether dependent claims reference claims
    that actually exist and precede them.
    """

    issues = []

    claim_numbers = {
        claim["number"]
        for claim in claims
    }

    for claim in claims:

        number = claim["number"]

        dependencies = extract_claim_dependencies(
            claim["text"]
        )

        if not dependencies:
            continue

        for dependency in dependencies:

            if dependency not in claim_numbers:

                issues.append(
                    {
                        "claim": number,
                        "type": "missing_parent_claim",
                        "finding": (
                            f"Claim {number} refers to "
                            f"claim {dependency}, but "
                            "that claim was not detected "
                            "in the document."
                        ),
                        "severity": "HIGH"
                    }
                )

            elif dependency >= number:

                issues.append(
                    {
                        "claim": number,
                        "type": "claim_dependency_order",
                        "finding": (
                            f"Claim {number} appears to "
                            f"refer to claim {dependency}, "
                            "which does not precede it."
                        ),
                        "severity": "HIGH"
                    }
                )

    return issues


# ---------------------------------------------------------
# CLAIM-BY-CLAIM ANALYSIS
# ---------------------------------------------------------

def analyze_single_claim(
    claim: dict
) -> dict[str, Any]:
    """
    Prepare structured information for one claim.
    """

    claim_number = claim.get(
        "number"
    )

    claim_text = normalize_claim_text(
        claim.get("text", "")
    )

    claim_type = identify_claim_type(
        claim_text
    )

    category = identify_claim_category(
        claim_text
    )

    dependencies = extract_claim_dependencies(
        claim_text
    )

    elements = extract_claim_elements(
        claim_text
    )

    antecedent_issues = check_antecedent_basis(
        claim_text
    )

    return {
        "claim_number": claim_number,
        "claim_type": claim_type,
        "category": category,
        "text": claim_text,
        "dependencies": dependencies,
        "elements": elements,
        "antecedent_issues": antecedent_issues
    }


# ---------------------------------------------------------
# COMPLETE CLAIM ANALYSIS
# ---------------------------------------------------------

def analyze_claims(
    claims: list[dict]
) -> dict[str, Any]:
    """
    Analyze all claims in a patent draft.
    """

    if not claims:

        return {
            "claims": [],
            "issues": [
                {
                    "type": "claims_not_detected",
                    "finding": (
                        "No claims were detected in "
                        "the uploaded document."
                    ),
                    "severity": "CRITICAL"
                }
            ],
            "statistics": {
                "total": 0,
                "independent": 0,
                "dependent": 0
            }
        }

    analyzed_claims = []

    for claim in claims:

        analyzed_claims.append(
            analyze_single_claim(
                claim
            )
        )

    dependency_issues = (
        validate_claim_dependencies(
            claims
        )
    )

    antecedent_issues = []

    for claim in analyzed_claims:

        for issue in claim[
            "antecedent_issues"
        ]:

            antecedent_issues.append(
                {
                    "claim": claim[
                        "claim_number"
                    ],
                    **issue
                }
            )

    independent_count = sum(
        1
        for claim in analyzed_claims
        if claim["claim_type"]
        == "independent"
    )

    dependent_count = sum(
        1
        for claim in analyzed_claims
        if claim["claim_type"]
        == "dependent"
    )

    return {
        "claims": analyzed_claims,

        "issues": (
            dependency_issues
            + antecedent_issues
        ),

        "statistics": {
            "total": len(
                analyzed_claims
            ),
            "independent": independent_count,
            "dependent": dependent_count
        }
    }


# ---------------------------------------------------------
# CLAIM-SPECIFICATION SUPPORT PREPARATION
# ---------------------------------------------------------

def prepare_support_search(
    analyzed_claim: dict
) -> list[str]:
    """
    Return important claim terms that should be searched
    in the specification.

    The actual semantic support determination will be
    performed later using Gemini.
    """

    elements = analyzed_claim.get(
        "elements",
        []
    )

    return [
        element
        for element in elements
        if len(element) >= 3
    ]
