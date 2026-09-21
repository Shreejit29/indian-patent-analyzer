"""
Gemini AI Service V3
====================

Purpose
-------
AI reasoning/orchestration layer for the Indian Patent Analyzer.

Design principle
----------------
Gemini must NOT be treated as the source of truth.

Deterministic layers:
    document_parser.py
    claim_analyzer.py
    evidence_engine.py
    prior_art.py
    rule_engine.py
    scoring.py

AI layer:
    - explanation
    - summarization
    - structured reasoning
    - claim interpretation
    - evidence-based drafting
    - reviewer assistance

Security
--------
API keys are loaded from:
    1. Streamlit secrets: GEMINI_API_KEY
    2. Environment variable: GEMINI_API_KEY

Never hard-code an API key in this file.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

GEMINI_SERVICE_VERSION = "3.0.0"

DEFAULT_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-2.5-flash",
)


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def _truncate(text: str, max_chars: int = 12000) -> str:
    text = _clean_text(text)

    if len(text) <= max_chars:
        return text

    return text[:max_chars] + "\n...[TRUNCATED]..."


def _safe_json_loads(text: str) -> Optional[Dict[str, Any]]:
    """
    Attempt to extract JSON from Gemini output.

    Handles:
        pure JSON
        ```json ... ```
        surrounding explanatory text
    """

    if not text:
        return None

    cleaned = text.strip()

    # Markdown fenced JSON
    fenced = re.search(
        r"```(?:json)?\s*(.*?)\s*```",
        cleaned,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if fenced:
        cleaned = fenced.group(1).strip()

    try:
        result = json.loads(cleaned)

        if isinstance(result, dict):
            return result

    except Exception:
        pass

    # Try locating the first JSON object
    start = cleaned.find("{")
    end = cleaned.rfind("}")

    if start >= 0 and end > start:
        candidate = cleaned[start:end + 1]

        try:
            result = json.loads(candidate)

            if isinstance(result, dict):
                return result

        except Exception:
            pass

    return None


def _get_streamlit_secret(name: str) -> Optional[str]:
    """
    Read a secret without making Streamlit a hard dependency.
    """

    try:
        import streamlit as st

        value = st.secrets.get(name)

        if value:
            return str(value)

    except Exception:
        pass

    return None


def get_api_key() -> Optional[str]:
    """
    Resolve Gemini API key.

    Priority:
        Streamlit secrets
        Environment variable
    """

    key = _get_streamlit_secret("GEMINI_API_KEY")

    if key:
        return key.strip()

    key = os.getenv("GEMINI_API_KEY")

    if key:
        return key.strip()

    return None


# ---------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------

@dataclass
class AIResponse:
    success: bool
    text: str
    model: str
    timestamp: str
    structured: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    provider: str = "Google Gemini"
    service_version: str = GEMINI_SERVICE_VERSION

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AIRequest:
    task: str
    context: str
    system_instruction: Optional[str] = None
    temperature: float = 0.1
    max_output_tokens: int = 4096

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------
# Gemini client
# ---------------------------------------------------------------------

class GeminiService:
    """
    Production-oriented wrapper around Google Gemini.

    The implementation supports the modern google-genai SDK.

    Installation:

        pip install google-genai

    API key:

        GEMINI_API_KEY

    or Streamlit:

        .streamlit/secrets.toml

        GEMINI_API_KEY = "your-key"
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
    ):
        self.api_key = (
            api_key
            or get_api_key()
        )

        self.model = (
            model
            or DEFAULT_MODEL
        )

        self.client = None
        self.available = False
        self.initialization_error = None

        self._initialize()

    # -----------------------------------------------------------------
    # Initialization
    # -----------------------------------------------------------------

    def _initialize(self) -> None:

        if not self.api_key:
            self.initialization_error = (
                "GEMINI_API_KEY was not found. "
                "Configure it using Streamlit secrets or "
                "the GEMINI_API_KEY environment variable."
            )
            return

        try:

            from google import genai

            self.client = genai.Client(
                api_key=self.api_key
            )

            self.available = True

        except ImportError:

            self.initialization_error = (
                "google-genai is not installed. "
                "Install it using: pip install google-genai"
            )

        except Exception as exc:

            self.initialization_error = str(exc)

    # -----------------------------------------------------------------
    # Status
    # -----------------------------------------------------------------

    def status(self) -> Dict[str, Any]:

        return {
            "service": "GeminiService",
            "version": GEMINI_SERVICE_VERSION,
            "provider": "Google Gemini",
            "model": self.model,
            "available": self.available,
            "error": self.initialization_error,
            "timestamp": _utc_now(),
        }

    # -----------------------------------------------------------------
    # Core generation
    # -----------------------------------------------------------------

    def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
        max_output_tokens: int = 4096,
    ) -> AIResponse:

        if not self.available:

            return AIResponse(
                success=False,
                text="",
                model=self.model,
                timestamp=_utc_now(),
                error=self.initialization_error
                or "Gemini service unavailable.",
            )

        prompt = _clean_text(prompt)

        if not prompt:

            return AIResponse(
                success=False,
                text="",
                model=self.model,
                timestamp=_utc_now(),
                error="Empty prompt.",
            )

        try:

            from google.genai import types

            config = types.GenerateContentConfig(
                temperature=temperature,
                max_output_tokens=max_output_tokens,
                system_instruction=(
                    system_instruction
                    if system_instruction
                    else None
                ),
            )

            response = self.client.models.generate_content(
                model=self.model,
                contents=prompt,
                config=config,
            )

            text = getattr(
                response,
                "text",
                None,
            )

            if not text:

                text = ""

            return AIResponse(
                success=True,
                text=str(text).strip(),
                model=self.model,
                timestamp=_utc_now(),
            )

        except Exception as exc:

            return AIResponse(
                success=False,
                text="",
                model=self.model,
                timestamp=_utc_now(),
                error=str(exc),
            )

    # -----------------------------------------------------------------
    # Structured generation
    # -----------------------------------------------------------------

    def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.0,
        max_output_tokens: int = 4096,
    ) -> AIResponse:

        json_instruction = """
Return ONLY valid JSON.

Do not use Markdown.
Do not use ```json fences.
Do not add explanations before or after the JSON.
"""

        if system_instruction:
            system_instruction = (
                system_instruction
                + "\n\n"
                + json_instruction
            )
        else:
            system_instruction = json_instruction

        response = self.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=temperature,
            max_output_tokens=max_output_tokens,
        )

        if not response.success:
            return response

        structured = _safe_json_loads(
            response.text
        )

        if structured is None:

            return AIResponse(
                success=False,
                text=response.text,
                model=response.model,
                timestamp=response.timestamp,
                error=(
                    "Gemini returned output that could not "
                    "be parsed as valid JSON."
                ),
            )

        response.structured = structured

        return response

    # -----------------------------------------------------------------
    # Patent-specific reasoning
    # -----------------------------------------------------------------

    def summarize_patent(
        self,
        patent_text: str,
    ) -> AIResponse:

        prompt = f"""
Analyze the following patent document.

Create a concise technical summary covering:

1. Technical field
2. Problem addressed
3. Existing limitation/problem
4. Proposed solution
5. Key technical components
6. Important operating relationships
7. Main advantages
8. Independent-claim concepts
9. Potentially important technical terminology

Do not invent facts.

Only use information present in the supplied document.

PATENT DOCUMENT:
{_truncate(patent_text, 30000)}
"""

        system = """
You are a patent-analysis assistant.

Your job is to explain the supplied patent text accurately.

Rules:
- Do not invent technical features.
- Do not infer unsupported facts.
- Clearly distinguish explicit disclosure from interpretation.
- Do not provide a legal conclusion.
- Preserve technical terminology.
"""

        return self.generate(
            prompt,
            system_instruction=system,
            temperature=0.1,
            max_output_tokens=5000,
        )

    # -----------------------------------------------------------------

    def analyze_claim(
        self,
        claim_text: str,
        specification_text: str = "",
    ) -> AIResponse:

        prompt = f"""
Analyze this patent claim.

CLAIM:
{_truncate(claim_text, 12000)}

SPECIFICATION CONTEXT:
{_truncate(specification_text, 18000)}

Identify:

1. Claim category
2. Core inventive concept
3. Technical elements
4. Functional limitations
5. Structural limitations
6. Relationships between elements
7. Numerical or operational constraints
8. Potential antecedent-basis issues
9. Potential clarity issues
10. Terms that may require specification support
11. Search concepts for prior-art research

Do not conclude that the claim is valid, invalid, novel, non-novel,
patentable or unpatentable.
"""

        system = """
You are assisting a patent professional.

Perform technical claim analysis only.

Every observation must be grounded in the supplied claim or specification.
Do not fabricate prior art.
Do not invent legal requirements.
Do not provide a final legal opinion.
"""

        return self.generate(
            prompt,
            system_instruction=system,
            temperature=0.05,
            max_output_tokens=5000,
        )

    # -----------------------------------------------------------------

    def compare_claim_to_prior_art(
        self,
        claim_text: str,
        prior_art_text: str,
    ) -> AIResponse:

        prompt = f"""
Compare the patent claim against the supplied prior-art document.

CLAIM:
{_truncate(claim_text, 15000)}

PRIOR ART:
{_truncate(prior_art_text, 25000)}

For each important claim limitation:

- identify the limitation
- identify whether the prior art explicitly discloses it
- quote or identify the relevant evidence
- distinguish explicit disclosure from inference
- identify missing or uncertain limitations

Do not assume that a similar concept means the same limitation is disclosed.

Do not make a legal novelty conclusion.
"""

        system = """
You are an evidence-focused patent comparison assistant.

The supplied text is the only evidence available.

Never fabricate citations, paragraphs, page numbers, quotations,
or technical features.

Use:
EXPLICIT
INFERRED
NOT_FOUND
UNCERTAIN

when describing disclosure status.
"""

        return self.generate(
            prompt,
            system_instruction=system,
            temperature=0.0,
            max_output_tokens=6000,
        )

    # -----------------------------------------------------------------

    def generate_claim_chart(
        self,
        claim: Dict[str, Any],
        evidence: List[Dict[str, Any]],
    ) -> AIResponse:

        claim_json = json.dumps(
            claim,
            ensure_ascii=False,
            indent=2,
        )

        evidence_json = json.dumps(
            evidence,
            ensure_ascii=False,
            indent=2,
        )

        prompt = f"""
Create an evidence-based claim chart.

CLAIM STRUCTURE:
{_truncate(claim_json, 18000)}

AVAILABLE EVIDENCE:
{_truncate(evidence_json, 30000)}

For every claim limitation:

1. limitation_id
2. limitation_text
3. evidence_id
4. evidence_text
5. disclosure_status
6. reasoning
7. confidence

Disclosure status must be one of:

EXPLICIT
PARTIAL
INFERRED
NOT_FOUND
UNCERTAIN

Use only supplied evidence.

Return JSON with this structure:

{{
  "claim_chart": [
    {{
      "limitation_id": "",
      "limitation_text": "",
      "evidence_id": "",
      "evidence_text": "",
      "disclosure_status": "",
      "reasoning": "",
      "confidence": 0.0
    }}
  ]
}}
"""

        system = """
You are an evidence-grounded patent claim-chart assistant.

Critical rule:

Never create evidence.

If evidence is missing, mark it NOT_FOUND or UNCERTAIN.

Confidence must reflect the supplied evidence rather than
your general knowledge.

Do not provide a legal conclusion.
"""

        return self.generate_json(
            prompt,
            system_instruction=system,
            temperature=0.0,
            max_output_tokens=7000,
        )

    # -----------------------------------------------------------------

    def explain_rule_finding(
        self,
        finding: Dict[str, Any],
    ) -> AIResponse:

        finding_json = json.dumps(
            finding,
            ensure_ascii=False,
            indent=2,
        )

        prompt = f"""
Explain the following deterministic patent-analysis finding.

FINDING:
{_truncate(finding_json, 15000)}

Explain:

1. What triggered the finding
2. What evidence supports it
3. Why it may matter for review
4. What a patent professional should verify
5. What additional evidence may be required

Do not change the finding's severity.

Do not turn a screening signal into a legal conclusion.
"""

        system = """
You explain deterministic patent-analysis findings.

The finding itself is authoritative for the detected signal.
Do not invent evidence or legal rules.

Your role is explanation and reviewer guidance.
"""

        return self.generate(
            prompt,
            system_instruction=system,
            temperature=0.05,
            max_output_tokens=3500,
        )

    # -----------------------------------------------------------------

    def draft_search_strategy(
        self,
        claims: List[Dict[str, Any]],
    ) -> AIResponse:

        claims_json = json.dumps(
            claims,
            ensure_ascii=False,
            indent=2,
        )

        prompt = f"""
Develop a patent prior-art search strategy from these structured claims.

CLAIMS:
{_truncate(claims_json, 25000)}

Produce:

1. Core technical concepts
2. Synonym groups
3. Alternative terminology
4. Functional search terms
5. Structural search terms
6. Relationship-based search terms
7. Numerical/constraint search terms
8. CPC/IPC research directions
9. Assignee/inventor search directions
10. Citation/family search directions
11. Search-query combinations
12. Concepts that should NOT be broadened because they may lose
   technical meaning

Do not claim that prior art has been found.
"""

        system = """
You are a patent prior-art search planning assistant.

Your job is to construct a reproducible search strategy.

Do not fabricate CPC codes, patents, publications, applicants,
inventors or dates.

If a classification cannot be determined from the supplied claims,
describe it as a research direction rather than inventing a code.
"""

        return self.generate(
            prompt,
            system_instruction=system,
            temperature=0.1,
            max_output_tokens=6000,
        )

    # -----------------------------------------------------------------

    def analyze_fer(
        self,
        fer_text: str,
        application_text: str = "",
    ) -> AIResponse:

        prompt = f"""
Analyze this Indian patent examination report / FER.

FER:
{_truncate(fer_text, 30000)}

APPLICATION CONTEXT:
{_truncate(application_text, 20000)}

Extract:

1. Objections raised
2. Objection category
3. Claims affected
4. Evidence/citations mentioned
5. Applicant response requirements
6. Deadlines explicitly stated in the supplied text
7. Amendments requested or discussed
8. Issues requiring human review

Do not invent objections or deadlines.

Do not provide legal advice.
"""

        system = """
You are a patent prosecution document-analysis assistant.

Extract and organize information from the supplied FER.

Do not fabricate citations, objections, dates or legal provisions.

Distinguish:
EXPLICITLY_STATED
INFERRED
UNCERTAIN
"""

        return self.generate(
            prompt,
            system_instruction=system,
            temperature=0.0,
            max_output_tokens=6000,
        )

    # -----------------------------------------------------------------

    def draft_patent_report(
        self,
        analysis: Dict[str, Any],
    ) -> AIResponse:

        analysis_json = json.dumps(
            analysis,
            ensure_ascii=False,
            indent=2,
        )

        prompt = f"""
Create a professional patent-analysis report based ONLY on the
following structured analysis.

ANALYSIS:
{_truncate(analysis_json, 45000)}

Report sections:

1. Executive Summary
2. Document Overview
3. Claim Structure
4. Technical Features
5. Prior-Art Search Strategy
6. Evidence Findings
7. Rule-Based Findings
8. Risk/Review Signals
9. Missing Evidence
10. Recommended Human Review Actions
11. Reproducibility / Provenance

Important:

Do not convert review signals into legal conclusions.

Use cautious language such as:
- "identified for review"
- "requires verification"
- "evidence indicates"
- "not established from the available evidence"

Do not invent information.
"""

        system = """
You are generating a professional patent intelligence report.

The structured analysis is the source of truth.

Do not add unsupported facts.

Do not make final legal determinations.

Clearly separate:
FACT
EVIDENCE
ANALYTICAL INTERPRETATION
HUMAN REVIEW REQUIRED
"""

        return self.generate(
            prompt,
            system_instruction=system,
            temperature=0.1,
            max_output_tokens=8000,
        )


# ---------------------------------------------------------------------
# Singleton-style helper
# ---------------------------------------------------------------------

_service: Optional[GeminiService] = None


def get_gemini_service(
    model: Optional[str] = None,
) -> GeminiService:

    global _service

    if (
        _service is None
        or (
            model
            and _service.model != model
        )
    ):
        _service = GeminiService(
            model=model
        )

    return _service


# ---------------------------------------------------------------------
# Backward-compatible helper functions
# ---------------------------------------------------------------------

def ask_gemini(
    prompt: str,
    model: Optional[str] = None,
    temperature: float = 0.1,
    max_output_tokens: int = 4096,
) -> str:

    service = get_gemini_service(
        model=model
    )

    response = service.generate(
        prompt=prompt,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
    )

    if not response.success:
        return (
            f"Gemini Error: {response.error}"
        )

    return response.text


def generate_ai_response(
    prompt: str,
    model: Optional[str] = None,
) -> AIResponse:

    service = get_gemini_service(
        model=model
    )

    return service.generate(
        prompt
    )


def summarize_patent(
    patent_text: str,
) -> str:

    response = get_gemini_service().summarize_patent(
        patent_text
    )

    if not response.success:
        return f"Gemini Error: {response.error}"

    return response.text


def analyze_claim(
    claim_text: str,
    specification_text: str = "",
) -> str:

    response = get_gemini_service().analyze_claim(
        claim_text,
        specification_text,
    )

    if not response.success:
        return f"Gemini Error: {response.error}"

    return response.text


def analyze_claim_json(
    claim_text: str,
    specification_text: str = "",
) -> Dict[str, Any]:

    response = get_gemini_service().generate_json(
        prompt=f"""
Analyze this patent claim:

CLAIM:
{_truncate(claim_text, 15000)}

SPECIFICATION:
{_truncate(specification_text, 18000)}

Return JSON:

{{
  "claim_category": "",
  "core_concept": "",
  "technical_elements": [],
  "functional_limitations": [],
  "structural_limitations": [],
  "relationships": [],
  "constraints": [],
  "antecedent_basis_issues": [],
  "clarity_issues": [],
  "support_terms": [],
  "search_concepts": []
}}
""",
        system_instruction="""
Return structured claim analysis only.

Do not fabricate facts.
Do not provide a legal conclusion.
""",
    )

    if not response.success:
        return {
            "error": response.error
        }

    return response.structured or {}


# ---------------------------------------------------------------------
# Module exports
# ---------------------------------------------------------------------

__all__ = [
    "GEMINI_SERVICE_VERSION",
    "DEFAULT_MODEL",
    "AIResponse",
    "AIRequest",
    "GeminiService",
    "get_api_key",
    "get_gemini_service",
    "ask_gemini",
    "generate_ai_response",
    "summarize_patent",
    "analyze_claim",
    "analyze_claim_json",
]
