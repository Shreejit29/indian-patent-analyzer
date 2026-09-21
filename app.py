"""
Indian Patent Analyzer
V3 Integration Test Dashboard

Purpose:
- Test the current V3 backend modules before adding more functionality.
- Upload a patent PDF.
- Run deterministic analysis.
- Display parser, claims, rules, Section 3, prior-art planning,
  novelty, inventive-step, prosecution, graph, scoring and validation.
- Clearly report failures instead of crashing the application.

Run:
    streamlit run app.py
"""

from __future__ import annotations

import io
import json
import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List

import streamlit as st


# ---------------------------------------------------------------------
# PAGE CONFIG
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="Indian Patent Analyzer",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------
# CONSTANTS
# ---------------------------------------------------------------------

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


# ---------------------------------------------------------------------
# STYLING
# ---------------------------------------------------------------------

st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.3rem;
        font-weight: 700;
        margin-bottom: 0.2rem;
    }

    .subtitle {
        color: #6b7280;
        font-size: 1rem;
        margin-bottom: 1.5rem;
    }

    .status-card {
        padding: 1rem;
        border-radius: 12px;
        border: 1px solid #e5e7eb;
        margin-bottom: 0.7rem;
    }

    .success {
        border-left: 5px solid #16a34a;
    }

    .warning {
        border-left: 5px solid #f59e0b;
    }

    .error {
        border-left: 5px solid #dc2626;
    }

    .info {
        border-left: 5px solid #2563eb;
    }

    .metric-label {
        font-size: 0.8rem;
        color: #6b7280;
    }

    .metric-value {
        font-size: 1.5rem;
        font-weight: 700;
    }

    .small-muted {
        color: #6b7280;
        font-size: 0.8rem;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_import(module_name: str):
    """
    Import a module without crashing the whole application.
    """
    try:
        module = __import__(module_name, fromlist=["*"])
        return {
            "ok": True,
            "module": module,
            "error": None,
        }
    except Exception as exc:
        return {
            "ok": False,
            "module": None,
            "error": f"{type(exc).__name__}: {exc}",
            "traceback": traceback.format_exc(),
        }


def call_first_available(module: Any, names: List[str], *args, **kwargs):
    """
    Call the first available function from a list.

    This is intentionally defensive because the V3 modules have
    backward-compatible function names.
    """
    for name in names:
        fn = getattr(module, name, None)

        if callable(fn):
            return fn(*args, **kwargs)

    raise AttributeError(
        f"No compatible function found. Tried: {', '.join(names)}"
    )


def normalize_result(value: Any) -> Any:
    """
    Convert dataclasses / objects into JSON-friendly structures.
    """
    if value is None:
        return None

    if hasattr(value, "to_dict") and callable(value.to_dict):
        try:
            return value.to_dict()
        except Exception:
            pass

    if hasattr(value, "__dataclass_fields__"):
        try:
            from dataclasses import asdict

            return asdict(value)
        except Exception:
            pass

    if isinstance(value, dict):
        return {
            str(k): normalize_result(v)
            for k, v in value.items()
        }

    if isinstance(value, list):
        return [normalize_result(v) for v in value]

    if isinstance(value, tuple):
        return [normalize_result(v) for v in value]

    if isinstance(value, set):
        return [normalize_result(v) for v in value]

    if isinstance(value, (str, int, float, bool)):
        return value

    try:
        json.dumps(value)
        return value
    except Exception:
        return str(value)


def count_items(value: Any) -> int:
    """
    Estimate the number of records in a result.
    """
    if value is None:
        return 0

    if isinstance(value, (list, tuple, set)):
        return len(value)

    if isinstance(value, dict):
        for key in (
            "items",
            "claims",
            "findings",
            "results",
            "evidence",
            "documents",
            "limitations",
            "issues",
            "nodes",
            "edges",
        ):
            if key in value and isinstance(value[key], (list, tuple, set)):
                return len(value[key])

    return 1


def show_json(data: Any, height: int = 500):
    """
    Safe JSON viewer.
    """
    normalized = normalize_result(data)

    try:
        st.json(normalized, expanded=False)
    except Exception:
        st.code(
            json.dumps(
                normalized,
                indent=2,
                default=str,
            ),
            language="json",
        )


def status_badge(ok: bool, label: str):
    if ok:
        st.success(f"✅ {label}")
    else:
        st.error(f"❌ {label}")


# ---------------------------------------------------------------------
# MODULE HEALTH CHECK
# ---------------------------------------------------------------------

@st.cache_data(show_spinner=False)
def check_modules():
    results = {}

    for module_name in MODULES:
        results[module_name] = safe_import(
            f"services.{module_name}"
        )

    return results


# ---------------------------------------------------------------------
# HEADER
# ---------------------------------------------------------------------

st.markdown(
    '<div class="main-title">⚖️ Indian Patent Analyzer</div>',
    unsafe_allow_html=True,
)

st.markdown(
    f"""
    <div class="subtitle">
        V{APP_VERSION} — Deterministic Patent Intelligence & Prosecution Analysis
    </div>
    """,
    unsafe_allow_html=True,
)


# ---------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------

with st.sidebar:
    st.header("System")

    st.caption(
        f"Application Version: {APP_VERSION}"
    )

    st.caption(
        f"Test Time: {utc_now()}"
    )

    st.divider()

    page = st.radio(
        "Navigate",
        [
            "🏠 Dashboard",
            "📄 Patent Analysis",
            "🧪 Module Test",
            "📊 Results",
            "ℹ️ About",
        ],
    )

    st.divider()

    st.caption(
        "This application provides automated screening and "
        "analysis support. It does not constitute legal advice."
    )


# ---------------------------------------------------------------------
# MODULE STATUS
# ---------------------------------------------------------------------

module_results = check_modules()

loaded_count = sum(
    1 for result in module_results.values()
    if result["ok"]
)

total_count = len(module_results)


# ---------------------------------------------------------------------
# DASHBOARD
# ---------------------------------------------------------------------

if page == "🏠 Dashboard":

    st.subheader("System Health")

    c1, c2, c3, c4 = st.columns(4)

    with c1:
        st.metric(
            "Modules",
            f"{loaded_count}/{total_count}",
        )

    with c2:
        st.metric(
            "Status",
            "READY" if loaded_count == total_count else "PARTIAL",
        )

    with c3:
        st.metric(
            "Version",
            APP_VERSION,
        )

    with c4:
        st.metric(
            "Mode",
            "Deterministic",
        )

    st.divider()

    st.subheader("Backend Modules")

    cols = st.columns(3)

    for index, module_name in enumerate(MODULES):
        result = module_results[module_name]

        with cols[index % 3]:
            if result["ok"]:
                st.success(
                    f"✅ `{module_name}`"
                )
            else:
                st.error(
                    f"❌ `{module_name}`"
                )
                st.caption(result["error"])

    st.divider()

    if loaded_count == total_count:
        st.success(
            "All registered V3 modules imported successfully."
        )
    else:
        st.warning(
            f"{total_count - loaded_count} module(s) could not be imported. "
            "Use the Module Test page to inspect the exact errors."
        )


# ---------------------------------------------------------------------
# PATENT ANALYSIS
# ---------------------------------------------------------------------

elif page == "📄 Patent Analysis":

    st.subheader("Patent Document Analysis")

    st.write(
        "Upload a patent PDF to test the current V3 analysis stack."
    )

    uploaded_file = st.file_uploader(
        "Upload Patent PDF",
        type=["pdf"],
        accept_multiple_files=False,
    )

    if uploaded_file is None:
        st.info(
            "Upload a PDF to begin."
        )

        st.markdown(
            """
            ### Analysis pipeline

            **PDF**
            → Document Parser
            → Claims
            → Limitations
            → Rule Engine
            → Section 3
            → Prior Art Plan
            → Evidence
            → Novelty
            → Inventive Step
            → Prosecution
            → Knowledge Graph
            → Validation
            """
        )

    else:

        file_bytes = uploaded_file.getvalue()

        st.success(
            f"Loaded `{uploaded_file.name}` "
            f"({len(file_bytes):,} bytes)"
        )

        if st.button(
            "🚀 Run Patent Analysis",
            type="primary",
            use_container_width=True,
        ):

            results = {}

            progress = st.progress(0)
            status = st.empty()

            # ---------------------------------------------------------
            # 1. DOCUMENT PARSER
            # ---------------------------------------------------------

            status.info("1/10 — Parsing document...")

            parser_result = module_results.get(
                "document_parser"
            )

            if not parser_result["ok"]:
                st.error(
                    parser_result["error"]
                )
                st.stop()

            parser = parser_result["module"]

            try:

                parsed = call_first_available(
                    parser,
                    [
                        "parse_document",
                        "parse_pdf",
                        "parse_file",
                    ],
                    file_bytes,
                )

                results["document"] = parsed

                st.success("✅ Document parsed")

            except Exception as exc:

                st.error(
                    f"Document parsing failed: {exc}"
                )

                st.code(
                    traceback.format_exc()
                )

                st.stop()

            progress.progress(10)

            # ---------------------------------------------------------
            # 2. CLAIM ANALYSIS
            # ---------------------------------------------------------

            status.info("2/10 — Analyzing claims...")

            claim_module = module_results.get(
                "claim_analyzer"
            )

            try:

                claims = None

                if claim_module["ok"]:

                    module = claim_module["module"]

                    claims = call_first_available(
                        module,
                        [
                            "analyze_claims",
                            "extract_claims",
                            "analyze_claim",
                        ],
                        parsed,
                    )

                results["claims"] = claims

                st.success("✅ Claim analysis completed")

            except Exception as exc:

                results["claims_error"] = str(exc)

                st.warning(
                    f"Claim analysis warning: {exc}"
                )

            progress.progress(20)

            # ---------------------------------------------------------
            # 3. RULE ENGINE
            # ---------------------------------------------------------

            status.info("3/10 — Running patent rules...")

            rule_module = module_results.get(
                "rule_engine"
            )

            try:

                rules = None

                if rule_module["ok"]:

                    module = rule_module["module"]

                    rules = call_first_available(
                        module,
                        [
                            "run_rule_engine",
                            "check_claims",
                            "evaluate_rules",
                        ],
                        parsed,
                    )

                results["rules"] = rules

                st.success("✅ Rule engine completed")

            except Exception as exc:

                results["rules_error"] = str(exc)

                st.warning(
                    f"Rule engine warning: {exc}"
                )

            progress.progress(30)

            # ---------------------------------------------------------
            # 4. SECTION 3
            # ---------------------------------------------------------

            status.info("4/10 — Screening Section 3...")

            section3_module = module_results.get(
                "section3_analyzer"
            )

            try:

                section3 = None

                if section3_module and section3_module["ok"]:

                    module = section3_module["module"]

                    section3 = call_first_available(
                        module,
                        [
                            "screen_document",
                            "analyze_section_3",
                        ],
                        parsed,
                    )

                results["section3"] = section3

                st.success(
                    "✅ Section 3 screening completed"
                )

            except Exception as exc:

                results["section3_error"] = str(exc)

                st.warning(
                    f"Section 3 warning: {exc}"
                )

            progress.progress(40)

            # ---------------------------------------------------------
            # 5. PRIOR ART
            # ---------------------------------------------------------

            status.info("5/10 — Building prior-art search plan...")

            prior_art_module = module_results.get(
                "prior_art"
            )

            try:

                prior_art = None

                if prior_art_module["ok"]:

                    module = prior_art_module["module"]

                    prior_art = call_first_available(
                        module,
                        [
                            "prepare_prior_art_analysis",
                            "build_search_plan",
                            "generate_search_queries",
                        ],
                        claims if claims is not None else parsed,
                    )

                results["prior_art"] = prior_art

                st.success(
                    "✅ Prior-art planning completed"
                )

            except Exception as exc:

                results["prior_art_error"] = str(exc)

                st.warning(
                    f"Prior-art warning: {exc}"
                )

            progress.progress(50)

            # ---------------------------------------------------------
            # 6. NOVELTY
            # ---------------------------------------------------------

            status.info("6/10 — Running novelty screening...")

            novelty_module = module_results.get(
                "novelty_analyzer"
            )

            try:

                novelty = None

                if novelty_module and novelty_module["ok"]:

                    module = novelty_module["module"]

                    novelty = call_first_available(
                        module,
                        [
                            "analyze_novelty",
                            "screen_novelty",
                            "calculate_novelty_statistics",
                        ],
                        claims if claims is not None else parsed,
                    )

                results["novelty"] = novelty

                st.success(
                    "✅ Novelty screening completed"
                )

            except Exception as exc:

                results["novelty_error"] = str(exc)

                st.warning(
                    f"Novelty warning: {exc}"
                )

            progress.progress(60)

            # ---------------------------------------------------------
            # 7. INVENTIVE STEP
            # ---------------------------------------------------------

            status.info(
                "7/10 — Running inventive-step screening..."
            )

            inventive_module = module_results.get(
                "inventive_step_analyzer"
            )

            try:

                inventive_step = None

                if inventive_module and inventive_module["ok"]:

                    module = inventive_module["module"]

                    inventive_step = call_first_available(
                        module,
                        [
                            "analyze_inventive_step",
                            "screen_inventive_step",
                            "analyze_claim_inventive_step",
                        ],
                        claims if claims is not None else parsed,
                    )

                results["inventive_step"] = inventive_step

                st.success(
                    "✅ Inventive-step screening completed"
                )

            except Exception as exc:

                results["inventive_step_error"] = str(exc)

                st.warning(
                    f"Inventive-step warning: {exc}"
                )

            progress.progress(70)

            # ---------------------------------------------------------
            # 8. PROSECUTION
            # ---------------------------------------------------------

            status.info(
                "8/10 — Building prosecution analysis..."
            )

            prosecution_module = module_results.get(
                "prosecution_analyzer"
            )

            try:

                prosecution = None

                if prosecution_module and prosecution_module["ok"]:

                    module = prosecution_module["module"]

                    prosecution = call_first_available(
                        module,
                        [
                            "analyze_prosecution",
                            "create_prosecution_dashboard",
                            "analyze_prosecution_history",
                        ],
                        results,
                    )

                results["prosecution"] = prosecution

                st.success(
                    "✅ Prosecution analysis completed"
                )

            except Exception as exc:

                results["prosecution_error"] = str(exc)

                st.warning(
                    f"Prosecution warning: {exc}"
                )

            progress.progress(80)

            # ---------------------------------------------------------
            # 9. KNOWLEDGE GRAPH
            # ---------------------------------------------------------

            status.info(
                "9/10 — Building knowledge graph..."
            )

            graph_module = module_results.get(
                "knowledge_graph"
            )

            try:

                graph = None

                if graph_module and graph_module["ok"]:

                    module = graph_module["module"]

                    graph = call_first_available(
                        module,
                        [
                            "create_knowledge_graph",
                            "build_knowledge_graph",
                            "create_graph",
                        ],
                        results,
                    )

                results["knowledge_graph"] = graph

                st.success(
                    "✅ Knowledge graph generated"
                )

            except Exception as exc:

                results["knowledge_graph_error"] = str(exc)

                st.warning(
                    f"Knowledge graph warning: {exc}"
                )

            progress.progress(90)

            # ---------------------------------------------------------
            # 10. VALIDATION
            # ---------------------------------------------------------

            status.info(
                "10/10 — Validating analysis..."
            )

            validation_module = module_results.get(
                "validation"
            )

            try:

                validation = None

                if validation_module and validation_module["ok"]:

                    module = validation_module["module"]

                    validation = call_first_available(
                        module,
                        [
                            "validate_analysis",
                            "validate_pipeline",
                            "quick_validate",
                        ],
                        results,
                    )

                results["validation"] = validation

                st.success(
                    "✅ Validation completed"
                )

            except Exception as exc:

                results["validation_error"] = str(exc)

                st.warning(
                    f"Validation warning: {exc}"
                )

            progress.progress(100)

            status.success(
                "Analysis pipeline finished."
            )

            st.session_state["analysis_results"] = results
            st.session_state["analysis_filename"] = uploaded_file.name
            st.session_state["analysis_bytes"] = file_bytes

            st.balloons()

            st.success(
                "🎉 Test run completed. Open the Results page."
            )


# ---------------------------------------------------------------------
# MODULE TEST
# ---------------------------------------------------------------------

elif page == "🧪 Module Test":

    st.subheader("V3 Backend Module Test")

    st.write(
        "This page checks whether every registered backend module "
        "can be imported successfully."
    )

    for module_name in MODULES:

        result = module_results[module_name]

        if result["ok"]:

            with st.expander(
                f"✅ {module_name}",
                expanded=False,
            ):

                module = result["module"]

                st.write(
                    f"Module: `services.{module_name}`"
                )

                version_candidates = [
                    key
                    for key in dir(module)
                    if "VERSION" in key.upper()
                ]

                if version_candidates:

                    st.write("Detected version constants:")

                    versions = {}

                    for key in version_candidates:

                        try:
                            versions[key] = getattr(
                                module,
                                key,
                            )
                        except Exception:
                            pass

                    st.json(versions)

                public_functions = [
                    name
                    for name in dir(module)
                    if not name.startswith("_")
                    and callable(getattr(module, name, None))
                ]

                st.write(
                    f"Public callable objects: "
                    f"**{len(public_functions)}**"
                )

                st.code(
                    "\n".join(
                        public_functions[:100]
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

                if "traceback" in result:
                    st.code(
                        result["traceback"]
                    )


# ---------------------------------------------------------------------
# RESULTS
# ---------------------------------------------------------------------

elif page == "📊 Results":

    st.subheader("Analysis Results")

    results = st.session_state.get(
        "analysis_results"
    )

    filename = st.session_state.get(
        "analysis_filename"
    )

    if not results:

        st.info(
            "No analysis has been run yet. "
            "Go to Patent Analysis and upload a PDF."
        )

    else:

        if filename:
            st.caption(
                f"Document: `{filename}`"
            )

        # -------------------------------------------------------------
        # SUMMARY METRICS
        # -------------------------------------------------------------

        successful = 0
        failed = 0

        for key, value in results.items():

            if key.endswith("_error"):

                failed += 1

            elif value is not None:

                successful += 1

        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric(
                "Completed Stages",
                successful,
            )

        with c2:
            st.metric(
                "Warnings / Errors",
                failed,
            )

        with c3:
            st.metric(
                "Result Sections",
                len(results),
            )

        st.divider()

        # -------------------------------------------------------------
        # TABS
        # -------------------------------------------------------------

        tab_names = list(results.keys())

        tabs = st.tabs(
            [
                name.replace("_", " ").title()
                for name in tab_names
            ]
        )

        for tab, key in zip(tabs, tab_names):

            with tab:

                value = results[key]

                if key.endswith("_error"):

                    st.error(
                        str(value)
                    )

                else:

                    if value is None:

                        st.info(
                            "No result returned."
                        )

                    else:

                        st.write(
                            f"Result type: `{type(value).__name__}`"
                        )

                        show_json(
                            value
                        )

        st.divider()

        # -------------------------------------------------------------
        # DOWNLOAD JSON
        # -------------------------------------------------------------

        json_data = json.dumps(
            normalize_result(results),
            indent=2,
            default=str,
        )

        st.download_button(
            "⬇️ Download Analysis JSON",
            data=json_data,
            file_name="patent_analysis_results.json",
            mime="application/json",
            use_container_width=True,
        )


# ---------------------------------------------------------------------
# ABOUT
# ---------------------------------------------------------------------

elif page == "ℹ️ About":

    st.subheader("About Indian Patent Analyzer")

    st.markdown(
        """
        ### Architecture

        The application is designed around a provenance-first,
        evidence-based patent analysis architecture.

        ```text
        Patent PDF
             │
             ▼
        Document Parser
             │
             ▼
        Claims + Limitations
             │
             ├──────────────► Rule Engine
             │
             ├──────────────► Section 3 Screening
             │
             ├──────────────► Prior-Art Search Plan
             │
             ├──────────────► Evidence Retrieval
             │
             ▼
        Evidence Verification
             │
             ├──────────────► Novelty
             │
             ├──────────────► Inventive Step
             │
             ├──────────────► Amendments
             │
             └──────────────► Prosecution
             │
             ▼
        Knowledge Graph
             │
             ▼
        Validation
             │
             ▼
        Report
        ```

        ### Design principle

        The system separates:

        **Facts → Evidence → Rules → Analysis → AI explanation**

        Gemini/LLM output should not be treated as the authoritative
        source of patent-law facts.

        ### Current status

        This build is intended primarily for **integration testing**.

        Once the complete pipeline passes with real patent PDFs,
        we can move to the persistent document store, production API,
        authentication, advanced search, and final frontend.
        """
    )

    st.info(
        "Automated analysis is a screening and research aid, "
        "not a legal opinion."
    )


# ---------------------------------------------------------------------
# FOOTER
# ---------------------------------------------------------------------

st.divider()

st.caption(
    f"Indian Patent Analyzer V{APP_VERSION} • "
    "Integration Test Build • "
    "Generated {utc_now()}"
)
