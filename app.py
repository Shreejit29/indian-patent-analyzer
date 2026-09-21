
import json
import streamlit as st
from services.analyzer import analyze_document
from services.document_parser import extract_text_from_file
from services.form2_rewriter import rewrite_form2, revised_form2_to_text, get_rewrite_summary
from services.report_generator import generate_markdown_report, generate_text_report
from services.evidence_engine import claim_support_map, detect_risk_signals, document_fingerprint
from services.prior_art import build_queries, links
from services.scoring import score_analysis

st.set_page_config(page_title="Patent Intelligence Studio", page_icon="⚖️", layout="wide", initial_sidebar_state="expanded")

st.markdown("""<style>
.block-container{padding-top:1.4rem;max-width:1500px}
.hero{padding:1.4rem 1.6rem;border-radius:18px;background:linear-gradient(135deg,#111827,#1f2937);color:white;margin-bottom:1rem}
.hero h1{margin:0;font-size:2.2rem}.hero p{opacity:.82;margin:.35rem 0 0}
.badge{display:inline-block;padding:.22rem .55rem;border-radius:999px;background:#e5e7eb;color:#111827;font-size:.75rem;margin:.12rem}
</style>""",unsafe_allow_html=True)

for k,v in {"analysis_result":None,"uploaded_text":"","uploaded_filename":"","uploaded_bytes":None,"rewrite_result":None}.items():
    st.session_state.setdefault(k,v)

st.markdown('<div class="hero"><h1>⚖️ Patent Intelligence Studio</h1><p>Evidence-first Indian patent draft analysis • claim intelligence • support mapping • amendment screening • prior-art discovery</p></div>',unsafe_allow_html=True)

with st.sidebar:
    st.header("Analysis Controls")
    document_type=st.selectbox("Document type",["Form 2 Complete Specification","Form 2 Provisional Specification","Claims","Abstract","FER Response","Other"])
    analysis_level=st.selectbox("Analysis depth",["Basic","Detailed","Comprehensive"],index=2)
    st.caption("The analyzer is decision support. It does not determine patentability, validity, infringement, or grant/rejection.")
    st.divider()
    st.markdown("**Knowledge-base status**")
    st.info("Local Manual: 2019 v3.0\n\nCurrent official IP India pages should be checked for amendments. The bundled manual is guidance, not law.")

uploaded=st.file_uploader("Upload patent document",type=["pdf","docx"],help="PDF or DOCX. For scanned PDFs, provide an OCR/text-enabled version for best results.")
if uploaded:
    b=uploaded.getvalue()
    try:
        text=extract_text_from_file(b,uploaded.name)
        st.session_state.update(uploaded_bytes=b,uploaded_text=text,uploaded_filename=uploaded.name,analysis_result=None,rewrite_result=None)
        c1,c2,c3,c4=st.columns(4)
        c1.metric("Document",uploaded.name[:28])
        c2.metric("Size",f"{len(b)/1024:.1f} KB")
        c3.metric("Characters",f"{len(text):,}")
        c4.metric("Words",f"{len(text.split()):,}")
        with st.expander("Extracted text preview"):
            st.text(text[:12000])
    except Exception as e: st.error(f"Document extraction failed: {e}")

a,b=st.columns([2,1])
with a: analyze=st.button("🔍 Analyze Patent",type="primary",use_container_width=True)
with b: rewrite=st.button("✍️ Propose Form 2 Revision",use_container_width=True,disabled=not st.session_state.uploaded_text)

if analyze:
    if not st.session_state.uploaded_bytes: st.warning("Upload a document first.")
    else:
        with st.status("Running evidence-first analysis…",expanded=True) as status:
            try:
                result=analyze_document(st.session_state.uploaded_bytes,st.session_state.uploaded_filename,document_type,analysis_level)
                # Add deterministic post-analysis intelligence.
                rule=result.get("rule_engine",{}); ce=result.get("claim_engine",{})
                claims=ce.get("claims",[])
                support=claim_support_map(claims,st.session_state.uploaded_text)
                risks=detect_risk_signals(st.session_state.uploaded_text,claims)
                result["support_map"]=support
                result["risk_signals"]=risks
                result["quality_score"]=score_analysis(rule,ce,result.get("gemini_analysis",{}))
                result["fingerprint"]=document_fingerprint(st.session_state.uploaded_text)
                result["prior_art_queries"]=build_queries(rule.get("title",""),rule.get("abstract",""),claims)
                st.session_state.analysis_result=result
                status.update(label="Analysis complete",state="complete")
            except Exception as e:
                status.update(label="Analysis failed",state="error"); st.exception(e)

if rewrite:
    if not st.session_state.uploaded_text: st.warning("Upload a document first.")
    else:
        with st.spinner("Generating proposed revision and screening for new matter…"):
            try:
                ctx=json.dumps(st.session_state.analysis_result,ensure_ascii=False)[:60000] if st.session_state.analysis_result else ""
                st.session_state.rewrite_result=rewrite_form2(st.session_state.uploaded_text,ctx,document_type,analysis_level)
            except Exception as e: st.error(f"Rewrite failed: {e}")

analysis=st.session_state.analysis_result
if analysis:
    gem=analysis.get("gemini_analysis",{}); qa=analysis.get("quality_score",{})
    st.divider()
    tabs=st.tabs(["Executive","Claims & Support","Issues","Prior Art","Evidence","Report"])
    with tabs[0]:
        st.subheader("Executive assessment")
        da=gem.get("document_assessment",{})
        st.write(da.get("overall_summary",da.get("summary",da.get("core_invention","")) if isinstance(da,dict) else da))
        cols=st.columns(5)
        for col,(label,key) in zip(cols,[("Readiness","overall_readiness"),("Structure","form_structure"),("Claims","claim_structure"),("Completeness","document_completeness"),("Risks", "risk_count")]):
            val=len(analysis.get("risk_signals",[])) if key=="risk_count" else qa.get(key,"—")
            col.metric(label,val)
        st.caption(qa.get("methodology",""))
        st.subheader("Document identity")
        st.json({"filename":analysis.get("document_name"),"sha256":analysis.get("fingerprint",{}).get("sha256"),"statistics":analysis.get("document_statistics",{})})
    with tabs[1]:
        claims=analysis.get("claim_engine",{}).get("claims",[])
        support=analysis.get("support_map",[])
        smap={x["claim_number"]:x for x in support}
        if not claims: st.warning("No claims were reliably parsed.")
        for c in claims:
            n=c.get("claim_number","?"); text=c.get("claim_text",c.get("text",""))
            with st.expander(f"Claim {n} • {c.get('claim_type','')}"):
                st.write(text)
                mapped=smap.get(n,{}).get("elements",[])
                if mapped:
                    st.markdown("**Limitation-to-disclosure support map**")
                    for m in mapped:
                        icon={"CLEAR_SUPPORT":"🟢","POSSIBLE_SUPPORT":"🟡","NO_CLEAR_SUPPORT":"🔴"}.get(m["status"],"⚪")
                        st.markdown(f"{icon} **{m['status']}** — {m['element']}")
                        for ev in m.get("evidence",[])[:2]: st.caption(f"Evidence: {ev['text']}")
    with tabs[2]:
        issues=analysis.get("rule_engine",{}).get("issues",[])+analysis.get("risk_signals",[])+gem.get("issues",[])
        if not issues: st.success("No issues were surfaced by the available deterministic and AI checks.")
        for i,x in enumerate(issues,1):
            if isinstance(x,dict):
                sev=x.get("severity",x.get("category","REVIEW")); title=x.get("finding",x.get("message",x.get("title",f"Issue {i}")))
                with st.expander(f"{sev} • {title}"):
                    st.json(x)
            else: st.write(x)
    with tabs[3]:
        st.subheader("Prior-art discovery workspace")
        st.caption("These are search aids, not novelty conclusions. Review the cited documents yourself.")
        queries=analysis.get("prior_art_queries",[])
        for q in queries:
            st.markdown(f"**Query:** `{q}`")
            for name,url in links(q).items(): st.markdown(f"- [{name}]({url})")
    with tabs[4]:
        st.subheader("Traceable evidence")
        st.write("Manual retrieval",analysis.get("manual",{}).get("retrieval_status"))
        for e in analysis.get("manual",{}).get("evidence",[])[:12]:
            st.markdown(f"**Manual pages {e.get('page_start')}-{e.get('page_end')}** • score {e.get('match_score')}")
            st.caption(e.get("text","")[:1200])
        st.subheader("Deterministic risk signals")
        st.json(analysis.get("risk_signals",[]))
    with tabs[5]:
        name=analysis.get("document_name","patent")
        md=generate_markdown_report(analysis,name)
        txt=generate_text_report(analysis,name)
        st.download_button("Download Markdown report",md,file_name=f"{name.rsplit('.',1)[0]}_analysis.md")
        st.download_button("Download Text report",txt,file_name=f"{name.rsplit('.',1)[0]}_analysis.txt")
        st.download_button("Download JSON evidence",json.dumps(analysis,indent=2,ensure_ascii=False),file_name=f"{name.rsplit('.',1)[0]}_analysis.json",mime="application/json")
        st.markdown(md[:20000])

if st.session_state.rewrite_result:
    r=st.session_state.rewrite_result
    st.divider(); st.header("Proposed Form 2 Revision")
    s=get_rewrite_summary(r); c=st.columns(4)
    c[0].metric("Status",s["rewrite_status"]); c[1].metric("Changed claims",s["changed_claims"]); c[2].metric("New-matter flags",s["flag_count"]); c[3].metric("Human review","REQUIRED" if s["human_review_required"] else "NOT FLAGGED")
    st.warning("AI-proposed drafting only. Compare every amendment with the originally filed disclosure and applicable law before use.")
    nm=r.get("new_matter_check",{})
    st.subheader("Section 59 screening")
    st.info(nm.get("overall_status","UNKNOWN"))
    st.json(nm.get("flags",[]))
    st.subheader("Proposed text")
    revised=revised_form2_to_text(r)
    st.text_area("Revised Form 2",revised,height=600)
    st.download_button("Download proposed Form 2",revised,file_name="proposed_revised_form2.txt")

st.divider()
st.caption("Patent Intelligence Studio • AI-assisted drafting and review • Not legal advice • Always verify current IP India Act, Rules, forms, notifications and case law.")
