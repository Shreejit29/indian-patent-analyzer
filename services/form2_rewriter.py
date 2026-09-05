import json
from typing import Any, Dict, List

from services.gemini_service import generate_response


# ============================================================
# FORM 2 REWRITER
# ============================================================

DEFAULT_REWRITE_MODEL = "gemini-3.6-flash"


# ============================================================
# JSON CLEANING
# ============================================================

def clean_json_response(
    response_text: str,
) -> str:
    """
    Remove Markdown code fences from Gemini JSON output.
    """

    text = response_text.strip()

    if text.startswith("```json"):
        text = text[7:]

    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


def parse_json_response(
    response_text: str,
) -> Dict[str, Any]:
    """
    Parse Gemini response as JSON.
    """

    cleaned = clean_json_response(
        response_text
    )

    try:

        result = json.loads(
            cleaned
        )

    except json.JSONDecodeError as error:

        raise ValueError(
            "Gemini returned invalid JSON while "
            "generating the revised Form 2. "
            f"Response preview: {cleaned[:1500]}"
        ) from error

    if not isinstance(
        result,
        dict,
    ):

        raise ValueError(
            "Form 2 rewrite response must be a JSON object."
        )

    return result


# ============================================================
# REWRITE PROMPT
# ============================================================

def build_rewrite_prompt(
    original_text: str,
    document_type: str,
    analysis_level: str,
    analysis_context: str,
) -> str:
    """
    Build the controlled Form 2 rewriting prompt.
    """

    return f"""
You are an expert AI-assisted Indian patent drafting engine.

Your task is to prepare a PROPOSED REVISED FORM 2 COMPLETE
SPECIFICATION based strictly on the supplied original patent
document.

This is a drafting/revision task.

It is NOT a legal opinion and does NOT guarantee patentability,
grant, validity, or compliance.

============================================================
DOCUMENT INFORMATION
============================================================

Document Type:
{document_type}

Analysis Level:
{analysis_level}

============================================================
PRIMARY OBJECTIVE
============================================================

Improve the supplied patent specification by:

1. Improving organization.
2. Improving clarity.
3. Improving technical consistency.
4. Improving patent drafting quality.
5. Improving description-to-claim consistency.
6. Improving claim clarity and structure.
7. Improving abstract structure.
8. Addressing identified drafting/formal concerns.
9. Preserving the disclosed invention.
10. Aligning the proposed drafting with the supplied
    Indian patent rules and guidance.

============================================================
CRITICAL NO-NEW-MATTER RULE
============================================================

THIS IS THE MOST IMPORTANT RULE.

DO NOT INTRODUCE NEW TECHNICAL MATTER.

Every technical feature in the revised specification must
be supported by the original patent document.

Do NOT:

- invent components;
- invent dimensions;
- invent materials;
- invent numerical ranges;
- invent experimental results;
- invent advantages;
- invent performance values;
- invent technical effects;
- invent algorithms;
- invent processing steps;
- invent embodiments;
- invent examples;
- invent manufacturing methods;
- invent biological characteristics;
- invent chemical properties;
- invent test results;
- invent prior-art statements.

If an improvement would require new technical information,
DO NOT add that information.

Instead:

- preserve the original wording; OR
- flag the matter for human review.

============================================================
SECTION 59 SAFEGUARD
============================================================

The proposed revision must not intentionally introduce
matter not in substance disclosed in the original
specification.

Treat Section 59 as a strict drafting safeguard.

Do not expand the technical scope merely to make the
patent appear stronger.

============================================================
SOURCE HIERARCHY
============================================================

Use the supplied analysis context according to this hierarchy:

1. Patents Act
2. Applicable Patents Rules
3. Official amendments / Gazette material
4. Official Patent Office guidelines
5. Patent Office Manual
6. Deterministic application analysis
7. Drafting reasoning

The Patent Office Manual is practical/procedural guidance.
It must not be treated as legislation.

============================================================
WHAT MAY BE REWRITTEN
============================================================

The following may be improved where supported:

- grammar;
- sentence structure;
- terminology consistency;
- paragraph organization;
- section organization;
- repetition;
- ambiguous drafting;
- antecedent references;
- claim dependency wording;
- claim structure;
- abstract wording;
- reference numeral consistency;
- transitions between sections;
- description organization.

============================================================
WHAT MUST NOT BE CHANGED
============================================================

Do not change:

- the identity of the invention;
- the disclosed technical concept;
- technical components;
- disclosed relationships;
- disclosed operating steps;
- disclosed materials;
- disclosed parameters;
- disclosed numerical ranges;
- disclosed examples;
- disclosed embodiments;

unless the change is purely linguistic and preserves
the original technical meaning.

============================================================
FORM 2 STRUCTURE
============================================================

Where the original document supports the information,
organize the proposed specification into appropriate
sections such as:

1. TITLE OF THE INVENTION

2. FIELD OF THE INVENTION

3. BACKGROUND OF THE INVENTION

4. OBJECTS OF THE INVENTION

5. SUMMARY OF THE INVENTION

6. BRIEF DESCRIPTION OF THE DRAWINGS

7. DETAILED DESCRIPTION OF THE INVENTION

8. CLAIMS

9. ABSTRACT

Do not manufacture a section's substantive content if
the original document does not disclose it.

If a section is absent and cannot safely be reconstructed,
mark it as:

"[HUMAN INPUT REQUIRED]"

rather than inventing content.

============================================================
TITLE
============================================================

Improve the title only if supported by the invention.

The title should identify the specific subject matter.

Avoid unnecessary promotional language.

Follow the supplied Rule 13 guidance regarding title
length and abstract requirements.

============================================================
BACKGROUND
============================================================

Improve the background by organizing information already
present in the original document.

Do not invent:

- prior-art documents;
- patent numbers;
- publications;
- dates;
- competitors;
- technical disadvantages;
- market facts.

If the original contains unsupported assertions, preserve
their substance cautiously or flag them for review.

============================================================
OBJECTS
============================================================

Extract and organize objects that are actually disclosed.

Do not invent new objectives merely because they would
make the specification appear stronger.

============================================================
SUMMARY
============================================================

The summary must accurately reflect the disclosed invention.

Do not introduce technical features that appear only in
the claims unless those features are supported elsewhere
in the original specification.

============================================================
DETAILED DESCRIPTION
============================================================

Improve:

- logical order;
- terminology;
- component relationships;
- operation sequence;
- embodiment organization;
- reference numeral consistency.

Do not add technical information.

If the description does not sufficiently support a claim,
DO NOT invent supporting disclosure.

Instead flag:

"[SUPPORT GAP — HUMAN REVIEW REQUIRED]"

============================================================
CLAIMS
============================================================

Claims are critical.

Improve claims only using matter already disclosed.

Check:

- claim numbering;
- independent/dependent structure;
- dependency;
- antecedent basis;
- clarity;
- succinctness;
- consistency with description;
- unnecessary repetition;
- terminology consistency;
- scope consistency.

Do NOT broaden claims by adding undisclosed features.

Do NOT narrow claims by adding new technical limitations.

Do NOT create a technical feature merely because it could
potentially improve patentability.

If a claim cannot safely be improved:

preserve the original claim and flag it.

============================================================
ABSTRACT
============================================================

Prepare a concise abstract based only on disclosed matter.

The abstract should:

- identify the technical field;
- summarize the invention;
- identify technical advancement where supported;
- identify principal use where supported;
- remain consistent with the specification;
- avoid speculative use;
- use applicable reference signs where appropriate.

Keep the proposed abstract at or below 150 words.

============================================================
REFERENCE NUMERALS
============================================================

Preserve existing reference numerals.

Do not invent new reference numerals unless the original
document clearly establishes the corresponding feature.

If reference numerals are inconsistent:

flag the inconsistency for human review.

============================================================
HUMAN REVIEW FLAGS
============================================================

Use a human-review flag whenever:

- technical support is insufficient;
- a claim appears broader than the description;
- a proposed change could introduce new matter;
- a section cannot be reconstructed safely;
- a reference numeral is ambiguous;
- the original disclosure is internally inconsistent;
- the legal significance cannot be determined reliably.

============================================================
ORIGINAL PATENT DOCUMENT
============================================================

{original_text}

============================================================
APPLICATION ANALYSIS AND SOURCE CONTEXT
============================================================

{analysis_context}

============================================================
OUTPUT FORMAT
============================================================

Return ONLY valid JSON.

Do not use Markdown.

Use exactly this structure:

{{
  "rewrite_status": "completed",
  "document_type": "{document_type}",

  "revision_summary": {{
    "overall": "",
    "changes_made": [],
    "limitations": []
  }},

  "new_matter_safeguard": {{
    "status": "passed",
    "assessment": "",
    "potential_new_matter": []
  }},

  "human_review_required": [],

  "revised_form2": {{
    "title": "",

    "field_of_invention": "",

    "background": "",

    "objects": [],

    "summary": "",

    "brief_description_of_drawings": "",

    "detailed_description": "",

    "claims": [
      {{
        "claim_number": 1,
        "claim_text": "",
        "claim_type": "independent",
        "status": "revised"
      }}
    ],

    "abstract": ""
  }},

  "section_review": {{
    "title": {{
      "status": "",
      "changes": ""
    }},

    "field_of_invention": {{
      "status": "",
      "changes": ""
    }},

    "background": {{
      "status": "",
      "changes": ""
    }},

    "objects": {{
      "status": "",
      "changes": ""
    }},

    "summary": {{
      "status": "",
      "changes": ""
    }},

    "brief_description_of_drawings": {{
      "status": "",
      "changes": ""
    }},

    "detailed_description": {{
      "status": "",
      "changes": ""
    }},

    "claims": {{
      "status": "",
      "changes": ""
    }},

    "abstract": {{
      "status": "",
      "changes": ""
    }}
  }},

  "change_log": [
    {{
      "section": "",
      "change_type": "language",
      "original_issue": "",
      "change_made": "",
      "reason": "",
      "new_matter_risk": "low"
    }}
  ],

  "compliance_review": {{
    "section_10_review": "",
    "section_10_5_claim_review": "",
    "rule_13_review": "",
    "section_59_review": ""
  }},

  "disclaimer": ""
}}

============================================================
FINAL VALIDATION
============================================================

Before returning JSON:

1. Verify that every technical feature in the revised
   document is supported by the original document.

2. Verify that no new technical matter was introduced.

3. Verify that claims do not contain unsupported features.

4. Verify that the abstract is no more than 150 words.

5. Verify that claim numbering is sequential.

6. Verify that dependent claims refer only to appropriate
   earlier claims.

7. Verify terminology consistency.

8. Verify that reference numerals were not arbitrarily
   invented.

9. Verify that unsupported sections are marked for
   human review.

10. Verify that legal requirements are not represented
    as guaranteed compliance.

11. Verify that Section 59 concerns are explicitly flagged
    where applicable.

12. Return valid JSON only.
"""


# ============================================================
# FORM 2 REWRITE
# ============================================================

def rewrite_form2(
    original_text: str,
    analysis_context: str = "",
    document_type: str = "Form 2 Complete Specification",
    analysis_level: str = "Detailed",
    api_key: str | None = None,
    model: str = DEFAULT_REWRITE_MODEL,
) -> Dict[str, Any]:
    """
    Generate a proposed revised Form 2 Complete Specification.

    The function is deliberately conservative and instructs
    Gemini not to introduce new technical matter.
    """

    if not original_text or not original_text.strip():

        raise ValueError(
            "Original patent document contains no readable text."
        )

    prompt = build_rewrite_prompt(
        original_text=original_text,
        document_type=document_type,
        analysis_level=analysis_level,
        analysis_context=analysis_context,
    )

    raw_response = generate_response(
        prompt=prompt,
        api_key=api_key,
        model=model,
    )

    result = parse_json_response(
        raw_response
    )

    # --------------------------------------------------------
    # Basic structural validation
    # --------------------------------------------------------

    required_fields = [
        "rewrite_status",
        "revision_summary",
        "new_matter_safeguard",
        "human_review_required",
        "revised_form2",
        "section_review",
        "change_log",
        "compliance_review",
        "disclaimer",
    ]

    missing_fields = [
        field
        for field in required_fields
        if field not in result
    ]

    if missing_fields:

        raise ValueError(
            "Form 2 rewrite response is missing required "
            f"fields: {', '.join(missing_fields)}"
        )

    revised_form2 = result.get(
        "revised_form2",
        {},
    )

    if not isinstance(
        revised_form2,
        dict,
    ):

        raise ValueError(
            "revised_form2 must be a JSON object."
        )

    # --------------------------------------------------------
    # Ensure claims are a list
    # --------------------------------------------------------

    claims = revised_form2.get(
        "claims",
        [],
    )

    if not isinstance(
        claims,
        list,
    ):

        revised_form2["claims"] = []

    # --------------------------------------------------------
    # Ensure human review list
    # --------------------------------------------------------

    if not isinstance(
        result.get(
            "human_review_required"
        ),
        list,
    ):

        result["human_review_required"] = []

    # --------------------------------------------------------
    # Ensure change log list
    # --------------------------------------------------------

    if not isinstance(
        result.get(
            "change_log"
        ),
        list,
    ):

        result["change_log"] = []

    # --------------------------------------------------------
    # Add system metadata
    # --------------------------------------------------------

    result["rewrite_engine"] = {
        "model": model,
        "mode": "conservative_no_new_matter",
        "source": "original_document_plus_supplied_analysis",
    }

    return result


# ============================================================
# CONVERT REVISED FORM 2 TO TEXT
# ============================================================

def revised_form2_to_text(
    rewrite_result: Dict[str, Any],
) -> str:
    """
    Convert structured revised Form 2 JSON into readable text.
    """

    form2 = rewrite_result.get(
        "revised_form2",
        {},
    )

    sections = []

    # --------------------------------------------------------
    # Title
    # --------------------------------------------------------

    title = form2.get(
        "title",
        "",
    )

    if title:
        sections.append(
            "TITLE OF THE INVENTION\n\n"
            + str(title).strip()
        )

    # --------------------------------------------------------
    # Field
    # --------------------------------------------------------

    field = form2.get(
        "field_of_invention",
        "",
    )

    if field:
        sections.append(
            "FIELD OF THE INVENTION\n\n"
            + str(field).strip()
        )

    # --------------------------------------------------------
    # Background
    # --------------------------------------------------------

    background = form2.get(
        "background",
        "",
    )

    if background:
        sections.append(
            "BACKGROUND OF THE INVENTION\n\n"
            + str(background).strip()
        )

    # --------------------------------------------------------
    # Objects
    # --------------------------------------------------------

    objects = form2.get(
        "objects",
        [],
    )

    if objects:

        object_lines = []

        if isinstance(
            objects,
            list,
        ):

            for index, item in enumerate(
                objects,
                start=1,
            ):

                object_lines.append(
                    f"{index}. {str(item).strip()}"
                )

        else:

            object_lines.append(
                str(objects).strip()
            )

        sections.append(
            "OBJECTS OF THE INVENTION\n\n"
            + "\n".join(object_lines)
        )

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------

    summary = form2.get(
        "summary",
        "",
    )

    if summary:
        sections.append(
            "SUMMARY OF THE INVENTION\n\n"
            + str(summary).strip()
        )

    # --------------------------------------------------------
    # Drawings
    # --------------------------------------------------------

    drawings = form2.get(
        "brief_description_of_drawings",
        "",
    )

    if drawings:
        sections.append(
            "BRIEF DESCRIPTION OF THE DRAWINGS\n\n"
            + str(drawings).strip()
        )

    # --------------------------------------------------------
    # Detailed description
    # --------------------------------------------------------

    description = form2.get(
        "detailed_description",
        "",
    )

    if description:
        sections.append(
            "DETAILED DESCRIPTION OF THE INVENTION\n\n"
            + str(description).strip()
        )

    # --------------------------------------------------------
    # Claims
    # --------------------------------------------------------

    claims = form2.get(
        "claims",
        [],
    )

    if claims:

        claim_lines = []

        for claim in claims:

            if isinstance(
                claim,
                dict,
            ):

                number = claim.get(
                    "claim_number",
                    len(claim_lines) + 1,
                )

                claim_text = claim.get(
                    "claim_text",
                    "",
                )

                if claim_text:

                    claim_lines.append(
                        f"{number}. {str(claim_text).strip()}"
                    )

            elif isinstance(
                claim,
                str,
            ):

                claim_lines.append(
                    claim.strip()
                )

        if claim_lines:

            sections.append(
                "CLAIMS\n\n"
                + "\n".join(claim_lines)
            )

    # --------------------------------------------------------
    # Abstract
    # --------------------------------------------------------

    abstract = form2.get(
        "abstract",
        "",
    )

    if abstract:
        sections.append(
            "ABSTRACT\n\n"
            + str(abstract).strip()
        )

    return "\n\n\n".join(
        sections
    )


# ============================================================
# REWRITE SUMMARY
# ============================================================

def get_rewrite_summary(
    rewrite_result: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Return a compact summary suitable for the Streamlit UI.
    """

    safeguard = rewrite_result.get(
        "new_matter_safeguard",
        {},
    )

    return {
        "status": rewrite_result.get(
            "rewrite_status",
            "unknown",
        ),

        "new_matter_status": safeguard.get(
            "status",
            "unknown",
        ),

        "human_review_count": len(
            rewrite_result.get(
                "human_review_required",
                [],
            )
        ),

        "change_count": len(
            rewrite_result.get(
                "change_log",
                [],
            )
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
    }
