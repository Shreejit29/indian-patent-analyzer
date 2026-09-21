
"""Evidence-first deterministic patent analysis helpers.

These checks are intentionally conservative: they surface evidence for
human review and never make a legal determination.
"""
from __future__ import annotations
import re, math, hashlib
from collections import Counter
from typing import Any, Dict, List, Tuple

STOPWORDS = set("""
a an the and or of to in for with on by from is are was were be been being
this that which as at into than then there their its it we our your said
such may can could should would using used use based comprising including
where when through between within without having provided configured thereof
therein said one two three
""".split())

def paragraphs(text: str) -> List[Dict[str, Any]]:
    blocks=[]
    offset=0
    for raw in re.split(r"\n\s*\n+", text or ""):
        s=raw.strip()
        if not s:
            offset += len(raw)+1; continue
        start=(text or "").find(s, offset)
        blocks.append({"id":len(blocks)+1,"text":s,"start":start,"end":start+len(s)})
        offset=start+len(s)
    return blocks

def sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", text or "") if s.strip()]

def terms(text: str) -> List[str]:
    toks=re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", (text or "").lower())
    return [t for t in toks if t not in STOPWORDS]

def sentence_evidence(query: str, text: str, top_k: int=5) -> List[Dict[str,Any]]:
    q=Counter(terms(query))
    if not q: return []
    out=[]
    for i,s in enumerate(sentences(text),1):
        c=Counter(terms(s))
        overlap=sum(min(q[k],c[k]) for k in q)
        if overlap:
            score=overlap/(sum(q.values()) or 1)
            out.append({"sentence_id":i,"score":round(score,4),"text":s})
    return sorted(out,key=lambda x:x["score"],reverse=True)[:top_k]

def claim_element_extraction(claim: str) -> List[str]:
    """Conservative extraction of structural/functional limitations."""
    if not claim: return []
    x=re.sub(r"\s+"," ",claim).strip()
    x=re.sub(r"^\d+\s*[\.)]\s*","",x)
    # Split around drafting connectors while retaining technical phrases.
    parts=re.split(r";|\bcomprising\b|\bwherein\b|\bconfigured to\b|\badapted to\b|\bcharacterized by\b",x,flags=re.I)
    elements=[]
    for p in parts:
        p=p.strip(" ,:")
        if len(p.split())>=2 and p.lower() not in {"a system","a method","an apparatus"}:
            elements.append(p)
    return elements[:40]

def claim_support_map(claims: List[Dict[str,Any]], specification: str) -> List[Dict[str,Any]]:
    result=[]
    for c in claims:
        num=c.get("claim_number")
        text=c.get("claim_text",c.get("text",""))
        els=claim_element_extraction(text)
        mapped=[]
        for e in els:
            ev=sentence_evidence(e,specification,3)
            mapped.append({
                "element":e,
                "status":"CLEAR_SUPPORT" if ev and ev[0]["score"]>=0.35 else ("POSSIBLE_SUPPORT" if ev else "NO_CLEAR_SUPPORT"),
                "evidence":ev,
            })
        result.append({"claim_number":num,"elements":mapped})
    return result

def document_fingerprint(text: str) -> Dict[str,str]:
    clean=re.sub(r"\s+"," ",text or "").strip().lower()
    return {"sha256":hashlib.sha256(clean.encode()).hexdigest(),"characters":str(len(text or ""))}

def detect_risk_signals(text: str, claims: List[Dict[str,Any]]) -> List[Dict[str,Any]]:
    findings=[]
    low=(text or "").lower()
    checks=[
        ("MISSING_DETAILED_DISCLOSURE", r"\bdetailed description\b", "No detailed-description heading was detected."),
        ("RESULT_ONLY_LANGUAGE", r"\b(?:best|excellent|superior|significantly improved)\b", "Promotional/result-only language may merit technical substantiation."),
        ("UNDEFINED_ACRONYMS", r"\b[A-Z]{3,6}\b", "Upper-case acronyms may require definition at first use."),
    ]
    for code,pat,msg in checks:
        if not re.search(pat,text or "",re.I if code!="UNDEFINED_ACRONYMS" else 0):
            if code=="MISSING_DETAILED_DISCLOSURE": findings.append({"code":code,"severity":"HIGH","message":msg})
        elif code!="MISSING_DETAILED_DISCLOSURE":
            findings.append({"code":code,"severity":"LOW","message":msg})
    for c in claims:
        ct=c.get("claim_text","")
        if len(ct.split())>180:
            findings.append({"code":"LONG_CLAIM","severity":"MEDIUM","claim_number":c.get("claim_number"),"message":"Claim is unusually long; review claim structure and conciseness."})
        if re.search(r"\bthe\s+\w+\b",ct,re.I) and not re.search(r"\ba\s+\w+|\ban\s+\w+|\bone\s+\w+",ct,re.I):
            findings.append({"code":"ANTECEDENT_REVIEW","severity":"MEDIUM","claim_number":c.get("claim_number"),"message":"Possible antecedent-basis issue; verify every 'the' term has a clear antecedent."})
    return findings

def confidence_from_evidence(evidence: List[Dict[str,Any]]) -> str:
    if not evidence: return "LOW"
    s=evidence[0].get("score",0)
    return "HIGH" if s>=0.65 else ("MEDIUM" if s>=0.35 else "LOW")
