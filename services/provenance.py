"""
services/provenance.py

Indian Patent Analyzer
Analysis provenance, audit trail, and reproducibility layer.

Version: 3.0.0

Purpose
-------
Track where every important analysis result came from:

    Document
        -> Parser
        -> Claims
        -> Search Queries
        -> Prior Art
        -> Evidence
        -> Verification
        -> Legal Rules
        -> AI Interpretation
        -> Report

Design principles
-----------------
1. Every important artifact gets a stable identifier.
2. Source hashes are retained whenever source text is available.
3. Pipeline stages are append-only from the application's perspective.
4. AI-generated content is explicitly marked as AI-derived.
5. External sources retain URLs and retrieval timestamps.
6. Provenance metadata does not itself establish legal conclusions.
7. The module has no database dependency.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


PROVENANCE_VERSION = "3.0.0"


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

SOURCE_DOCUMENT = "document"
SOURCE_PARSER = "parser"
SOURCE_CLAIM = "claim"
SOURCE_LIMITATION = "limitation"
SOURCE_SEARCH_QUERY = "search_query"
SOURCE_SEARCH_RESULT = "search_result"
SOURCE_PRIOR_ART = "prior_art"
SOURCE_EVIDENCE = "evidence"
SOURCE_VERIFICATION = "verification"
SOURCE_RULE = "rule"
SOURCE_SECTION3 = "section3"
SOURCE_NOVELTY = "novelty"
SOURCE_INVENTIVE_STEP = "inventive_step"
SOURCE_AMENDMENT = "amendment"
SOURCE_FER = "fer"
SOURCE_LEGAL_PROVISION = "legal_provision"
SOURCE_AI = "ai"
SOURCE_REPORT = "report"
SOURCE_PIPELINE = "pipeline"
SOURCE_USER = "user"
SOURCE_SYSTEM = "system"


DERIVATION_DETERMINISTIC = "deterministic"
DERIVATION_EXTERNAL = "external_source"
DERIVATION_AI = "ai_generated"
DERIVATION_USER = "user_supplied"
DERIVATION_IMPORTED = "imported"
DERIVATION_UNKNOWN = "unknown"


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(str(value).split()).strip()


def _normalize(value: Any) -> str:
    text = _clean(value).lower()

    text = re.sub(
        r"\s+",
        " ",
        text,
    )

    return text.strip()


def _stable_hash(*parts: Any) -> str:
    payload = "||".join(
        _normalize(part)
        for part in parts
    )

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def stable_id(
    prefix: str,
    *parts: Any,
) -> str:
    """
    Generate a deterministic identifier.

    Example:
        stable_id("DOC", document_sha256)
    """

    digest = _stable_hash(*parts)[:20]

    return f"{prefix.upper()}-{digest}"


def calculate_text_hash(
    text: Any,
) -> str:
    """
    Calculate SHA-256 for source text.
    """

    normalized = _clean(text)

    return hashlib.sha256(
        normalized.encode("utf-8")
    ).hexdigest()


def calculate_object_hash(
    value: Any,
) -> str:
    """
    Calculate a stable hash for a JSON-compatible object.
    """

    try:
        serialized = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    except Exception:
        serialized = str(value)

    return hashlib.sha256(
        serialized.encode("utf-8")
    ).hexdigest()


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


# ---------------------------------------------------------------------------
# Provenance records
# ---------------------------------------------------------------------------


@dataclass
class ProvenanceSource:
    """
    Describes the origin of an artifact.
    """

    source_id: str
    source_type: str

    title: str = ""
    uri: str = ""

    document_id: str = ""
    publication_number: str = ""

    source_hash: str = ""

    retrieved_at: str = ""
    published_at: str = ""
    priority_date: str = ""

    provider: str = ""

    derivation: str = DERIVATION_UNKNOWN

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProvenanceEvent:
    """
    One auditable operation in the analysis pipeline.
    """

    event_id: str

    timestamp: str

    event_type: str

    stage: str = ""

    artifact_id: str = ""

    parent_ids: List[str] = field(
        default_factory=list
    )

    source_ids: List[str] = field(
        default_factory=list
    )

    operation: str = ""

    actor: str = "system"

    version: str = PROVENANCE_VERSION

    input_hash: str = ""
    output_hash: str = ""

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    warnings: List[str] = field(
        default_factory=list
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProvenanceArtifact:
    """
    A derived analysis artifact.

    Examples:
        claim
        limitation
        search result
        evidence
        finding
        report
    """

    artifact_id: str
    artifact_type: str

    created_at: str

    title: str = ""

    source_ids: List[str] = field(
        default_factory=list
    )

    parent_ids: List[str] = field(
        default_factory=list
    )

    content_hash: str = ""

    derivation: str = DERIVATION_DETERMINISTIC

    version: str = PROVENANCE_VERSION

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class AnalysisManifest:
    """
    Top-level immutable-style analysis manifest.

    The manifest identifies the exact analysis execution and the
    relationships between artifacts.
    """

    analysis_id: str

    created_at: str

    analyzer_version: str = PROVENANCE_VERSION

    document_id: str = ""

    document_hash: str = ""

    input_hash: str = ""

    configuration_hash: str = ""

    source_ids: List[str] = field(
        default_factory=list
    )

    artifact_ids: List[str] = field(
        default_factory=list
    )

    event_ids: List[str] = field(
        default_factory=list
    )

    warnings: List[str] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    manifest_hash: str = ""

    def to_dict(
        self,
        include_hash: bool = True,
    ) -> Dict[str, Any]:

        data = asdict(self)

        if not include_hash:
            data.pop(
                "manifest_hash",
                None,
            )

        return data


# ---------------------------------------------------------------------------
# Provenance ledger
# ---------------------------------------------------------------------------


class ProvenanceLedger:
    """
    In-memory provenance ledger.

    The ledger is intentionally simple and serializable.

    Persistence can be added later through:
        document_store.py
        database
        object storage
        JSON export
    """

    def __init__(
        self,
        analysis_id: Optional[str] = None,
        analyzer_version: str = PROVENANCE_VERSION,
    ) -> None:

        self.analysis_id = (
            analysis_id
            or stable_id(
                "ANALYSIS",
                _utc_now(),
            )
        )

        self.analyzer_version = analyzer_version

        self.created_at = _utc_now()

        self.sources: Dict[
            str,
            ProvenanceSource,
        ] = {}

        self.artifacts: Dict[
            str,
            ProvenanceArtifact,
        ] = {}

        self.events: Dict[
            str,
            ProvenanceEvent,
        ] = {}

        self.warnings: List[str] = []

        self.document_id = ""
        self.document_hash = ""
        self.input_hash = ""
        self.configuration_hash = ""

    # ------------------------------------------------------------------
    # Sources
    # ------------------------------------------------------------------

    def register_source(
        self,
        source_type: str,
        title: str = "",
        uri: str = "",
        content: Any = "",
        document_id: str = "",
        publication_number: str = "",
        provider: str = "",
        derivation: str = DERIVATION_UNKNOWN,
        retrieved_at: str = "",
        published_at: str = "",
        priority_date: str = "",
        metadata: Optional[Mapping[str, Any]] = None,
        source_id: Optional[str] = None,
    ) -> ProvenanceSource:

        source_hash = ""

        if content not in (
            None,
            "",
        ):
            if isinstance(
                content,
                str,
            ):
                source_hash = calculate_text_hash(
                    content
                )
            else:
                source_hash = calculate_object_hash(
                    content
                )

        resolved_id = (
            source_id
            or stable_id(
                "SRC",
                source_type,
                uri,
                document_id,
                publication_number,
                source_hash,
            )
        )

        if resolved_id in self.sources:
            return self.sources[resolved_id]

        source = ProvenanceSource(
            source_id=resolved_id,
            source_type=_clean(source_type),
            title=_clean(title),
            uri=_clean(uri),
            document_id=_clean(document_id),
            publication_number=_clean(
                publication_number
            ),
            source_hash=source_hash,
            retrieved_at=(
                retrieved_at
                or _utc_now()
            ),
            published_at=_clean(
                published_at
            ),
            priority_date=_clean(
                priority_date
            ),
            provider=_clean(provider),
            derivation=_clean(derivation)
            or DERIVATION_UNKNOWN,
            metadata=dict(metadata or {}),
        )

        self.sources[
            resolved_id
        ] = source

        return source

    def register_document(
        self,
        document_id: str,
        document_hash: str,
        title: str = "",
        uri: str = "",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> ProvenanceSource:

        source = self.register_source(
            source_type=SOURCE_DOCUMENT,
            title=title,
            uri=uri,
            content=document_hash,
            document_id=document_id,
            derivation=DERIVATION_IMPORTED,
            metadata=metadata,
        )

        self.document_id = document_id
        self.document_hash = document_hash

        return source

    def get_source(
        self,
        source_id: str,
    ) -> Optional[ProvenanceSource]:

        return self.sources.get(source_id)

    # ------------------------------------------------------------------
    # Artifacts
    # ------------------------------------------------------------------

    def register_artifact(
        self,
        artifact_type: str,
        title: str = "",
        content: Any = "",
        source_ids: Optional[Sequence[str]] = None,
        parent_ids: Optional[Sequence[str]] = None,
        derivation: str = DERIVATION_DETERMINISTIC,
        metadata: Optional[Mapping[str, Any]] = None,
        artifact_id: Optional[str] = None,
    ) -> ProvenanceArtifact:

        content_hash = ""

        if content not in (
            None,
            "",
        ):
            content_hash = calculate_object_hash(
                content
            )

        resolved_id = (
            artifact_id
            or stable_id(
                "ART",
                artifact_type,
                content_hash,
                *(source_ids or []),
                *(parent_ids or []),
            )
        )

        if resolved_id in self.artifacts:
            return self.artifacts[
                resolved_id
            ]

        artifact = ProvenanceArtifact(
            artifact_id=resolved_id,
            artifact_type=_clean(
                artifact_type
            ),
            created_at=_utc_now(),
            title=_clean(title),
            source_ids=list(
                source_ids or []
            ),
            parent_ids=list(
                parent_ids or []
            ),
            content_hash=content_hash,
            derivation=_clean(
                derivation
            )
            or DERIVATION_UNKNOWN,
            version=self.analyzer_version,
            metadata=dict(
                metadata or {}
            ),
        )

        self.artifacts[
            resolved_id
        ] = artifact

        return artifact

    def get_artifact(
        self,
        artifact_id: str,
    ) -> Optional[ProvenanceArtifact]:

        return self.artifacts.get(
            artifact_id
        )

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def record_event(
        self,
        event_type: str,
        stage: str = "",
        artifact_id: str = "",
        parent_ids: Optional[Sequence[str]] = None,
        source_ids: Optional[Sequence[str]] = None,
        operation: str = "",
        actor: str = "system",
        input_data: Any = "",
        output_data: Any = "",
        metadata: Optional[Mapping[str, Any]] = None,
        warnings: Optional[Sequence[str]] = None,
        event_id: Optional[str] = None,
    ) -> ProvenanceEvent:

        input_hash = ""

        if input_data not in (
            None,
            "",
        ):
            input_hash = calculate_object_hash(
                input_data
            )

        output_hash = ""

        if output_data not in (
            None,
            "",
        ):
            output_hash = calculate_object_hash(
                output_data
            )

        resolved_id = (
            event_id
            or stable_id(
                "EVT",
                self.analysis_id,
                event_type,
                stage,
                artifact_id,
                input_hash,
                output_hash,
            )
        )

        if resolved_id in self.events:
            return self.events[
                resolved_id
            ]

        event = ProvenanceEvent(
            event_id=resolved_id,
            timestamp=_utc_now(),
            event_type=_clean(
                event_type
            ),
            stage=_clean(stage),
            artifact_id=_clean(
                artifact_id
            ),
            parent_ids=list(
                parent_ids or []
            ),
            source_ids=list(
                source_ids or []
            ),
            operation=_clean(
                operation
            ),
            actor=_clean(actor) or "system",
            version=self.analyzer_version,
            input_hash=input_hash,
            output_hash=output_hash,
            metadata=dict(
                metadata or {}
            ),
            warnings=list(
                warnings or []
            ),
        )

        self.events[
            resolved_id
        ] = event

        return event

    # ------------------------------------------------------------------
    # Analysis stages
    # ------------------------------------------------------------------

    def record_stage(
        self,
        stage: str,
        operation: str,
        input_data: Any = "",
        output_data: Any = "",
        artifact_id: str = "",
        source_ids: Optional[Sequence[str]] = None,
        parent_ids: Optional[Sequence[str]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
        warnings: Optional[Sequence[str]] = None,
    ) -> ProvenanceEvent:

        return self.record_event(
            event_type="pipeline_stage",
            stage=stage,
            artifact_id=artifact_id,
            parent_ids=parent_ids,
            source_ids=source_ids,
            operation=operation,
            input_data=input_data,
            output_data=output_data,
            metadata=metadata,
            warnings=warnings,
        )

    # ------------------------------------------------------------------
    # AI tracking
    # ------------------------------------------------------------------

    def record_ai_operation(
        self,
        operation: str,
        prompt: str,
        response: Any,
        model: str = "",
        artifact_id: str = "",
        source_ids: Optional[Sequence[str]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> ProvenanceEvent:

        ai_metadata = dict(
            metadata or {}
        )

        ai_metadata.update(
            {
                "model": _clean(model),
                "ai_generated": True,
                "prompt_hash": calculate_text_hash(
                    prompt
                ),
                "response_hash": calculate_object_hash(
                    response
                ),
            }
        )

        return self.record_event(
            event_type="ai_operation",
            stage="ai",
            artifact_id=artifact_id,
            source_ids=source_ids,
            operation=operation,
            actor="ai",
            input_data=prompt,
            output_data=response,
            metadata=ai_metadata,
        )

    # ------------------------------------------------------------------
    # Search tracking
    # ------------------------------------------------------------------

    def record_search(
        self,
        query: str,
        provider: str,
        results: Any = "",
        source_ids: Optional[Sequence[str]] = None,
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> ProvenanceEvent:

        search_metadata = dict(
            metadata or {}
        )

        search_metadata.update(
            {
                "query": query,
                "provider": provider,
                "result_count": (
                    len(results)
                    if isinstance(
                        results,
                        (list, tuple)
                    )
                    else None
                ),
            }
        )

        return self.record_event(
            event_type="search",
            stage="prior_art_search",
            source_ids=source_ids,
            operation="patent_search",
            actor="system",
            input_data=query,
            output_data=results,
            metadata=search_metadata,
        )

    # ------------------------------------------------------------------
    # Warnings
    # ------------------------------------------------------------------

    def add_warning(
        self,
        warning: str,
    ) -> None:

        warning = _clean(warning)

        if warning and warning not in self.warnings:
            self.warnings.append(
                warning
            )

    # ------------------------------------------------------------------
    # Manifest
    # ------------------------------------------------------------------

    def build_manifest(
        self,
        input_data: Any = "",
        configuration: Any = "",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> AnalysisManifest:

        self.input_hash = (
            calculate_object_hash(
                input_data
            )
            if input_data not in (
                None,
                "",
            )
            else ""
        )

        self.configuration_hash = (
            calculate_object_hash(
                configuration
            )
            if configuration not in (
                None,
                "",
            )
            else ""
        )

        manifest = AnalysisManifest(
            analysis_id=self.analysis_id,
            created_at=self.created_at,
            analyzer_version=self.analyzer_version,
            document_id=self.document_id,
            document_hash=self.document_hash,
            input_hash=self.input_hash,
            configuration_hash=self.configuration_hash,
            source_ids=sorted(
                self.sources.keys()
            ),
            artifact_ids=sorted(
                self.artifacts.keys()
            ),
            event_ids=sorted(
                self.events.keys()
            ),
            warnings=list(
                self.warnings
            ),
            metadata=dict(
                metadata or {}
            ),
        )

        manifest.manifest_hash = (
            calculate_object_hash(
                manifest.to_dict(
                    include_hash=False
                )
            )
        )

        return manifest

    def snapshot(
        self,
        input_data: Any = "",
        configuration: Any = "",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> Dict[str, Any]:

        manifest = self.build_manifest(
            input_data=input_data,
            configuration=configuration,
            metadata=metadata,
        )

        return {
            "version": PROVENANCE_VERSION,
            "manifest": manifest.to_dict(),
            "sources": [
                source.to_dict()
                for source in self.sources.values()
            ],
            "artifacts": [
                artifact.to_dict()
                for artifact in self.artifacts.values()
            ],
            "events": [
                event.to_dict()
                for event in self.events.values()
            ],
        }

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def validate(
        self,
    ) -> Dict[str, Any]:

        errors: List[str] = []
        warnings: List[str] = []

        source_ids = set(
            self.sources.keys()
        )

        artifact_ids = set(
            self.artifacts.keys()
        )

        for artifact in self.artifacts.values():

            for source_id in artifact.source_ids:
                if source_id not in source_ids:
                    errors.append(
                        f"Artifact {artifact.artifact_id} "
                        f"references missing source "
                        f"{source_id}."
                    )

            for parent_id in artifact.parent_ids:
                if parent_id not in artifact_ids:
                    warnings.append(
                        f"Artifact {artifact.artifact_id} "
                        f"references missing parent "
                        f"{parent_id}."
                    )

        for event in self.events.values():

            if (
                event.artifact_id
                and event.artifact_id
                not in artifact_ids
            ):
                warnings.append(
                    f"Event {event.event_id} references "
                    f"missing artifact "
                    f"{event.artifact_id}."
                )

            for source_id in event.source_ids:
                if source_id not in source_ids:
                    errors.append(
                        f"Event {event.event_id} "
                        f"references missing source "
                        f"{source_id}."
                    )

        if not self.document_id:
            warnings.append(
                "No document_id registered."
            )

        if not self.document_hash:
            warnings.append(
                "No document hash registered."
            )

        return {
            "valid": len(errors) == 0,
            "error_count": len(errors),
            "warning_count": len(warnings),
            "errors": errors,
            "warnings": warnings,
        }


# ---------------------------------------------------------------------------
# High-level provenance manager
# ---------------------------------------------------------------------------


class ProvenanceManager:
    """
    Convenient façade over ProvenanceLedger.
    """

    def __init__(
        self,
        analysis_id: Optional[str] = None,
        analyzer_version: str = PROVENANCE_VERSION,
    ) -> None:

        self.ledger = ProvenanceLedger(
            analysis_id=analysis_id,
            analyzer_version=analyzer_version,
        )

    @property
    def analysis_id(self) -> str:
        return self.ledger.analysis_id

    def register_document(
        self,
        document_id: str,
        document_hash: str,
        title: str = "",
        uri: str = "",
        metadata: Optional[Mapping[str, Any]] = None,
    ) -> ProvenanceSource:

        return self.ledger.register_document(
            document_id=document_id,
            document_hash=document_hash,
            title=title,
            uri=uri,
            metadata=metadata,
        )

    def register_source(
        self,
        **kwargs: Any,
    ) -> ProvenanceSource:

        return self.ledger.register_source(
            **kwargs
        )

    def register_artifact(
        self,
        **kwargs: Any,
    ) -> ProvenanceArtifact:

        return self.ledger.register_artifact(
            **kwargs
        )

    def record_stage(
        self,
        **kwargs: Any,
    ) -> ProvenanceEvent:

        return self.ledger.record_stage(
            **kwargs
        )

    def record_ai(
        self,
        **kwargs: Any,
    ) -> ProvenanceEvent:

        return self.ledger.record_ai_operation(
            **kwargs
        )

    def record_search(
        self,
        **kwargs: Any,
    ) -> ProvenanceEvent:

        return self.ledger.record_search(
            **kwargs
        )

    def add_warning(
        self,
        warning: str,
    ) -> None:

        self.ledger.add_warning(
            warning
        )

    def snapshot(
        self,
        **kwargs: Any,
    ) -> Dict[str, Any]:

        return self.ledger.snapshot(
            **kwargs
        )

    def validate(self) -> Dict[str, Any]:

        return self.ledger.validate()


# ---------------------------------------------------------------------------
# Provenance query helpers
# ---------------------------------------------------------------------------


def get_artifact_lineage(
    snapshot: Mapping[str, Any],
    artifact_id: str,
) -> Dict[str, Any]:

    artifacts = {
        item.get("artifact_id"): item
        for item in snapshot.get(
            "artifacts",
            []
        )
        if isinstance(item, Mapping)
    }

    sources = {
        item.get("source_id"): item
        for item in snapshot.get(
            "sources",
            []
        )
        if isinstance(item, Mapping)
    }

    events = [
        item
        for item in snapshot.get(
            "events",
            []
        )
        if isinstance(item, Mapping)
    ]

    artifact = artifacts.get(
        artifact_id
    )

    if not artifact:
        return {
            "artifact_id": artifact_id,
            "found": False,
            "parents": [],
            "sources": [],
            "events": [],
        }

    parent_ids = list(
        artifact.get(
            "parent_ids",
            [],
        )
    )

    source_ids = list(
        artifact.get(
            "source_ids",
            [],
        )
    )

    related_events = [
        event
        for event in events
        if (
            event.get("artifact_id")
            == artifact_id
        )
        or artifact_id in event.get(
            "parent_ids",
            [],
        )
    ]

    return {
        "artifact_id": artifact_id,
        "found": True,
        "artifact": artifact,
        "parents": [
            artifacts[parent_id]
            for parent_id in parent_ids
            if parent_id in artifacts
        ],
        "sources": [
            sources[source_id]
            for source_id in source_ids
            if source_id in sources
        ],
        "events": related_events,
    }


def find_events_by_stage(
    snapshot: Mapping[str, Any],
    stage: str,
) -> List[Dict[str, Any]]:

    return [
        dict(event)
        for event in snapshot.get(
            "events",
            []
        )
        if (
            _normalize(
                event.get("stage")
            )
            == _normalize(stage)
        )
    ]


def find_events_by_artifact(
    snapshot: Mapping[str, Any],
    artifact_id: str,
) -> List[Dict[str, Any]]:

    return [
        dict(event)
        for event in snapshot.get(
            "events",
            []
        )
        if event.get(
            "artifact_id"
        ) == artifact_id
    ]


def find_source(
    snapshot: Mapping[str, Any],
    source_id: str,
) -> Optional[Dict[str, Any]]:

    for source in snapshot.get(
        "sources",
        [],
    ):

        if source.get(
            "source_id"
        ) == source_id:
            return dict(source)

    return None


# ---------------------------------------------------------------------------
# Integrity verification
# ---------------------------------------------------------------------------


def verify_manifest_integrity(
    snapshot: Mapping[str, Any],
) -> Dict[str, Any]:

    manifest = snapshot.get(
        "manifest"
    )

    if not isinstance(
        manifest,
        Mapping,
    ):
        return {
            "valid": False,
            "reason": "Manifest missing.",
        }

    stored_hash = _clean(
        manifest.get(
            "manifest_hash"
        )
    )

    if not stored_hash:
        return {
            "valid": False,
            "reason": "Manifest hash missing.",
        }

    manifest_copy = dict(
        manifest
    )

    manifest_copy.pop(
        "manifest_hash",
        None,
    )

    calculated_hash = calculate_object_hash(
        manifest_copy
    )

    return {
        "valid": (
            calculated_hash
            == stored_hash
        ),
        "stored_hash": stored_hash,
        "calculated_hash": calculated_hash,
    }


def verify_artifact_integrity(
    artifact: Mapping[str, Any],
    content: Any,
) -> Dict[str, Any]:

    expected_hash = _clean(
        artifact.get(
            "content_hash"
        )
    )

    calculated_hash = calculate_object_hash(
        content
    )

    return {
        "artifact_id": artifact.get(
            "artifact_id"
        ),
        "valid": (
            not expected_hash
            or expected_hash
            == calculated_hash
        ),
        "expected_hash": expected_hash,
        "calculated_hash": calculated_hash,
    }


# ---------------------------------------------------------------------------
# Serialization
# ---------------------------------------------------------------------------


def serialize_provenance(
    snapshot: Mapping[str, Any],
    indent: int = 2,
) -> str:

    return json.dumps(
        snapshot,
        ensure_ascii=False,
        indent=indent,
        default=str,
    )


def deserialize_provenance(
    serialized: str,
) -> Dict[str, Any]:

    value = json.loads(
        serialized
    )

    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            "Invalid provenance snapshot."
        )

    return value


def save_provenance_json(
    snapshot: Mapping[str, Any],
    path: str,
) -> str:

    with open(
        path,
        "w",
        encoding="utf-8",
    ) as handle:

        json.dump(
            snapshot,
            handle,
            ensure_ascii=False,
            indent=2,
            default=str,
        )

    return path


def load_provenance_json(
    path: str,
) -> Dict[str, Any]:

    with open(
        path,
        "r",
        encoding="utf-8",
    ) as handle:

        value = json.load(
            handle
        )

    if not isinstance(
        value,
        dict,
    ):
        raise ValueError(
            "Invalid provenance JSON."
        )

    return value


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def create_provenance_manager(
    analysis_id: Optional[str] = None,
    analyzer_version: str = PROVENANCE_VERSION,
) -> ProvenanceManager:

    return ProvenanceManager(
        analysis_id=analysis_id,
        analyzer_version=analyzer_version,
    )


def create_provenance_ledger(
    analysis_id: Optional[str] = None,
    analyzer_version: str = PROVENANCE_VERSION,
) -> ProvenanceLedger:

    return ProvenanceLedger(
        analysis_id=analysis_id,
        analyzer_version=analyzer_version,
    )


def build_document_provenance(
    document_id: str,
    document_hash: str,
    title: str = "",
    uri: str = "",
    metadata: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:

    manager = ProvenanceManager()

    manager.register_document(
        document_id=document_id,
        document_hash=document_hash,
        title=title,
        uri=uri,
        metadata=metadata,
    )

    return manager.snapshot()


def provenance_statistics(
    snapshot: Mapping[str, Any],
) -> Dict[str, Any]:

    sources = snapshot.get(
        "sources",
        []
    )

    artifacts = snapshot.get(
        "artifacts",
        []
    )

    events = snapshot.get(
        "events",
        []
    )

    derivations: Dict[str, int] = {}

    for artifact in artifacts:
        derivation = (
            artifact.get(
                "derivation"
            )
            or DERIVATION_UNKNOWN
        )

        derivations[
            derivation
        ] = (
            derivations.get(
                derivation,
                0,
            )
            + 1
        )

    return {
        "version": PROVENANCE_VERSION,
        "analysis_id": (
            snapshot.get(
                "manifest",
                {},
            ).get(
                "analysis_id"
            )
        ),
        "source_count": len(
            sources
        ),
        "artifact_count": len(
            artifacts
        ),
        "event_count": len(
            events
        ),
        "artifact_derivations": derivations,
        "integrity": verify_manifest_integrity(
            snapshot
        ),
    }


# ---------------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------------


AuditTrail = ProvenanceLedger
Provenance = ProvenanceManager
ProvenanceRecord = ProvenanceEvent


def create_audit_trail(
    analysis_id: Optional[str] = None,
    analyzer_version: str = PROVENANCE_VERSION,
) -> ProvenanceLedger:

    return create_provenance_ledger(
        analysis_id=analysis_id,
        analyzer_version=analyzer_version,
    )


def calculate_hash(
    value: Any,
) -> str:

    if isinstance(
        value,
        str,
    ):
        return calculate_text_hash(
            value
        )

    return calculate_object_hash(
        value
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


__all__ = [
    "PROVENANCE_VERSION",

    "SOURCE_DOCUMENT",
    "SOURCE_PARSER",
    "SOURCE_CLAIM",
    "SOURCE_LIMITATION",
    "SOURCE_SEARCH_QUERY",
    "SOURCE_SEARCH_RESULT",
    "SOURCE_PRIOR_ART",
    "SOURCE_EVIDENCE",
    "SOURCE_VERIFICATION",
    "SOURCE_RULE",
    "SOURCE_SECTION3",
    "SOURCE_NOVELTY",
    "SOURCE_INVENTIVE_STEP",
    "SOURCE_AMENDMENT",
    "SOURCE_FER",
    "SOURCE_LEGAL_PROVISION",
    "SOURCE_AI",
    "SOURCE_REPORT",
    "SOURCE_PIPELINE",
    "SOURCE_USER",
    "SOURCE_SYSTEM",

    "DERIVATION_DETERMINISTIC",
    "DERIVATION_EXTERNAL",
    "DERIVATION_AI",
    "DERIVATION_USER_SUPPLIED",
    "DERIVATION_IMPORTED",
    "DERIVATION_UNKNOWN",

    "ProvenanceSource",
    "ProvenanceEvent",
    "ProvenanceArtifact",
    "AnalysisManifest",

    "stable_id",
    "calculate_text_hash",
    "calculate_object_hash",

    "ProvenanceLedger",
    "ProvenanceManager",

    "get_artifact_lineage",
    "find_events_by_stage",
    "find_events_by_artifact",
    "find_source",

    "verify_manifest_integrity",
    "verify_artifact_integrity",

    "serialize_provenance",
    "deserialize_provenance",
    "save_provenance_json",
    "load_provenance_json",

    "create_provenance_manager",
    "create_provenance_ledger",
    "build_document_provenance",
    "provenance_statistics",

    "AuditTrail",
    "Provenance",
    "ProvenanceRecord",
    "create_audit_trail",
    "calculate_hash",
]
