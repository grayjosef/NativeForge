"""South Carolina recognition sets and the geography gate (Gate 92I).

## Three sets, never one

The research pass found three distinct South Carolina lists that are routinely
confused with each other, and conflating any two of them produces a wrong
eligibility answer:

1. **SC state-recognized entities** - the Advance SC registry (SC Commission
   for Community Advancement and Engagement). Three categories: Tribes, Indian
   Groups, and Special Interest Organizations.
2. **Federally recognized Tribes resident in SC** - exactly **one**: the
   Catawba Nation, confirmed against the BIA's annual Federal Register notice
   of 575 entities.
3. **Federally recognized Tribes with SC consultation interest** - the SCDAH
   Section 106 list of **16** Tribes with historic affiliation to South
   Carolina, of which 15 are non-resident. This is a consulting-party list, not
   a recognition list.

Set 3 is where the damage happens: it is 16 entries long and reads like a
recognition list. It is not one.

## Why this is not a cosmetic distinction

Federal recognition is a hard gate on GAP, CWA §106/§319, TTP, TTPSF, SS4A,
DOE TELGP, CTAS and more. A state-recognized-only SC entity cannot win those,
and surfacing them is worse than surfacing nothing - it spends a small grant
office's scarcest resource on an application it cannot win.

Two documented exceptions are encoded rather than generalized:

* **FTA** states plainly that tribal governments which are not federally
  recognized *"remain eligible to apply to the state as a subrecipient for
  funding under the state's apportionment."* That is the clearest
  state-recognition pathway found anywhere in the set.
* **ED Title VI** counts members of state-recognized tribes, terminated tribes,
  and first- and second-degree descendants for student eligibility - but
  whether such a Tribe may itself be the *applicant* is unresolved, so that
  stays ``UNKNOWN`` instead of being rounded up.

## The geography gate runs before ranking, not after

Four clean out-of-scope test cases for an SC customer: Potlatch Fund
(ID/MT/OR/WA), Bush Foundation (MN/ND/SD), Cherokee Preservation Foundation
(EBCI/western NC), Bureau of Reclamation (17 Western States). None may ever
reach an SC customer, and a ranker that scores them first has already failed.

Enumerated-set eligibility is supported alongside class-based: Reclamation's
current tribal drought opportunity is restricted to a hard-coded list of 30
named Colorado River Basin Tribes, which no class vocabulary can express.

Deny by default throughout: a source with unknown geography is **withheld**,
because a filter that passes what it does not understand is not a filter.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.native_eligibility_code_classification_service import (
    ELIGIBILITY_CLASSES,
)

SCHEMA_VERSION = "nf_sc_native_recognition_and_geography_v1"

RECOGNITION_SETS = frozenset(
    {
        "sc_state_recognized",
        "federally_recognized_resident_in_sc",
        "federally_recognized_with_sc_consultation_interest",
    }
)

# Advance SC publishes three categories under state recognition. They are not
# interchangeable, so the category travels with the entity.
SC_STATE_RECOGNITION_CATEGORIES = frozenset(
    {
        "native_american_indian_tribe",
        "indian_group",
        "special_interest_organization",
    }
)

# Counts as published by the research pass, held as constants so a later drift
# in the data is visible rather than silent.
SC_STATE_RECOGNIZED_ENTITY_COUNT = 16
SC_STATE_RECOGNIZED_TRIBE_COUNT = 10
FEDERALLY_RECOGNIZED_RESIDENT_IN_SC_COUNT = 1
SC_SECTION_106_CONSULTING_TRIBE_COUNT = 16
BIA_FEDERALLY_RECOGNIZED_ENTITY_COUNT = 575

CATAWBA_NATION_NAME = "Catawba Nation"

# The registry publishes no date stamp anywhere, so change detection must be
# content hashing rather than date checking.
SC_REGISTRY_HAS_DATE_STAMP = False

GEOGRAPHY_VERDICTS = frozenset({"in_scope", "out_of_scope", "withheld_unknown"})

# Documented geographic limits. An SC customer fails every one of them.
GEOGRAPHY_TEST_CASES: dict[str, tuple[str, ...]] = {
    "Potlatch Fund": ("ID", "MT", "OR", "WA"),
    "Bush Foundation": ("MN", "ND", "SD"),
    "Cherokee Preservation Foundation": ("NC",),
    "Bureau of Reclamation Native American Affairs": (
        "AZ", "CA", "CO", "ID", "KS", "MT", "NE", "NV", "NM", "ND",
        "OK", "OR", "SD", "TX", "UT", "WA", "WY",
    ),
}

RECLAMATION_WESTERN_STATE_COUNT = 17

DISTRIBUTION_MODES = frozenset(
    {"direct", "state_formula", "state_competitive", "either", "unknown"}
)

# Programs where federal recognition is a documented hard gate.
FEDERAL_RECOGNITION_GATED_PROGRAMS = frozenset(
    {"GAP", "CWA_106", "CWA_319", "TTP", "TTPSF", "SS4A", "DOE_TELGP", "CTAS"}
)

# The one documented pathway for a non-federally-recognized tribal government.
STATE_SUBRECIPIENT_PATHWAY_PROGRAMS = frozenset({"FTA_5311", "FTA_5310"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_recognition_record(
    *,
    entity_name: Any,
    recognition_set: Any,
    sc_category: Any = None,
    federally_recognized: Any = None,
    resident_state: Any = None,
) -> dict[str, Any]:
    """One entity, in exactly one recognition set."""
    rs = str(recognition_set).strip() if recognition_set else ""
    if rs not in RECOGNITION_SETS:
        rs = ""

    cat = str(sc_category).strip() if sc_category else None
    if cat is not None and cat not in SC_STATE_RECOGNITION_CATEGORIES:
        cat = None

    # Deny by default: federal recognition is asserted only where the set says
    # so. An absent value is UNKNOWN, never False-as-if-determined.
    if rs in {
        "federally_recognized_resident_in_sc",
        "federally_recognized_with_sc_consultation_interest",
    }:
        fed = True
    elif rs == "sc_state_recognized":
        fed = False
    elif federally_recognized is None:
        fed = None
    else:
        fed = bool(federally_recognized)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "entity_name": entity_name,
            "recognition_set": rs,
            "sc_recognition_category": cat,
            "federally_recognized": fed,
            "federal_recognition_status": (
                "federally_recognized"
                if fed is True
                else "state_recognized_only"
                if fed is False
                else "UNKNOWN"
            ),
            "resident_state": resident_state,
            # A consulting-party listing is not recognition.
            "is_consultation_listing": rs
            == "federally_recognized_with_sc_consultation_interest",
            "consultation_listing_implies_recognition_in_sc": False,
            "sets_collapsed": False,
            "fabricated": False,
        }
    )


def evaluate_program_access(
    *,
    entity: dict[str, Any],
    program_id: Any = None,
    federal_recognition_required: Any = None,
) -> dict[str, Any]:
    """Can this entity access this program? Unknowns stay unknown."""
    fed = entity.get("federally_recognized")
    pid = str(program_id) if program_id else None

    if pid in FEDERAL_RECOGNITION_GATED_PROGRAMS:
        required: Any = True
    elif federal_recognition_required is None:
        required = None
    else:
        required = bool(federal_recognition_required)

    if required is None:
        access = "unknown"
    elif required is False:
        access = "eligible_class" if fed is not None else "unknown"
    elif fed is True:
        access = "eligible_class"
    elif fed is False:
        access = "excluded_federal_recognition_required"
    else:
        access = "unknown"

    state_pathway = (
        fed is False and pid in STATE_SUBRECIPIENT_PATHWAY_PROGRAMS
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "entity_name": entity.get("entity_name"),
            "program_id": pid,
            "federal_recognition_required": required,
            "access_status": access,
            # FTA's documented route, applied only where documented.
            "state_subrecipient_pathway_available": state_pathway,
            "state_subrecipient_pathway_is_documented": state_pathway,
            # ED Title VI student counts are not applicant eligibility.
            "applicant_eligibility_determined": False,
            "customer_advised": False,
            "fabricated": False,
        }
    )


def apply_geography_gate(
    *,
    customer_states: list[Any] | None = None,
    source_states: list[Any] | None = None,
    source_name: Any = None,
    eligible_entity_set: list[Any] | None = None,
    customer_entity_name: Any = None,
    distribution_mode: Any = None,
) -> dict[str, Any]:
    """Deny by default. Unknown geography is withheld, not passed through."""
    cust = sorted(
        {str(s).strip().upper() for s in (customer_states or []) if str(s).strip()}
    )
    src = sorted(
        {str(s).strip().upper() for s in (source_states or []) if str(s).strip()}
    )

    mode = str(distribution_mode).strip().lower() if distribution_mode else "unknown"
    if mode not in DISTRIBUTION_MODES:
        mode = "unknown"

    overlap = sorted(set(cust) & set(src))

    if not cust:
        verdict = "withheld_unknown"
        reason = "customer_states_unknown"
    elif not src:
        verdict = "withheld_unknown"
        reason = "source_geography_unknown"
    elif overlap:
        verdict = "in_scope"
        reason = "state_overlap"
    else:
        verdict = "out_of_scope"
        reason = "no_state_overlap"

    # Enumerated-set eligibility, where a class vocabulary cannot express the
    # restriction (Reclamation's 30 named Colorado River Basin Tribes).
    enumerated = [str(e).strip() for e in (eligible_entity_set or []) if str(e).strip()]
    if enumerated:
        named = str(customer_entity_name or "").strip()
        if not named:
            verdict, reason = "withheld_unknown", "enumerated_set_customer_unnamed"
        elif named not in enumerated:
            verdict, reason = "out_of_scope", "not_in_enumerated_eligible_set"
        elif verdict == "in_scope":
            reason = "state_overlap_and_named_in_enumerated_set"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_name": source_name,
            "customer_states": cust,
            "source_states": src,
            "state_overlap": overlap,
            "verdict": verdict,
            "reason": reason,
            "enumerated_eligible_set_size": len(enumerated),
            "enumerated_set_applied": bool(enumerated),
            "distribution_mode": mode,
            # The gate runs before ranking, not as a post-filter on results.
            "runs_before_ranking": True,
            "surfaced_to_customer": verdict == "in_scope",
            "fabricated": False,
        }
    )


def recognition_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if record.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if record.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    if "recognition_set" in record:
        rs = record.get("recognition_set")
        if rs not in RECOGNITION_SETS:
            fails.append("recognition_set_out_of_vocabulary")
        if record.get("sets_collapsed") is not False:
            fails.append("recognition_sets_collapsed")
        # A Section 106 consulting-party listing must never read as SC
        # recognition.
        if record.get("is_consultation_listing") and record.get(
            "consultation_listing_implies_recognition_in_sc"
        ):
            fails.append("consultation_listing_treated_as_recognition")
        if rs == "sc_state_recognized":
            if record.get("federally_recognized") is not False:
                fails.append("state_recognized_entity_marked_federally_recognized")
            if record.get("sc_recognition_category") not in (
                SC_STATE_RECOGNITION_CATEGORIES
            ):
                fails.append("sc_entity_without_a_recognition_category")
        if rs == "federally_recognized_resident_in_sc":
            if record.get("entity_name") != CATAWBA_NATION_NAME:
                fails.append("more_than_the_one_resident_federally_recognized_tribe")

    if "access_status" in record:
        if record.get("applicant_eligibility_determined") is not False:
            fails.append("recognition_record_claimed_applicant_eligibility")
        if record.get("customer_advised") is not False:
            fails.append("recognition_record_claimed_customer_advice")
        # The state-subrecipient route may only be reported where documented.
        if record.get("state_subrecipient_pathway_available") and not record.get(
            "state_subrecipient_pathway_is_documented"
        ):
            fails.append("undocumented_state_pathway_offered")
        # A federal-recognition-gated program may only read eligible_class for
        # an entity that actually holds federal recognition.
        if (
            record.get("program_id") in FEDERAL_RECOGNITION_GATED_PROGRAMS
            and record.get("access_status") == "eligible_class"
            and record.get("federal_recognition_required") is not True
        ):
            fails.append("gated_program_did_not_require_federal_recognition")

    return fails


def geography_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    verdict = result.get("verdict")
    if verdict not in GEOGRAPHY_VERDICTS:
        fails.append("geography_verdict_out_of_vocabulary")
    if result.get("runs_before_ranking") is not True:
        fails.append("geography_gate_demoted_to_a_post_filter")

    # Deny by default: only in_scope surfaces.
    if result.get("surfaced_to_customer") and verdict != "in_scope":
        fails.append("non_in_scope_source_surfaced")
    if verdict == "in_scope" and not result.get("state_overlap"):
        fails.append("in_scope_without_state_overlap")
    if verdict == "withheld_unknown" and result.get("surfaced_to_customer"):
        fails.append("unknown_geography_passed_through")
    if result.get("distribution_mode") not in DISTRIBUTION_MODES:
        fails.append("distribution_mode_out_of_vocabulary")
    if result.get("enumerated_set_applied") and not result.get(
        "enumerated_eligible_set_size"
    ):
        fails.append("enumerated_set_applied_but_empty")

    return fails


def bridged_eligibility_classes() -> frozenset[str]:
    """Gate 92F's class vocabulary, imported rather than redeclared."""
    return ELIGIBILITY_CLASSES
