import re
from typing import Any, Dict, List, Set


def normalize_text(text: str) -> str:
    """Normalize text for comparison."""
    if not text:
        return ""

    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[^\w\s.%/-]", " ", text)
    return text.strip()


def tokenize(text: str) -> Set[str]:
    """Extract meaningful tokens from text."""
    normalized = normalize_text(text)

    words = re.findall(r"\b[a-zA-Z][a-zA-Z0-9-]{2,}\b", normalized)

    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "from",
        "that",
        "this",
        "which",
        "where",
        "when",
        "into",
        "using",
        "used",
        "such",
        "said",
        "may",
        "can",
        "comprising",
        "including",
        "thereof",
        "therein",
        "thereby",
        "having",
        "provided",
        "configured",
        "based",
    }

    return {
        word
        for word in words
        if word not in stopwords and len(word) >= 3
    }


def extract_technical_terms(text: str) -> Set[str]:
    """
    Extract potentially important technical terms.

    This is deliberately conservative. It does NOT determine legal
    disclosure or support; it identifies terms that deserve review.
    """
    if not text:
        return set()

    normalized = normalize_text(text)

    terms = set()

    # Multi-word technical phrases
    phrase_patterns = [
        r"\b[a-zA-Z]+(?:\s+[a-zA-Z0-9-]+){1,3}\b",
    ]

    for pattern in phrase_patterns:
        matches = re.findall(pattern, normalized)
        for match in matches:
            words = match.split()

            if len(words) >= 2:
                meaningful = [
                    word
                    for word in words
                    if len(word) >= 3
                ]

                if len(meaningful) >= 2:
                    terms.add(" ".join(meaningful))

    # Technical-looking terms containing numbers, hyphens or units
    technical_patterns = [
        r"\b[a-zA-Z]+[-][a-zA-Z0-9-]+\b",
        r"\b[a-zA-Z]+\d+[a-zA-Z0-9-]*\b",
        r"\b\d+(?:\.\d+)?\s*(?:nm|mm|cm|m|khz|mhz|ghz|hz|v|mv|kv|a|ma|db|°c|%)\b",
    ]

    for pattern in technical_patterns:
        for match in re.findall(pattern, normalized):
            terms.add(match.strip())

    return terms


def calculate_token_overlap(
    original_text: str,
    revised_text: str,
) -> Dict[str, Any]:
    """Compare meaningful vocabulary between original and revised text."""

    original_tokens = tokenize(original_text)
    revised_tokens = tokenize(revised_text)

    if not revised_tokens:
        return {
            "original_token_count": len(original_tokens),
            "revised_token_count": 0,
            "new_token_count": 0,
            "new_token_ratio": 0.0,
            "new_tokens": [],
        }

    new_tokens = revised_tokens - original_tokens

    ratio = len(new_tokens) / len(revised_tokens)

    return {
        "original_token_count": len(original_tokens),
        "revised_token_count": len(revised_tokens),
        "new_token_count": len(new_tokens),
        "new_token_ratio": round(ratio, 4),
        "new_tokens": sorted(new_tokens),
    }


def compare_technical_terms(
    original_text: str,
    revised_text: str,
) -> Dict[str, Any]:
    """
    Compare technical-looking terms.

    A new term does NOT automatically mean new matter.
    It is simply flagged for human/legal review.
    """

    original_terms = extract_technical_terms(original_text)
    revised_terms = extract_technical_terms(revised_text)

    new_terms = revised_terms - original_terms

    return {
        "original_term_count": len(original_terms),
        "revised_term_count": len(revised_terms),
        "new_term_count": len(new_terms),
        "new_terms": sorted(new_terms),
    }


def compare_claims(
    original_claims: List[Any],
    revised_claims: List[Any],
) -> Dict[str, Any]:
    """
    Compare original and revised claims.

    The function accepts either strings or dictionaries containing
    claim_text.
    """

    def get_claim_text(claim: Any) -> str:
        if isinstance(claim, str):
            return claim

        if isinstance(claim, dict):
            return str(
                claim.get("claim_text")
                or claim.get("text")
                or ""
            )

        return ""

    original = [
        get_claim_text(claim)
        for claim in original_claims
    ]

    revised = [
        get_claim_text(claim)
        for claim in revised_claims
    ]

    original_normalized = {
        normalize_text(claim)
        for claim in original
        if claim.strip()
    }

    changed_claims = []

    for index, claim in enumerate(revised, start=1):
        normalized = normalize_text(claim)

        if not normalized:
            continue

        if normalized not in original_normalized:
            changed_claims.append(
                {
                    "claim_number": index,
                    "claim_text": claim,
                    "status": "CHANGED_OR_NEW",
                }
            )

    return {
        "original_claim_count": len(original),
        "revised_claim_count": len(revised),
        "changed_claim_count": len(changed_claims),
        "changed_claims": changed_claims,
    }


def assess_new_matter(
    original_text: str,
    revised_text: str,
    original_claims: List[Any] | None = None,
    revised_claims: List[Any] | None = None,
) -> Dict[str, Any]:
    """
    Perform a conservative new-matter screening.

    IMPORTANT:
    This is NOT a legal determination under Section 59.
    It is a drafting-assistance and review mechanism.
    """

    original_text = original_text or ""
    revised_text = revised_text or ""

    token_comparison = calculate_token_overlap(
        original_text,
        revised_text,
    )

    technical_comparison = compare_technical_terms(
        original_text,
        revised_text,
    )

    claim_comparison = compare_claims(
        original_claims or [],
        revised_claims or [],
    )

    flags = []

    if technical_comparison["new_term_count"] > 0:
        flags.append(
            {
                "type": "NEW_TECHNICAL_TERMS",
                "severity": "REVIEW",
                "message": (
                    "The revised document contains technical terms "
                    "not detected in the original document. "
                    "Verify that these terms are already disclosed "
                    "or supported by the original specification."
                ),
                "items": technical_comparison["new_terms"],
            }
        )

    if token_comparison["new_token_ratio"] > 0.20:
        flags.append(
            {
                "type": "HIGH_VOCABULARY_CHANGE",
                "severity": "REVIEW",
                "message": (
                    "A relatively large amount of new vocabulary "
                    "appears in the revised document. Review carefully "
                    "for possible introduction of new subject matter."
                ),
                "ratio": token_comparison["new_token_ratio"],
            }
        )

    if claim_comparison["changed_claim_count"] > 0:
        flags.append(
            {
                "type": "CLAIM_CHANGES",
                "severity": "HIGH",
                "message": (
                    "One or more claims differ from the original "
                    "claims. Each amended claim should be checked "
                    "against the original disclosure and claim scope."
                ),
                "claims": claim_comparison["changed_claims"],
            }
        )

    if flags:
        overall_status = "HUMAN_REVIEW_REQUIRED"
    else:
        overall_status = "NO_OBVIOUS_NEW_MATTER_SIGNAL"

    return {
        "overall_status": overall_status,
        "section_59_basis": (
            "Amendment must not result in a specification claiming "
            "or describing matter not in substance disclosed or shown "
            "before amendment."
        ),
        "token_comparison": token_comparison,
        "technical_term_comparison": technical_comparison,
        "claim_comparison": claim_comparison,
        "flags": flags,
        "legal_determination": False,
        "human_review_required": bool(flags),
        "disclaimer": (
            "This automated comparison is not a legal determination "
            "of compliance with Section 59 of the Patents Act, 1970. "
            "New wording or terminology may be legitimate clarification "
            "or correction. Substantive disclosure and claim scope "
            "must be reviewed by a patent professional."
        ),
    }


def get_new_matter_summary(result: Dict[str, Any]) -> Dict[str, Any]:
    """Return a compact summary suitable for the Streamlit UI."""

    return {
        "status": result.get(
            "overall_status",
            "UNKNOWN",
        ),
        "new_technical_terms": result.get(
            "technical_term_comparison",
            {},
        ).get("new_term_count", 0),
        "changed_claims": result.get(
            "claim_comparison",
            {},
        ).get("changed_claim_count", 0),
        "review_required": result.get(
            "human_review_required",
            True,
        ),
        "flag_count": len(
            result.get("flags", [])
        ),
    }
