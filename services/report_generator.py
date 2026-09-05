from datetime import datetime
from typing import Any


def _safe(value: Any, default: str = "Not available") -> str:
    """Return a readable string for missing values."""
    if value is None or value == "":
        return default
    return str(value)


def _severity_icon(severity: str) -> str:
    """Return a simple icon for issue severity."""
    severity = severity.lower()

    if severity == "critical":
        return "🔴"
    if severity == "high":
        return "🟠"
    if severity == "medium":
        return "🟡"
    if severity == "low":
        return "🟢"

    return "⚪"


def _format_list(items: Any) -> str:
    """Format a list as Markdown bullets."""
    if not items:
        return "- None identified"

    if isinstance(items, str):
        return f"- {items}"

    return "\n".join(f"- {item}" for item in items)


def generate_markdown_report(
    analysis: dict,
    document_name: str = "Patent Document",
) -> str:
    """
    Generate a human-readable Markdown report from structured patent analysis.

    Parameters
    ----------
    analysis:
        Structured analysis dictionary returned by the analyzer.
    document_name:
        Name of the analyzed document.

    Returns
    -------
    str
        Markdown-formatted report.
    """

    assessment = analysis.get("document_assessment", {})
    scores = analysis.get("scores", {})
    sections = analysis.get("sections", {})
    issues = analysis.get("issues", [])
    claims = analysis.get("claims", [])
    abstract = analysis.get("abstract_analysis", {})
    reference_numbers = analysis.get("reference_numeral_analysis", {})
    recommendations = analysis.get("recommendations", [])
    sources = analysis.get("sources", [])
    disclaimer = analysis.get(
        "disclaimer",
        "This report is an AI-assisted preliminary analysis and is not legal advice.",
    )

    report = []

    # ---------------------------------------------------------
    # HEADER
    # ---------------------------------------------------------

    report.append("# Indian Patent Draft Analysis Report")
    report.append("")

    report.append(f"**Document:** {_safe(document_name)}")
    report.append(
        f"**Analysis Date:** {datetime.now().strftime('%d %B %Y, %H:%M')}"
    )
    report.append("")

    report.append("---")
    report.append("")

    # ---------------------------------------------------------
    # EXECUTIVE SUMMARY
    # ---------------------------------------------------------

    report.append("## 1. Executive Summary")
    report.append("")

    report.append(
        f"**Overall Assessment:** {_safe(assessment.get('overall_assessment'))}"
    )
    report.append("")

    report.append(
        f"**Document Type:** {_safe(assessment.get('document_type'))}"
    )
    report.append("")

    if assessment.get("summary"):
        report.append("### Summary")
        report.append("")
        report.append(str(assessment["summary"]))
        report.append("")

    # ---------------------------------------------------------
    # SCORES
    # ---------------------------------------------------------

    report.append("## 2. Analysis Scores")
    report.append("")

    if scores:
        report.append("| Area | Score |")
        report.append("|---|---:|")

        for name, score in scores.items():
            report.append(f"| {name.replace('_', ' ').title()} | {score}/100 |")

        report.append("")
        report.append(
            "> Scores are AI-generated indicators for drafting review only. "
            "They are not official Indian Patent Office scores."
        )
        report.append("")
    else:
        report.append("No scores were provided.")
        report.append("")

    # ---------------------------------------------------------
    # DOCUMENT STRUCTURE
    # ---------------------------------------------------------

    report.append("## 3. Document Structure")
    report.append("")

    if sections:
        report.append("| Section | Status |")
        report.append("|---|---|")

        for section, status in sections.items():
            if isinstance(status, bool):
                status_text = "Present" if status else "Missing"
            else:
                status_text = _safe(status)

            report.append(
                f"| {section.replace('_', ' ').title()} | {status_text} |"
            )

        report.append("")
    else:
        report.append("No section analysis available.")
        report.append("")

    # ---------------------------------------------------------
    # ISSUES
    # ---------------------------------------------------------

    report.append("## 4. Identified Issues")
    report.append("")

    if not issues:
        report.append("No issues were identified by the analysis.")
        report.append("")
    else:
        for index, issue in enumerate(issues, start=1):

            if isinstance(issue, str):
                report.append(f"### {index}. {issue}")
                report.append("")
                continue

            title = _safe(
                issue.get("title"),
                issue.get("issue", f"Issue {index}"),
            )

            severity = _safe(issue.get("severity"), "Unknown")
            category = _safe(issue.get("category"), "General")
            confidence = _safe(issue.get("confidence"), "Not specified")

            report.append(
                f"### {index}. {_severity_icon(severity)} {title}"
            )
            report.append("")

            report.append(f"**Category:** {category}")
            report.append("")

            report.append(f"**Severity:** {severity}")
            report.append("")

            report.append(f"**Confidence:** {confidence}")
            report.append("")

            if issue.get("type"):
                report.append(f"**Type:** {issue['type']}")
                report.append("")

            if issue.get("evidence"):
                report.append("**Evidence:**")
                report.append("")
                report.append(str(issue["evidence"]))
                report.append("")

            if issue.get("explanation"):
                report.append("**Explanation:**")
                report.append("")
                report.append(str(issue["explanation"]))
                report.append("")

            if issue.get("recommendation"):
                report.append("**Recommended Action:**")
                report.append("")
                report.append(str(issue["recommendation"]))
                report.append("")

    # ---------------------------------------------------------
    # CLAIM ANALYSIS
    # ---------------------------------------------------------

    report.append("## 5. Claim Analysis")
    report.append("")

    if not claims:
        report.append("No claim analysis was provided.")
        report.append("")
    else:

        for index, claim in enumerate(claims, start=1):

            if isinstance(claim, str):
                report.append(f"### Claim {index}")
                report.append("")
                report.append(claim)
                report.append("")
                continue

            claim_number = claim.get("claim_number", index)

            report.append(f"### Claim {claim_number}")
            report.append("")

            if claim.get("claim_type"):
                report.append(
                    f"**Claim Type:** {_safe(claim.get('claim_type'))}"
                )
                report.append("")

            if claim.get("category"):
                report.append(
                    f"**Category:** {_safe(claim.get('category'))}"
                )
                report.append("")

            if claim.get("dependency"):
                report.append(
                    f"**Dependency:** {_safe(claim.get('dependency'))}"
                )
                report.append("")

            if claim.get("assessment"):
                report.append("**Assessment:**")
                report.append("")
                report.append(str(claim["assessment"]))
                report.append("")

            if claim.get("issues"):
                report.append("**Issues:**")
                report.append("")
                report.append(_format_list(claim["issues"]))
                report.append("")

            if claim.get("recommendations"):
                report.append("**Recommendations:**")
                report.append("")
                report.append(_format_list(claim["recommendations"]))
                report.append("")

    # ---------------------------------------------------------
    # ABSTRACT
    # ---------------------------------------------------------

    report.append("## 6. Abstract Analysis")
    report.append("")

    if abstract:

        if abstract.get("assessment"):
            report.append("### Assessment")
            report.append("")
            report.append(str(abstract["assessment"]))
            report.append("")

        if abstract.get("word_count") is not None:
            report.append(
                f"**Word Count:** {abstract.get('word_count')}"
            )
            report.append("")

        if abstract.get("issues"):
            report.append("### Issues")
            report.append("")
            report.append(_format_list(abstract["issues"]))
            report.append("")

        if abstract.get("recommendations"):
            report.append("### Recommendations")
            report.append("")
            report.append(_format_list(abstract["recommendations"]))
            report.append("")

    else:
        report.append("No abstract analysis was provided.")
        report.append("")

    # ---------------------------------------------------------
    # REFERENCE NUMERALS
    # ---------------------------------------------------------

    report.append("## 7. Reference Numeral Analysis")
    report.append("")

    if reference_numbers:

        if reference_numbers.get("assessment"):
            report.append(str(reference_numbers["assessment"]))
            report.append("")

        if reference_numbers.get("missing"):
            report.append("### Missing or Potentially Missing References")
            report.append("")
            report.append(_format_list(reference_numbers["missing"]))
            report.append("")

        if reference_numbers.get("unused"):
            report.append("### Unused Reference Numerals")
            report.append("")
            report.append(_format_list(reference_numbers["unused"]))
            report.append("")

    else:
        report.append("No reference numeral analysis was provided.")
        report.append("")

    # ---------------------------------------------------------
    # RECOMMENDATIONS
    # ---------------------------------------------------------

    report.append("## 8. Recommended Actions")
    report.append("")

    if recommendations:
        for index, recommendation in enumerate(recommendations, start=1):

            if isinstance(recommendation, str):
                report.append(f"{index}. {recommendation}")
                continue

            title = _safe(
                recommendation.get("title"),
                f"Recommendation {index}",
            )

            priority = _safe(
                recommendation.get("priority"),
                "Normal",
            )

            report.append(
                f"### {index}. {title}"
            )
            report.append("")
            report.append(f"**Priority:** {priority}")
            report.append("")

            if recommendation.get("action"):
                report.append(str(recommendation["action"]))
                report.append("")

            if recommendation.get("reason"):
                report.append(f"**Reason:** {recommendation['reason']}")
                report.append("")

    else:
        report.append("No recommendations were provided.")
        report.append("")

    # ---------------------------------------------------------
    # SOURCES
    # ---------------------------------------------------------

    report.append("## 9. Sources and Rule References")
    report.append("")

    if sources:

        for source in sources:

            if isinstance(source, str):
                report.append(f"- {source}")
                continue

            name = _safe(source.get("name"), "Source")
            reference = source.get("reference")
            authority = source.get("authority")

            if reference:
                report.append(f"- **{name}** — {reference}")
            else:
                report.append(f"- **{name}**")

            if authority:
                report.append(f"  - Authority: {authority}")

    else:
        report.append(
            "No external sources were returned by the analysis."
        )

    report.append("")

    # ---------------------------------------------------------
    # DISCLAIMER
    # ---------------------------------------------------------

    report.append("---")
    report.append("")
    report.append("## 10. Disclaimer")
    report.append("")
    report.append(str(disclaimer))
    report.append("")

    report.append(
        "The analysis should be reviewed against the current Indian Patent "
        "Act, Patents Rules, applicable official guidelines/manuals, and the "
        "actual patent record before making filing or prosecution decisions."
    )
    report.append("")

    return "\n".join(report)


def generate_text_report(
    analysis: dict,
    document_name: str = "Patent Document",
) -> str:
    """
    Generate a plain-text version of the report.

    This is useful for simple downloads, logs, or future integrations.
    """

    markdown_report = generate_markdown_report(
        analysis=analysis,
        document_name=document_name,
    )

    # Basic Markdown-to-text conversion.
    text = markdown_report

    replacements = {
        "# ": "",
        "## ": "",
        "### ": "",
        "**": "",
        "---": "",
        "🔴": "[CRITICAL]",
        "🟠": "[HIGH]",
        "🟡": "[MEDIUM]",
        "🟢": "[LOW]",
        "⚪": "[INFO]",
    }

    for old, new in replacements.items():
        text = text.replace(old, new)

    return text.strip()
