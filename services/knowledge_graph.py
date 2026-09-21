"""
Knowledge Graph V3
==================

Purpose
-------
Build a unified, queryable evidence graph for the patent analyzer.

Core graph:

    Patent
      |
      +---- Claim
      |       |
      |       +---- Limitation
      |                |
      |                +---- Evidence
      |                         |
      |                         +---- Prior-Art Document
      |
      +---- FER Objection
      |
      +---- Section 3 Finding
      |
      +---- Amendment
      |
      +---- Legal Provision
      |
      +---- Novelty Finding
      |
      +---- Inventive-Step Finding


Design principles
-----------------
1. Deterministic identifiers.
2. Explicit node types.
3. Explicit relationship types.
4. Evidence remains traceable to its source.
5. No hidden AI conclusions.
6. Graph can be serialized to JSON.
7. Graph can be queried without a database.
8. Compatible with future Neo4j / graph database migration.

Version
-------
3.0.0
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


KNOWLEDGE_GRAPH_VERSION = "3.0.0"


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


def _stable_id(
    prefix: str,
    value: Any,
) -> str:

    digest = hashlib.sha256(
        _clean(value).encode(
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


# ---------------------------------------------------------------------
# Node types
# ---------------------------------------------------------------------

NODE_PATENT = "PATENT"
NODE_APPLICATION = "APPLICATION"

NODE_CLAIM = "CLAIM"
NODE_LIMITATION = "LIMITATION"

NODE_DOCUMENT = "PRIOR_ART_DOCUMENT"
NODE_EVIDENCE = "EVIDENCE"

NODE_FER = "FER_OBJECTION"
NODE_SECTION3 = "SECTION3_FINDING"

NODE_NOVELTY = "NOVELTY_FINDING"
NODE_INVENTIVE_STEP = "INVENTIVE_STEP_FINDING"

NODE_AMENDMENT = "AMENDMENT"
NODE_LEGAL_PROVISION = "LEGAL_PROVISION"

NODE_PARAGRAPH = "PARAGRAPH"
NODE_SEARCH_QUERY = "SEARCH_QUERY"


# ---------------------------------------------------------------------
# Edge types
# ---------------------------------------------------------------------

EDGE_HAS_CLAIM = "HAS_CLAIM"
EDGE_HAS_LIMITATION = "HAS_LIMITATION"

EDGE_SUPPORTED_BY = "SUPPORTED_BY"
EDGE_EVIDENCE_FOR = "EVIDENCE_FOR"

EDGE_DISCLOSES = "DISCLOSES"
EDGE_PARTIALLY_DISCLOSES = "PARTIALLY_DISCLOSES"
EDGE_DOES_NOT_DISCLOSE = "DOES_NOT_DISCLOSE"

EDGE_REFERENCES = "REFERENCES"
EDGE_APPLIES_TO = "APPLIES_TO"

EDGE_HAS_FINDING = "HAS_FINDING"
EDGE_HAS_OBJECTION = "HAS_OBJECTION"

EDGE_AMENDS = "AMENDS"
EDGE_MODIFIES = "MODIFIES"
EDGE_ADDS = "ADDS"
EDGE_DELETES = "DELETES"

EDGE_CITES = "CITES"
EDGE_RELATED_TO = "RELATED_TO"

EDGE_COMBINES_WITH = "COMBINES_WITH"
EDGE_STARTING_REFERENCE = "STARTING_REFERENCE"

EDGE_DERIVED_FROM = "DERIVED_FROM"
EDGE_GENERATED_FROM = "GENERATED_FROM"

EDGE_CONTAINS = "CONTAINS"


# ---------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------

@dataclass
class GraphNode:

    node_id: str
    node_type: str

    label: str

    properties: Dict[str, Any]

    created_at: str

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(
            self
        )


@dataclass
class GraphEdge:

    edge_id: str

    source_id: str
    target_id: str

    edge_type: str

    properties: Dict[str, Any]

    created_at: str

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return asdict(
            self
        )


# ---------------------------------------------------------------------
# Graph
# ---------------------------------------------------------------------

class KnowledgeGraph:

    def __init__(
        self,
    ):

        self.nodes: Dict[
            str,
            GraphNode
        ] = {}

        self.edges: Dict[
            str,
            GraphEdge
        ] = {}

        self._outgoing: Dict[
            str,
            List[str]
        ] = {}

        self._incoming: Dict[
            str,
            List[str]
        ] = {}

    # -------------------------------------------------------------
    # Node operations
    # -------------------------------------------------------------

    def add_node(
        self,
        node_id: str,
        node_type: str,
        label: str,
        properties: Optional[
            Dict[str, Any]
        ] = None,
    ) -> GraphNode:

        node_id = _clean(
            node_id
        )

        if not node_id:

            raise ValueError(
                "node_id cannot be empty"
            )

        if node_id in self.nodes:

            existing = self.nodes[
                node_id
            ]

            if properties:

                existing.properties.update(
                    properties
                )

            if label:

                existing.label = label

            return existing

        node = GraphNode(
            node_id=node_id,
            node_type=node_type,
            label=_clean(
                label
            ),
            properties=(
                properties
                or {}
            ),
            created_at=_utc_now(),
        )

        self.nodes[
            node_id
        ] = node

        self._outgoing.setdefault(
            node_id,
            [],
        )

        self._incoming.setdefault(
            node_id,
            [],
        )

        return node

    def get_node(
        self,
        node_id: str,
    ) -> Optional[
        GraphNode
    ]:

        return self.nodes.get(
            node_id
        )

    def remove_node(
        self,
        node_id: str,
    ) -> bool:

        if node_id not in self.nodes:
            return False

        edge_ids = (
            self._outgoing.get(
                node_id,
                [],
            )
            + self._incoming.get(
                node_id,
                [],
            )
        )

        for edge_id in set(
            edge_ids
        ):

            self.remove_edge(
                edge_id
            )

        del self.nodes[
            node_id
        ]

        self._outgoing.pop(
            node_id,
            None,
        )

        self._incoming.pop(
            node_id,
            None,
        )

        return True

    # -------------------------------------------------------------
    # Edge operations
    # -------------------------------------------------------------

    def add_edge(
        self,
        source_id: str,
        target_id: str,
        edge_type: str,
        properties: Optional[
            Dict[str, Any]
        ] = None,
    ) -> GraphEdge:

        if source_id not in self.nodes:

            raise KeyError(
                f"Source node not found: {source_id}"
            )

        if target_id not in self.nodes:

            raise KeyError(
                f"Target node not found: {target_id}"
            )

        edge_id = _stable_id(
            "E",
            (
                f"{source_id}|"
                f"{target_id}|"
                f"{edge_type}|"
                f"{properties or {}}"
            ),
        )

        if edge_id in self.edges:

            return self.edges[
                edge_id
            ]

        edge = GraphEdge(
            edge_id=edge_id,
            source_id=source_id,
            target_id=target_id,
            edge_type=edge_type,
            properties=(
                properties
                or {}
            ),
            created_at=_utc_now(),
        )

        self.edges[
            edge_id
        ] = edge

        self._outgoing[
            source_id
        ].append(
            edge_id
        )

        self._incoming[
            target_id
        ].append(
            edge_id
        )

        return edge

    def get_edge(
        self,
        edge_id: str,
    ) -> Optional[
        GraphEdge
    ]:

        return self.edges.get(
            edge_id
        )

    def remove_edge(
        self,
        edge_id: str,
    ) -> bool:

        edge = self.edges.get(
            edge_id
        )

        if edge is None:
            return False

        if edge_id in self._outgoing.get(
            edge.source_id,
            [],
        ):

            self._outgoing[
                edge.source_id
            ].remove(
                edge_id
            )

        if edge_id in self._incoming.get(
            edge.target_id,
            [],
        ):

            self._incoming[
                edge.target_id
            ].remove(
                edge_id
            )

        del self.edges[
            edge_id
        ]

        return True

    # -------------------------------------------------------------
    # Traversal
    # -------------------------------------------------------------

    def outgoing_edges(
        self,
        node_id: str,
        edge_type: Optional[str] = None,
    ) -> List[GraphEdge]:

        result = []

        for edge_id in self._outgoing.get(
            node_id,
            [],
        ):

            edge = self.edges[
                edge_id
            ]

            if (
                edge_type is None
                or edge.edge_type
                == edge_type
            ):

                result.append(
                    edge
                )

        return result

    def incoming_edges(
        self,
        node_id: str,
        edge_type: Optional[str] = None,
    ) -> List[GraphEdge]:

        result = []

        for edge_id in self._incoming.get(
            node_id,
            [],
        ):

            edge = self.edges[
                edge_id
            ]

            if (
                edge_type is None
                or edge.edge_type
                == edge_type
            ):

                result.append(
                    edge
                )

        return result

    def neighbors(
        self,
        node_id: str,
    ) -> List[GraphNode]:

        ids = []

        for edge in self.outgoing_edges(
            node_id
        ):

            ids.append(
                edge.target_id
            )

        for edge in self.incoming_edges(
            node_id
        ):

            ids.append(
                edge.source_id
            )

        result = []

        for node_id in dict.fromkeys(
            ids
        ):

            node = self.get_node(
                node_id
            )

            if node:

                result.append(
                    node
                )

        return result

    # -------------------------------------------------------------
    # Queries
    # -------------------------------------------------------------

    def nodes_by_type(
        self,
        node_type: str,
    ) -> List[GraphNode]:

        return [
            node
            for node
            in self.nodes.values()
            if node.node_type
            == node_type
        ]

    def edges_by_type(
        self,
        edge_type: str,
    ) -> List[GraphEdge]:

        return [
            edge
            for edge
            in self.edges.values()
            if edge.edge_type
            == edge_type
        ]

    def find_nodes(
        self,
        *,
        node_type: Optional[str] = None,
        label_contains: Optional[str] = None,
        property_name: Optional[str] = None,
        property_value: Any = None,
    ) -> List[GraphNode]:

        result = []

        label_query = (
            label_contains.lower()
            if label_contains
            else None
        )

        for node in self.nodes.values():

            if (
                node_type
                and node.node_type
                != node_type
            ):
                continue

            if (
                label_query
                and label_query
                not in node.label.lower()
            ):
                continue

            if property_name:

                if (
                    node.properties.get(
                        property_name
                    )
                    != property_value
                ):
                    continue

            result.append(
                node
            )

        return result

    # -------------------------------------------------------------
    # Serialization
    # -------------------------------------------------------------

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return {
            "version":
                KNOWLEDGE_GRAPH_VERSION,

            "generated_at":
                _utc_now(),

            "nodes": [
                node.to_dict()
                for node
                in self.nodes.values()
            ],

            "edges": [
                edge.to_dict()
                for edge
                in self.edges.values()
            ],

            "statistics":
                self.statistics(),
        }

    def statistics(
        self,
    ) -> Dict[str, Any]:

        node_counts = {}

        for node in self.nodes.values():

            node_counts[
                node.node_type
            ] = (
                node_counts.get(
                    node.node_type,
                    0,
                )
                + 1
            )

        edge_counts = {}

        for edge in self.edges.values():

            edge_counts[
                edge.edge_type
            ] = (
                edge_counts.get(
                    edge.edge_type,
                    0,
                )
                + 1
            )

        return {
            "node_count":
                len(
                    self.nodes
                ),

            "edge_count":
                len(
                    self.edges
                ),

            "node_types":
                node_counts,

            "edge_types":
                edge_counts,
        }


# ---------------------------------------------------------------------
# Patent graph builder
# ---------------------------------------------------------------------

class PatentKnowledgeGraphBuilder:

    def __init__(
        self,
    ):

        self.graph = KnowledgeGraph()

    # -------------------------------------------------------------
    # Patent
    # -------------------------------------------------------------

    def add_patent(
        self,
        patent: Dict[str, Any],
    ) -> str:

        patent_id = _clean(
            patent.get(
                "patent_id",
                patent.get(
                    "application_number",
                    "",
                ),
            )
        )

        if not patent_id:

            patent_id = _stable_id(
                "PAT",
                patent,
            )

        self.graph.add_node(
            patent_id,
            NODE_PATENT,
            _clean(
                patent.get(
                    "title",
                    "Patent",
                )
            ),
            {
                "application_number":
                    _clean(
                        patent.get(
                            "application_number",
                            "",
                        )
                    ),

                "publication_number":
                    _clean(
                        patent.get(
                            "publication_number",
                            "",
                        )
                    ),

                "filing_date":
                    _clean(
                        patent.get(
                            "filing_date",
                            "",
                        )
                    ),

                "priority_date":
                    _clean(
                        patent.get(
                            "priority_date",
                            "",
                        )
                    ),

                "status":
                    _clean(
                        patent.get(
                            "status",
                            "",
                        )
                    ),
            },
        )

        return patent_id

    # -------------------------------------------------------------
    # Claims
    # -------------------------------------------------------------

    def add_claim(
        self,
        patent_id: str,
        claim: Dict[str, Any],
    ) -> str:

        number = _safe_int(
            claim.get(
                "claim_number",
                claim.get(
                    "number",
                    1,
                ),
            ),
            1,
        )

        claim_text = _clean(
            claim.get(
                "text",
                claim.get(
                    "claim_text",
                    "",
                ),
            )
        )

        claim_id = _clean(
            claim.get(
                "claim_id",
                "",
            )
        )

        if not claim_id:

            claim_id = _stable_id(
                "CLAIM",
                f"{patent_id}|{number}|{claim_text}",
            )

        self.graph.add_node(
            claim_id,
            NODE_CLAIM,
            f"Claim {number}",
            {
                "claim_number":
                    number,

                "text":
                    claim_text,

                "claim_type":
                    _clean(
                        claim.get(
                            "claim_type",
                            "",
                        )
                    ),

                "category":
                    _clean(
                        claim.get(
                            "category",
                            "",
                        )
                    ),
            },
        )

        self.graph.add_edge(
            patent_id,
            claim_id,
            EDGE_HAS_CLAIM,
        )

        return claim_id

    # -------------------------------------------------------------
    # Limitations
    # -------------------------------------------------------------

    def add_limitation(
        self,
        claim_id: str,
        limitation: Dict[str, Any],
        index: int = 1,
    ) -> str:

        limitation_text = _clean(
            limitation.get(
                "text",
                limitation.get(
                    "limitation",
                    limitation.get(
                        "description",
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
                f"{claim_id}|{index}|{limitation_text}",
            )

        self.graph.add_node(
            limitation_id,
            NODE_LIMITATION,
            f"Limitation {index}",
            {
                "text":
                    limitation_text,

                "index":
                    index,

                "type":
                    _clean(
                        limitation.get(
                            "type",
                            "",
                        )
                    ),
            },
        )

        self.graph.add_edge(
            claim_id,
            limitation_id,
            EDGE_HAS_LIMITATION,
        )

        return limitation_id

    # -------------------------------------------------------------
    # Prior art
    # -------------------------------------------------------------

    def add_prior_art_document(
        self,
        document: Dict[str, Any],
    ) -> str:

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
                document,
            )

        title = _clean(
            document.get(
                "title",
                document.get(
                    "name",
                    "Prior-art document",
                ),
            )
        )

        self.graph.add_node(
            document_id,
            NODE_DOCUMENT,
            title,
            {
                "publication_number":
                    _clean(
                        document.get(
                            "publication_number",
                            "",
                        )
                    ),

                "publication_date":
                    _clean(
                        document.get(
                            "publication_date",
                            "",
                        )
                    ),

                "priority_date":
                    _clean(
                        document.get(
                            "priority_date",
                            "",
                        )
                    ),

                "source":
                    _clean(
                        document.get(
                            "source",
                            document.get(
                                "url",
                                "",
                            ),
                        )
                    ),

                "text":
                    _clean(
                        document.get(
                            "text",
                            document.get(
                                "content",
                                "",
                            ),
                        )
                    ),
            },
        )

        return document_id

    # -------------------------------------------------------------
    # Evidence
    # -------------------------------------------------------------

    def add_evidence(
        self,
        evidence: Dict[str, Any],
    ) -> str:

        document_id = _clean(
            evidence.get(
                "document_id",
                "",
            )
        )

        limitation_id = _clean(
            evidence.get(
                "limitation_id",
                "",
            )
        )

        evidence_text = _clean(
            evidence.get(
                "text",
                evidence.get(
                    "passage",
                    evidence.get(
                        "evidence_text",
                        "",
                    ),
                ),
            )
        )

        evidence_id = _clean(
            evidence.get(
                "evidence_id",
                "",
            )
        )

        if not evidence_id:

            evidence_id = _stable_id(
                "EVID",
                (
                    f"{document_id}|"
                    f"{limitation_id}|"
                    f"{evidence_text}"
                ),
            )

        self.graph.add_node(
            evidence_id,
            NODE_EVIDENCE,
            "Evidence",
            {
                "text":
                    evidence_text,

                "document_id":
                    document_id,

                "limitation_id":
                    limitation_id,

                "score":
                    _safe_float(
                        evidence.get(
                            "combined_score",
                            evidence.get(
                                "score",
                                0.0,
                            ),
                        )
                    ),

                "semantic_score":
                    _safe_float(
                        evidence.get(
                            "semantic_score",
                            0.0,
                        )
                    ),

                "lexical_score":
                    _safe_float(
                        evidence.get(
                            "lexical_score",
                            0.0,
                        )
                    ),

                "page":
                    evidence.get(
                        "page",
                    ),

                "source":
                    _clean(
                        evidence.get(
                            "source",
                            "",
                        )
                    ),
            },
        )

        if document_id in self.graph.nodes:

            self.graph.add_edge(
                evidence_id,
                document_id,
                EDGE_EVIDENCE_FOR,
            )

        if limitation_id in self.graph.nodes:

            self.graph.add_edge(
                evidence_id,
                limitation_id,
                EDGE_SUPPORTED_BY,
            )

        return evidence_id

    # -------------------------------------------------------------
    # Legal provision
    # -------------------------------------------------------------

    def add_legal_provision(
        self,
        provision: Dict[str, Any],
    ) -> str:

        section = _clean(
            provision.get(
                "section",
                provision.get(
                    "code",
                    "",
                ),
            )
        )

        title = _clean(
            provision.get(
                "title",
                provision.get(
                    "name",
                    "",
                ),
            )
        )

        provision_id = _clean(
            provision.get(
                "provision_id",
                "",
            )
        )

        if not provision_id:

            provision_id = _stable_id(
                "LAW",
                f"{section}|{title}",
            )

        self.graph.add_node(
            provision_id,
            NODE_LEGAL_PROVISION,
            (
                f"Section {section}"
                + (
                    f" — {title}"
                    if title
                    else ""
                )
            ),
            {
                "section":
                    section,

                "title":
                    title,

                "summary":
                    _clean(
                        provision.get(
                            "summary",
                            "",
                        )
                    ),

                "source_url":
                    _clean(
                        provision.get(
                            "source_url",
                            "",
                        )
                    ),
            },
        )

        return provision_id

    # -------------------------------------------------------------
    # FER
    # -------------------------------------------------------------

    def add_fer_objection(
        self,
        objection: Dict[str, Any],
    ) -> str:

        objection_id = _clean(
            objection.get(
                "objection_id",
                objection.get(
                    "finding_id",
                    "",
                ),
            )
        )

        description = _clean(
            objection.get(
                "description",
                objection.get(
                    "text",
                    objection.get(
                        "objection",
                        "",
                    ),
                ),
            )
        )

        category = _clean(
            objection.get(
                "category",
                objection.get(
                    "type",
                    "",
                ),
            )
        )

        if not objection_id:

            objection_id = _stable_id(
                "FER",
                f"{category}|{description}",
            )

        self.graph.add_node(
            objection_id,
            NODE_FER,
            _clean(
                objection.get(
                    "title",
                    category
                    or "FER Objection",
                )
            ),
            {
                "category":
                    category,

                "description":
                    description,

                "severity":
                    _clean(
                        objection.get(
                            "severity",
                            "",
                        )
                    ),

                "confidence":
                    _safe_float(
                        objection.get(
                            "confidence",
                            0.0,
                        )
                    ),
            },
        )

        for claim_number in (
            objection.get(
                "claim_numbers",
                [],
            )
            if isinstance(
                objection.get(
                    "claim_numbers",
                    [],
                ),
                list,
            )
            else []
        ):

            claim_nodes = self.graph.find_nodes(
                node_type=NODE_CLAIM,
                property_name="claim_number",
                property_value=_safe_int(
                    claim_number
                ),
            )

            for claim_node in claim_nodes:

                self.graph.add_edge(
                    objection_id,
                    claim_node.node_id,
                    EDGE_APPLIES_TO,
                )

        return objection_id

    # -------------------------------------------------------------
    # Section 3
    # -------------------------------------------------------------

    def add_section3_finding(
        self,
        finding: Dict[str, Any],
    ) -> str:

        section = _clean(
            finding.get(
                "section",
                "",
            )
        )

        finding_id = _clean(
            finding.get(
                "finding_id",
                "",
            )
        )

        if not finding_id:

            finding_id = _stable_id(
                "S3",
                f"{section}|{finding}",
            )

        self.graph.add_node(
            finding_id,
            NODE_SECTION3,
            _clean(
                finding.get(
                    "title",
                    f"Section {section}",
                )
            ),
            {
                "section":
                    section,

                "status":
                    _clean(
                        finding.get(
                            "status",
                            "",
                        )
                    ),

                "confidence":
                    _safe_float(
                        finding.get(
                            "confidence",
                            0.0,
                        )
                    ),

                "reasoning":
                    _clean(
                        finding.get(
                            "reasoning",
                            finding.get(
                                "explanation",
                                "",
                            ),
                        )
                    ),
            },
        )

        for claim_number in (
            finding.get(
                "claim_numbers",
                [],
            )
            if isinstance(
                finding.get(
                    "claim_numbers",
                    [],
                ),
                list,
            )
            else []
        ):

            claim_nodes = self.graph.find_nodes(
                node_type=NODE_CLAIM,
                property_name="claim_number",
                property_value=_safe_int(
                    claim_number
                ),
            )

            for claim_node in claim_nodes:

                self.graph.add_edge(
                    finding_id,
                    claim_node.node_id,
                    EDGE_APPLIES_TO,
                )

        return finding_id

    # -------------------------------------------------------------
    # Novelty
    # -------------------------------------------------------------

    def add_novelty_finding(
        self,
        finding: Dict[str, Any],
    ) -> str:

        claim_number = _safe_int(
            finding.get(
                "claim_number",
                0,
            )
        )

        finding_id = _clean(
            finding.get(
                "finding_id",
                "",
            )
        )

        if not finding_id:

            finding_id = _stable_id(
                "NOV",
                f"{claim_number}|{finding}",
            )

        self.graph.add_node(
            finding_id,
            NODE_NOVELTY,
            (
                f"Novelty finding "
                f"— Claim {claim_number}"
            ),
            {
                "claim_number":
                    claim_number,

                "status":
                    _clean(
                        finding.get(
                            "status",
                            "",
                        )
                    ),

                "coverage":
                    _safe_float(
                        finding.get(
                            "coverage",
                            0.0,
                        )
                    ),

                "best_document_id":
                    _clean(
                        finding.get(
                            "best_document_id",
                            "",
                        )
                    ),

                "reasoning":
                    _clean(
                        finding.get(
                            "reasoning",
                            "",
                        )
                    ),
            },
        )

        claim_nodes = self.graph.find_nodes(
            node_type=NODE_CLAIM,
            property_name="claim_number",
            property_value=claim_number,
        )

        for claim_node in claim_nodes:

            self.graph.add_edge(
                finding_id,
                claim_node.node_id,
                EDGE_HAS_FINDING,
            )

        document_id = _clean(
            finding.get(
                "best_document_id",
                "",
            )
        )

        if (
            document_id
            and document_id
            in self.graph.nodes
        ):

            self.graph.add_edge(
                finding_id,
                document_id,
                EDGE_REFERENCES,
            )

        return finding_id

    # -------------------------------------------------------------
    # Inventive step
    # -------------------------------------------------------------

    def add_inventive_step_finding(
        self,
        finding: Dict[str, Any],
    ) -> str:

        claim_number = _safe_int(
            finding.get(
                "claim_number",
                0,
            )
        )

        finding_id = _clean(
            finding.get(
                "finding_id",
                "",
            )
        )

        if not finding_id:

            finding_id = _stable_id(
                "IS",
                f"{claim_number}|{finding}",
            )

        self.graph.add_node(
            finding_id,
            NODE_INVENTIVE_STEP,
            (
                f"Inventive-step finding "
                f"— Claim {claim_number}"
            ),
            {
                "claim_number":
                    claim_number,

                "status":
                    _clean(
                        finding.get(
                            "status",
                            "",
                        )
                    ),

                "evidence_strength":
                    _safe_float(
                        finding.get(
                            "evidence_strength",
                            0.0,
                        )
                    ),

                "starting_reference_id":
                    _clean(
                        finding.get(
                            "starting_reference_id",
                            "",
                        )
                    ),

                "reasoning":
                    _clean(
                        finding.get(
                            "reasoning",
                            "",
                        )
                    ),
            },
        )

        claim_nodes = self.graph.find_nodes(
            node_type=NODE_CLAIM,
            property_name="claim_number",
            property_value=claim_number,
        )

        for claim_node in claim_nodes:

            self.graph.add_edge(
                finding_id,
                claim_node.node_id,
                EDGE_HAS_FINDING,
            )

        starting_reference = _clean(
            finding.get(
                "starting_reference_id",
                "",
            )
        )

        if (
            starting_reference
            in self.graph.nodes
        ):

            self.graph.add_edge(
                finding_id,
                starting_reference,
                EDGE_STARTING_REFERENCE,
            )

        for combination in (
            finding.get(
                "combinations",
                [],
            )
        ):

            if not isinstance(
                combination,
                dict,
            ):
                continue

            ids = combination.get(
                "reference_ids",
                [],
            )

            if not isinstance(
                ids,
                list,
            ):
                continue

            valid_ids = [
                document_id
                for document_id
                in ids
                if document_id
                in self.graph.nodes
            ]

            if len(valid_ids) == 2:

                self.graph.add_edge(
                    valid_ids[0],
                    valid_ids[1],
                    EDGE_COMBINES_WITH,
                    {
                        "combination_id":
                            combination.get(
                                "combination_id",
                                "",
                            ),

                        "coverage":
                            _safe_float(
                                combination.get(
                                    "coverage",
                                    0.0,
                                )
                            ),

                        "complementarity":
                            _safe_float(
                                combination.get(
                                    "complementarity",
                                    0.0,
                                )
                            ),
                    },
                )

        return finding_id

    # -------------------------------------------------------------
    # Amendment
    # -------------------------------------------------------------

    def add_amendment(
        self,
        amendment: Dict[str, Any],
    ) -> str:

        claim_number = _safe_int(
            amendment.get(
                "claim_number",
                amendment.get(
                    "new_claim_number",
                    0,
                ),
            )
        )

        amendment_id = _clean(
            amendment.get(
                "amendment_id",
                "",
            )
        )

        if not amendment_id:

            amendment_id = _stable_id(
                "AMD",
                amendment,
            )

        self.graph.add_node(
            amendment_id,
            NODE_AMENDMENT,
            (
                f"Amendment "
                f"— Claim {claim_number}"
            ),
            {
                "claim_number":
                    claim_number,

                "amendment_date":
                    _clean(
                        amendment.get(
                            "amendment_date",
                            "",
                        )
                    ),

                "status":
                    _clean(
                        amendment.get(
                            "status",
                            "",
                        )
                    ),

                "added_count":
                    len(
                        amendment.get(
                            "added_limitations",
                            amendment.get(
                                "added",
                                [],
                            ),
                        )
                        or []
                    ),

                "modified_count":
                    len(
                        amendment.get(
                            "modified_limitations",
                            amendment.get(
                                "modified",
                                [],
                            ),
                        )
                        or []
                    ),

                "deleted_count":
                    len(
                        amendment.get(
                            "deleted_limitations",
                            amendment.get(
                                "deleted",
                                [],
                            )
                        )
                        or []
                    ),
            },
        )

        claim_nodes = self.graph.find_nodes(
            node_type=NODE_CLAIM,
            property_name="claim_number",
            property_value=claim_number,
        )

        for claim_node in claim_nodes:

            self.graph.add_edge(
                amendment_id,
                claim_node.node_id,
                EDGE_AMENDS,
            )

        return amendment_id

    # -------------------------------------------------------------
    # Complete patent graph
    # -------------------------------------------------------------

    def build(
        self,
        *,
        patent: Optional[
            Dict[str, Any]
        ] = None,
        claims: Optional[
            Iterable[Any]
        ] = None,
        prior_art: Optional[
            Iterable[Any]
        ] = None,
        evidence: Optional[
            Iterable[Any]
        ] = None,
        legal_provisions: Optional[
            Iterable[Any]
        ] = None,
        fer_analysis: Optional[
            Dict[str, Any]
        ] = None,
        section3_analysis: Optional[
            Dict[str, Any]
        ] = None,
        novelty_analysis: Optional[
            Dict[str, Any]
        ] = None,
        inventive_step_analysis: Optional[
            Dict[str, Any]
        ] = None,
        amendment_analysis: Optional[
            Dict[str, Any]
        ] = None,
    ) -> KnowledgeGraph:

        patent_id = ""

        if patent:

            patent_id = self.add_patent(
                patent
            )

        # ---------------------------------------------------------
        # Claims
        # ---------------------------------------------------------

        claim_map = {}

        for index, raw_claim in enumerate(
            claims or [],
            start=1,
        ):

            if isinstance(
                raw_claim,
                dict,
            ):

                claim = raw_claim

            else:

                claim = {
                    "claim_number":
                        index,

                    "text":
                        _clean(
                            raw_claim
                        ),
                }

            if not patent_id:

                patent_id = self.add_patent(
                    {
                        "title":
                            "Patent Analysis",
                    }
                )

            claim_id = self.add_claim(
                patent_id,
                claim,
            )

            claim_number = _safe_int(
                claim.get(
                    "claim_number",
                    index,
                ),
                index,
            )

            claim_map[
                claim_number
            ] = claim_id

            limitations = claim.get(
                "limitations",
                [],
            )

            for limitation_index, limitation in enumerate(
                limitations,
                start=1,
            ):

                if not isinstance(
                    limitation,
                    dict,
                ):

                    limitation = {
                        "text":
                            _clean(
                                limitation
                            )
                    }

                self.add_limitation(
                    claim_id,
                    limitation,
                    limitation_index,
                )

        # ---------------------------------------------------------
        # Prior art
        # ---------------------------------------------------------

        for document in prior_art or []:

            if not isinstance(
                document,
                dict,
            ):
                continue

            self.add_prior_art_document(
                document
            )

        # ---------------------------------------------------------
        # Evidence
        # ---------------------------------------------------------

        for item in evidence or []:

            if not isinstance(
                item,
                dict,
            ):
                continue

            self.add_evidence(
                item
            )

        # ---------------------------------------------------------
        # Legal provisions
        # ---------------------------------------------------------

        for provision in legal_provisions or []:

            if not isinstance(
                provision,
                dict,
            ):
                continue

            self.add_legal_provision(
                provision
            )

        # ---------------------------------------------------------
        # FER
        # ---------------------------------------------------------

        if fer_analysis:

            for objection in _iter_dicts(
                fer_analysis.get(
                    "objections",
                    fer_analysis.get(
                        "findings",
                        [],
                    ),
                )
            ):

                self.add_fer_objection(
                    objection
                )

        # ---------------------------------------------------------
        # Section 3
        # ---------------------------------------------------------

        if section3_analysis:

            for finding in _iter_dicts(
                section3_analysis.get(
                    "findings",
                    [],
                )
            ):

                self.add_section3_finding(
                    finding
                )

        # ---------------------------------------------------------
        # Novelty
        # ---------------------------------------------------------

        if novelty_analysis:

            for finding in _iter_dicts(
                novelty_analysis.get(
                    "claims",
                    [],
                )
            ):

                self.add_novelty_finding(
                    finding
                )

        # ---------------------------------------------------------
        # Inventive step
        # ---------------------------------------------------------

        if inventive_step_analysis:

            for finding in _iter_dicts(
                inventive_step_analysis.get(
                    "claims",
                    [],
                )
            ):

                self.add_inventive_step_finding(
                    finding
                )

        # ---------------------------------------------------------
        # Amendments
        # ---------------------------------------------------------

        if amendment_analysis:

            comparisons = (
                amendment_analysis.get(
                    "comparisons",
                    amendment_analysis.get(
                        "claims",
                        [],
                    ),
                )
            )

            for amendment in _iter_dicts(
                comparisons
            ):

                self.add_amendment(
                    amendment
                )

        return self.graph


# ---------------------------------------------------------------------
# Graph queries
# ---------------------------------------------------------------------

def get_claim_evidence(
    graph: KnowledgeGraph,
    claim_id: str,
) -> List[Dict[str, Any]]:

    evidence = []

    claim_node = graph.get_node(
        claim_id
    )

    if not claim_node:
        return evidence

    limitation_nodes = []

    for edge in graph.outgoing_edges(
        claim_id,
        EDGE_HAS_LIMITATION,
    ):

        node = graph.get_node(
            edge.target_id
        )

        if node:

            limitation_nodes.append(
                node
            )

    for limitation in limitation_nodes:

        for edge in graph.incoming_edges(
            limitation.node_id,
            EDGE_SUPPORTED_BY,
        ):

            evidence_node = graph.get_node(
                edge.source_id
            )

            if not evidence_node:
                continue

            evidence.append(
                {
                    "claim_id":
                        claim_id,

                    "limitation_id":
                        limitation.node_id,

                    "limitation":
                        limitation.properties.get(
                            "text",
                            "",
                        ),

                    "evidence_id":
                        evidence_node.node_id,

                    "evidence":
                        evidence_node.properties.get(
                            "text",
                            "",
                        ),

                    "score":
                        evidence_node.properties.get(
                            "score",
                            0.0,
                        ),

                    "document_id":
                        evidence_node.properties.get(
                            "document_id",
                            "",
                        ),
                }
            )

    return evidence


def get_document_disclosures(
    graph: KnowledgeGraph,
    document_id: str,
) -> List[Dict[str, Any]]:

    result = []

    document = graph.get_node(
        document_id
    )

    if not document:
        return result

    for edge in graph.incoming_edges(
        document_id,
        EDGE_EVIDENCE_FOR,
    ):

        evidence = graph.get_node(
            edge.source_id
        )

        if not evidence:
            continue

        limitation_id = (
            evidence.properties.get(
                "limitation_id",
                "",
            )
        )

        limitation = graph.get_node(
            limitation_id
        )

        result.append(
            {
                "evidence_id":
                    evidence.node_id,

                "limitation_id":
                    limitation_id,

                "limitation":
                    (
                        limitation.properties.get(
                            "text",
                            "",
                        )
                        if limitation
                        else ""
                    ),

                "evidence":
                    evidence.properties.get(
                        "text",
                        "",
                    ),

                "score":
                    evidence.properties.get(
                        "score",
                        0.0,
                    ),
            }
        )

    return result


def get_claim_findings(
    graph: KnowledgeGraph,
    claim_number: int,
) -> Dict[str, List[Dict[str, Any]]]:

    result = {
        "novelty": [],
        "inventive_step": [],
        "section3": [],
        "fer": [],
        "amendments": [],
    }

    claim_nodes = graph.find_nodes(
        node_type=NODE_CLAIM,
        property_name="claim_number",
        property_value=claim_number,
    )

    claim_ids = {
        node.node_id
        for node
        in claim_nodes
    }

    for claim_id in claim_ids:

        for edge in graph.incoming_edges(
            claim_id
        ):

            source = graph.get_node(
                edge.source_id
            )

            if not source:
                continue

            if source.node_type == NODE_NOVELTY:

                result[
                    "novelty"
                ].append(
                    source.to_dict()
                )

            elif (
                source.node_type
                == NODE_INVENTIVE_STEP
            ):

                result[
                    "inventive_step"
                ].append(
                    source.to_dict()
                )

            elif (
                source.node_type
                == NODE_SECTION3
            ):

                result[
                    "section3"
                ].append(
                    source.to_dict()
                )

            elif source.node_type == NODE_FER:

                result[
                    "fer"
                ].append(
                    source.to_dict()
                )

            elif (
                source.node_type
                == NODE_AMENDMENT
            ):

                result[
                    "amendments"
                ].append(
                    source.to_dict()
                )

    return result


def get_prior_art_for_claim(
    graph: KnowledgeGraph,
    claim_number: int,
) -> List[Dict[str, Any]]:

    findings = get_claim_findings(
        graph,
        claim_number,
    )

    document_ids = set()

    for finding in (
        findings[
            "novelty"
        ]
    ):

        document_id = _clean(
            finding[
                "properties"
            ].get(
                "best_document_id",
                "",
            )
        )

        if document_id:
            document_ids.add(
                document_id
            )

    for finding in (
        findings[
            "inventive_step"
        ]
    ):

        properties = finding[
            "properties"
        ]

        starting_reference = _clean(
            properties.get(
                "starting_reference_id",
                "",
            )
        )

        if starting_reference:

            document_ids.add(
                starting_reference
            )

    result = []

    for document_id in document_ids:

        document = graph.get_node(
            document_id
        )

        if document:

            result.append(
                document.to_dict()
            )

    return result


# ---------------------------------------------------------------------
# Evidence path
# ---------------------------------------------------------------------

def trace_evidence_path(
    graph: KnowledgeGraph,
    evidence_id: str,
) -> Dict[str, Any]:

    evidence = graph.get_node(
        evidence_id
    )

    if not evidence:

        return {
            "found":
                False,

            "path":
                [],
        }

    path = [
        {
            "node_id":
                evidence.node_id,

            "node_type":
                evidence.node_type,

            "label":
                evidence.label,
        }
    ]

    limitation_id = evidence.properties.get(
        "limitation_id",
        "",
    )

    limitation = graph.get_node(
        limitation_id
    )

    if limitation:

        path.append(
            {
                "node_id":
                    limitation.node_id,

                "node_type":
                    limitation.node_type,

                "label":
                    limitation.label,
            }
        )

        for edge in graph.incoming_edges(
            limitation.node_id,
            EDGE_HAS_LIMITATION,
        ):

            claim = graph.get_node(
                edge.source_id
            )

            if claim:

                path.append(
                    {
                        "node_id":
                            claim.node_id,

                        "node_type":
                            claim.node_type,

                        "label":
                            claim.label,
                    }
                )

                break

    document_id = evidence.properties.get(
        "document_id",
        "",
    )

    document = graph.get_node(
        document_id
    )

    if document:

        path.append(
            {
                "node_id":
                    document.node_id,

                "node_type":
                    document.node_type,

                "label":
                    document.label,
            }
        )

    return {
        "found":
            True,

        "path":
            path,
    }


# ---------------------------------------------------------------------
# Graph validation
# ---------------------------------------------------------------------

def validate_graph(
    graph: KnowledgeGraph,
) -> Dict[str, Any]:

    errors = []
    warnings = []

    for edge in graph.edges.values():

        if edge.source_id not in graph.nodes:

            errors.append(
                (
                    f"Missing source node "
                    f"{edge.source_id}"
                )
            )

        if edge.target_id not in graph.nodes:

            errors.append(
                (
                    f"Missing target node "
                    f"{edge.target_id}"
                )
            )

    # Evidence should normally point to a document.
    for evidence in graph.nodes_by_type(
        NODE_EVIDENCE
    ):

        document_id = evidence.properties.get(
            "document_id",
            "",
        )

        if (
            document_id
            and document_id
            not in graph.nodes
        ):

            warnings.append(
                (
                    f"Evidence {evidence.node_id} "
                    f"references missing document "
                    f"{document_id}"
                )
            )

    return {
        "valid":
            not errors,

        "error_count":
            len(errors),

        "warning_count":
            len(warnings),

        "errors":
            errors,

        "warnings":
            warnings,
    }


# ---------------------------------------------------------------------
# Export helpers
# ---------------------------------------------------------------------

def export_graph_json(
    graph: KnowledgeGraph,
) -> Dict[str, Any]:

    return graph.to_dict()


def build_knowledge_graph(
    *,
    patent: Optional[
        Dict[str, Any]
    ] = None,
    claims: Optional[
        Iterable[Any]
    ] = None,
    prior_art: Optional[
        Iterable[Any]
    ] = None,
    evidence: Optional[
        Iterable[Any]
    ] = None,
    legal_provisions: Optional[
        Iterable[Any]
    ] = None,
    fer_analysis: Optional[
        Dict[str, Any]
    ] = None,
    section3_analysis: Optional[
        Dict[str, Any]
    ] = None,
    novelty_analysis: Optional[
        Dict[str, Any]
    ] = None,
    inventive_step_analysis: Optional[
        Dict[str, Any]
    ] = None,
    amendment_analysis: Optional[
        Dict[str, Any]
    ] = None,
) -> KnowledgeGraph:

    builder = (
        PatentKnowledgeGraphBuilder()
    )

    return builder.build(
        patent=patent,
        claims=claims,
        prior_art=prior_art,
        evidence=evidence,
        legal_provisions=legal_provisions,
        fer_analysis=fer_analysis,
        section3_analysis=section3_analysis,
        novelty_analysis=novelty_analysis,
        inventive_step_analysis=(
            inventive_step_analysis
        ),
        amendment_analysis=amendment_analysis,
    )


# ---------------------------------------------------------------------
# Backward-compatible aliases
# ---------------------------------------------------------------------

def create_knowledge_graph(
    **kwargs: Any,
) -> KnowledgeGraph:

    return build_knowledge_graph(
        **kwargs
    )


def create_graph(
    **kwargs: Any,
) -> KnowledgeGraph:

    return build_knowledge_graph(
        **kwargs
    )


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

__all__ = [
    "KNOWLEDGE_GRAPH_VERSION",

    "NODE_PATENT",
    "NODE_APPLICATION",
    "NODE_CLAIM",
    "NODE_LIMITATION",
    "NODE_DOCUMENT",
    "NODE_EVIDENCE",
    "NODE_FER",
    "NODE_SECTION3",
    "NODE_NOVELTY",
    "NODE_INVENTIVE_STEP",
    "NODE_AMENDMENT",
    "NODE_LEGAL_PROVISION",
    "NODE_PARAGRAPH",
    "NODE_SEARCH_QUERY",

    "EDGE_HAS_CLAIM",
    "EDGE_HAS_LIMITATION",
    "EDGE_SUPPORTED_BY",
    "EDGE_EVIDENCE_FOR",
    "EDGE_DISCLOSES",
    "EDGE_PARTIALLY_DISCLOSES",
    "EDGE_DOES_NOT_DISCLOSE",
    "EDGE_REFERENCES",
    "EDGE_APPLIES_TO",
    "EDGE_HAS_FINDING",
    "EDGE_HAS_OBJECTION",
    "EDGE_AMENDS",
    "EDGE_MODIFIES",
    "EDGE_ADDS",
    "EDGE_DELETES",
    "EDGE_CITES",
    "EDGE_RELATED_TO",
    "EDGE_COMBINES_WITH",
    "EDGE_STARTING_REFERENCE",
    "EDGE_DERIVED_FROM",
    "EDGE_GENERATED_FROM",
    "EDGE_CONTAINS",

    "GraphNode",
    "GraphEdge",
    "KnowledgeGraph",
    "PatentKnowledgeGraphBuilder",

    "get_claim_evidence",
    "get_document_disclosures",
    "get_claim_findings",
    "get_prior_art_for_claim",
    "trace_evidence_path",
    "validate_graph",
    "export_graph_json",

    "build_knowledge_graph",
    "create_knowledge_graph",
    "create_graph",
]
