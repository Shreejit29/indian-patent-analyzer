"""
Indian Patent Legal Knowledge Layer V3
======================================

Purpose
-------
Centralized, versioned legal-reference layer for the Indian Patent
Analyzer.

This module stores structured references to provisions that the
analysis engines may need, including:

    - Patents Act, 1970
    - Section 3
    - Section 10
    - Section 57
    - Section 59
    - Rules / prosecution concepts

Design principle
----------------
Legal knowledge is separate from AI reasoning.

The rule engine may consume this module, while Gemini may explain
the resulting findings.

The module does NOT provide legal advice or determine the legal
validity of a patent/application.

Version
-------
3.0.0

IMPORTANT
---------
The provision summaries below are intentionally concise. They should
be synchronized against the current official statutory text before
being used as the authoritative legal source in a production
prosecution workflow.

For production deployment, store the official source URL, effective
date, retrieval date and document hash alongside each legal source.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional


LEGAL_KNOWLEDGE_VERSION = "3.0.0"


# ---------------------------------------------------------------------
# Utilities
# ---------------------------------------------------------------------

def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean(value: Any) -> str:
    if value is None:
        return ""

    return re.sub(
        r"\s+",
        " ",
        str(value),
    ).strip()


def _stable_hash(value: str) -> str:
    return hashlib.sha256(
        _clean(value).encode(
            "utf-8"
        )
    ).hexdigest()


def _unique(
    values: Iterable[Any],
) -> List[Any]:

    result = []
    seen = set()

    for value in values:

        key = str(value).strip().lower()

        if not key or key in seen:
            continue

        seen.add(key)
        result.append(value)

    return result


# ---------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------

@dataclass
class LegalProvision:

    provision_id: str
    act: str
    provision: str
    title: str
    summary: str
    analysis_topics: List[str]
    source_url: str = ""
    source_type: str = "official"
    effective_from: str = ""
    retrieved_at: str = ""
    source_hash: str = ""
    verification_status: str = "reference"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class LegalSource:

    source_id: str
    title: str
    source_url: str
    source_type: str
    retrieved_at: str
    effective_from: str = ""
    document_hash: str = ""
    verification_status: str = "unverified"

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------
# Official source references
# ---------------------------------------------------------------------

# These URLs are source references only. The application should refresh
# and verify them before treating them as current authoritative text.

IPINDIA_ACT_URL = (
    "https://ipindia.gov.in/"
)

IPINDIA_RULES_URL = (
    "https://ipindia.gov.in/"
)


# ---------------------------------------------------------------------
# Provision database
# ---------------------------------------------------------------------

DEFAULT_PROVISIONS: List[LegalProvision] = [

    LegalProvision(
        provision_id="PA-3",
        act="Patents Act, 1970",
        provision="Section 3",
        title="What are not inventions",
        summary=(
            "Identifies categories of subject matter that are excluded "
            "from the meaning of invention under the Act."
        ),
        analysis_topics=[
            "patentability",
            "excluded_subject_matter",
            "section_3",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-3-A",
        act="Patents Act, 1970",
        provision="Section 3(a)",
        title="Frivolous inventions / contrary to natural laws",
        summary=(
            "Exclusion relating to frivolous inventions or claims "
            "contrary to well-established natural laws."
        ),
        analysis_topics=[
            "section_3",
            "natural_laws",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-3-B",
        act="Patents Act, 1970",
        provision="Section 3(b)",
        title="Public order / morality / specified harmful subject matter",
        summary=(
            "Covers specified subject matter involving public order, "
            "morality, or certain harmful uses."
        ),
        analysis_topics=[
            "section_3",
            "public_order",
            "morality",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-3-C",
        act="Patents Act, 1970",
        provision="Section 3(c)",
        title="Mere discovery of scientific principle or abstract theory",
        summary=(
            "Concerns mere discovery of a scientific principle, "
            "abstract theory, or naturally occurring living or "
            "non-living substance, subject to the statutory wording."
        ),
        analysis_topics=[
            "section_3",
            "discovery",
            "scientific_principle",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-3-D",
        act="Patents Act, 1970",
        provision="Section 3(d)",
        title="New form / new property / new use of known substance",
        summary=(
            "Addresses specified claims involving known substances, "
            "including new forms, properties, or uses, subject to "
            "the statutory requirements and explanations."
        ),
        analysis_topics=[
            "section_3",
            "known_substance",
            "pharmaceuticals",
            "efficacy",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-3-E",
        act="Patents Act, 1970",
        provision="Section 3(e)",
        title="Substance obtained by mere admixture",
        summary=(
            "Addresses specified compositions resulting from mere "
            "admixture where the statutory conditions are met."
        ),
        analysis_topics=[
            "section_3",
            "composition",
            "admixture",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-3-F",
        act="Patents Act, 1970",
        provision="Section 3(f)",
        title="Mere arrangement or re-arrangement of known devices",
        summary=(
            "Addresses specified arrangements or re-arrangements "
            "of known devices where each functions independently "
            "in a known way."
        ),
        analysis_topics=[
            "section_3",
            "known_devices",
            "arrangement",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-3-G",
        act="Patents Act, 1970",
        provision="Section 3(g)",
        title="Certain excluded agricultural / horticultural methods",
        summary=(
            "Addresses specified methods relating to agriculture or "
            "horticulture excluded under the Act."
        ),
        analysis_topics=[
            "section_3",
            "agriculture",
            "horticulture",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-3-H",
        act="Patents Act, 1970",
        provision="Section 3(h)",
        title="Certain methods of medical treatment",
        summary=(
            "Addresses specified methods of treatment of humans or "
            "animals excluded under the Act."
        ),
        analysis_topics=[
            "section_3",
            "medical_treatment",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-3-I",
        act="Patents Act, 1970",
        provision="Section 3(i)",
        title="Diagnostic / therapeutic / surgical processes",
        summary=(
            "Addresses specified diagnostic, therapeutic or surgical "
            "processes for treatment of humans or animals."
        ),
        analysis_topics=[
            "section_3",
            "diagnostic",
            "therapeutic",
            "surgical",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-3-J",
        act="Patents Act, 1970",
        provision="Section 3(j)",
        title="Plants and animals / biological processes",
        summary=(
            "Addresses specified plants, animals, seeds, varieties, "
            "species and essentially biological processes, subject "
            "to the statutory exceptions."
        ),
        analysis_topics=[
            "section_3",
            "biological_material",
            "plants",
            "animals",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-3-K",
        act="Patents Act, 1970",
        provision="Section 3(k)",
        title="Mathematical methods / business methods / computer program per se",
        summary=(
            "Addresses specified mathematical methods, business "
            "methods, computer programmes per se and algorithms."
        ),
        analysis_topics=[
            "section_3",
            "software",
            "computer_program",
            "algorithm",
            "business_method",
            "mathematical_method",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-3-L",
        act="Patents Act, 1970",
        provision="Section 3(l)",
        title="Literary / dramatic / musical / artistic works",
        summary=(
            "Addresses specified literary, dramatic, musical or "
            "artistic works and certain related subject matter."
        ),
        analysis_topics=[
            "section_3",
            "copyright_subject_matter",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-3-M",
        act="Patents Act, 1970",
        provision="Section 3(m)",
        title="Scheme / rule / method of performing mental act or game",
        summary=(
            "Addresses specified schemes, rules, methods of "
            "performing mental acts, or methods of playing games."
        ),
        analysis_topics=[
            "section_3",
            "mental_act",
            "game",
            "scheme",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-3-N",
        act="Patents Act, 1970",
        provision="Section 3(n)",
        title="Presentation of information",
        summary=(
            "Addresses specified presentation of information."
        ),
        analysis_topics=[
            "section_3",
            "information_presentation",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-3-O",
        act="Patents Act, 1970",
        provision="Section 3(o)",
        title="Topography of integrated circuits",
        summary=(
            "Addresses specified topography of integrated circuits."
        ),
        analysis_topics=[
            "section_3",
            "integrated_circuit",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-3-P",
        act="Patents Act, 1970",
        provision="Section 3(p)",
        title="Traditional knowledge / aggregation of known properties",
        summary=(
            "Addresses specified traditional knowledge and "
            "aggregation or duplication of known properties of "
            "traditionally known components."
        ),
        analysis_topics=[
            "section_3",
            "traditional_knowledge",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-10",
        act="Patents Act, 1970",
        provision="Section 10",
        title="Contents of specifications",
        summary=(
            "Sets statutory requirements concerning the contents "
            "of patent specifications, including claim and "
            "description-related requirements."
        ),
        analysis_topics=[
            "specification",
            "claims",
            "support",
            "sufficiency",
            "clarity",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-57",
        act="Patents Act, 1970",
        provision="Section 57",
        title="Amendment of applications and specifications",
        summary=(
            "Provides the statutory framework for amendment of "
            "applications or specifications, subject to the Act."
        ),
        analysis_topics=[
            "amendment",
            "prosecution",
            "specification",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PA-59",
        act="Patents Act, 1970",
        provision="Section 59",
        title="Supplementary provisions as to amendment",
        summary=(
            "Contains statutory restrictions and requirements "
            "applicable to amendments of applications and "
            "specifications."
        ),
        analysis_topics=[
            "amendment",
            "new_matter",
            "claim_scope",
            "prosecution",
        ],
        source_url=IPINDIA_ACT_URL,
        verification_status="reference",
    ),
]


# ---------------------------------------------------------------------
# Rule references
# ---------------------------------------------------------------------

DEFAULT_RULE_REFERENCES: List[LegalProvision] = [

    LegalProvision(
        provision_id="PR-01",
        act="Patents Rules, 2003",
        provision="Rule 13",
        title="Specification and amendments",
        summary=(
            "Reference point for procedural matters relating to "
            "specifications and amendments."
        ),
        analysis_topics=[
            "specification",
            "amendment",
        ],
        source_url=IPINDIA_RULES_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PR-02",
        act="Patents Rules, 2003",
        provision="Rule 24B",
        title="Request for examination",
        summary=(
            "Reference point concerning the request for examination "
            "and associated procedural requirements."
        ),
        analysis_topics=[
            "examination",
            "prosecution",
        ],
        source_url=IPINDIA_RULES_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PR-03",
        act="Patents Rules, 2003",
        provision="Rule 28",
        title="Hearing",
        summary=(
            "Reference point concerning hearing-related procedure "
            "in patent examination."
        ),
        analysis_topics=[
            "hearing",
            "prosecution",
        ],
        source_url=IPINDIA_RULES_URL,
        verification_status="reference",
    ),

    LegalProvision(
        provision_id="PR-04",
        act="Patents Rules, 2003",
        provision="Rule 29",
        title="Amendment-related procedure",
        summary=(
            "Reference point for procedural matters associated "
            "with amendments."
        ),
        analysis_topics=[
            "amendment",
            "prosecution",
        ],
        source_url=IPINDIA_RULES_URL,
        verification_status="reference",
    ),
]


# ---------------------------------------------------------------------
# Legal knowledge registry
# ---------------------------------------------------------------------

class LegalKnowledgeBase:

    def __init__(
        self,
        provisions: Optional[
            Iterable[LegalProvision]
        ] = None,
    ):

        if provisions is None:

            provisions = (
                DEFAULT_PROVISIONS
                + DEFAULT_RULE_REFERENCES
            )

        self.provisions = list(
            provisions
        )

        self.created_at = _utc_now()

    # -----------------------------------------------------------------
    # Lookup
    # -----------------------------------------------------------------

    def get(
        self,
        provision: str,
    ) -> Optional[LegalProvision]:

        target = _clean(
            provision
        ).lower()

        for item in self.provisions:

            if (
                item.provision.lower()
                == target
            ):
                return item

        return None

    def get_by_id(
        self,
        provision_id: str,
    ) -> Optional[LegalProvision]:

        target = _clean(
            provision_id
        ).lower()

        for item in self.provisions:

            if (
                item.provision_id.lower()
                == target
            ):
                return item

        return None

    def search(
        self,
        query: str,
    ) -> List[LegalProvision]:

        query = _clean(
            query
        ).lower()

        if not query:
            return []

        tokens = set(
            query.split()
        )

        scored = []

        for provision in self.provisions:

            searchable = " ".join(
                [
                    provision.provision,
                    provision.title,
                    provision.summary,
                    " ".join(
                        provision.analysis_topics
                    ),
                ]
            ).lower()

            score = 0

            if query in searchable:
                score += 5

            for token in tokens:

                if token in searchable:
                    score += 1

            if score:

                scored.append(
                    (
                        score,
                        provision,
                    )
                )

        scored.sort(
            key=lambda item:
                item[0],
            reverse=True,
        )

        return [
            provision
            for _, provision
            in scored
        ]

    # -----------------------------------------------------------------
    # Section 3
    # -----------------------------------------------------------------

    def section_3(
        self,
        subsection: Optional[str] = None,
    ) -> List[LegalProvision]:

        if subsection:

            target = (
                "Section 3"
                + subsection
                .replace(
                    "Section 3",
                    "",
                )
                .replace(
                    "section 3",
                    "",
                )
                .strip()
            )

            return [
                item
                for item in self.provisions
                if item.provision.lower()
                == target.lower()
            ]

        return [
            item
            for item in self.provisions
            if item.provision.lower()
            == "section 3"
            or item.provision.lower().startswith(
                "section 3("
            )
        ]

    # -----------------------------------------------------------------
    # Topic lookup
    # -----------------------------------------------------------------

    def by_topic(
        self,
        topic: str,
    ) -> List[LegalProvision]:

        topic = _clean(
            topic
        ).lower()

        return [
            item
            for item in self.provisions
            if any(
                topic
                in str(
                    analysis_topic
                ).lower()
                for analysis_topic
                in item.analysis_topics
            )
        ]

    # -----------------------------------------------------------------
    # Export
    # -----------------------------------------------------------------

    def to_dict(
        self,
    ) -> Dict[str, Any]:

        return {
            "legal_knowledge_version":
                LEGAL_KNOWLEDGE_VERSION,

            "created_at":
                self.created_at,

            "provision_count":
                len(self.provisions),

            "provisions": [
                item.to_dict()
                for item in self.provisions
            ],
        }


# ---------------------------------------------------------------------
# Source management
# ---------------------------------------------------------------------

def build_legal_source(
    title: str,
    source_url: str,
    source_text: str = "",
    *,
    source_type: str = "official",
    effective_from: str = "",
    verification_status: str = "unverified",
) -> LegalSource:

    document_hash = ""

    if source_text:

        document_hash = _stable_hash(
            source_text
        )

    source_id = _stable_hash(
        title
        + "|"
        + source_url
        + "|"
        + document_hash
    )[:16]

    return LegalSource(
        source_id=source_id,
        title=_clean(title),
        source_url=_clean(source_url),
        source_type=_clean(
            source_type
        ),
        retrieved_at=_utc_now(),
        effective_from=_clean(
            effective_from
        ),
        document_hash=document_hash,
        verification_status=_clean(
            verification_status
        ),
    )


# ---------------------------------------------------------------------
# Versioned legal snapshot
# ---------------------------------------------------------------------

def create_legal_snapshot(
    *,
    provisions: Optional[
        Iterable[LegalProvision]
    ] = None,
    sources: Optional[
        Iterable[LegalSource]
    ] = None,
) -> Dict[str, Any]:

    if provisions is None:

        provisions = (
            DEFAULT_PROVISIONS
            + DEFAULT_RULE_REFERENCES
        )

    provisions = list(
        provisions
    )

    if sources is None:
        sources = []

    sources = list(
        sources
    )

    payload = (
        [
            item.to_dict()
            for item in provisions
        ]
        +
        [
            item.to_dict()
            for item in sources
        ]
    )

    snapshot_hash = _stable_hash(
        str(payload)
    )

    return {
        "legal_knowledge_version":
            LEGAL_KNOWLEDGE_VERSION,

        "created_at":
            _utc_now(),

        "snapshot_hash":
            snapshot_hash,

        "provisions": [
            item.to_dict()
            for item in provisions
        ],

        "sources": [
            item.to_dict()
            for item in sources
        ],
    }


# ---------------------------------------------------------------------
# Rule-engine integration
# ---------------------------------------------------------------------

def get_rule_reference(
    rule_id: str,
) -> Optional[Dict[str, Any]]:

    rule_id = _clean(
        rule_id
    ).upper()

    mapping = {

        "SEC3-A":
            "Section 3(a)",

        "SEC3-B":
            "Section 3(b)",

        "SEC3-C":
            "Section 3(c)",

        "SEC3-D":
            "Section 3(d)",

        "SEC3-E":
            "Section 3(e)",

        "SEC3-F":
            "Section 3(f)",

        "SEC3-G":
            "Section 3(g)",

        "SEC3-H":
            "Section 3(h)",

        "SEC3-I":
            "Section 3(i)",

        "SEC3-J":
            "Section 3(j)",

        "SEC3-K":
            "Section 3(k)",

        "SEC3-L":
            "Section 3(l)",

        "SEC3-M":
            "Section 3(m)",

        "SEC3-N":
            "Section 3(n)",

        "SEC3-O":
            "Section 3(o)",

        "SEC3-P":
            "Section 3(p)",

        "SEC10":
            "Section 10",

        "SEC59":
            "Section 59",

        "SEC57":
            "Section 57",
    }

    provision_name = mapping.get(
        rule_id
    )

    if not provision_name:
        return None

    knowledge = (
        LegalKnowledgeBase()
    )

    provision = knowledge.get(
        provision_name
    )

    if not provision:
        return None

    return provision.to_dict()


# ---------------------------------------------------------------------
# Legal-reference enrichment
# ---------------------------------------------------------------------

def attach_legal_references(
    findings: Iterable[Dict[str, Any]],
) -> List[Dict[str, Any]]:

    enriched = []

    knowledge = (
        LegalKnowledgeBase()
    )

    for finding in findings:

        if not isinstance(
            finding,
            dict,
        ):
            continue

        item = dict(
            finding
        )

        rule_id = _clean(
            item.get(
                "rule_id",
                ""
            )
        ).upper()

        provision = get_rule_reference(
            rule_id
        )

        if provision:

            item[
                "legal_reference"
            ] = provision

        else:

            item[
                "legal_reference"
            ] = None

        enriched.append(
            item
        )

    return enriched


# ---------------------------------------------------------------------
# Legal verification status
# ---------------------------------------------------------------------

def verify_snapshot_metadata(
    snapshot: Dict[str, Any],
) -> Dict[str, Any]:

    if not isinstance(
        snapshot,
        dict,
    ):

        return {
            "valid": False,
            "reason":
                "Snapshot is not a dictionary.",
        }

    provisions = snapshot.get(
        "provisions",
        [],
    )

    sources = snapshot.get(
        "sources",
        [],
    )

    snapshot_hash = snapshot.get(
        "snapshot_hash",
        "",
    )

    if not snapshot_hash:

        return {
            "valid": False,
            "reason":
                "Snapshot hash is missing.",
        }

    payload = (
        provisions
        + sources
    )

    calculated_hash = _stable_hash(
        str(payload)
    )

    return {
        "valid":
            calculated_hash
            == snapshot_hash,

        "stored_hash":
            snapshot_hash,

        "calculated_hash":
            calculated_hash,

        "provision_count":
            len(provisions),

        "source_count":
            len(sources),

        "verification_status":
            (
                "integrity_verified"
                if calculated_hash
                == snapshot_hash
                else
                "integrity_failed"
            ),
    }


# ---------------------------------------------------------------------
# Human-readable helper
# ---------------------------------------------------------------------

def describe_provision(
    provision: str,
) -> str:

    knowledge = (
        LegalKnowledgeBase()
    )

    item = knowledge.get(
        provision
    )

    if not item:

        return (
            f"No provision reference found for "
            f"'{provision}'."
        )

    return (
        f"{item.provision}: "
        f"{item.title}. "
        f"{item.summary}"
    )


# ---------------------------------------------------------------------
# Backward-compatible helpers
# ---------------------------------------------------------------------

def get_legal_provisions() -> List[Dict[str, Any]]:

    return [
        item.to_dict()
        for item in (
            DEFAULT_PROVISIONS
            + DEFAULT_RULE_REFERENCES
        )
    ]


def get_section_3_provisions() -> List[Dict[str, Any]]:

    return [
        item.to_dict()
        for item in (
            LegalKnowledgeBase()
            .section_3()
        )
    ]


def search_legal_knowledge(
    query: str,
) -> List[Dict[str, Any]]:

    return [
        item.to_dict()
        for item in (
            LegalKnowledgeBase()
            .search(query)
        )
    ]


def get_provision(
    provision: str,
) -> Optional[Dict[str, Any]]:

    item = (
        LegalKnowledgeBase()
        .get(provision)
    )

    if item is None:
        return None

    return item.to_dict()


# ---------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------

__all__ = [
    "LEGAL_KNOWLEDGE_VERSION",
    "IPINDIA_ACT_URL",
    "IPINDIA_RULES_URL",
    "LegalProvision",
    "LegalSource",
    "LegalKnowledgeBase",
    "DEFAULT_PROVISIONS",
    "DEFAULT_RULE_REFERENCES",
    "build_legal_source",
    "create_legal_snapshot",
    "get_rule_reference",
    "attach_legal_references",
    "verify_snapshot_metadata",
    "describe_provision",
    "get_legal_provisions",
    "get_section_3_provisions",
    "search_legal_knowledge",
    "get_provision",
]
