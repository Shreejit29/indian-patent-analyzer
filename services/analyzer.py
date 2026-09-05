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
from services.manual_retriever import (
    build_manual_evidence,
    format_manual_evidence,
)
from services.rule_engine import analyze_form2_document


# ============================================================
# PROJECT PATHS
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

FORM2_RULES_FILE = (
    BASE_DIR / "data" / "form2_rules.json"
)

PATENT_RULES_FILE = (
    BASE_DIR / "data" / "patent_rules.json"
)

MANUAL_FILE = (
    BASE_DIR
    / "data"
    / "manuals"
    / "patent_office_manual_2019_v3.pdf"
)


# ============================================================
# RULE DATABASE
# ============================================================

def load_json_rules(
    file_path: Path,
) -> List[Dict[str, Any]]:
    """
    Load rules from a JSON file.

    Supports both:
        - a direct JSON list
        - {"rules": [...]}
    """

    if not file_path.exists():
        return []

    try:
        with open(
            file_path,
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        if isinstance(data, dict):
            return data.get("rules", [])

    except Exception:
        return []

    return []


def load_form2_rules() -> List[Dict[str, Any]]:
    """Load Form 2 specific rules."""

    return load_json_rules(
        FORM2_RULES_FILE
    )


def load_patent_rules() -> List[Dict[str, Any]]:
    """Load the broader Indian patent rules database."""

    return load_json_rules(
        PATENT_RULES_FILE
    )


def rules_to_text(
    rules: List[Dict[str, Any]],
) -> str:
    """
    Convert rules into compact text for Gemini.
    """

    if not rules:
        return "No local rules were loaded."

    parts = []

    for rule in rules:
        parts.append(
            f"Provision: {rule.get('provision', '')}\n"
            f"Category: {rule.get('category', '')}\n"
            f"Title: {rule.get('title', '')}\n"
            f"Requirement: {rule.get('requirement', '')}\n"
            f"Analysis Type: {rule.get('analysis_type', '')}\n"
            f"Severity: {rule.get('severity', '')}\n"
            f"Source Status: {rule.get('source_status', '')}\n"
            f"Authority: {rule.get('authority', '')}\n"
            f"Source Reference: {rule.get('source_reference', '')}"
        )

    return "\n\n".join(parts)


# ============================================================
# CLAIM EXTRACTION
# ============================================================

def extract_claims_section(
    text: str,
) -> str:
    """
    Extract the claims portion of a patent specification.

    Different patent documents use different claim headings,
    so several patterns are supported.
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

        match = re.search(
            pattern,
            text,
            re.IGNORECASE | re.MULTILINE,
        )

        if match:
            start = match.end()
            break

    if start is None:
        return ""

    remaining = text[start:]

    # Stop at likely sections following claims.
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
            end_positions.append(
                match.start()
            )

    if end_positions:
        remaining = remaining[
            : min(end_positions)
        ]

    return remaining.strip()


# ============================================================
# CLAIM NORMALIZATION
# ============================================================

def normalize_claims_for_analyzer(
    claims: List[Any],
) -> List[Dict[str, Any]]:
    """
    Convert claims returned by the rule engine into the
    structure expected by claim_analyzer.py.
    """

    normalized = []

    for index, claim in enumerate(
        claims,
        start=1,
    ):

        if isinstance(claim, dict):

            claim_number = claim.get(
                "claim_number",
                claim.get(
                    "number",
                    index,
                ),
            )

            claim_text = claim.get(
                "claim_text",
                claim.get(
                    "text",
                    "",
                ),
            )

            normalized.append(
                {
                    "claim_number": claim_number,
                    "claim_text": str(
                        claim_text
                    ).strip(),
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


def parse_numbered_claims(
    claim_text: str,
) -> List[Dict[str, Any]]:
    """
    Fallback parser for numbered claims such as:

    1. A system comprising...
    2. The system of claim 1...
    3. ...
    """

    if not claim_text:
        return []

    pattern = re.compile(
        r"(?:^|\n)"
        r"\s*(\d+)"
        r"\s*[\.\)]"
        r"\s*(.*?)"
        r"(?=\n\s*\d+\s*[\.\)]|\Z)",
        re.IGNORECASE | re.DOTALL,
    )

    matches = pattern.findall(
        claim_text
    )

    claims = []

    for number, text in matches:

        cleaned = re.sub(
            r"\s+",
            " ",
            text,
        ).strip()

        if cleaned:

            claims.append(
                {
                    "claim_number": int(
                        number
                    ),
                    "claim_text": cleaned,
                }
            )

    return claims


# ============================================================
# CLAIM ANALYSIS
# ============================================================

def prepare_claim_analysis(
    rule_analysis: Dict[str, Any],
    claim_text: str,
) -> Dict[str, Any]:
    """
    Prepare claims for deterministic claim analysis.
    """

    if not claim_text:

        return {
            "status": "not_available",
            "claims": [],
            "issues": [
                {
                    "type": "missing_claims",
                    "severity": "high",
                    "message": (
                        "No claims section could be identified."
                    ),
                }
            ],
        }

    extracted_claims = rule_analysis.get(
        "claims",
        [],
    )

    normalized_claims = (
        normalize_claims_for_analyzer(
            extracted_claims
        )
    )

    # --------------------------------------------------------
    # Fallback parser
    # --------------------------------------------------------

    if not normalized_claims:

        normalized_claims = (
            parse_numbered_claims(
                claim_text
            )
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
                        "A claims section was detected, "
                        "but individual claims could not "
                        "be reliably parsed."
                    ),
                }
            ],
        }

    # --------------------------------------------------------
    # Claim analyzer
    # --------------------------------------------------------

    try:

        analysis = analyze_claims(
            normalized_claims
        )

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


# ============================================================
# PATENT MANUAL
# ============================================================

def load_manual() -> Dict[str, Any]:
    """
    Load and parse the local Patent Office Manual.
    """

    if not MANUAL_FILE.exists():

        return {
            "status": "not_available",
            "page_count": 0,
            "pages": [],
            "chunks": [],
            "full_text": "",
        }

    try:

        with open(
            MANUAL_FILE,
            "rb",
        ) as file:

            manual_bytes = file.read()

        parsed = parse_manual_pdf(
            manual_bytes
        )

        parsed["status"] = "loaded"

        parsed["source"] = (
            "Manual of Patent Office Practice "
            "and Procedure"
        )

        parsed["version"] = (
            "Version 3.0"
        )

        parsed["date"] = (
            "26 November 2019"
        )

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


# ============================================================
# MANUAL QUERY GENERATION
# ============================================================

def build_manual_queries(
    document_type: str,
    rule_analysis: Dict[str, Any],
    claim_analysis: Dict[str, Any],
) -> List[str]:
    """
    Create targeted searches for the Patent Manual.
    """

    queries = []

    document_type_lower = (
        document_type or ""
    ).lower()

    # --------------------------------------------------------
    # Form 2 / specification
    # --------------------------------------------------------

    if "form 2" in document_type_lower:

        queries.extend(
            [
                "provisional complete specification",
                "complete specification contents",
                "description invention operation use method",
                "best method of performing invention",
                "claims clear succinct fairly based",
                "abstract complete specification",
                "drawings specification",
            ]
        )

    # --------------------------------------------------------
    # Claims
    # --------------------------------------------------------

    claims = claim_analysis.get(
        "claims",
        [],
    )

    if claims:

        queries.extend(
            [
                "claims clarity succinctness",
                "claims fairly based on specification",
                "independent dependent claims",
                "claim drafting",
                "claim scope",
            ]
        )

    # --------------------------------------------------------
    # Rule-engine issues
    # --------------------------------------------------------

    for issue in rule_analysis.get(
        "issues",
        [],
    ):

        if isinstance(issue, dict):

            message = issue.get(
                "message",
                "",
            )

            if message:
                queries.append(
                    message
                )

    # --------------------------------------------------------
    # Remove duplicates
    # --------------------------------------------------------

    unique_queries = []

    for query in queries:

        query = query.strip()

        if (
            query
            and query not in unique_queries
        ):
            unique_queries.append(
                query
            )

    return unique_queries


# ============================================================
# MANUAL RETRIEVAL
# ============================================================

def prepare_manual_context(
    manual: Dict[str, Any],
    document_type: str,
    rule_analysis: Dict[str, Any],
    claim_analysis: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Retrieve only the relevant portions of the Patent Manual.
    """

    if manual.get("status") != "loaded":

        return {
            "status": manual.get(
                "status",
                "not_available",
            ),
            "queries": [],
            "evidence": [],
            "context": "",
        }

    queries = build_manual_queries(
        document_type=document_type,
        rule_analysis=rule_analysis,
        claim_analysis=claim_analysis,
    )

    if not queries:

        return {
            "status": "no_queries",
            "queries": [],
            "evidence": [],
            "context": "",
        }

    evidence = build_manual_evidence(
        manual_chunks=manual.get(
            "chunks",
            [],
        ),
        queries=queries,
        max_results_per_query=2,
    )

    # --------------------------------------------------------
    # Remove duplicate chunks
    # --------------------------------------------------------

    unique_evidence = []

    seen_chunks = set()

    for item in evidence:

        chunk_id = item.get(
            "chunk_id"
        )

        if chunk_id in seen_chunks:
            continue

        seen_chunks.add(
            chunk_id
        )

        unique_evidence.append(
            item
        )

    context = format_manual_evidence(
        unique_evidence
    )

    return {
        "status": "completed",
        "queries": queries,
        "evidence": unique_evidence,
        "context": context,
    }


# ============================================================
# MAIN ANALYZER
# ============================================================

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
        Form 2 rule engine
              ↓
        Claim engine
              ↓
        Patent Manual retrieval
              ↓
        Gemini
              ↓
        Final analysis
    """

    # ========================================================
    # 1. EXTRACT PATENT DOCUMENT
    # ========================================================

    text = extract_text_from_file(
        file_bytes,
        filename,
    )

    statistics = (
        get_document_statistics(
            text
        )
    )

    # ========================================================
    # 2. LOAD KNOWLEDGE BASES
    # ========================================================

    form2_rules = (
        load_form2_rules()
    )

    patent_rules = (
        load_patent_rules()
    )

    # ========================================================
    # 3. FORM 2 RULE ENGINE
    # ========================================================

    rule_analysis = (
        analyze_form2_document(
            text
        )
    )

    # ========================================================
    # 4. EXTRACT CLAIMS
    # ========================================================

    claim_text = (
        extract_claims_section(
            text
        )
    )

    # ========================================================
    # 5. CLAIM ENGINE
    # ========================================================

    claim_analysis = (
        prepare_claim_analysis(
            rule_analysis=rule_analysis,
            claim_text=claim_text,
        )
    )

    # ========================================================
    # 6. LOAD PATENT MANUAL
    # ========================================================

    manual = load_manual()

    # ========================================================
    # 7. RETRIEVE RELEVANT MANUAL CONTENT
    # ========================================================

    manual_context = (
        prepare_manual_context(
            manual=manual,
            document_type=document_type,
            rule_analysis=rule_analysis,
            claim_analysis=claim_analysis,
        )
    )

    # ========================================================
    # 8. CONVERT RULE DATABASES TO GEMINI CONTEXT
    # ========================================================

    form2_rules_context = (
        rules_to_text(
            form2_rules
        )
    )

    patent_rules_context = (
        rules_to_text(
            patent_rules
        )
    )

    # ========================================================
    # 9. BUILD GEMINI CONTEXT
    # ========================================================

    gemini_context = f"""

============================================================
DOCUMENT INFORMATION
============================================================

Document Type:
{document_type}

Analysis Level:
{analysis_level}

Document Name:
{filename}


============================================================
AUTHORITATIVE FORM 2 RULE DATABASE
============================================================

The following local database contains Form 2 related
requirements.

{form2_rules_context}


============================================================
INDIAN PATENT ACT / RULES DATABASE
============================================================

The following local database contains Indian patent
provisions and procedural rules.

Use these provisions as the primary legal/statutory
reference available in this application.

{patent_rules_context}


============================================================
DETERMINISTIC FORM 2 ANALYSIS
============================================================

The application performed the following preliminary
rule-based analysis:

{json.dumps(
    rule_analysis,
    indent=2,
    ensure_ascii=False,
)}


============================================================
CLAIM ENGINE ANALYSIS
============================================================

The application performed the following preliminary
claim analysis:

{json.dumps(
    claim_analysis,
    indent=2,
    ensure_ascii=False,
)}


============================================================
PATENT OFFICE MANUAL GUIDANCE
============================================================

The following information has been retrieved from the
local Manual of Patent Office Practice and Procedure.

Manual:
Manual of Patent Office Practice and Procedure

Version:
Version 3.0

Date:
26 November 2019

IMPORTANT:

The Patent Manual is procedural/practical guidance.
It must NOT be treated as legislation.

The Manual must not override the Patents Act,
Patents Rules, Gazette notifications, or applicable
official guidelines.

Relevant Manual Evidence:

{
    manual_context.get(
        "context",
        "No relevant manual guidance was retrieved.",
    )
}


============================================================
SOURCE HIERARCHY
============================================================

When assessing an issue, follow this hierarchy:

1. Patents Act, 1970
2. Applicable Patents Rules
3. Official amendments / Gazette notifications
4. Official Patent Office guidelines
5. Patent Office Manual
6. Deterministic checks performed by this application
7. Drafting suggestions

If sources conflict, do not silently resolve the conflict.

Identify the conflict and state that the current
applicable statutory or official source should be checked.


============================================================
ANALYSIS CLASSIFICATION
============================================================

Every identified issue should be classified where
appropriate as one of:

1. LEGAL / FORMAL REQUIREMENT

A requirement arising from the applicable Act, Rules,
forms or other authoritative source.

2. EXAMINATION RISK

An issue that may attract an objection or require
clarification during examination.

3. DRAFTING SUGGESTION

An improvement to clarity, consistency, precision,
readability or drafting quality that is not itself
necessarily a legal defect.


============================================================
IMPORTANT SAFEGUARDS
============================================================

Do NOT:

- fabricate Indian patent provisions
- fabricate rules
- fabricate case law
- fabricate official citations
- invent Patent Manual page numbers
- claim that a patent will definitely be granted
- claim that a patent will definitely be rejected
- introduce new matter into the invention
- silently modify the applicant's invention
- treat drafting suggestions as statutory requirements
- treat the Patent Manual as having the force of law

Clearly distinguish:

- statutory/legal requirement
- examination risk
- drafting suggestion
- preliminary heuristic observation


============================================================
PATENT DOCUMENT
============================================================

The following is the extracted text of the patent
document being analyzed:

{text}

"""

    # ========================================================
    # 10. GEMINI
    # ========================================================

    gemini_analysis = (
        analyze_patent_text(
            patent_text=text,
            context=gemini_context,
            document_type=document_type,
            analysis_level=analysis_level,
        )
    )

    # ========================================================
    # 11. FINAL RESULT
    # ========================================================

    return {
        "document_name": filename,

        "document_type": document_type,

        "analysis_level": analysis_level,

        "document_statistics": statistics,

        # ----------------------------------------------------
        # Deterministic analysis
        # ----------------------------------------------------

        "rule_engine": rule_analysis,

        "claim_engine": claim_analysis,

        # ----------------------------------------------------
        # Patent Manual
        # ----------------------------------------------------

        "manual": {
            "status": manual.get(
                "status"
            ),

            "source": manual.get(
                "source"
            ),

            "version": manual.get(
                "version"
            ),

            "date": manual.get(
                "date"
            ),

            "page_count": manual.get(
                "page_count",
                0,
            ),

            "retrieval_status": manual_context.get(
                "status"
            ),

            "queries": manual_context.get(
                "queries",
                [],
            ),

            "evidence": manual_context.get(
                "evidence",
                [],
            ),
        },

        # ----------------------------------------------------
        # Gemini
        # ----------------------------------------------------

        "gemini_analysis": gemini_analysis,

        # ----------------------------------------------------
        # Knowledge sources
        # ----------------------------------------------------

        "rules_used": {
            "form2_rules": form2_rules,
            "patent_rules": patent_rules,
        },

        # ----------------------------------------------------
        # Status
        # ----------------------------------------------------

        "status": "completed",
    }
