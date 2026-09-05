import os

from google import genai
from google.genai import types


# ---------------------------------------------------------
# GEMINI CLIENT
# ---------------------------------------------------------

def get_gemini_client(api_key: str | None = None):
    """
    Create and return a Gemini API client.

    The API key should be supplied through Streamlit
    Secrets in production.
    """

    if api_key is None:
        api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise ValueError(
            "Gemini API key not found. "
            "Configure GEMINI_API_KEY in Streamlit Secrets."
        )

    return genai.Client(
        api_key=api_key
    )


# ---------------------------------------------------------
# BASIC GEMINI REQUEST
# ---------------------------------------------------------

def generate_response(
    prompt: str,
    api_key: str | None = None,
    model: str = "gemini-2.5-flash"
) -> str:
    """
    Send a prompt to Gemini and return the response text.
    """

    client = get_gemini_client(api_key)

    try:

        response = client.models.generate_content(
            model=model,
            contents=prompt
        )

        if not response.text:
            raise ValueError(
                "Gemini returned an empty response."
            )

        return response.text.strip()

    except Exception as exc:

        raise RuntimeError(
            f"Gemini API request failed: {exc}"
        ) from exc


# ---------------------------------------------------------
# STRUCTURED PATENT ANALYSIS
# ---------------------------------------------------------

def analyze_patent_text(
    patent_text: str,
    rules_text: str = "",
    api_key: str | None = None
) -> str:
    """
    Analyze patent text using Gemini.

    This is the initial analysis function.
    The detailed system prompt and rule engine will
    be added in later files.
    """

    if not patent_text.strip():

        raise ValueError(
            "Patent document contains no readable text."
        )

    prompt = f"""
You are an Indian Patent Draft Analysis Assistant.

Analyze the following patent draft.

Your task is to identify:

1. Patent document structure
2. Title
3. Field of invention
4. Background
5. Objects
6. Summary
7. Detailed description
8. Claims
9. Abstract
10. Potential drafting issues
11. Specification/claim consistency issues
12. Potential examination concerns

IMPORTANT:

- Do not invent Indian patent rules.
- Do not invent legal provisions.
- Do not introduce new technical matter.
- Do not state that a patent will definitely be granted or rejected.
- Clearly distinguish legal/formal requirements from drafting suggestions.
- Treat this as a preliminary AI-assisted analysis.

AVAILABLE RULE INFORMATION:

{rules_text}

PATENT DOCUMENT:

{patent_text}
"""

    return generate_response(
        prompt=prompt,
        api_key=api_key
    )
