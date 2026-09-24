"""Gate 174E: what an organisation can actually do, versioned.

An eligibility match is a comparison between what a funder requires and what
an applicant has. Gate 174 owns the first half; this module owns the second.

Three design decisions carry the weight.

**Every field is three-valued.** A profile says yes, no, or *we have not
asked*. A missing answer must never read as "no", because the difference
between "this Tribe has no matching funds" and "nobody has asked this Tribe
about matching funds" is the difference between an opportunity discarded and
an opportunity pursued. `UNANSWERED` is the default for everything.

**The profile is versioned and a match names its version.** An eligibility
result computed against last quarter's profile is a claim about last quarter.
When a Tribe obtains a UEI, previous CONDITIONALLY_ELIGIBLE results do not
silently become wrong - they become results about a superseded profile, and
the version on the row says so.

**Verification is declared, never assumed.** Each fact carries how it is
known: the organisation said so, a document was uploaded, or somebody
verified it. Gate 174 does NOT verify anything - `VERIFIED_BY_AUTHORITY` is
the value Gate 177 will write once tribal authority verification exists, and
nothing in this gate may produce it. It exists now so that Gate 177 attaches
to a shape rather than migrating one.

Federal recognition is deliberately a FACT with a verification state, not a
boolean. Asserting that an organisation is a federally recognised Tribe is a
legal claim; this layer records who claimed it and how.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.native_relevance_ontology_service import (
    ENTITY_CLASSES,
    NATIVE_ENTITY_CLASSES,
)

SCHEMA_VERSION = "nf_organization_capability_profile_v1"

PROFILE_SCHEMA_VERSION = "2026.09.1"

# --------------------------------------------------------------------
# how a fact is known
# --------------------------------------------------------------------

SELF_DECLARED = "SELF_DECLARED"
DOCUMENT_PROVIDED = "DOCUMENT_PROVIDED"
VERIFIED_BY_AUTHORITY = "VERIFIED_BY_AUTHORITY"
UNANSWERED = "UNANSWERED"

VERIFICATION_STATES: tuple[str, ...] = (
    SELF_DECLARED,
    DOCUMENT_PROVIDED,
    VERIFIED_BY_AUTHORITY,
    UNANSWERED,
)

VERIFICATION_MEANINGS: dict[str, str] = {
    SELF_DECLARED: "the organisation told us",
    DOCUMENT_PROVIDED: "the organisation supplied a document we retained",
    VERIFIED_BY_AUTHORITY: (
        "an authority verification confirmed it - Gate 177 writes this, and "
        "nothing in Gate 174 may"
    ),
    UNANSWERED: "nobody has asked; this is NOT a no",
}

#: States that represent an actual answer. `UNANSWERED` is excluded, which is
#: the whole point of having four values instead of a boolean.
ANSWERED: frozenset[str] = frozenset(
    {SELF_DECLARED, DOCUMENT_PROVIDED, VERIFIED_BY_AUTHORITY}
)

#: Gate 174 cannot produce this. Named so the invariant can refuse it rather
#: than relying on nobody calling it.
GATE_177_ONLY: frozenset[str] = frozenset({VERIFIED_BY_AUTHORITY})

# --------------------------------------------------------------------
# what a profile can hold
# --------------------------------------------------------------------

#: (field, kind). `kind` says what the value looks like, so a match engine can
#: compare without guessing.
_PROFILE_FIELDS: tuple[tuple[str, str], ...] = (
    ("entity_class", "entity_class"),
    ("legal_entity_type", "text"),
    ("jurisdiction", "text"),
    ("service_area", "list"),
    ("geographies_served", "list"),
    ("federal_recognition", "boolean"),
    ("state_recognition", "boolean"),
    ("recognition_authority", "text"),
    ("population_served", "number"),
    ("populations_served", "list"),
    ("sam_registration", "boolean"),
    ("unique_entity_id", "text"),
    ("indirect_cost_rate", "number"),
    ("matching_funds_capability", "boolean"),
    ("matching_funds_ceiling", "number"),
    ("partnership_capability", "list"),
    ("designations", "list"),
    ("certifications", "list"),
    ("program_experience", "list"),
    ("priority_sectors", "list"),
    ("excluded_sectors", "list"),
    ("annual_budget_band", "text"),
    ("staff_capacity_band", "text"),
    ("owner_or_control", "text"),
)

PROFILE_FIELDS: tuple[str, ...] = tuple(name for name, _ in _PROFILE_FIELDS)
PROFILE_FIELD_KINDS: dict[str, str] = dict(_PROFILE_FIELDS)

#: Fields whose value is a legal claim about status. They may be recorded from
#: a self-declaration, but a match that RELIES on one must say so, because a
#: Tribe told us we are federally recognised is a different evidentiary
#: position from an authority confirmed it.
LEGAL_STATUS_FIELDS: frozenset[str] = frozenset(
    {"federal_recognition", "state_recognition", "recognition_authority"}
)


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def blank_profile() -> dict[str, dict[str, Any]]:
    """Every field unanswered. The honest starting point."""
    return {
        name: {"value": None, "verification": UNANSWERED, "evidence_ref": None}
        for name in PROFILE_FIELDS
    }


def build_profile(
    *,
    organization_id: Any,
    facts: dict[str, Any] | None = None,
    profile_version: Any = None,
    recorded_at: Any = None,
) -> dict[str, Any]:
    """One organisation's capabilities, with every answer's provenance.

    `facts` maps a field to either a bare value (recorded as SELF_DECLARED) or
    a dict with `value`, `verification` and optionally `evidence_ref`.
    """
    fields = blank_profile()
    unknown_fields: list[str] = []

    for name, supplied in (facts or {}).items():
        if name not in PROFILE_FIELDS:
            unknown_fields.append(str(name))
            continue
        if isinstance(supplied, dict) and "value" in supplied:
            verification = str(supplied.get("verification") or SELF_DECLARED)
            fields[name] = {
                "value": supplied.get("value"),
                "verification": verification,
                "evidence_ref": supplied.get("evidence_ref"),
            }
        else:
            fields[name] = {
                "value": supplied,
                "verification": SELF_DECLARED,
                "evidence_ref": None,
            }

    answered = sorted(
        name for name, entry in fields.items() if str(entry["verification"]) in ANSWERED
    )
    digest = hashlib.sha256(
        json.dumps(fields, sort_keys=True, default=str).encode("utf-8")
    ).hexdigest()

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "profile_schema_version": PROFILE_SCHEMA_VERSION,
            "organization_id": str(organization_id) if organization_id else None,
            # Derived from CONTENT, so two profiles with the same answers have
            # the same version and a changed answer is a new one.
            "profile_version": str(profile_version) if profile_version else digest[:16],
            "content_digest": digest,
            "fields": fields,
            "answered_fields": answered,
            "answered_count": len(answered),
            "unanswered_count": len(PROFILE_FIELDS) - len(answered),
            "unrecognised_fields_supplied": sorted(unknown_fields),
            "recorded_at": recorded_at,
            # Gate 177 attaches here. Stated so the shape is visible now.
            "authority_verification_performed": False,
            "authority_verification_gate": "177",
        }
    )


def field_value(profile: dict[str, Any], name: str) -> Any:
    """The value, or None if nobody has answered. Never a default."""
    entry = (profile.get("fields") or {}).get(name) or {}
    if str(entry.get("verification")) not in ANSWERED:
        return None
    return entry.get("value")


def field_is_answered(profile: dict[str, Any], name: str) -> bool:
    entry = (profile.get("fields") or {}).get(name) or {}
    return str(entry.get("verification")) in ANSWERED


def entity_classes_for(profile: dict[str, Any]) -> list[str]:
    """The entity classes this organisation claims. Never inferred."""
    value = field_value(profile, "entity_class")
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    return sorted(str(v) for v in value if str(v) in ENTITY_CLASSES)


def profile_invariant_failures(profile: dict[str, Any]) -> list[str]:
    """Refuse a profile that claims more than it was told."""
    failures: list[str] = []

    if not profile.get("organization_id"):
        failures.append("profile_not_bound_to_an_organization")
    if not profile.get("profile_version"):
        failures.append("profile_has_no_version")
    if not profile.get("profile_schema_version"):
        failures.append("profile_does_not_record_its_schema_version")

    fields = profile.get("fields") or {}
    for name in PROFILE_FIELDS:
        if name not in fields:
            failures.append(f"profile_missing_field:{name}")

    for name, entry in fields.items():
        if name not in PROFILE_FIELDS:
            failures.append(f"profile_field_outside_the_schema:{name}")
            continue
        verification = str((entry or {}).get("verification") or "")
        if verification not in VERIFICATION_STATES:
            failures.append(
                f"verification_outside_the_vocabulary:{name}:{verification}"
            )
        # An answer with no value, or a value with no answer, is incoherent.
        if verification in ANSWERED and (entry or {}).get("value") is None:
            failures.append(f"field_claims_an_answer_with_no_value:{name}")
        if verification == UNANSWERED and (entry or {}).get("value") is not None:
            failures.append(f"field_holds_a_value_while_unanswered:{name}")
        # Gate 174 may not verify anything.
        if verification in GATE_177_ONLY:
            failures.append(f"gate174_produced_an_authority_verification:{name}")
        if verification == DOCUMENT_PROVIDED and not (entry or {}).get("evidence_ref"):
            failures.append(f"document_backed_field_names_no_document:{name}")

    if profile.get("authority_verification_performed"):
        failures.append("gate174_profile_claims_authority_verification")

    entity = field_value(profile, "entity_class")
    if entity is not None:
        values = [entity] if isinstance(entity, str) else list(entity)
        for value in values:
            if str(value) not in ENTITY_CLASSES:
                failures.append(f"entity_class_outside_the_vocabulary:{value}")

    return sorted(set(failures))


def describe_profile_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "profile_schema_version": PROFILE_SCHEMA_VERSION,
            "profile_fields": list(PROFILE_FIELDS),
            "field_kinds": dict(PROFILE_FIELD_KINDS),
            "verification_states": list(VERIFICATION_STATES),
            "every_verification_has_a_meaning": set(VERIFICATION_MEANINGS)
            == set(VERIFICATION_STATES),
            "unanswered_is_not_no": UNANSWERED not in ANSWERED,
            "every_field_defaults_to_unanswered": all(
                entry["verification"] == UNANSWERED
                for entry in blank_profile().values()
            ),
            "profile_is_versioned": True,
            "version_is_derived_from_content": True,
            "gate174_cannot_verify_authority": sorted(GATE_177_ONLY),
            "legal_status_fields": sorted(LEGAL_STATUS_FIELDS),
            "native_entity_classes": sorted(NATIVE_ENTITY_CLASSES),
        }
    )
