"""
Patent Intelligence Report Generator V3
========================================

Generates professional HTML and Markdown reports from the structured
analysis produced by the Indian Patent Analyzer.

Design principles
-----------------
1. Deterministic findings remain separate from AI interpretation.
2. Evidence is traceable through IDs.
3. No legal conclusion is invented by the report generator.
4. Reports include provenance and reproducibility information.
5. Output is suitable for conversion to PDF/DOCX later.

Version
-------
3.0.0
"""

from __future__ import annotations

import html
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional


REPORT_VERSION = "3.0.0"


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def _safe(value: Any) -> str:
    return html.escape(
        _clean(value)
    )


def _as_list(value: Any) -> List[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return value

    return [value]


def _get(
    data: Dict[str, Any],
    *keys: str,
    default: Any = None,
) -> Any:

    for key in keys:

        if key in data:
            return data[key]

    return default


def _json(
    value: Any,
    max_chars: int = 10000,
) -> str:

    try:

        text = json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    except Exception:

        text = str(value)

    if len(text) > max_chars:

        return (
            text[:max_chars]
            + "\n...[TRUNCATED]..."
        )

    return text


def _severity_class(
    severity: Any,
) -> str:

    value = _clean(severity).lower()

    if value in {
        "critical",
        "high",
        "medium",
        "low",
        "info",
        "review",
    }:
        return value

    return "review"


# ---------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------

@dataclass
class ReportSection:

    title: str
    content: str
    order: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ReportMetadata:

    report_id: str
    generated_at: str
    report_version: str
    analyzer_version: str
    document_name: str
    document_sha256: str
    analysis_id: str
    ai_model: str = ""
    ai_used: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------
# Report Generator
# ---------------------------------------------------------------------

class PatentReportGenerator:
    """
    Generate professional patent intelligence reports.
    """

    def __init__(
        self,
        analysis: Optional[Dict[str, Any]] = None,
    ):

        self.analysis = (
            analysis
            if isinstance(analysis, dict)
            else {}
        )

    # -----------------------------------------------------------------
    # Metadata
    # -----------------------------------------------------------------

    def build_metadata(
        self,
    ) -> ReportMetadata:

        provenance = _get(
            self.analysis,
            "provenance",
            default={},
        )

        if not isinstance(
            provenance,
            dict,
        ):
            provenance = {}

        document = _get(
            self.analysis,
            "document",
            default={},
        )

        if not isinstance(
            document,
            dict,
        ):
            document = {}

        report_id = _clean(
            _get(
                self.analysis,
                "report_id",
                "analysis_id",
                default="",
            )
        )

        if not report_id:
            report_id = (
                "RPT-"
                + datetime.now(
                    timezone.utc
                ).strftime(
                    "%Y%m%d%H%M%S"
                )
            )

        return ReportMetadata(
            report_id=report_id,
            generated_at=_utc_now(),
            report_version=REPORT_VERSION,
            analyzer_version=_clean(
                _get(
                    self.analysis,
                    "analyzer_version",
                    default=provenance.get(
                        "analyzer_version",
                        "",
                    ),
                )
            ),
            document_name=_clean(
                _get(
                    self.analysis,
                    "filename",
                    "document_name",
                    default=document.get(
                        "filename",
                        "",
                    ),
                )
            ),
            document_sha256=_clean(
                _get(
                    self.analysis,
                    "sha256",
                    "document_sha256",
                    default=document.get(
                        "sha256",
                        "",
                    ),
                )
            ),
            analysis_id=_clean(
                _get(
                    self.analysis,
                    "analysis_id",
                    default="",
                )
            ),
            ai_model=_clean(
                _get(
                    self.analysis,
                    "ai_model",
                    "model",
                    default="",
                )
            ),
            ai_used=bool(
                _get(
                    self.analysis,
                    "ai_used",
                    default=False,
                )
            ),
        )

    # -----------------------------------------------------------------
    # Executive summary
    # -----------------------------------------------------------------

    def executive_summary(
        self,
    ) -> str:

        summary = _get(
            self.analysis,
            "executive_summary",
            "summary",
            default="",
        )

        if summary:
            return _clean(summary)

        stats = _get(
            self.analysis,
            "statistics",
            "stats",
            default={},
        )

        if not isinstance(stats, dict):
            stats = {}

        claims = _as_list(
            _get(
                self.analysis,
                "claims",
                default=[],
            )
        )

        findings = _as_list(
            _get(
                self.analysis,
                "findings",
                "rule_findings",
                default=[],
            )
        )

        evidence = _as_list(
            _get(
                self.analysis,
                "evidence",
                "evidence_items",
                default=[],
            )
        )

        return (
            f"The analysis identified "
            f"{len(claims)} claim record(s), "
            f"{len(findings)} review finding(s), "
            f"and {len(evidence)} evidence item(s). "
            "The findings represent analytical signals requiring "
            "human verification and are not, by themselves, "
            "legal conclusions."
        )

    # -----------------------------------------------------------------
    # Document overview
    # -----------------------------------------------------------------

    def document_overview(
        self,
    ) -> Dict[str, Any]:

        metadata = self.build_metadata()

        stats = _get(
            self.analysis,
            "statistics",
            "stats",
            default={},
        )

        if not isinstance(stats, dict):
            stats = {}

        return {
            "Document": metadata.document_name,
            "SHA-256": metadata.document_sha256,
            "Analysis ID": metadata.analysis_id,
            "Analyzer Version": metadata.analyzer_version,
            "Report Version": metadata.report_version,
            "Pages": _get(
                stats,
                "pages",
                "page_count",
                default="",
            ),
            "Paragraphs": _get(
                stats,
                "paragraphs",
                "paragraph_count",
                default="",
            ),
            "Claims": _get(
                stats,
                "claims",
                "claim_count",
                default="",
            ),
        }

    # -----------------------------------------------------------------
    # Claims
    # -----------------------------------------------------------------

    def claims(
        self,
    ) -> List[Dict[str, Any]]:

        claims = _as_list(
            _get(
                self.analysis,
                "claims",
                default=[],
            )
        )

        result = []

        for index, claim in enumerate(
            claims,
            start=1,
        ):

            if not isinstance(
                claim,
                dict,
            ):
                claim = {
                    "text": str(claim)
                }

            result.append(
                {
                    "number": _get(
                        claim,
                        "claim_number",
                        "number",
                        default=index,
                    ),
                    "type": _get(
                        claim,
                        "claim_type",
                        "type",
                        default="",
                    ),
                    "category": _get(
                        claim,
                        "category",
                        "claim_category",
                        default="",
                    ),
                    "dependencies": _get(
                        claim,
                        "dependencies",
                        "depends_on",
                        default=[],
                    ),
                    "limitation_count": len(
                        _as_list(
                            _get(
                                claim,
                                "limitations",
                                default=[],
                            )
                        )
                    ),
                    "text": _get(
                        claim,
                        "text",
                        "claim_text",
                        default="",
                    ),
                }
            )

        return result

    # -----------------------------------------------------------------
    # Limitations
    # -----------------------------------------------------------------

    def claim_limitations(
        self,
    ) -> List[Dict[str, Any]]:

        output = []

        for claim in _as_list(
            _get(
                self.analysis,
                "claims",
                default=[],
            )
        ):

            if not isinstance(
                claim,
                dict,
            ):
                continue

            claim_number = _get(
                claim,
                "claim_number",
                "number",
                default="",
            )

            for limitation in _as_list(
                _get(
                    claim,
                    "limitations",
                    default=[],
                )
            ):

                if not isinstance(
                    limitation,
                    dict,
                ):
                    limitation = {
                        "text": str(limitation)
                    }

                output.append(
                    {
                        "claim": claim_number,
                        "limitation_id": _get(
                            limitation,
                            "id",
                            "limitation_id",
                            default="",
                        ),
                        "type": _get(
                            limitation,
                            "type",
                            "limitation_type",
                            default="",
                        ),
                        "text": _get(
                            limitation,
                            "text",
                            "limitation_text",
                            default="",
                        ),
                    }
                )

        return output

    # -----------------------------------------------------------------
    # Findings
    # -----------------------------------------------------------------

    def findings(
        self,
    ) -> List[Dict[str, Any]]:

        findings = _as_list(
            _get(
                self.analysis,
                "findings",
                "rule_findings",
                default=[],
            )
        )

        result = []

        for finding in findings:

            if not isinstance(
                finding,
                dict,
            ):
                continue

            result.append(
                {
                    "finding_id": _get(
                        finding,
                        "finding_id",
                        "id",
                        default="",
                    ),
                    "rule_id": _get(
                        finding,
                        "rule_id",
                        default="",
                    ),
                    "title": _get(
                        finding,
                        "title",
                        "name",
                        default="",
                    ),
                    "severity": _get(
                        finding,
                        "severity",
                        default="review",
                    ),
                    "confidence": _get(
                        finding,
                        "confidence",
                        default="",
                    ),
                    "claim": _get(
                        finding,
                        "claim_number",
                        "claim",
                        default="",
                    ),
                    "message": _get(
                        finding,
                        "message",
                        "description",
                        default="",
                    ),
                    "evidence": _get(
                        finding,
                        "evidence",
                        "evidence_ids",
                        default=[],
                    ),
                }
            )

        return result

    # -----------------------------------------------------------------
    # Prior art
    # -----------------------------------------------------------------

    def prior_art(
        self,
    ) -> List[Dict[str, Any]]:

        candidates = _as_list(
            _get(
                self.analysis,
                "prior_art",
                "prior_art_candidates",
                "candidates",
                default=[],
            )
        )

        result = []

        for candidate in candidates:

            if not isinstance(
                candidate,
                dict,
            ):
                continue

            result.append(
                {
                    "id": _get(
                        candidate,
                        "candidate_id",
                        "id",
                        default="",
                    ),
                    "title": _get(
                        candidate,
                        "title",
                        default="",
                    ),
                    "publication": _get(
                        candidate,
                        "publication_number",
                        "publication",
                        default="",
                    ),
                    "date": _get(
                        candidate,
                        "publication_date",
                        "date",
                        default="",
                    ),
                    "assignee": _get(
                        candidate,
                        "assignee",
                        "applicant",
                        default="",
                    ),
                    "score": _get(
                        candidate,
                        "relevance_score",
                        "score",
                        default="",
                    ),
                    "url": _get(
                        candidate,
                        "url",
                        "source_url",
                        default="",
                    ),
                }
            )

        return result

    # -----------------------------------------------------------------
    # Evidence
    # -----------------------------------------------------------------

    def evidence(
        self,
    ) -> List[Dict[str, Any]]:

        evidence = _as_list(
            _get(
                self.analysis,
                "evidence",
                "evidence_items",
                default=[],
            )
        )

        result = []

        for item in evidence:

            if not isinstance(
                item,
                dict,
            ):
                continue

            result.append(
                {
                    "evidence_id": _get(
                        item,
                        "evidence_id",
                        "id",
                        default="",
                    ),
                    "source": _get(
                        item,
                        "source",
                        "document",
                        default="",
                    ),
                    "page": _get(
                        item,
                        "page",
                        "page_number",
                        default="",
                    ),
                    "section": _get(
                        item,
                        "section",
                        default="",
                    ),
                    "text": _get(
                        item,
                        "text",
                        "content",
                        default="",
                    ),
                    "type": _get(
                        item,
                        "evidence_type",
                        "type",
                        default="",
                    ),
                }
            )

        return result

    # -----------------------------------------------------------------
    # AI interpretation
    # -----------------------------------------------------------------

    def ai_interpretation(
        self,
    ) -> str:

        ai = _get(
            self.analysis,
            "ai_analysis",
            "ai_interpretation",
            "ai_summary",
            default="",
        )

        if isinstance(
            ai,
            dict,
        ):

            return _clean(
                _get(
                    ai,
                    "text",
                    "summary",
                    "interpretation",
                    default="",
                )
            )

        return _clean(ai)

    # -----------------------------------------------------------------
    # Reproducibility
    # -----------------------------------------------------------------

    def provenance(
        self,
    ) -> Dict[str, Any]:

        metadata = self.build_metadata()

        provenance = _get(
            self.analysis,
            "provenance",
            default={},
        )

        if not isinstance(
            provenance,
            dict,
        ):
            provenance = {}

        result = dict(provenance)

        result.update(
            {
                "report_version": REPORT_VERSION,
                "report_generated_at": metadata.generated_at,
                "document_name": metadata.document_name,
                "document_sha256": metadata.document_sha256,
                "analysis_id": metadata.analysis_id,
            }
        )

        return result

    # -----------------------------------------------------------------
    # Markdown
    # -----------------------------------------------------------------

    def generate_markdown(
        self,
    ) -> str:

        metadata = self.build_metadata()

        lines = []

        lines.append(
            "# Patent Intelligence Analysis Report"
        )

        lines.append("")

        lines.append(
            f"**Report ID:** {metadata.report_id}"
        )

        lines.append(
            f"**Generated:** {metadata.generated_at}"
        )

        lines.append(
            f"**Document:** {metadata.document_name}"
        )

        lines.append(
            f"**SHA-256:** `{metadata.document_sha256}`"
        )

        lines.append("")

        lines.append(
            "## 1. Executive Summary"
        )

        lines.append("")

        lines.append(
            self.executive_summary()
        )

        lines.append("")

        # -------------------------------------------------------------
        # Document overview
        # -------------------------------------------------------------

        lines.append(
            "## 2. Document Overview"
        )

        lines.append("")

        for key, value in (
            self.document_overview()
        ).items():

            lines.append(
                f"- **{key}:** {value}"
            )

        lines.append("")

        # -------------------------------------------------------------
        # Claims
        # -------------------------------------------------------------

        lines.append(
            "## 3. Claim Structure"
        )

        lines.append("")

        for claim in self.claims():

            lines.append(
                f"### Claim {claim['number']}"
            )

            lines.append("")

            lines.append(
                f"- **Type:** {claim['type']}"
            )

            lines.append(
                f"- **Category:** {claim['category']}"
            )

            lines.append(
                f"- **Dependencies:** "
                f"{claim['dependencies']}"
            )

            lines.append(
                f"- **Limitations:** "
                f"{claim['limitation_count']}"
            )

            if claim["text"]:
                lines.append("")
                lines.append(
                    f"> {claim['text']}"
                )

            lines.append("")

        # -------------------------------------------------------------
        # Limitations
        # -------------------------------------------------------------

        limitations = (
            self.claim_limitations()
        )

        if limitations:

            lines.append(
                "## 4. Claim Limitations"
            )

            lines.append("")

            for item in limitations:

                lines.append(
                    f"- **{item['limitation_id']}** "
                    f"(Claim {item['claim']}, "
                    f"{item['type']}): "
                    f"{item['text']}"
                )

            lines.append("")

        # -------------------------------------------------------------
        # Findings
        # -------------------------------------------------------------

        lines.append(
            "## 5. Rule-Based Findings"
        )

        lines.append("")

        findings = self.findings()

        if not findings:

            lines.append(
                "No rule-based findings were recorded."
            )

        else:

            for finding in findings:

                lines.append(
                    f"### {finding['title']}"
                )

                lines.append("")

                lines.append(
                    f"- **Finding ID:** "
                    f"{finding['finding_id']}"
                )

                lines.append(
                    f"- **Rule:** "
                    f"{finding['rule_id']}"
                )

                lines.append(
                    f"- **Severity:** "
                    f"{finding['severity']}"
                )

                lines.append(
                    f"- **Confidence:** "
                    f"{finding['confidence']}"
                )

                lines.append("")

                lines.append(
                    finding["message"]
                )

                lines.append("")

        # -------------------------------------------------------------
        # Prior art
        # -------------------------------------------------------------

        lines.append(
            "## 6. Prior-Art Research"
        )

        lines.append("")

        candidates = self.prior_art()

        if not candidates:

            lines.append(
                "No prior-art candidates were recorded."
            )

        else:

            for candidate in candidates:

                lines.append(
                    f"### {candidate['title']}"
                )

                lines.append("")

                lines.append(
                    f"- **Publication:** "
                    f"{candidate['publication']}"
                )

                lines.append(
                    f"- **Date:** "
                    f"{candidate['date']}"
                )

                lines.append(
                    f"- **Assignee:** "
                    f"{candidate['assignee']}"
                )

                lines.append(
                    f"- **Relevance score:** "
                    f"{candidate['score']}"
                )

                if candidate["url"]:

                    lines.append(
                        f"- **Source:** "
                        f"{candidate['url']}"
                    )

                lines.append("")

        # -------------------------------------------------------------
        # Evidence
        # -------------------------------------------------------------

        lines.append(
            "## 7. Evidence"
        )

        lines.append("")

        evidence = self.evidence()

        if not evidence:

            lines.append(
                "No evidence items were recorded."
            )

        else:

            for item in evidence:

                lines.append(
                    f"### {item['evidence_id']}"
                )

                lines.append("")

                lines.append(
                    f"- **Source:** "
                    f"{item['source']}"
                )

                lines.append(
                    f"- **Page:** "
                    f"{item['page']}"
                )

                lines.append(
                    f"- **Section:** "
                    f"{item['section']}"
                )

                lines.append("")

                lines.append(
                    f"> {item['text']}"
                )

                lines.append("")

        # -------------------------------------------------------------
        # AI
        # -------------------------------------------------------------

        ai_text = self.ai_interpretation()

        if ai_text:

            lines.append(
                "## 8. AI-Assisted Interpretation"
            )

            lines.append("")

            lines.append(ai_text)

            lines.append("")

        # -------------------------------------------------------------
        # Provenance
        # -------------------------------------------------------------

        lines.append(
            "## 9. Reproducibility & Provenance"
        )

        lines.append("")

        lines.append(
            "```json"
        )

        lines.append(
            _json(
                self.provenance(),
                max_chars=15000,
            )
        )

        lines.append(
            "```"
        )

        lines.append("")

        lines.append(
            "## Important Review Notice"
        )

        lines.append("")

        lines.append(
            "This report is an analytical and evidence-management "
            "artifact. Automated findings, AI interpretations, "
            "similarity results, and review signals should be "
            "verified by a qualified patent professional before "
            "being relied upon for prosecution, validity, "
            "enforcement, licensing, or other legal decisions."
        )

        return "\n".join(lines)

    # -----------------------------------------------------------------
    # HTML
    # -----------------------------------------------------------------

    def generate_html(
        self,
    ) -> str:

        metadata = self.build_metadata()

        html_parts = []

        html_parts.append(
            """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport"
      content="width=device-width, initial-scale=1.0">

<title>Patent Intelligence Analysis Report</title>

<style>

body {
    font-family: Arial, Helvetica, sans-serif;
    margin: 0;
    padding: 0;
    background: #f4f6f8;
    color: #1f2937;
    line-height: 1.55;
}

.container {
    max-width: 1100px;
    margin: 40px auto;
    padding: 0 24px;
}

.header {
    background: #111827;
    color: white;
    padding: 32px;
    border-radius: 12px;
    margin-bottom: 24px;
}

.header h1 {
    margin-top: 0;
    font-size: 30px;
}

.card {
    background: white;
    padding: 24px;
    margin-bottom: 20px;
    border-radius: 10px;
    box-shadow:
        0 2px 8px rgba(0,0,0,0.06);
}

h2 {
    border-bottom: 2px solid #e5e7eb;
    padding-bottom: 8px;
}

h3 {
    margin-top: 24px;
}

.meta-grid {
    display: grid;
    grid-template-columns:
        repeat(auto-fit, minmax(220px, 1fr));
    gap: 12px;
}

.meta {
    background: #f9fafb;
    padding: 12px;
    border-radius: 8px;
}

.meta strong {
    display: block;
    font-size: 12px;
    color: #6b7280;
    text-transform: uppercase;
}

table {
    width: 100%;
    border-collapse: collapse;
    margin-top: 12px;
}

th,
td {
    border: 1px solid #e5e7eb;
    padding: 10px;
    text-align: left;
    vertical-align: top;
}

th {
    background: #f9fafb;
}

.severity {
    font-weight: bold;
    text-transform: uppercase;
}

.severity.critical {
    color: #991b1b;
}

.severity.high {
    color: #b45309;
}

.severity.medium {
    color: #92400e;
}

.severity.low {
    color: #166534;
}

.severity.info {
    color: #1d4ed8;
}

.severity.review {
    color: #6b21a8;
}

.evidence {
    background: #f9fafb;
    border-left: 4px solid #6b7280;
    padding: 12px;
    margin: 10px 0;
}

.notice {
    background: #fff7ed;
    border-left: 4px solid #f97316;
    padding: 16px;
    margin-top: 20px;
}

code {
    word-break: break-word;
}

.footer {
    color: #6b7280;
    font-size: 12px;
    text-align: center;
    margin: 30px 0;
}

</style>
</head>

<body>
<div class="container">
"""
        )

        # Header

        html_parts.append(
            '<div class="header">'
        )

        html_parts.append(
            "<h1>Patent Intelligence Analysis Report</h1>"
        )

        html_parts.append(
            f"<div>Report ID: "
            f"{_safe(metadata.report_id)}</div>"
        )

        html_parts.append(
            f"<div>Generated: "
            f"{_safe(metadata.generated_at)}</div>"
        )

        html_parts.append(
            "</div>"
        )

        # Overview

        html_parts.append(
            '<div class="card">'
            '<h2>Document Overview</h2>'
            '<div class="meta-grid">'
        )

        for key, value in (
            self.document_overview()
        ).items():

            html_parts.append(
                f"""
<div class="meta">
<strong>{_safe(key)}</strong>
<div>{_safe(value)}</div>
</div>
"""
            )

        html_parts.append(
            "</div></div>"
        )

        # Executive Summary

        html_parts.append(
            '<div class="card">'
            '<h2>Executive Summary</h2>'
        )

        html_parts.append(
            f"<p>{_safe(self.executive_summary())}</p>"
        )

        html_parts.append(
            "</div>"
        )

        # Claims

        html_parts.append(
            '<div class="card">'
            '<h2>Claim Structure</h2>'
        )

        claims = self.claims()

        if claims:

            html_parts.append(
                """
<table>
<tr>
<th>Claim</th>
<th>Type</th>
<th>Category</th>
<th>Dependencies</th>
<th>Limitations</th>
</tr>
"""
            )

            for claim in claims:

                html_parts.append(
                    f"""
<tr>
<td>{_safe(claim["number"])}</td>
<td>{_safe(claim["type"])}</td>
<td>{_safe(claim["category"])}</td>
<td>{_safe(claim["dependencies"])}</td>
<td>{_safe(claim["limitation_count"])}</td>
</tr>
"""
                )

            html_parts.append(
                "</table>"
            )

        else:

            html_parts.append(
                "<p>No claims recorded.</p>"
            )

        html_parts.append(
            "</div>"
        )

        # Findings

        html_parts.append(
            '<div class="card">'
            '<h2>Rule-Based Findings</h2>'
        )

        findings = self.findings()

        if findings:

            html_parts.append(
                """
<table>
<tr>
<th>Finding</th>
<th>Rule</th>
<th>Severity</th>
<th>Confidence</th>
<th>Message</th>
</tr>
"""
            )

            for finding in findings:

                severity = _severity_class(
                    finding["severity"]
                )

                html_parts.append(
                    f"""
<tr>
<td>{_safe(finding["finding_id"])}</td>
<td>{_safe(finding["rule_id"])}</td>
<td>
<span class="severity {severity}">
{_safe(finding["severity"])}
</span>
</td>
<td>{_safe(finding["confidence"])}</td>
<td>{_safe(finding["message"])}</td>
</tr>
"""
                )

            html_parts.append(
                "</table>"
            )

        else:

            html_parts.append(
                "<p>No rule-based findings recorded.</p>"
            )

        html_parts.append(
            "</div>"
        )

        # Prior art

        html_parts.append(
            '<div class="card">'
            '<h2>Prior-Art Research</h2>'
        )

        candidates = self.prior_art()

        if candidates:

            html_parts.append(
                """
<table>
<tr>
<th>Title</th>
<th>Publication</th>
<th>Date</th>
<th>Assignee</th>
<th>Score</th>
</tr>
"""
            )

            for candidate in candidates:

                title = _safe(
                    candidate["title"]
                )

                if candidate["url"]:

                    title = (
                        f'<a href="'
                        f'{_safe(candidate["url"])}'
                        f'" target="_blank">'
                        f'{title}</a>'
                    )

                html_parts.append(
                    f"""
<tr>
<td>{title}</td>
<td>{_safe(candidate["publication"])}</td>
<td>{_safe(candidate["date"])}</td>
<td>{_safe(candidate["assignee"])}</td>
<td>{_safe(candidate["score"])}</td>
</tr>
"""
                )

            html_parts.append(
                "</table>"
            )

        else:

            html_parts.append(
                "<p>No prior-art candidates recorded.</p>"
            )

        html_parts.append(
            "</div>"
        )

        # Evidence

        html_parts.append(
            '<div class="card">'
            '<h2>Evidence</h2>'
        )

        evidence = self.evidence()

        if evidence:

            for item in evidence:

                html_parts.append(
                    f"""
<div class="evidence">
<strong>
{_safe(item["evidence_id"])}
</strong>

<br>

Source:
{_safe(item["source"])}

<br>

Page:
{_safe(item["page"])}

<br>

Section:
{_safe(item["section"])}

<p>
{_safe(item["text"])}
</p>

</div>
"""
                )

        else:

            html_parts.append(
                "<p>No evidence recorded.</p>"
            )

        html_parts.append(
            "</div>"
        )

        # AI

        ai_text = self.ai_interpretation()

        if ai_text:

            html_parts.append(
                '<div class="card">'
                '<h2>AI-Assisted Interpretation</h2>'
            )

            html_parts.append(
                f"<p>{_safe(ai_text)}</p>"
            )

            html_parts.append(
                "</div>"
            )

        # Provenance

        html_parts.append(
            '<div class="card">'
            '<h2>Reproducibility &amp; Provenance</h2>'
        )

        html_parts.append(
            "<pre>"
            + _safe(
                _json(
                    self.provenance(),
                    max_chars=20000,
                )
            )
            + "</pre>"
        )

        html_parts.append(
            "</div>"
        )

        # Notice

        html_parts.append(
            """
<div class="card">
<div class="notice">

<strong>Important Review Notice</strong>

<p>
This report is an analytical and evidence-management artifact.
Automated findings, AI interpretations, similarity results and
review signals should be verified by a qualified patent
professional before being relied upon for prosecution, validity,
enforcement, licensing, or other legal decisions.
</p>

</div>
</div>
"""
        )

        html_parts.append(
            """
<div class="footer">
Indian Patent Analyzer —
Report Generator V3
</div>

</div>
</body>
</html>
"""
        )

        return "".join(html_parts)

    # -----------------------------------------------------------------
    # File output
    # -----------------------------------------------------------------

    def save_markdown(
        self,
        path: str | Path,
    ) -> str:

        output = Path(path)

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output.write_text(
            self.generate_markdown(),
            encoding="utf-8",
        )

        return str(output)

    def save_html(
        self,
        path: str | Path,
    ) -> str:

        output = Path(path)

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output.write_text(
            self.generate_html(),
            encoding="utf-8",
        )

        return str(output)


# ---------------------------------------------------------------------
# Backward-compatible functions
# ---------------------------------------------------------------------

def generate_report(
    analysis: Dict[str, Any],
    format: str = "markdown",
) -> str:

    generator = PatentReportGenerator(
        analysis
    )

    format = _clean(format).lower()

    if format in {
        "html",
        "htm",
    }:

        return generator.generate_html()

    return generator.generate_markdown()


def create_report(
    analysis: Dict[str, Any],
    output_path: Optional[str] = None,
    format: str = "markdown",
) -> str:

    generator = PatentReportGenerator(
        analysis
    )

    format = _clean(format).lower()

    if format in {
        "html",
        "htm",
    }:

        content = generator.generate_html()

    else:

        content = generator.generate_markdown()

    if output_path:

        output = Path(output_path)

        output.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        output.write_text(
            content,
            encoding="utf-8",
        )

    return content


def export_report(
    analysis: Dict[str, Any],
    output_path: str,
) -> str:

    suffix = Path(
        output_path
    ).suffix.lower()

    if suffix in {
        ".html",
        ".htm",
    }:

        return create_report(
            analysis,
            output_path=output_path,
            format="html",
        )

    return create_report(
        analysis,
        output_path=output_path,
        format="markdown",
    )


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

__all__ = [
    "REPORT_VERSION",
    "ReportSection",
    "ReportMetadata",
    "PatentReportGenerator",
    "generate_report",
    "create_report",
    "export_report",
]
