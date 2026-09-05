import json
import re
from pathlib import Path
from typing import Any, Dict, List

from services.claim_analyzer import analyze_claims
from services.document_parser import (
    extract_text_from_file,
    get_document_statistics,
)
from services.gemini_service import analyze_patent_text
from services.manual_parser import parse_manual_pdf
from services.manual_retriever import build_manual_evidence, format_manual_evidence
from services.rule_engine import analyze_form2_document


BASE_DIR = Path(__file__).resolve().parent.parent

RULES_FILE = BASE_DIR / "data" / "form2_rules.json"

MANUAL_FILE = (
    BASE_DIR
    / "data"
    / "manuals"
    / "patent_office_manual_2019_v3.pdf"
)


def load_form2_rules() -> List[Dict[str, Any]]:
    """Load the deterministic Form 2 rules."""

    if not RULES_FILE.exists():
        return []

    try:
        with open(RULES_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            return data.get("rules", [])

    except Exception:
        return []

    return []


def rules_to_text(rules: List[Dict[str, Any]]) -> str:
    """Convert rules into compact text for Gemini."""

    if not rules:
        return "No local Form 2 rules were loaded."

    parts = []

    for rule in rules:
        parts.append(
            f"Provision: {rule.get('provision', '')}\n"
            f"Title: {rule.get('title', '')}\n"
            f"Requirement: {rule.get('requirement', '')}\n"
            f"Analysis Type: {rule.get('analysis_type', '')}\n"
            f"Severity: {rule.get('severity', '')}\n"
            f"Source Status: {rule.get('source_status', '')}"
        )

    return "\n\n".join(parts)


def extract_claims_section(text: str) -> str:
    """
    Extract the claims portion of a patent specification.

    This is intentionally conservative because claim formatting
    varies significantly between documents.
    """

    if not text:
        return ""

    patterns = [
        r"\bwhat\s+is\s+claimed\s+is\b",
        r"\bwe\s+claim\b",
        r"\bclaims?\s*[:\-]?\s*$",
    ]

    start = None

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)

        if match:
            start = match.end()
            break

    if start is None:
        return ""

    remaining = text[start:]

    # Stop if a new major section appears after claims.
    stop_patterns = [
        r"\n\s*abstract\b",
        r"\n\s*drawings?\b",
        r"\n\s*references?\b",
        r"\n\s*signature\b",
    ]

    end_positions = []

    for pattern in stop_patterns:
        match = re.search(
            pattern,
            remaining,
            re.IGNORECASE,
        )

        if match:
            end_positions.append(match.start())

    if end_positions:
        remaining = remaining[: min(end_positions)]

    return remaining.strip()


def normalize_claims_for_analyzer(
    claims: List[Any],
) -> List[Dict[str, Any]]:
    """
    Convert claims returned by different extraction methods
    into the structure expected by claim_analyzer.py.
    """

    normalized = []

    for index, claim in enumerate(claims, start=1):

        if isinstance(claim, dict):
            claim_number = claim.get(
                "claim_number",
                claim.get("number", index),
            )

            claim_text = claim.get(
                "claim_text",
                claim.get("text", ""),
            )

            normalized.append(
                {
                    "claim_number": claim_number,
                    "claim_text": str(claim_text).strip(),
                }
            )

        elif isinstance(claim, str):
            normalized.append(
                {
                    "claim_number": index,
                    "claim_text": claim.strip(),
                }
            )

    return [
        claim
        for claim in normalized
        if claim.get("claim_text")
    ]


def parse_numbered_claims(claim_text: str) -> List[Dict[str, Any]]:
    """
    Fallback claim parser for documents containing numbered claims.
    """

    if not claim_text:
        return []

    pattern = re.compile(
        r"(?:^|\n)\s*(\d+)\s*[\.\)]\s*(.*?)(?=\n\s*\d+\s*[\.\)]|\Z)",
        re.IGNORECASE | re.DOTALL,
    )

    matches = pattern.findall(claim_text)

    claims = []

    for number, text in matches:
        cleaned = re.sub(r"\s+", " ", text).strip()

        if cleaned:
            claims.append(
                {
                    "claim_number": int(number),
                    "claim_text": cleaned,
                }
            )

    return claims


def prepare_claim_analysis(
    rule_analysis: Dict[str, Any],
    claim_text: str,
) -> Dict[str, Any]:
    """Prepare claims for the deterministic claim analyzer."""

    if not claim_text:
        return {
            "status": "not_available",
            "claims": [],
            "issues": [
                {
                    "type": "missing_claims",
                    "severity": "high",
                    "message": "No claims section could be identified.",
                }
            ],
        }

    extracted_claims = rule_analysis.get("claims", [])

    normalized_claims = normalize_claims_for_analyzer(
        extracted_claims
    )

    # Fallback if rule engine could not identify claims.
    if not normalized_claims:
        normalized_claims = parse_numbered_claims(
            claim_text
        )

    if not normalized_claims:
        return {
            "status": "unable_to_parse",
            "claims": [],
            "issues": [
                {
                    "type": "claim_parsing",
                    "severity": "medium",
                    "message": (
                        "A claims section was detected, but "
                        "individual claims could not be reliably parsed."
                    ),
                }
            ],
        }

    try:
        analysis = analyze_claims(normalized_claims)

        return {
            "status": "completed",
            "claims": analysis,
        }

    except Exception as error:
        return {
            "status": "error",
            "claims": [],
            "issues": [
                {
                    "type": "claim_engine_error",
                    "severity": "medium",
                    "message": str(error),
                }
            ],
        }


def build_manual_queries(
    document_type: str,
    rule_analysis: Dict[str, Any],
    claim_analysis: Dict[str, Any],
) -> List[str]:
    """
    Build targeted searches for the Patent Manual.

    The whole manual is NOT sent to Gemini.
    Only relevant portions are retrieved.
    """

    queries = []

    document_type_lower = (
        document_type or ""
    ).lower()

    if "form 2" in document_type_lower:
        queries.extend(
            [
                "provisional complete specification",
                "complete specification contents",
                "description invention operation use method",
                "best method of performing invention",
                "claims clear succinct fairly based",
                "abstract complete specification",
            ]
        )

    # Claims
    claims = claim_analysis.get("claims", [])

    if claims:
        queries.extend(
            [
                "claims clarity succinctness",
                "claims fairly based specification",
                "independent dependent claims",
                "claim drafting",
            ]
        )

    # Common structural issues
    for issue in rule_analysis.get("issues", []):
        if isinstance(issue, dict):
            message = issue.get("message", "")

            if message:
                queries.append(message)

    # Remove duplicates while preserving order.
    unique_queries = []

    for query in queries:
        if query and query not in unique_queries:
            unique_queries.append(query)

    return unique_queries


def load_manual() -> Dict[str, Any]:
    """Load and parse the local Patent Office Manual."""

    if not MANUAL_FILE.exists():
        return {
            "status": "not_available",
            "page_count": 0,
            "pages": [],
            "chunks": [],
            "full_text": "",
        }

    try:
        with open(MANUAL_FILE, "rb") as file:
            manual_bytes = file.read()

        parsed = parse_manual_pdf(manual_bytes)

        parsed["status"] = "loaded"
        parsed["source"] = (
            "Manual of Patent Office Practice and Procedure"
        )
        parsed["version"] = "Version 3.0"
        parsed["date"] = "26 November 2019"

        return parsed

    except Exception as error:
        return {
            "status": "error",
            "page_count": 0,
            "pages": [],
            "chunks": [],
            "full_text": "",
            "error": str(error),
        }


def prepare_manual_context(
    manual: Dict[str, Any],
    document_type: str,
    rule_analysis: Dict[str, Any],
    claim_analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """Retrieve relevant manual evidence."""

    if manual.get("status") != "loaded":
        return {
            "status": manual.get("status", "not_available"),
            "evidence": [],
            "context": "",
        }

    queries = build_manual_queries(
        document_type=document_type,
        rule_analysis=rule_analysis,
        claim_analysis=claim_analysis,
    )

    evidence = build_manual_evidence(
        manual_chunks=manual.get("chunks", []),
        queries=queries,
        max_results_per_query=2,
    )

    # Remove duplicate chunks.
    unique_evidence = []
    seen_chunks = set()

    for item in evidence:
        chunk_id = item.get("chunk_id")

        if chunk_id in seen_chunks:
            continue

        seen_chunks.add(chunk_id)
        unique_evidence.append(item)

    context = format_manual_evidence(
        unique_evidence
    )

    return {
        "status": "completed",
        "queries": queries,
        "evidence": unique_evidence,
        "context": context,
    }


def analyze_document(
    file_bytes: bytes,
    filename: str,
    document_type: str,
    analysis_level: str = "Detailed",
) -> Dict[str, Any]:
    """
    Main patent analysis pipeline.

    Pipeline:

        Patent document
              ↓
        Document parser
              ↓
        Rule engine
              ↓
        Claim engine
              ↓
        Patent Manual retrieval
              ↓
        Gemini
    """

    # ---------------------------------------------------------
    # 1. Extract patent document text
    # ---------------------------------------------------------

    text = extract_text_from_file(
        file_bytes,
        filename,
    )

    statistics = get_document_statistics(text)

    # ---------------------------------------------------------
    # 2. Deterministic Form 2 analysis
    # ---------------------------------------------------------

    rules = load_form2_rules()

    rule_analysis = analyze_form2_document(text)

    # ---------------------------------------------------------
    # 3. Extract claims
    # ---------------------------------------------------------

    claim_text = extract_claims_section(text)

    # ---------------------------------------------------------
    # 4. Claim analysis
    # ---------------------------------------------------------

    claim_analysis = prepare_claim_analysis(
        rule_analysis=rule_analysis,
        claim_text=claim_text,
    )

    # ---------------------------------------------------------
    # 5. Load Patent Office Manual
    # ---------------------------------------------------------

    manual = load_manual()

    # ---------------------------------------------------------
    # 6. Retrieve only relevant manual sections
    # ---------------------------------------------------------

    manual_context = prepare_manual_context(
        manual=manual,
        document_type=document_type,
        rule_analysis=rule_analysis,
        claim_analysis=claim_analysis,
    )

    # ---------------------------------------------------------
    # 7. Build Gemini context
    # ---------------------------------------------------------

    rules_context = rules_to_text(rules)

    gemini_context = f"""
DOCUMENT TYPE:
{document_type}

ANALYSIS LEVEL:
{analysis_level}

==================================================
AUTHORITATIVE LOCAL FORM 2 RULES
==================================================

{rules_context}

==================================================
DETERMINISTIC RULE ENGINE ANALYSIS
==================================================

{json.dumps(rule_analysis, indent=2, ensure_ascii=False)}

==================================================
CLAIM ENGINE ANALYSIS
==================================================

{json.dumps(claim_analysis, indent=2, ensure_ascii=False)}

==================================================
PATENT OFFICE MANUAL GUIDANCE
==================================================

The following material is retrieved from the local
Manual of Patent Office Practice and Procedure.

It is guidance/procedural material and must NOT be
treated as overriding the Patents Act or Patents Rules.

{manual_context.get("context", "No relevant manual guidance retrieved.")}

==================================================
SOURCE HIERARCHY
==================================================

Use the following hierarchy:

1. Patents Act and applicable statutory provisions
2. Patents Rules and applicable amendments
3. Official Patent Office guidelines/manuals
4. Deterministic checks performed by this application
5. Drafting suggestions

Do not present the Patent Manual as having the force
of law.

Do not fabricate provisions, case law, citations,
rules, page numbers or examination objections.

==================================================
PATENT DOCUMENT
==================================================

{text}
"""

    # ---------------------------------------------------------
    # 8. Gemini analysis
    # ---------------------------------------------------------

    gemini_analysis = analyze_patent_text(
        patent_text=text,
        context=gemini_context,
        document_type=document_type,
        analysis_level=analysis_level,
    )

    # ---------------------------------------------------------
    # 9. Final result
    # ---------------------------------------------------------

    return {
        "document_name": filename,
        "document_type": document_type,
        "analysis_level": analysis_level,
        "document_statistics": statistics,

        "rule_engine": rule_analysis,

        "claim_engine": claim_analysis,

        "manual": {
            "status": manual.get("status"),
            "source": manual.get("source"),
            "version": manual.get("version"),
            "date": manual.get("date"),
            "page_count": manual.get("page_count", 0),
            "retrieval_status": manual_context.get("status"),
            "queries": manual_context.get("queries", []),
            "evidence": manual_context.get("evidence", []),
        },

        "gemini_analysis": gemini_analysis,

        "rules_used": rules,

        "status": "completed",
    }
