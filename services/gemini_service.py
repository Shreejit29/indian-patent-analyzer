import json
import os
from typing import Any

from google import genai


DEFAULT_MODEL = "gemini-2.5-flash"


def get_gemini_client(api_key: str | None = None):
    """Create and return a Gemini API client."""

    if api_key is None:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError(
            "Gemini API key not found. Configure GEMINI_API_KEY "
            "in Streamlit Secrets."
        )

    return genai.Client(api_key=api_key)


def generate_response(
    prompt: str,
    api_key: str | None = None,
    model: str = DEFAULT_MODEL,
) -> str:
    """Send a prompt to Gemini and return its text response."""

    client = get_gemini_client(api_key)

    try:
        response = client.models.generate_content(
            model=model,
            contents=prompt,
        )

        if not response.text:
            raise ValueError("Gemini returned an empty response.")

        return response.text.strip()

    except Exception as exc:
        raise RuntimeError(
            f"Gemini API request failed: {exc}"
        ) from exc


def clean_json_response(response_text: str) -> str:
    """
    Remove common Markdown code fences from Gemini JSON output.
    """

    text = response_text.strip()

    if text.startswith("```json"):
        text = text[7:]

    elif text.startswith("```"):
        text = text[3:]

    if text.endswith("```"):
        text = text[:-3]

    return text.strip()


def parse_json_response(response_text: str) -> dict[str, Any]:
    """
    Parse Gemini response as JSON.

    Raises a clear error if Gemini returns invalid JSON.
    """

    cleaned = clean_json_response(response_text)

    try:
        result = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise ValueError(
            "Gemini returned invalid JSON. "
            f"Response preview: {cleaned[:500]}"
        ) from exc

    if not isinstance(result, dict):
        raise ValueError(
            "Gemini JSON response must be an object."
        )

    return result


def analyze_patent_text(
    patent_text: str,
    rules_text: str = "",
    api_key: str | None = None,
    analysis_level: str = "Detailed",
) -> dict[str, Any]:
    """
    Analyze patent text using Gemini and return structured JSON.
    """

    if not patent_text.strip():
        raise ValueError(
            "Patent document contains no readable text."
        )

    prompt = f"""
You are the AI analysis engine for an Indian Patent Draft Analyzer.

Your task is to analyze the supplied patent document using:
1. The actual patent document.
2. The verified Indian patent rule information supplied below.
3. Careful drafting analysis.

ANALYSIS LEVEL:
{analysis_level}

IMPORTANT LEGAL SAFETY RULES:

- Do not invent Indian patent laws, sections, rules, forms, or guidelines.
- Do not fabricate citations.
- Do not say that a patent will definitely be granted or rejected.
- Clearly distinguish formal/legal requirements from drafting suggestions.
- Do not introduce new technical matter.
- Do not rewrite the invention by adding unsupported technical features.
- Identify evidence from the actual document whenever possible.
- If evidence is insufficient, say so.
- Treat this as preliminary AI-assisted analysis, not legal advice.

RULE CLASSIFICATION:

LEGAL_FORMAL_REQUIREMENT:
A requirement supported by the supplied official legal/rule source.

EXAMINATION_RISK:
A potential issue that may attract examination attention.

DRAFTING_SUGGESTION:
An improvement that may improve clarity, consistency, completeness,
or readability but is not necessarily a legal requirement.

SOURCE CONFIDENCE:

HIGH:
Directly supported by supplied official source.

MEDIUM:
Reasonable analytical inference from the document and supplied rules.

LOW:
Possible concern requiring human verification.

Return ONLY valid JSON.
Do not use Markdown.
Do not put the JSON inside a code block.

The JSON must follow this structure:

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
      "severity": "critical|high|medium|low|info",
      "confidence": "high|medium|low",
      "evidence": "",
      "explanation": "",
      "recommendation": "",
      "source": ""
    }}
  ],

  "claims": [
    {{
      "claim_number": 1,
      "claim_type": "independent|dependent|unknown",
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
      "priority": "critical|high|medium|low",
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

SCORING:

All scores must be between 0 and 100.

These are internal AI-assisted indicators only.
They are NOT official Indian Patent Office scores.

SOURCE RULE:

Only cite sources contained in the supplied rule information
or sources explicitly provided in the prompt.

VERIFIED INDIAN PATENT RULE INFORMATION:

{rules_text}

PATENT DOCUMENT:

{patent_text}
"""

    raw_response = generate_response(
        prompt=prompt,
        api_key=api_key,
    )

    return parse_json_response(raw_response)
