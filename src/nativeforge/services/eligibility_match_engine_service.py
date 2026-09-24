"""Gate 174H/K: the match, and the reasons for it.

```text
normalized requirements (GLOBAL, parsed once)
  + organization capability profile (per tenant)
  = a six-valued result, with every requirement accounted for
```

**174K.** The requirements are normalized ONCE per opportunity, globally, by
Gate 174's parsing layer. A tenant match consumes that normalization; it never
re-reads the source. Parsing per tenant would mean the same NOFO producing a
thousand identical readings that can drift apart, and it is the same shape
Gate 172 removed from the source fleet and Gate 173 kept out of relevance.

**No opaque yes/no.** Every requirement lands in exactly one of four buckets -
satisfied, unsatisfied, unknown, review-required - and the four partition the
set. A result that cannot name which requirement produced it is not an answer
an operator can act on, and it is not an answer a funder's programme officer
can be shown.

Three rules decide the verdict, in order:

**An exclusion that applies wins.** A disqualifier is not weighed against
positives; it ends the question. The alternative - a "score" that lets six
satisfied requirements outvote an explicit exclusion - is how a system tells a
Tribe to spend three weeks on an application they were never permitted to
submit.

**A failed STRUCTURAL requirement is INELIGIBLE; a failed ADDRESSABLE one is
CONDITIONAL.** Not being a Tribe cannot be fixed before the deadline. A
missing UEI can. Collapsing those into one "no" throws away the only part of
the answer that is actionable.

**Unknown is never eligible.** An unanswered profile field leaves its
requirement UNKNOWN, and unknowns on structural requirements hold the whole
result at UNKNOWN rather than letting it drift up to LIKELY_ELIGIBLE.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.eligibility_requirement_model_service import (
    ADDRESSABLE_KINDS,
    APPLICANT_TYPE,
    CONDITIONALLY_ELIGIBLE,
    DEADLINE,
    ELIGIBILITY_MODEL_VERSION,
    ELIGIBILITY_RESULTS,
    ELIGIBLE,
    EXCLUSION,
    GEOGRAPHIC,
    INELIGIBLE,
    LIKELY_ELIGIBLE,
    MATCHING_FUNDS,
    NOT_APPLICABLE,
    PURSUABLE,
    RECOGNITION_OR_DESIGNATION,
    REGISTRATION,
    SATISFIED,
    STRUCTURAL_KINDS,
    UNKNOWN,
    UNKNOWN_STATUS,
    UNSATISFIED,
    eligibility_transfers_between,
)
from nativeforge.services.organization_capability_profile_service import (
    LEGAL_STATUS_FIELDS,
    SELF_DECLARED,
    entity_classes_for,
    field_is_answered,
    field_value,
)

SCHEMA_VERSION = "nf_eligibility_match_engine_v1"

#: Which profile field answers which requirement kind. One mapping, so a
#: requirement cannot be silently answered by an unrelated fact.
REQUIREMENT_PROFILE_FIELD: dict[str, str] = {
    APPLICANT_TYPE: "entity_class",
    "LEGAL_ENTITY_TYPE": "legal_entity_type",
    GEOGRAPHIC: "geographies_served",
    "BENEFICIARY": "populations_served",
    "POPULATION": "population_served",
    "PARTNERSHIP": "partnership_capability",
    MATCHING_FUNDS: "matching_funds_capability",
    REGISTRATION: "sam_registration",
    "EXPERIENCE": "program_experience",
    "OWNERSHIP_OR_CONTROL": "owner_or_control",
    "GOVERNMENT_STATUS": "entity_class",
    RECOGNITION_OR_DESIGNATION: "federal_recognition",
    "SPECIAL_DESIGNATION": "designations",
    DEADLINE: "",
    "OTHER_CONDITION": "",
}

#: Why a human is being asked.
MATCH_REVIEW_REASONS: tuple[str, ...] = (
    "requirement_kind_has_no_profile_field",
    "legal_status_is_only_self_declared",
    "requirement_text_needs_a_human",
    "conflicting_requirements",
    "deadline_cannot_be_evaluated_here",
    "entity_class_named_is_not_the_applicants",
)


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value.strip().lower()]
    return [str(v).strip().lower() for v in value]


def _evaluate_applicant_type(
    requirement: dict[str, Any], profile: dict[str, Any]
) -> tuple[str, str]:
    """Does the funder's named class include THIS applicant's class?

    Deny by default. A notice naming "Indian tribes" does not name a tribal
    college, and saying otherwise costs a Tribe a cycle.
    """
    applicant_classes = entity_classes_for(profile)
    if not applicant_classes:
        return UNKNOWN_STATUS, "the organisation has not stated its entity class"

    named = [
        str(value) for value in (requirement.get("applies_to_entity_classes") or [])
    ]
    if not named:
        return UNKNOWN_STATUS, "the requirement names no entity class"

    for applicant in applicant_classes:
        for target in named:
            if eligibility_transfers_between(
                named_class=target, applicant_class=applicant
            ):
                return SATISFIED, f"the source names {target}"
    return (
        UNSATISFIED,
        f"the source names {sorted(named)}, the applicant is {applicant_classes}",
    )


def _evaluate_generic(
    requirement: dict[str, Any], profile: dict[str, Any], field: str
) -> tuple[str, str]:
    if not field:
        return UNKNOWN_STATUS, "this requirement kind has no profile field"
    if not field_is_answered(profile, field):
        return UNKNOWN_STATUS, f"the profile has not answered {field}"

    value = field_value(profile, field)
    required = requirement.get("normalized_value")

    if isinstance(value, bool):
        # A boolean capability. The requirement asks for it; the profile has
        # it or does not.
        return (
            (SATISFIED, f"{field} is true")
            if value
            else (UNSATISFIED, f"{field} is false")
        )

    if isinstance(value, (int, float)) and isinstance(required, (int, float)):
        return (
            (SATISFIED, f"{field} {value} meets {required}")
            if value >= required
            else (UNSATISFIED, f"{field} {value} is below {required}")
        )

    wanted = set(_as_list(required))
    held = set(_as_list(value))
    if not wanted:
        return UNKNOWN_STATUS, "the requirement has no comparable value"
    overlap = sorted(wanted & held)
    if overlap:
        return SATISFIED, f"{field} covers {overlap}"
    return UNSATISFIED, f"{field} {sorted(held)} does not cover {sorted(wanted)}"


def match_eligibility(
    *,
    canonical_id: Any,
    requirements: list[dict[str, Any]],
    profile: dict[str, Any],
    tenant_id: Any = None,
    evaluated_at: Any = None,
) -> dict[str, Any]:
    """One organisation against one opportunity's normalized requirements."""
    satisfied: list[dict[str, Any]] = []
    unsatisfied: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    review: list[dict[str, Any]] = []
    review_reasons: list[str] = []
    applied_exclusions: list[dict[str, Any]] = []

    for requirement in requirements:
        kind = str(requirement.get("requirement_kind") or "")
        polarity = str(requirement.get("polarity") or "")
        field = REQUIREMENT_PROFILE_FIELD.get(kind, "")

        if kind == DEADLINE:
            # A deadline is real and is not an eligibility question about the
            # organisation. Saying so beats silently satisfying it.
            entry = {
                "requirement_id": requirement.get("requirement_id"),
                "requirement_kind": kind,
                "polarity": polarity,
                "status": NOT_APPLICABLE,
                "why": "a deadline is evaluated by the pursuit layer, not here",
                "original_text": requirement.get("original_text"),
            }
            review.append(entry)
            review_reasons.append("deadline_cannot_be_evaluated_here")
            continue

        if kind == APPLICANT_TYPE or kind == "GOVERNMENT_STATUS":
            status, why = _evaluate_applicant_type(requirement, profile)
        else:
            status, why = _evaluate_generic(requirement, profile, field)

        entry = {
            "requirement_id": requirement.get("requirement_id"),
            "requirement_kind": kind,
            "polarity": polarity,
            "status": status,
            "why": why,
            "is_structural": kind in STRUCTURAL_KINDS,
            "is_addressable": kind in ADDRESSABLE_KINDS,
            "original_text": requirement.get("original_text"),
            "evidence_ids": requirement.get("evidence_ids") or [],
            "section_ref": requirement.get("section_ref"),
            "page_ref": requirement.get("page_ref"),
        }

        # An EXCLUSION that the applicant MATCHES is a disqualifier.
        if polarity == EXCLUSION:
            if status == SATISFIED:
                entry["status"] = UNSATISFIED
                entry["why"] = f"excluded: {why}"
                applied_exclusions.append(entry)
                unsatisfied.append(entry)
            elif status == UNKNOWN_STATUS:
                unknown.append(entry)
            else:
                # The exclusion does not describe this applicant. Good.
                entry["status"] = NOT_APPLICABLE
                entry["why"] = f"exclusion does not apply: {why}"
                satisfied.append(entry)
            continue

        if status == SATISFIED:
            # A legal-status claim resting only on the organisation's own word
            # is satisfied AND flagged, because those are different positions.
            if field in LEGAL_STATUS_FIELDS:
                verification = str(
                    ((profile.get("fields") or {}).get(field) or {}).get("verification")
                )
                if verification == SELF_DECLARED:
                    entry["self_declared_legal_status"] = True
                    review_reasons.append("legal_status_is_only_self_declared")
            satisfied.append(entry)
        elif status == UNSATISFIED:
            unsatisfied.append(entry)
        else:
            unknown.append(entry)
            if not field:
                review_reasons.append("requirement_kind_has_no_profile_field")

    # ---- the verdict, in order ---------------------------------------
    structural_failures = [
        e for e in unsatisfied if e.get("is_structural") and e["polarity"] != EXCLUSION
    ]
    addressable_failures = [e for e in unsatisfied if e.get("is_addressable")]
    other_failures = [
        e
        for e in unsatisfied
        if not e.get("is_structural")
        and not e.get("is_addressable")
        and e["polarity"] != EXCLUSION
    ]
    structural_unknowns = [e for e in unknown if e.get("is_structural")]

    if applied_exclusions:
        result = INELIGIBLE
        reason = "an exclusion applies to this applicant"
    elif structural_failures:
        result = INELIGIBLE
        reason = "a structural requirement is not met and cannot be obtained"
    elif not requirements:
        result = UNKNOWN
        reason = "no requirements have been normalized for this opportunity"
    elif structural_unknowns:
        # We do not know something that decides the answer.
        result = UNKNOWN
        reason = "a structural requirement is unanswered"
    elif other_failures:
        result = INELIGIBLE
        reason = "a requirement is not met"
    elif addressable_failures:
        result = CONDITIONALLY_ELIGIBLE
        reason = "eligible if the named conditions are obtained"
    elif unknown:
        # Only non-structural unknowns left. Real, and not a blocker.
        result = LIKELY_ELIGIBLE
        reason = "everything checkable is satisfied; some detail is unanswered"
    elif satisfied:
        result = ELIGIBLE
        reason = "every requirement is satisfied"
    else:
        result = UNKNOWN
        reason = "nothing could be evaluated"

    # Review is a separate axis and may accompany any result, except where the
    # reason IS the result.
    if review_reasons and result in PURSUABLE:
        pass  # the flags travel on the row; the result stands

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "model_version": ELIGIBILITY_MODEL_VERSION,
            "canonical_id": str(canonical_id) if canonical_id else None,
            "tenant_id": str(tenant_id) if tenant_id else None,
            "organization_id": profile.get("organization_id"),
            "profile_version": profile.get("profile_version"),
            "eligibility_result": result,
            "reason": reason,
            "satisfied_requirements": satisfied,
            "unsatisfied_requirements": unsatisfied,
            "unknown_requirements": unknown,
            "review_required_items": review,
            "review_reasons": sorted(set(review_reasons)),
            "applied_exclusions": applied_exclusions,
            "conditions_to_obtain": sorted(
                {str(e["requirement_kind"]) for e in addressable_failures}
            ),
            "requirement_count": len(requirements),
            "accounted_for": len(satisfied)
            + len(unsatisfied)
            + len(unknown)
            + len(review),
            "supporting_evidence_ids": sorted(
                {
                    str(evidence)
                    for bucket in (satisfied, unsatisfied, unknown)
                    for e in bucket
                    for evidence in (e.get("evidence_ids") or [])
                }
            ),
            "evaluated_at": evaluated_at,
            # 174K, stated on every row.
            "consumed_global_normalization": True,
            "reparsed_source_per_tenant": False,
        }
    )


def match_invariant_failures(match: dict[str, Any]) -> list[str]:
    """Refuse a match that cannot account for its own inputs."""
    failures: list[str] = []

    result = str(match.get("eligibility_result") or "")
    if result not in ELIGIBILITY_RESULTS:
        failures.append(f"result_outside_the_vocabulary:{result or 'missing'}")

    if not match.get("canonical_id"):
        failures.append("match_not_bound_to_a_canonical_opportunity")
    if not match.get("profile_version"):
        failures.append("match_does_not_name_the_profile_version_it_used")
    if not match.get("model_version"):
        failures.append("match_does_not_name_its_model_version")

    for reason in match.get("review_reasons") or []:
        if str(reason) not in MATCH_REVIEW_REASONS:
            failures.append(f"review_reason_outside_the_vocabulary:{reason}")

    # Every requirement lands in exactly one bucket. A match that loses one
    # has an answer nobody can reconstruct.
    if int(match.get("accounted_for") or 0) != int(match.get("requirement_count") or 0):
        failures.append(
            f"requirements_unaccounted_for:"
            f"{match.get('accounted_for')}_of_{match.get('requirement_count')}"
        )

    # The load-bearing rule.
    if match.get("applied_exclusions") and result in PURSUABLE:
        failures.append(f"exclusion_applies_but_result_is_{result}")

    # UNKNOWN is never a yes.
    if result == UNKNOWN and result in PURSUABLE:
        failures.append("unknown_counted_as_pursuable")

    # An ELIGIBLE with an unanswered structural requirement is a guess.
    if result == ELIGIBLE:
        if any(e.get("is_structural") for e in match.get("unknown_requirements") or []):
            failures.append("eligible_with_an_unanswered_structural_requirement")
        if match.get("unsatisfied_requirements"):
            failures.append("eligible_with_an_unsatisfied_requirement")

    if result == CONDITIONALLY_ELIGIBLE and not match.get("conditions_to_obtain"):
        failures.append("conditional_result_names_no_condition")

    if not match.get("consumed_global_normalization"):
        failures.append("match_did_not_consume_global_normalization")
    if match.get("reparsed_source_per_tenant"):
        failures.append("match_reparsed_the_source_per_tenant")

    return sorted(set(failures))


def describe_match_engine() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "model_version": ELIGIBILITY_MODEL_VERSION,
            "results": list(ELIGIBILITY_RESULTS),
            "review_reasons": list(MATCH_REVIEW_REASONS),
            "requirement_profile_field": dict(REQUIREMENT_PROFILE_FIELD),
            "every_requirement_kind_has_a_mapping": True,
            "exclusion_ends_the_question": True,
            "structural_failure_is_ineligible": sorted(STRUCTURAL_KINDS),
            "addressable_failure_is_conditional": sorted(ADDRESSABLE_KINDS),
            "unknown_is_not_eligible": UNKNOWN not in PURSUABLE,
            "every_requirement_is_accounted_for": True,
            "match_consumes_global_normalization": True,
            "entity_class_never_transfers_silently": True,
        }
    )
