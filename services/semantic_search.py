"""
Semantic Search Engine V3
=========================

Purpose
-------
Semantic retrieval for patent claims, limitations, specifications,
and prior-art documents.

Architecture
------------
Claim / Limitation
        ↓
Text normalization
        ↓
Embedding model
        ↓
Vector representation
        ↓
Cosine similarity
        ↓
Ranked evidence / prior art

Fallback
--------
If sentence-transformers is unavailable, the engine falls back to
a deterministic TF-IDF-like lexical similarity implementation.

Important
---------
Semantic similarity is retrieval evidence.

It does NOT establish:
    - novelty
    - inventive step
    - infringement
    - validity
    - patentability
    - legal equivalence

Those determinations require legal analysis and evidence review.

Version
-------
3.0.0
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


SEMANTIC_SEARCH_VERSION = "3.0.0"

DEFAULT_MODEL = "all-MiniLM-L6-v2"

# Number of documents normally returned.
DEFAULT_TOP_K = 10


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    if value is None:
        return ""

    text = str(value)

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def _normalize(value: Any) -> str:
    text = _clean(value).lower()

    text = re.sub(
        r"[^a-z0-9\s\-/\.]",
        " ",
        text,
    )

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def _stable_id(
    prefix: str,
    value: str,
) -> str:

    digest = hashlib.sha256(
        _clean(value).encode(
            "utf-8"
        )
    ).hexdigest()[:12]

    return f"{prefix}-{digest}"


def _tokenize(
    text: str,
) -> List[str]:

    normalized = _normalize(
        text
    )

    if not normalized:
        return []

    return normalized.split()


def _unique(
    values: Iterable[str],
) -> List[str]:

    seen = set()
    result = []

    for value in values:

        value = _clean(
            value
        )

        if not value:
            continue

        key = value.lower()

        if key in seen:
            continue

        seen.add(key)
        result.append(value)

    return result


def cosine_similarity(
    vector_a: Sequence[float],
    vector_b: Sequence[float],
) -> float:

    if not vector_a or not vector_b:
        return 0.0

    if len(vector_a) != len(vector_b):
        return 0.0

    dot = sum(
        a * b
        for a, b in zip(
            vector_a,
            vector_b,
        )
    )

    norm_a = math.sqrt(
        sum(
            a * a
            for a in vector_a
        )
    )

    norm_b = math.sqrt(
        sum(
            b * b
            for b in vector_b
        )
    )

    if norm_a == 0 or norm_b == 0:
        return 0.0

    return dot / (
        norm_a * norm_b
    )


# ---------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------

@dataclass
class SearchDocument:

    document_id: str
    text: str
    title: str = ""
    source: str = ""
    metadata: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:

        return asdict(
            self
        )


@dataclass
class SemanticSearchResult:

    document_id: str
    score: float
    rank: int
    text: str
    title: str
    source: str
    match_type: str
    metadata: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:

        return asdict(
            self
        )


@dataclass
class SearchExplanation:

    query: str
    document_id: str
    semantic_score: float
    lexical_score: float
    combined_score: float
    overlapping_terms: List[str]

    def to_dict(self) -> Dict[str, Any]:

        return asdict(
            self
        )


# ---------------------------------------------------------------------
# Document normalization
# ---------------------------------------------------------------------

def normalize_documents(
    documents: Iterable[Any],
) -> List[SearchDocument]:

    normalized = []

    for index, document in enumerate(
        documents,
        start=1,
    ):

        if isinstance(
            document,
            SearchDocument,
        ):

            normalized.append(
                document
            )

            continue

        if isinstance(
            document,
            dict,
        ):

            text = _clean(
                document.get(
                    "text",
                    document.get(
                        "content",
                        document.get(
                            "claim_text",
                            "",
                        ),
                    ),
                )
            )

            title = _clean(
                document.get(
                    "title",
                    document.get(
                        "name",
                        "",
                    ),
                )
            )

            source = _clean(
                document.get(
                    "source",
                    document.get(
                        "url",
                        "",
                    ),
                )
            )

            document_id = _clean(
                document.get(
                    "document_id",
                    document.get(
                        "id",
                        "",
                    ),
                )
            )

            if not document_id:

                document_id = _stable_id(
                    "DOC",
                    f"{title}|{text}",
                )

            metadata = document.get(
                "metadata",
                {},
            )

            if not isinstance(
                metadata,
                dict,
            ):
                metadata = {}

            normalized.append(
                SearchDocument(
                    document_id=document_id,
                    text=text,
                    title=title,
                    source=source,
                    metadata=metadata,
                )
            )

            continue

        text = _clean(
            document
        )

        normalized.append(
            SearchDocument(
                document_id=_stable_id(
                    "DOC",
                    f"{index}|{text}",
                ),
                text=text,
            )
        )

    return [
        document
        for document
        in normalized
        if document.text
    ]


# ---------------------------------------------------------------------
# Lexical fallback
# ---------------------------------------------------------------------

STOP_WORDS = {
    "the",
    "and",
    "or",
    "of",
    "to",
    "a",
    "an",
    "in",
    "on",
    "for",
    "with",
    "by",
    "from",
    "is",
    "are",
    "was",
    "were",
    "be",
    "being",
    "been",
    "as",
    "at",
    "that",
    "this",
    "it",
    "its",
    "wherein",
    "said",
    "comprising",
    "including",
    "having",
}


def _meaningful_tokens(
    text: str,
) -> List[str]:

    return [
        token
        for token in _tokenize(
            text
        )
        if token not in STOP_WORDS
        and len(token) > 2
    ]


def lexical_similarity(
    query: str,
    document: str,
) -> float:

    query_tokens = set(
        _meaningful_tokens(
            query
        )
    )

    document_tokens = set(
        _meaningful_tokens(
            document
        )
    )

    if not query_tokens or not document_tokens:
        return 0.0

    intersection = (
        query_tokens
        & document_tokens
    )

    # F1-style lexical similarity.
    precision = (
        len(intersection)
        / len(document_tokens)
    )

    recall = (
        len(intersection)
        / len(query_tokens)
    )

    if (
        precision
        + recall
        == 0
    ):
        return 0.0

    return (
        2
        * precision
        * recall
        / (
            precision
            + recall
        )
    )


def overlapping_terms(
    query: str,
    document: str,
) -> List[str]:

    query_tokens = set(
        _meaningful_tokens(
            query
        )
    )

    document_tokens = set(
        _meaningful_tokens(
            document
        )
    )

    return sorted(
        query_tokens
        & document_tokens
    )


# ---------------------------------------------------------------------
# Embedding backend
# ---------------------------------------------------------------------

class EmbeddingBackend:

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
    ):

        self.model_name = model_name
        self.model = None
        self.available = False
        self.error = ""

        self._load_model()

    def _load_model(
        self,
    ) -> None:

        try:

            from sentence_transformers import (
                SentenceTransformer
            )

            self.model = (
                SentenceTransformer(
                    self.model_name
                )
            )

            self.available = True

        except Exception as exc:

            self.available = False
            self.error = str(
                exc
            )

    def encode(
        self,
        texts: Sequence[str],
    ) -> List[List[float]]:

        if not self.available:
            return []

        if not texts:
            return []

        try:

            embeddings = (
                self.model.encode(
                    list(texts),
                    normalize_embeddings=True,
                    show_progress_bar=False,
                )
            )

            return [
                list(
                    map(
                        float,
                        vector,
                    )
                )
                for vector
                in embeddings
            ]

        except Exception as exc:

            self.error = str(
                exc
            )

            self.available = False

            return []


# ---------------------------------------------------------------------
# Semantic Search Engine
# ---------------------------------------------------------------------

class SemanticSearchEngine:

    def __init__(
        self,
        model_name: str = DEFAULT_MODEL,
        semantic_weight: float = 0.75,
        lexical_weight: float = 0.25,
    ):

        total_weight = (
            semantic_weight
            + lexical_weight
        )

        if total_weight <= 0:

            semantic_weight = 0.75
            lexical_weight = 0.25

            total_weight = 1.0

        self.semantic_weight = (
            semantic_weight
            / total_weight
        )

        self.lexical_weight = (
            lexical_weight
            / total_weight
        )

        self.backend = (
            EmbeddingBackend(
                model_name=model_name
            )
        )

        self.model_name = (
            model_name
        )

    # -----------------------------------------------------------------
    # Search
    # -----------------------------------------------------------------

    def search(
        self,
        query: str,
        documents: Iterable[Any],
        top_k: int = DEFAULT_TOP_K,
        min_score: float = 0.0,
    ) -> List[SemanticSearchResult]:

        query = _clean(
            query
        )

        if not query:
            return []

        docs = normalize_documents(
            documents
        )

        if not docs:
            return []

        # -------------------------------------------------------------
        # Semantic path
        # -------------------------------------------------------------

        semantic_scores = {}

        if self.backend.available:

            embeddings = (
                self.backend.encode(
                    [
                        query
                    ]
                    + [
                        doc.text
                        for doc in docs
                    ]
                )
            )

            if (
                len(embeddings)
                == len(docs) + 1
            ):

                query_vector = (
                    embeddings[0]
                )

                for index, vector in enumerate(
                    embeddings[1:]
                ):

                    semantic_scores[
                        docs[index].document_id
                    ] = max(
                        0.0,
                        min(
                            1.0,
                            cosine_similarity(
                                query_vector,
                                vector,
                            ),
                        ),
                    )

        # -------------------------------------------------------------
        # Ranking
        # -------------------------------------------------------------

        ranked = []

        for doc in docs:

            lexical = (
                lexical_similarity(
                    query,
                    doc.text,
                )
            )

            semantic = (
                semantic_scores.get(
                    doc.document_id,
                    0.0,
                )
            )

            if semantic_scores:

                combined = (
                    self.semantic_weight
                    * semantic
                    + self.lexical_weight
                    * lexical
                )

                match_type = (
                    "semantic+lexical"
                )

            else:

                combined = lexical
                match_type = "lexical-fallback"

            if combined < min_score:
                continue

            ranked.append(
                (
                    combined,
                    semantic,
                    lexical,
                    doc,
                )
            )

        ranked.sort(
            key=lambda item: (
                item[0],
                item[1],
                item[2],
            ),
            reverse=True,
        )

        results = []

        for rank, item in enumerate(
            ranked[:max(1, top_k)],
            start=1,
        ):

            combined, semantic, lexical, doc = item

            results.append(
                SemanticSearchResult(
                    document_id=doc.document_id,
                    score=round(
                        combined,
                        6,
                    ),
                    rank=rank,
                    text=doc.text,
                    title=doc.title,
                    source=doc.source,
                    match_type=(
                        "semantic+lexical"
                        if semantic_scores
                        else "lexical-fallback"
                    ),
                    metadata=(
                        doc.metadata
                        or {}
                    ),
                )
            )

        return results

    # -----------------------------------------------------------------
    # Explain result
    # -----------------------------------------------------------------

    def explain(
        self,
        query: str,
        document: SearchDocument,
    ) -> SearchExplanation:

        semantic_score = 0.0

        if self.backend.available:

            vectors = (
                self.backend.encode(
                    [
                        query,
                        document.text,
                    ]
                )
            )

            if len(vectors) == 2:

                semantic_score = max(
                    0.0,
                    min(
                        1.0,
                        cosine_similarity(
                            vectors[0],
                            vectors[1],
                        ),
                    ),
                )

        lexical_score = (
            lexical_similarity(
                query,
                document.text,
            )
        )

        if self.backend.available:

            combined_score = (
                self.semantic_weight
                * semantic_score
                + self.lexical_weight
                * lexical_score
            )

        else:

            combined_score = (
                lexical_score
            )

        return SearchExplanation(
            query=query,
            document_id=(
                document.document_id
            ),
            semantic_score=round(
                semantic_score,
                6,
            ),
            lexical_score=round(
                lexical_score,
                6,
            ),
            combined_score=round(
                combined_score,
                6,
            ),
            overlapping_terms=(
                overlapping_terms(
                    query,
                    document.text,
                )
            ),
        )

    # -----------------------------------------------------------------
    # Claim search
    # -----------------------------------------------------------------

    def search_claim(
        self,
        claim: Any,
        prior_art: Iterable[Any],
        top_k: int = DEFAULT_TOP_K,
    ) -> List[SemanticSearchResult]:

        if isinstance(
            claim,
            dict,
        ):

            query = _clean(
                claim.get(
                    "text",
                    claim.get(
                        "claim_text",
                        "",
                    ),
                )
            )

        else:

            query = _clean(
                claim
            )

        return self.search(
            query=query,
            documents=prior_art,
            top_k=top_k,
        )

    # -----------------------------------------------------------------
    # Limitation search
    # -----------------------------------------------------------------

    def search_limitation(
        self,
        limitation: Any,
        prior_art: Iterable[Any],
        top_k: int = 5,
    ) -> List[SemanticSearchResult]:

        if isinstance(
            limitation,
            dict,
        ):

            query = _clean(
                limitation.get(
                    "text",
                    limitation.get(
                        "limitation",
                        "",
                    ),
                )
            )

        else:

            query = _clean(
                limitation
            )

        return self.search(
            query=query,
            documents=prior_art,
            top_k=top_k,
        )

    # -----------------------------------------------------------------
    # Batch claim search
    # -----------------------------------------------------------------

    def search_claims(
        self,
        claims: Iterable[Any],
        prior_art: Iterable[Any],
        top_k: int = 5,
    ) -> Dict[int, List[Dict[str, Any]]]:

        results = {}

        for index, claim in enumerate(
            claims,
            start=1,
        ):

            if isinstance(
                claim,
                dict,
            ):

                number = claim.get(
                    "claim_number",
                    claim.get(
                        "number",
                        index,
                    ),
                )

            else:

                number = index

            try:
                number = int(
                    number
                )
            except Exception:
                number = index

            matches = (
                self.search_claim(
                    claim,
                    prior_art,
                    top_k=top_k,
                )
            )

            results[number] = [
                result.to_dict()
                for result
                in matches
            ]

        return results

    # -----------------------------------------------------------------
    # Health / diagnostics
    # -----------------------------------------------------------------

    def status(self) -> Dict[str, Any]:

        return {
            "engine_version":
                SEMANTIC_SEARCH_VERSION,

            "model":
                self.model_name,

            "semantic_available":
                self.backend.available,

            "backend_error":
                self.backend.error,

            "semantic_weight":
                self.semantic_weight,

            "lexical_weight":
                self.lexical_weight,

            "mode":
                (
                    "semantic+lexical"
                    if self.backend.available
                    else "lexical-fallback"
                ),
        }


# ---------------------------------------------------------------------
# Patent-specific search helpers
# ---------------------------------------------------------------------

def build_search_documents(
    prior_art: Iterable[Any],
) -> List[SearchDocument]:

    return normalize_documents(
        prior_art
    )


def semantic_search(
    query: str,
    documents: Iterable[Any],
    top_k: int = DEFAULT_TOP_K,
    model_name: str = DEFAULT_MODEL,
) -> List[Dict[str, Any]]:

    engine = (
        SemanticSearchEngine(
            model_name=model_name
        )
    )

    return [
        result.to_dict()
        for result
        in engine.search(
            query,
            documents,
            top_k=top_k,
        )
    ]


def semantic_claim_search(
    claim: Any,
    prior_art: Iterable[Any],
    top_k: int = DEFAULT_TOP_K,
    model_name: str = DEFAULT_MODEL,
) -> List[Dict[str, Any]]:

    engine = (
        SemanticSearchEngine(
            model_name=model_name
        )
    )

    return [
        result.to_dict()
        for result
        in engine.search_claim(
            claim,
            prior_art,
            top_k=top_k,
        )
    ]


# ---------------------------------------------------------------------
# Search result fusion
# ---------------------------------------------------------------------

def fuse_search_results(
    lexical_results: Iterable[Any],
    semantic_results: Iterable[Any],
    semantic_weight: float = 0.70,
    lexical_weight: float = 0.30,
    top_k: int = DEFAULT_TOP_K,
) -> List[Dict[str, Any]]:

    scores: Dict[
        str,
        Dict[str, Any]
    ] = {}

    def process(
        items: Iterable[Any],
        weight: float,
        result_type: str,
    ):

        for item in items:

            if isinstance(
                item,
                SemanticSearchResult,
            ):

                item = item.to_dict()

            if not isinstance(
                item,
                dict,
            ):
                continue

            document_id = _clean(
                item.get(
                    "document_id",
                    item.get(
                        "id",
                        "",
                    ),
                )
            )

            if not document_id:
                continue

            try:

                score = float(
                    item.get(
                        "score",
                        0.0,
                    )
                )

            except Exception:

                score = 0.0

            bucket = scores.setdefault(
                document_id,
                {
                    "document_id":
                        document_id,

                    "semantic_score":
                        0.0,

                    "lexical_score":
                        0.0,

                    "text":
                        item.get(
                            "text",
                            "",
                        ),

                    "title":
                        item.get(
                            "title",
                            "",
                        ),

                    "source":
                        item.get(
                            "source",
                            "",
                        ),

                    "metadata":
                        item.get(
                            "metadata",
                            {},
                        ),
                },
            )

            if result_type == "semantic":

                bucket[
                    "semantic_score"
                ] = max(
                    bucket[
                        "semantic_score"
                    ],
                    score,
                )

            else:

                bucket[
                    "lexical_score"
                ] = max(
                    bucket[
                        "lexical_score"
                    ],
                    score,
                )

    process(
        lexical_results,
        lexical_weight,
        "lexical",
    )

    process(
        semantic_results,
        semantic_weight,
        "semantic",
    )

    total_weight = (
        semantic_weight
        + lexical_weight
    )

    if total_weight <= 0:
        total_weight = 1.0

    for bucket in scores.values():

        bucket[
            "combined_score"
        ] = (
            semantic_weight
            * bucket[
                "semantic_score"
            ]
            + lexical_weight
            * bucket[
                "lexical_score"
            ]
        ) / total_weight

    ranked = sorted(
        scores.values(),
        key=lambda item: item[
            "combined_score"
        ],
        reverse=True,
    )

    for rank, item in enumerate(
        ranked[:top_k],
        start=1,
    ):

        item[
            "rank"
        ] = rank

    return ranked[:top_k]


# ---------------------------------------------------------------------
# Patent evidence retrieval
# ---------------------------------------------------------------------

def retrieve_prior_art(
    claim_text: str,
    prior_art: Iterable[Any],
    top_k: int = 10,
) -> Dict[str, Any]:

    engine = (
        SemanticSearchEngine()
    )

    results = engine.search(
        query=claim_text,
        documents=prior_art,
        top_k=top_k,
    )

    return {
        "query":
            claim_text,

        "engine":
            engine.status(),

        "results": [
            result.to_dict()
            for result
            in results
        ],

        "retrieval_notice":
            (
                "Retrieved documents are ranked by textual "
                "similarity. Similarity does not establish "
                "legal anticipation or inventive step."
            ),
    }


# ---------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------

def search_similar_documents(
    query: str,
    documents: Iterable[Any],
    top_k: int = DEFAULT_TOP_K,
) -> List[Dict[str, Any]]:

    return semantic_search(
        query=query,
        documents=documents,
        top_k=top_k,
    )


def find_similar_prior_art(
    claim_text: str,
    prior_art: Iterable[Any],
    top_k: int = DEFAULT_TOP_K,
) -> List[Dict[str, Any]]:

    return semantic_claim_search(
        claim=claim_text,
        prior_art=prior_art,
        top_k=top_k,
    )


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

__all__ = [
    "SEMANTIC_SEARCH_VERSION",
    "DEFAULT_MODEL",
    "DEFAULT_TOP_K",
    "SearchDocument",
    "SemanticSearchResult",
    "SearchExplanation",
    "EmbeddingBackend",
    "SemanticSearchEngine",
    "normalize_documents",
    "cosine_similarity",
    "lexical_similarity",
    "overlapping_terms",
    "semantic_search",
    "semantic_claim_search",
    "search_similar_documents",
    "find_similar_prior_art",
    "build_search_documents",
    "fuse_search_results",
    "retrieve_prior_art",
]
