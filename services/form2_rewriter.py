import json
from typing import Any, Dict, List

from services.gemini_service import generate_response
from services.new_matter_checker import assess_new_matter


DEFAULT_REWRITE_MODEL = "gemini-3.6-flash"


def clean_json_response(text: str) -> str:
    """Remove common Markdown wrappers around JSON."""

    if not text:
        return ""

    text = text.strip()

    if text.startswith("```json"):
        text = text[7:]

    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


def parse_json_response(text: str) -> Dict[str, Any]:
    """Parse Gemini JSON safely."""

    cleaned = clean_json_response(text)

    try:
        result = json.loads(cleaned)

        if isinstance(result, dict):
            return result

    except json.JSONDecodeError:
        pass

    # Try to recover JSON object embedded in text.
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start >= 0 and end > start:
        try:
            result = json.loads(
                cleaned[start:end + 1]
            )

            if isinstance(result, dict):
                return result

        except json.JSONDecodeError:
            pass

    raise ValueError(
        "Gemini did not return valid JSON."
    )


def build_rewrite_prompt(
    original_text: str,
    document_type: str,
    analysis_level: str,
    analysis_context: str,
) -> str:
    """Build the Form 2 rewriting prompt."""

    return f"""
You are an Indian patent drafting and prosecution assistant.

Your task is to prepare a proposed revised Form 2 Complete Specification
based ONLY on the applicant's existing disclosure.

This is a DRAFTING ASSISTANCE task.

Do NOT create new technical subject matter.

IMPORTANT LEGAL SAFEGUARD:

The proposed revision must respect Section 59 of the Patents Act, 1970.

An amendment should not result in the specification claiming or describing
matter not in substance disclosed or shown in the specification before
amendment.

Claims must also remain within the permissible scope of the original
claims where Section 59 applies.

The output must therefore be treated as a proposed draft requiring
human patent-professional review.

==================================================
SOURCE HIERARCHY
==================================================

Use information in this order:

1. Original Form 2 text supplied by the applicant.
2. Deterministic analysis of the original document.
3. Indian Patents Act / Rules information supplied in the context.
4. Patent Office Manual guidance supplied in the context.
5. General drafting knowledge only for wording, organization and clarity.

Never invent technical facts.

==================================================
WHAT YOU MAY CHANGE
==================================================

You MAY:

- improve grammar;
- improve sentence structure;
- improve patent drafting language;
- reorganize existing disclosure;
- remove unnecessary repetition;
- improve clarity;
- improve consistency;
- improve antecedent basis;
- improve claim dependency wording;
- improve section organization;
- improve title wording when supported by the invention;
- improve abstract wording;
- correct obvious drafting errors;
- make terminology consistent;
- identify unclear or unsupported passages;
- flag passages requiring human verification.

You MUST NOT:

- invent components;
- invent materials;
- invent dimensions;
- invent experimental results;
- invent advantages;
- invent performance data;
- invent embodiments;
- invent alternatives;
- invent operating conditions;
- invent technical relationships;
- add unsupported claim limitations;
- introduce new inventive concepts;
- broaden the invention using information absent from the original disclosure.

If a useful patent-drafting statement is not supported by the original
document, DO NOT add it.

==================================================
FORM 2 STRUCTURE
==================================================

Prepare the revised document using, where supported:

1. Title
2. Field of Invention
3. Background
4. Objects of the Invention
5. Summary of the Invention
6. Brief Description of Drawings
7. Detailed Description
8. Claims
9. Abstract

Do not force a section to contain information that does not exist.

==================================================
TITLE
==================================================

The title should accurately identify the invention.

Do not introduce a new technical concept merely to improve the title.

==================================================
FIELD OF INVENTION
==================================================

Describe the technical field using information already present in the
original document.

==================================================
BACKGROUND
==================================================

Improve clarity and patent style.

Do not invent prior-art documents, publications, dates, products or
technical disadvantages.

Do not make unsupported statements that something is "known", "widely
used", "conventional" or "prior art".

==================================================
OBJECTS
==================================================

Objects must be derived from the original disclosure.

Do not add an advantage merely because it would normally appear in a
patent specification.

==================================================
SUMMARY
==================================================

Summarize the disclosed invention.

Do not expand its scope.

==================================================
DETAILED DESCRIPTION
==================================================

Preserve the technical disclosure.

Improve:

- terminology;
- sequence;
- references;
- clarity;
- consistency;
- relationship between components;
- explanation of operation.

Do not create missing technical details.

==================================================
CLAIMS
==================================================

Claims require special caution.

Do not add technical limitations that were absent from the original
claims/specification.

Do not broaden claims merely to make them appear stronger.

Check:

- independent/dependent relationship;
- antecedent basis;
- clarity;
- consistency;
- unnecessary duplication;
- claim numbering;
- support in the specification.

If a claim appears unsupported or potentially problematic, retain the
safest supported formulation and flag it for human review.

==================================================
ABSTRACT
==================================================

Prepare a concise abstract based only on disclosed material.

Do not introduce new technical information.

Follow the applicable Indian patent requirements supplied in the context.

==================================================
NEW MATTER
==================================================

Before finalizing the answer, internally compare the proposed revision
with the original text.

If there is uncertainty whether something constitutes new matter:

1. DO NOT confidently add it.
2. Prefer the original disclosure.
3. Flag the issue for HUMAN REVIEW.

==================================================
OUTPUT
==================================================

Return ONLY valid JSON.

Use this structure:

{{
  "rewrite_status": "COMPLETED",
  "document_type": "{document_type}",

  "revision_summary": [
    "..."
  ],

  "new_matter_safeguard": {{
    "status": "PASS_OR_REVIEW_REQUIRED",
    "reason": "...",
    "suspected_new_matter": []
  }},

  "human_review_required": true,

  "revised_form2": {{
    "title": "...",
    "field_of_invention": "...",
    "background": "...",
    "objects": [],
    "summary": "...",
    "brief_description_of_drawings": "...",
    "detailed_description": "...",
    "claims": [
      {{
        "claim_number": 1,
        "claim_text": "...",
        "claim_type": "INDEPENDENT",
        "status": "REVISED"
      }}
    ],
    "abstract": "..."
  }},

  "section_review": [
    {{
      "section": "Title",
      "status": "PASS",
      "comments": "..."
    }}
  ],

  "change_log": [
    {{
      "section": "Claims",
      "change": "...",
      "reason": "...",
      "new_matter_risk": "LOW"
    }}
  ],

  "compliance_review": {{
    "form2_structure": "PASS_OR_REVIEW_REQUIRED",
    "section_10": "PASS_OR_REVIEW_REQUIRED",
    "section_59": "PASS_OR_REVIEW_REQUIRED",
    "claims": "PASS_OR_REVIEW_REQUIRED",
    "abstract": "PASS_OR_REVIEW_REQUIRED"
  }},

  "disclaimer": "..."
}}

==================================================
ORIGINAL DOCUMENT
==================================================

{original_text}

==================================================
ANALYSIS CONTEXT
==================================================

{analysis_context}

==================================================
DOCUMENT TYPE
==================================================

{document_type}

==================================================
ANALYSIS LEVEL
==================================================

{analysis_level}
"""


def rewrite_form2(
    original_text: str,
    analysis_context: str = "",
    document_type: str = "Form 2 Complete Specification",
    analysis_level: str = "Detailed",
    api_key: str | None = None,
    model: str = DEFAULT_REWRITE_MODEL,
) -> Dict[str, Any]:
    """
    Generate a proposed revised Form 2 and run a deterministic
    new-matter screening comparison.
    """

    if not original_text or not original_text.strip():
        raise ValueError(
            "Original Form 2 text is empty."
        )

    prompt = build_rewrite_prompt(
        original_text=original_text,
        document_type=document_type,
        analysis_level=analysis_level,
        analysis_context=analysis_context,
    )

    response_text = generate_response(
        prompt=prompt,
        api_key=api_key,
        model=model,
    )

    result = parse_json_response(response_text)

    # ------------------------------------------------------------
    # Validate minimum structure
    # ------------------------------------------------------------

    required_fields = [
        "rewrite_status",
        "revised_form2",
        "new_matter_safeguard",
        "human_review_required",
    ]

    missing_fields = [
        field
        for field in required_fields
        if field not in result
    ]

    if missing_fields:
        raise ValueError(
            "Rewrite response is missing required fields: "
            + ", ".join(missing_fields)
        )

    revised_form2 = result.get(
        "revised_form2",
        {},
    )

    if not isinstance(revised_form2, dict):
        raise ValueError(
            "revised_form2 must be a JSON object."
        )

    # ------------------------------------------------------------
    # Ensure claims list exists
    # ------------------------------------------------------------

    claims = revised_form2.get(
        "claims",
        [],
    )

    if not isinstance(claims, list):
        claims = []

    revised_form2["claims"] = claims

    # ------------------------------------------------------------
    # Ensure review/change-log lists exist
    # ------------------------------------------------------------

    if not isinstance(
        result.get("section_review"),
        list,
    ):
        result["section_review"] = []

    if not isinstance(
        result.get("change_log"),
        list,
    ):
        result["change_log"] = []

    if not isinstance(
        result.get("revision_summary"),
        list,
    ):
        result["revision_summary"] = []

    # ------------------------------------------------------------
    # Convert revised Form 2 to text
    # ------------------------------------------------------------

    revised_text = revised_form2_to_text(
        result
    )

    # ------------------------------------------------------------
    # Extract original claims when available
    # ------------------------------------------------------------

    original_claims = []

    # The analysis context may contain deterministic claim data,
    # but we intentionally do not rely on it for the legal comparison.
    # The original text remains the primary source.

    original_claims = extract_claims_from_text(
        original_text
    )

    revised_claims = [
        claim.get("claim_text", "")
        if isinstance(claim, dict)
        else str(claim)
        for claim in claims
    ]

    # ------------------------------------------------------------
    # Deterministic Section 59 screening
    # ------------------------------------------------------------

    new_matter_check = assess_new_matter(
        original_text=original_text,
        revised_text=revised_text,
        original_claims=original_claims,
        revised_claims=revised_claims,
    )

    result["new_matter_check"] = new_matter_check

    # ------------------------------------------------------------
    # Reconcile Gemini and deterministic results
    # ------------------------------------------------------------

    deterministic_review_required = (
        new_matter_check.get(
            "human_review_required",
            True,
        )
    )

    gemini_review_required = bool(
        result.get(
            "human_review_required",
            True,
        )
    )

    result["human_review_required"] = (
        deterministic_review_required
        or gemini_review_required
    )

    if deterministic_review_required:
        result["new_matter_safeguard"][
            "status"
        ] = "REVIEW_REQUIRED"

        result["new_matter_safeguard"][
            "reason"
        ] = (
            "Automated comparison detected differences "
            "requiring human review under the Section 59 "
            "no-new-matter safeguard."
        )

    # ------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------

    result["rewrite_engine"] = {
        "model": model,
        "analysis_level": analysis_level,
        "new_matter_checker": True,
        "section_59_screening": True,
        "legal_determination": False,
    }

    return result


def extract_claims_from_text(
    text: str,
) -> List[str]:
    """
    Extract a basic claims section from original Form 2 text.

    This is intentionally conservative and is only used for comparison.
    """

    if not text:
        return []

    lines = text.splitlines()

    claims_start = None

    for index, line in enumerate(lines):
        normalized = line.strip().lower()

        if normalized in {
            "claims",
            "claims:",
            "what is claimed is:",
            "what is claimed:",
        }:
            claims_start = index + 1
            break

        if (
            "claims" in normalized
            and len(normalized) < 80
        ):
            claims_start = index + 1
            break

    if claims_start is None:
        return []

    claim_lines = lines[claims_start:]

    claims = []

    current_claim = []

    for line in claim_lines:

        stripped = line.strip()

        if not stripped:
            continue

        # Detect numbered claims.
        if (
            stripped[:1].isdigit()
            and (
                "." in stripped[:4]
                or ")" in stripped[:4]
            )
        ):
            if current_claim:
                claims.append(
                    " ".join(current_claim).strip()
                )

            current_claim = [
                stripped
            ]

        else:
            current_claim.append(stripped)

    if current_claim:
        claims.append(
            " ".join(current_claim).strip()
        )

    return claims


def revised_form2_to_text(
    rewrite_result: Dict[str, Any],
) -> str:
    """
    Convert structured rewrite JSON into readable Form 2 text.
    """

    form2 = rewrite_result.get(
        "revised_form2",
        {},
    )

    sections = []

    title = form2.get(
        "title",
        "",
    ).strip()

    if title:
        sections.append(
            "TITLE\n"
            + title
        )

    field = form2.get(
        "field_of_invention",
        "",
    ).strip()

    if field:
        sections.append(
            "FIELD OF INVENTION\n"
            + field
        )

    background = form2.get(
        "background",
        "",
    ).strip()

    if background:
        sections.append(
            "BACKGROUND\n"
            + background
        )

    objects = form2.get(
        "objects",
        [],
    )

    if isinstance(objects, list):
        object_text = "\n".join(
            f"{index}. {item}"
            for index, item in enumerate(
                objects,
                start=1,
            )
            if str(item).strip()
        )
    else:
        object_text = str(objects)

    if object_text.strip():
        sections.append(
            "OBJECTS OF THE INVENTION\n"
            + object_text
        )

    summary = form2.get(
        "summary",
        "",
    ).strip()

    if summary:
        sections.append(
            "SUMMARY OF THE INVENTION\n"
            + summary
        )

    drawings = form2.get(
        "brief_description_of_drawings",
        "",
    ).strip()

    if drawings:
        sections.append(
            "BRIEF DESCRIPTION OF DRAWINGS\n"
            + drawings
        )

    detailed = form2.get(
        "detailed_description",
        "",
    ).strip()

    if detailed:
        sections.append(
            "DETAILED DESCRIPTION\n"
            + detailed
        )

    claims = form2.get(
        "claims",
        [],
    )

    claim_texts = []

    if isinstance(claims, list):
        for index, claim in enumerate(
            claims,
            start=1,
        ):
            if isinstance(claim, dict):
                number = claim.get(
                    "claim_number",
                    index,
                )

                text = claim.get(
                    "claim_text",
                    "",
                )

                if text:
                    claim_texts.append(
                        f"{number}. {text}"
                    )

            elif str(claim).strip():
                claim_texts.append(
                    f"{index}. {claim}"
                )

    if claim_texts:
        sections.append(
            "CLAIMS\n"
            + "\n".join(claim_texts)
        )

    abstract = form2.get(
        "abstract",
        "",
    ).strip()

    if abstract:
        sections.append(
            "ABSTRACT\n"
            + abstract
        )

    return "\n\n".join(
        sections
    ).strip()


def get_rewrite_summary(
    rewrite_result: Dict[str, Any],
) -> Dict[str, Any]:
    """Return compact rewrite information for the UI."""

    new_matter_check = rewrite_result.get(
        "new_matter_check",
        {},
    )

    claim_comparison = new_matter_check.get(
        "claim_comparison",
        {},
    )

    return {
        "rewrite_status": rewrite_result.get(
            "rewrite_status",
            "UNKNOWN",
        ),
        "new_matter_status": new_matter_check.get(
            "overall_status",
            "UNKNOWN",
        ),
        "human_review_required": rewrite_result.get(
            "human_review_required",
            True,
        ),
        "flag_count": len(
            new_matter_check.get(
                "flags",
                [],
            )
        ),
        "changed_claims": claim_comparison.get(
            "changed_claim_count",
            0,
        ),
        "revised_claim_count": len(
            rewrite_result.get(
                "revised_form2",
                {},
            ).get(
                "claims",
                [],
            )
        ),
        "change_count": len(
            rewrite_result.get(
                "change_log",
                [],
            )
        ),
    }
