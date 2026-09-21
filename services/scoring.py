
"""Transparent, evidence-based draft quality scoring.

Scores are internal workflow indicators, not legal or patentability scores.
"""
from typing import Dict,Any

def score_analysis(rule: Dict[str,Any], claims: Dict[str,Any], gemini: Dict[str,Any]) -> Dict[str,Any]:
    sections=rule.get("sections",{})
    present=sum(1 for v in sections.values() if isinstance(v,dict) and v.get("present"))
    total=max(len(sections),1)
    section_score=round(100*present/total)
    claim_list=claims.get("claims",[])
    claim_score=100 if claim_list else 25
    issues=rule.get("issues",[]) or []
    penalties=sum({"critical":25,"high":15,"medium":7,"low":2}.get(str(i.get("severity","")).lower(),0) for i in issues if isinstance(i,dict))
    form=max(0,min(100,section_score-penalties))
    overall=round(form*.35+claim_score*.35+section_score*.15+max(0,100-penalties)*.15)
    return {"form_structure":form,"claim_structure":claim_score,"document_completeness":section_score,"overall_readiness":overall,
            "methodology":"Transparent heuristic from deterministic checks; not a legal/patentability opinion."}
