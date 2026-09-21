"""
Analysis Pipeline V3
====================

Central orchestration layer for the Indian Patent Analyzer.

Pipeline
--------

    Document
       │
       ▼
    Parser
       │
       ├── Claims
       │     └── Limitations
       │
       ├── Specification
       │
       ▼
    Rule Engine
       │
       ├── Section 3 screening
       ├── Claim support
       └── Claim clarity
       │
       ▼
    Prior-Art Search Plan
       │
       ▼
    Evidence
       │
       ├── Claim chart
       ├── Novelty
       └── Inventive Step
       │
       ▼
    FER / Prosecution
       │
       ▼
    Knowledge Graph
       │
       ▼
    Scoring
       │
       ▼
    Report / UI / Gemini


Important design principle
--------------------------
This module orchestrates deterministic analysis.

AI is optional.

Gemini is never treated as the source of truth.

Every downstream conclusion should remain traceable to:
    document
    page
    paragraph
    claim
    limitation
    evidence
    rule
    legal provision
    analysis version

Version
-------
3.0.0
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


PIPELINE_VERSION = "3.0.0"


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


def _clean(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
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
        value.encode("utf-8")
    ).hexdigest()[:16]

    return f"{prefix}-{digest}"


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


def _safe_float(
    value: Any,
    default: float = 0.0,
) -> float:

    try:
        return float(value)

    except Exception:
        return default


# ---------------------------------------------------------------------
# Pipeline data structures
# ---------------------------------------------------------------------

@dataclass
class PipelineStage:

    name: str

    status: str = "PENDING"

    started_at: str = ""

    completed_at: str = ""

    duration_seconds: float = 0.0

    item_count: int = 0

    warnings: List[str] = field(
        default_factory=list
    )

    errors: List[str] = field(
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
class PipelineResult:

    analysis_id: str

    pipeline_version: str

    started_at: str

    completed_at: str

    status: str

    stages: List[
        PipelineStage
    ]

    document: Dict[str, Any]

    parsed_document: Dict[str, Any]

    claims: List[
        Dict[str, Any]
    ]

    rule_analysis: Dict[str, Any]

    section3_analysis: Dict[str, Any]

    prior_art_analysis: Dict[str, Any]

    evidence_analysis: Dict[str, Any]

    novelty_analysis: Dict[str, Any]

    inventive_step_analysis: Dict[str, Any]

    prosecution_analysis: Dict[str, Any]

    amendment_analysis: Dict[str, Any]

    knowledge_graph: Dict[str, Any]

    scoring: Dict[str, Any]

    ai_analysis: Dict[str, Any]

    warnings: List[str]

    errors: List[str]

    metadata: Dict[str, Any]

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(
            self
        )


# ---------------------------------------------------------------------
# Analyzer imports
#
# Imports are intentionally isolated so that the application can
# still import the pipeline when an optional component is unavailable.
# ---------------------------------------------------------------------

def _import_module(
    module_name: str,
):

    try:

        return __import__(
            module_name,
            fromlist=["*"],
        )

    except Exception:

        return None


# ---------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------

class PatentAnalysisPipeline:

    def __init__(
        self,
        *,
        enable_ai: bool = False,
        enable_prior_art_links: bool = True,
        strict: bool = False,
    ):

        self.enable_ai = (
            enable_ai
        )

        self.enable_prior_art_links = (
            enable_prior_art_links
        )

        self.strict = strict

        self.stages: List[
            PipelineStage
        ] = []

        self.warnings: List[str] = []

        self.errors: List[str] = []

    # -------------------------------------------------------------
    # Stage handling
    # -------------------------------------------------------------

    def _start_stage(
        self,
        name: str,
    ) -> PipelineStage:

        stage = PipelineStage(
            name=name,
            status="RUNNING",
            started_at=_utc_now(),
        )

        self.stages.append(
            stage
        )

        return stage

    def _finish_stage(
        self,
        stage: PipelineStage,
        *,
        status: str = "COMPLETED",
        item_count: int = 0,
    ):

        stage.status = status

        stage.completed_at = _utc_now()

        try:

            start = datetime.fromisoformat(
                stage.started_at
            )

            end = datetime.fromisoformat(
                stage.completed_at
            )

            stage.duration_seconds = (
                end - start
            ).total_seconds()

        except Exception:

            stage.duration_seconds = 0.0

        stage.item_count = (
            item_count
        )

    def _fail_stage(
        self,
        stage: PipelineStage,
        error: Exception,
    ):

        stage.status = "FAILED"

        stage.completed_at = _utc_now()

        message = (
            f"{stage.name}: "
            f"{type(error).__name__}: "
            f"{error}"
        )

        stage.errors.append(
            message
        )

        self.errors.append(
            message
        )

        if self.strict:
            raise error

    # -------------------------------------------------------------
    # Parser
    # -------------------------------------------------------------

    def parse_document(
        self,
        document: Any,
        *,
        filename: str = "",
    ) -> Dict[str, Any]:

        stage = self._start_stage(
            "document_parser"
        )

        try:

            parser = _import_module(
                "services.document_parser"
            )

            if parser is None:

                raise ImportError(
                    "services.document_parser "
                    "could not be imported"
                )

            parsed = None

            # Already parsed dictionary.
            if isinstance(
                document,
                dict,
            ):

                parsed = document

            # Raw bytes.
            elif isinstance(
                document,
                bytes,
            ):

                parsed = (
                    parser.parse_document(
                        document
                    )
                )

            # File path.
            elif isinstance(
                document,
                str,
            ):

                if not os.path.exists(
                    document
                ):

                    raise FileNotFoundError(
                        document
                    )

                parsed = (
                    parser.parse_file(
                        document
                    )
                )

            else:

                # File-like object.
                if hasattr(
                    document,
                    "read",
                ):

                    raw = document.read()

                    if isinstance(
                        raw,
                        str,
                    ):

                        raw = raw.encode(
                            "utf-8"
                        )

                    parsed = (
                        parser.parse_document(
                            raw
                        )
                    )

                else:

                    raise TypeError(
                        "Unsupported document "
                        "input type"
                    )

            result = _to_dict(
                parsed
            )

            stage.metadata[
                "filename"
            ] = filename

            self._finish_stage(
                stage,
                item_count=len(
                    result.get(
                        "pages",
                        [],
                    )
                ),
            )

            return result

        except Exception as error:

            self._fail_stage(
                stage,
                error,
            )

            return {}

    # -------------------------------------------------------------
    # Claims
    # -------------------------------------------------------------

    def analyze_claims(
        self,
        parsed_document: Dict[str, Any],
    ) -> List[
        Dict[str, Any]
    ]:

        stage = self._start_stage(
            "claim_analysis"
        )

        try:

            claims = parsed_document.get(
                "claims",
                [],
            )

            result = []

            claim_module = _import_module(
                "services.claim_analyzer"
            )

            if claim_module:

                try:

                    analyzed = (
                        claim_module.analyze_claims(
                            claims
                        )
                    )

                    if analyzed is not None:

                        claims = analyzed

                except Exception as error:

                    stage.warnings.append(
                        "Claim analyzer "
                        f"could not enrich claims: "
                        f"{error}"
                    )

            for index, claim in enumerate(
                _listify(claims),
                start=1,
            ):

                claim_dict = _to_dict(
                    claim
                )

                if not claim_dict:

                    continue

                claim_dict.setdefault(
                    "claim_number",
                    index,
                )

                claim_dict.setdefault(
                    "text",
                    claim_dict.get(
                        "claim_text",
                        "",
                    ),
                )

                result.append(
                    claim_dict
                )

            self._finish_stage(
                stage,
                item_count=len(
                    result
                ),
            )

            return result

        except Exception as error:

            self._fail_stage(
                stage,
                error,
            )

            return []

    # -------------------------------------------------------------
    # Rule engine
    # -------------------------------------------------------------

    def run_rules(
        self,
        *,
        claims: List[
            Dict[str, Any]
        ],
        parsed_document: Dict[str, Any],
    ) -> Dict[str, Any]:

        stage = self._start_stage(
            "rule_engine"
        )

        try:

            module = _import_module(
                "services.rule_engine"
            )

            if module is None:

                raise ImportError(
                    "Rule engine unavailable"
                )

            specification = (
                parsed_document.get(
                    "text",
                    parsed_document.get(
                        "full_text",
                        "",
                    ),
                )
            )

            try:

                result = (
                    module.run_rule_engine(
                        claims=claims,
                        specification=specification,
                    )
                )

            except TypeError:

                result = (
                    module.run_rule_engine(
                        claims,
                        specification,
                    )
                )

            result = _to_dict(
                result
            )

            self._finish_stage(
                stage,
                item_count=len(
                    result.get(
                        "findings",
                        [],
                    )
                ),
            )

            return result

        except Exception as error:

            self._fail_stage(
                stage,
                error,
            )

            return {
                "findings": [],
                "error": str(error),
            }

    # -------------------------------------------------------------
    # Section 3
    # -------------------------------------------------------------

    def analyze_section3(
        self,
        *,
        claims: List[
            Dict[str, Any]
        ],
        parsed_document: Dict[str, Any],
    ) -> Dict[str, Any]:

        stage = self._start_stage(
            "section3_analysis"
        )

        try:

            module = _import_module(
                "services.section3_analyzer"
            )

            if module is None:

                raise ImportError(
                    "Section 3 analyzer unavailable"
                )

            specification = (
                parsed_document.get(
                    "text",
                    parsed_document.get(
                        "full_text",
                        "",
                    ),
                )
            )

            if hasattr(
                module,
                "analyze_section_3",
            ):

                result = (
                    module.analyze_section_3(
                        claims=claims,
                        specification=specification,
                    )
                )

            elif hasattr(
                module,
                "screen_document",
            ):

                result = (
                    module.screen_document(
                        claims=claims,
                        specification=specification,
                    )
                )

            else:

                raise AttributeError(
                    "No Section 3 analysis "
                    "function found"
                )

            result = _to_dict(
                result
            )

            self._finish_stage(
                stage,
                item_count=len(
                    result.get(
                        "findings",
                        [],
                    )
                ),
            )

            return result

        except Exception as error:

            self._fail_stage(
                stage,
                error,
            )

            return {
                "findings": [],
                "error": str(error),
            }

    # -------------------------------------------------------------
    # Prior art
    # -------------------------------------------------------------

    def build_prior_art_plan(
        self,
        claims: List[
            Dict[str, Any]
        ],
    ) -> Dict[str, Any]:

        stage = self._start_stage(
            "prior_art_planning"
        )

        try:

            module = _import_module(
                "services.prior_art"
            )

            if module is None:

                raise ImportError(
                    "Prior-art module unavailable"
                )

            if hasattr(
                module,
                "build_search_plan",
            ):

                plan = (
                    module.build_search_plan(
                        claims
                    )
                )

            elif hasattr(
                module,
                "generate_search_queries",
            ):

                queries = (
                    module.generate_search_queries(
                        claims
                    )
                )

                plan = {
                    "queries":
                        queries,
                }

            else:

                plan = {
                    "queries": [],
                    "message":
                        "No search planner available",
                }

            result = _to_dict(
                plan
            )

            self._finish_stage(
                stage,
                item_count=len(
                    result.get(
                        "queries",
                        [],
                    )
                ),
            )

            return result

        except Exception as error:

            self._fail_stage(
                stage,
                error,
            )

            return {
                "queries": [],
                "error": str(error),
            }

    # -------------------------------------------------------------
    # Evidence / claim charts
    # -------------------------------------------------------------

    def build_evidence_analysis(
        self,
        *,
        claims: List[
            Dict[str, Any]
        ],
        prior_art_documents: Optional[
            List[
                Dict[str, Any]
            ]
        ] = None,
        evidence: Optional[
            List[
                Dict[str, Any]
            ]
        ] = None,
    ) -> Dict[str, Any]:

        stage = self._start_stage(
            "evidence_analysis"
        )

        try:

            module = _import_module(
                "services.claim_chart"
            )

            if module is None:

                raise ImportError(
                    "Claim chart module unavailable"
                )

            documents = (
                prior_art_documents
                or []
            )

            evidence_items = (
                evidence
                or []
            )

            charts = []

            for claim in claims:

                claim_number = claim.get(
                    "claim_number",
                    0,
                )

                claim_evidence = [
                    item
                    for item
                    in evidence_items
                    if (
                        item.get(
                            "claim_number"
                        )
                        == claim_number
                        or item.get(
                            "claim_id"
                        )
                        == claim.get(
                            "claim_id"
                        )
                    )
                ]

                try:

                    chart = (
                        module.build_claim_chart(
                            claim=claim,
                            prior_art_documents=documents,
                            evidence=claim_evidence,
                        )
                    )

                except TypeError:

                    try:

                        chart = (
                            module.create_claim_chart(
                                claim,
                                documents,
                                claim_evidence,
                            )
                        )

                    except Exception:

                        chart = {}

                charts.append(
                    _to_dict(
                        chart
                    )
                )

            result = {
                "charts":
                    charts,

                "evidence":
                    evidence_items,

                "document_count":
                    len(documents),
            }

            self._finish_stage(
                stage,
                item_count=len(
                    charts
                ),
            )

            return result

        except Exception as error:

            self._fail_stage(
                stage,
                error,
            )

            return {
                "charts": [],
                "evidence": [],
                "error": str(error),
            }

    # -------------------------------------------------------------
    # Novelty
    # -------------------------------------------------------------

    def analyze_novelty(
        self,
        *,
        claims: List[
            Dict[str, Any]
        ],
        evidence_analysis: Dict[str, Any],
        prior_art_documents: List[
            Dict[str, Any]
        ],
    ) -> Dict[str, Any]:

        stage = self._start_stage(
            "novelty_analysis"
        )

        try:

            module = _import_module(
                "services.novelty_analyzer"
            )

            if module is None:

                raise ImportError(
                    "Novelty analyzer unavailable"
                )

            if hasattr(
                module,
                "analyze_novelty",
            ):

                result = (
                    module.analyze_novelty(
                        claims=claims,
                        evidence=evidence_analysis.get(
                            "evidence",
                            [],
                        ),
                        prior_art=prior_art_documents,
                    )
                )

            elif hasattr(
                module,
                "NoveltyAnalyzer",
            ):

                analyzer = (
                    module.NoveltyAnalyzer()
                )

                result = (
                    analyzer.analyze(
                        claims=claims,
                        evidence=evidence_analysis.get(
                            "evidence",
                            [],
                        ),
                        prior_art=prior_art_documents,
                    )
                )

            else:

                result = {
                    "claims": [],
                }

            result = _to_dict(
                result
            )

            self._finish_stage(
                stage,
                item_count=len(
                    result.get(
                        "claims",
                        [],
                    )
                ),
            )

            return result

        except Exception as error:

            self._fail_stage(
                stage,
                error,
            )

            return {
                "claims": [],
                "error": str(error),
            }

    # -------------------------------------------------------------
    # Inventive step
    # -------------------------------------------------------------

    def analyze_inventive_step(
        self,
        *,
        claims: List[
            Dict[str, Any]
        ],
        evidence_analysis: Dict[str, Any],
        prior_art_documents: List[
            Dict[str, Any]
        ],
    ) -> Dict[str, Any]:

        stage = self._start_stage(
            "inventive_step_analysis"
        )

        try:

            module = _import_module(
                "services.inventive_step_analyzer"
            )

            if module is None:

                raise ImportError(
                    "Inventive-step analyzer "
                    "unavailable"
                )

            evidence = (
                evidence_analysis.get(
                    "evidence",
                    [],
                )
            )

            if hasattr(
                module,
                "analyze_inventive_step",
            ):

                result = (
                    module.analyze_inventive_step(
                        claims=claims,
                        prior_art=prior_art_documents,
                        evidence=evidence,
                    )
                )

            elif hasattr(
                module,
                "InventiveStepAnalyzer",
            ):

                analyzer = (
                    module.InventiveStepAnalyzer()
                )

                result = (
                    analyzer.analyze(
                        claims=claims,
                        prior_art=prior_art_documents,
                        evidence=evidence,
                    )
                )

            else:

                result = {
                    "claims": [],
                }

            result = _to_dict(
                result
            )

            self._finish_stage(
                stage,
                item_count=len(
                    result.get(
                        "claims",
                        [],
                    )
                ),
            )

            return result

        except Exception as error:

            self._fail_stage(
                stage,
                error,
            )

            return {
                "claims": [],
                "error": str(error),
            }

    # -------------------------------------------------------------
    # Amendments
    # -------------------------------------------------------------

    def analyze_amendments(
        self,
        amendment_input: Any = None,
    ) -> Dict[str, Any]:

        stage = self._start_stage(
            "amendment_analysis"
        )

        try:

            if amendment_input is None:

                result = {
                    "comparisons": [],
                    "message":
                        "No amendment history supplied",
                }

                self._finish_stage(
                    stage,
                    item_count=0,
                )

                return result

            module = _import_module(
                "services.amendment_analyzer"
            )

            if module is None:

                raise ImportError(
                    "Amendment analyzer unavailable"
                )

            if hasattr(
                module,
                "analyze_amendments",
            ):

                result = (
                    module.analyze_amendments(
                        amendment_input
                    )
                )

            elif hasattr(
                module,
                "compare_claim_versions",
            ):

                result = (
                    module.compare_claim_versions(
                        amendment_input
                    )
                )

            else:

                result = {
                    "comparisons": [],
                }

            result = _to_dict(
                result
            )

            self._finish_stage(
                stage,
                item_count=len(
                    result.get(
                        "comparisons",
                        result.get(
                            "claims",
                            [],
                        ),
                    )
                ),
            )

            return result

        except Exception as error:

            self._fail_stage(
                stage,
                error,
            )

            return {
                "comparisons": [],
                "error": str(error),
            }

    # -------------------------------------------------------------
    # Prosecution
    # -------------------------------------------------------------

    def analyze_prosecution(
        self,
        *,
        claims: List[
            Dict[str, Any]
        ],
        fer_analysis: Dict[str, Any],
        section3_analysis: Dict[str, Any],
        novelty_analysis: Dict[str, Any],
        inventive_step_analysis: Dict[str, Any],
        amendment_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:

        stage = self._start_stage(
            "prosecution_analysis"
        )

        try:

            module = _import_module(
                "services.prosecution_analyzer"
            )

            if module is None:

                raise ImportError(
                    "Prosecution analyzer unavailable"
                )

            result = (
                module.analyze_prosecution(
                    claims=claims,
                    fer_analysis=fer_analysis,
                    section3_analysis=section3_analysis,
                    novelty_analysis=novelty_analysis,
                    inventive_step_analysis=(
                        inventive_step_analysis
                    ),
                    amendment_analysis=(
                        amendment_analysis
                    ),
                )
            )

            result = _to_dict(
                result
            )

            self._finish_stage(
                stage,
                item_count=len(
                    result.get(
                        "issues",
                        [],
                    )
                ),
            )

            return result

        except Exception as error:

            self._fail_stage(
                stage,
                error,
            )

            return {
                "issues": [],
                "error": str(error),
            }

    # -------------------------------------------------------------
    # Knowledge graph
    # -------------------------------------------------------------

    def build_knowledge_graph(
        self,
        *,
        patent: Dict[str, Any],
        claims: List[
            Dict[str, Any]
        ],
        prior_art: List[
            Dict[str, Any]
        ],
        evidence: List[
            Dict[str, Any]
        ],
        legal_provisions: List[
            Dict[str, Any]
        ],
        fer_analysis: Dict[str, Any],
        section3_analysis: Dict[str, Any],
        novelty_analysis: Dict[str, Any],
        inventive_step_analysis: Dict[str, Any],
        amendment_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:

        stage = self._start_stage(
            "knowledge_graph"
        )

        try:

            module = _import_module(
                "services.knowledge_graph"
            )

            if module is None:

                raise ImportError(
                    "Knowledge graph unavailable"
                )

            graph = (
                module.build_knowledge_graph(
                    patent=patent,
                    claims=claims,
                    prior_art=prior_art,
                    evidence=evidence,
                    legal_provisions=(
                        legal_provisions
                    ),
                    fer_analysis=fer_analysis,
                    section3_analysis=(
                        section3_analysis
                    ),
                    novelty_analysis=(
                        novelty_analysis
                    ),
                    inventive_step_analysis=(
                        inventive_step_analysis
                    ),
                    amendment_analysis=(
                        amendment_analysis
                    ),
                )
            )

            if hasattr(
                graph,
                "to_dict",
            ):

                result = graph.to_dict()

            else:

                result = _to_dict(
                    graph
                )

            self._finish_stage(
                stage,
                item_count=len(
                    result.get(
                        "nodes",
                        [],
                    )
                ),
            )

            return result

        except Exception as error:

            self._fail_stage(
                stage,
                error,
            )

            return {
                "nodes": [],
                "edges": [],
                "error": str(error),
            }

    # -------------------------------------------------------------
    # Scoring
    # -------------------------------------------------------------

    def calculate_scoring(
        self,
        *,
        findings: Dict[str, Any],
        evidence_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:

        stage = self._start_stage(
            "risk_scoring"
        )

        try:

            module = _import_module(
                "services.scoring"
            )

            if module is None:

                raise ImportError(
                    "Scoring module unavailable"
                )

            all_findings = []

            for key in (
                "findings",
                "issues",
                "claims",
            ):

                value = findings.get(
                    key,
                    [],
                )

                if isinstance(
                    value,
                    list,
                ):

                    all_findings.extend(
                        value
                    )

            if hasattr(
                module,
                "score_analysis",
            ):

                result = (
                    module.score_analysis(
                        findings=all_findings,
                        evidence=evidence_analysis.get(
                            "evidence",
                            [],
                        ),
                    )
                )

            else:

                result = {
                    "signals": [],
                    "overall": 0.0,
                }

            result = _to_dict(
                result
            )

            self._finish_stage(
                stage,
                item_count=len(
                    result.get(
                        "signals",
                        [],
                    )
                ),
            )

            return result

        except Exception as error:

            self._fail_stage(
                stage,
                error,
            )

            return {
                "signals": [],
                "error": str(error),
            }

    # -------------------------------------------------------------
    # AI
    # -------------------------------------------------------------

    def run_ai(
        self,
        *,
        claims: List[
            Dict[str, Any]
        ],
        graph: Dict[str, Any],
        rule_analysis: Dict[str, Any],
        novelty_analysis: Dict[str, Any],
        inventive_step_analysis: Dict[str, Any],
    ) -> Dict[str, Any]:

        stage = self._start_stage(
            "ai_analysis"
        )

        if not self.enable_ai:

            stage.status = "SKIPPED"

            stage.completed_at = _utc_now()

            stage.metadata[
                "reason"
            ] = "AI disabled"

            return {
                "enabled": False,
                "status": "SKIPPED",
            }

        try:

            module = _import_module(
                "services.gemini_service"
            )

            if module is None:

                raise ImportError(
                    "Gemini service unavailable"
                )

            service = (
                module.get_gemini_service()
            )

            context = {
                "claims":
                    claims,

                "graph_statistics":
                    graph.get(
                        "statistics",
                        {},
                    ),

                "rule_analysis":
                    rule_analysis,

                "novelty_analysis":
                    novelty_analysis,

                "inventive_step_analysis":
                    inventive_step_analysis,
            }

            prompt = """
You are an analysis assistant inside a patent intelligence system.

Use ONLY the supplied structured evidence.

Do not invent:
- prior-art disclosures
- legal provisions
- claim limitations
- evidence
- dates
- citations
- technical facts

Do not provide a definitive legal opinion.

Return a concise structured interpretation identifying:
1. important evidence patterns
2. unresolved questions
3. possible contradictions
4. areas requiring human review

Every material statement should be traceable to supplied data.
"""

            if hasattr(
                service,
                "generate_json",
            ):

                result = service.generate_json(
                    prompt=prompt,
                    context=context,
                )

            else:

                result = service.generate(
                    prompt,
                    context=context,
                )

            result = _to_dict(
                result
            )

            result[
                "enabled"
            ] = True

            result[
                "status"
            ] = "COMPLETED"

            self._finish_stage(
                stage,
                item_count=1,
            )

            return result

        except Exception as error:

            self._fail_stage(
                stage,
                error,
            )

            return {
                "enabled": True,
                "status": "FAILED",
                "error": str(error),
            }

    # -------------------------------------------------------------
    # Main execution
    # -------------------------------------------------------------

    def run(
        self,
        document: Any,
        *,
        filename: str = "",
        patent_metadata: Optional[
            Dict[str, Any]
        ] = None,
        prior_art_documents: Optional[
            List[
                Dict[str, Any]
            ]
        ] = None,
        evidence: Optional[
            List[
                Dict[str, Any]
            ]
        ] = None,
        legal_provisions: Optional[
            List[
                Dict[str, Any]
            ]
        ] = None,
        fer_analysis: Optional[
            Dict[str, Any]
        ] = None,
        amendment_input: Any = None,
    ) -> PipelineResult:

        started_at = _utc_now()

        analysis_id = _stable_id(
            "ANALYSIS",
            (
                f"{filename}|"
                f"{started_at}|"
                f"{PIPELINE_VERSION}"
            ),
        )

        # ---------------------------------------------------------
        # Document
        # ---------------------------------------------------------

        parsed_document = (
            self.parse_document(
                document,
                filename=filename,
            )
        )

        if not parsed_document:

            self.errors.append(
                "Document parsing produced no result."
            )

        document_info = (
            patent_metadata
            or {}
        )

        document_info = {
            **document_info,
            "filename":
                filename,
            "analysis_id":
                analysis_id,
        }

        # ---------------------------------------------------------
        # Claims
        # ---------------------------------------------------------

        claims = self.analyze_claims(
            parsed_document
        )

        # ---------------------------------------------------------
        # Rules
        # ---------------------------------------------------------

        rule_analysis = self.run_rules(
            claims=claims,
            parsed_document=parsed_document,
        )

        # ---------------------------------------------------------
        # Section 3
        # ---------------------------------------------------------

        section3_analysis = (
            self.analyze_section3(
                claims=claims,
                parsed_document=parsed_document,
            )
        )

        # ---------------------------------------------------------
        # Prior-art search plan
        # ---------------------------------------------------------

        prior_art_plan = (
            self.build_prior_art_plan(
                claims
            )
        )

        # ---------------------------------------------------------
        # Prior art
        #
        # Actual external search is intentionally NOT performed
        # here. Search providers can be connected separately.
        # ---------------------------------------------------------

        prior_art = (
            prior_art_documents
            or []
        )

        prior_art_analysis = {
            "search_plan":
                prior_art_plan,

            "documents":
                prior_art,

            "document_count":
                len(prior_art),

            "external_search_required":
                len(prior_art) == 0,
        }

        # ---------------------------------------------------------
        # Evidence
        # ---------------------------------------------------------

        evidence_analysis = (
            self.build_evidence_analysis(
                claims=claims,
                prior_art_documents=prior_art,
                evidence=evidence,
            )
        )

        # ---------------------------------------------------------
        # Novelty
        # ---------------------------------------------------------

        novelty_analysis = (
            self.analyze_novelty(
                claims=claims,
                evidence_analysis=(
                    evidence_analysis
                ),
                prior_art_documents=prior_art,
            )
        )

        # ---------------------------------------------------------
        # Inventive step
        # ---------------------------------------------------------

        inventive_step_analysis = (
            self.analyze_inventive_step(
                claims=claims,
                evidence_analysis=(
                    evidence_analysis
                ),
                prior_art_documents=prior_art,
            )
        )

        # ---------------------------------------------------------
        # Amendments
        # ---------------------------------------------------------

        amendment_analysis = (
            self.analyze_amendments(
                amendment_input
            )
        )

        # ---------------------------------------------------------
        # FER
        # ---------------------------------------------------------

        if fer_analysis is None:

            fer_analysis = {
                "objections": [],
                "citations": [],
                "deadlines": [],
            }

        # ---------------------------------------------------------
        # Prosecution
        # ---------------------------------------------------------

        prosecution_analysis = (
            self.analyze_prosecution(
                claims=claims,
                fer_analysis=fer_analysis,
                section3_analysis=(
                    section3_analysis
                ),
                novelty_analysis=(
                    novelty_analysis
                ),
                inventive_step_analysis=(
                    inventive_step_analysis
                ),
                amendment_analysis=(
                    amendment_analysis
                ),
            )
        )

        # ---------------------------------------------------------
        # Knowledge graph
        # ---------------------------------------------------------

        graph = (
            self.build_knowledge_graph(
                patent=document_info,
                claims=claims,
                prior_art=prior_art,
                evidence=evidence_analysis.get(
                    "evidence",
                    evidence
                    or [],
                ),
                legal_provisions=(
                    legal_provisions
                    or []
                ),
                fer_analysis=fer_analysis,
                section3_analysis=(
                    section3_analysis
                ),
                novelty_analysis=(
                    novelty_analysis
                ),
                inventive_step_analysis=(
                    inventive_step_analysis
                ),
                amendment_analysis=(
                    amendment_analysis
                ),
            )
        )

        # ---------------------------------------------------------
        # Scoring
        # ---------------------------------------------------------

        scoring_findings = {
            "findings":
                rule_analysis.get(
                    "findings",
                    [],
                ),

            "issues":
                prosecution_analysis.get(
                    "issues",
                    [],
                ),

            "claims":
                novelty_analysis.get(
                    "claims",
                    [],
                ),
        }

        scoring = self.calculate_scoring(
            findings=scoring_findings,
            evidence_analysis=(
                evidence_analysis
            ),
        )

        # ---------------------------------------------------------
        # AI
        # ---------------------------------------------------------

        ai_analysis = self.run_ai(
            claims=claims,
            graph=graph,
            rule_analysis=rule_analysis,
            novelty_analysis=novelty_analysis,
            inventive_step_analysis=(
                inventive_step_analysis
            ),
        )

        completed_at = _utc_now()

        status = (
            "COMPLETED"
            if not self.errors
            else "COMPLETED_WITH_ERRORS"
        )

        metadata = {
            "pipeline_version":
                PIPELINE_VERSION,

            "analysis_id":
                analysis_id,

            "deterministic":
                True,

            "ai_enabled":
                self.enable_ai,

            "prior_art_count":
                len(prior_art),

            "claim_count":
                len(claims),

            "stage_count":
                len(self.stages),

            "review_notice":
                (
                    "This pipeline organizes and "
                    "analyzes patent information. "
                    "Automated findings are not "
                    "legal conclusions."
                ),
        }

        return PipelineResult(
            analysis_id=analysis_id,
            pipeline_version=PIPELINE_VERSION,
            started_at=started_at,
            completed_at=completed_at,
            status=status,
            stages=self.stages,
            document=document_info,
            parsed_document=parsed_document,
            claims=claims,
            rule_analysis=rule_analysis,
            section3_analysis=section3_analysis,
            prior_art_analysis=prior_art_analysis,
            evidence_analysis=evidence_analysis,
            novelty_analysis=novelty_analysis,
            inventive_step_analysis=(
                inventive_step_analysis
            ),
            prosecution_analysis=(
                prosecution_analysis
            ),
            amendment_analysis=(
                amendment_analysis
            ),
            knowledge_graph=graph,
            scoring=scoring,
            ai_analysis=ai_analysis,
            warnings=self.warnings,
            errors=self.errors,
            metadata=metadata,
        )


# ---------------------------------------------------------------------
# Convenience API
# ---------------------------------------------------------------------

def run_analysis_pipeline(
    document: Any,
    *,
    filename: str = "",
    patent_metadata: Optional[
        Dict[str, Any]
    ] = None,
    prior_art_documents: Optional[
        List[
            Dict[str, Any]
        ]
    ] = None,
    evidence: Optional[
        List[
            Dict[str, Any]
        ]
    ] = None,
    legal_provisions: Optional[
        List[
            Dict[str, Any]
        ]
    ] = None,
    fer_analysis: Optional[
        Dict[str, Any]
    ] = None,
    amendment_input: Any = None,
    enable_ai: bool = False,
    strict: bool = False,
) -> Dict[str, Any]:

    pipeline = PatentAnalysisPipeline(
        enable_ai=enable_ai,
        strict=strict,
    )

    result = pipeline.run(
        document,
        filename=filename,
        patent_metadata=patent_metadata,
        prior_art_documents=(
            prior_art_documents
        ),
        evidence=evidence,
        legal_provisions=(
            legal_provisions
        ),
        fer_analysis=fer_analysis,
        amendment_input=amendment_input,
    )

    return result.to_dict()


def analyze_patent(
    document: Any,
    **kwargs: Any,
) -> Dict[str, Any]:

    return run_analysis_pipeline(
        document,
        **kwargs,
    )


# ---------------------------------------------------------------------
# Lightweight pipeline inspection
# ---------------------------------------------------------------------

def pipeline_statistics(
    result: Dict[str, Any],
) -> Dict[str, Any]:

    stages = result.get(
        "stages",
        [],
    )

    completed = 0
    failed = 0
    skipped = 0

    for stage in stages:

        status = stage.get(
            "status",
            "",
        )

        if status == "COMPLETED":

            completed += 1

        elif status == "FAILED":

            failed += 1

        elif status == "SKIPPED":

            skipped += 1

    return {
        "analysis_id":
            result.get(
                "analysis_id",
                "",
            ),

        "status":
            result.get(
                "status",
                "",
            ),

        "stage_count":
            len(stages),

        "completed_stages":
            completed,

        "failed_stages":
            failed,

        "skipped_stages":
            skipped,

        "claim_count":
            len(
                result.get(
                    "claims",
                    [],
                )
            ),

        "prior_art_count":
            len(
                result.get(
                    "prior_art_analysis",
                    {}
                ).get(
                    "documents",
                    [],
                )
            ),

        "error_count":
            len(
                result.get(
                    "errors",
                    [],
                )
            ),

        "warning_count":
            len(
                result.get(
                    "warnings",
                    [],
                )
            ),
    }


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

__all__ = [
    "PIPELINE_VERSION",

    "PipelineStage",
    "PipelineResult",

    "PatentAnalysisPipeline",

    "run_analysis_pipeline",
    "analyze_patent",

    "pipeline_statistics",
]
