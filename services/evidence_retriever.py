"""
Evidence Retriever V3
=====================

Purpose
-------
Convert patent-search results into limitation-level evidence.

Pipeline position
-----------------

    Claim
      |
      v
    Search Engine
      |
      v
    Candidate Documents
      |
      v
    Evidence Retriever
      |
      +---- exact / lexical matches
      +---- phrase matches
      +---- contextual passages
      +---- claim-section matches
      +---- page / paragraph provenance
      |
      v
    Claim Chart
      |
      v
    Novelty / Inventive Step

Important
---------
This module retrieves and ranks textual evidence.

It does NOT decide:
- legal novelty
- inventive step
- infringement
- patent validity
- prior-art status

Every evidence item should remain traceable to its source document
and, where available, its page, section, paragraph, or source URL.

Version
-------
3.0.0
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


EVIDENCE_RETRIEVER_VERSION = "3.0.0"


# ---------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------

EVIDENCE_EXPLICIT = "EXPLICIT"
EVIDENCE_PARTIAL = "PARTIAL"
EVIDENCE_CONTEXTUAL = "CONTEXTUAL"
EVIDENCE_WEAK = "WEAK"
EVIDENCE_NOT_FOUND = "NOT_FOUND"

SOURCE_CLAIMS = "CLAIMS"
SOURCE_ABSTRACT = "ABSTRACT"
SOURCE_DESCRIPTION = "DESCRIPTION"
SOURCE_PARAGRAPH = "PARAGRAPH"
SOURCE_SECTION = "SECTION"
SOURCE_METADATA = "METADATA"


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _clean(
    value: Any,
) -> str:

    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def _normalize(
    value: Any,
) -> str:

    text = _clean(value).lower()

    text = re.sub(
        r"[^a-z0-9\s\-]",
        " ",
        text,
    )

    return re.sub(
        r"\s+",
        " ",
        text,
    ).strip()


def _stable_id(
    prefix: str,
    value: Any,
) -> str:

    if not isinstance(
        value,
        str,
    ):

        value = json.dumps(
            value,
            sort_keys=True,
            default=str,
        )

    digest = hashlib.sha256(
        value.encode(
            "utf-8"
        )
    ).hexdigest()[:16]

    return f"{prefix}-{digest}"


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:
        return float(value)

    except Exception:
        return default


def _safe_int(
    value: Any,
    default: int = 0,
) -> int:

    try:
        return int(value)

    except Exception:
        return default


def _to_dict(
    value: Any,
) -> Dict[str, Any]:

    if value is None:
        return {}

    if isinstance(
        value,
        dict,
    ):

        return value

    if hasattr(
        value,
        "to_dict",
    ):

        try:

            result = value.to_dict()

            if isinstance(
                result,
                dict,
            ):

                return result

        except Exception:
            pass

    if hasattr(
        value,
        "__dict__",
    ):

        return dict(
            value.__dict__
        )

    return {}


def _listify(
    value: Any,
) -> List[Any]:

    if value is None:
        return []

    if isinstance(
        value,
        list,
    ):

        return value

    if isinstance(
        value,
        tuple,
    ):

        return list(value)

    return [value]


def _unique(
    values: Iterable[Any],
) -> List[Any]:

    result = []

    seen = set()

    for value in values:

        key = _normalize(
            value
        )

        if not key:
            continue

        if key in seen:
            continue

        seen.add(
            key
        )

        result.append(
            value
        )

    return result


def _tokenize(
    text: str,
) -> List[str]:

    return re.findall(
        r"\b[a-zA-Z0-9][a-zA-Z0-9\-]{2,}\b",
        _normalize(text),
    )


# ---------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------

@dataclass
class EvidencePassage:

    evidence_id: str

    document_id: str

    limitation_id: str

    claim_number: Optional[int]

    text: str

    source_type: str

    source_location: str = ""

    page: Optional[int] = None

    paragraph_id: str = ""

    section: str = ""

    start_offset: Optional[int] = None

    end_offset: Optional[int] = None

    matched_terms: List[str] = field(
        default_factory=list
    )

    matched_phrases: List[str] = field(
        default_factory=list
    )

    lexical_score: float = 0.0

    phrase_score: float = 0.0

    context_score: float = 0.0

    provenance_score: float = 0.0

    combined_score: float = 0.0

    disclosure_status: str = EVIDENCE_WEAK

    source_url: str = ""

    publication_number: str = ""

    publication_date: str = ""

    priority_date: str = ""

    retrieval_method: str = ""

    review_required: bool = True

    created_at: str = field(
        default_factory=_utc_now
    )

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(
            self
        )


@dataclass
class EvidenceDocument:

    document_id: str

    title: str = ""

    publication_number: str = ""

    publication_date: str = ""

    priority_date: str = ""

    url: str = ""

    abstract: str = ""

    claims: str = ""

    description: str = ""

    paragraphs: List[
        Dict[str, Any]
    ] = field(
        default_factory=list
    )

    sections: List[
        Dict[str, Any]
    ] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(
            self
        )


@dataclass
class EvidenceRetrievalResult:

    claim_number: Optional[int]

    limitation_count: int

    evidence_count: int

    evidence: List[
        EvidencePassage
    ] = field(
        default_factory=list
    )

    limitation_coverage: Dict[
        str,
        float
    ] = field(
        default_factory=dict
    )

    warnings: List[str] = field(
        default_factory=list
    )

    created_at: str = field(
        default_factory=_utc_now
    )

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return {
            "claim_number":
                self.claim_number,

            "limitation_count":
                self.limitation_count,

            "evidence_count":
                self.evidence_count,

            "evidence": [
                item.to_dict()
                for item
                in self.evidence
            ],

            "limitation_coverage":
                self.limitation_coverage,

            "warnings":
                self.warnings,

            "created_at":
                self.created_at,
        }


# ---------------------------------------------------------------------
# Text segmentation
# ---------------------------------------------------------------------

class TextSegmenter:

    @staticmethod
    def split_sentences(
        text: str,
    ) -> List[str]:

        text = _clean(
            text
        )

        if not text:
            return []

        parts = re.split(
            r"(?<=[.!?;])\s+",
            text,
        )

        return [
            _clean(part)
            for part
            in parts
            if _clean(part)
        ]

    @staticmethod
    def split_paragraphs(
        text: str,
    ) -> List[
        Dict[str, Any]
    ]:

        if not text:
            return []

        raw = re.split(
            r"\n\s*\n+",
            str(text),
        )

        paragraphs = []

        for index, paragraph in enumerate(
            raw,
            start=1,
        ):

            cleaned = _clean(
                paragraph
            )

            if not cleaned:
                continue

            paragraphs.append(
                {
                    "paragraph_id":
                        f"P{index}",

                    "text":
                        cleaned,

                    "index":
                        index,
                }
            )

        return paragraphs

    @staticmethod
    def split_into_windows(
        text: str,
        *,
        window_sentences: int = 3,
        overlap: int = 1,
    ) -> List[
        Dict[str, Any]
    ]:

        sentences = (
            TextSegmenter
            .split_sentences(
                text
            )
        )

        if not sentences:
            return []

        window_sentences = max(
            1,
            window_sentences,
        )

        overlap = min(
            overlap,
            window_sentences - 1,
        )

        step = max(
            1,
            window_sentences
            - overlap,
        )

        windows = []

        for start in range(
            0,
            len(sentences),
            step,
        ):

            subset = sentences[
                start:
                start
                + window_sentences
            ]

            if not subset:
                continue

            windows.append(
                {
                    "text":
                        " ".join(
                            subset
                        ),

                    "start_sentence":
                        start,

                    "end_sentence":
                        start
                        + len(subset)
                        - 1,
                }
            )

            if (
                start
                + window_sentences
                >= len(sentences)
            ):

                break

        return windows


# ---------------------------------------------------------------------
# Document normalization
# ---------------------------------------------------------------------

class EvidenceDocumentNormalizer:

    @staticmethod
    def normalize(
        document: Any,
    ) -> EvidenceDocument:

        item = _to_dict(
            document
        )

        document_id = _clean(
            item.get(
                "document_id",
                item.get(
                    "result_id",
                    item.get(
                        "id",
                        "",
                    ),
                ),
            )
        )

        if not document_id:

            document_id = _stable_id(
                "DOC",
                item,
            )

        paragraphs = []

        raw_paragraphs = item.get(
            "paragraphs",
            [],
        )

        for index, paragraph in enumerate(
            _listify(
                raw_paragraphs
            ),
            start=1,
        ):

            paragraph_dict = _to_dict(
                paragraph
            )

            if paragraph_dict:

                paragraph_dict.setdefault(
                    "paragraph_id",
                    f"P{index}",
                )

                paragraph_dict[
                    "text"
                ] = _clean(
                    paragraph_dict.get(
                        "text",
                        paragraph_dict.get(
                            "content",
                            "",
                        ),
                    )
                )

                paragraphs.append(
                    paragraph_dict
                )

            else:

                text = _clean(
                    paragraph
                )

                if text:

                    paragraphs.append(
                        {
                            "paragraph_id":
                                f"P{index}",

                            "text":
                                text,
                        }
                    )

        sections = []

        for section in _listify(
            item.get(
                "sections",
                [],
            )
        ):

            section_dict = _to_dict(
                section
            )

            if section_dict:

                section_dict[
                    "title"
                ] = _clean(
                    section_dict.get(
                        "title",
                        "",
                    )
                )

                section_dict[
                    "text"
                ] = _clean(
                    section_dict.get(
                        "text",
                        section_dict.get(
                            "content",
                            "",
                        ),
                    )
                )

                sections.append(
                    section_dict
                )

        return EvidenceDocument(
            document_id=document_id,

            title=_clean(
                item.get(
                    "title",
                    "",
                )
            ),

            publication_number=_clean(
                item.get(
                    "publication_number",
                    "",
                )
            ),

            publication_date=_clean(
                item.get(
                    "publication_date",
                    "",
                )
            ),

            priority_date=_clean(
                item.get(
                    "priority_date",
                    "",
                )
            ),

            url=_clean(
                item.get(
                    "url",
                    item.get(
                        "source",
                        "",
                    ),
                )
            ),

            abstract=_clean(
                item.get(
                    "abstract",
                    "",
                )
            ),

            claims=_clean(
                item.get(
                    "claims",
                    "",
                )
            ),

            description=_clean(
                item.get(
                    "description",
                    "",
                )
            ),

            paragraphs=paragraphs,

            sections=sections,

            metadata=item.get(
                "metadata",
                item.get(
                    "source_metadata",
                    {},
                ),
            ),
        )


# ---------------------------------------------------------------------
# Limitation matching
# ---------------------------------------------------------------------

class LimitationMatcher:

    GENERIC_TERMS = {
        "wherein",
        "comprising",
        "including",
        "configured",
        "adapted",
        "said",
        "thereof",
        "therein",
        "method",
        "system",
        "device",
        "apparatus",
        "using",
        "providing",
        "having",
        "further",
        "plurality",
        "first",
        "second",
        "third",
        "one",
        "more",
        "least",
        "based",
    }

    def technical_terms(
        self,
        text: str,
    ) -> List[str]:

        tokens = _tokenize(
            text
        )

        return [
            token
            for token
            in tokens
            if token
            not in self.GENERIC_TERMS
        ]

    def lexical_score(
        self,
        limitation: str,
        passage: str,
    ) -> Tuple[
        float,
        List[str],
    ]:

        limitation_terms = set(
            self.technical_terms(
                limitation
            )
        )

        passage_terms = set(
            _tokenize(
                passage
            )
        )

        if not limitation_terms:
            return 0.0, []

        matched = sorted(
            limitation_terms
            & passage_terms
        )

        score = (
            len(matched)
            / len(
                limitation_terms
            )
        )

        return score, matched

    def phrase_score(
        self,
        limitation: str,
        passage: str,
    ) -> Tuple[
        float,
        List[str],
    ]:

        normalized_limitation = _normalize(
            limitation
        )

        normalized_passage = _normalize(
            passage
        )

        if not normalized_limitation:
            return 0.0, []

        phrases = []

        words = normalized_limitation.split()

        # Generate short technical n-grams.
        for n in (
            4,
            3,
            2,
        ):

            for index in range(
                0,
                max(
                    0,
                    len(words)
                    - n
                    + 1,
                ),
            ):

                phrase = " ".join(
                    words[
                        index:
                        index + n
                    ]
                )

                if (
                    phrase
                    in normalized_passage
                    and len(phrase) > 10
                ):

                    phrases.append(
                        phrase
                    )

        phrases = _unique(
            phrases
        )

        if not phrases:
            return 0.0, []

        # Longer phrase matches receive more weight.
        longest = max(
            len(
                phrase.split()
            )
            for phrase
            in phrases
        )

        score = min(
            1.0,
            longest / 5.0,
        )

        return score, phrases

    def classify(
        self,
        lexical_score: float,
        phrase_score: float,
    ) -> str:

        if (
            phrase_score >= 0.8
            and lexical_score >= 0.7
        ):

            return EVIDENCE_EXPLICIT

        if (
            lexical_score >= 0.7
            or phrase_score >= 0.6
        ):

            return EVIDENCE_PARTIAL

        if (
            lexical_score >= 0.35
            or phrase_score >= 0.3
        ):

            return EVIDENCE_CONTEXTUAL

        if (
            lexical_score > 0
            or phrase_score > 0
        ):

            return EVIDENCE_WEAK

        return EVIDENCE_NOT_FOUND


# ---------------------------------------------------------------------
# Evidence retrieval
# ---------------------------------------------------------------------

class EvidenceRetriever:

    def __init__(
        self,
        *,
        max_evidence_per_limitation: int = 5,
        minimum_score: float = 0.15,
        window_sentences: int = 3,
    ):

        self.max_evidence_per_limitation = (
            max_evidence_per_limitation
        )

        self.minimum_score = (
            minimum_score
        )

        self.window_sentences = (
            window_sentences
        )

        self.matcher = (
            LimitationMatcher()
        )

    # -------------------------------------------------------------
    # Source extraction
    # -------------------------------------------------------------

    def _source_blocks(
        self,
        document: EvidenceDocument,
    ) -> List[
        Dict[str, Any]
    ]:

        blocks = []

        # Abstract
        if document.abstract:

            blocks.append(
                {
                    "source_type":
                        SOURCE_ABSTRACT,

                    "source_location":
                        "abstract",

                    "text":
                        document.abstract,

                    "page":
                        None,

                    "paragraph_id":
                        "",

                    "section":
                        "Abstract",
                }
            )

        # Claims
        if document.claims:

            blocks.append(
                {
                    "source_type":
                        SOURCE_CLAIMS,

                    "source_location":
                        "claims",

                    "text":
                        document.claims,

                    "page":
                        None,

                    "paragraph_id":
                        "",

                    "section":
                        "Claims",
                }
            )

        # Description
        if document.description:

            blocks.append(
                {
                    "source_type":
                        SOURCE_DESCRIPTION,

                    "source_location":
                        "description",

                    "text":
                        document.description,

                    "page":
                        None,

                    "paragraph_id":
                        "",

                    "section":
                        "Description",
                }
            )

        # Structured paragraphs
        for paragraph in (
            document.paragraphs
        ):

            text = _clean(
                paragraph.get(
                    "text",
                    "",
                )
            )

            if not text:
                continue

            blocks.append(
                {
                    "source_type":
                        SOURCE_PARAGRAPH,

                    "source_location":
                        paragraph.get(
                            "paragraph_id",
                            "",
                        ),

                    "text":
                        text,

                    "page":
                        paragraph.get(
                            "page",
                        ),

                    "paragraph_id":
                        paragraph.get(
                            "paragraph_id",
                            "",
                        ),

                    "section":
                        _clean(
                            paragraph.get(
                                "section",
                                "",
                            )
                        ),
                }
            )

        # Structured sections
        for section in (
            document.sections
        ):

            text = _clean(
                section.get(
                    "text",
                    "",
                )
            )

            if not text:
                continue

            blocks.append(
                {
                    "source_type":
                        SOURCE_SECTION,

                    "source_location":
                        _clean(
                            section.get(
                                "title",
                                "",
                            )
                        ),

                    "text":
                        text,

                    "page":
                        section.get(
                            "page",
                        ),

                    "paragraph_id":
                        "",

                    "section":
                        _clean(
                            section.get(
                                "title",
                                "",
                            )
                        ),
                }
            )

        return blocks

    # -------------------------------------------------------------
    # Window generation
    # -------------------------------------------------------------

    def _candidate_windows(
        self,
        block: Dict[str, Any],
    ) -> List[
        Dict[str, Any]
    ]:

        text = _clean(
            block.get(
                "text",
                "",
            )
        )

        if not text:
            return []

        windows = (
            TextSegmenter
            .split_into_windows(
                text,
                window_sentences=(
                    self.window_sentences
                ),
                overlap=1,
            )
        )

        result = []

        for window in windows:

            item = dict(
                block
            )

            item[
                "text"
            ] = window[
                "text"
            ]

            item[
                "start_sentence"
            ] = window.get(
                "start_sentence"
            )

            item[
                "end_sentence"
            ] = window.get(
                "end_sentence"
            )

            result.append(
                item
            )

        return result

    # -------------------------------------------------------------
    # Context score
    # -------------------------------------------------------------

    def _context_score(
        self,
        limitation: str,
        passage: str,
    ) -> float:

        terms = self.matcher.technical_terms(
            limitation
        )

        if not terms:
            return 0.0

        passage_tokens = set(
            _tokenize(
                passage
            )
        )

        # Important technical terms are counted more than generic
        # lexical overlap.
        weights = []

        for term in terms:

            weight = 1.0

            if len(term) >= 10:

                weight = 1.25

            elif "-" in term:

                weight = 1.2

            weights.append(
                (
                    term,
                    weight,
                )
            )

        total = sum(
            weight
            for _, weight
            in weights
        )

        matched = sum(
            weight
            for term, weight
            in weights
            if term
            in passage_tokens
        )

        if total <= 0:
            return 0.0

        return min(
            1.0,
            matched / total,
        )

    # -------------------------------------------------------------
    # Provenance score
    # -------------------------------------------------------------

    def _provenance_score(
        self,
        block: Dict[str, Any],
        document: EvidenceDocument,
    ) -> float:

        score = 0.0

        source_type = block.get(
            "source_type",
            "",
        )

        if source_type == SOURCE_CLAIMS:

            score += 0.45

        elif source_type == SOURCE_PARAGRAPH:

            score += 0.40

        elif source_type == SOURCE_SECTION:

            score += 0.35

        elif source_type == SOURCE_DESCRIPTION:

            score += 0.30

        elif source_type == SOURCE_ABSTRACT:

            score += 0.25

        if block.get(
            "page"
        ) is not None:

            score += 0.25

        if block.get(
            "paragraph_id"
        ):

            score += 0.20

        if document.url:

            score += 0.10

        return min(
            score,
            1.0,
        )

    # -------------------------------------------------------------
    # Single limitation
    # -------------------------------------------------------------

    def retrieve_for_limitation(
        self,
        limitation: Dict[str, Any],
        document: EvidenceDocument,
        *,
        claim_number: Optional[int] = None,
    ) -> List[
        EvidencePassage
    ]:

        limitation_text = _clean(
            limitation.get(
                "text",
                limitation.get(
                    "description",
                    limitation.get(
                        "limitation",
                        "",
                    ),
                ),
            )
        )

        limitation_id = _clean(
            limitation.get(
                "limitation_id",
                limitation.get(
                    "id",
                    "",
                ),
            )
        )

        if not limitation_id:

            limitation_id = _stable_id(
                "LIM",
                (
                    f"{claim_number}|"
                    f"{limitation_text}"
                ),
            )

        if not limitation_text:

            return []

        blocks = []

        for block in self._source_blocks(
            document
        ):

            blocks.extend(
                self._candidate_windows(
                    block
                )
            )

        evidence = []

        for block in blocks:

            passage = _clean(
                block.get(
                    "text",
                    "",
                )
            )

            if not passage:
                continue

            lexical, matched_terms = (
                self.matcher.lexical_score(
                    limitation_text,
                    passage,
                )
            )

            phrase, matched_phrases = (
                self.matcher.phrase_score(
                    limitation_text,
                    passage,
                )
            )

            context = (
                self._context_score(
                    limitation_text,
                    passage,
                )
            )

            provenance = (
                self._provenance_score(
                    block,
                    document,
                )
            )

            combined = (
                lexical * 0.40
                + phrase * 0.30
                + context * 0.20
                + provenance * 0.10
            )

            if (
                combined
                < self.minimum_score
            ):

                continue

            status = (
                self.matcher.classify(
                    lexical,
                    phrase,
                )
            )

            evidence_id = _stable_id(
                "EVID",
                (
                    f"{document.document_id}|"
                    f"{limitation_id}|"
                    f"{block.get('source_location', '')}|"
                    f"{passage}"
                ),
            )

            evidence.append(
                EvidencePassage(
                    evidence_id=evidence_id,

                    document_id=(
                        document.document_id
                    ),

                    limitation_id=(
                        limitation_id
                    ),

                    claim_number=(
                        claim_number
                    ),

                    text=passage,

                    source_type=(
                        block.get(
                            "source_type",
                            "",
                        )
                    ),

                    source_location=(
                        _clean(
                            block.get(
                                "source_location",
                                "",
                            )
                        )
                    ),

                    page=block.get(
                        "page"
                    ),

                    paragraph_id=(
                        _clean(
                            block.get(
                                "paragraph_id",
                                "",
                            )
                        )
                    ),

                    section=(
                        _clean(
                            block.get(
                                "section",
                                "",
                            )
                        )
                    ),

                    matched_terms=(
                        matched_terms
                    ),

                    matched_phrases=(
                        matched_phrases
                    ),

                    lexical_score=round(
                        lexical,
                        6,
                    ),

                    phrase_score=round(
                        phrase,
                        6,
                    ),

                    context_score=round(
                        context,
                        6,
                    ),

                    provenance_score=round(
                        provenance,
                        6,
                    ),

                    combined_score=round(
                        combined,
                        6,
                    ),

                    disclosure_status=(
                        status
                    ),

                    source_url=(
                        document.url
                    ),

                    publication_number=(
                        document.publication_number
                    ),

                    publication_date=(
                        document.publication_date
                    ),

                    priority_date=(
                        document.priority_date
                    ),

                    retrieval_method=(
                        "lexical+phrase+context"
                    ),
                )
            )

        evidence.sort(
            key=lambda item:
                -item.combined_score
        )

        # Remove duplicate text.
        unique = []

        seen = set()

        for item in evidence:

            key = _normalize(
                item.text
            )

            if key in seen:
                continue

            seen.add(
                key
            )

            unique.append(
                item
            )

            if (
                len(unique)
                >= self.max_evidence_per_limitation
            ):

                break

        return unique

    # -------------------------------------------------------------
    # Claim
    # -------------------------------------------------------------

    def retrieve_for_claim(
        self,
        claim: Dict[str, Any],
        document: Any,
    ) -> EvidenceRetrievalResult:

        claim_number = _safe_int(
            claim.get(
                "claim_number",
                0,
            ),
            0,
        )

        normalized_document = (
            EvidenceDocumentNormalizer
            .normalize(
                document
            )
        )

        limitations = _listify(
            claim.get(
                "limitations",
                [],
            )
        )

        evidence = []

        coverage = {}

        warnings = []

        for index, item in enumerate(
            limitations,
            start=1,
        ):

            limitation = _to_dict(
                item
            )

            if not limitation:

                limitation = {
                    "text":
                        _clean(
                            item
                        )
                }

            limitation.setdefault(
                "limitation_id",
                _stable_id(
                    "LIM",
                    (
                        f"{claim_number}|"
                        f"{index}|"
                        f"{limitation.get('text', '')}"
                    ),
                ),
            )

            limitation_evidence = (
                self.retrieve_for_limitation(
                    limitation,
                    normalized_document,
                    claim_number=(
                        claim_number
                    ),
                )
            )

            evidence.extend(
                limitation_evidence
            )

            if limitation_evidence:

                coverage[
                    limitation[
                        "limitation_id"
                    ]
                ] = max(
                    item.combined_score
                    for item
                    in limitation_evidence
                )

            else:

                coverage[
                    limitation[
                        "limitation_id"
                    ]
                ] = 0.0

                warnings.append(
                    (
                        "No evidence found for "
                        f"limitation "
                        f"{limitation['limitation_id']}"
                    )
                )

        return EvidenceRetrievalResult(
            claim_number=(
                claim_number
                if claim_number
                else None
            ),

            limitation_count=len(
                limitations
            ),

            evidence_count=len(
                evidence
            ),

            evidence=evidence,

            limitation_coverage=coverage,

            warnings=warnings,
        )

    # -------------------------------------------------------------
    # Multiple claims / documents
    # -------------------------------------------------------------

    def retrieve(
        self,
        claims: Iterable[Any],
        documents: Iterable[Any],
    ) -> Dict[str, Any]:

        normalized_documents = [
            EvidenceDocumentNormalizer
            .normalize(
                document
            )
            for document
            in documents
        ]

        all_evidence = []

        claim_results = []

        for claim in claims:

            claim_dict = _to_dict(
                claim
            )

            if not claim_dict:
                continue

            claim_number = _safe_int(
                claim_dict.get(
                    "claim_number",
                    0,
                )
            )

            claim_evidence = []

            document_coverage = {}

            for document in (
                normalized_documents
            ):

                result = (
                    self.retrieve_for_claim(
                        claim_dict,
                        document,
                    )
                )

                claim_evidence.extend(
                    result.evidence
                )

                document_coverage[
                    document.document_id
                ] = (
                    result.limitation_coverage
                )

            # Rank evidence globally for the claim.
            claim_evidence.sort(
                key=lambda item:
                    -item.combined_score
            )

            claim_result = {
                "claim_number":
                    claim_number,

                "evidence_count":
                    len(
                        claim_evidence
                    ),

                "document_count":
                    len(
                        normalized_documents
                    ),

                "evidence":
                    [
                        item.to_dict()
                        for item
                        in claim_evidence
                    ],

                "document_coverage":
                    document_coverage,
            }

            claim_results.append(
                claim_result
            )

            all_evidence.extend(
                claim_evidence
            )

        return {
            "version":
                EVIDENCE_RETRIEVER_VERSION,

            "claims":
                claim_results,

            "evidence":
                [
                    item.to_dict()
                    for item
                    in all_evidence
                ],

            "statistics":
                calculate_evidence_statistics(
                    all_evidence
                ),

            "review_notice":
                (
                    "Evidence retrieval is a "
                    "technical retrieval layer. "
                    "Retrieved text must be reviewed "
                    "against the original source."
                ),

            "created_at":
                _utc_now(),
        }


# ---------------------------------------------------------------------
# Evidence filtering
# ---------------------------------------------------------------------

def filter_evidence(
    evidence: Iterable[Any],
    *,
    minimum_score: float = 0.0,
    statuses: Optional[
        Sequence[str]
    ] = None,
    document_id: Optional[str] = None,
    limitation_id: Optional[str] = None,
) -> List[
    Dict[str, Any]
]:

    allowed_statuses = (
        set(statuses)
        if statuses
        else None
    )

    result = []

    for item in evidence:

        evidence_dict = _to_dict(
            item
        )

        if not evidence_dict:
            continue

        if (
            _safe_float(
                evidence_dict.get(
                    "combined_score",
                    0.0,
                )
            )
            < minimum_score
        ):

            continue

        if (
            allowed_statuses
            and evidence_dict.get(
                "disclosure_status"
            )
            not in allowed_statuses
        ):

            continue

        if (
            document_id
            and evidence_dict.get(
                "document_id"
            )
            != document_id
        ):

            continue

        if (
            limitation_id
            and evidence_dict.get(
                "limitation_id"
            )
            != limitation_id
        ):

            continue

        result.append(
            evidence_dict
        )

    result.sort(
        key=lambda item:
            -_safe_float(
                item.get(
                    "combined_score",
                    0.0,
                )
            )
    )

    return result


# ---------------------------------------------------------------------
# Best evidence
# ---------------------------------------------------------------------

def get_best_evidence(
    evidence: Iterable[Any],
    limitation_id: str,
    *,
    top_k: int = 3,
) -> List[
    Dict[str, Any]
]:

    filtered = filter_evidence(
        evidence,
        limitation_id=limitation_id,
    )

    return filtered[
        :max(
            1,
            top_k,
        )
    ]


# ---------------------------------------------------------------------
# Coverage
# ---------------------------------------------------------------------

def calculate_limitation_coverage(
    limitations: Iterable[Any],
    evidence: Iterable[Any],
) -> Dict[str, float]:

    evidence_list = [
        _to_dict(item)
        for item
        in evidence
    ]

    coverage = {}

    for limitation in limitations:

        limitation_dict = _to_dict(
            limitation
        )

        limitation_id = _clean(
            limitation_dict.get(
                "limitation_id",
                limitation_dict.get(
                    "id",
                    "",
                ),
            )
        )

        if not limitation_id:
            continue

        matches = [
            item
            for item
            in evidence_list
            if item.get(
                "limitation_id"
            )
            == limitation_id
        ]

        if not matches:

            coverage[
                limitation_id
            ] = 0.0

            continue

        coverage[
            limitation_id
        ] = max(
            _safe_float(
                item.get(
                    "combined_score",
                    0.0,
                )
            )
            for item
            in matches
        )

    return coverage


def calculate_claim_coverage(
    limitations: Iterable[Any],
    evidence: Iterable[Any],
) -> float:

    coverage = calculate_limitation_coverage(
        limitations,
        evidence,
    )

    if not coverage:
        return 0.0

    return (
        sum(
            coverage.values()
        )
        / len(
            coverage
        )
    )


# ---------------------------------------------------------------------
# Statistics
# ---------------------------------------------------------------------

def calculate_evidence_statistics(
    evidence: Iterable[Any],
) -> Dict[str, Any]:

    evidence_list = [
        _to_dict(item)
        for item
        in evidence
    ]

    if not evidence_list:

        return {
            "evidence_count":
                0,

            "document_count":
                0,

            "limitation_count":
                0,

            "average_score":
                0.0,

            "highest_score":
                0.0,

            "status_counts":
                {},

            "source_type_counts":
                {},
        }

    scores = [
        _safe_float(
            item.get(
                "combined_score",
                0.0,
            )
        )
        for item
        in evidence_list
    ]

    status_counts = {}

    source_counts = {}

    for item in evidence_list:

        status = item.get(
            "disclosure_status",
            EVIDENCE_WEAK,
        )

        source = item.get(
            "source_type",
            "UNKNOWN",
        )

        status_counts[
            status
        ] = (
            status_counts.get(
                status,
                0,
            )
            + 1
        )

        source_counts[
            source
        ] = (
            source_counts.get(
                source,
                0,
            )
            + 1
        )

    return {
        "evidence_count":
            len(
                evidence_list
            ),

        "document_count":
            len(
                {
                    item.get(
                        "document_id",
                        "",
                    )
                    for item
                    in evidence_list
                    if item.get(
                        "document_id",
                        "",
                    )
                }
            ),

        "limitation_count":
            len(
                {
                    item.get(
                        "limitation_id",
                        "",
                    )
                    for item
                    in evidence_list
                    if item.get(
                        "limitation_id",
                        "",
                    )
                }
            ),

        "average_score":
            round(
                sum(scores)
                / len(scores),
                6,
            ),

        "highest_score":
            round(
                max(scores),
                6,
            ),

        "status_counts":
            status_counts,

        "source_type_counts":
            source_counts,
    }


# ---------------------------------------------------------------------
# Claim-level evidence packet
# ---------------------------------------------------------------------

def build_evidence_packet(
    claim: Dict[str, Any],
    evidence: Iterable[Any],
    *,
    top_k_per_limitation: int = 3,
) -> Dict[str, Any]:

    claim_number = _safe_int(
        claim.get(
            "claim_number",
            0,
        )
    )

    limitations = []

    for index, item in enumerate(
        claim.get(
            "limitations",
            [],
        ),
        start=1,
    ):

        limitation = _to_dict(
            item
        )

        if not limitation:

            limitation = {
                "text":
                    _clean(
                        item
                    )
            }

        limitation_id = _clean(
            limitation.get(
                "limitation_id",
                limitation.get(
                    "id",
                    "",
                ),
            )
        )

        if not limitation_id:

            limitation_id = _stable_id(
                "LIM",
                (
                    f"{claim_number}|"
                    f"{index}|"
                    f"{limitation.get('text', '')}"
                ),
            )

        best = get_best_evidence(
            evidence,
            limitation_id,
            top_k=(
                top_k_per_limitation
            ),
        )

        limitations.append(
            {
                "limitation_id":
                    limitation_id,

                "limitation":
                    _clean(
                        limitation.get(
                            "text",
                            limitation.get(
                                "description",
                                "",
                            ),
                        )
                    ),

                "evidence":
                    best,
            }
        )

    return {
        "claim_number":
            claim_number,

        "claim_text":
            _clean(
                claim.get(
                    "text",
                    claim.get(
                        "claim_text",
                        "",
                    ),
                )
            ),

        "limitations":
            limitations,

        "review_notice":
            (
                "Evidence passages are retrieval "
                "candidates and must be verified "
                "against the source document."
            ),
    }


# ---------------------------------------------------------------------
# Backward-compatible APIs
# ---------------------------------------------------------------------

def retrieve_evidence(
    claims: Iterable[Any],
    documents: Iterable[Any],
    **kwargs: Any,
) -> Dict[str, Any]:

    retriever = EvidenceRetriever(
        **kwargs
    )

    return retriever.retrieve(
        claims,
        documents,
    )


def extract_evidence(
    limitation: Dict[str, Any],
    document: Dict[str, Any],
    **kwargs: Any,
) -> List[
    Dict[str, Any]
]:

    retriever = EvidenceRetriever(
        **kwargs
    )

    normalized = (
        EvidenceDocumentNormalizer
        .normalize(
            document
        )
    )

    result = (
        retriever.retrieve_for_limitation(
            limitation,
            normalized,
            claim_number=(
                limitation.get(
                    "claim_number"
                )
                if isinstance(
                    limitation,
                    dict,
                )
                else None
            ),
        )
    )

    return [
        item.to_dict()
        for item
        in result
    ]


def find_limitation_evidence(
    limitation: Dict[str, Any],
    documents: Iterable[Any],
    **kwargs: Any,
) -> List[
    Dict[str, Any]
]:

    retriever = EvidenceRetriever(
        **kwargs
    )

    all_results = []

    for document in documents:

        normalized = (
            EvidenceDocumentNormalizer
            .normalize(
                document
            )
        )

        results = (
            retriever.retrieve_for_limitation(
                limitation,
                normalized,
            )
        )

        all_results.extend(
            item.to_dict()
            for item
            in results
        )

    all_results.sort(
        key=lambda item:
            -_safe_float(
                item.get(
                    "combined_score",
                    0.0,
                )
            )
    )

    return all_results


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

__all__ = [
    "EVIDENCE_RETRIEVER_VERSION",

    "EVIDENCE_EXPLICIT",
    "EVIDENCE_PARTIAL",
    "EVIDENCE_CONTEXTUAL",
    "EVIDENCE_WEAK",
    "EVIDENCE_NOT_FOUND",

    "SOURCE_CLAIMS",
    "SOURCE_ABSTRACT",
    "SOURCE_DESCRIPTION",
    "SOURCE_PARAGRAPH",
    "SOURCE_SECTION",
    "SOURCE_METADATA",

    "EvidencePassage",
    "EvidenceDocument",
    "EvidenceRetrievalResult",

    "TextSegmenter",
    "EvidenceDocumentNormalizer",
    "LimitationMatcher",
    "EvidenceRetriever",

    "filter_evidence",
    "get_best_evidence",

    "calculate_limitation_coverage",
    "calculate_claim_coverage",
    "calculate_evidence_statistics",

    "build_evidence_packet",

    "retrieve_evidence",
    "extract_evidence",
    "find_limitation_evidence",
]
