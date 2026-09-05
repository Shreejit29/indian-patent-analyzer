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


# ---------------------------------------------------------
# RULE LOADING
# ---------------------------------------------------------

def load_form2_rules() -> list[dict[str, Any]]:
    """Load Indian patent Form 2 rules from the local JSON file."""

    if not RULES_FILE.exists():
        raise FileNotFoundError(
            f"Form 2 rules file not found: {RULES_FILE}"
        )

    with open(RULES_FILE, "r", encoding="utf-8") as file:
        data = json.load(file)

    if isinstance(data, dict):
        rules = data.get("rules", [])

    elif isinstance(data, list):
        rules = data

    else:
        raise ValueError(
            "Invalid form2_rules.json format."
        )

    if not isinstance(rules, list):
        raise ValueError(
            "The 'rules' section must be a list."
        )

    return rules


def rules_to_text(
    rules: list[dict[str, Any]]
) -> str:
    """Convert structured rules into text for Gemini."""

    lines = []

    for rule in rules:

        if not isinstance(rule, dict):
            continue

        rule_id = rule.get("id", "")
        provision = rule.get("provision", "")
        requirement = rule.get("requirement", "")
        source = rule.get(
            "source_reference",
            ""
        )

        lines.append(
            f"{rule_id} | "
            f"{provision} | "
            f"{requirement} | "
            f"Source: {source}"
        )

    return "\n".join(lines)


# ---------------------------------------------------------
# CLAIM EXTRACTION
# ---------------------------------------------------------

def extract_claim_text(
    text: str
) -> str:
    """
    Extract the claims section from the patent document.

    This is a first-stage extraction method. More advanced
    section detection can be added later.
    """

    lower_text = text.lower()

    claim_markers = [
        "what is claimed is",
        "we claim",
        "claims:",
        "claims",
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


def normalize_claims_for_analyzer(
    claims: Any
) -> list[dict[str, Any]]:
    """
    Convert claims returned by the rule engine into the
    dictionary format expected by claim_analyzer.py.

    Handles:
    - string claims
    - dictionary claims
    - mixed lists
    """

    normalized = []

    if not isinstance(claims, list):
        return normalized

    for index, claim in enumerate(
        claims,
        start=1,
    ):

        # -------------------------------------------------
        # Claim already in dictionary format
        # -------------------------------------------------

        if isinstance(claim, dict):

            claim_record = dict(claim)

            if not claim_record.get(
                "claim_number"
            ):
                claim_record["claim_number"] = index

            normalized.append(
                claim_record
            )

            continue

        # -------------------------------------------------
        # Claim returned as a string
        # -------------------------------------------------

        if isinstance(claim, str):

            claim_text = claim.strip()

            if not claim_text:
                continue

            normalized.append(
                {
                    "claim_number": index,
                    "text": claim_text,
                }
            )

    return normalized


def prepare_claim_analysis(
    rule_analysis: dict[str, Any],
    claim_text: str,
) -> dict[str, Any]:
    """
    Prepare claims and send them to the deterministic
    claim analyzer.
    """

    if not claim_text.strip():

        return {
            "claims": [],
            "claim_count": 0,
            "independent_claims": [],
            "dependent_claims": [],
            "issues": [
                {
                    "type": "missing_claim_section",
                    "severity": "high",
                    "message": (
                        "A claims section could not "
                        "be identified."
                    ),
                }
            ],
        }

    # Try claims extracted by rule_engine first.
    extracted_claims = rule_analysis.get(
        "claims",
        []
    )

    normalized_claims = normalize_claims_for_analyzer(
        extracted_claims
    )

    # -----------------------------------------------------
    # If rule engine did not provide usable claims,
    # create a basic numbered claim list from the text.
    # -----------------------------------------------------

    if not normalized_claims:

        lines = claim_text.splitlines()

        current_claim = None
        current_number = None
        fallback_claims = []

        for line in lines:

            stripped = line.strip()

            if not stripped:
                continue

            # Detect numbered claims:
            # 1. ...
            # 2. ...
            # 10. ...
            parts = stripped.split(".", 1)

            if (
                len(parts) == 2
                and parts[0].strip().isdigit()
            ):

                if current_claim:

                    fallback_claims.append(
                        {
                            "claim_number": current_number,
                            "text": current_claim.strip(),
                        }
                    )

                current_number = int(
                    parts[0].strip()
                )

                current_claim = parts[1].strip()

            else:

                if current_claim is not None:
                    current_claim += " " + stripped

        # Add final claim
        if current_claim:

            fallback_claims.append(
                {
                    "claim_number": current_number,
                    "text": current_claim.strip(),
                }
            )

        normalized_claims = fallback_claims

    # -----------------------------------------------------
    # Run deterministic claim analyzer
    # -----------------------------------------------------

    if normalized_claims:

        try:

            return analyze_claims(
                normalized_claims
            )

        except AttributeError as exc:

            # Defensive fallback so that one malformed claim
            # does not crash the entire Streamlit application.

            return {
                "claims": normalized_claims,
                "claim_count": len(
                    normalized_claims
                ),
                "independent_claims": [],
                "dependent_claims": [],
                "issues": [
                    {
                        "type": "claim_analyzer_error",
                        "severity": "high",
                        "message": (
                            "The claim analyzer could not "
                            "process the extracted claim format."
                        ),
                        "technical_detail": str(exc),
                    }
                ],
            }

    return {
        "claims": [],
        "claim_count": 0,
        "independent_claims": [],
        "dependent_claims": [],
        "issues": [
            {
                "type": "claim_extraction_failed",
                "severity": "high",
                "message": (
                    "A claims section was found, but "
                    "individual claims could not be extracted."
                ),
            }
        ],
    }


# ---------------------------------------------------------
# GEMINI CONTEXT
# ---------------------------------------------------------

def build_gemini_context(
    document_text: str,
    rule_analysis: dict[str, Any],
    claim_analysis: dict[str, Any],
) -> str:
    """Build structured context for Gemini."""

    context = {
        "document_statistics": get_document_statistics(
            document_text
        ),
        "rule_engine_analysis": rule_analysis,
        "claim_engine_analysis": claim_analysis,
    }

    return json.dumps(
        context,
        indent=2,
        ensure_ascii=False,
        default=str,
    )


# ---------------------------------------------------------
# MAIN ANALYZER
# ---------------------------------------------------------

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

        PDF/DOCX
            ↓
        Text Extraction
            ↓
        IPO Rule Engine
            ↓
        Claim Analyzer
            ↓
        Gemini
            ↓
        Combined Analysis
    """

    # =====================================================
    # 1. EXTRACT DOCUMENT TEXT
    # =====================================================

    document_text = extract_text_from_file(
        file_bytes=file_bytes,
        filename=filename,
    )

    if not document_text.strip():

        raise ValueError(
            "No readable text was extracted "
            "from the uploaded document."
        )

    # =====================================================
    # 2. DOCUMENT STATISTICS
    # =====================================================

    statistics = get_document_statistics(
        document_text
    )

    # =====================================================
    # 3. LOAD VERIFIED RULES
    # =====================================================

    rules = load_form2_rules()

    rules_text = rules_to_text(
        rules
    )

    # =====================================================
    # 4. RUN DETERMINISTIC FORM 2 ANALYSIS
    # =====================================================

    rule_analysis = analyze_form2_document(
        document_text
    )

    # =====================================================
    # 5. EXTRACT CLAIM SECTION
    # =====================================================

    claim_text = extract_claim_text(
        document_text
    )

    # =====================================================
    # 6. RUN CLAIM ANALYZER
    # =====================================================

    claim_analysis = prepare_claim_analysis(
        rule_analysis=rule_analysis,
        claim_text=claim_text,
    )

    # =====================================================
    # 7. BUILD GEMINI CONTEXT
    # =====================================================

    analysis_context = build_gemini_context(
        document_text=document_text,
        rule_analysis=rule_analysis,
        claim_analysis=claim_analysis,
    )

    # =====================================================
    # 8. GEMINI ANALYSIS
    # =====================================================

    gemini_prompt = f"""
You are analyzing an Indian patent document.

DOCUMENT TYPE:
{document_type}

ANALYSIS LEVEL:
{analysis_level}

IMPORTANT:

Use the supplied Indian patent rule information as the
verified legal/formal reference.

Do not invent provisions.

Do not fabricate legal citations.

Do not treat drafting suggestions as legal requirements.

Do not introduce new technical matter.

Do not state that the patent will definitely be granted
or rejected.

The deterministic analysis below is generated by the
application and should be treated as supporting analysis,
not automatically as legal conclusions.

VERIFIED INDIAN PATENT RULE INFORMATION:

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
        analysis_level=analysis_level,
    )

    # =====================================================
    # 9. COMBINE RESULTS
    # =====================================================

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
