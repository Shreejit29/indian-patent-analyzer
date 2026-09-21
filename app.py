"""
Indian Patent Analyzer
V3 Integration Test Dashboard

Purpose
-------
This application is currently being used to test the V3 backend
architecture before adding further production modules.

Pipeline:

PDF
 ↓
Document Parser
 ↓
Claims / Limitations
 ↓
Rule Engine
 ↓
Section 3 Screening
 ↓
Prior-Art Planning
 ↓
Novelty Screening
 ↓
Inventive-Step Screening
 ↓
Prosecution Analysis
 ↓
Knowledge Graph
 ↓
Validation

Run:
    streamlit run app.py
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List

import streamlit as st


# ============================================================
# APPLICATION CONFIGURATION
# ============================================================

APP_VERSION = "3.0.0"

MODULES = [
    "document_parser",
    "claim_analyzer",
    "rule_engine",
    "prior_art",
    "evidence_engine",
    "scoring",
    "section3_analyzer",
    "novelty_analyzer",
    "inventive_step_analyzer",
    "amendment_analyzer",
    "prosecution_analyzer",
    "knowledge_graph",
    "provenance",
    "validation",
    "report_generator",
]


# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Indian Patent Analyzer",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CUSTOM CSS
# ============================================================

st.markdown(
    """
    <style>

    .main-title {
        font-size: 2.3rem;
        font-weight: 700;
        margin-bottom: 0.1rem;
    }

    .subtitle {
        color: #6b7280;
        font-size: 1rem;
        margin-bottom: 1.5rem;
    }

    .section-title {
        font-size: 1.35rem;
        font-weight: 650;
        margin-top: 1rem;
        margin-bottom: 0.75rem;
    }

    .small-muted {
        color: #6b7280;
        font-size: 0.82rem;
    }

    .pipeline-box {
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 1rem;
        margin-bottom: 1rem;
    }

    .success-box {
        border-left: 5px solid #16a34a;
        padding: 0.75rem;
        border-radius: 8px;
        background: rgba(22, 163, 74, 0.05);
    }

    .warning-box {
        border-left: 5px solid #f59e0b;
        padding: 0.75rem;
        border-radius: 8px;
        background: rgba(245, 158, 11, 0.05);
    }

    .error-box {
        border-left: 5px solid #dc2626;
        padding: 0.75rem;
        border-radius: 8px;
        background: rgba(220, 38, 38, 0.05);
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# GENERAL HELPERS
# ============================================================

def utc_now() -> str:
    """Return current UTC timestamp."""
    return datetime.now(timezone.utc).isoformat()


def safe_import(module_name: str) -> Dict[str, Any]:
    """
    Import a module safely.

    IMPORTANT:
    Do not cache imported module objects with st.cache_data.
    Python module objects are not serializable by Streamlit.
    """

    try:
        module = __import__(
            module_name,
            fromlist=["*"],
        )

        return {
            "ok": True,
            "module": module,
            "error": None,
            "traceback": None,
        }

    except Exception as exc:

        return {
            "ok": False,
            "module": None,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }


def check_modules() -> Dict[str, Dict[str, Any]]:
    """
    Check all registered backend modules.

    Deliberately NOT cached because the returned objects include
    Python module objects.
    """

    results = {}

    for module_name in MODULES:

        results[module_name] = safe_import(
            f"services.{module_name}"
        )

    return results


def call_first_available(
    module: Any,
    function_names: List[str],
    *args,
    **kwargs,
):
    """
    Call the first compatible function available in a module.
    """

    for function_name in function_names:

        function = getattr(
            module,
            function_name,
            None,
        )

        if callable(function):

            return function(
                *args,
                **kwargs,
            )

    raise AttributeError(
        "No compatible function found. "
        f"Tried: {', '.join(function_names)}"
    )


def normalize_result(value: Any) -> Any:
    """
    Convert arbitrary Python results into JSON-friendly structures.
    """

    if value is None:
        return None

    # Custom to_dict()
    if hasattr(value, "to_dict"):

        try:

            return normalize_result(
                value.to_dict()
            )

        except Exception:
            pass

    # Dataclass
    if hasattr(value, "__dataclass_fields__"):

        try:

            from dataclasses import asdict

            return normalize_result(
                asdict(value)
            )

        except Exception:
            pass

    # Dictionary
    if isinstance(value, dict):

        return {
            str(key): normalize_result(val)
            for key, val in value.items()
        }

    # List
    if isinstance(value, list):

        return [
            normalize_result(item)
            for item in value
        ]

    # Tuple
    if isinstance(value, tuple):

        return [
            normalize_result(item)
            for item in value
        ]

    # Set
    if isinstance(value, set):

        return [
            normalize_result(item)
            for item in value
        ]

    # Primitive
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

    # Fallback
    try:

        json.dumps(value)

        return value

    except Exception:

        return str(value)


def show_json(
    data: Any,
):
    """
    Display data safely.
    """

    normalized = normalize_result(
        data
    )

    try:

        st.json(
            normalized,
            expanded=False,
        )

    except Exception:

        st.code(
            json.dumps(
                normalized,
                indent=2,
                default=str,
            ),
            language="json",
        )


def result_size(value: Any) -> int:
    """
    Estimate number of records contained in a result.
    """

    if value is None:
        return 0

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):

        return len(value)

    if isinstance(value, dict):

        candidate_keys = [
            "items",
            "claims",
            "limitations",
            "findings",
            "results",
            "evidence",
            "documents",
            "issues",
            "nodes",
            "edges",
            "queries",
        ]

        for key in candidate_keys:

            candidate = value.get(key)

            if isinstance(
                candidate,
                (
                    list,
                    tuple,
                    set,
                ),
            ):

                return len(candidate)

    return 1


def module_version(module: Any) -> Dict[str, Any]:
    """
    Extract version constants from a module.
    """

    versions = {}

    try:

        for name in dir(module):

            if "VERSION" not in name.upper():
                continue

            try:

                value = getattr(
                    module,
                    name,
                )

                if isinstance(
                    value,
                    (
                        str,
                        int,
                        float,
                    ),
                ):

                    versions[name] = value

            except Exception:
                continue

    except Exception:
        pass

    return versions


def public_callables(module: Any) -> List[str]:
    """
    Return public callable names from a module.
    """

    names = []

    try:

        for name in dir(module):

            if name.startswith("_"):
                continue

            try:

                obj = getattr(
                    module,
                    name,
                )

                if callable(obj):

                    names.append(name)

            except Exception:
                continue

    except Exception:
        pass

    return sorted(names)


# ============================================================
# MODULE HEALTH
# ============================================================

module_results = check_modules()

loaded_modules = [
    name
    for name, result in module_results.items()
    if result["ok"]
]

failed_modules = [
    name
    for name, result in module_results.items()
    if not result["ok"]
]

loaded_count = len(loaded_modules)
failed_count = len(failed_modules)
total_count = len(MODULES)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">⚖️ Indian Patent Analyzer</div>',
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="subtitle">
        V{APP_VERSION} — Integration Test Build
    </div>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR
# ============================================================

with st.sidebar:

    st.header("Navigation")

    page = st.radio(
        "Select page",
        [
            "🏠 Dashboard",
            "📄 Patent Analysis",
            "🧪 Module Test",
            "📊 Results",
            "ℹ️ About",
        ],
    )

    st.divider()

    st.subheader("System")

    st.write(
        f"**Version:** {APP_VERSION}"
    )

    st.write(
        f"**Modules:** "
        f"{loaded_count}/{total_count}"
    )

    if failed_count == 0:

        st.success(
            "System Ready"
        )

    else:

        st.warning(
            f"{failed_count} module(s) need attention"
        )

    st.divider()

    st.caption(
        "Automated patent analysis is a "
        "research and screening aid and "
        "is not a legal opinion."
    )


# ============================================================
# DASHBOARD
# ============================================================

if page == "🏠 Dashboard":

    st.subheader(
        "System Health"
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Modules Loaded",
            f"{loaded_count}/{total_count}",
        )

    with col2:

        st.metric(
            "Failed Modules",
            failed_count,
        )

    with col3:

        st.metric(
            "Application",
            APP_VERSION,
        )

    with col4:

        st.metric(
            "Mode",
            "TEST",
        )

    st.divider()

    st.subheader(
        "Backend Status"
    )

    columns = st.columns(3)

    for index, module_name in enumerate(
        MODULES
    ):

        result = module_results[
            module_name
        ]

        with columns[index % 3]:

            if result["ok"]:

                st.success(
                    f"✅ {module_name}"
                )

            else:

                st.error(
                    f"❌ {module_name}"
                )

                st.caption(
                    result["error"]
                )

    st.divider()

    if failed_count == 0:

        st.success(
            "All registered V3 backend modules "
            "loaded successfully."
        )

    else:

        st.warning(
            "Some modules failed to load. "
            "Open 'Module Test' to inspect "
            "the exact traceback."
        )

    st.divider()

    st.subheader(
        "Current Architecture"
    )

    st.markdown(
        """
        <div class="pipeline-box">

        **Patent PDF**

        ↓

        **Document Parser**

        ↓

        **Claims + Limitations**

        ↓

        **Rule Engine**

        ↓

        **Section 3 Screening**

        ↓

        **Prior-Art Search Planning**

        ↓

        **Evidence Retrieval / Verification**

        ↓

        **Novelty + Inventive Step**

        ↓

        **FER + Prosecution**

        ↓

        **Knowledge Graph**

        ↓

        **Validation**

        ↓

        **Report**

        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================
# PATENT ANALYSIS
# ============================================================

elif page == "📄 Patent Analysis":

    st.subheader(
        "Patent Document Analysis"
    )

    st.write(
        "Upload a patent PDF to test the current "
        "V3 analysis stack."
    )

    uploaded_file = st.file_uploader(
        "Upload Patent PDF",
        type=["pdf"],
        accept_multiple_files=False,
    )

    if uploaded_file is None:

        st.info(
            "Upload a PDF to begin testing."
        )

        st.markdown(
            """
            ### Test pipeline

            1. PDF parsing
            2. Claim extraction
            3. Limitation analysis
            4. Rule screening
            5. Section 3 screening
            6. Prior-art planning
            7. Novelty screening
            8. Inventive-step screening
            9. Prosecution analysis
            10. Knowledge graph
            11. Validation
            """
        )

    else:

        file_bytes = uploaded_file.getvalue()

        st.success(
            f"Loaded `{uploaded_file.name}` "
            f"— {len(file_bytes):,} bytes"
        )

        if st.button(
            "🚀 Run V3 Integration Test",
            type="primary",
            use_container_width=True,
        ):

            results = {}

            progress = st.progress(
                0
            )

            status = st.empty()

            # ----------------------------------------------------
            # STAGE 1
            # ----------------------------------------------------

            status.info(
                "Stage 1/10 — Parsing patent document..."
            )

            parser_result = module_results.get(
                "document_parser"
            )

            if not parser_result["ok"]:

                st.error(
                    "Document parser cannot be imported."
                )

                st.code(
                    parser_result["traceback"]
                )

                st.stop()

            try:

                parser = parser_result["module"]

                parsed = call_first_available(
                    parser,
                    [
                        "parse_document",
                        "parse_pdf",
                        "parse_file",
                    ],
                    file_bytes,
                )

                results[
                    "document"
                ] = parsed

                st.success(
                    "✅ Document parsing completed."
                )

            except Exception as exc:

                results[
                    "document_error"
                ] = str(exc)

                st.error(
                    f"Document parsing failed: {exc}"
                )

                st.code(
                    traceback.format_exc()
                )

                st.stop()

            progress.progress(
                10
            )

            # ----------------------------------------------------
            # STAGE 2
            # ----------------------------------------------------

            status.info(
                "Stage 2/10 — Analyzing claims..."
            )

            claim_result = module_results.get(
                "claim_analyzer"
            )

            try:

                if claim_result["ok"]:

                    claim_module = (
                        claim_result["module"]
                    )

                    claims = call_first_available(
                        claim_module,
                        [
                            "analyze_claims",
                            "extract_claims",
                            "parse_claims",
                            "analyze_claim",
                        ],
                        parsed,
                    )

                    results[
                        "claims"
                    ] = claims

                    st.success(
                        "✅ Claim analysis completed."
                    )

                else:

                    results[
                        "claims_error"
                    ] = claim_result["error"]

                    st.warning(
                        "Claim analyzer unavailable."
                    )

            except Exception as exc:

                results[
                    "claims_error"
                ] = str(exc)

                st.warning(
                    f"Claim analysis warning: {exc}"
                )

            progress.progress(
                20
            )

            # ----------------------------------------------------
            # STAGE 3
            # ----------------------------------------------------

            status.info(
                "Stage 3/10 — Running rule engine..."
            )

            rule_result = module_results.get(
                "rule_engine"
            )

            try:

                if rule_result["ok"]:

                    rule_module = (
                        rule_result["module"]
                    )

                    rules = call_first_available(
                        rule_module,
                        [
                            "run_rule_engine",
                            "check_claims",
                            "evaluate_rules",
                        ],
                        parsed,
                    )

                    results[
                        "rules"
                    ] = rules

                    st.success(
                        "✅ Rule engine completed."
                    )

                else:

                    results[
                        "rules_error"
                    ] = rule_result["error"]

                    st.warning(
                        "Rule engine unavailable."
                    )

            except Exception as exc:

                results[
                    "rules_error"
                ] = str(exc)

                st.warning(
                    f"Rule engine warning: {exc}"
                )

            progress.progress(
                30
            )

            # ----------------------------------------------------
            # STAGE 4
            # ----------------------------------------------------

            status.info(
                "Stage 4/10 — Section 3 screening..."
            )

            section3_result = module_results.get(
                "section3_analyzer"
            )

            try:

                if (
                    section3_result
                    and section3_result["ok"]
                ):

                    section3_module = (
                        section3_result["module"]
                    )

                    section3 = call_first_available(
                        section3_module,
                        [
                            "screen_document",
                            "analyze_section_3",
                            "screen_claim",
                        ],
                        parsed,
                    )

                    results[
                        "section3"
                    ] = section3

                    st.success(
                        "✅ Section 3 screening completed."
                    )

                else:

                    results[
                        "section3_error"
                    ] = (
                        section3_result["error"]
                        if section3_result
                        else "Module unavailable."
                    )

                    st.warning(
                        "Section 3 analyzer unavailable."
                    )

            except Exception as exc:

                results[
                    "section3_error"
                ] = str(exc)

                st.warning(
                    f"Section 3 warning: {exc}"
                )

            progress.progress(
                40
            )

            # ----------------------------------------------------
            # STAGE 5
            # ----------------------------------------------------

            status.info(
                "Stage 5/10 — Building prior-art search plan..."
            )

            prior_result = module_results.get(
                "prior_art"
            )

            try:

                if prior_result["ok"]:

                    prior_module = (
                        prior_result["module"]
                    )

                    prior_art = call_first_available(
                        prior_module,
                        [
                            "prepare_prior_art_analysis",
                            "build_search_plan",
                            "build_claim_search_queries",
                            "generate_search_queries",
                        ],
                        (
                            results.get(
                                "claims"
                            )
                            or parsed
                        ),
                    )

                    results[
                        "prior_art"
                    ] = prior_art

                    st.success(
                        "✅ Prior-art planning completed."
                    )

                else:

                    results[
                        "prior_art_error"
                    ] = prior_result["error"]

                    st.warning(
                        "Prior-art module unavailable."
                    )

            except Exception as exc:

                results[
                    "prior_art_error"
                ] = str(exc)

                st.warning(
                    f"Prior-art warning: {exc}"
                )

            progress.progress(
                50
            )

            # ----------------------------------------------------
            # STAGE 6
            # ----------------------------------------------------

            status.info(
                "Stage 6/10 — Novelty screening..."
            )

            novelty_result = module_results.get(
                "novelty_analyzer"
            )

            try:

                if (
                    novelty_result
                    and novelty_result["ok"]
                ):

                    novelty_module = (
                        novelty_result["module"]
                    )

                    novelty = call_first_available(
                        novelty_module,
                        [
                            "analyze_novelty",
                            "screen_novelty",
                            "analyze_claim_novelty",
                            "calculate_novelty_statistics",
                        ],
                        (
                            results.get(
                                "claims"
                            )
                            or parsed
                        ),
                    )

                    results[
                        "novelty"
                    ] = novelty

                    st.success(
                        "✅ Novelty screening completed."
                    )

                else:

                    results[
                        "novelty_error"
                    ] = (
                        novelty_result["error"]
                        if novelty_result
                        else "Module unavailable."
                    )

                    st.warning(
                        "Novelty analyzer unavailable."
                    )

            except Exception as exc:

                results[
                    "novelty_error"
                ] = str(exc)

                st.warning(
                    f"Novelty warning: {exc}"
                )

            progress.progress(
                60
            )

            # ----------------------------------------------------
            # STAGE 7
            # ----------------------------------------------------

            status.info(
                "Stage 7/10 — Inventive-step screening..."
            )

            inventive_result = module_results.get(
                "inventive_step_analyzer"
            )

            try:

                if (
                    inventive_result
                    and inventive_result["ok"]
                ):

                    inventive_module = (
                        inventive_result["module"]
                    )

                    inventive_step = call_first_available(
                        inventive_module,
                        [
                            "analyze_inventive_step",
                            "screen_inventive_step",
                            "analyze_claim_inventive_step",
                            "analyze_claim",
                        ],
                        (
                            results.get(
                                "claims"
                            )
                            or parsed
                        ),
                    )

                    results[
                        "inventive_step"
                    ] = inventive_step

                    st.success(
                        "✅ Inventive-step screening completed."
                    )

                else:

                    results[
                        "inventive_step_error"
                    ] = (
                        inventive_result["error"]
                        if inventive_result
                        else "Module unavailable."
                    )

                    st.warning(
                        "Inventive-step analyzer unavailable."
                    )

            except Exception as exc:

                results[
                    "inventive_step_error"
                ] = str(exc)

                st.warning(
                    f"Inventive-step warning: {exc}"
                )

            progress.progress(
                70
            )

            # ----------------------------------------------------
            # STAGE 8
            # ----------------------------------------------------

            status.info(
                "Stage 8/10 — Prosecution analysis..."
            )

            prosecution_result = module_results.get(
                "prosecution_analyzer"
            )

            try:

                if (
                    prosecution_result
                    and prosecution_result["ok"]
                ):

                    prosecution_module = (
                        prosecution_result["module"]
                    )

                    prosecution = call_first_available(
                        prosecution_module,
                        [
                            "analyze_prosecution",
                            "create_prosecution_dashboard",
                            "analyze_prosecution_history",
                        ],
                        results,
                    )

                    results[
                        "prosecution"
                    ] = prosecution

                    st.success(
                        "✅ Prosecution analysis completed."
                    )

                else:

                    results[
                        "prosecution_error"
                    ] = (
                        prosecution_result["error"]
                        if prosecution_result
                        else "Module unavailable."
                    )

                    st.warning(
                        "Prosecution analyzer unavailable."
                    )

            except Exception as exc:

                results[
                    "prosecution_error"
                ] = str(exc)

                st.warning(
                    f"Prosecution warning: {exc}"
                )

            progress.progress(
                80
            )

            # ----------------------------------------------------
            # STAGE 9
            # ----------------------------------------------------

            status.info(
                "Stage 9/10 — Building knowledge graph..."
            )

            graph_result = module_results.get(
                "knowledge_graph"
            )

            try:

                if (
                    graph_result
                    and graph_result["ok"]
                ):

                    graph_module = (
                        graph_result["module"]
                    )

                    graph = call_first_available(
                        graph_module,
                        [
                            "create_knowledge_graph",
                            "build_knowledge_graph",
                            "create_graph",
                        ],
                        results,
                    )

                    results[
                        "knowledge_graph"
                    ] = graph

                    st.success(
                        "✅ Knowledge graph completed."
                    )

                else:

                    results[
                        "knowledge_graph_error"
                    ] = (
                        graph_result["error"]
                        if graph_result
                        else "Module unavailable."
                    )

                    st.warning(
                        "Knowledge graph module unavailable."
                    )

            except Exception as exc:

                results[
                    "knowledge_graph_error"
                ] = str(exc)

                st.warning(
                    f"Knowledge graph warning: {exc}"
                )

            progress.progress(
                90
            )

            # ----------------------------------------------------
            # STAGE 10
            # ----------------------------------------------------

            status.info(
                "Stage 10/10 — Validation..."
            )

            validation_result = module_results.get(
                "validation"
            )

            try:

                if (
                    validation_result
                    and validation_result["ok"]
                ):

                    validation_module = (
                        validation_result["module"]
                    )

                    validation = call_first_available(
                        validation_module,
                        [
                            "validate_analysis",
                            "validate_pipeline",
                            "quick_validate",
                            "validate",
                        ],
                        results,
                    )

                    results[
                        "validation"
                    ] = validation

                    st.success(
                        "✅ Validation completed."
                    )

                else:

                    results[
                        "validation_error"
                    ] = (
                        validation_result["error"]
                        if validation_result
                        else "Module unavailable."
                    )

                    st.warning(
                        "Validation module unavailable."
                    )

            except Exception as exc:

                results[
                    "validation_error"
                ] = str(exc)

                st.warning(
                    f"Validation warning: {exc}"
                )

            progress.progress(
                100
            )

            # ----------------------------------------------------
            # SAVE SESSION RESULTS
            # ----------------------------------------------------

            st.session_state[
                "analysis_results"
            ] = results

            st.session_state[
                "analysis_filename"
            ] = uploaded_file.name

            st.session_state[
                "analysis_bytes"
            ] = file_bytes

            status.success(
                "🎉 V3 integration test completed."
            )

            st.success(
                "Open the **📊 Results** page "
                "to inspect the output."
            )


# ============================================================
# MODULE TEST
# ============================================================

elif page == "🧪 Module Test":

    st.subheader(
        "V3 Backend Module Test"
    )

    st.write(
        "This page verifies that the current backend "
        "modules can be imported independently."
    )

    st.info(
        f"Loaded {loaded_count} of {total_count} modules."
    )

    st.divider()

    for module_name in MODULES:

        result = module_results[
            module_name
        ]

        if result["ok"]:

            with st.expander(
                f"✅ {module_name}",
                expanded=False,
            ):

                module = result["module"]

                st.write(
                    f"**Import:** Successful"
                )

                versions = module_version(
                    module
                )

                if versions:

                    st.write(
                        "**Version information:**"
                    )

                    st.json(
                        versions
                    )

                functions = public_callables(
                    module
                )

                st.write(
                    f"**Public callables:** "
                    f"{len(functions)}"
                )

                if functions:

                    st.code(
                        "\n".join(
                            functions
                        )
                    )

        else:

            with st.expander(
                f"❌ {module_name}",
                expanded=True,
            ):

                st.error(
                    result["error"]
                )

                if result.get(
                    "traceback"
                ):

                    st.code(
                        result["traceback"]
                    )


# ============================================================
# RESULTS PAGE
# ============================================================

elif page == "📊 Results":

    st.subheader(
        "Analysis Results"
    )

    results = st.session_state.get(
        "analysis_results"
    )

    filename = st.session_state.get(
        "analysis_filename"
    )

    if not results:

        st.info(
            "No analysis has been run yet."
        )

        st.write(
            "Go to **📄 Patent Analysis**, "
            "upload a patent PDF and run the test."
        )

    else:

        if filename:

            st.caption(
                f"Document: `{filename}`"
            )

        # --------------------------------------------------------
        # RESULT COUNTERS
        # --------------------------------------------------------

        successful = 0
        errors = 0

        for key, value in results.items():

            if key.endswith(
                "_error"
            ):

                errors += 1

            elif value is not None:

                successful += 1

        c1, c2, c3 = st.columns(3)

        with c1:

            st.metric(
                "Successful Results",
                successful,
            )

        with c2:

            st.metric(
                "Warnings / Errors",
                errors,
            )

        with c3:

            st.metric(
                "Total Result Sections",
                len(results),
            )

        st.divider()

        # --------------------------------------------------------
        # RESULT TABS
        # --------------------------------------------------------

        result_keys = list(
            results.keys()
        )

        tabs = st.tabs(
            [
                key.replace(
                    "_",
                    " ",
                ).title()
                for key in result_keys
            ]
        )

        for tab, key in zip(
            tabs,
            result_keys,
        ):

            with tab:

                value = results[
                    key
                ]

                if key.endswith(
                    "_error"
                ):

                    st.error(
                        str(value)
                    )

                elif value is None:

                    st.info(
                        "No result returned."
                    )

                else:

                    st.caption(
                        f"Type: "
                        f"`{type(value).__name__}`"
                    )

                    st.caption(
                        f"Estimated records: "
                        f"{result_size(value)}"
                    )

                    show_json(
                        value
                    )

        st.divider()

        # --------------------------------------------------------
        # DOWNLOAD JSON
        # --------------------------------------------------------

        json_data = json.dumps(
            normalize_result(
                results
            ),
            indent=2,
            default=str,
        )

        st.download_button(
            label="⬇️ Download Analysis JSON",
            data=json_data,
            file_name=(
                "patent_analysis_results.json"
            ),
            mime="application/json",
            use_container_width=True,
        )


# ============================================================
# ABOUT
# ============================================================

elif page == "ℹ️ About":

    st.subheader(
        "About the Test Build"
    )

    st.markdown(
        """
        ## Indian Patent Analyzer

        This build is intentionally focused on **testing the backend
        architecture before adding more production functionality**.

        ### Design philosophy

        The system separates:

        **Facts**

        ↓

        **Evidence**

        ↓

        **Rules**

        ↓

        **Analysis**

        ↓

        **AI Explanation**

        The AI layer should not become the authoritative source for
        legal facts or evidence.

        ### Current backend

        The current architecture includes:

        - Document parsing
        - Claim analysis
        - Limitation extraction
        - Rule engine
        - Prior-art search planning
        - Evidence processing
        - Section 3 screening
        - Novelty screening
        - Inventive-step screening
        - Amendment analysis
        - FER analysis
        - Prosecution analysis
        - Knowledge graph
        - Provenance
        - Validation
        - Report generation

        ### Next step

        The next development stage should be based on the actual
        integration-test results rather than adding more modules
        blindly.
        """
    )

    st.info(
        "Automated results are screening/research outputs "
        "and should be reviewed by a qualified patent professional."
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    f"Indian Patent Analyzer V{APP_VERSION} • "
    f"Integration Test Build • "
    f"{utc_now()}"
)
