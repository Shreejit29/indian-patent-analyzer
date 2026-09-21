from __future__ import annotations

import re
from typing import Any


ANALYZER_VERSION = "3.0.0"
_STOPWORDS = {"the", "a", "an", "and", "or", "of", "to", "in", "on", "for", "with", "by", "from", "as", "at", "is", "are", "was", "were", "configured", "wherein", "comprising", "including", "said", "such"}
_GENERIC = {"method", "system", "device", "apparatus", "step", "first", "second", "third", "one", "more", "claim", "claims", "component", "element"}

def normalize_claim_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def extract_claim_dependencies(claim_text: str) -> list[int]:
    text = normalize_claim_text(claim_text)
    if not text: return []
    patterns = [
        r"\bclaims?\s+([0-9\s,;\-]+)",
        r"\b(?:claim|claims)\s+(?:number\s+)?([0-9\s,;\-]+)",
    ]
    found = set()
    for pat in patterns:
        for m in re.finditer(pat, text, re.I):
            for n in re.findall(r"\d+", m.group(1)):
                found.add(int(n))
    return sorted(found)

def identify_claim_type(claim_text: str) -> str:
    return "dependent" if extract_claim_dependencies(claim_text) else "independent"

def identify_claim_category(claim_text: str) -> str:
    text = normalize_claim_text(claim_text).lower()
    if re.search(r"\b(computer[- ]implemented|software|processor|machine learning|algorithm)\b", text): return "computer-implemented"
    if re.search(r"\b(method|process|step of)\b", text): return "method/process"
    if re.search(r"\b(system|apparatus|device|assembly|module)\b", text): return "apparatus/system/device"
    if re.search(r"\b(composition|formulation|mixture)\b", text): return "composition/formulation"
    if re.search(r"\b(kit|set)\b", text): return "kit"
    return "other"

def _split_limitations(text: str) -> list[str]:
    text = normalize_claim_text(text)
    if not text: return []
    # Preserve useful technical chunks while avoiding destructive sentence splitting.
    parts = re.split(r";\s*|\bwherein\b|\bconfigured to\b|\bcomprising\b", text, flags=re.I)
    out=[]
    for p in parts:
        p=re.sub(r"^(and|or)\s+", "", p.strip(), flags=re.I)
        if len(p) >= 8: out.append(p)
    return out

def extract_claim_elements(claim_text: str) -> list[str]:
    text = normalize_claim_text(claim_text)
    if not text: return []
    candidates=[]
    # Technical noun phrases after articles, plus explicit functional phrases.
    for m in re.finditer(r"\b(?:a|an|the|said)\s+([A-Za-z][A-Za-z0-9_/-]*(?:\s+[A-Za-z][A-Za-z0-9_/-]*){0,5})", text, re.I):
        phrase=m.group(1).strip(" ,.;:")
        words=phrase.split()
        while words and words[-1].lower() in _STOPWORDS: words.pop()
        phrase=" ".join(words)
        if phrase and phrase.lower() not in _GENERIC and len(phrase)>2: candidates.append(phrase)
    for part in _split_limitations(text):
        if any(k in part.lower() for k in ("configured to", "adapted to", "responsive to", "coupled to", "coupled with", "based on")):
            candidates.append(part)
    seen=set(); out=[]
    for x in candidates:
        k=re.sub(r"[^a-z0-9]+"," ",x.lower()).strip()
        if k and k not in seen:
            seen.add(k); out.append(x)
    return out[:75]

def extract_limitation_records(claim_text: str) -> list[dict[str, Any]]:
    text=normalize_claim_text(claim_text)
    if not text: return []
    records=[]
    for idx, part in enumerate(_split_limitations(text), 1):
        low=part.lower()
        kind="technical_element"
        if any(x in low for x in ("configured to", "adapted to", "operable to", "responsive to")): kind="functional"
        elif any(x in low for x in ("coupled", "connected", "between", "relative to")): kind="relationship"
        elif re.search(r"\bwherein\b|\bcomprising\b", low): kind="constraint"
        records.append({"id": f"L{idx}", "text": part, "type": kind, "search_terms": _keywords(part)})
    return records[:50]

def _keywords(text: str) -> list[str]:
    words=re.findall(r"[A-Za-z][A-Za-z0-9_-]{2,}", text.lower())
    out=[]
    for w in words:
        if w not in _STOPWORDS and w not in _GENERIC and w not in out: out.append(w)
    return out[:12]

def check_antecedent_basis(claim_text: str) -> list[dict[str, Any]]:
    text=normalize_claim_text(claim_text)
    introduced={x.lower() for x in re.findall(r"\b(?:a|an)\s+([A-Za-z][A-Za-z0-9_-]{2,50})", text, re.I)}
    issues=[]; seen=set()
    for term in re.findall(r"\b(?:the|said)\s+([A-Za-z][A-Za-z0-9_-]{2,50})", text, re.I):
        t=term.lower()
        if t in seen or t in _GENERIC: continue
        seen.add(t)
        if t not in introduced:
            issues.append({"type":"possible_antecedent_basis","term":term,"finding":f'The term "{term}" is used with definite wording but no earlier indefinite introduction was detected by this heuristic.',"severity":"MEDIUM"})
    return issues

def validate_claim_dependencies(claims: list[dict]) -> list[dict[str, Any]]:
    issues=[]; nums={c.get("number") for c in claims if c.get("number") is not None}
    for c in claims:
        n=c.get("number"); deps=extract_claim_dependencies(c.get("text", ""))
        for d in deps:
            if d not in nums: issues.append({"claim":n,"type":"missing_parent_claim","finding":f"Claim {n} refers to claim {d}, but that claim was not detected.","severity":"HIGH"})
            elif n is not None and d >= n: issues.append({"claim":n,"type":"claim_dependency_order","finding":f"Claim {n} refers to claim {d}, which does not precede it.","severity":"HIGH"})
    return issues

def analyze_single_claim(claim: dict) -> dict[str, Any]:
    text=normalize_claim_text(claim.get("text", "")); deps=extract_claim_dependencies(text); lim=extract_limitation_records(text)
    return {"claim_number":claim.get("number"),"claim_type":identify_claim_type(text),"category":identify_claim_category(text),"text":text,"dependencies":deps,"elements":extract_claim_elements(text),"limitations":lim,"limitation_count":len(lim),"antecedent_issues":check_antecedent_basis(text)}

def analyze_claims(claims: list[dict]) -> dict[str, Any]:
    if not claims:
        return {"claims":[],"issues":[{"type":"claims_not_detected","finding":"No claims were detected in the uploaded document.","severity":"CRITICAL"}],"statistics":{"total":0,"independent":0,"dependent":0,"limitations":0,"average_limitations":0}}
    analyzed=[analyze_single_claim(c) for c in claims]
    issues=validate_claim_dependencies(claims)
    for c in analyzed:
        issues.extend({"claim":c["claim_number"], **i} for i in c["antecedent_issues"])
    indep=sum(c["claim_type"]=="independent" for c in analyzed); dep=len(analyzed)-indep; lim=sum(c["limitation_count"] for c in analyzed)
    return {"claims":analyzed,"issues":issues,"statistics":{"total":len(analyzed),"independent":indep,"dependent":dep,"limitations":lim,"average_limitations":round(lim/len(analyzed),2)}}

def prepare_support_search(analyzed_claim: dict) -> list[str]:
    terms=list(analyzed_claim.get("elements", []))
    for lim in analyzed_claim.get("limitations", []): terms.extend(lim.get("search_terms", []))
    seen=set(); out=[]
    for t in terms:
        k=t.lower().strip()
        if k and k not in seen: seen.add(k); out.append(t)
    return out[:100]
