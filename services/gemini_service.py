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
    1. Explicit API key
    2. Streamlit Secrets
    3. Environment variable
    """

    if api_key:
        return api_key.strip()

    # -----------------------------------------------------
    # Streamlit Cloud Secrets
    # -----------------------------------------------------

    try:

        secret_key = st.secrets.get(
            "GEMINI_API_KEY"
        )

        if secret_key:

            return str(
                secret_key
            ).strip()

    except Exception:
        pass

    # -----------------------------------------------------
    # Environment variable
    # -----------------------------------------------------

    environment_key = os.getenv(
        "GEMINI_API_KEY"
    )

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
    """
    Create Gemini client.
    """

    key = get_gemini_api_key(
        api_key
    )

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

    client = get_gemini_client(
        api_key
    )

    try:

        interaction = (
            client.interactions.create(
                model=model,
                input=prompt,
            )
        )

        response_text = (
            interaction.output_text
        )

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
# CLEAN JSON
# =========================================================

def clean_json_response(
    response_text: str,
) -> str:
    """
    Remove Markdown code fences if Gemini
    returns JSON inside a code block.
    """

    text = response_text.strip()

    if text.startswith(
        "```json"
    ):

        text = text[7:]

    elif text.startswith(
        "```"
    ):

        text = text[3:]

    if text.endswith(
        "```"
    ):

        text = text[:-3]

    return text.strip()


# =========================================================
# PARSE JSON
# =========================================================

def parse_json_response(
    response_text: str,
) -> dict[str, Any]:
    """
    Parse Gemini response into a Python dictionary.
    """

    cleaned = clean_json_response(
        response_text
    )

    try:

        result = json.loads(
            cleaned
        )

    except json.JSONDecodeError as exc:

        raise ValueError(
            "Gemini returned invalid JSON. "
            f"Response preview: {cleaned[:1000]}"
        ) from exc

    if not isinstance(
        result,
        dict,
    ):

        raise ValueError(
            "Gemini JSON response must be an object."
        )

    return result


# =========================================================
# PATENT ANALYSIS
# =========================================================

def analyze_patent_text(
    patent_text: str,
    context: str = "",
    document_type: str = "Other",
    api_key: str | None = None,
    analysis_level: str = "Detailed",
) -> dict[str, Any]:
    """
    Analyze an Indian patent document using Gemini.

    Parameters
    ----------
    patent_text:
        Extracted patent document text.

    context:
        Complete analysis context prepared by analyzer.py.
        This includes:

        - Form 2 rules
        - Patent Act / Rules database
        - deterministic rule analysis
        - claim analysis
        - Patent Office Manual evidence
        - source hierarchy

    document_type:
        Type selected by the user in the Streamlit interface.

    api_key:
        Gemini API key.

    analysis_level:
        Basic, Detailed, or Comprehensive.
    """

    if not patent_text or not patent_text.strip():

        raise ValueError(
            "Patent document contains no readable text."
        )

    if not context:

        context = (
            "No additional analysis context was supplied."
        )

    # =====================================================
    # GEMINI PROMPT
    # =====================================================

    prompt = f"""
You are the AI analysis engine for an
Indian Patent Draft Analyzer.

You analyze Indian patent documents using the supplied
patent document and the verified knowledge/context
prepared by the application.

==================================================
DOCUMENT TYPE
==================================================

{document_type}

==================================================
ANALYSIS LEVEL
==================================================

{analysis_level}

==================================================
SOURCE HIERARCHY
==================================================

The supplied context contains information from multiple
sources.

Use the following hierarchy:

1. Patents Act, 1970
2. Applicable Patents Rules
3. Official amendments / Gazette notifications
4. Official Patent Office guidelines
5. Patent Office Manual
6. Deterministic application analysis
7. Drafting suggestions

If two sources appear to conflict:

- do not silently resolve the conflict;
- identify the conflict;
- prefer the applicable statutory/official source;
- state that human verification of the current official
  source is required.

The Patent Office Manual is procedural/practical guidance.
It does NOT have the force of legislation and must not
override the Patents Act or Patents Rules.

==================================================
IMPORTANT LEGAL SAFETY RULES
==================================================

- Do not invent Indian patent laws.
- Do not invent sections.
- Do not invent rules.
- Do not invent forms.
- Do not fabricate case law.
- Do not fabricate citations.
- Do not fabricate URLs.
- Do not fabricate Patent Office Manual page numbers.
- Do not claim that a patent will definitely be granted.
- Do not claim that a patent will definitely be rejected.
- Do not introduce new technical matter.
- Do not add unsupported technical features.
- Do not silently modify the applicant's invention.
- Base findings on the actual patent document.
- If evidence is insufficient, explicitly say so.
- Distinguish statutory requirements from examination risks.
- Distinguish examination risks from drafting suggestions.
- Treat this as preliminary AI-assisted analysis.
- This is not legal advice.

==================================================
ISSUE CLASSIFICATION
==================================================

LEGAL_FORMAL_REQUIREMENT

Use this only when the issue is directly supported by
the supplied authoritative Indian patent law/rule information.

EXAMINATION_RISK

Use this when the issue may attract examination attention
or require clarification, but is not necessarily a confirmed
statutory violation.

DRAFTING_SUGGESTION

Use this for improvements in:

- clarity
- consistency
- precision
- completeness
- readability
- claim drafting
- specification organization

==================================================
CONFIDENCE
==================================================

HIGH

Directly supported by the supplied official source and
clearly applicable to the document.

MEDIUM

Reasonable analytical inference from the patent document
and supplied sources.

LOW

Possible concern requiring human verification.

==================================================
DOCUMENT ANALYSIS
==================================================

Analyze the document as applicable to its selected type.

Consider:

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
14. Claim succinctness
15. Claim dependency
16. Antecedent basis
17. Claim scope
18. Sufficiency of disclosure
19. Best method considerations
20. Unity / single invention considerations
21. Abstract requirements
22. Potential Section 3 exclusions
23. Other examination risks supported by the supplied sources

Do not determine patentability conclusively.

==================================================
CLAIM ANALYSIS
==================================================

For each claim, where claims are available, consider:

- claim number
- independent/dependent status
- claim category
- technical elements
- antecedent basis
- dependency
- clarity
- succinctness
- support by description
- consistency with disclosed embodiments
- potentially unnecessary limitations
- unclear terminology
- possible examination risks

Do not introduce technical matter that is not disclosed
in the patent document.

==================================================
ABSTRACT ANALYSIS
==================================================

Where an abstract exists, assess:

- presence
- title relationship
- approximate word count
- technical disclosure
- consistency with the invention
- unnecessary matter
- reference numerals where applicable
- compliance with supplied rules

==================================================
SOURCE RULE
==================================================

Use only sources supplied in the context.

Do not invent a source.

Do not invent a citation.

Do not invent a legal provision.

If the supplied context does not establish a point,
state that human verification is required.

==================================================
APPLICATION-GENERATED CONTEXT
==================================================

The following context was prepared by the patent
analysis application.

{context}

==================================================
PATENT DOCUMENT
==================================================

The following is the extracted text of the actual
patent document being analyzed.

{patent_text}

==================================================
OUTPUT REQUIREMENT
==================================================

Return ONLY valid JSON.

Do not use Markdown.

Do not put JSON inside a code block.

Do not add explanatory text before or after the JSON.

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

The scores must NOT be interpreted as:

- probability of patent grant;
- probability of patent rejection;
- legal validity;
- enforceability.

==================================================
VALIDATION BEFORE RESPONSE
==================================================

Before returning the response:

1. Ensure the response is valid JSON.
2. Ensure all required top-level fields are present.
3. Ensure scores are integers from 0 to 100.
4. Ensure issue types use only:
   LEGAL_FORMAL_REQUIREMENT
   EXAMINATION_RISK
   DRAFTING_SUGGESTION
5. Do not fabricate legal citations.
6. Do not fabricate evidence.
7. Do not fabricate sources.
8. Do not introduce new technical matter.
9. Ensure findings are grounded in the supplied patent document.
10. Distinguish statutory requirements from suggestions.
11. Distinguish examination risks from drafting suggestions.
12. Do not claim guaranteed grant or rejection.
"""

    # =====================================================
    # GEMINI REQUEST
    # =====================================================

    raw_response = generate_response(
        prompt=prompt,
        api_key=api_key,
        model=DEFAULT_MODEL,
    )

    # =====================================================
    # JSON PARSING
    # =====================================================

    return parse_json_response(
        raw_response
    )
