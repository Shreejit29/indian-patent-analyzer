import streamlit as st

from services.analyzer import analyze_document
from services.document_parser import extract_text_from_file
from services.form2_rewriter import (
    rewrite_form2,
    revised_form2_to_text,
    get_rewrite_summary,
)
from services.report_generator import (
    generate_markdown_report,
    generate_text_report,
)
import google.genai

st.sidebar.markdown("### Gemini Diagnostics")

st.sidebar.write(
    "SDK version:",
    google.genai.__version__,
)

api_key = str(
    st.secrets.get(
        "GEMINI_API_KEY",
        "",
    )
).strip()

st.sidebar.write(
    "Key detected:",
    bool(api_key),
)

st.sidebar.write(
    "Key prefix:",
    api_key[:3] if api_key else "NONE",
)

if st.sidebar.button("Test Gemini Connection"):

    try:

        client = google.genai.Client(
            api_key=api_key
        )

        response = client.models.generate_content(
            model="gemini-3.7-flash",
            contents="Reply with exactly: GEMINI_OK",
        )

        st.sidebar.success(
            "Gemini connection successful"
        )

        st.sidebar.write(
            response.text
        )

    except Exception as exc:

        st.sidebar.error(
            "Gemini connection failed"
        )

        st.sidebar.code(
            str(exc)
        )
import google.genai

st.sidebar.write(
    "google-genai version:",
    google.genai.__version__,
)

st.sidebar.write(
    "Gemini key detected:",
    bool(st.secrets.get("GEMINI_API_KEY")),
)

if "GEMINI_API_KEY" in st.secrets:
    st.sidebar.write(
        "Key prefix:",
        str(st.secrets["GEMINI_API_KEY"])[:3],
    )

# ============================================================
# PAGE CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Indian Patent Draft Analyzer",
    page_icon="📜",
    layout="wide",
)


# ============================================================
# SESSION STATE
# ============================================================

if "analysis_result" not in st.session_state:
    st.session_state.analysis_result = None

if "uploaded_text" not in st.session_state:
    st.session_state.uploaded_text = ""

if "uploaded_filename" not in st.session_state:
    st.session_state.uploaded_filename = ""

if "uploaded_bytes" not in st.session_state:
    st.session_state.uploaded_bytes = None

if "rewrite_result" not in st.session_state:
    st.session_state.rewrite_result = None


# ============================================================
# HEADER
# ============================================================

st.title("📜 Indian Patent Draft Analyzer")

st.markdown(
    """
Analyze and improve Indian patent documents using:

- Indian Patents Act
- Patents Rules
- Form 2 requirements
- Patent Office Manual guidance
- Deterministic rule checks
- Claim analysis
- Gemini-based drafting analysis
- Section 59 no-new-matter screening
"""
)


# ============================================================
# SIDEBAR
# ============================================================

st.sidebar.header("Document Settings")

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
)

st.sidebar.markdown("---")

st.sidebar.info(
    """
For Form 2 documents, the analyzer checks structure,
claims, abstract, support, drafting issues and selected
Indian patent requirements.
"""
)


# ============================================================
# FILE UPLOAD
# ============================================================

uploaded_file = st.file_uploader(
    "Upload Patent Document",
    type=["pdf", "docx"],
)


if uploaded_file is not None:

    try:

        # Get original file bytes.
        file_bytes = uploaded_file.getvalue()

        # Extract text only for preview and rewrite workflow.
        extracted_text = extract_text_from_file(
            file_bytes,
            uploaded_file.name,
        )

        # Store everything in session state.
        st.session_state.uploaded_bytes = file_bytes
        st.session_state.uploaded_text = extracted_text
        st.session_state.uploaded_filename = uploaded_file.name

        # New upload = clear previous results.
        st.session_state.analysis_result = None
        st.session_state.rewrite_result = None

        st.success(
            f"Document loaded: {uploaded_file.name}"
        )

        # ----------------------------------------------------
        # File information
        # ----------------------------------------------------

        info_col1, info_col2, info_col3 = st.columns(3)

        with info_col1:

            st.metric(
                "File",
                uploaded_file.name,
            )

        with info_col2:

            st.metric(
                "Size",
                f"{len(file_bytes) / 1024:.1f} KB",
            )

        with info_col3:

            st.metric(
                "Characters",
                f"{len(extracted_text):,}",
            )

        # ----------------------------------------------------
        # Preview
        # ----------------------------------------------------

        with st.expander(
            "Preview Extracted Text"
        ):

            preview = extracted_text[:10000]

            st.text_area(
                "Extracted Text",
                preview,
                height=300,
            )

    except Exception as exc:

        st.error(
            f"Unable to process document: {exc}"
        )


# ============================================================
# MAIN ACTION BUTTONS
# ============================================================

col1, col2 = st.columns(2)


with col1:

    analyze_button = st.button(
        "🔍 Start Patent Analysis",
        type="primary",
        use_container_width=True,
    )


with col2:

    rewrite_button = st.button(
        "✍️ Rewrite Form 2",
        use_container_width=True,
        disabled=(
            document_type
            != "Form 2 Complete Specification"
            or st.session_state.uploaded_bytes is None
        ),
    )


# ============================================================
# PATENT ANALYSIS
# ============================================================

if analyze_button:

    if st.session_state.uploaded_bytes is None:

        st.warning(
            "Please upload a PDF or DOCX document first."
        )

    else:

        with st.spinner(
            "Analyzing patent document..."
        ):

            try:

                # IMPORTANT:
                # analyzer.py expects file_bytes, NOT text.
                result = analyze_document(
                    file_bytes=(
                        st.session_state.uploaded_bytes
                    ),
                    filename=(
                        st.session_state.uploaded_filename
                    ),
                    document_type=document_type,
                    analysis_level=analysis_level,
                )

                st.session_state.analysis_result = result

                st.success(
                    "Patent analysis completed successfully."
                )

            except Exception as exc:

                st.error(
                    f"Analysis failed: {exc}"
                )


# ============================================================
# FORM 2 REWRITE
# ============================================================

if rewrite_button:

    if document_type != "Form 2 Complete Specification":

        st.warning(
            "Rewrite is currently available only for "
            "Form 2 Complete Specification."
        )

    elif not st.session_state.uploaded_text:

        st.warning(
            "Please upload a Form 2 document first."
        )

    else:

        # ----------------------------------------------------
        # Build analysis context
        # ----------------------------------------------------

        analysis_context = ""

        if st.session_state.analysis_result:

            try:

                analysis_context = str(
                    st.session_state.analysis_result
                )

            except Exception:

                analysis_context = ""

        with st.spinner(
            "Preparing proposed revised Form 2..."
        ):

            try:

                result = rewrite_form2(
                    original_text=(
                        st.session_state.uploaded_text
                    ),
                    analysis_context=analysis_context,
                    document_type=document_type,
                    analysis_level=analysis_level,
                )

                st.session_state.rewrite_result = result

                st.success(
                    "Proposed Form 2 rewrite generated."
                )

            except Exception as exc:

                st.error(
                    f"Form 2 rewriting failed: {exc}"
                )


# ============================================================
# ANALYSIS DASHBOARD
# ============================================================

analysis = st.session_state.analysis_result


if analysis:

    st.markdown("---")

    st.header(
        "Patent Analysis Dashboard"
    )

    tabs = st.tabs(
        [
            "Executive Summary",
            "Form 2",
            "Claims",
            "Abstract",
            "Potential Issues",
            "Report",
        ]
    )


    # ========================================================
    # EXECUTIVE SUMMARY
    # ========================================================

    with tabs[0]:

        gemini = analysis.get(
            "gemini_analysis",
            {},
        )

        document_assessment = gemini.get(
            "document_assessment",
            {},
        )

        scores = gemini.get(
            "scores",
            {},
        )

        st.subheader(
            "Executive Summary"
        )

        if isinstance(
            document_assessment,
            dict,
        ):

            summary = document_assessment.get(
                "summary",
                document_assessment.get(
                    "overall_assessment",
                    "",
                ),
            )

            if summary:
                st.write(summary)

        elif document_assessment:

            st.write(
                document_assessment
            )

        score_columns = st.columns(4)

        score_items = [
            (
                "Overall",
                scores.get(
                    "overall_score",
                    "N/A",
                ),
            ),
            (
                "Compliance",
                scores.get(
                    "compliance_score",
                    "N/A",
                ),
            ),
            (
                "Claims",
                scores.get(
                    "claim_score",
                    "N/A",
                ),
            ),
            (
                "Draft Quality",
                scores.get(
                    "drafting_quality_score",
                    "N/A",
                ),
            ),
        ]

        for column, (
            label,
            value,
        ) in zip(
            score_columns,
            score_items,
        ):

            with column:

                st.metric(
                    label,
                    value,
                )


    # ========================================================
    # FORM 2
    # ========================================================

    with tabs[1]:

        st.subheader(
            "Form 2 Structure & Compliance"
        )

        rule_engine = analysis.get(
            "rule_engine",
            {},
        )

        if rule_engine:

            col1, col2, col3 = st.columns(3)

            with col1:

                st.metric(
                    "Word Count",
                    rule_engine.get(
                        "word_count",
                        "N/A",
                    ),
                )

            with col2:

                claims = rule_engine.get(
                    "claims",
                    [],
                )

                st.metric(
                    "Claims",
                    len(claims),
                )

            with col3:

                issues = rule_engine.get(
                    "issues",
                    [],
                )

                st.metric(
                    "Issues",
                    len(issues),
                )

            sections = rule_engine.get(
                "sections",
                {},
            )

            if sections:

                st.markdown(
                    "### Detected Sections"
                )

                for section, detected in sections.items():

                    if detected:

                        st.success(
                            f"✓ {section}"
                        )

                    else:

                        st.warning(
                            f"⚠ {section} not detected"
                        )

        gemini_sections = (
            analysis
            .get(
                "gemini_analysis",
                {},
            )
            .get(
                "sections",
                [],
            )
        )

        if gemini_sections:

            st.markdown(
                "### Gemini Section Review"
            )

            for section in gemini_sections:

                if isinstance(
                    section,
                    dict,
                ):

                    section_name = section.get(
                        "section",
                        "Section",
                    )

                    with st.expander(
                        section_name
                    ):

                        st.write(
                            section.get(
                                "assessment",
                                section.get(
                                    "comments",
                                    "",
                                ),
                            )
                        )


    # ========================================================
    # CLAIMS
    # ========================================================

    with tabs[2]:

        st.subheader(
            "Claim Analysis"
        )

        claim_engine = analysis.get(
            "claim_engine",
            {},
        )

        claims = claim_engine.get(
            "claims",
            [],
        )

        if claims:

            for claim in claims:

                if isinstance(
                    claim,
                    dict,
                ):

                    number = claim.get(
                        "claim_number",
                        "?",
                    )

                    claim_type = claim.get(
                        "claim_type",
                        "",
                    )

                    with st.expander(
                        f"Claim {number} — {claim_type}"
                    ):

                        st.write(
                            claim.get(
                                "claim_text",
                                claim.get(
                                    "text",
                                    "",
                                ),
                            )
                        )

                        claim_issues = claim.get(
                            "issues",
                            [],
                        )

                        if claim_issues:

                            st.markdown(
                                "**Issues:**"
                            )

                            for issue in claim_issues:

                                st.warning(
                                    str(issue)
                                )

                else:

                    st.write(
                        str(claim)
                    )

        else:

            st.info(
                "No claim analysis available."
            )


    # ========================================================
    # ABSTRACT
    # ========================================================

    with tabs[3]:

        st.subheader(
            "Abstract Analysis"
        )

        abstract_analysis = (
            analysis
            .get(
                "gemini_analysis",
                {},
            )
            .get(
                "abstract_analysis",
                {},
            )
        )

        if abstract_analysis:

            st.json(
                abstract_analysis
            )

        else:

            rule_abstract = (
                analysis
                .get(
                    "rule_engine",
                    {},
                )
                .get(
                    "abstract",
                    "",
                )
            )

            if rule_abstract:

                st.text_area(
                    "Extracted Abstract",
                    rule_abstract,
                    height=250,
                )

            else:

                st.info(
                    "No abstract analysis available."
                )


    # ========================================================
    # POTENTIAL ISSUES
    # ========================================================

    with tabs[4]:

        st.subheader(
            "Potential Issues"
        )

        gemini_issues = (
            analysis
            .get(
                "gemini_analysis",
                {},
            )
            .get(
                "issues",
                [],
            )
        )

        rule_issues = (
            analysis
            .get(
                "rule_engine",
                {},
            )
            .get(
                "issues",
                [],
            )
        )

        all_issues = []

        if rule_issues:

            all_issues.extend(
                [
                    {
                        "source": "Rule Engine",
                        "issue": issue,
                    }
                    for issue in rule_issues
                ]
            )

        if gemini_issues:

            all_issues.extend(
                [
                    {
                        "source": "Gemini",
                        "issue": issue,
                    }
                    for issue in gemini_issues
                ]
            )

        if not all_issues:

            st.success(
                "No potential issues were identified."
            )

        else:

            for item in all_issues:

                issue = item["issue"]

                if isinstance(
                    issue,
                    dict,
                ):

                    severity = issue.get(
                        "severity",
                        "REVIEW",
                    )

                    title = issue.get(
                        "title",
                        issue.get(
                            "issue",
                            "Potential Issue",
                        ),
                    )

                    with st.expander(
                        f"{severity}: {title}"
                    ):

                        st.write(
                            issue.get(
                                "description",
                                issue.get(
                                    "message",
                                    "",
                                ),
                            )
                        )

                        recommendation = issue.get(
                            "recommendation"
                        )

                        if recommendation:

                            st.markdown(
                                "**Recommendation:**"
                            )

                            st.write(
                                recommendation
                            )

                else:

                    st.warning(
                        str(issue)
                    )


    # ========================================================
    # REPORT
    # ========================================================

    with tabs[5]:

        st.subheader(
            "Analysis Report"
        )

        document_name = (
            st.session_state.uploaded_filename
            or "patent_document"
        )

        markdown_report = (
            generate_markdown_report(
                analysis,
                document_name,
            )
        )

        text_report = (
            generate_text_report(
                analysis,
                document_name,
            )
        )

        st.download_button(
            "⬇️ Download Markdown Report",
            markdown_report,
            file_name="patent_analysis_report.md",
            mime="text/markdown",
        )

        st.download_button(
            "⬇️ Download Text Report",
            text_report,
            file_name="patent_analysis_report.txt",
            mime="text/plain",
        )

        with st.expander(
            "Preview Report"
        ):

            st.markdown(
                markdown_report
            )


# ============================================================
# REWRITE RESULTS
# ============================================================

rewrite = st.session_state.rewrite_result


if rewrite:

    st.markdown("---")

    st.header(
        "✍️ Proposed Revised Form 2"
    )

    st.warning(
        """
        This is a proposed drafting revision, not an automatically
        legally valid amendment. Review the changes against the
        originally filed disclosure and applicable Indian patent law
        before using it for prosecution.
        """
    )


    # ========================================================
    # REWRITE SUMMARY
    # ========================================================

    summary = get_rewrite_summary(
        rewrite
    )

    col1, col2, col3, col4 = st.columns(4)

    with col1:

        st.metric(
            "Rewrite Status",
            summary.get(
                "rewrite_status",
                "UNKNOWN",
            ),
        )

    with col2:

        st.metric(
            "Changed Claims",
            summary.get(
                "changed_claims",
                0,
            ),
        )

    with col3:

        st.metric(
            "New-Matter Flags",
            summary.get(
                "flag_count",
                0,
            ),
        )

    with col4:

        st.metric(
            "Human Review",
            (
                "REQUIRED"
                if summary.get(
                    "human_review_required",
                    True,
                )
                else "NOT FLAGGED"
            ),
        )


    # ========================================================
    # SECTION 59 SCREENING
    # ========================================================

    new_matter = rewrite.get(
        "new_matter_check",
        {},
    )

    st.markdown(
        "### Section 59 New-Matter Screening"
    )

    status = new_matter.get(
        "overall_status",
        "UNKNOWN",
    )

    if status == "NO_OBVIOUS_NEW_MATTER_SIGNAL":

        st.success(
            "No obvious new-matter signal was detected "
            "by the automated comparison."
        )

    else:

        st.error(
            "Human review is required: the automated comparison "
            "detected differences requiring review."
        )

    st.caption(
        "This comparison is a screening tool and does not "
        "make a legal determination under Section 59."
    )


    # ========================================================
    # REVIEW FLAGS
    # ========================================================

    flags = new_matter.get(
        "flags",
        [],
    )

    if flags:

        st.markdown(
            "#### Review Flags"
        )

        for flag in flags:

            flag_type = flag.get(
                "type",
                "Review Flag",
            )

            with st.expander(
                flag_type
            ):

                st.write(
                    flag.get(
                        "message",
                        "",
                    )
                )

                if flag.get("items"):

                    st.write(
                        flag["items"]
                    )

                if flag.get("claims"):

                    st.json(
                        flag["claims"]
                    )


    # ========================================================
    # REVISION SUMMARY
    # ========================================================

    revision_summary = rewrite.get(
        "revision_summary",
        [],
    )

    if revision_summary:

        st.markdown(
            "### Revision Summary"
        )

        for item in revision_summary:

            st.write(
                f"• {item}"
            )


    # ========================================================
    # ORIGINAL VS REVISED
    # ========================================================

    st.markdown(
        "### Original vs Revised"
    )

    original_text = (
        st.session_state.uploaded_text
    )

    revised_text = revised_form2_to_text(
        rewrite
    )

    original_col, revised_col = st.columns(2)

    with original_col:

        st.markdown(
            "#### Original Form 2"
        )

        st.text_area(
            "Original",
            original_text,
            height=700,
            label_visibility="collapsed",
            key="original_form2_display",
        )

    with revised_col:

        st.markdown(
            "#### Proposed Revised Form 2"
        )

        st.text_area(
            "Revised",
            revised_text,
            height=700,
            label_visibility="collapsed",
            key="revised_form2_display",
        )


    # ========================================================
    # REVISED SECTIONS
    # ========================================================

    revised_form2 = rewrite.get(
        "revised_form2",
        {},
    )

    st.markdown(
        "### Revised Form 2 Sections"
    )

    section_labels = [
        (
            "Title",
            "title",
        ),
        (
            "Field of Invention",
            "field_of_invention",
        ),
        (
            "Background",
            "background",
        ),
        (
            "Objects of the Invention",
            "objects",
        ),
        (
            "Summary",
            "summary",
        ),
        (
            "Brief Description of Drawings",
            "brief_description_of_drawings",
        ),
        (
            "Detailed Description",
            "detailed_description",
        ),
        (
            "Abstract",
            "abstract",
        ),
    ]

    for label, key in section_labels:

        value = revised_form2.get(
            key,
            "",
        )

        if isinstance(
            value,
            list,
        ):

            value = "\n".join(
                str(item)
                for item in value
            )

        if value:

            with st.expander(
                label
            ):

                st.text_area(
                    label,
                    str(value),
                    height=200,
                    key=f"rewrite_section_{key}",
                )


    # ========================================================
    # REVISED CLAIMS
    # ========================================================

    revised_claims = revised_form2.get(
        "claims",
        [],
    )

    if revised_claims:

        st.markdown(
            "### Proposed Revised Claims"
        )

        for index, claim in enumerate(
            revised_claims,
            start=1,
        ):

            if isinstance(
                claim,
                dict,
            ):

                claim_number = claim.get(
                    "claim_number",
                    index,
                )

                claim_text = claim.get(
                    "claim_text",
                    "",
                )

                claim_type = claim.get(
                    "claim_type",
                    "",
                )

                claim_status = claim.get(
                    "status",
                    "",
                )

            else:

                claim_number = index
                claim_text = str(claim)
                claim_type = ""
                claim_status = ""

            with st.expander(
                f"Claim {claim_number}"
            ):

                if claim_type:

                    st.caption(
                        f"Type: {claim_type}"
                    )

                if claim_status:

                    st.caption(
                        f"Status: {claim_status}"
                    )

                st.text_area(
                    f"Claim {claim_number}",
                    claim_text,
                    height=180,
                    key=f"revised_claim_{claim_number}",
                )


    # ========================================================
    # CHANGE LOG
    # ========================================================

    change_log = rewrite.get(
        "change_log",
        [],
    )

    if change_log:

        st.markdown(
            "### Change Log"
        )

        for change in change_log:

            if isinstance(
                change,
                dict,
            ):

                section = change.get(
                    "section",
                    "Section",
                )

                reason = change.get(
                    "reason",
                    "",
                )

                risk = change.get(
                    "new_matter_risk",
                    "REVIEW",
                )

                with st.expander(
                    f"{section} — {risk}"
                ):

                    st.write(
                        change.get(
                            "change",
                            "",
                        )
                    )

                    if reason:

                        st.caption(
                            f"Reason: {reason}"
                        )

            else:

                st.write(
                    str(change)
                )


    # ========================================================
    # COMPLIANCE REVIEW
    # ========================================================

    compliance = rewrite.get(
        "compliance_review",
        {},
    )

    if compliance:

        st.markdown(
            "### Compliance Review"
        )

        st.json(
            compliance
        )


    # ========================================================
    # EXPORT
    # ========================================================

    st.markdown(
        "### Export Proposed Revision"
    )

    st.download_button(
        "⬇️ Download Revised Form 2",
        revised_text,
        file_name="proposed_revised_form2.txt",
        mime="text/plain",
    )

    revised_markdown = (
        "# Proposed Revised Form 2\n\n"
        + revised_text
        + "\n\n---\n\n"
        + "This document is a proposed drafting revision "
        "and requires human patent-professional review."
    )

    st.download_button(
        "⬇️ Download Revised Form 2 Markdown",
        revised_markdown,
        file_name="proposed_revised_form2.md",
        mime="text/markdown",
    )


# ============================================================
# FOOTER
# ============================================================

st.markdown("---")

st.caption(
    """
Indian Patent Draft Analyzer — Drafting assistance only.
Automated analysis does not constitute legal advice, a patentability
opinion, or a determination by the Indian Patent Office.
"""
)
