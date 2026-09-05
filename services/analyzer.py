import json
from pathlib import Path
from typing import Any

from services.claim_analyzer import analyze_claims
from services.document_parser import (
    extract_text_from_file,
    get_document_statistics,
)
from services.gemini_service import analyze_patent_text
from services.rule_engine import analyze_form2_document


BASE_DIR = Path(__file__).resolve().parent.parent
RULES_FILE = BASE_DIR / "data" / "form2_rules.json"


def load_form2_rules() -> list[dict[str, Any]]:
    """Load Indian patent Form 2 rules from the local JSON database."""

    if not RULES_FILE.exists():
        raise FileNotFoundError(
            f"Form 2 rules file not found: {RULES_FILE}"
        )

    with open(RULES_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, dict):
        return data.get("rules", [])

    if isinstance(data, list):
        return data

    raise ValueError("Invalid form2_rules.json format.")


def rules_to_text(rules: list[dict[str, Any]]) -> str:
    """Convert structured rules into concise text for Gemini."""

    lines = []

    for rule in rules:
        rule_id = rule.get("id", "")
        provision = rule.get("provision", "")
        requirement = rule.get("requirement", "")
        source = rule.get("source_reference", "")

        lines.append(
            f"{rule_id} | {provision} | "
            f"{requirement} | Source: {source}"
        )

    return "\n".join(lines)


def extract_claim_text(text: str) -> str:
    """
    Extract the claims section for the dedicated claim analyzer.

    This is intentionally simple at MVP stage. The rule engine performs
    the primary claim extraction and later versions can use more robust
    section detection.
    """

    lower_text = text.lower()

    claim_markers = [
        "claims",
        "claims:",
        "what is claimed is",
        "we claim",
    ]

    start = -1

    for marker in claim_markers:
        position = lower_text.find(marker)

        if position != -1:
            start = position
            break

    if start == -1:
        return ""

    return text[start:]


def build_gemini_context(
    document_text: str,
    rule_analysis: dict[str, Any],
    claim_analysis: dict[str, Any],
) -> str:
    """Build structured context for Gemini."""

    return json.dumps(
        {
            "document_statistics": get_document_statistics(document_text),
            "rule_engine_analysis": rule_analysis,
            "claim_engine_analysis": claim_analysis,
        },
        indent=2,
        ensure_ascii=False,
    )


def analyze_document(
    file_bytes: bytes,
    filename: str,
    document_type: str = "Form 2 Complete Specification",
    analysis_level: str = "Detailed",
    api_key: str | None = None,
) -> dict[str, Any]:
    """
    Run the complete patent analysis pipeline.

    Pipeline:
        File
        ↓
        Text extraction
        ↓
        Rule engine
        ↓
        Claim analyzer
        ↓
        Gemini
        ↓
        Combined analysis
    """

    # ---------------------------------------------------------
    # 1. Extract document text
    # ---------------------------------------------------------

    document_text = extract_text_from_file(
        file_bytes=file_bytes,
        filename=filename,
    )

    if not document_text.strip():
        raise ValueError(
            "No readable text was extracted from the uploaded document."
        )

    # ---------------------------------------------------------
    # 2. Basic document statistics
    # ---------------------------------------------------------

    statistics = get_document_statistics(document_text)

    # ---------------------------------------------------------
    # 3. Load Indian patent rules
    # ---------------------------------------------------------

    rules = load_form2_rules()
    rules_text = rules_to_text(rules)

    # ---------------------------------------------------------
    # 4. Run deterministic Form 2 checks
    # ---------------------------------------------------------

    rule_analysis = analyze_form2_document(document_text)

    # ---------------------------------------------------------
    # 5. Run claim analysis
    # ---------------------------------------------------------

    claim_text = extract_claim_text(document_text)

    if claim_text:
        claim_analysis = analyze_claims(claim_text)
    else:
        claim_analysis = {
            "claims": [],
            "claim_count": 0,
            "independent_claims": [],
            "dependent_claims": [],
            "issues": [
                {
                    "type": "missing_claim_section",
                    "severity": "high",
                    "message": "A claims section could not be identified.",
                }
            ],
        }

    # ---------------------------------------------------------
    # 6. Build context for Gemini
    # ---------------------------------------------------------

    analysis_context = build_gemini_context(
        document_text=document_text,
        rule_analysis=rule_analysis,
        claim_analysis=claim_analysis,
    )

    # ---------------------------------------------------------
    # 7. Send document + verified local rules to Gemini
    # ---------------------------------------------------------

    gemini_prompt = f"""
You are analyzing an Indian patent document.

DOCUMENT TYPE:
{document_type}

ANALYSIS LEVEL:
{analysis_level}

IMPORTANT:
Use the supplied Indian Patent Office rule information as the
verified legal/formal reference.

Do not invent provisions.

Do not treat drafting suggestions as legal requirements.

Do not introduce new technical matter.

Do not state that the patent will definitely be granted or rejected.

Return a structured analysis that can be combined with the
deterministic analysis already performed by the application.

VERIFIED LOCAL RULE INFORMATION:
{rules_text}

APPLICATION ANALYSIS CONTEXT:
{analysis_context}

PATENT DOCUMENT:
{document_text}
"""

    gemini_analysis = analyze_patent_text(
        patent_text=gemini_prompt,
        rules_text=rules_text,
        api_key=api_key,
    )

    # ---------------------------------------------------------
    # 8. Combine all analysis
    # ---------------------------------------------------------

    return {
        "document_name": filename,
        "document_type": document_type,
        "analysis_level": analysis_level,

        "document_statistics": statistics,

        "rule_engine": rule_analysis,

        "claim_engine": claim_analysis,

        "gemini_analysis": gemini_analysis,

        "rules_used": rules,

        "status": "completed",
    }
