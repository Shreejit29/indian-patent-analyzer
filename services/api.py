"""
services/api.py

Indian Patent Analyzer
Unified application service/API layer.

Version: 3.0.0

Purpose
-------
Expose a stable interface between the user interface and the analysis
backend.

Architecture
------------

    UI / Streamlit / REST / CLI
                |
                v
          PatentAnalyzerAPI
                |
        +-------+--------+
        |                |
        v                v
  Analysis Pipeline   Validation
        |
        +-------------------------------+
        |        |       |       |      |
      Claims   PriorArt  FER    Graph  Scoring
        |
        v
      Report

Design principles
-----------------
1. UI should not directly orchestrate internal services.
2. Analysis should remain deterministic by default.
3. AI is optional and explicitly enabled.
4. Validation occurs before report generation.
5. Provenance is retained.
6. Errors are returned as structured objects.
7. This module does not make legal conclusions.
"""

from __future__ import annotations

import hashlib
import json
import os
import traceback
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, BinaryIO, Dict, List, Mapping, Optional, Sequence, Union


API_VERSION = "3.0.0"


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    if value is None:
        return ""

    return " ".join(str(value).split()).strip()


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _stable_hash(value: Any) -> str:
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )
    except Exception:
        payload = str(value)

    return hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()


def _stable_id(
    prefix: str,
    *parts: Any,
) -> str:

    payload = "||".join(
        _clean(part)
        for part in parts
    )

    digest = hashlib.sha256(
        payload.encode("utf-8")
    ).hexdigest()[:18]

    return f"{prefix.upper()}-{digest}"


def _to_dict(value: Any) -> Any:
    """
    Convert dataclasses and compatible objects into dictionaries.
    """

    if value is None:
        return None

    if isinstance(
        value,
        Mapping,
    ):
        return {
            key: _to_dict(item)
            for key, item in value.items()
        }

    if isinstance(
        value,
        (list, tuple),
    ):
        return [
            _to_dict(item)
            for item in value
        ]

    if hasattr(
        value,
        "to_dict",
    ):
        try:
            return _to_dict(
                value.to_dict()
            )
        except Exception:
            pass

    try:
        return asdict(value)
    except Exception:
        pass

    return value


def _extract_result_dict(
    value: Any,
) -> Dict[str, Any]:

    result = _to_dict(
        value
    )

    if isinstance(
        result,
        Mapping,
    ):
        return dict(result)

    return {
        "result": result
    }


# ---------------------------------------------------------------------------
# API data models
# ---------------------------------------------------------------------------


@dataclass
class APIError:
    """
    Structured API error.
    """

    error_id: str

    code: str

    message: str

    stage: str = ""

    details: Dict[str, Any] = field(
        default_factory=dict
    )

    recoverable: bool = True

    timestamp: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class APIResponse:
    """
    Standard response envelope used by the UI/API layer.
    """

    success: bool

    request_id: str

    timestamp: str

    data: Dict[str, Any] = field(
        default_factory=dict
    )

    errors: List[APIError] = field(
        default_factory=list
    )

    warnings: List[str] = field(
        default_factory=list
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "request_id": self.request_id,
            "timestamp": self.timestamp,
            "data": self.data,
            "errors": [
                error.to_dict()
                for error in self.errors
            ],
            "warnings": list(
                self.warnings
            ),
            "metadata": dict(
                self.metadata
            ),
        }


@dataclass
class AnalysisRequest:
    """
    Request object for patent analysis.
    """

    source: Any = None

    filename: str = ""

    enable_ai: bool = False

    generate_report: bool = True

    report_format: str = "html"

    include_prior_art: bool = True

    include_fer: bool = True

    include_amendments: bool = True

    include_knowledge_graph: bool = True

    validate_output: bool = True

    strict_validation: bool = False

    configuration: Dict[str, Any] = field(
        default_factory=dict
    )

    metadata: Dict[str, Any] = field(
        default_factory=dict
    )


# ---------------------------------------------------------------------------
# API
# ---------------------------------------------------------------------------


class PatentAnalyzerAPI:
    """
    Main application API.

    This class provides stable methods for:

        analyze()
        parse()
        analyze_claims()
        search()
        verify_evidence()
        analyze_fer()
        compare_amendments()
        generate_report()
        validate()
        health()
    """

    def __init__(
        self,
        pipeline: Any = None,
        validator: Any = None,
        search_registry: Any = None,
        provenance_manager: Any = None,
    ) -> None:

        self.pipeline = pipeline
        self.validator = validator
        self.search_registry = search_registry
        self.provenance_manager = provenance_manager

        self._initialize_dependencies()

    # ------------------------------------------------------------------
    # Dependency initialization
    # ------------------------------------------------------------------

    def _initialize_dependencies(
        self,
    ) -> None:

        if self.pipeline is None:

            try:
                from .analysis_pipeline import (
                    PatentAnalysisPipeline,
                )

                self.pipeline = (
                    PatentAnalysisPipeline()
                )

            except Exception:
                self.pipeline = None

        if self.validator is None:

            try:
                from .validation import (
                    PatentAnalysisValidator,
                )

                self.validator = (
                    PatentAnalysisValidator()
                )

            except Exception:
                self.validator = None

        if self.search_registry is None:

            try:
                from .search_providers import (
                    build_provider_registry,
                )

                self.search_registry = (
                    build_provider_registry()
                )

            except Exception:
                self.search_registry = None

        if self.provenance_manager is None:

            try:
                from .provenance import (
                    ProvenanceManager,
                )

                self.provenance_manager = (
                    ProvenanceManager()
                )

            except Exception:
                self.provenance_manager = None

    # ------------------------------------------------------------------
    # Request handling
    # ------------------------------------------------------------------

    def _request_id(
        self,
    ) -> str:

        return (
            "REQ-"
            + uuid.uuid4().hex[:16]
        )

    def _success(
        self,
        request_id: str,
        data: Optional[Mapping[str, Any]] = None,
        warnings: Optional[
            Sequence[str]
        ] = None,
        metadata: Optional[
            Mapping[str, Any]
        ] = None,
    ) -> APIResponse:

        return APIResponse(
            success=True,
            request_id=request_id,
            timestamp=_utc_now(),
            data=dict(
                data or {}
            ),
            warnings=list(
                warnings or []
            ),
            metadata={
                "api_version": API_VERSION,
                **dict(
                    metadata or {}
                ),
            },
        )

    def _failure(
        self,
        request_id: str,
        code: str,
        message: str,
        stage: str = "",
        details: Optional[
            Mapping[str, Any]
        ] = None,
        recoverable: bool = True,
        warnings: Optional[
            Sequence[str]
        ] = None,
    ) -> APIResponse:

        error = APIError(
            error_id=_stable_id(
                "ERR",
                request_id,
                code,
                message,
            ),
            code=code,
            message=message,
            stage=stage,
            details=dict(
                details or {}
            ),
            recoverable=recoverable,
            timestamp=_utc_now(),
        )

        return APIResponse(
            success=False,
            request_id=request_id,
            timestamp=_utc_now(),
            data={},
            errors=[error],
            warnings=list(
                warnings or []
            ),
            metadata={
                "api_version": API_VERSION,
            },
        )

    # ------------------------------------------------------------------
    # Main analysis
    # ------------------------------------------------------------------

    def analyze(
        self,
        request: Optional[
            Union[
                AnalysisRequest,
                Mapping[str, Any],
            ]
        ] = None,
        **kwargs: Any,
    ) -> APIResponse:

        request_id = self._request_id()

        try:

            request_obj = self._normalize_request(
                request,
                **kwargs,
            )

            if request_obj.source is None:
                return self._failure(
                    request_id=request_id,
                    code="MISSING_SOURCE",
                    message=(
                        "No patent document or analysis source "
                        "was supplied."
                    ),
                    stage="request_validation",
                    recoverable=True,
                )

            if self.pipeline is None:
                return self._failure(
                    request_id=request_id,
                    code="PIPELINE_UNAVAILABLE",
                    message=(
                        "Patent analysis pipeline could not "
                        "be initialized."
                    ),
                    stage="initialization",
                    recoverable=False,
                )

            pipeline_result = self._run_pipeline(
                request_obj
            )

            analysis = _extract_result_dict(
                pipeline_result
            )

            warnings: List[str] = []

            warnings.extend(
                self._extract_warnings(
                    analysis
                )
            )

            validation_result = None

            if request_obj.validate_output:

                validation_result = (
                    self._validate_analysis(
                        analysis,
                        strict=(
                            request_obj
                            .strict_validation
                        ),
                    )
                )

                analysis[
                    "validation"
                ] = _to_dict(
                    validation_result
                )

                if isinstance(
                    validation_result,
                    Mapping,
                ):

                    warnings.extend(
                        self._validation_warnings(
                            validation_result
                        )
                    )

            if request_obj.generate_report:

                report = self._generate_report(
                    analysis,
                    request_obj.report_format,
                )

                if report is not None:
                    analysis[
                        "report"
                    ] = _extract_result_dict(
                        report
                    )

            analysis[
                "api_metadata"
            ] = {
                "api_version": API_VERSION,
                "request_id": request_id,
                "analysis_timestamp": _utc_now(),
                "filename": request_obj.filename,
            }

            return self._success(
                request_id=request_id,
                data=analysis,
                warnings=warnings,
                metadata={
                    "analysis_completed": True,
                },
            )

        except Exception as exc:

            return self._failure(
                request_id=request_id,
                code="ANALYSIS_FAILED",
                message=str(exc),
                stage="analysis",
                details={
                    "exception_type": type(
                        exc
                    ).__name__,
                    "traceback": traceback.format_exc(),
                },
                recoverable=True,
            )

    # ------------------------------------------------------------------
    # Pipeline invocation
    # ------------------------------------------------------------------

    def _run_pipeline(
        self,
        request: AnalysisRequest,
    ) -> Any:

        options = dict(
            request.configuration
        )

        options.update(
            {
                "enable_ai": request.enable_ai,
                "include_prior_art": (
                    request.include_prior_art
                ),
                "include_fer": (
                    request.include_fer
                ),
                "include_amendments": (
                    request.include_amendments
                ),
                "include_knowledge_graph": (
                    request.include_knowledge_graph
                ),
            }
        )

        if hasattr(
            self.pipeline,
            "run",
        ):

            return self.pipeline.run(
                source=request.source,
                **options,
            )

        if hasattr(
            self.pipeline,
            "analyze",
        ):

            return self.pipeline.analyze(
                source=request.source,
                **options,
            )

        # Existing compatibility function.
        from .analysis_pipeline import (
            run_analysis_pipeline,
        )

        return run_analysis_pipeline(
            source=request.source,
            **options,
        )

    # ------------------------------------------------------------------
    # Request normalization
    # ------------------------------------------------------------------

    def _normalize_request(
        self,
        request: Optional[
            Union[
                AnalysisRequest,
                Mapping[str, Any],
            ]
        ],
        **kwargs: Any,
    ) -> AnalysisRequest:

        if isinstance(
            request,
            AnalysisRequest,
        ):

            if kwargs:
                values = asdict(
                    request
                )
                values.update(
                    kwargs
                )

                return AnalysisRequest(
                    **values
                )

            return request

        if isinstance(
            request,
            Mapping,
        ):

            values = dict(
                request
            )

            values.update(
                kwargs
            )

            return AnalysisRequest(
                **{
                    key: value
                    for key, value in values.items()
                    if key in {
                        "source",
                        "filename",
                        "enable_ai",
                        "generate_report",
                        "report_format",
                        "include_prior_art",
                        "include_fer",
                        "include_amendments",
                        "include_knowledge_graph",
                        "validate_output",
                        "strict_validation",
                        "configuration",
                        "metadata",
                    }
                }
            )

        values = dict(
            kwargs
        )

        if request is not None:
            values[
                "source"
            ] = request

        return AnalysisRequest(
            **{
                key: value
                for key, value in values.items()
                if key in {
                    "source",
                    "filename",
                    "enable_ai",
                    "generate_report",
                    "report_format",
                    "include_prior_art",
                    "include_fer",
                    "include_amendments",
                    "include_knowledge_graph",
                    "validate_output",
                    "strict_validation",
                    "configuration",
                    "metadata",
                }
            }
        )

    # ------------------------------------------------------------------
    # Parsing API
    # ------------------------------------------------------------------

    def parse(
        self,
        source: Any,
        **kwargs: Any,
    ) -> APIResponse:

        request_id = self._request_id()

        try:

            from .document_parser import (
                parse_document,
            )

            result = parse_document(
                source,
                **kwargs,
            )

            return self._success(
                request_id,
                data={
                    "document": _extract_result_dict(
                        result
                    )
                },
            )

        except Exception as exc:

            return self._failure(
                request_id,
                "PARSE_FAILED",
                str(exc),
                stage="document_parser",
                details={
                    "exception_type": type(
                        exc
                    ).__name__,
                },
            )

    # ------------------------------------------------------------------
    # Claim API
    # ------------------------------------------------------------------

    def analyze_claims(
        self,
        claims: Any,
        **kwargs: Any,
    ) -> APIResponse:

        request_id = self._request_id()

        try:

            from .claim_analyzer import (
                analyze_claims,
            )

            result = analyze_claims(
                claims,
                **kwargs,
            )

            return self._success(
                request_id,
                data={
                    "claims": _to_dict(
                        result
                    )
                },
            )

        except ImportError:

            try:

                from .claim_analyzer import (
                    ClaimAnalyzer,
                )

                analyzer = (
                    ClaimAnalyzer()
                )

                result = analyzer.analyze(
                    claims,
                    **kwargs,
                )

                return self._success(
                    request_id,
                    data={
                        "claims": _to_dict(
                            result
                        )
                    },
                )

            except Exception as exc:

                return self._failure(
                    request_id,
                    "CLAIM_ANALYSIS_FAILED",
                    str(exc),
                    stage="claim_analyzer",
                )

        except Exception as exc:

            return self._failure(
                request_id,
                "CLAIM_ANALYSIS_FAILED",
                str(exc),
                stage="claim_analyzer",
            )

    # ------------------------------------------------------------------
    # Search API
    # ------------------------------------------------------------------

    def search(
        self,
        query: str,
        provider: Optional[str] = None,
        providers: Optional[
            Sequence[str]
        ] = None,
        max_results: int = 20,
        **kwargs: Any,
    ) -> APIResponse:

        request_id = self._request_id()

        query = _clean(
            query
        )

        if not query:
            return self._failure(
                request_id,
                "EMPTY_QUERY",
                "Patent search query is empty.",
                stage="search",
            )

        try:

            if self.search_registry is None:
                return self._failure(
                    request_id,
                    "SEARCH_UNAVAILABLE",
                    (
                        "Patent search provider registry "
                        "is unavailable."
                    ),
                    stage="search",
                )

            if provider:

                response = (
                    self.search_registry.search(
                        provider_name=provider,
                        query=query,
                        max_results=max_results,
                        **kwargs,
                    )
                )

                return self._success(
                    request_id,
                    data={
                        "provider": provider,
                        "query": query,
                        "response": _to_dict(
                            response
                        ),
                    },
                )

            responses = (
                self.search_registry.search_all(
                    query=query,
                    provider_names=providers,
                    max_results=max_results,
                )
            )

            return self._success(
                request_id,
                data={
                    "query": query,
                    "responses": _to_dict(
                        responses
                    ),
                },
            )

        except Exception as exc:

            return self._failure(
                request_id,
                "SEARCH_FAILED",
                str(exc),
                stage="search",
                details={
                    "query": query,
                },
            )

    # ------------------------------------------------------------------
    # Evidence verification API
    # ------------------------------------------------------------------

    def verify_evidence(
        self,
        limitation_text: str,
        evidence: Sequence[Any],
        limitation_id: str = "",
        claim_number: Optional[int] = None,
    ) -> APIResponse:

        request_id = self._request_id()

        try:

            from .evidence_verifier import (
                verify_limitation,
            )

            result = verify_limitation(
                limitation_text=limitation_text,
                evidence=evidence,
                limitation_id=limitation_id,
                claim_number=claim_number,
            )

            return self._success(
                request_id,
                data={
                    "verification": _to_dict(
                        result
                    )
                },
            )

        except Exception as exc:

            return self._failure(
                request_id,
                "EVIDENCE_VERIFICATION_FAILED",
                str(exc),
                stage="evidence_verifier",
            )

    # ------------------------------------------------------------------
    # FER API
    # ------------------------------------------------------------------

    def analyze_fer(
        self,
        fer_source: Any,
        **kwargs: Any,
    ) -> APIResponse:

        request_id = self._request_id()

        try:

            from .fer_analyzer import (
                analyze_fer,
            )

            result = analyze_fer(
                fer_source,
                **kwargs,
            )

            return self._success(
                request_id,
                data={
                    "fer": _to_dict(
                        result
                    )
                },
            )

        except Exception as exc:

            return self._failure(
                request_id,
                "FER_ANALYSIS_FAILED",
                str(exc),
                stage="fer_analyzer",
            )

    # ------------------------------------------------------------------
    # Amendment API
    # ------------------------------------------------------------------

    def compare_amendments(
        self,
        original_claims: Any,
        amended_claims: Any,
        **kwargs: Any,
    ) -> APIResponse:

        request_id = self._request_id()

        try:

            from .amendment_analyzer import (
                compare_claim_versions,
            )

            result = compare_claim_versions(
                original_claims,
                amended_claims,
                **kwargs,
            )

            return self._success(
                request_id,
                data={
                    "amendments": _to_dict(
                        result
                    )
                },
            )

        except Exception as exc:

            return self._failure(
                request_id,
                "AMENDMENT_ANALYSIS_FAILED",
                str(exc),
                stage="amendment_analyzer",
            )

    # ------------------------------------------------------------------
    # Section 3 API
    # ------------------------------------------------------------------

    def analyze_section3(
        self,
        claims: Any,
        specification: Any = None,
        **kwargs: Any,
    ) -> APIResponse:

        request_id = self._request_id()

        try:

            from .section3_analyzer import (
                analyze_section_3,
            )

            result = analyze_section_3(
                claims=claims,
                specification=specification,
                **kwargs,
            )

            return self._success(
                request_id,
                data={
                    "section3": _to_dict(
                        result
                    )
                },
            )

        except Exception as exc:

            return self._failure(
                request_id,
                "SECTION3_ANALYSIS_FAILED",
                str(exc),
                stage="section3_analyzer",
            )

    # ------------------------------------------------------------------
    # Novelty API
    # ------------------------------------------------------------------

    def analyze_novelty(
        self,
        claims: Any,
        prior_art: Any,
        evidence: Any = None,
        **kwargs: Any,
    ) -> APIResponse:

        request_id = self._request_id()

        try:

            from .novelty_analyzer import (
                analyze_novelty,
            )

            result = analyze_novelty(
                claims=claims,
                prior_art=prior_art,
                evidence=evidence,
                **kwargs,
            )

            return self._success(
                request_id,
                data={
                    "novelty": _to_dict(
                        result
                    )
                },
            )

        except Exception as exc:

            return self._failure(
                request_id,
                "NOVELTY_ANALYSIS_FAILED",
                str(exc),
                stage="novelty_analyzer",
            )

    # ------------------------------------------------------------------
    # Inventive-step API
    # ------------------------------------------------------------------

    def analyze_inventive_step(
        self,
        claims: Any,
        prior_art: Any,
        evidence: Any = None,
        **kwargs: Any,
    ) -> APIResponse:

        request_id = self._request_id()

        try:

            from .inventive_step_analyzer import (
                analyze_inventive_step,
            )

            result = analyze_inventive_step(
                claims=claims,
                prior_art=prior_art,
                evidence=evidence,
                **kwargs,
            )

            return self._success(
                request_id,
                data={
                    "inventive_step": _to_dict(
                        result
                    )
                },
            )

        except Exception as exc:

            return self._failure(
                request_id,
                "INVENTIVE_STEP_ANALYSIS_FAILED",
                str(exc),
                stage="inventive_step_analyzer",
            )

    # ------------------------------------------------------------------
    # Prosecution API
    # ------------------------------------------------------------------

    def analyze_prosecution(
        self,
        fer: Any = None,
        section3: Any = None,
        novelty: Any = None,
        inventive_step: Any = None,
        amendments: Any = None,
        **kwargs: Any,
    ) -> APIResponse:

        request_id = self._request_id()

        try:

            from .prosecution_analyzer import (
                analyze_prosecution,
            )

            result = analyze_prosecution(
                fer=fer,
                section3=section3,
                novelty=novelty,
                inventive_step=inventive_step,
                amendments=amendments,
                **kwargs,
            )

            return self._success(
                request_id,
                data={
                    "prosecution": _to_dict(
                        result
                    )
                },
            )

        except Exception as exc:

            return self._failure(
                request_id,
                "PROSECUTION_ANALYSIS_FAILED",
                str(exc),
                stage="prosecution_analyzer",
            )

    # ------------------------------------------------------------------
    # Knowledge graph API
    # ------------------------------------------------------------------

    def build_knowledge_graph(
        self,
        analysis: Mapping[str, Any],
        **kwargs: Any,
    ) -> APIResponse:

        request_id = self._request_id()

        try:

            from .knowledge_graph import (
                create_knowledge_graph,
            )

            result = create_knowledge_graph(
                analysis,
                **kwargs,
            )

            return self._success(
                request_id,
                data={
                    "knowledge_graph": _to_dict(
                        result
                    )
                },
            )

        except Exception as exc:

            return self._failure(
                request_id,
                "GRAPH_BUILD_FAILED",
                str(exc),
                stage="knowledge_graph",
            )

    # ------------------------------------------------------------------
    # Validation API
    # ------------------------------------------------------------------

    def validate(
        self,
        analysis: Mapping[str, Any],
        strict: bool = False,
    ) -> APIResponse:

        request_id = self._request_id()

        try:

            from .validation import (
                validate_analysis,
            )

            result = validate_analysis(
                analysis,
                strict=strict,
            )

            return self._success(
                request_id,
                data={
                    "validation": _to_dict(
                        result
                    )
                },
            )

        except Exception as exc:

            return self._failure(
                request_id,
                "VALIDATION_FAILED",
                str(exc),
                stage="validation",
            )

    # ------------------------------------------------------------------
    # Report API
    # ------------------------------------------------------------------

    def generate_report(
        self,
        analysis: Mapping[str, Any],
        format: str = "html",
        output_path: Optional[str] = None,
        **kwargs: Any,
    ) -> APIResponse:

        request_id = self._request_id()

        try:

            result = self._generate_report(
                analysis=analysis,
                report_format=format,
                output_path=output_path,
                **kwargs,
            )

            return self._success(
                request_id,
                data={
                    "report": _extract_result_dict(
                        result
                    )
                },
            )

        except Exception as exc:

            return self._failure(
                request_id,
                "REPORT_GENERATION_FAILED",
                str(exc),
                stage="report_generator",
            )

    def _generate_report(
        self,
        analysis: Mapping[str, Any],
        report_format: str = "html",
        output_path: Optional[str] = None,
        **kwargs: Any,
    ) -> Any:

        from .report_generator import (
            PatentReportGenerator,
        )

        generator = (
            PatentReportGenerator()
        )

        format_name = (
            _clean(
                report_format
            ).lower()
            or "html"
        )

        if hasattr(
            generator,
            "generate",
        ):

            return generator.generate(
                analysis,
                format=format_name,
                output_path=output_path,
                **kwargs,
            )

        if format_name == "markdown":
            content = generator.generate_markdown(
                analysis
            )

            if output_path:
                generator.save_markdown(
                    content,
                    output_path,
                )

            return {
                "format": "markdown",
                "content": content,
                "output_path": output_path,
            }

        content = generator.generate_html(
            analysis
        )

        if output_path:
            generator.save_html(
                content,
                output_path,
            )

        return {
            "format": "html",
            "content": content,
            "output_path": output_path,
        }

    # ------------------------------------------------------------------
    # Provenance API
    # ------------------------------------------------------------------

    def get_provenance(
        self,
        analysis: Mapping[str, Any],
    ) -> APIResponse:

        request_id = self._request_id()

        provenance = analysis.get(
            "provenance"
        )

        if provenance is None:
            return self._failure(
                request_id,
                "PROVENANCE_NOT_FOUND",
                "No provenance information is present.",
                stage="provenance",
            )

        return self._success(
            request_id,
            data={
                "provenance": _to_dict(
                    provenance
                )
            },
        )

    # ------------------------------------------------------------------
    # Health API
    # ------------------------------------------------------------------

    def health(
        self,
    ) -> APIResponse:

        request_id = self._request_id()

        checks: Dict[str, Any] = {}

        checks[
            "api"
        ] = {
            "status": "ok",
            "version": API_VERSION,
        }

        checks[
            "pipeline"
        ] = {
            "available": (
                self.pipeline is not None
            )
        }

        checks[
            "validator"
        ] = {
            "available": (
                self.validator is not None
            )
        }

        checks[
            "search"
        ] = {
            "available": (
                self.search_registry
                is not None
            )
        }

        if (
            self.search_registry is not None
            and hasattr(
                self.search_registry,
                "health_check",
            )
        ):

            try:
                checks[
                    "search"
                ][
                    "providers"
                ] = (
                    self.search_registry
                    .health_check()
                )

            except Exception as exc:
                checks[
                    "search"
                ][
                    "error"
                ] = str(exc)

        checks[
            "provenance"
        ] = {
            "available": (
                self.provenance_manager
                is not None
            )
        }

        available = all(
            bool(
                item.get(
                    "available",
                    True,
                )
            )
            for key, item in checks.items()
            if isinstance(
                item,
                Mapping,
            )
            and key != "api"
        )

        return self._success(
            request_id,
            data={
                "status": (
                    "healthy"
                    if available
                    else "degraded"
                ),
                "checks": checks,
            },
        )

    # ------------------------------------------------------------------
    # Metadata
    # ------------------------------------------------------------------

    def capabilities(
        self,
    ) -> APIResponse:

        request_id = self._request_id()

        return self._success(
            request_id,
            data={
                "version": API_VERSION,
                "capabilities": [
                    "document_parsing",
                    "claim_analysis",
                    "prior_art_search",
                    "evidence_retrieval",
                    "evidence_verification",
                    "section_3_screening",
                    "novelty_screening",
                    "inventive_step_screening",
                    "amendment_analysis",
                    "fer_analysis",
                    "prosecution_analysis",
                    "knowledge_graph",
                    "risk_scoring",
                    "provenance",
                    "validation",
                    "report_generation",
                    "optional_ai_assistance",
                ],
            },
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _validate_analysis(
        self,
        analysis: Mapping[str, Any],
        strict: bool = False,
    ) -> Any:

        try:

            from .validation import (
                validate_analysis,
            )

            return validate_analysis(
                analysis,
                strict=strict,
            )

        except Exception:

            if self.validator is not None:

                if hasattr(
                    self.validator,
                    "validate_analysis",
                ):
                    return self.validator.validate_analysis(
                        analysis
                    )

            return None

    def _extract_warnings(
        self,
        analysis: Mapping[str, Any],
    ) -> List[str]:

        warnings: List[str] = []

        for key in (
            "warnings",
            "warning",
            "errors",
        ):

            value = analysis.get(
                key
            )

            if isinstance(
                value,
                list,
            ):

                warnings.extend(
                    _clean(item)
                    for item in value
                    if _clean(item)
                )

        return warnings

    def _validation_warnings(
        self,
        validation: Any,
    ) -> List[str]:

        data = _to_dict(
            validation
        )

        if not isinstance(
            data,
            Mapping,
        ):
            return []

        warnings: List[str] = []

        for issue in (
            data.get(
                "warnings",
                []
            )
        ):

            if isinstance(
                issue,
                Mapping,
            ):

                message = _clean(
                    issue.get(
                        "message"
                    )
                )

                if message:
                    warnings.append(
                        "Validation: "
                        + message
                    )

            else:

                message = _clean(
                    issue
                )

                if message:
                    warnings.append(
                        "Validation: "
                        + message
                    )

        return warnings


# ---------------------------------------------------------------------------
# Singleton/default API
# ---------------------------------------------------------------------------


_default_api: Optional[
    PatentAnalyzerAPI
] = None


def get_api() -> PatentAnalyzerAPI:

    global _default_api

    if _default_api is None:
        _default_api = PatentAnalyzerAPI()

    return _default_api


def create_api(
    **kwargs: Any,
) -> PatentAnalyzerAPI:

    return PatentAnalyzerAPI(
        **kwargs
    )


# ---------------------------------------------------------------------------
# Convenience functions
# ---------------------------------------------------------------------------


def analyze_patent(
    source: Any,
    **kwargs: Any,
) -> APIResponse:

    api = get_api()

    return api.analyze(
        source=source,
        **kwargs,
    )


def parse_patent(
    source: Any,
    **kwargs: Any,
) -> APIResponse:

    return get_api().parse(
        source,
        **kwargs,
    )


def search_patents(
    query: str,
    **kwargs: Any,
) -> APIResponse:

    return get_api().search(
        query,
        **kwargs,
    )


def verify_evidence(
    limitation_text: str,
    evidence: Sequence[Any],
    **kwargs: Any,
) -> APIResponse:

    return get_api().verify_evidence(
        limitation_text,
        evidence,
        **kwargs,
    )


def analyze_fer(
    fer_source: Any,
    **kwargs: Any,
) -> APIResponse:

    return get_api().analyze_fer(
        fer_source,
        **kwargs,
    )


def compare_amendments(
    original_claims: Any,
    amended_claims: Any,
    **kwargs: Any,
) -> APIResponse:

    return get_api().compare_amendments(
        original_claims,
        amended_claims,
        **kwargs,
    )


def validate_analysis(
    analysis: Mapping[str, Any],
    strict: bool = False,
) -> APIResponse:

    return get_api().validate(
        analysis,
        strict=strict,
    )


def generate_report(
    analysis: Mapping[str, Any],
    format: str = "html",
    **kwargs: Any,
) -> APIResponse:

    return get_api().generate_report(
        analysis,
        format=format,
        **kwargs,
    )


def health_check() -> APIResponse:

    return get_api().health()


def get_capabilities() -> APIResponse:

    return get_api().capabilities()


# ---------------------------------------------------------------------------
# JSON serialization
# ---------------------------------------------------------------------------


def response_to_json(
    response: APIResponse,
    indent: int = 2,
) -> str:

    return json.dumps(
        response.to_dict(),
        ensure_ascii=False,
        indent=indent,
        default=str,
    )


def response_from_json(
    value: str,
) -> APIResponse:

    data = json.loads(
        value
    )

    errors = [
        APIError(
            **item
        )
        for item in data.get(
            "errors",
            []
        )
        if isinstance(
            item,
            Mapping,
        )
    ]

    return APIResponse(
        success=bool(
            data.get(
                "success",
                False,
            )
        ),
        request_id=_clean(
            data.get(
                "request_id"
            )
        ),
        timestamp=_clean(
            data.get(
                "timestamp"
            )
        ),
        data=dict(
            data.get(
                "data",
                {}
            )
        ),
        errors=errors,
        warnings=list(
            data.get(
                "warnings",
                []
            )
        ),
        metadata=dict(
            data.get(
                "metadata",
                {}
            )
        ),
    )


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------


def analyze_file(
    path: Union[
        str,
        Path,
    ],
    **kwargs: Any,
) -> APIResponse:

    path = Path(
        path
    )

    if not path.exists():
        request_id = (
            "REQ-"
            + uuid.uuid4().hex[:16]
        )

        return APIResponse(
            success=False,
            request_id=request_id,
            timestamp=_utc_now(),
            errors=[
                APIError(
                    error_id=_stable_id(
                        "ERR",
                        request_id,
                        "FILE_NOT_FOUND",
                    ),
                    code="FILE_NOT_FOUND",
                    message=(
                        f"File does not exist: {path}"
                    ),
                    stage="file_input",
                    recoverable=True,
                    timestamp=_utc_now(),
                )
            ],
            metadata={
                "api_version": API_VERSION,
            },
        )

    return analyze_patent(
        source=str(path),
        filename=path.name,
        **kwargs,
    )


def analyze_bytes(
    data: bytes,
    filename: str = "document.pdf",
    **kwargs: Any,
) -> APIResponse:

    return analyze_patent(
        source=data,
        filename=filename,
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------------


PatentAPI = PatentAnalyzerAPI
ApplicationAPI = PatentAnalyzerAPI

run_analysis = analyze_patent
run_patent_analysis = analyze_patent
search = search_patents
parse_document = parse_patent


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


__all__ = [
    "API_VERSION",

    "APIError",
    "APIResponse",
    "AnalysisRequest",

    "PatentAnalyzerAPI",
    "PatentAPI",
    "ApplicationAPI",

    "get_api",
    "create_api",

    "analyze_patent",
    "analyze_file",
    "analyze_bytes",
    "parse_patent",
    "search_patents",
    "verify_evidence",
    "analyze_fer",
    "compare_amendments",
    "validate_analysis",
    "generate_report",
    "health_check",
    "get_capabilities",

    "response_to_json",
    "response_from_json",

    "run_analysis",
    "run_patent_analysis",
    "search",
    "parse_document",
]
