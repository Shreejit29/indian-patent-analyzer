import json
import hashlib
from datetime import datetime, timezone

import streamlit as st

from services.analyzer import analyze_document
from services.document_parser import extract_text_from_file, get_document_statistics
from services.form2_rewriter import rewrite_form2, revised_form2_to_text, get_rewrite_summary
from services.report_generator import generate_markdown_report, generate_text_report
from services.evidence_engine import claim_support_map, detect_risk_signals, document_fingerprint
from services.prior_art import build_queries, links
from services.scoring import score_analysis

APP_VERSION = "3.0.0"

st.set_page_config(
    page_title="Indian Patent Intelligence Studio",
    page_icon="⚖️",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
    .block-container {max-width: 1500px; padding-top: 1.2rem; padding-bottom: 3rem;}
    .hero {padding: 1.6rem 1.8rem; border-radius: 20px; background: linear-gradient(135deg,#0f172a,#1e293b); color: white; margin-bottom: 1rem; border: 1px solid #334155;}
    .hero h1 {margin:0; font-size:2.25rem; letter-spacing:-.03em;}
    .hero p {margin:.45rem 0 0; opacity:.82; font-size:1rem;}
    .small {font-size:.82rem; opacity:.75;}
    .section-card {padding:1rem; border:1px solid #e5e7eb; border-radius:14px; margin:.5rem 0;}
    </style>
    """,
    unsafe_allow_html=True,
)

DEFAULTS = {
    "analysis_result": None,
    "uploaded_text": "",
    "uploaded_filename": "",
    "uploaded_bytes": None,
    "rewrite_result": None,
    "analysis_id": None,
}
for key, value in DEFAULTS.items():
    st.session_state.setdefault(key, value)

st.markdown(
    '<div class="hero"><h1>⚖️ Indian Patent Intelligence Studio</h1>'
    '<p>Evidence-first claim analysis • Indian patent-rule screening • support mapping • prior-art discovery • amendment review</p></div>',
    unsafe_allow_html=True,
)

with st.sidebar:
    st.header("Analysis Controls")
    document_type = st.selectbox(
        "Document type",
        [
            "Form 2 Complete Specification",
            "Form 2 Provisional Specification",
            "Claims",
            "Abstract",
            "FER Response",
            "Other",
        ],
    )
    analysis_level = st.selectbox("Analysis depth", ["Basic", "Detailed", "Comprehensive"], index=2)
    st.divider()
    st.caption(f"Application version: {APP_VERSION}")
    st.caption("Analysis ID, document fingerprint and evidence are retained in the current session.")
    st.info(
        "Decision-support software only. It does not determine patentability, validity, infringement, or grant/rejection."
    )
    st.warning(
        "Verify the current Patents Act, Rules, notifications, manuals and case law before relying on any legal analysis."
    )

uploaded = st.file_uploader(
    "Upload patent document",
    type=["pdf", "docx"],
    help="PDF or DOCX. For scanned PDFs, OCR is recommended before analysis.",
)

if uploaded:
    raw = uploaded.getvalue()
    if (
        st.session_state.uploaded_filename != uploaded.name
        or st.session_state.uploaded_bytes != raw
    ):
        try:
            extracted = extract_text_from_file(raw, uploaded.name)
            st.session_state.update(
                uploaded_bytes=raw,
                uploaded_text=extracted,
                uploaded_filename=uploaded.name,
                analysis_result=None,
                rewrite_result=None,
                analysis_id=None,
            )
        except Exception as exc:
            st.error(f"Document extraction failed: {exc}")

if st.session_state.uploaded_text:
    stats = get_document_statistics(st.session_state.uploaded_text)
    fingerprint = hashlib.sha256(st.session_state.uploaded_bytes or b"").hexdigest()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Document", st.session_state.uploaded_filename[:28])
    c2.metric("Size", f"{len(st.session_state.uploaded_bytes)/1024:.1f} KB")
    c3.metric("Words", f"{len(st.session_state.uploaded_text.split()):,}")
    c4.metric("SHA-256", fingerprint[:12] + "…")
    with st.expander("Extracted text preview"):
        st.text(st.session_state.uploaded_text[:12000])

col_a, col_b = st.columns([2, 1])
with col_a:
    analyze = st.button("🔍 Run Full Patent Analysis", type="primary", use_container_width=True)
with col_b:
    rewrite = st.button(
        "✍️ Propose Form 2 Revision",
        use_container_width=True,
        disabled=not bool(st.session_state.uploaded_text),
    )

if analyze:
    if not st.session_state.uploaded_bytes:
        st.warning("Upload a document first.")
    else:
        with st.status("Running evidence-first analysis…", expanded=True) as status:
            try:
                result = analyze_document(
                    st.session_state.uploaded_bytes,
                    st.session_state.uploaded_filename,
                    document_type,
                    analysis_level,
                )
                rule = result.get("rule_engine", {})
                claim_engine = result.get("claim_engine", {})
                claims = claim_engine.get("claims", [])

                result["support_map"] = claim_support_map(claims, st.session_state.uploaded_text)
                result["risk_signals"] = detect_risk_signals(st.session_state.uploaded_text, claims)
                result["quality_score"] = score_analysis(
                    rule, claim_engine, result.get("gemini_analysis", {})
                )
                result["fingerprint"] = document_fingerprint(st.session_state.uploaded_text)
                result["prior_art_queries"] = build_queries(
                    rule.get("title", ""), rule.get("abstract", ""), claims
                )

                analysis_id = "IPA-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + "-" + fingerprint[:8]
                result["provenance"] = {
                    "analysis_id": analysis_id,
                    "application_version": APP_VERSION,
                    "analysis_timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "document_sha256": fingerprint,
                    "document_type": document_type,
                    "analysis_level": analysis_level,
                }

                st.session_state.analysis_result = result
                st.session_state.analysis_id = analysis_id
                status.update(label="Analysis complete", state="complete")
            except Exception as exc:
                status.update(label="Analysis failed", state="error")
                st.exception(exc)

if rewrite:
    with st.spinner("Generating proposed revision and screening for potential new matter…"):
        try:
            context = json.dumps(st.session_state.analysis_result, ensure_ascii=False)[:60000] if st.session_state.analysis_result else ""
            st.session_state.rewrite_result = rewrite_form2(
                st.session_state.uploaded_text, context, document_type, analysis_level
            )
        except Exception as exc:
            st.error(f"Rewrite failed: {exc}")

analysis = st.session_state.analysis_result
if analysis:
    gemini = analysis.get("gemini_analysis", {})
    quality = analysis.get("quality_score", {})
    claims = analysis.get("claim_engine", {}).get("claims", [])
    support = analysis.get("support_map", [])
    support_by_claim = {item.get("claim_number"): item for item in support}

    st.divider()
    tabs = st.tabs([
        "Overview",
        "Claims & Support",
        "Legal Issues",
        "Prior Art",
        "Evidence",
        "Provenance",
        "Report",
    ])

    with tabs[0]:
        assessment = gemini.get("document_assessment", {})
        summary = assessment.get("overall_summary", assessment.get("summary", "")) if isinstance(assessment, dict) else assessment
        st.subheader("Executive assessment")
        st.write(summary or "No executive summary was returned.")
        metrics = st.columns(5)
        values = [
            ("Readiness", quality.get("overall_readiness", "—")),
            ("Structure", quality.get("form_structure", "—")),
            ("Claims", quality.get("claim_structure", "—")),
            ("Completeness", quality.get("document_completeness", "—")),
            ("Review signals", len(analysis.get("risk_signals", []))),
        ]
        for col, (label, value) in zip(metrics, values):
            col.metric(label, value)
        st.caption(quality.get("methodology", ""))

    with tabs[1]:
        st.subheader(f"Claim intelligence · {len(claims)} claims")
        if not claims:
            st.warning("No claims were reliably parsed from the uploaded document.")
        for claim in claims:
            number = claim.get("claim_number", "?")
            with st.expander(f"Claim {number} · {claim.get('claim_type', 'Unknown')} · {claim.get('claim_category', '')}"):
                st.write(claim.get("claim_text", claim.get("text", "")))
                mapped = support_by_claim.get(number, {}).get("elements", [])
                if mapped:
                    st.markdown("**Limitation-to-disclosure support**")
                    for item in mapped:
                        status = item.get("status", "UNKNOWN")
                        icon = {"CLEAR_SUPPORT": "🟢", "POSSIBLE_SUPPORT": "🟡", "NO_CLEAR_SUPPORT": "🔴"}.get(status, "⚪")
                        st.markdown(f"{icon} **{status}** — {item.get('element', '')}")
                        for evidence in item.get("evidence", [])[:3]:
                            st.caption(f"Evidence: {evidence.get('text', '')}")
                checks = []
                if claim.get("antecedent_basis_issues"):
                    checks.append(("Antecedent basis", claim["antecedent_basis_issues"]))
                if claim.get("dependency_issues"):
                    checks.append(("Dependency", claim["dependency_issues"]))
                for label, issues in checks:
                    st.warning(f"{label}: {issues}")

    with tabs[2]:
        st.subheader("Issues requiring human review")
        issues = (
            analysis.get("rule_engine", {}).get("issues", [])
            + analysis.get("risk_signals", [])
            + (gemini.get("issues", []) if isinstance(gemini, dict) else [])
        )
        if not issues:
            st.success("No issues were surfaced by the available checks.")
        for index, issue in enumerate(issues, 1):
            if isinstance(issue, dict):
                severity = issue.get("severity", issue.get("category", "REVIEW"))
                title = issue.get("finding", issue.get("message", issue.get("title", f"Issue {index}")))
                with st.expander(f"{severity} · {title}"):
                    st.json(issue)
            else:
                st.write(issue)

    with tabs[3]:
        st.subheader("Prior-art discovery workspace")
        st.caption("Search links are discovery aids. They are not a novelty or inventive-step conclusion.")
        for query in analysis.get("prior_art_queries", []):
            st.markdown(f"**Query:** `{query}`")
            for name, url in links(query).items():
                st.markdown(f"- [{name}]({url})")

    with tabs[4]:
        st.subheader("Traceable evidence")
        manual = analysis.get("manual", {})
        st.write("Manual retrieval status:", manual.get("retrieval_status", "Unknown"))
        for evidence in manual.get("evidence", [])[:15]:
            st.markdown(
                f"**Pages {evidence.get('page_start')}-{evidence.get('page_end')}** · score {evidence.get('match_score')}"
            )
            st.caption(evidence.get("text", "")[:1400])
        st.subheader("Deterministic risk signals")
        st.json(analysis.get("risk_signals", []))

    with tabs[5]:
        st.subheader("Analysis provenance")
        st.json(analysis.get("provenance", {}))
        st.caption("Use the analysis ID and document SHA-256 when comparing or reproducing a review.")

    with tabs[6]:
        name = analysis.get("document_name", "patent")
        markdown = generate_markdown_report(analysis, name)
        text_report = generate_text_report(analysis, name)
        base = name.rsplit(".", 1)[0]
        st.download_button("Download Markdown report", markdown, file_name=f"{base}_analysis.md")
        st.download_button("Download Text report", text_report, file_name=f"{base}_analysis.txt")
        st.download_button(
            "Download JSON evidence",
            json.dumps(analysis, indent=2, ensure_ascii=False),
            file_name=f"{base}_analysis.json",
            mime="application/json",
        )
        st.markdown(markdown[:20000])

if st.session_state.rewrite_result:
    result = st.session_state.rewrite_result
    st.divider()
    st.header("Proposed Form 2 Revision")
    summary = get_rewrite_summary(result)
    cols = st.columns(4)
    cols[0].metric("Status", summary["rewrite_status"])
    cols[1].metric("Changed claims", summary["changed_claims"])
    cols[2].metric("New-matter flags", summary["flag_count"])
    cols[3].metric("Human review", "REQUIRED" if summary["human_review_required"] else "NOT FLAGGED")
    st.warning("AI-proposed drafting only. Compare every amendment with the originally filed disclosure and current law before use.")
    new_matter = result.get("new_matter_check", {})
    st.subheader("Section 59 screening")
    st.info(new_matter.get("overall_status", "UNKNOWN"))
    st.json(new_matter.get("flags", []))
    st.subheader("Proposed text")
    revised = revised_form2_to_text(result)
    st.text_area("Revised Form 2", revised, height=600)
    st.download_button("Download proposed Form 2", revised, file_name="proposed_revised_form2.txt")

st.divider()
st.caption(
    "Indian Patent Intelligence Studio · AI-assisted review · Not legal advice · Verify current IP India sources before use."
)
