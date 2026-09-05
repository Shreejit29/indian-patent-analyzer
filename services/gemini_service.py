import json
import os
from typing import Any

import streamlit as st
from google import genai


# =========================================================
# GEMINI CONFIGURATION
# =========================================================

DEFAULT_MODEL = "gemini-3.6-flash"


# =========================================================
# API KEY
# =========================================================

def get_gemini_api_key(
    api_key: str | None = None,
) -> str:
    """
    Get Gemini API key.

    Priority:
    1. Explicitly supplied API key
    2. Streamlit Secrets
    3. Environment variable
    """

    if api_key:
        return api_key.strip()

    # Streamlit Cloud Secrets
    try:
        secret_key = st.secrets.get("GEMINI_API_KEY")

        if secret_key:
            return str(secret_key).strip()

    except Exception:
        pass

    # Local environment variable
    environment_key = os.getenv("GEMINI_API_KEY")

    if environment_key:
        return environment_key.strip()

    raise ValueError(
        "Gemini API key not found. "
        "Add GEMINI_API_KEY to Streamlit Secrets."
    )


# =========================================================
# GEMINI CLIENT
# =========================================================

def get_gemini_client(
    api_key: str | None = None,
):
    """Create Gemini client."""

    key = get_gemini_api_key(api_key)

    return genai.Client(
        api_key=key
    )


# =========================================================
# GENERATE RESPONSE
# =========================================================

def generate_response(
    prompt: str,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
) -> str:
    """
    Generate a response using the Gemini Interactions API.
    """

    if not prompt or not prompt.strip():
        raise ValueError(
            "Gemini prompt cannot be empty."
        )

    client = get_gemini_client(api_key)

    try:

        interaction = client.interactions.create(
            model=model,
            input=prompt,
        )

        response_text = interaction.output_text

        if not response_text:
            raise ValueError(
                "Gemini returned an empty response."
            )

        return response_text.strip()

    except Exception as exc:

        raise RuntimeError(
            f"Gemini API request failed: {exc}"
        ) from exc


# =========================================================
# CLEAN JSON RESPONSE
# =========================================================

def clean_json_response(
    response_text: str,
) -> str:
    """
    Remove Markdown code fences if Gemini
    returns JSON inside a code block.
    """

    text = response_text.strip()

    if text.startswith("```json"):
        text = text[7:]

    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


# =========================================================
# PARSE JSON RESPONSE
# =========================================================

def parse_json_response(
    response_text: str,
) -> dict[str, Any]:
    """
    Parse Gemini response into a Python dictionary.
    """

    cleaned = clean_json_response(response_text)

    try:

        result = json.loads(cleaned)

    except json.JSONDecodeError as exc:

        raise ValueError(
            "Gemini returned invalid JSON. "
            f"Response preview: {cleaned[:1000]}"
        ) from exc

    if not isinstance(result, dict):

        raise ValueError(
            "Gemini JSON response must be an object."
        )

    return result


# =========================================================
# PATENT ANALYSIS
# =========================================================

def analyze_patent_text(
    patent_text: str,
    rules_text: str = "",
    context: str = "",
    api_key: str | None = None,
    analysis_level: str = "Detailed",
) -> dict[str, Any]:
    """
    Analyze an Indian patent document using Gemini.

    Parameters
    ----------
    patent_text:
        Extracted patent document text.

    rules_text:
        Verified Indian Patent Act / Rules information.

    context:
        Additional retrieved evidence, including
        Patent Office Manual material and other
        deterministic analysis context.

    api_key:
        Gemini API key.

    analysis_level:
        Basic, Detailed, or Comprehensive.
    """

    if not patent_text or not patent_text.strip():

        raise ValueError(
            "Patent document contains no readable text."
        )

    # -----------------------------------------------------
    # Optional context
    # -----------------------------------------------------

    if not context:
        context = (
            "No additional Patent Office Manual evidence "
            "was retrieved for this document."
        )

    if not rules_text:
        rules_text = (
            "No verified patent rule information was supplied."
        )

    # -----------------------------------------------------
    # Gemini prompt
    # -----------------------------------------------------

    prompt = f"""
You are the AI analysis engine for an
Indian Patent Draft Analyzer.

Your task is to analyze the supplied Indian patent document.

You MUST use the supplied sources as the primary basis
for your analysis.

==================================================
ANALYSIS LEVEL
==================================================

{analysis_level}

==================================================
SOURCE HIERARCHY
==================================================

Use the sources in this order of authority:

1. Indian Patents Act and verified statutory provisions
2. Indian Patents Rules and verified rules
3. Official Indian Patent Office guidelines
4. Patent Office Manual / procedural guidance
5. Deterministic analysis generated by the application
6. Your own patent-drafting reasoning

IMPORTANT:

The Patent Office Manual is practical/procedural guidance.
It must NOT override the Patents Act or Patents Rules.

Do not treat a drafting suggestion as a statutory requirement.

==================================================
IMPORTANT LEGAL SAFETY RULES
==================================================

- Do not invent Indian patent laws.
- Do not invent sections.
- Do not invent rules.
- Do not invent forms.
- Do not fabricate citations.
- Do not fabricate source references.
- Do not claim that a patent will definitely be granted.
- Do not claim that a patent will definitely be rejected.
- Clearly distinguish legal/formal requirements from
  examination risks and drafting suggestions.
- Do not introduce new technical matter.
- Do not add unsupported technical features.
- Base findings on the actual patent document.
- If evidence is insufficient, explicitly say so.
- Do not assume facts that are not present in the document.
- Treat this as preliminary AI-assisted analysis.
- This is not legal advice.

==================================================
ISSUE CLASSIFICATION
==================================================

LEGAL_FORMAL_REQUIREMENT:

Use this only where the issue is directly supported by
the supplied verified Indian patent law/rule information.

EXAMINATION_RISK:

Use this where the issue is a potential concern that
may attract examination attention, but is not necessarily
a confirmed statutory violation.

DRAFTING_SUGGESTION:

Use this for improvements to clarity, consistency,
structure, completeness, readability, or drafting quality.

==================================================
CONFIDENCE
==================================================

HIGH:

Directly supported by the supplied official source
and clearly applicable to the document.

MEDIUM:

Reasonable analytical inference from the document
and supplied sources.

LOW:

Possible concern requiring human verification.

==================================================
EVIDENCE REQUIREMENT
==================================================

For every significant issue:

- identify the relevant document evidence;
- explain why it matters;
- identify the supplied source where applicable;
- do not fabricate page numbers or citations;
- if the source does not directly support the finding,
  classify it as examination risk or drafting suggestion.

==================================================
PATENT DOCUMENT ANALYSIS
==================================================

Analyze, where applicable:

1. Document type
2. Title
3. Field of invention
4. Background
5. Objects
6. Summary
7. Detailed description
8. Claims
9. Abstract
10. Reference numerals
11. Internal consistency
12. Claim support
13. Claim clarity
14. Claim dependency
15. Antecedent basis
16. Claim scope
17. Unity / single invention considerations
18. Sufficiency of disclosure
19. Best method considerations
20. Abstract compliance
21. Potential Section 3 exclusions
22. Other examination risks supported by supplied sources

Do not determine patentability conclusively.

==================================================
CLAIM ANALYSIS
==================================================

For each claim, consider:

- independent/dependent status
- claim category
- technical elements
- antecedent basis
- dependency
- clarity
- succinctness
- support by description
- consistency with disclosed embodiments
- unnecessary limitations
- potentially unclear terminology
- possible examination risks

Do not rewrite claims by introducing technical matter
that is not disclosed in the patent document.

==================================================
ABSTRACT ANALYSIS
==================================================

Check:

- presence
- relationship with title
- approximate word count
- technical disclosure
- consistency with invention
- unnecessary claims of advantage
- reference numerals where applicable
- consistency with the supplied rules

==================================================
SOURCE RULE
==================================================

Only cite sources that appear in the supplied
verified rule information or supplied manual context.

Do not create URLs.

Do not create legal references that are not supplied.

==================================================
VERIFIED INDIAN PATENT RULE INFORMATION
==================================================

{rules_text}

==================================================
PATENT OFFICE MANUAL / ADDITIONAL EVIDENCE
==================================================

{context}

==================================================
PATENT DOCUMENT
==================================================

{patent_text}

==================================================
JSON OUTPUT
==================================================

Return ONLY valid JSON.

Do not use Markdown.

Do not put JSON inside a code block.

Use exactly this structure:

{{
  "document_assessment": {{
    "overall_assessment": "",
    "document_type": "",
    "summary": ""
  }},

  "scores": {{
    "overall": 0,
    "structure": 0,
    "claims": 0,
    "support": 0,
    "clarity": 0,
    "abstract": 0
  }},

  "sections": {{

    "title": {{
      "status": "",
      "assessment": ""
    }},

    "field_of_invention": {{
      "status": "",
      "assessment": ""
    }},

    "background": {{
      "status": "",
      "assessment": ""
    }},

    "objects": {{
      "status": "",
      "assessment": ""
    }},

    "summary": {{
      "status": "",
      "assessment": ""
    }},

    "detailed_description": {{
      "status": "",
      "assessment": ""
    }},

    "claims": {{
      "status": "",
      "assessment": ""
    }},

    "abstract": {{
      "status": "",
      "assessment": ""
    }}

  }},

  "issues": [
    {{
      "id": "",
      "title": "",
      "type": "LEGAL_FORMAL_REQUIREMENT",
      "category": "",
      "severity": "critical",
      "confidence": "high",
      "evidence": "",
      "explanation": "",
      "recommendation": "",
      "source": ""
    }}
  ],

  "claims": [
    {{
      "claim_number": 1,
      "claim_type": "independent",
      "category": "",
      "assessment": "",
      "issues": [],
      "recommendations": []
    }}
  ],

  "abstract_analysis": {{
    "assessment": "",
    "word_count": 0,
    "issues": [],
    "recommendations": []
  }},

  "reference_numeral_analysis": {{
    "assessment": "",
    "missing": [],
    "unused": []
  }},

  "recommendations": [
    {{
      "title": "",
      "priority": "high",
      "action": "",
      "reason": ""
    }}
  ],

  "sources": [
    {{
      "name": "",
      "authority": "",
      "reference": ""
    }}
  ],

  "disclaimer": ""
}}

==================================================
SCORING
==================================================

All scores must be integers from 0 to 100.

These are internal AI-assisted indicators.

They are NOT official Indian Patent Office scores.

Do not interpret the overall score as a probability
of patent grant or rejection.

==================================================
FINAL VALIDATION
==================================================

Before returning the JSON:

1. Ensure it is valid JSON.
2. Ensure all required top-level fields are present.
3. Ensure scores are integers from 0 to 100.
4. Ensure issue types are one of:
   - LEGAL_FORMAL_REQUIREMENT
   - EXAMINATION_RISK
   - DRAFTING_SUGGESTION
5. Do not fabricate legal citations.
6. Do not fabricate evidence.
7. Do not introduce new technical matter.
8. Ensure findings are grounded in the supplied document.
9. Distinguish statutory requirements from suggestions.
"""

    # -----------------------------------------------------
    # Gemini request
    # -----------------------------------------------------

    raw_response = generate_response(
        prompt=prompt,
        api_key=api_key,
        model=DEFAULT_MODEL,
    )

    # -----------------------------------------------------
    # JSON parsing
    # -----------------------------------------------------

    return parse_json_response(
        raw_response
    )
