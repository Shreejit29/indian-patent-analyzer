from typing import List, Dict

from services.manual_parser import search_manual


def retrieve_manual_context(
    manual_chunks: List[Dict],
    query: str,
    max_results: int = 5,
) -> str:
    """
    Retrieve the most relevant portions of the Patent Manual
    for a given analysis query.
    """

    if not manual_chunks or not query:
        return ""

    results = search_manual(
        manual_chunks,
        query,
        max_results=max_results,
    )

    if not results:
        return ""

    context_parts = []

    for result in results:
        page_start = result.get("page_start")
        page_end = result.get("page_end")
        text = result.get("text", "").strip()

        if not text:
            continue

        if page_start == page_end:
            page_reference = f"Manual Page {page_start}"
        else:
            page_reference = (
                f"Manual Pages {page_start}-{page_end}"
            )

        context_parts.append(
            f"[{page_reference}]\n{text}"
        )

    return "\n\n".join(context_parts)


def retrieve_for_document_issue(
    manual_chunks: List[Dict],
    issue: str,
    max_results: int = 5,
) -> str:
    """
    Retrieve manual guidance for a specific patent-drafting
    or examination issue.
    """

    return retrieve_manual_context(
        manual_chunks=manual_chunks,
        query=issue,
        max_results=max_results,
    )


def retrieve_for_claim(
    manual_chunks: List[Dict],
    claim_text: str,
    max_results: int = 5,
) -> str:
    """
    Retrieve relevant manual guidance for a patent claim.
    """

    query = (
        "patent claim clarity succinctness "
        "support fair basis scope "
        "antecedent basis claim drafting "
        + claim_text
    )

    return retrieve_manual_context(
        manual_chunks=manual_chunks,
        query=query,
        max_results=max_results,
    )


def retrieve_for_abstract(
    manual_chunks: List[Dict],
    abstract_text: str,
    max_results: int = 5,
) -> str:
    """
    Retrieve relevant manual guidance for an abstract.
    """

    query = (
        "abstract patent specification "
        "content drafting requirements "
        + abstract_text
    )

    return retrieve_manual_context(
        manual_chunks=manual_chunks,
        query=query,
        max_results=max_results,
    )


def build_manual_evidence(
    manual_chunks: List[Dict],
    queries: List[str],
    max_results_per_query: int = 3,
) -> List[Dict]:
    """
    Retrieve manual evidence for multiple issues.

    Returns structured evidence that can be passed to Gemini.
    """

    evidence = []

    for query in queries:
        results = search_manual(
            manual_chunks,
            query,
            max_results=max_results_per_query,
        )

        for result in results:
            evidence.append(
                {
                    "query": query,
                    "chunk_id": result.get("chunk_id"),
                    "page_start": result.get("page_start"),
                    "page_end": result.get("page_end"),
                    "match_score": result.get("match_score"),
                    "text": result.get("text", ""),
                }
            )

    return evidence


def format_manual_evidence(evidence: List[Dict]) -> str:
    """
    Convert structured manual evidence into a clean text context
    for Gemini.
    """

    if not evidence:
        return ""

    parts = []

    for item in evidence:
        page_start = item.get("page_start")
        page_end = item.get("page_end")
        text = item.get("text", "").strip()

        if not text:
            continue

        if page_start == page_end:
            page = f"Page {page_start}"
        else:
            page = f"Pages {page_start}-{page_end}"

        parts.append(
            f"MANUAL EVIDENCE — {page}\n"
            f"Query: {item.get('query', '')}\n"
            f"{text}"
        )

    return "\n\n".join(parts)
