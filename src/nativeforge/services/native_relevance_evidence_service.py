"""Gate 173C: the evidence a Native relevance claim is allowed to rest on.

The rule this module exists to make unbreakable:

```text
no classification without evidence, and no evidence without a payload it
came from.
```

An explanation that is not tied to a byte-addressable observation is a
plausible sentence, and a plausible sentence is exactly what an intelligence
product must not ship. Every item here therefore carries the canonical
opportunity it is about, the source that said it, the sha256 of the payload
that contained it, and - where the source structure supports it - the field,
section or page it was read from.

Twelve evidence types, because the product principle requires that relevance
can arise from twelve different places. If a classification could only ever
cite `PROGRAM_PURPOSE`, the system would be a keyword matcher wearing a
taxonomy.

Confidence and ambiguity are separate fields on purpose. "We are sure the text
says X" and "what X means here is contested" are different problems, and a
single confidence number cannot express the second one.

This module does NOT store anything. Persistence belongs to the relevance
repository; this is the contract every row has to satisfy before it gets
there, and the invariant checker that refuses the ones that do not.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_native_relevance_evidence_v1"

# --------------------------------------------------------------------
# evidence types
# --------------------------------------------------------------------

APPLICANT_ELIGIBILITY = "APPLICANT_ELIGIBILITY"
BENEFICIARY_POPULATION = "BENEFICIARY_POPULATION"
GEOGRAPHIC_RELEVANCE = "GEOGRAPHIC_RELEVANCE"
PROGRAM_PURPOSE = "PROGRAM_PURPOSE"
AGENCY_CONTEXT = "AGENCY_CONTEXT"
PROGRAM_HISTORY = "PROGRAM_HISTORY"
PRIOR_NATIVE_AWARDS = "PRIOR_NATIVE_AWARDS"
STATUTORY_LANGUAGE = "STATUTORY_LANGUAGE"
SOURCE_CONTEXT = "SOURCE_CONTEXT"
SECTOR_ALIGNMENT = "SECTOR_ALIGNMENT"
DOCUMENT_REFERENCE = "DOCUMENT_REFERENCE"
OTHER_EVIDENCE = "OTHER_EVIDENCE"

EVIDENCE_TYPES: tuple[str, ...] = (
    APPLICANT_ELIGIBILITY,
    BENEFICIARY_POPULATION,
    GEOGRAPHIC_RELEVANCE,
    PROGRAM_PURPOSE,
    AGENCY_CONTEXT,
    PROGRAM_HISTORY,
    PRIOR_NATIVE_AWARDS,
    STATUTORY_LANGUAGE,
    SOURCE_CONTEXT,
    SECTOR_ALIGNMENT,
    DOCUMENT_REFERENCE,
    OTHER_EVIDENCE,
)

EVIDENCE_TYPE_MEANINGS: dict[str, str] = {
    APPLICANT_ELIGIBILITY: "who the source says may apply",
    BENEFICIARY_POPULATION: "who the money is meant to reach",
    GEOGRAPHIC_RELEVANCE: (
        "where it applies - reservation, trust land, service area, state"
    ),
    PROGRAM_PURPOSE: "what the program is for, in the source's own words",
    AGENCY_CONTEXT: "the funder's mission or bureau, where that carries meaning",
    PROGRAM_HISTORY: "what this program has funded in prior cycles",
    PRIOR_NATIVE_AWARDS: "an observed award to a Native entity under this program",
    STATUTORY_LANGUAGE: "the authority the program is issued under",
    SOURCE_CONTEXT: "the publisher itself - a Native-serving source is a signal",
    SECTOR_ALIGNMENT: "the program area, where Native need in it is established",
    DOCUMENT_REFERENCE: (
        "a fact read out of an attached document rather than the record"
    ),
    OTHER_EVIDENCE: "a signal this vocabulary does not name, described in full",
}

#: Evidence types that speak to WHO MAY APPLY. A classification in the
#: applicant-relevant band has to cite at least one of these; beneficiary or
#: sector evidence alone cannot carry it, which is the separation the product
#: principle turns on.
APPLICANT_BEARING: frozenset[str] = frozenset(
    {APPLICANT_ELIGIBILITY, STATUTORY_LANGUAGE, DOCUMENT_REFERENCE}
)

#: Evidence that is suggestive and never sufficient on its own. A pipeline
#: built only on these is the keyword matcher the ontology forbids.
SUGGESTIVE_ONLY: frozenset[str] = frozenset(
    {AGENCY_CONTEXT, SECTOR_ALIGNMENT, SOURCE_CONTEXT, PROGRAM_HISTORY}
)

# --------------------------------------------------------------------
# confidence and ambiguity
# --------------------------------------------------------------------

#: How sure we are the source SAYS this.
OBSERVED = "OBSERVED"
DERIVED = "DERIVED"
INFERRED = "INFERRED"
ASSERTED_BY_HUMAN = "ASSERTED_BY_HUMAN"
UNKNOWN_CONFIDENCE = "UNKNOWN_CONFIDENCE"

CONFIDENCE_CLASSES: tuple[str, ...] = (
    OBSERVED,
    DERIVED,
    INFERRED,
    ASSERTED_BY_HUMAN,
    UNKNOWN_CONFIDENCE,
)

#: Confidence classes strong enough to carry a definite classification.
#: INFERRED is excluded: an inference is a hypothesis, and a hypothesis that
#: decides an answer without a human is the failure mode this gate is built
#: against.
DEFINITE_ENOUGH: frozenset[str] = frozenset({OBSERVED, DERIVED, ASSERTED_BY_HUMAN})

#: What is unclear about the evidence, separately from how sure we are of it.
NO_AMBIGUITY = "NO_AMBIGUITY"
ENTITY_CLASS_AMBIGUOUS = "ENTITY_CLASS_AMBIGUOUS"
SCOPE_AMBIGUOUS = "SCOPE_AMBIGUOUS"
TEMPORAL_AMBIGUOUS = "TEMPORAL_AMBIGUOUS"
CONTEXT_AMBIGUOUS = "CONTEXT_AMBIGUOUS"
CONFLICTING_SOURCES = "CONFLICTING_SOURCES"

AMBIGUITY_CLASSES: tuple[str, ...] = (
    NO_AMBIGUITY,
    ENTITY_CLASS_AMBIGUOUS,
    SCOPE_AMBIGUOUS,
    TEMPORAL_AMBIGUOUS,
    CONTEXT_AMBIGUOUS,
    CONFLICTING_SOURCES,
)

AMBIGUITY_MEANINGS: dict[str, str] = {
    NO_AMBIGUITY: "the evidence means what it says",
    ENTITY_CLASS_AMBIGUOUS: (
        "the source names a category that may or may not include the entity "
        "class in question - 'units of local government' and a Tribe"
    ),
    SCOPE_AMBIGUOUS: "it is unclear whether this applies to the whole program",
    TEMPORAL_AMBIGUOUS: (
        "the evidence may describe a prior cycle rather than this one - the "
        "background-paragraph problem"
    ),
    CONTEXT_AMBIGUOUS: (
        "the term appears in narrative, history or a place name rather than in "
        "an operative clause"
    ),
    CONFLICTING_SOURCES: "another source says something incompatible",
}

#: Ambiguity classes that mean a definite classification must not be asserted
#: from this item alone.
BLOCKS_DEFINITE: frozenset[str] = frozenset(
    {ENTITY_CLASS_AMBIGUOUS, CONTEXT_AMBIGUOUS, CONFLICTING_SOURCES}
)

#: Every field a stored evidence row carries.
EVIDENCE_FIELDS: tuple[str, ...] = (
    "evidence_id",
    "canonical_id",
    "evidence_type",
    "source_id",
    "raw_payload_sha256",
    "observation_id",
    "version_id",
    "field_name",
    "section_ref",
    "page_ref",
    "document_ref",
    "evidence_value",
    "confidence_class",
    "ambiguity_class",
    "supports_classes",
    "observed_at",
    "ontology_version",
)


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def build_evidence_id(
    *,
    canonical_id: Any,
    evidence_type: Any,
    source_id: Any,
    raw_payload_sha256: Any,
    field_name: Any = None,
    section_ref: Any = None,
) -> str:
    """Derived from what the evidence IS, so the same reading of the same bytes
    cannot produce two rows.

    The payload hash is part of the identity on purpose: if the bytes change,
    it is a different observation and deserves a different row, which is what
    lets Gate 170 see relevance move when a source amends.
    """
    parts = [
        str(canonical_id or ""),
        str(evidence_type or ""),
        str(source_id or ""),
        str(raw_payload_sha256 or ""),
        str(field_name or ""),
        str(section_ref or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_evidence(
    *,
    canonical_id: Any,
    evidence_type: str,
    source_id: Any,
    raw_payload_sha256: Any,
    evidence_value: Any,
    confidence_class: str = UNKNOWN_CONFIDENCE,
    ambiguity_class: str = NO_AMBIGUITY,
    supports_classes: list[str] | None = None,
    observation_id: Any = None,
    version_id: Any = None,
    field_name: Any = None,
    section_ref: Any = None,
    page_ref: Any = None,
    document_ref: Any = None,
    observed_at: Any = None,
    ontology_version: Any = None,
) -> dict[str, Any]:
    """One evidence item, shaped so it cannot be stored without its origin."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "evidence_id": build_evidence_id(
                canonical_id=canonical_id,
                evidence_type=evidence_type,
                source_id=source_id,
                raw_payload_sha256=raw_payload_sha256,
                field_name=field_name,
                section_ref=section_ref,
            ),
            "canonical_id": str(canonical_id) if canonical_id else None,
            "evidence_type": str(evidence_type),
            "source_id": str(source_id) if source_id else None,
            "raw_payload_sha256": (
                str(raw_payload_sha256) if raw_payload_sha256 else None
            ),
            "observation_id": str(observation_id) if observation_id else None,
            "version_id": str(version_id) if version_id else None,
            "field_name": str(field_name) if field_name else None,
            "section_ref": str(section_ref) if section_ref else None,
            "page_ref": int(page_ref) if page_ref is not None else None,
            "document_ref": str(document_ref) if document_ref else None,
            "evidence_value": evidence_value,
            "confidence_class": str(confidence_class),
            "ambiguity_class": str(ambiguity_class),
            "supports_classes": sorted(supports_classes or []),
            "observed_at": observed_at,
            "ontology_version": str(ontology_version) if ontology_version else None,
        }
    )


def evidence_invariant_failures(evidence: dict[str, Any]) -> list[str]:
    """Refuse an evidence row that cannot be traced back to bytes."""
    failures: list[str] = []

    for field in EVIDENCE_FIELDS:
        if field not in evidence:
            failures.append(f"evidence_missing_field:{field}")

    kind = str(evidence.get("evidence_type") or "")
    if kind not in EVIDENCE_TYPES:
        failures.append(f"evidence_type_outside_the_vocabulary:{kind or 'missing'}")

    confidence = str(evidence.get("confidence_class") or "")
    if confidence not in CONFIDENCE_CLASSES:
        failures.append(f"confidence_outside_the_vocabulary:{confidence or 'missing'}")

    ambiguity = str(evidence.get("ambiguity_class") or "")
    if ambiguity not in AMBIGUITY_CLASSES:
        failures.append(f"ambiguity_outside_the_vocabulary:{ambiguity or 'missing'}")

    if not evidence.get("canonical_id"):
        failures.append("evidence_not_bound_to_a_canonical_opportunity")

    # The load-bearing one. A human assertion is allowed to have no payload -
    # a person is the origin - but nothing else is.
    if not evidence.get("raw_payload_sha256") and confidence != ASSERTED_BY_HUMAN:
        failures.append("evidence_not_bound_to_a_payload")

    if not evidence.get("source_id") and confidence != ASSERTED_BY_HUMAN:
        failures.append("evidence_has_no_source")

    if evidence.get("evidence_value") in (None, "", [], {}):
        failures.append("evidence_has_no_value")

    page = evidence.get("page_ref")
    if page is not None and int(page) < 1:
        failures.append(f"page_reference_is_not_a_page:{page}")

    return sorted(set(failures))


def is_definite_enough(evidence: dict[str, Any]) -> bool:
    """Can this item carry a definite classification by itself?"""
    return (
        str(evidence.get("confidence_class")) in DEFINITE_ENOUGH
        and str(evidence.get("ambiguity_class")) not in BLOCKS_DEFINITE
    )


def summarise_evidence(items: list[dict[str, Any]]) -> dict[str, Any]:
    """What a classifier is allowed to conclude from a pile of evidence."""
    types = [str(item.get("evidence_type")) for item in items]
    definite = [item for item in items if is_definite_enough(item)]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "evidence_count": len(items),
            "types_present": sorted(set(types)),
            "definite_count": len(definite),
            "has_applicant_bearing_evidence": any(
                kind in APPLICANT_BEARING for kind in types
            ),
            "has_definite_applicant_bearing_evidence": any(
                str(item.get("evidence_type")) in APPLICANT_BEARING for item in definite
            ),
            "only_suggestive": bool(types)
            and all(kind in SUGGESTIVE_ONLY for kind in types),
            "ambiguities": sorted(
                {
                    str(item.get("ambiguity_class"))
                    for item in items
                    if str(item.get("ambiguity_class")) != NO_AMBIGUITY
                }
            ),
            "sources": sorted(
                {str(item.get("source_id")) for item in items if item.get("source_id")}
            ),
            "payloads": sorted(
                {
                    str(item.get("raw_payload_sha256"))
                    for item in items
                    if item.get("raw_payload_sha256")
                }
            ),
        }
    )


def describe_evidence_model() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "evidence_types": list(EVIDENCE_TYPES),
            "confidence_classes": list(CONFIDENCE_CLASSES),
            "ambiguity_classes": list(AMBIGUITY_CLASSES),
            "evidence_fields": list(EVIDENCE_FIELDS),
            "every_type_has_a_meaning": set(EVIDENCE_TYPE_MEANINGS)
            == set(EVIDENCE_TYPES),
            "every_ambiguity_has_a_meaning": set(AMBIGUITY_MEANINGS)
            == set(AMBIGUITY_CLASSES),
            "evidence_must_name_its_payload": True,
            "inference_is_not_definite": INFERRED not in DEFINITE_ENOUGH,
            "confidence_and_ambiguity_are_separate": True,
            "suggestive_types_are_never_sufficient": sorted(SUGGESTIVE_ONLY),
            "applicant_bearing_types": sorted(APPLICANT_BEARING),
        }
    )
