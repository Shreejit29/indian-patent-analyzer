import io
import re
from typing import List, Dict

from pypdf import PdfReader


def clean_text(text: str) -> str:
    """Clean extracted PDF text while preserving useful structure."""

    if not text:
        return ""

    # Normalize line endings
    text = text.replace("\r\n", "\n").replace("\r", "\n")

    # Remove excessive spaces
    text = re.sub(r"[ \t]+", " ", text)

    # Remove excessive blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()


def extract_manual_text(file_bytes: bytes) -> List[Dict]:
    """
    Extract patent manual text page-by-page.

    Returns:
        [
            {
                "page": 1,
                "text": "..."
            },
            ...
        ]
    """

    reader = PdfReader(io.BytesIO(file_bytes))

    pages = []

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            text = page.extract_text() or ""
        except Exception:
            text = ""

        text = clean_text(text)

        pages.append(
            {
                "page": page_number,
                "text": text,
            }
        )

    return pages


def combine_pages(pages: List[Dict]) -> str:
    """Combine extracted pages while retaining page markers."""

    sections = []

    for page in pages:
        if not page.get("text"):
            continue

        sections.append(
            f"--- MANUAL PAGE {page['page']} ---\n"
            f"{page['text']}"
        )

    return "\n\n".join(sections)


def split_into_chunks(
    pages: List[Dict],
    chunk_size: int = 6000,
    overlap: int = 500,
) -> List[Dict]:
    """
    Split manual text into searchable chunks.

    Page information is retained so the analyzer can cite
    the relevant manual page.
    """

    chunks = []

    for page in pages:
        text = page.get("text", "").strip()

        if not text:
            continue

        page_number = page["page"]

        # If page fits within one chunk
        if len(text) <= chunk_size:
            chunks.append(
                {
                    "chunk_id": len(chunks) + 1,
                    "page_start": page_number,
                    "page_end": page_number,
                    "text": text,
                }
            )
            continue

        start = 0

        while start < len(text):
            end = min(start + chunk_size, len(text))

            chunk_text = text[start:end]

            chunks.append(
                {
                    "chunk_id": len(chunks) + 1,
                    "page_start": page_number,
                    "page_end": page_number,
                    "text": chunk_text,
                }
            )

            if end >= len(text):
                break

            start = max(end - overlap, start + 1)

    return chunks


def parse_manual_pdf(
    file_bytes: bytes,
    chunk_size: int = 6000,
    overlap: int = 500,
) -> Dict:
    """
    Complete patent manual processing pipeline.

    Returns extracted pages and searchable chunks.
    """

    pages = extract_manual_text(file_bytes)

    chunks = split_into_chunks(
        pages,
        chunk_size=chunk_size,
        overlap=overlap,
    )

    full_text = combine_pages(pages)

    return {
        "page_count": len(pages),
        "pages": pages,
        "full_text": full_text,
        "chunks": chunks,
    }


def search_manual(
    chunks: List[Dict],
    query: str,
    max_results: int = 5,
) -> List[Dict]:
    """
    Simple keyword-based retrieval from manual chunks.

    This is an MVP retrieval layer. Later we can replace it
    with semantic/vector retrieval.
    """

    if not query:
        return []

    query_words = set(
        word.lower()
        for word in re.findall(r"\b[a-zA-Z0-9]{3,}\b", query)
    )

    scored_chunks = []

    for chunk in chunks:
        text = chunk.get("text", "")
        text_words = set(
            word.lower()
            for word in re.findall(r"\b[a-zA-Z0-9]{3,}\b", text)
        )

        matched_words = query_words.intersection(text_words)

        if matched_words:
            score = len(matched_words)

            scored_chunks.append(
                {
                    **chunk,
                    "match_score": score,
                }
            )

    scored_chunks.sort(
        key=lambda item: item["match_score"],
        reverse=True,
    )

    return scored_chunks[:max_results]
