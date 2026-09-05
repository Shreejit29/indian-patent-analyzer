import json
import os
import re
import time
from typing import Any

from google import genai


# ============================================================
# MODEL CONFIGURATION
# ============================================================

DEFAULT_MODEL = "gemini-3.6-flash"

FALLBACK_MODELS = [
    "gemini-3.5-flash",
    "gemini-2.5-flash",
]


# ============================================================
# API KEY
# ============================================================

def get_api_key(
    api_key: str | None = None,
) -> str:

    if api_key:

        return api_key.strip()

    # --------------------------------------------------------
    # Streamlit secrets
    # --------------------------------------------------------

    try:

        import streamlit as st

        if "GEMINI_API_KEY" in st.secrets:

            key = str(
                st.secrets["GEMINI_API_KEY"]
            ).strip()

            if key:
                return key

    except Exception:

        pass

    # --------------------------------------------------------
    # Environment variable
    # --------------------------------------------------------

    key = os.getenv(
        "GEMINI_API_KEY",
        "",
    ).strip()

    if key:
        return key

    raise RuntimeError(
        "GEMINI_API_KEY was not found. "
        "Add GEMINI_API_KEY to Streamlit secrets."
    )


# ============================================================
# JSON CLEANING
# ============================================================

def clean_json_response(
    text: str,
) -> str:

    if not text:
        return ""

    text = text.strip()

    text = re.sub(
        r"^```json\s*",
        "",
        text,
        flags=re.IGNORECASE,
    )

    text = re.sub(
        r"^```\s*",
        "",
        text,
    )

    text = re.sub(
        r"\s*```$",
        "",
        text,
    )

    return text.strip()


def parse_json_response(
    text: str,
) -> dict[str, Any]:

    cleaned = clean_json_response(
        text
    )

    # Direct parsing
    try:

        result = json.loads(
            cleaned
        )

        if isinstance(
            result,
            dict,
        ):

            return result

    except json.JSONDecodeError:

        pass

    # Extract JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start >= 0 and end > start:

        candidate = cleaned[
            start:end + 1
        ]

        try:

            result = json.loads(
                candidate
            )

            if isinstance(
                result,
                dict,
            ):

                return result

        except json.JSONDecodeError:

            pass

    raise ValueError(
        "Gemini returned invalid JSON."
    )


# ============================================================
# PATENT ANALYSIS PROMPT
# ============================================================

def build_analysis_prompt(
    patent_text: str,
    context: str,
    document_type: str,
    analysis_level: str,
) -> str:

    return f"""
You are an Indian Patent Draft Analyzer AI.

Analyze the supplied patent document using the supplied
Indian patent law, rules, deterministic checks and Patent
Office Manual evidence.

You are a drafting and examination-risk assistance system.

You are NOT the Indian Patent Office and must not provide
a definitive legal determination.

==================================================
DOCUMENT INFORMATION
==================================================

Document Type:
{document_type}

Analysis Level:
{analysis_level}

==================================================
IMPORTANT SAFEGUARDS
==================================================

1. Do not fabricate facts.
2. Do not fabricate prior-art documents.
3. Do not fabricate patent numbers.
4. Do not fabricate case law.
5. Do not invent technical features.
6. Do not assume missing disclosure.
7. Distinguish clearly between:
   - Legal/formal requirement
   - Examination risk
   - Drafting suggestion
8. Section 3 screening is not a final patentability decision.
9. Section 59 issues must be treated cautiously.
10. Never guarantee grant or refusal.
11. Use the original document as the primary technical source.

==================================================
SOURCE HIERARCHY
==================================================

Use sources in this order:

1. Original patent document
2. Deterministic rule-engine analysis
3. Indian Patents Act / Rules supplied in context
4. Patent Office Manual evidence supplied in context
5. General drafting knowledge

If sources conflict, identify the conflict.

==================================================
ANALYZE
==================================================

Analyze:

- document structure
- Form 2 requirements
- title
- field of invention
- background
- objects
- summary
- detailed description
- best method
- claims
- claim clarity
- claim dependency
- antecedent basis
- support/fair basis
- unity
- abstract
- drawings/reference numerals
- Section 3 exclusions
- Section 10 requirements
- examination risks
- drafting weaknesses
- inconsistencies
- missing information
- possible objections
- recommendations

==================================================
OUTPUT
==================================================

Return ONLY valid JSON.

Use this structure:

{{
  "document_assessment": {{
    "summary": "...",
    "document_type": "...",
    "overall_assessment": "..."
  }},

  "scores": {{
    "overall_score": 0,
    "compliance_score": 0,
    "claim_score": 0,
    "drafting_quality_score": 0
  }},

  "sections": [],

  "issues": [
    {{
      "category": "LEGAL/FORMAL REQUIREMENT",
      "severity": "HIGH",
      "confidence": "HIGH",
      "title": "...",
      "description": "...",
      "recommendation": "...",
      "evidence": "..."
    }}
  ],

  "claims": [
    {{
      "claim_number": 1,
      "claim_type": "INDEPENDENT",
      "assessment": "...",
      "issues": [],
      "recommendations": []
    }}
  ],

  "abstract_analysis": {{
    "assessment": "...",
    "issues": [],
    "recommendations": []
  }},

  "reference_numeral_analysis": {{
    "assessment": "...",
    "issues": []
  }},

  "recommendations": [],

  "sources": [],

  "disclaimer": "This is automated drafting and examination-risk assistance and not legal advice or an Indian Patent Office determination."
}}

==================================================
ANALYSIS CONTEXT
==================================================

{context}

==================================================
PATENT DOCUMENT
==================================================

{patent_text}
"""


# ============================================================
# DETECT TEMPORARY CAPACITY ERRORS
# ============================================================

def is_temporary_capacity_error(
    error: Exception,
) -> bool:

    message = str(
        error
    ).lower()

    capacity_terms = [
        "503",
        "unavailable",
        "high demand",
        "temporarily",
        "no capacity",
        "service unavailable",
    ]

    return any(
        term in message
        for term in capacity_terms
    )


# ============================================================
# GEMINI REQUEST
# ============================================================

def generate_response(
    prompt: str,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
) -> str:

    key = get_api_key(
        api_key
    )

    client = genai.Client(
        api_key=key
    )

    models_to_try = [
        model
    ]

    for fallback in FALLBACK_MODELS:

        if fallback not in models_to_try:

            models_to_try.append(
                fallback
            )

    errors = []

    for current_model in models_to_try:

        # ----------------------------------------------------
        # Retry each model up to 3 times
        # ----------------------------------------------------

        max_retries = 3

        for attempt in range(
            max_retries
        ):

            try:

                response = (
                    client.models.generate_content(
                        model=current_model,
                        contents=prompt,
                    )
                )

                text = getattr(
                    response,
                    "text",
                    None,
                )

                if not text:

                    raise RuntimeError(
                        "Gemini returned an empty response."
                    )

                return text.strip()

            except Exception as exc:

                errors.append(
                    {
                        "model": current_model,
                        "attempt": attempt + 1,
                        "error": str(exc),
                    }
                )

                # ------------------------------------------------
                # Only retry temporary capacity errors
                # ------------------------------------------------

                if not is_temporary_capacity_error(
                    exc
                ):

                    raise RuntimeError(
                        "Gemini API request failed: "
                        + str(exc)
                    ) from exc

                # ------------------------------------------------
                # Exponential backoff
                # ------------------------------------------------

                if attempt < max_retries - 1:

                    delay = 2 ** attempt

                    time.sleep(
                        delay
                    )

        # ----------------------------------------------------
        # Move to fallback model
        # ----------------------------------------------------

    error_summary = "\n".join(
        [
            (
                f"Model={item['model']}, "
                f"Attempt={item['attempt']}: "
                f"{item['error']}"
            )
            for item in errors
        ]
    )

    raise RuntimeError(
        "Gemini models are temporarily unavailable "
        "or experiencing high demand.\n\n"
        "Models attempted:\n"
        + error_summary
    )


# ============================================================
# PATENT ANALYSIS
# ============================================================

def analyze_patent_text(
    patent_text: str,
    context: str = "",
    document_type: str = "Other",
    api_key: str | None = None,
    analysis_level: str = "Detailed",
) -> dict[str, Any]:

    if not patent_text or not patent_text.strip():

        raise ValueError(
            "Patent text is empty."
        )

    prompt = build_analysis_prompt(
        patent_text=patent_text,
        context=context,
        document_type=document_type,
        analysis_level=analysis_level,
    )

    response_text = generate_response(
        prompt=prompt,
        api_key=api_key,
        model=DEFAULT_MODEL,
    )

    try:

        result = parse_json_response(
            response_text
        )

    except Exception as exc:

        raise RuntimeError(
            "Gemini response could not be converted "
            "to the required JSON format: "
            + str(exc)
        ) from exc

    # --------------------------------------------------------
    # Ensure expected fields
    # --------------------------------------------------------

    result.setdefault(
        "document_assessment",
        {},
    )

    result.setdefault(
        "scores",
        {},
    )

    result.setdefault(
        "sections",
        [],
    )

    result.setdefault(
        "issues",
        [],
    )

    result.setdefault(
        "claims",
        [],
    )

    result.setdefault(
        "abstract_analysis",
        {},
    )

    result.setdefault(
        "reference_numeral_analysis",
        {},
    )

    result.setdefault(
        "recommendations",
        [],
    )

    result.setdefault(
        "sources",
        [],
    )

    result.setdefault(
        "disclaimer",
        (
            "This is automated drafting and "
            "examination-risk assistance and not "
            "legal advice."
        ),
    )

    return result
