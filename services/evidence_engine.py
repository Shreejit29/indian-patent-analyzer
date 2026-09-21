"""V3 evidence and provenance engine for Indian Patent Analyzer.

Evidence-first, deterministic and auditable. It does not make legal conclusions.
"""
from __future__ import annotations
import hashlib, re
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Iterable

STOPWORDS = set("""a an the and or of to in for with on by from is are was were be been being
this that which as at into than then there their its it we our your said such may can
could should would using used use based comprising including where when through between
within without having provided configured thereof therein said one two three""".split())


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _tokens(text: str) -> List[str]:
    return [t for t in re.findall(r"[A-Za-z][A-Za-z0-9-]{2,}", (text or "").lower()) if t not in STOPWORDS]


def terms(text: str) -> List[str]:
    """Backward-compatible public token extractor."""
    return _tokens(text)


def paragraphs(text: str) -> List[Dict[str, Any]]:
    text = text or ""
    blocks: List[Dict[str, Any]] = []
    cursor = 0
    for raw in re.split(r"\n\s*\n+", text):
        clean = raw.strip()
        if not clean:
            cursor += len(raw)
            continue
        start = text.find(clean, cursor)
        blocks.append({"id": len(blocks) + 1, "text": clean,
                       "start": start, "end": start + len(clean)})
        cursor = start + len(clean)
    return blocks


def sentences(text: str) -> List[str]:
    return [s.strip() for s in re.split(r"(?<=[.!?])\s+", normalize_text(text)) if s.strip()]


def _similarity(query: str, candidate: str) -> float:
    q = Counter(_tokens(query)); c = Counter(_tokens(candidate))
    if not q: return 0.0
    overlap = sum(min(q[k], c[k]) for k in q)
    # Weighted lexical coverage; capped for deterministic interpretability.
    return min(1.0, overlap / max(1, sum(q.values())))


def sentence_evidence(query: str, text: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Return ranked sentence-level evidence with stable IDs and offsets."""
    if not normalize_text(query): return []
    out = []
    for i, s in enumerate(sentences(text), 1):
        score = _similarity(query, s)
        if score > 0:
            out.append({"sentence_id": i, "score": round(score, 4), "text": s})
    return sorted(out, key=lambda x: (-x["score"], x["sentence_id"]))[:top_k]


def claim_element_extraction(claim: str) -> List[str]:
    """Conservative limitation extraction retained for backward compatibility."""
    x = re.sub(r"\s+", " ", claim or "").strip()
    x = re.sub(r"^\d+\s*[.)]\s*", "", x)
    parts = re.split(r";|\bcomprising\b|\bwherein\b|\bconfigured to\b|\badapted to\b|\bcharacterized by\b", x, flags=re.I)
    return [p.strip(" ,:") for p in parts if len(p.strip().split()) >= 2][:40]


def evidence_record(query: str, text: str, source_type: str = "specification", source_id: str = "") -> Dict[str, Any]:
    matches = sentence_evidence(query, text, 5)
    return {
        "query": query,
        "source_type": source_type,
        "source_id": source_id,
        "matches": matches,
        "confidence": confidence_from_evidence(matches),
        "evidence_found": bool(matches),
    }


def claim_support_map(claims: List[Dict[str, Any]], specification: str) -> List[Dict[str, Any]]:
    result = []
    for c in claims or []:
        num = c.get("claim_number")
        text = c.get("claim_text", c.get("text", ""))
        elements = c.get("limitations") or c.get("elements") or claim_element_extraction(text)
        mapped = []
        for idx, element in enumerate(elements, 1):
            if isinstance(element, dict):
                element_text = element.get("text", element.get("element", ""))
                element_id = element.get("id", f"L{idx}")
            else:
                element_text, element_id = str(element), f"L{idx}"
            ev = sentence_evidence(element_text, specification, 3)
            top = ev[0]["score"] if ev else 0.0
            mapped.append({
                "id": element_id,
                "element": element_text,
                "status": "CLEAR_SUPPORT" if top >= .65 else ("POSSIBLE_SUPPORT" if ev else "NO_CLEAR_SUPPORT"),
                "confidence": confidence_from_evidence(ev),
                "evidence": ev,
            })
        result.append({"claim_number": num, "elements": mapped})
    return result


def document_fingerprint(text: str) -> Dict[str, str]:
    raw = text or ""
    clean = normalize_text(raw).lower()
    return {
        "sha256": hashlib.sha256(clean.encode("utf-8")).hexdigest(),
        "characters": str(len(raw)),
        "normalized_characters": str(len(clean)),
    }


def provenance(text: str, *, analyzer_version: str = "3.0.0", source_name: str = "") -> Dict[str, Any]:
    fp = document_fingerprint(text)
    return {
        "analysis_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "analyzer_version": analyzer_version,
        "source_name": source_name,
        "document_sha256": fp["sha256"],
        "document_characters": int(fp["characters"]),
    }


def detect_risk_signals(text: str, claims: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    low = (text or "").lower()
    if not re.search(r"\bdetailed description\b|\bdetailed disclosure\b", low):
        findings.append({"code": "MISSING_DETAILED_DISCLOSURE", "severity": "HIGH",
                         "message": "No detailed-description heading was detected; verify document structure."})
    if re.search(r"\b(?:best|excellent|superior|significantly improved)\b", text or "", re.I):
        findings.append({"code": "RESULT_ONLY_LANGUAGE", "severity": "LOW",
                         "message": "Promotional/result-only language may merit technical substantiation."})
    for c in claims or []:
        ct = c.get("claim_text", c.get("text", ""))
        if len(ct.split()) > 180:
            findings.append({"code": "LONG_CLAIM", "severity": "MEDIUM", "claim_number": c.get("claim_number"),
                             "message": "Claim is unusually long; review claim structure and conciseness."})
    return findings


def confidence_from_evidence(evidence: Iterable[Dict[str, Any]]) -> str:
    evidence = list(evidence or [])
    if not evidence: return "LOW"
    s = float(evidence[0].get("score", 0))
    return "HIGH" if s >= .65 else ("MEDIUM" if s >= .35 else "LOW")
