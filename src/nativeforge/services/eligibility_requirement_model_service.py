"""Gate 174B/C/D/G: eligibility as a set of requirements, not a boolean.

The question an operator actually has is not "are we eligible". It is:

```text
who can apply, under what conditions, what disqualifies us, and what is
still unknown?
```

A boolean cannot carry any of that. `True` hides a matching-funds condition
nobody can meet; `False` hides that the only reason is a missing UEI that
takes a week to obtain. So eligibility here is a set of typed REQUIREMENTS,
each with its own status, and a result that is six-valued.

**Negative requirements are first class.** This is the half that layers
usually miss. A model that stores only who MAY apply represents "tribal
governments are not eligible" as the absence of a tribal class from a list -
which is byte-identical to "nobody wrote the list down". Those are different
facts and a disqualifier is therefore its own row, with its own evidence,
never an inference from silence.

**Entity classes do not lend each other eligibility.** A notice naming
"Indian tribes" does not name a tribal college; one naming "tribal
organizations" does not name a tribal enterprise. The transfer rule is
explicit and deny-by-default, because the failure mode - telling a Tribe they
may apply when the source named a different Native entity class - costs them a
cycle and their credibility with the funder.

The original source text is preserved alongside every normalization. A
normalized requirement is our reading; the text is what the funder wrote, and
only one of those is authoritative when somebody disputes it.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.native_relevance_ontology_service import (
    ENTITY_CLASSES,
    NATIVE_ENTITY_CLASSES,
)

SCHEMA_VERSION = "nf_eligibility_requirement_model_v1"

#: Bumped when a requirement kind or result value changes meaning.
ELIGIBILITY_MODEL_VERSION = "2026.09.1"

# --------------------------------------------------------------------
# 174B: requirement kinds
# --------------------------------------------------------------------

APPLICANT_TYPE = "APPLICANT_TYPE"
LEGAL_ENTITY_TYPE = "LEGAL_ENTITY_TYPE"
GEOGRAPHIC = "GEOGRAPHIC"
BENEFICIARY = "BENEFICIARY"
POPULATION = "POPULATION"
PARTNERSHIP = "PARTNERSHIP"
MATCHING_FUNDS = "MATCHING_FUNDS"
REGISTRATION = "REGISTRATION"
EXPERIENCE = "EXPERIENCE"
OWNERSHIP_OR_CONTROL = "OWNERSHIP_OR_CONTROL"
GOVERNMENT_STATUS = "GOVERNMENT_STATUS"
RECOGNITION_OR_DESIGNATION = "RECOGNITION_OR_DESIGNATION"
SPECIAL_DESIGNATION = "SPECIAL_DESIGNATION"
DEADLINE = "DEADLINE"
OTHER_CONDITION = "OTHER_CONDITION"

REQUIREMENT_KINDS: tuple[str, ...] = (
    APPLICANT_TYPE,
    LEGAL_ENTITY_TYPE,
    GEOGRAPHIC,
    BENEFICIARY,
    POPULATION,
    PARTNERSHIP,
    MATCHING_FUNDS,
    REGISTRATION,
    EXPERIENCE,
    OWNERSHIP_OR_CONTROL,
    GOVERNMENT_STATUS,
    RECOGNITION_OR_DESIGNATION,
    SPECIAL_DESIGNATION,
    DEADLINE,
    OTHER_CONDITION,
)

REQUIREMENT_KIND_MEANINGS: dict[str, str] = {
    APPLICANT_TYPE: "the category of applicant the funder names",
    LEGAL_ENTITY_TYPE: "the legal form the applicant must hold",
    GEOGRAPHIC: "where the applicant, the work or the beneficiaries must be",
    BENEFICIARY: "who the funded work must serve",
    POPULATION: "a population threshold or characteristic",
    PARTNERSHIP: "a partner the applicant must bring",
    MATCHING_FUNDS: "a cost share the applicant must supply",
    REGISTRATION: "a registration such as SAM or a UEI",
    EXPERIENCE: "prior program or administrative experience",
    OWNERSHIP_OR_CONTROL: "who must own or control the applicant",
    GOVERNMENT_STATUS: "a governmental status the applicant must hold",
    RECOGNITION_OR_DESIGNATION: "federal or state recognition, or a designation",
    SPECIAL_DESIGNATION: "a program-specific designation such as a TDHE or TCU",
    DEADLINE: "a date by which something must happen",
    OTHER_CONDITION: "a condition this vocabulary does not name, quoted in full",
}

#: Requirement kinds whose failure is usually FATAL rather than fixable. A
#: matching-funds gap can often be closed; not being a Tribe cannot.
STRUCTURAL_KINDS: frozenset[str] = frozenset(
    {
        APPLICANT_TYPE,
        LEGAL_ENTITY_TYPE,
        GOVERNMENT_STATUS,
        RECOGNITION_OR_DESIGNATION,
        OWNERSHIP_OR_CONTROL,
    }
)

#: Kinds an applicant can plausibly satisfy with effort before the deadline.
#: Used to decide CONDITIONALLY_ELIGIBLE rather than INELIGIBLE.
ADDRESSABLE_KINDS: frozenset[str] = frozenset(
    {MATCHING_FUNDS, REGISTRATION, PARTNERSHIP, EXPERIENCE, SPECIAL_DESIGNATION}
)

# --------------------------------------------------------------------
# requirement polarity - the 174G half
# --------------------------------------------------------------------

#: The applicant must satisfy this to be eligible.
INCLUSION = "INCLUSION"
#: Satisfying this makes the applicant INELIGIBLE. A first-class row.
EXCLUSION = "EXCLUSION"

POLARITIES: tuple[str, ...] = (INCLUSION, EXCLUSION)

# --------------------------------------------------------------------
# 174C: the result
# --------------------------------------------------------------------

ELIGIBLE = "ELIGIBLE"
LIKELY_ELIGIBLE = "LIKELY_ELIGIBLE"
CONDITIONALLY_ELIGIBLE = "CONDITIONALLY_ELIGIBLE"
INELIGIBLE = "INELIGIBLE"
UNKNOWN = "UNKNOWN"
REVIEW_REQUIRED = "REVIEW_REQUIRED"

ELIGIBILITY_RESULTS: tuple[str, ...] = (
    ELIGIBLE,
    LIKELY_ELIGIBLE,
    CONDITIONALLY_ELIGIBLE,
    INELIGIBLE,
    UNKNOWN,
    REVIEW_REQUIRED,
)

RESULT_MEANINGS: dict[str, str] = {
    ELIGIBLE: "every requirement is satisfied by evidence and none excludes",
    LIKELY_ELIGIBLE: (
        "every requirement we can check is satisfied, and the unchecked ones "
        "are not structural"
    ),
    CONDITIONALLY_ELIGIBLE: (
        "eligible IF something addressable is obtained - a match, a "
        "registration, a partner - and the condition is named"
    ),
    INELIGIBLE: "an exclusion applies, or a structural requirement fails",
    UNKNOWN: (
        "not enough is known to answer; this is not a soft no and never "
        "counts as eligible"
    ),
    REVIEW_REQUIRED: ("the evidence conflicts, or a human must read the source text"),
}

#: Results that mean "this organisation may pursue this". UNKNOWN is
#: deliberately absent: an unanswered question is not a yes.
PURSUABLE: frozenset[str] = frozenset(
    {ELIGIBLE, LIKELY_ELIGIBLE, CONDITIONALLY_ELIGIBLE}
)

# --------------------------------------------------------------------
# requirement status
# --------------------------------------------------------------------

SATISFIED = "SATISFIED"
UNSATISFIED = "UNSATISFIED"
UNKNOWN_STATUS = "UNKNOWN_STATUS"
NOT_APPLICABLE = "NOT_APPLICABLE"

REQUIREMENT_STATUSES: tuple[str, ...] = (
    SATISFIED,
    UNSATISFIED,
    UNKNOWN_STATUS,
    NOT_APPLICABLE,
)

# --------------------------------------------------------------------
# 174D: entity classes, and what they do NOT imply
# --------------------------------------------------------------------

#: Deny-by-default. A source naming one class names ONLY that class, unless a
#: transfer is listed here with a reason. The map is deliberately near-empty:
#: every entry is a claim that one Native entity class can stand in for
#: another, and that claim belongs to the source text, not to this table.
ELIGIBILITY_TRANSFERS: dict[str, tuple[str, ...]] = {
    # A federally recognised Tribe acting as a government IS a tribal
    # government; this is the one identity relation, not a transfer.
    "tribal_government": ("tribal_government",),
}

#: Phrases a source uses that genuinely name a GROUP of classes. Reading these
#: is the source's own scoping, not ours.
CLASS_GROUPS: dict[str, tuple[str, ...]] = {
    "indian_tribes": ("tribal_government",),
    "tribal_organizations": (
        "tribal_government",
        "tribal_consortium",
        "tribal_authority",
        "native_nonprofit",
    ),
    "tribal_entities": (
        "tribal_government",
        "tribal_consortium",
        "tribal_enterprise",
        "tribal_authority",
        "tribal_housing_entity",
    ),
    "units_of_local_government": ("local_government",),
}

REQUIREMENT_FIELDS: tuple[str, ...] = (
    "requirement_id",
    "canonical_id",
    "requirement_kind",
    "polarity",
    "normalized_value",
    "original_text",
    "applies_to_entity_classes",
    "evidence_ids",
    "document_ref",
    "section_ref",
    "page_ref",
    "source_id",
    "raw_payload_sha256",
    "confidence_class",
    "model_version",
)


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def build_requirement_id(
    *,
    canonical_id: Any,
    requirement_kind: Any,
    polarity: Any,
    normalized_value: Any,
    section_ref: Any = None,
) -> str:
    parts = [
        str(canonical_id or ""),
        str(requirement_kind or ""),
        str(polarity or ""),
        json.dumps(normalized_value, sort_keys=True, default=str),
        str(section_ref or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_requirement(
    *,
    canonical_id: Any,
    requirement_kind: str,
    normalized_value: Any,
    original_text: Any,
    polarity: str = INCLUSION,
    applies_to_entity_classes: list[str] | None = None,
    evidence_ids: list[str] | None = None,
    source_id: Any = None,
    raw_payload_sha256: Any = None,
    document_ref: Any = None,
    section_ref: Any = None,
    page_ref: Any = None,
    confidence_class: Any = None,
) -> dict[str, Any]:
    """One requirement, with the funder's own words kept beside our reading."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "requirement_id": build_requirement_id(
                canonical_id=canonical_id,
                requirement_kind=requirement_kind,
                polarity=polarity,
                normalized_value=normalized_value,
                section_ref=section_ref,
            ),
            "canonical_id": str(canonical_id) if canonical_id else None,
            "requirement_kind": str(requirement_kind),
            "polarity": str(polarity),
            "normalized_value": normalized_value,
            # Never dropped. Our normalization is a reading; this is the fact.
            "original_text": str(original_text) if original_text is not None else None,
            "applies_to_entity_classes": sorted(applies_to_entity_classes or []),
            "evidence_ids": sorted(evidence_ids or []),
            "document_ref": str(document_ref) if document_ref else None,
            "section_ref": str(section_ref) if section_ref else None,
            "page_ref": int(page_ref) if page_ref is not None else None,
            "source_id": str(source_id) if source_id else None,
            "raw_payload_sha256": (
                str(raw_payload_sha256) if raw_payload_sha256 else None
            ),
            "confidence_class": str(confidence_class) if confidence_class else None,
            "model_version": ELIGIBILITY_MODEL_VERSION,
            "is_structural": str(requirement_kind) in STRUCTURAL_KINDS,
            "is_addressable": str(requirement_kind) in ADDRESSABLE_KINDS,
        }
    )


def expand_class_group(phrase: Any) -> list[str]:
    """What a source's own grouping phrase names. Never widened by us.

    Spaces and hyphens normalise to underscores, because a source writes
    "tribal organizations" and the table is keyed "tribal_organizations".
    Matching on case alone returned an EMPTY list for every real phrase, which
    reads as "this names no classes" rather than as a lookup miss.
    """
    key = str(phrase or "").strip().lower().replace("-", "_").replace(" ", "_")
    return sorted(CLASS_GROUPS.get(key, ()))


def eligibility_transfers_between(*, named_class: str, applicant_class: str) -> bool:
    """Does naming one entity class make another one eligible?

    Deny by default. The only true case is a class naming itself. Everything
    else has to come from the source's own grouping language, read through
    `expand_class_group`, because "tribal organizations" including a tribal
    enterprise is the FUNDER's scoping decision and not ours to infer.
    """
    named = str(named_class)
    applicant = str(applicant_class)
    if named == applicant:
        return True
    return applicant in ELIGIBILITY_TRANSFERS.get(named, ())


def requirement_invariant_failures(requirement: dict[str, Any]) -> list[str]:
    """Refuse a requirement that cannot be defended."""
    failures: list[str] = []

    for field in REQUIREMENT_FIELDS:
        if field not in requirement:
            failures.append(f"requirement_missing_field:{field}")

    kind = str(requirement.get("requirement_kind") or "")
    if kind not in REQUIREMENT_KINDS:
        failures.append(f"requirement_kind_outside_the_vocabulary:{kind or 'missing'}")

    polarity = str(requirement.get("polarity") or "")
    if polarity not in POLARITIES:
        failures.append(f"polarity_outside_the_vocabulary:{polarity or 'missing'}")

    if not requirement.get("canonical_id"):
        failures.append("requirement_not_bound_to_a_canonical_opportunity")

    # The funder's words are the authority when a reading is disputed.
    if requirement.get("original_text") in (None, ""):
        failures.append("requirement_discards_the_original_text")

    if requirement.get("normalized_value") in (None, "", [], {}):
        failures.append("requirement_has_no_normalized_value")

    # A requirement is a claim about the source and needs to point at it.
    if not requirement.get("evidence_ids") and not requirement.get(
        "raw_payload_sha256"
    ):
        failures.append("requirement_has_no_evidence_and_no_payload")

    for entity_class in requirement.get("applies_to_entity_classes") or []:
        if str(entity_class) not in ENTITY_CLASSES:
            failures.append(f"entity_class_outside_the_vocabulary:{entity_class}")

    page = requirement.get("page_ref")
    if page is not None and int(page) < 1:
        failures.append(f"page_reference_is_not_a_page:{page}")

    return sorted(set(failures))


def describe_requirement_model() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "model_version": ELIGIBILITY_MODEL_VERSION,
            "requirement_kinds": list(REQUIREMENT_KINDS),
            "polarities": list(POLARITIES),
            "eligibility_results": list(ELIGIBILITY_RESULTS),
            "requirement_statuses": list(REQUIREMENT_STATUSES),
            "every_kind_has_a_meaning": set(REQUIREMENT_KIND_MEANINGS)
            == set(REQUIREMENT_KINDS),
            "every_result_has_a_meaning": set(RESULT_MEANINGS)
            == set(ELIGIBILITY_RESULTS),
            "every_result_meaning_is_distinct": len(set(RESULT_MEANINGS.values()))
            == len(ELIGIBILITY_RESULTS),
            "result_is_not_a_boolean": len(ELIGIBILITY_RESULTS) > 2,
            "negative_requirements_are_first_class": EXCLUSION in POLARITIES,
            "unknown_is_not_eligible": UNKNOWN not in PURSUABLE,
            "review_required_is_not_eligible": REVIEW_REQUIRED not in PURSUABLE,
            "original_text_is_never_discarded": True,
            "entity_classes_do_not_transfer_by_default": all(
                targets == (named,) for named, targets in ELIGIBILITY_TRANSFERS.items()
            ),
            "native_entity_classes": sorted(NATIVE_ENTITY_CLASSES),
            "class_groups_come_from_source_language": sorted(CLASS_GROUPS),
            "structural_kinds": sorted(STRUCTURAL_KINDS),
            "addressable_kinds": sorted(ADDRESSABLE_KINDS),
        }
    )
