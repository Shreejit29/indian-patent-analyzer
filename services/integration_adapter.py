"""
Indian Patent Analyzer
V3 Integration Adapter

Purpose
-------
Provides one stable integration interface over the existing patent-analysis
modules, even when individual modules expose different function signatures.

Architecture:

    Raw PDF
       ↓
    Document Parser
       ↓
    Integration Adapter
       ↓
    Claim Analysis
    Rule Engine
    Section 3
    Prior Art
    Novelty
    Inventive Step
    Prosecution
    Knowledge Graph
    Validation

Important
---------
This adapter does not create legal conclusions.

It only:
    1. prepares data,
    2. calls existing deterministic modules,
    3. normalizes their outputs,
    4. records warnings/errors,
    5. provides a stable pipeline interface.
"""

from __future__ import annotations

import hashlib
import inspect
import re
import traceback
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ============================================================
# VERSION
# ============================================================

INTEGRATION_ADAPTER_VERSION = "3.0.0"


# ============================================================
# BASIC UTILITIES
# ============================================================

def utc_now() -> str:
    """Return an ISO UTC timestamp."""

    return datetime.now(
        timezone.utc
    ).isoformat()


def clean_text(value: Any) -> str:
    """Safely convert a value to clean text."""

    if value is None:
        return ""

    if isinstance(value, str):
        return re.sub(
            r"\s+",
            " ",
            value,
        ).strip()

    return str(value).strip()


def stable_id(
    prefix: str,
    value: Any,
) -> str:
    """
    Create a deterministic identifier.
    """

    raw = clean_text(
        value
    )

    digest = hashlib.sha256(
        raw.encode(
            "utf-8"
        )
    ).hexdigest()[:16]

    return f"{prefix}-{digest}"


def safe_call(
    function,
    *args,
    **kwargs,
) -> Dict[str, Any]:
    """
    Execute a function safely.

    Returns:
        {
            "ok": bool,
            "result": Any,
            "error": str | None,
            "traceback": str | None
        }
    """

    try:

        result = function(
            *args,
            **kwargs,
        )

        return {
            "ok": True,
            "result": result,
            "error": None,
            "traceback": None,
        }

    except Exception as exc:

        return {
            "ok": False,
            "result": None,
            "error": (
                f"{type(exc).__name__}: {exc}"
            ),
            "traceback": traceback.format_exc(),
        }


def get_function(
    module: Any,
    names: List[str],
):
    """
    Return the first callable matching the supplied names.
    """

    for name in names:

        function = getattr(
            module,
            name,
            None,
        )

        if callable(function):
            return function

    return None


def function_signature(
    function,
) -> str:
    """
    Safely return a function signature.
    """

    try:

        return str(
            inspect.signature(
                function
            )
        )

    except Exception:

        return "(signature unavailable)"


def accepts_parameter(
    function,
    parameter_name: str,
) -> bool:
    """
    Check whether a function explicitly accepts a parameter.
    """

    try:

        signature = inspect.signature(
            function
        )

        parameters = signature.parameters

        if parameter_name in parameters:
            return True

        return any(
            p.kind
            == inspect.Parameter.VAR_KEYWORD
            for p in parameters.values()
        )

    except Exception:

        return False


def serialize_value(
    value: Any,
) -> Any:
    """
    Convert common Python objects into JSON-friendly structures.
    """

    if value is None:
        return None

    if hasattr(
        value,
        "to_dict",
    ):

        try:

            return serialize_value(
                value.to_dict()
            )

        except Exception:
            pass

    if hasattr(
        value,
        "__dataclass_fields__",
    ):

        try:

            return serialize_value(
                asdict(value)
            )

        except Exception:
            pass

    if isinstance(
        value,
        dict,
    ):

        return {
            str(key): serialize_value(
                item
            )
            for key, item in value.items()
        }

    if isinstance(
        value,
        (list, tuple, set),
    ):

        return [
            serialize_value(
                item
            )
            for item in value
        ]

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):

        return value

    return str(value)


# ============================================================
# RESULT OBJECTS
# ============================================================

@dataclass
class AdapterStageResult:
    """
    Standardized output from one pipeline stage.
    """

    stage: str

    status: str

    result: Any = None

    error: Optional[str] = None

    warning: Optional[str] = None

    function: Optional[str] = None

    signature: Optional[str] = None

    timestamp: str = ""

    def __post_init__(
        self,
    ):

        if not self.timestamp:

            self.timestamp = utc_now()

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return serialize_value(
            asdict(self)
        )


@dataclass
class AdapterPipelineResult:
    """
    Complete standardized pipeline output.
    """

    adapter_version: str

    analysis_id: str

    status: str

    document: Dict[str, Any]

    stages: Dict[str, Any]

    warnings: List[str]

    errors: List[str]

    started_at: str

    completed_at: str

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return serialize_value(
            asdict(self)
        )


# ============================================================
# DATA NORMALIZATION
# ============================================================

def normalize_claims(
    claims: Any,
) -> List[Dict[str, Any]]:
    """
    Convert different claim representations into:

        {
            "number": int,
            "text": str
        }
    """

    if claims is None:
        return []

    if isinstance(
        claims,
        dict,
    ):

        for key in (
            "claims",
            "items",
            "results",
        ):

            if isinstance(
                claims.get(key),
                list,
            ):

                return normalize_claims(
                    claims[key]
                )

        # Single claim dictionary.
        if (
            "claim_number" in claims
            or "number" in claims
        ):

            claims = [
                claims
            ]

        else:

            return []

    if not isinstance(
        claims,
        list,
    ):

        return []

    normalized = []

    for index, claim in enumerate(
        claims,
        start=1,
    ):

        if isinstance(
            claim,
            str,
        ):

            normalized.append(
                {
                    "number": index,
                    "text": clean_text(
                        claim
                    ),
                }
            )

            continue

        if not isinstance(
            claim,
            dict,
        ):

            continue

        number = (
            claim.get(
                "number"
            )
            or claim.get(
                "claim_number"
            )
            or index
        )

        text = (
            claim.get(
                "text"
            )
            or claim.get(
                "claim_text"
            )
            or claim.get(
                "content"
            )
            or ""
        )

        try:

            number = int(
                number
            )

        except Exception:

            number = index

        normalized.append(
            {
                "number": number,
                "text": clean_text(
                    text
                ),
            }
        )

    return normalized


def normalize_document(
    parsed: Any,
) -> Dict[str, Any]:
    """
    Normalize the output of the current document parser.
    """

    if isinstance(
        parsed,
        str,
    ):

        text = parsed

        return {
            "text": text,
            "title": "",
            "abstract": "",
            "claims": [],
            "statistics": {
                "characters": len(
                    text
                ),
                "words": len(
                    text.split()
                ),
            },
        }

    if not isinstance(
        parsed,
        dict,
    ):

        parsed = serialize_value(
            parsed
        )

    if not isinstance(
        parsed,
        dict,
    ):

        return {
            "text": clean_text(
                parsed
            ),
            "title": "",
            "abstract": "",
            "claims": [],
        }

    text = (
        parsed.get(
            "text"
        )
        or parsed.get(
            "content"
        )
        or parsed.get(
            "full_text"
        )
        or ""
    )

    claims = normalize_claims(
        parsed.get(
            "claims"
        )
    )

    return {
        **parsed,
        "text": clean_text(
            text
        ),
        "title": clean_text(
            parsed.get(
                "title"
            )
        ),
        "abstract": clean_text(
            parsed.get(
                "abstract"
            )
        ),
        "claims": claims,
    }


# ============================================================
# ADAPTER
# ============================================================

class PatentIntegrationAdapter:
    """
    Stable integration layer for the current repository.
    """

    def __init__(
        self,
        modules: Optional[
            Dict[str, Any]
        ] = None,
    ):

        self.modules = (
            modules or {}
        )

        self.stage_results: Dict[
            str,
            AdapterStageResult,
        ] = {}

        self.warnings: List[str] = []

        self.errors: List[str] = []

    # ========================================================
    # MODULE ACCESS
    # ========================================================

    def module(
        self,
        name: str,
    ):

        result = self.modules.get(
            name
        )

        if isinstance(
            result,
            dict,
        ):

            if result.get(
                "ok"
            ):

                return result.get(
                    "module"
                )

            return None

        return result

    # ========================================================
    # STAGE RECORDING
    # ========================================================

    def record_stage(
        self,
        stage: str,
        result: Any = None,
        function: Optional[str] = None,
        signature: Optional[str] = None,
        warning: Optional[str] = None,
        error: Optional[str] = None,
    ) -> Any:

        if error:

            status = "error"

            self.errors.append(
                f"{stage}: {error}"
            )

        elif warning:

            status = "warning"

            self.warnings.append(
                f"{stage}: {warning}"
            )

        else:

            status = "completed"

        self.stage_results[
            stage
        ] = AdapterStageResult(
            stage=stage,
            status=status,
            result=result,
            error=error,
            warning=warning,
            function=function,
            signature=signature,
        )

        return result

    # ========================================================
    # DOCUMENT
    # ========================================================

    def parse_document(
        self,
        file_bytes: bytes,
        filename: str = "patent.pdf",
    ) -> Dict[str, Any]:

        module = self.module(
            "document_parser"
        )

        if module is None:

            return self.record_stage(
                "document",
                error=(
                    "document_parser "
                    "module unavailable"
                ),
            )

        # Current repository parser.
        function = get_function(
            module,
            [
                "extract_text_from_file",
                "extract_pdf_text",
                "parse_document",
                "parse_pdf",
            ],
        )

        if function is None:

            return self.record_stage(
                "document",
                error=(
                    "No compatible document "
                    "parser function found."
                ),
            )

        signature = function_signature(
            function
        )

        call = safe_call(
            function,
            file_bytes,
            filename,
        )

        if not call["ok"]:

            # Some parser functions accept
            # only bytes.
            call = safe_call(
                function,
                file_bytes,
            )

        if not call["ok"]:

            return self.record_stage(
                "document",
                function=getattr(
                    function,
                    "__name__",
                    None,
                ),
                signature=signature,
                error=call["error"],
            )

        raw = call["result"]

        document = normalize_document(
            raw
        )

        # If parser returned plain text,
        # enrich it using rule_engine extraction
        # when available.
        if not document.get(
            "text"
        ) and isinstance(
            raw,
            str,
        ):

            document[
                "text"
            ] = raw

        return self.record_stage(
            "document",
            result=document,
            function=getattr(
                function,
                "__name__",
                None,
            ),
            signature=signature,
        )

    # ========================================================
    # CLAIM ANALYSIS
    # ========================================================

    def analyze_claims(
        self,
        document: Dict[str, Any],
    ) -> Dict[str, Any]:

        module = self.module(
            "claim_analyzer"
        )

        if module is None:

            return self.record_stage(
                "claims",
                error=(
                    "claim_analyzer "
                    "module unavailable"
                ),
            )

        claims = normalize_claims(
            document.get(
                "claims"
            )
        )

        # Current V3 claim analyzer expects
        # list[dict] with number/text.
        function = get_function(
            module,
            [
                "analyze_claims",
                "analyze_claim_structure",
            ],
        )

        if function is None:

            return self.record_stage(
                "claims",
                error=(
                    "No compatible claim "
                    "analysis function found."
                ),
            )

        signature = function_signature(
            function
        )

        call = safe_call(
            function,
            claims,
        )

        if not call["ok"]:

            return self.record_stage(
                "claims",
                function=getattr(
                    function,
                    "__name__",
                    None,
                ),
                signature=signature,
                error=call["error"],
            )

        return self.record_stage(
            "claims",
            result=call["result"],
            function=getattr(
                function,
                "__name__",
                None,
            ),
            signature=signature,
        )

    # ========================================================
    # RULE ENGINE
    # ========================================================

    def run_rules(
        self,
        document: Dict[str, Any],
    ) -> Dict[str, Any]:

        module = self.module(
            "rule_engine"
        )

        if module is None:

            return self.record_stage(
                "rules",
                error=(
                    "rule_engine module unavailable"
                ),
            )

        # The current rule_engine.py contains
        # helper functions that operate on text.
        #
        # It also has a zero-argument run_rule_engine()
        # in the current repository.
        #
        # Therefore we first inspect the callable.

        function = get_function(
            module,
            [
                "run_rule_engine",
            ],
        )

        if function is not None:

            signature = function_signature(
                function
            )

            try:

                sig = inspect.signature(
                    function
                )

                required = [
                    p
                    for p in sig.parameters.values()
                    if (
                        p.default
                        is inspect.Parameter.empty
                        and p.kind
                        in (
                            inspect.Parameter.POSITIONAL_ONLY,
                            inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        )
                    )
                ]

                if not required:

                    call = safe_call(
                        function
                    )

                    if call["ok"]:

                        return self.record_stage(
                            "rules",
                            result=call["result"],
                            function="run_rule_engine",
                            signature=signature,
                        )

            except Exception:
                pass

        # Fallback to deterministic helpers.
        text = document.get(
            "text",
            "",
        )

        sections = {}

        detect_sections = get_function(
            module,
            [
                "detect_sections",
            ],
        )

        if detect_sections:

            call = safe_call(
                detect_sections,
                text,
            )

            if call["ok"]:

                sections = (
                    call["result"]
                    or {}
                )

        title = ""

        extract_title = get_function(
            module,
            [
                "extract_title",
            ],
        )

        if extract_title:

            call = safe_call(
                extract_title,
                text,
            )

            if call["ok"]:

                title = (
                    call["result"]
                    or ""
                )

        abstract = ""

        extract_abstract = get_function(
            module,
            [
                "extract_abstract",
            ],
        )

        if extract_abstract:

            call = safe_call(
                extract_abstract,
                text,
            )

            if call["ok"]:

                abstract = (
                    call["result"]
                    or ""
                )

        extract_claims = get_function(
            module,
            [
                "extract_claims",
            ],
        )

        raw_claims = []

        if extract_claims:

            call = safe_call(
                extract_claims,
                text,
            )

            if call["ok"]:

                raw_claims = (
                    call["result"]
                    or []
                )

        # Prefer parser claims if
        # rule-engine extraction failed.
        if not raw_claims:

            raw_claims = (
                document.get(
                    "claims"
                )
                or []
            )

        rule_output = {
            "status": "completed",
            "title": title,
            "abstract": abstract,
            "sections": sections,
            "claims": raw_claims,
        }

        return self.record_stage(
            "rules",
            result=rule_output,
            function="deterministic_helpers",
        )

    # ========================================================
    # SECTION 3
    # ========================================================

    def section3(
        self,
        document: Dict[str, Any],
        claims: Dict[str, Any],
    ) -> Dict[str, Any]:

        module = self.module(
            "section3_analyzer"
        )

        if module is None:

            return self.record_stage(
                "section3",
                warning=(
                    "Section 3 analyzer is not "
                    "available in the current repository."
                ),
                result={
                    "status": "not_available",
                    "findings": [],
                },
            )

        # Try common APIs.
        function = get_function(
            module,
            [
                "analyze_section_3",
                "screen_document",
                "screen_claim",
                "analyze",
            ],
        )

        if function is None:

            return self.record_stage(
                "section3",
                warning=(
                    "No compatible Section 3 "
                    "function is exposed by the module."
                ),
                result={
                    "status": "not_available",
                    "findings": [],
                },
            )

        signature = function_signature(
            function
        )

        # Prepare possible arguments.
        candidates = [
            (
                document,
                claims,
            ),
            (
                claims,
            ),
            (
                document,
            ),
        ]

        for args in candidates:

            call = safe_call(
                function,
                *args,
            )

            if call["ok"]:

                return self.record_stage(
                    "section3",
                    result=call["result"],
                    function=getattr(
                        function,
                        "__name__",
                        None,
                    ),
                    signature=signature,
                )

        return self.record_stage(
            "section3",
            warning=(
                "Section 3 module exists, but "
                "its current function signature "
                "does not match the adapter."
            ),
            function=getattr(
                function,
                "__name__",
                None,
            ),
            signature=signature,
            result={
                "status": "not_available",
                "findings": [],
            },
        )

    # ========================================================
    # PRIOR ART
    # ========================================================

    def prior_art(
        self,
        document: Dict[str, Any],
        claims: Dict[str, Any],
    ) -> Dict[str, Any]:

        module = self.module(
            "prior_art"
        )

        if module is None:

            return self.record_stage(
                "prior_art",
                warning=(
                    "Prior-art module unavailable."
                ),
                result={
                    "status": "not_available",
                    "queries": [],
                },
            )

        title = (
            document.get(
                "title"
            )
            or ""
        )

        abstract = (
            document.get(
                "abstract"
            )
            or ""
        )

        claim_list = normalize_claims(
            claims.get(
                "claims",
                document.get(
                    "claims",
                    [],
                ),
            )
        )

        queries = []

        # ----------------------------------------------------
        # Current repository API
        # ----------------------------------------------------

        build_queries = get_function(
            module,
            [
                "build_queries",
                "generate_search_queries",
                "build_claim_search_queries",
            ],
        )

        if build_queries:

            signature = function_signature(
                build_queries
            )

            call = safe_call(
                build_queries,
                title,
                abstract,
                claim_list,
            )

            if call["ok"]:

                queries = (
                    call["result"]
                    or []
                )

                return self.record_stage(
                    "prior_art",
                    result={
                        "status": "completed",
                        "queries": queries,
                    },
                    function=getattr(
                        build_queries,
                        "__name__",
                        None,
                    ),
                    signature=signature,
                )

        # ----------------------------------------------------
        # V3-style fallback
        # ----------------------------------------------------

        prepare = get_function(
            module,
            [
                "prepare_prior_art_analysis",
            ],
        )

        if prepare:

            signature = function_signature(
                prepare
            )

            # Never call this blindly with one argument.
            # Inspect required parameters first.

            try:

                sig = inspect.signature(
                    prepare
                )

                params = list(
                    sig.parameters.values()
                )

                required = [
                    p
                    for p in params
                    if (
                        p.default
                        is inspect.Parameter.empty
                        and p.kind
                        in (
                            inspect.Parameter.POSITIONAL_ONLY,
                            inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        )
                    )
                ]

                # Build candidates/evidence as an
                # empty collection for planning-only mode.
                if len(required) >= 2:

                    call = safe_call(
                        prepare,
                        {
                            "claims": claim_list,
                            "title": title,
                            "abstract": abstract,
                        },
                        [],
                    )

                else:

                    call = safe_call(
                        prepare,
                        {
                            "claims": claim_list,
                            "title": title,
                            "abstract": abstract,
                        },
                    )

                if call["ok"]:

                    return self.record_stage(
                        "prior_art",
                        result=call["result"],
                        function=getattr(
                            prepare,
                            "__name__",
                            None,
                        ),
                        signature=signature,
                    )

            except Exception:
                pass

        return self.record_stage(
            "prior_art",
            warning=(
                "Prior-art module loaded, but no "
                "compatible search function could "
                "be executed."
            ),
            result={
                "status": "not_available",
                "queries": [],
            },
        )

    # ========================================================
    # NOVELTY
    # ========================================================

    def novelty(
        self,
        claims: Dict[str, Any],
        evidence: Optional[Any] = None,
        documents: Optional[Any] = None,
    ) -> Dict[str, Any]:

        module = self.module(
            "novelty_analyzer"
        )

        if module is None:

            return self.record_stage(
                "novelty",
                warning=(
                    "Novelty analyzer unavailable."
                ),
                result={
                    "status": "not_available",
                    "findings": [],
                },
            )

        function = get_function(
            module,
            [
                "analyze_novelty",
                "screen_novelty",
                "analyze_claim_novelty",
            ],
        )

        if function is None:

            return self.record_stage(
                "novelty",
                warning=(
                    "No compatible novelty function."
                ),
                result={
                    "status": "not_available",
                    "findings": [],
                },
            )

        signature = function_signature(
            function
        )

        claim_data = claims or {}
        evidence_data = evidence or {}
        document_data = documents or []

        # Current V3 analyzer requires
        # evidence_analysis.
        attempts = [
            (
                claim_data,
                evidence_data,
            ),
            (
                claim_data,
                evidence_data,
                document_data,
            ),
        ]

        for args in attempts:

            call = safe_call(
                function,
                *args,
            )

            if call["ok"]:

                return self.record_stage(
                    "novelty",
                    result=call["result"],
                    function=getattr(
                        function,
                        "__name__",
                        None,
                    ),
                    signature=signature,
                )

        return self.record_stage(
            "novelty",
            warning=(
                "Novelty analyzer requires "
                "evidence analysis. No verified "
                "evidence packet is currently "
                "available, so novelty analysis "
                "was not executed."
            ),
            result={
                "status": "awaiting_evidence",
                "findings": [],
            },
            function=getattr(
                function,
                "__name__",
                None,
            ),
            signature=signature,
        )

    # ========================================================
    # INVENTIVE STEP
    # ========================================================

    def inventive_step(
        self,
        claims: Dict[str, Any],
        evidence: Optional[Any] = None,
        documents: Optional[Any] = None,
    ) -> Dict[str, Any]:

        module = self.module(
            "inventive_step_analyzer"
        )

        if module is None:

            return self.record_stage(
                "inventive_step",
                warning=(
                    "Inventive-step analyzer unavailable."
                ),
                result={
                    "status": "not_available",
                    "findings": [],
                },
            )

        function = get_function(
            module,
            [
                "analyze_inventive_step",
                "screen_inventive_step",
            ],
        )

        if function is None:

            return self.record_stage(
                "inventive_step",
                warning=(
                    "No compatible inventive-step "
                    "function."
                ),
                result={
                    "status": "not_available",
                    "findings": [],
                },
            )

        signature = function_signature(
            function
        )

        # The current implementation expects:
        #
        # claims
        # evidence_analysis
        # documents

        if evidence is None:

            return self.record_stage(
                "inventive_step",
                warning=(
                    "Inventive-step analysis requires "
                    "evidence analysis. No evidence "
                    "packet is currently available."
                ),
                result={
                    "status": "awaiting_evidence",
                    "findings": [],
                },
                function=getattr(
                    function,
                    "__name__",
                    None,
                ),
                signature=signature,
            )

        call = safe_call(
            function,
            claims,
            evidence,
            documents or [],
        )

        if call["ok"]:

            return self.record_stage(
                "inventive_step",
                result=call["result"],
                function=getattr(
                    function,
                    "__name__",
                    None,
                ),
                signature=signature,
            )

        return self.record_stage(
            "inventive_step",
            warning=(
                "Inventive-step function could not "
                "be executed with the available "
                "evidence/documents."
            ),
            result={
                "status": "awaiting_evidence",
                "findings": [],
            },
            function=getattr(
                function,
                "__name__",
                None,
            ),
            signature=signature,
        )

    # ========================================================
    # PROSECUTION
    # ========================================================

    def prosecution(
        self,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:

        module = self.module(
            "prosecution_analyzer"
        )

        if module is None:

            return self.record_stage(
                "prosecution",
                warning=(
                    "Prosecution analyzer unavailable."
                ),
                result={
                    "status": "not_available",
                },
            )

        function = get_function(
            module,
            [
                "analyze_prosecution",
                "create_prosecution_dashboard",
                "analyze_prosecution_history",
            ],
        )

        if function is None:

            return self.record_stage(
                "prosecution",
                warning=(
                    "No compatible prosecution "
                    "function."
                ),
                result={
                    "status": "not_available",
                },
            )

        signature = function_signature(
            function
        )

        # Some versions expose a no-argument
        # analyzer that returns a configuration/
        # class-level result.

        try:

            sig = inspect.signature(
                function
            )

            required = [
                p
                for p in sig.parameters.values()
                if (
                    p.default
                    is inspect.Parameter.empty
                    and p.kind
                    in (
                        inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    )
                )
            ]

            if not required:

                call = safe_call(
                    function
                )

            else:

                call = safe_call(
                    function,
                    data,
                )

            if call["ok"]:

                return self.record_stage(
                    "prosecution",
                    result=call["result"],
                    function=getattr(
                        function,
                        "__name__",
                        None,
                    ),
                    signature=signature,
                )

        except Exception:
            pass

        return self.record_stage(
            "prosecution",
            warning=(
                "Prosecution analyzer could not "
                "be executed with the current "
                "input structure."
            ),
            result={
                "status": "not_available",
            },
            function=getattr(
                function,
                "__name__",
                None,
            ),
            signature=signature,
        )

    # ========================================================
    # KNOWLEDGE GRAPH
    # ========================================================

    def knowledge_graph(
        self,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:

        module = self.module(
            "knowledge_graph"
        )

        if module is None:

            return self.record_stage(
                "knowledge_graph",
                warning=(
                    "Knowledge graph module unavailable."
                ),
                result={
                    "status": "not_available",
                },
            )

        function = get_function(
            module,
            [
                "create_knowledge_graph",
                "build_knowledge_graph",
                "create_graph",
            ],
        )

        if function is None:

            return self.record_stage(
                "knowledge_graph",
                warning=(
                    "No compatible knowledge "
                    "graph function."
                ),
                result={
                    "status": "not_available",
                },
            )

        signature = function_signature(
            function
        )

        try:

            sig = inspect.signature(
                function
            )

            required = [
                p
                for p in sig.parameters.values()
                if (
                    p.default
                    is inspect.Parameter.empty
                    and p.kind
                    in (
                        inspect.Parameter.POSITIONAL_ONLY,
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                    )
                )
            ]

            if not required:

                call = safe_call(
                    function
                )

            else:

                call = safe_call(
                    function,
                    data,
                )

            if call["ok"]:

                return self.record_stage(
                    "knowledge_graph",
                    result=call["result"],
                    function=getattr(
                        function,
                        "__name__",
                        None,
                    ),
                    signature=signature,
                )

        except Exception:
            pass

        return self.record_stage(
            "knowledge_graph",
            warning=(
                "Knowledge graph could not "
                "be constructed from the "
                "current result structure."
            ),
            result={
                "status": "not_available",
            },
            function=getattr(
                function,
                "__name__",
                None,
            ),
            signature=signature,
        )

    # ========================================================
    # VALIDATION
    # ========================================================

    def validate(
        self,
        data: Dict[str, Any],
    ) -> Dict[str, Any]:

        module = self.module(
            "validation"
        )

        if module is None:

            return self.record_stage(
                "validation",
                warning=(
                    "Validation module unavailable."
                ),
                result={
                    "status": "not_available",
                },
            )

        function = get_function(
            module,
            [
                "validate_analysis",
                "validate_pipeline",
                "quick_validate",
                "validate",
            ],
        )

        if function is None:

            return self.record_stage(
                "validation",
                warning=(
                    "No compatible validation function."
                ),
                result={
                    "status": "not_available",
                },
            )

        signature = function_signature(
            function
        )

        call = safe_call(
            function,
            data,
        )

        if call["ok"]:

            return self.record_stage(
                "validation",
                result=call["result"],
                function=getattr(
                    function,
                    "__name__",
                    None,
                ),
                signature=signature,
            )

        # Try no-argument validators.
        call = safe_call(
            function
        )

        if call["ok"]:

            return self.record_stage(
                "validation",
                result=call["result"],
                function=getattr(
                    function,
                    "__name__",
                    None,
                ),
                signature=signature,
            )

        return self.record_stage(
            "validation",
            warning=(
                "Validation function could "
                "not be executed."
            ),
            result={
                "status": "not_available",
            },
            function=getattr(
                function,
                "__name__",
                None,
            ),
            signature=signature,
        )

    # ========================================================
    # COMPLETE PIPELINE
    # ========================================================

    def analyze(
        self,
        file_bytes: bytes,
        filename: str = "patent.pdf",
    ) -> AdapterPipelineResult:

        started_at = utc_now()

        analysis_id = stable_id(
            "ANALYSIS",
            (
                filename
                + str(
                    len(
                        file_bytes
                    )
                )
                + hashlib.sha256(
                    file_bytes
                ).hexdigest()
            ),
        )

        # ----------------------------------------------------
        # DOCUMENT
        # ----------------------------------------------------

        document = self.parse_document(
            file_bytes,
            filename,
        )

        if not document:

            document = {}

        # ----------------------------------------------------
        # CLAIMS
        # ----------------------------------------------------

        claims = self.analyze_claims(
            document
        )

        # ----------------------------------------------------
        # RULES
        # ----------------------------------------------------

        rules = self.run_rules(
            document
        )

        # ----------------------------------------------------
        # SECTION 3
        # ----------------------------------------------------

        section3 = self.section3(
            document,
            claims
            if isinstance(
                claims,
                dict,
            )
            else {},
        )

        # ----------------------------------------------------
        # PRIOR ART
        # ----------------------------------------------------

        prior_art = self.prior_art(
            document,
            claims
            if isinstance(
                claims,
                dict,
            )
            else {},
        )

        # ----------------------------------------------------
        # EVIDENCE
        # ----------------------------------------------------

        evidence = {
            "status": "not_run",
            "reason": (
                "Evidence retrieval requires "
                "search candidates/documents."
            ),
        }

        self.record_stage(
            "evidence",
            result=evidence,
            warning=(
                "No external prior-art documents "
                "were supplied, so evidence retrieval "
                "was not executed."
            ),
        )

        # ----------------------------------------------------
        # NOVELTY
        # ----------------------------------------------------

        novelty = self.novelty(
            claims
            if isinstance(
                claims,
                dict,
            )
            else {},
            evidence=None,
            documents=[],
        )

        # ----------------------------------------------------
        # INVENTIVE STEP
        # ----------------------------------------------------

        inventive_step = self.inventive_step(
            claims
            if isinstance(
                claims,
                dict,
            )
            else {},
            evidence=None,
            documents=[],
        )

        # ----------------------------------------------------
        # PROSECUTION
        # ----------------------------------------------------

        prosecution = self.prosecution(
            {
                "document": document,
                "claims": claims,
                "rules": rules,
                "section3": section3,
                "prior_art": prior_art,
                "novelty": novelty,
                "inventive_step": inventive_step,
            }
        )

        # ----------------------------------------------------
        # KNOWLEDGE GRAPH
        # ----------------------------------------------------

        graph = self.knowledge_graph(
            {
                "document": document,
                "claims": claims,
                "rules": rules,
                "section3": section3,
                "prior_art": prior_art,
                "evidence": evidence,
                "novelty": novelty,
                "inventive_step": inventive_step,
                "prosecution": prosecution,
            }
        )

        # ----------------------------------------------------
        # COMPLETE DATA
        # ----------------------------------------------------

        all_results = {
            "document": document,
            "claims": claims,
            "rules": rules,
            "section3": section3,
            "prior_art": prior_art,
            "evidence": evidence,
            "novelty": novelty,
            "inventive_step": inventive_step,
            "prosecution": prosecution,
            "knowledge_graph": graph,
        }

        # ----------------------------------------------------
        # VALIDATION
        # ----------------------------------------------------

        validation = self.validate(
            all_results
        )

        all_results[
            "validation"
        ] = validation

        completed_at = utc_now()

        # ----------------------------------------------------
        # STATUS
        # ----------------------------------------------------

        if self.errors:

            overall_status = "partial"

        elif self.warnings:

            overall_status = "completed_with_warnings"

        else:

            overall_status = "completed"

        return AdapterPipelineResult(
            adapter_version=(
                INTEGRATION_ADAPTER_VERSION
            ),
            analysis_id=analysis_id,
            status=overall_status,
            document={
                "filename": filename,
                "size_bytes": len(
                    file_bytes
                ),
                "sha256": hashlib.sha256(
                    file_bytes
                ).hexdigest(),
            },
            stages={
                name: stage.to_dict()
                for name, stage
                in self.stage_results.items()
            },
            warnings=list(
                self.warnings
            ),
            errors=list(
                self.errors
            ),
            started_at=started_at,
            completed_at=completed_at,
        )


# ============================================================
# FACTORY
# ============================================================

def create_integration_adapter(
    modules: Optional[
        Dict[str, Any]
    ] = None,
) -> PatentIntegrationAdapter:
    """
    Create a configured integration adapter.
    """

    return PatentIntegrationAdapter(
        modules=modules
    )


# ============================================================
# CONVENIENCE API
# ============================================================

def run_integration_test(
    file_bytes: bytes,
    filename: str,
    modules: Dict[str, Any],
) -> Dict[str, Any]:
    """
    Run the integration adapter and return
    a JSON-friendly dictionary.
    """

    adapter = PatentIntegrationAdapter(
        modules=modules
    )

    result = adapter.analyze(
        file_bytes=file_bytes,
        filename=filename,
    )

    return result.to_dict()


# ============================================================
# PUBLIC API
# ============================================================

__all__ = [
    "INTEGRATION_ADAPTER_VERSION",
    "AdapterStageResult",
    "AdapterPipelineResult",
    "PatentIntegrationAdapter",
    "create_integration_adapter",
    "run_integration_test",
    "normalize_claims",
    "normalize_document",
    "serialize_value",
]
