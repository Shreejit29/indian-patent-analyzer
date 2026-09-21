"""
Indian Patent Analyzer
Document Parser V3

Responsibilities
----------------
- Extract text from PDF
- Preserve page boundaries
- Extract paragraphs
- Detect claims
- Detect specification sections
- Extract headings
- Produce stable paragraph IDs
- Generate document fingerprint
- Preserve document provenance
- Provide structured input for claim/evidence engines

This module intentionally does not make legal conclusions.
"""

from __future__ import annotations

import hashlib
import io
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


PARSER_VERSION = "3.0.0"


# ---------------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_text(value: Any) -> str:
    if value is None:
        return ""

    text = str(value)

    # Normalize common PDF artifacts.
    text = text.replace("\u00ad", "")
    text = text.replace("\x00", "")

    # Join hyphenated line breaks:
    # electro-
    # chemical
    # -> electrochemical
    text = re.sub(
        r"(\w)-\s*\n\s*(\w)",
        r"\1\2",
        text,
    )

    # Normalize whitespace.
    text = re.sub(
        r"[ \t]+",
        " ",
        text,
    )

    text = re.sub(
        r"\n{3,}",
        "\n\n",
        text,
    )

    return text.strip()


def _stable_id(
    prefix: str,
    value: str,
) -> str:

    digest = hashlib.sha256(
        value.encode("utf-8")
    ).hexdigest()[:16]

    return f"{prefix}-{digest}"


def calculate_sha256(
    data: bytes,
) -> str:

    return hashlib.sha256(
        data
    ).hexdigest()


def _unique(
    values: Iterable[str],
) -> List[str]:

    output = []
    seen = set()

    for value in values:

        value = _clean_text(
            value
        )

        if not value:
            continue

        key = value.lower()

        if key not in seen:

            seen.add(key)
            output.append(value)

    return output


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class PatentParagraph:

    paragraph_id: str

    page_number: int

    paragraph_number: int

    text: str

    section: str = ""

    heading: str = ""

    character_start: int = 0

    character_end: int = 0

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


@dataclass
class PatentPage:

    page_number: int

    text: str

    character_start: int = 0

    character_end: int = 0

    word_count: int = 0

    character_count: int = 0


@dataclass
class PatentClaim:

    claim_number: str

    text: str

    claim_type: str = "unknown"

    category: str = "unknown"

    depends_on: List[str] = field(
        default_factory=list
    )

    limitations: List[
        Dict[str, Any]
    ] = field(
        default_factory=list
    )

    page_number: Optional[int] = None

    paragraph_id: str = ""

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


# ---------------------------------------------------------------------------
# PDF loading
# ---------------------------------------------------------------------------

def _load_pdf_reader(
    source: Any,
):
    """
    Load a PyPDF2/PdfReader-compatible reader.

    Kept isolated so the rest of the parser does not depend on the
    exact PDF library API.
    """

    try:

        from pypdf import PdfReader

        return PdfReader(
            source
        )

    except ImportError:

        try:

            from PyPDF2 import PdfReader

            return PdfReader(
                source
            )

        except ImportError as exc:

            raise ImportError(
                "PDF parsing requires either "
                "'pypdf' or 'PyPDF2'. "
                "Install pypdf with: "
                "pip install pypdf"
            ) from exc


# ---------------------------------------------------------------------------
# PDF extraction
# ---------------------------------------------------------------------------

def extract_pdf_pages(
    source: Any,
) -> List[PatentPage]:

    reader = _load_pdf_reader(
        source
    )

    pages = []

    running_offset = 0

    for page_index, page in enumerate(
        reader.pages,
        start=1,
    ):

        try:

            raw_text = (
                page.extract_text()
                or ""
            )

        except Exception:

            raw_text = ""

        text = _clean_text(
            raw_text
        )

        start = running_offset

        end = (
            start
            + len(text)
        )

        pages.append(
            PatentPage(
                page_number=page_index,
                text=text,
                character_start=start,
                character_end=end,
                word_count=len(
                    text.split()
                ),
                character_count=len(
                    text
                ),
            )
        )

        running_offset = end + 2

    return pages


def extract_pdf_bytes(
    data: bytes,
) -> List[PatentPage]:

    stream = io.BytesIO(
        data
    )

    return extract_pdf_pages(
        stream
    )


def extract_pdf_file(
    file_path: str | Path,
) -> List[PatentPage]:

    file_path = Path(
        file_path
    )

    if not file_path.exists():

        raise FileNotFoundError(
            f"PDF not found: {file_path}"
        )

    with file_path.open(
        "rb"
    ) as file:

        return extract_pdf_pages(
            file
        )


# ---------------------------------------------------------------------------
# Page utilities
# ---------------------------------------------------------------------------

def pages_to_text(
    pages: Sequence[PatentPage],
) -> str:

    return "\n\n".join(
        page.text
        for page in pages
        if page.text
    )


def get_page(
    pages: Sequence[PatentPage],
    page_number: int,
) -> Optional[PatentPage]:

    for page in pages:

        if page.page_number == page_number:
            return page

    return None


# ---------------------------------------------------------------------------
# Heading detection
# ---------------------------------------------------------------------------

SECTION_HEADINGS = {
    "abstract": "abstract",
    "field of the invention": "field",
    "background": "background",
    "background of the invention": "background",
    "summary": "summary",
    "summary of the invention": "summary",
    "brief description": "brief_description",
    "brief description of drawings": "drawings",
    "detailed description": "detailed_description",
    "description": "description",
    "claims": "claims",
    "claim": "claims",
    "drawings": "drawings",
}


def detect_heading(
    line: str,
) -> Optional[str]:

    clean = _clean_text(
        line
    )

    if not clean:
        return None

    normalized = clean.lower()

    # Direct section match.
    for heading, section in (
        SECTION_HEADINGS.items()
    ):

        if normalized == heading:
            return section

    # Common numbered headings.
    numbered = re.sub(
        r"^\d+[\.\)]?\s*",
        "",
        normalized,
    )

    for heading, section in (
        SECTION_HEADINGS.items()
    ):

        if numbered == heading:
            return section

    return None


def detect_headings(
    text: str,
) -> List[
    Tuple[
        int,
        str,
        str,
    ]
]:

    results = []

    for line_number, line in enumerate(
        text.splitlines(),
        start=1,
    ):

        section = detect_heading(
            line
        )

        if section:

            results.append(
                (
                    line_number,
                    _clean_text(line),
                    section,
                )
            )

    return results


# ---------------------------------------------------------------------------
# Paragraph extraction
# ---------------------------------------------------------------------------

def split_into_paragraphs(
    pages: Sequence[PatentPage],
) -> List[PatentParagraph]:

    paragraphs = []

    paragraph_number = 0

    for page in pages:

        if not page.text:
            continue

        # First attempt: blank-line paragraph boundaries.
        raw_blocks = re.split(
            r"\n\s*\n",
            page.text,
        )

        # If PDF extraction collapsed everything into one block,
        # fall back to sentence-like chunks.
        if (
            len(raw_blocks) == 1
            and len(
                raw_blocks[0]
            ) > 5000
        ):

            raw_blocks = re.split(
                r"(?<=[.!?])\s+(?=[A-Z])",
                page.text,
            )

        local_offset = 0

        for block in raw_blocks:

            block = _clean_text(
                block
            )

            if not block:
                continue

            paragraph_number += 1

            start = (
                page.character_start
                + local_offset
            )

            end = (
                start
                + len(block)
            )

            paragraph_id = _stable_id(
                "PARA",
                f"{page.page_number}|"
                f"{paragraph_number}|"
                f"{block}",
            )

            paragraphs.append(
                PatentParagraph(
                    paragraph_id=paragraph_id,
                    page_number=page.page_number,
                    paragraph_number=paragraph_number,
                    text=block,
                    character_start=start,
                    character_end=end,
                    metadata={
                        "parser_version":
                            PARSER_VERSION,
                    },
                )
            )

            local_offset += (
                len(block) + 2
            )

    return paragraphs


# ---------------------------------------------------------------------------
# Claim detection
# ---------------------------------------------------------------------------

CLAIM_START_PATTERN = re.compile(
    r"^\s*(?:claim\s*)?(\d{1,4})\s*[\.\):\-]\s*(.+)$",
    re.IGNORECASE,
)

CLAIM_INLINE_PATTERN = re.compile(
    r"(?:^|\n)\s*(?:claim\s*)?(\d{1,4})\s*[\.\):\-]\s*",
    re.IGNORECASE,
)


def _is_claim_number_line(
    line: str,
) -> Optional[str]:

    match = CLAIM_START_PATTERN.match(
        line
    )

    if not match:
        return None

    return match.group(1)


def _detect_claim_type(
    text: str,
    claim_number: str,
) -> str:

    lowered = text.lower()

    if re.search(
        r"\baccording to claim\s+\d+",
        lowered,
    ):

        return "dependent"

    if re.search(
        r"\bof claim\s+\d+",
        lowered,
    ):

        return "dependent"

    if re.search(
        r"\bthe method of claim\s+\d+",
        lowered,
    ):

        return "dependent"

    return "independent"


def _detect_claim_category(
    text: str,
) -> str:

    lowered = text.lower()

    if re.search(
        r"\ba method\b|\bmethod of\b|\bmethod comprising\b",
        lowered,
    ):

        return "method"

    if re.search(
        r"\ba system\b|\bsystem comprising\b",
        lowered,
    ):

        return "system"

    if re.search(
        r"\ban apparatus\b|\bapparatus comprising\b",
        lowered,
    ):

        return "apparatus"

    if re.search(
        r"\ba device\b|\bdevice comprising\b",
        lowered,
    ):

        return "device"

    if re.search(
        r"\ba composition\b|\bcomposition comprising\b",
        lowered,
    ):

        return "composition"

    if re.search(
        r"\ba computer-readable\b|\bcomputer readable\b",
        lowered,
    ):

        return "computer-readable-medium"

    return "unknown"


def _detect_dependencies(
    text: str,
) -> List[str]:

    patterns = [
        r"\bclaim\s+(\d+)",
        r"\bclaims\s+(\d+)",
        r"\bof\s+claim\s+(\d+)",
    ]

    dependencies = []

    for pattern in patterns:

        dependencies.extend(
            re.findall(
                pattern,
                text,
                flags=re.IGNORECASE,
            )
        )

    return _unique(
        dependencies
    )


def parse_claims(
    pages: Sequence[PatentPage],
) -> List[PatentClaim]:

    # Restrict claim extraction primarily to the claims section
    # when such a section can be identified.
    claims = []

    in_claim_section = False

    current_number: Optional[str] = None
    current_lines: List[str] = []
    current_page: Optional[int] = None

    def flush_current():

        nonlocal current_number
        nonlocal current_lines
        nonlocal current_page

        if (
            current_number is None
            or not current_lines
        ):

            return

        text = _clean_text(
            " ".join(
                current_lines
            )
        )

        if not text:
            return

        claim_type = _detect_claim_type(
            text,
            current_number,
        )

        category = _detect_claim_category(
            text
        )

        dependencies = (
            _detect_dependencies(
                text
            )
        )

        claim_seed = (
            f"{current_number}|"
            f"{text}"
        )

        paragraph_id = _stable_id(
            "CLAIM",
            claim_seed,
        )

        claims.append(
            PatentClaim(
                claim_number=current_number,
                text=text,
                claim_type=claim_type,
                category=category,
                depends_on=dependencies,
                page_number=current_page,
                paragraph_id=paragraph_id,
                metadata={
                    "parser_version":
                        PARSER_VERSION,
                },
            )
        )

        current_number = None
        current_lines = []
        current_page = None

    for page in pages:

        lines = page.text.splitlines()

        for line in lines:

            clean_line = _clean_text(
                line
            )

            if not clean_line:
                continue

            detected_section = detect_heading(
                clean_line
            )

            if detected_section == "claims":

                flush_current()

                in_claim_section = True

                continue

            # If another major section appears after claims,
            # stop claim extraction.
            if (
                in_claim_section
                and detected_section
                and detected_section
                != "claims"
            ):

                flush_current()

                in_claim_section = False

                continue

            # A claim-number line.
            number = _is_claim_number_line(
                clean_line
            )

            if number is not None:

                flush_current()

                current_number = number

                current_lines = [
                    CLAIM_START_PATTERN.match(
                        clean_line
                    ).group(2)
                ]

                current_page = (
                    page.page_number
                )

                continue

            # Some patent PDFs omit the "Claims" heading.
            #
            # If a line begins with a numbered claim and contains
            # "comprising", "wherein", etc., allow it.
            if not in_claim_section:

                inline_match = (
                    CLAIM_START_PATTERN.match(
                        clean_line
                    )
                )

                if inline_match:

                    if (
                        re.search(
                            r"\bcomprising\b"
                            r"|\bwherein\b"
                            r"|\bconfigured\b",
                            clean_line,
                            re.IGNORECASE,
                        )
                    ):

                        flush_current()

                        current_number = (
                            inline_match.group(1)
                        )

                        current_lines = [
                            inline_match.group(2)
                        ]

                        current_page = (
                            page.page_number
                        )

                        continue

            if current_number is not None:

                current_lines.append(
                    clean_line
                )

    flush_current()

    return claims


# ---------------------------------------------------------------------------
# Claim limitation preparation
# ---------------------------------------------------------------------------

def _split_claim_limitations(
    claim_text: str,
) -> List[str]:

    text = _clean_text(
        claim_text
    )

    if not text:
        return []

    # First split on semicolons.
    parts = re.split(
        r";\s*",
        text,
    )

    # If there are too few parts, split on common claim connectors.
    if len(parts) <= 1:

        parts = re.split(
            r",\s+(?=(?:a|an|the|at least|one or more)\s+)",
            text,
            flags=re.IGNORECASE,
        )

    cleaned = [
        _clean_text(part)
        for part in parts
        if _clean_text(part)
    ]

    return cleaned


def add_claim_limitations(
    claims: Sequence[PatentClaim],
) -> List[PatentClaim]:

    output = []

    for claim in claims:

        parts = _split_claim_limitations(
            claim.text
        )

        limitations = []

        for index, part in enumerate(
            parts,
            start=1,
        ):

            limitation_id = _stable_id(
                "L",
                f"{claim.claim_number}|"
                f"{index}|"
                f"{part}",
            )

            lowered = part.lower()

            if (
                "configured to" in lowered
                or "adapted to" in lowered
                or "operable to" in lowered
            ):
                limitation_type = "functional"

            elif (
                "coupled" in lowered
                or "connected" in lowered
                or "between" in lowered
                or "relative to" in lowered
            ):
                limitation_type = "relationship"

            elif re.search(
                r"\bgreater than\b"
                r"|\bless than\b"
                r"|\bat least\b"
                r"|\bat most\b"
                r"|\bbetween\b"
                r"|\bwithin\b",
                lowered,
            ):
                limitation_type = "constraint"

            else:
                limitation_type = "element"

            limitations.append(
                {
                    "id": limitation_id,
                    "text": part,
                    "type": limitation_type,
                }
            )

        claim.limitations = limitations

        output.append(
            claim
        )

    return output


# ---------------------------------------------------------------------------
# Specification section classification
# ---------------------------------------------------------------------------

def classify_paragraph_sections(
    paragraphs: Sequence[PatentParagraph],
) -> List[PatentParagraph]:

    current_section = ""

    current_heading = ""

    for paragraph in paragraphs:

        detected = detect_heading(
            paragraph.text
        )

        if detected:

            current_section = detected
            current_heading = paragraph.text

            paragraph.section = (
                current_section
            )

            paragraph.heading = (
                current_heading
            )

            continue

        paragraph.section = (
            current_section
        )

        paragraph.heading = (
            current_heading
        )

    return list(
        paragraphs
    )


# ---------------------------------------------------------------------------
# Document statistics
# ---------------------------------------------------------------------------

def document_statistics(
    pages: Sequence[PatentPage],
    paragraphs: Sequence[PatentParagraph],
    claims: Sequence[PatentClaim],
) -> Dict[str, Any]:

    total_words = sum(
        page.word_count
        for page in pages
    )

    total_characters = sum(
        page.character_count
        for page in pages
    )

    independent_claims = sum(
        claim.claim_type
        == "independent"
        for claim in claims
    )

    dependent_claims = sum(
        claim.claim_type
        == "dependent"
        for claim in claims
    )

    limitations = sum(
        len(
            claim.limitations
        )
        for claim in claims
    )

    return {
        "page_count":
            len(pages),

        "paragraph_count":
            len(paragraphs),

        "claim_count":
            len(claims),

        "independent_claim_count":
            independent_claims,

        "dependent_claim_count":
            dependent_claims,

        "limitation_count":
            limitations,

        "word_count":
            total_words,

        "character_count":
            total_characters,
    }


# ---------------------------------------------------------------------------
# Full document parsing
# ---------------------------------------------------------------------------

def parse_document(
    data: bytes,
    filename: str = "document.pdf",
) -> Dict[str, Any]:

    if not data:

        raise ValueError(
            "Document is empty."
        )

    document_hash = calculate_sha256(
        data
    )

    pages = extract_pdf_bytes(
        data
    )

    paragraphs = (
        split_into_paragraphs(
            pages
        )
    )

    paragraphs = (
        classify_paragraph_sections(
            paragraphs
        )
    )

    claims = parse_claims(
        pages
    )

    claims = add_claim_limitations(
        claims
    )

    stats = document_statistics(
        pages,
        paragraphs,
        claims,
    )

    full_text = pages_to_text(
        pages
    )

    return {
        "parser_version":
            PARSER_VERSION,

        "generated_at":
            _utc_now(),

        "filename":
            filename,

        "document_hash":
            document_hash,

        "document_type":
            "PDF",

        "text":
            full_text,

        "pages": [
            asdict(page)
            for page in pages
        ],

        "paragraphs": [
            asdict(paragraph)
            for paragraph in paragraphs
        ],

        "claims": [
            asdict(claim)
            for claim in claims
        ],

        "statistics":
            stats,

        "provenance": {
            "parser_version":
                PARSER_VERSION,

            "document_sha256":
                document_hash,

            "filename":
                filename,

            "generated_at":
                _utc_now(),
        },
    }


# ---------------------------------------------------------------------------
# File convenience wrapper
# ---------------------------------------------------------------------------

def parse_file(
    file_path: str | Path,
) -> Dict[str, Any]:

    file_path = Path(
        file_path
    )

    if not file_path.exists():

        raise FileNotFoundError(
            f"File not found: {file_path}"
        )

    with file_path.open(
        "rb"
    ) as file:

        data = file.read()

    return parse_document(
        data,
        filename=file_path.name,
    )


# ---------------------------------------------------------------------------
# Backward-compatible helper
# ---------------------------------------------------------------------------

def extract_text(
    file_path: str | Path,
) -> str:

    result = parse_file(
        file_path
    )

    return result.get(
        "text",
        "",
    )


def parse_pdf(
    file_path: str | Path,
) -> Dict[str, Any]:

    return parse_file(
        file_path
    )


__all__ = [
    "PARSER_VERSION",
    "PatentParagraph",
    "PatentPage",
    "PatentClaim",
    "calculate_sha256",
    "extract_pdf_pages",
    "extract_pdf_bytes",
    "extract_pdf_file",
    "pages_to_text",
    "get_page",
    "detect_heading",
    "detect_headings",
    "split_into_paragraphs",
    "parse_claims",
    "add_claim_limitations",
    "classify_paragraph_sections",
    "document_statistics",
    "parse_document",
    "parse_file",
    "extract_text",
    "parse_pdf",
]
