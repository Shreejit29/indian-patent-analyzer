"""
Indian Patent Analyzer
V3 Integration Test Dashboard

The Streamlit UI talks only to:
    services.integration_adapter

The adapter handles differences between individual backend modules.
"""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from typing import Any, Dict

import streamlit as st


# ============================================================
# CONFIGURATION
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
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="Indian Patent Analyzer",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ============================================================
# CSS
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

    .pipeline-box {
        border: 1px solid #e5e7eb;
        border-radius: 12px;
        padding: 1rem;
        margin: 0.5rem 0;
    }

    .stage-card {
        border: 1px solid #e5e7eb;
        border-radius: 10px;
        padding: 0.8rem;
        margin-bottom: 0.5rem;
    }

    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# IMPORT HELPERS
# ============================================================

def safe_import(
    module_name: str,
) -> Dict[str, Any]:
    """
    Import a backend module without allowing one broken
    module to crash the application.
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
            "error": (
                f"{type(exc).__name__}: {exc}"
            ),
            "traceback": traceback.format_exc(),
        }


def check_modules() -> Dict[str, Dict[str, Any]]:
    """
    Check all backend modules.

    IMPORTANT:
    This function is intentionally NOT cached.

    Streamlit cannot serialize live Python module objects
    returned by this function.
    """

    results = {}

    for module_name in MODULES:

        results[module_name] = safe_import(
            f"services.{module_name}"
        )

    return results


# ============================================================
# SERIALIZATION
# ============================================================

def normalize_for_json(
    value: Any,
) -> Any:

    if value is None:
        return None

    if hasattr(
        value,
        "to_dict",
    ):

        try:
            return normalize_for_json(
                value.to_dict()
            )
        except Exception:
            pass

    if hasattr(
        value,
        "__dataclass_fields__",
    ):

        try:

            from dataclasses import asdict

            return normalize_for_json(
                asdict(value)
            )

        except Exception:
            pass

    if isinstance(
        value,
        dict,
    ):

        return {
            str(k): normalize_for_json(v)
            for k, v in value.items()
        }

    if isinstance(
        value,
        (list, tuple, set),
    ):

        return [
            normalize_for_json(v)
            for v in value
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


def show_json(
    value: Any,
):

    normalized = normalize_for_json(
        value
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


# ============================================================
# VERSION INFORMATION
# ============================================================

def get_module_versions(
    module: Any,
) -> Dict[str, Any]:

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

loaded_count = len(
    loaded_modules
)

failed_count = len(
    failed_modules
)

total_count = len(
    MODULES
)


# ============================================================
# HEADER
# ============================================================

st.markdown(
    '<div class="main-title">'
    "⚖️ Indian Patent Analyzer"
    "</div>",
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

    st.header(
        "Navigation"
    )

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

    st.subheader(
        "System"
    )

    st.write(
        f"**Application:** V{APP_VERSION}"
    )

    st.write(
        f"**Backend modules:** "
        f"{loaded_count}/{total_count}"
    )

    if failed_count == 0:

        st.success(
            "All modules loaded"
        )

    else:

        st.warning(
            f"{failed_count} module(s) failed"
        )

    st.divider()

    st.caption(
        "Automated outputs are screening and "
        "research aids, not legal opinions."
    )


# ============================================================
# DASHBOARD
# ============================================================

if page == "🏠 Dashboard":

    st.subheader(
        "System Health"
    )

    c1, c2, c3, c4 = st.columns(4)

    with c1:

        st.metric(
            "Modules Loaded",
            f"{loaded_count}/{total_count}",
        )

    with c2:

        st.metric(
            "Failed Modules",
            failed_count,
        )

    with c3:

        st.metric(
            "Version",
            APP_VERSION,
        )

    with c4:

        st.metric(
            "Mode",
            "Integration Test",
        )

    st.divider()

    st.subheader(
        "Backend Modules"
    )

    cols = st.columns(3)

    for index, module_name in enumerate(
        MODULES
    ):

        result = module_results[
            module_name
        ]

        with cols[
            index % 3
        ]:

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

    st.subheader(
        "Analysis Architecture"
    )

    st.markdown(
        """
        <div class="pipeline-box">

        📄 **Patent PDF**

        ↓

        🔎 **Document Parser**

        ↓

        📑 **Claims + Limitations**

        ↓

        ⚖️ **Rule Engine**

        ↓

        § **Section 3 Screening**

        ↓

        🔍 **Prior-Art Search Planning**

        ↓

        🧾 **Evidence Retrieval + Verification**

        ↓

        🧠 **Novelty + Inventive Step**

        ↓

        📬 **Prosecution Analysis**

        ↓

        🕸️ **Knowledge Graph**

        ↓

        ✅ **Validation**

        ↓

        📊 **Report**

        </div>
        """,
        unsafe_allow_html=True,
    )

    if failed_count:

        st.warning(
            "Some backend modules currently have "
            "integration issues. The adapter allows "
            "the working portions of the system to "
            "continue operating."
        )

    else:

        st.success(
            "All registered backend modules imported successfully."
        )


# ============================================================
# PATENT ANALYSIS
# ============================================================

elif page == "📄 Patent Analysis":

    st.subheader(
        "Patent Analysis"
    )

    st.write(
        "Upload a patent document and run the "
        "integration adapter."
    )

    uploaded_file = st.file_uploader(
        "Upload patent document",
        type=[
            "pdf",
            "docx",
        ],
        accept_multiple_files=False,
    )

    if uploaded_file is None:

        st.info(
            "Upload a PDF or DOCX file to begin."
        )

        st.markdown(
            """
            ### Current test pipeline

            1. Document extraction
            2. Claim normalization
            3. Claim analysis
            4. Rule screening
            5. Section 3 screening
            6. Prior-art planning
            7. Evidence status
            8. Novelty interface
            9. Inventive-step interface
            10. Prosecution interface
            11. Knowledge graph interface
            12. Validation
            """
        )

    else:

        file_bytes = (
            uploaded_file.getvalue()
        )

        st.success(
            f"Loaded `{uploaded_file.name}` "
            f"({len(file_bytes):,} bytes)"
        )

        if st.button(
            "🚀 Run Integration Test",
            type="primary",
            use_container_width=True,
        ):

            adapter_result = module_results.get(
                "document_parser"
            )

            if not adapter_result:

                st.error(
                    "Document parser module is missing."
                )

                st.stop()

            integration_result = module_results.get(
                "claim_analyzer"
            )

            if not integration_result:

                st.error(
                    "Claim analyzer module is missing."
                )

                st.stop()

            # ------------------------------------------------
            # IMPORT ADAPTER
            # ------------------------------------------------

            try:

                from services.integration_adapter import (
                    PatentIntegrationAdapter,
                )

            except Exception as exc:

                st.error(
                    "Could not import "
                    "services.integration_adapter"
                )

                st.code(
                    traceback.format_exc()
                )

                st.stop()

            # ------------------------------------------------
            # RUN
            # ------------------------------------------------

            progress = st.progress(
                0
            )

            status = st.empty()

            status.info(
                "Initializing integration adapter..."
            )

            progress.progress(
                5
            )

            try:

                adapter = PatentIntegrationAdapter(
                    modules=module_results
                )

                status.info(
                    "Running normalized V3 pipeline..."
                )

                progress.progress(
                    10
                )

                result = adapter.analyze(
                    file_bytes=file_bytes,
                    filename=uploaded_file.name,
                )

                progress.progress(
                    100
                )

                status.success(
                    "Integration pipeline finished."
                )

                result_dict = result.to_dict()

                # Save complete result.
                st.session_state[
                    "integration_result"
                ] = result_dict

                st.session_state[
                    "analysis_filename"
                ] = uploaded_file.name

                st.session_state[
                    "analysis_bytes"
                ] = file_bytes

                # --------------------------------------------
                # STATUS
                # --------------------------------------------

                if result.status == "completed":

                    st.success(
                        "🎉 Integration completed successfully."
                    )

                elif result.status == (
                    "completed_with_warnings"
                ):

                    st.warning(
                        "⚠️ Integration completed with warnings."
                    )

                else:

                    st.warning(
                        "⚠️ Integration completed partially."
                    )

                # --------------------------------------------
                # SUMMARY
                # --------------------------------------------

                warnings = result.warnings
                errors = result.errors

                c1, c2, c3 = st.columns(3)

                with c1:

                    st.metric(
                        "Pipeline Status",
                        result.status,
                    )

                with c2:

                    st.metric(
                        "Warnings",
                        len(warnings),
                    )

                with c3:

                    st.metric(
                        "Errors",
                        len(errors),
                    )

                # --------------------------------------------
                # STAGES
                # --------------------------------------------

                st.divider()

                st.subheader(
                    "Pipeline Stages"
                )

                stages = result.stages

                for stage_name, stage in stages.items():

                    stage_status = stage.get(
                        "status",
                        "unknown",
                    )

                    if stage_status == "completed":

                        st.success(
                            f"✅ {stage_name}"
                        )

                    elif stage_status == "warning":

                        st.warning(
                            f"⚠️ {stage_name}"
                        )

                    elif stage_status == "error":

                        st.error(
                            f"❌ {stage_name}"
                        )

                    else:

                        st.info(
                            f"ℹ️ {stage_name}"
                        )

                # --------------------------------------------
                # WARNINGS
                # --------------------------------------------

                if warnings:

                    st.divider()

                    st.subheader(
                        "Warnings"
                    )

                    for warning in warnings:

                        st.warning(
                            warning
                        )

                # --------------------------------------------
                # ERRORS
                # --------------------------------------------

                if errors:

                    st.divider()

                    st.subheader(
                        "Errors"
                    )

                    for error in errors:

                        st.error(
                            error
                        )

                st.info(
                    "Open the **📊 Results** page for "
                    "complete structured output."
                )

            except Exception as exc:

                progress.progress(
                    100
                )

                st.error(
                    "Integration pipeline failed."
                )

                st.code(
                    traceback.format_exc()
                )


# ============================================================
# MODULE TEST
# ============================================================

elif page == "🧪 Module Test":

    st.subheader(
        "Backend Module Test"
    )

    st.write(
        "This page checks imports independently. "
        "It does not execute the analysis pipeline."
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

                module = result[
                    "module"
                ]

                versions = get_module_versions(
                    module
                )

                if versions:

                    st.write(
                        "**Version:**"
                    )

                    st.json(
                        versions
                    )

                public_functions = []

                try:

                    for name in dir(module):

                        if name.startswith(
                            "_"
                        ):

                            continue

                        try:

                            obj = getattr(
                                module,
                                name,
                            )

                            if callable(
                                obj
                            ):

                                public_functions.append(
                                    name
                                )

                        except Exception:
                            continue

                except Exception:
                    pass

                st.write(
                    f"**Public callables:** "
                    f"{len(public_functions)}"
                )

                if public_functions:

                    st.code(
                        "\n".join(
                            sorted(
                                public_functions
                            )
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
# RESULTS
# ============================================================

elif page == "📊 Results":

    st.subheader(
        "Integration Results"
    )

    result = st.session_state.get(
        "integration_result"
    )

    filename = st.session_state.get(
        "analysis_filename"
    )

    if not result:

        st.info(
            "No integration result is available."
        )

        st.write(
            "Go to **📄 Patent Analysis** and "
            "run the integration test."
        )

    else:

        if filename:

            st.caption(
                f"Document: `{filename}`"
            )

        # ----------------------------------------------------
        # SUMMARY
        # ----------------------------------------------------

        document = result.get(
            "document",
            {},
        )

        stages = result.get(
            "stages",
            {},
        )

        warnings = result.get(
            "warnings",
            [],
        )

        errors = result.get(
            "errors",
            [],
        )

        c1, c2, c3, c4 = st.columns(4)

        with c1:

            st.metric(
                "Status",
                result.get(
                    "status",
                    "unknown",
                ),
            )

        with c2:

            st.metric(
                "Stages",
                len(stages),
            )

        with c3:

            st.metric(
                "Warnings",
                len(warnings),
            )

        with c4:

            st.metric(
                "Errors",
                len(errors),
            )

        st.divider()

        # ----------------------------------------------------
        # DOCUMENT
        # ----------------------------------------------------

        st.subheader(
            "Document"
        )

        show_json(
            document
        )

        # ----------------------------------------------------
        # PIPELINE
        # ----------------------------------------------------

        st.subheader(
            "Pipeline"
        )

        for stage_name, stage in stages.items():

            with st.expander(
                stage_name.replace(
                    "_",
                    " ",
                ).title(),
                expanded=False,
            ):

                st.write(
                    f"**Status:** "
                    f"{stage.get('status')}"
                )

                if stage.get(
                    "function"
                ):

                    st.write(
                        f"**Function:** "
                        f"`{stage['function']}`"
                    )

                if stage.get(
                    "signature"
                ):

                    st.code(
                        stage["signature"]
                    )

                if stage.get(
                    "warning"
                ):

                    st.warning(
                        stage["warning"]
                    )

                if stage.get(
                    "error"
                ):

                    st.error(
                        stage["error"]
                    )

                if stage.get(
                    "result"
                ) is not None:

                    st.write(
                        "**Result:**"
                    )

                    show_json(
                        stage["result"]
                    )

        # ----------------------------------------------------
        # WARNINGS
        # ----------------------------------------------------

        if warnings:

            st.divider()

            st.subheader(
                "Warnings"
            )

            for warning in warnings:

                st.warning(
                    warning
                )

        # ----------------------------------------------------
        # ERRORS
        # ----------------------------------------------------

        if errors:

            st.divider()

            st.subheader(
                "Errors"
            )

            for error in errors:

                st.error(
                    error
                )

        # ----------------------------------------------------
        # DOWNLOAD
        # ----------------------------------------------------

        st.divider()

        json_data = json.dumps(
            normalize_for_json(
                result
            ),
            indent=2,
            default=str,
        )

        st.download_button(
            "⬇️ Download Integration JSON",
            data=json_data,
            file_name=(
                "patent_integration_result.json"
            ),
            mime="application/json",
            use_container_width=True,
        )


# ============================================================
# ABOUT
# ============================================================

elif page == "ℹ️ About":

    st.subheader(
        "Indian Patent Analyzer V3"
    )

    st.markdown(
        """
        ### Current objective

        This build is testing the **integration layer** before
        further expansion of the application.

        The architecture deliberately separates:

        **Document**

        → **Structured Data**

        → **Deterministic Analysis**

        → **Evidence**

        → **AI Interpretation**

        → **Human Review**

        ### Important

        Individual backend modules may have different interfaces.
        `integration_adapter.py` provides the common interface
        between those modules and the Streamlit application.

        This prevents the UI from becoming tightly coupled to
        individual backend implementations.

        ### Current development priority

        The immediate goal is:

        **Make the existing modules work together correctly.**

        Only after that should we add persistence, advanced search,
        report generation, or additional AI features.
        """
    )


# ============================================================
# FOOTER
# ============================================================

st.divider()

st.caption(
    f"Indian Patent Analyzer V{APP_VERSION} • "
    f"Integration Test • "
    f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
)
