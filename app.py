import streamlit as st

from services.analyzer import analyze_document
from services.report_generator import (
    generate_markdown_report,
    generate_text_report,
)


# ---------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------

st.set_page_config(
    page_title="Indian Patent Draft Analyzer",
    page_icon="⚖️",
    layout="wide",
)


# ---------------------------------------------------------
# HEADER
# ---------------------------------------------------------

st.title("⚖️ Indian Patent Draft Analyzer")

st.write(
    "AI-assisted analysis of Indian patent drafts using "
    "structured Indian Patent Office rules and Gemini."
)

st.caption(
    "Preliminary analysis only — not legal advice and not a substitute "
    "for review by a registered patent professional."
)


# ---------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------

st.sidebar.header("Analysis Settings")

document_type = st.sidebar.selectbox(
    "Document Type",
    [
        "Form 2 Complete Specification",
        "Form 2 Provisional Specification",
        "Claims",
        "Abstract",
        "FER Response",
        "Other",
    ],
)

analysis_level = st.sidebar.selectbox(
    "Analysis Level",
    [
        "Basic",
        "Detailed",
        "Comprehensive",
    ],
    index=1,
)

st.sidebar.divider()

st.sidebar.info(
    """
The analyzer currently focuses on:

• Form 2 structure  
• Indian patent rules  
• Claims  
• Abstract  
• Reference numerals  
• Drafting issues  
• Examination risks
"""
)


# ---------------------------------------------------------
# FILE UPLOAD
# ---------------------------------------------------------

st.header("Upload Patent Document")

uploaded_file = st.file_uploader(
    "Upload your patent document",
    type=["pdf", "docx"],
    help="Upload a PDF or DOCX patent draft.",
)


# ---------------------------------------------------------
# DISPLAY FILE INFORMATION
# ---------------------------------------------------------

if uploaded_file:

    st.success(f"File uploaded: {uploaded_file.name}")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric(
            "File Name",
            uploaded_file.name,
        )

    with col2:
        st.metric(
            "File Type",
            uploaded_file.type,
        )

    with col3:
        st.metric(
            "File Size",
            f"{uploaded_file.size / 1024:.1f} KB",
        )

    st.divider()


# ---------------------------------------------------------
# ANALYSIS BUTTON
# ---------------------------------------------------------

if uploaded_file:

    start_analysis = st.button(
        "🔍 Start Patent Analysis",
        type="primary",
        use_container_width=True,
    )

    if start_analysis:

        # Store file bytes before running analysis.
        file_bytes = uploaded_file.getvalue()

        try:

            with st.spinner(
                "Analyzing patent document... "
                "This may take a moment."
            ):

                result = analyze_document(
                    file_bytes=file_bytes,
                    filename=uploaded_file.name,
                    document_type=document_type,
                    analysis_level=analysis_level,
                )

            # Save result in session state so it remains available
            # when the user interacts with the dashboard.
            st.session_state["analysis_result"] = result
            st.session_state["analysis_filename"] = uploaded_file.name

            st.success(
                "Patent analysis completed successfully."
            )

        except Exception as exc:

            st.error(
                "Analysis could not be completed."
            )

            st.exception(exc)


# ---------------------------------------------------------
# GET STORED RESULT
# ---------------------------------------------------------

result = st.session_state.get("analysis_result")


# ---------------------------------------------------------
# ANALYSIS DASHBOARD
# ---------------------------------------------------------

if result:

    st.divider()

    st.header("📊 Patent Analysis Dashboard")

    gemini = result.get("gemini_analysis", {})
    rule_engine = result.get("rule_engine", {})
    claim_engine = result.get("claim_engine", {})

    # -----------------------------------------------------
    # SCORE CARDS
    # -----------------------------------------------------

    scores = gemini.get("scores", {})

    if scores:

        st.subheader("Overall Analysis")

        score_items = [
            ("Overall", scores.get("overall")),
            ("Structure", scores.get("structure")),
            ("Claims", scores.get("claims")),
            ("Support", scores.get("support")),
            ("Clarity", scores.get("clarity")),
            ("Abstract", scores.get("abstract")),
        ]

        columns = st.columns(len(score_items))

        for column, (label, score) in zip(
            columns,
            score_items,
        ):

            with column:

                if isinstance(score, (int, float)):
                    st.metric(
                        label,
                        f"{score}/100",
                    )
                else:
                    st.metric(
                        label,
                        "N/A",
                    )

    st.divider()

    # -----------------------------------------------------
    # TABS
    # -----------------------------------------------------

    (
        summary_tab,
        form2_tab,
        claims_tab,
        abstract_tab,
        issues_tab,
        report_tab,
    ) = st.tabs(
        [
            "Executive Summary",
            "Form 2",
            "Claims",
            "Abstract",
            "Potential Issues",
            "Report",
        ]
    )

    # =====================================================
    # EXECUTIVE SUMMARY
    # =====================================================

    with summary_tab:

        assessment = gemini.get(
            "document_assessment",
            {},
        )

        st.subheader(
            assessment.get(
                "overall_assessment",
                "Assessment not available.",
            )
        )

        if assessment.get("document_type"):
            st.write(
                f"**Document Type:** "
                f"{assessment['document_type']}"
            )

        if assessment.get("summary"):
            st.write(
                assessment["summary"]
            )

        st.subheader("Document Statistics")

        statistics = result.get(
            "document_statistics",
            {},
        )

        stat1, stat2, stat3 = st.columns(3)

        with stat1:
            st.metric(
                "Words",
                statistics.get("words", "N/A"),
            )

        with stat2:
            st.metric(
                "Characters",
                statistics.get("characters", "N/A"),
            )

        with stat3:
            st.metric(
                "Paragraphs",
                statistics.get("paragraphs", "N/A"),
            )

    # =====================================================
    # FORM 2
    # =====================================================

    with form2_tab:

        st.subheader("Form 2 Structure")

        sections = gemini.get(
            "sections",
            {},
        )

        if sections:

            for section_name, section_data in sections.items():

                if isinstance(section_data, dict):

                    status = section_data.get(
                        "status",
                        "Unknown",
                    )

                    assessment_text = section_data.get(
                        "assessment",
                        "",
                    )

                    if status.lower() in [
                        "present",
                        "complete",
                        "adequate",
                        "satisfactory",
                    ]:
                        icon = "✅"
                    elif status.lower() in [
                        "missing",
                        "incomplete",
                        "weak",
                    ]:
                        icon = "⚠️"
                    else:
                        icon = "ℹ️"

                    with st.expander(
                        f"{icon} "
                        f"{section_name.replace('_', ' ').title()}"
                    ):

                        st.write(
                            f"**Status:** {status}"
                        )

                        if assessment_text:
                            st.write(
                                assessment_text
                            )

        st.subheader("Deterministic Rule Checks")

        rule_issues = rule_engine.get(
            "issues",
            [],
        )

        if rule_issues:

            for issue in rule_issues:

                if isinstance(issue, dict):

                    severity = issue.get(
                        "severity",
                        "info",
                    )

                    message = issue.get(
                        "message",
                        issue.get(
                            "title",
                            "Issue identified.",
                        ),
                    )

                    if severity == "high":
                        st.error(message)

                    elif severity == "medium":
                        st.warning(message)

                    else:
                        st.info(message)

                else:
                    st.info(str(issue))

        else:
            st.success(
                "No deterministic rule issues were identified."
            )

    # =====================================================
    # CLAIMS
    # =====================================================

    with claims_tab:

        st.subheader("Claim Analysis")

        claims = gemini.get(
            "claims",
            [],
        )

        if not claims:

            st.warning(
                "No structured claim analysis was returned."
            )

        else:

            for claim in claims:

                claim_number = claim.get(
                    "claim_number",
                    "?",
                )

                claim_type = claim.get(
                    "claim_type",
                    "unknown",
                )

                with st.expander(
                    f"Claim {claim_number} — "
                    f"{claim_type.title()}"
                ):

                    if claim.get("category"):
                        st.write(
                            f"**Category:** "
                            f"{claim['category']}"
                        )

                    if claim.get("assessment"):
                        st.write(
                            claim["assessment"]
                        )

                    if claim.get("issues"):

                        st.write("**Issues:**")

                        for issue in claim["issues"]:
                            st.warning(
                                str(issue)
                            )

                    if claim.get("recommendations"):

                        st.write(
                            "**Recommendations:**"
                        )

                        for recommendation in claim[
                            "recommendations"
                        ]:
                            st.info(
                                str(recommendation)
                            )

        st.subheader(
            "Deterministic Claim Analysis"
        )

        claim_count = claim_engine.get(
            "claim_count",
            0,
        )

        independent_count = len(
            claim_engine.get(
                "independent_claims",
                [],
            )
        )

        dependent_count = len(
            claim_engine.get(
                "dependent_claims",
                [],
            )
        )

        c1, c2, c3 = st.columns(3)

        with c1:
            st.metric(
                "Total Claims",
                claim_count,
            )

        with c2:
            st.metric(
                "Independent Claims",
                independent_count,
            )

        with c3:
            st.metric(
                "Dependent Claims",
                dependent_count,
            )

    # =====================================================
    # ABSTRACT
    # =====================================================

    with abstract_tab:

        st.subheader(
            "Abstract Analysis"
        )

        abstract = gemini.get(
            "abstract_analysis",
            {},
        )

        if abstract.get("assessment"):
            st.write(
                abstract["assessment"]
            )

        if abstract.get("word_count") is not None:
            st.metric(
                "Abstract Word Count",
                abstract["word_count"],
            )

        if abstract.get("issues"):

            st.write("### Issues")

            for issue in abstract["issues"]:
                st.warning(
                    str(issue)
                )

        if abstract.get("recommendations"):

            st.write(
                "### Recommendations"
            )

            for recommendation in abstract[
                "recommendations"
            ]:
                st.info(
                    str(recommendation)
                )

    # =====================================================
    # ISSUES
    # =====================================================

    with issues_tab:

        st.subheader(
            "Potential Issues"
        )

        issues = gemini.get(
            "issues",
            [],
        )

        if not issues:

            st.success(
                "No potential issues were returned."
            )

        else:

            for index, issue in enumerate(
                issues,
                start=1,
            ):

                if isinstance(issue, str):

                    st.warning(
                        f"{index}. {issue}"
                    )

                    continue

                title = issue.get(
                    "title",
                    f"Issue {index}",
                )

                severity = issue.get(
                    "severity",
                    "info",
                ).lower()

                issue_type = issue.get(
                    "type",
                    "DRAFTING_SUGGESTION",
                )

                confidence = issue.get(
                    "confidence",
                    "unknown",
                )

                if severity == "critical":
                    st.error(
                        f"🔴 {title}"
                    )

                elif severity == "high":
                    st.error(
                        f"🟠 {title}"
                    )

                elif severity == "medium":
                    st.warning(
                        f"🟡 {title}"
                    )

                else:
                    st.info(
                        f"🟢 {title}"
                    )

                st.caption(
                    f"Type: {issue_type} | "
                    f"Confidence: {confidence}"
                )

                if issue.get("evidence"):
                    st.write(
                        f"**Evidence:** "
                        f"{issue['evidence']}"
                    )

                if issue.get("explanation"):
                    st.write(
                        f"**Explanation:** "
                        f"{issue['explanation']}"
                    )

                if issue.get("recommendation"):
                    st.write(
                        f"**Recommended Action:** "
                        f"{issue['recommendation']}"
                    )

                if issue.get("source"):
                    st.caption(
                        f"Source: {issue['source']}"
                    )

                st.divider()

    # =====================================================
    # REPORT
    # =====================================================

    with report_tab:

        st.subheader(
            "Analysis Report"
        )

        report = generate_markdown_report(
            analysis={
                **gemini,
                "document_statistics": result.get(
                    "document_statistics",
                    {},
                ),
            },
            document_name=result.get(
                "document_name",
                "Patent Document",
            ),
        )

        st.markdown(report)

        st.divider()

        st.download_button(
            label="⬇️ Download Markdown Report",
            data=report,
            file_name="patent_analysis_report.md",
            mime="text/markdown",
            use_container_width=True,
        )

        text_report = generate_text_report(
            analysis=gemini,
            document_name=result.get(
                "document_name",
                "Patent Document",
            ),
        )

        st.download_button(
            label="⬇️ Download Text Report",
            data=text_report,
            file_name="patent_analysis_report.txt",
            mime="text/plain",
            use_container_width=True,
        )


else:

    # -----------------------------------------------------
    # INITIAL EMPTY STATE
    # -----------------------------------------------------

    st.info(
        "Upload a PDF or DOCX patent document and click "
        "**Start Patent Analysis** to begin."
    )

    st.subheader("Analysis Pipeline")

    pipeline_columns = st.columns(5)

    pipeline_steps = [
        ("1", "Document", "Extract patent text"),
        ("2", "Rules", "Check IPO requirements"),
        ("3", "Claims", "Analyze claim structure"),
        ("4", "Gemini", "Perform AI analysis"),
        ("5", "Report", "Generate report"),
    ]

    for column, (number, title, description) in zip(
        pipeline_columns,
        pipeline_steps,
    ):

        with column:

            st.markdown(
                f"### {number}. {title}"
            )

            st.caption(
                description
            )
