import streamlit as st

# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="Indian Patent Draft Analyzer",
    page_icon="⚖️",
    layout="wide"
)

# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

st.title("🇮🇳 Indian Patent Draft Analyzer")

st.markdown(
    """
    ### AI-assisted Indian Patent Office Compliance & Draft Analysis

    Upload an Indian patent draft to analyze its structure,
    claims, abstract, specification and potential examination issues.
    """
)

st.divider()

# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------

with st.sidebar:

    st.header("Analysis Settings")

    document_type = st.selectbox(
        "Document Type",
        [
            "Form 2 - Complete Specification",
            "Form 2 - Provisional Specification",
            "Claims",
            "Abstract",
            "FER Response",
            "Other"
        ]
    )

    analysis_level = st.selectbox(
        "Analysis Level",
        [
            "Basic",
            "Detailed",
            "Comprehensive"
        ]
    )

    st.divider()

    st.info(
        """
        This tool provides AI-assisted analysis for research
        and drafting purposes. It is not a substitute for
        professional patent advice.
        """
    )

# ---------------------------------------------------------
# FILE UPLOAD
# ---------------------------------------------------------

st.header("1. Upload Patent Draft")

uploaded_file = st.file_uploader(
    "Upload your patent draft",
    type=["pdf", "docx"],
    help="Supported formats: PDF and DOCX"
)

if uploaded_file:

    st.success(f"File uploaded: {uploaded_file.name}")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "File Type",
            uploaded_file.type
        )

    with col2:
        file_size_kb = uploaded_file.size / 1024

        st.metric(
            "File Size",
            f"{file_size_kb:.1f} KB"
        )

    with col3:
        st.metric(
            "Document Type",
            document_type
        )

    st.divider()

    # -----------------------------------------------------
    # START ANALYSIS
    # -----------------------------------------------------

    if st.button(
        "🔍 Start Patent Analysis",
        type="primary",
        use_container_width=True
    ):

        st.session_state["analysis_started"] = True

        st.info(
            "Document uploaded successfully. "
            "The analysis engine will be connected next."
        )

# ---------------------------------------------------------
# ANALYSIS DASHBOARD
# ---------------------------------------------------------

if st.session_state.get("analysis_started", False):

    st.header("2. Analysis Dashboard")

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            "Form Compliance",
            "—"
        )

    with col2:
        st.metric(
            "Claims",
            "—"
        )

    with col3:
        st.metric(
            "Abstract",
            "—"
        )

    with col4:
        st.metric(
            "Overall Score",
            "—"
        )

    st.divider()

    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "📋 Executive Summary",
            "📑 Form 2",
            "⚖️ Claims",
            "📝 Abstract",
            "⚠️ Potential Issues"
        ]
    )

    with tab1:

        st.subheader("Executive Summary")

        st.info(
            "Analysis results will appear here."
        )

    with tab2:

        st.subheader("Form 2 Compliance")

        st.info(
            "Form 2 compliance analysis will appear here."
        )

    with tab3:

        st.subheader("Claim Analysis")

        st.info(
            "Claim-by-claim analysis will appear here."
        )

    with tab4:

        st.subheader("Abstract Analysis")

        st.info(
            "Abstract analysis will appear here."
        )

    with tab5:

        st.subheader("Potential Examination Issues")

        st.info(
            "Potential examination issues will appear here."
        )

# ---------------------------------------------------------
# FOOTER
# ---------------------------------------------------------

st.divider()

st.caption(
    "Indian Patent Draft Analyzer | AI-assisted patent analysis"
)
