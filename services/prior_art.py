
"""Prior-art discovery helpers.

The application does not assert novelty or infringement. It creates
high-signal search queries and safe external search links for analyst review.
"""
from urllib.parse import quote_plus
import re
from typing import List, Dict

def invention_keywords(title: str, abstract: str, claims: List[Dict]) -> List[str]:
    text=" ".join([title or "", abstract or ""]+[c.get("claim_text","") for c in claims[:3]])
    words=re.findall(r"[A-Za-z][A-Za-z0-9-]{3,}",text.lower())
    stop=set("the and for with from that this invention method system device apparatus comprising wherein using".split())
    freq={}
    for w in words:
        if w not in stop: freq[w]=freq.get(w,0)+1
    return [w for w,_ in sorted(freq.items(),key=lambda x:(-x[1],x[0]))[:12]]

def build_queries(title: str, abstract: str, claims: List[Dict]) -> List[str]:
    kw=invention_keywords(title,abstract,claims)
    queries=[]
    if title: queries.append(title)
    if len(kw)>=4: queries.append(" ".join(kw[:6]))
    if claims:
        q=re.sub(r"\s+"," ",claims[0].get("claim_text",""))
        queries.append(" ".join(q.split()[:18]))
    return list(dict.fromkeys(q for q in queries if q.strip()))

def links(query: str) -> Dict[str,str]:
    q=quote_plus(query)
    return {
        "Google Patents":f"https://patents.google.com/?q={q}",
        "Espacenet":f"https://worldwide.espacenet.com/patent/search?q={q}",
        "WIPO PATENTSCOPE":f"https://patentscope.wipo.int/search/en/result.jsf?query={q}",
    }
