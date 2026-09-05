import json
import os
from typing import Any

import streamlit as st
from google import genai


# ---------------------------------------------------------
# GEMINI CONFIGURATION
# ---------------------------------------------------------

DEFAULT_MODEL = "gemini-3.6-flash"


# ---------------------------------------------------------
# API KEY
# ---------------------------------------------------------

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
        return api_key

    # Streamlit Cloud Secrets
    try:
        secret_key = st.secrets.get(
            "GEMINI_API_KEY"
        )

        if secret_key:
            return secret_key

    except Exception:
        pass

    # Local environment variable
    environment_key = os.getenv(
        "GEMINI_API_KEY"
    )

    if environment_key:
        return environment_key

    raise ValueError(
        "Gemini API key not found. "
        "Add GEMINI_API_KEY to Streamlit Secrets."
    )


# ---------------------------------------------------------
# GEMINI CLIENT
# ---------------------------------------------------------

def get_gemini_client(
    api_key: str | None = None,
):
    """Create Gemini client."""

    key = get_gemini_api_key(api_key)

    return genai.Client(
        api_key=key
    )


# ---------------------------------------------------------
# GENERATE RESPONSE
# ---------------------------------------------------------

def generate_response(
    prompt: str,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
) -> str:
    """
    Generate a response using the Gemini Interactions API.
    """

    if not prompt.strip():
        raise ValueError(
            "Gemini prompt cannot be empty."
        )

    client = get_gemini_client(
        api_key
    )

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


# ---------------------------------------------------------
# CLEAN JSON
# ---------------------------------------------------------

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


# ---------------------------------------------------------
# PARSE JSON
# ---------------------------------------------------------

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

    if not isinstance(result, dict):

        raise ValueError(
            "Gemini JSON response must be an object."
        )

    return result


# ---------------------------------------------------------
# PATENT ANALYSIS
# ---------------------------------------------------------

def analyze_patent_text(
    patent_text: str,
    rules_text: str = "",
    api_key: str | None = None,
    analysis_level: str = "Detailed",
) -> dict[str, Any]:
    """
    Analyze an Indian patent document using Gemini 3.6 Flash.
    """

    if not patent_text.strip():

        raise ValueError(
            "Patent document contains no readable text."
        )

    prompt = f"""
You are the AI analysis engine for an
Indian Patent Draft Analyzer.

Your task is to analyze the supplied patent document using:

1. The actual patent document.
2. The verified Indian patent rule information.
3. Careful patent drafting analysis.

ANALYSIS LEVEL:
{analysis_level}

==================================================
IMPORTANT LEGAL SAFETY RULES
==================================================

- Do not invent Indian patent laws.
- Do not invent sections.
- Do not invent rules.
- Do not invent forms.
- Do not fabricate citations.
- Do not claim that a patent will definitely be granted.
- Do not claim that a patent will definitely be rejected.
- Clearly distinguish legal/formal requirements from
  drafting suggestions.
- Do not introduce new technical matter.
- Do not add unsupported technical features.
- Base findings on the actual patent document.
- If evidence is insufficient, explicitly say so.
- Treat this as preliminary AI-assisted analysis.
- This is not legal advice.

==================================================
ISSUE CLASSIFICATION
==================================================

LEGAL_FORMAL_REQUIREMENT:
A requirement directly supported by the supplied
official Indian patent rule information.

EXAMINATION_RISK:
A potential issue that may attract examination
attention.

DRAFTING_SUGGESTION:
A drafting improvement that may improve clarity,
consistency, completeness, or readability.

==================================================
CONFIDENCE
==================================================

HIGH:
Directly supported by supplied official source.

MEDIUM:
Reasonable analytical inference from the document.

LOW:
Possible concern requiring human verification.

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

==================================================
SOURCE RULE
==================================================

Only cite sources contained in the supplied
verified rule information.

Do not create URLs or legal references yourself.

==================================================
VERIFIED INDIAN PATENT RULE INFORMATION
==================================================

{rules_text}

==================================================
PATENT DOCUMENT
==================================================

{patent_text}
"""

    raw_response = generate_response(
        prompt=prompt,
        api_key=api_key,
        model=DEFAULT_MODEL,
    )

    return parse_json_response(
        raw_response
    )
