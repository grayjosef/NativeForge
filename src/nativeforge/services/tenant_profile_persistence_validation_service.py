"""Tenant beta profile validation (Gate 123C).

Is a stored profile fit to drive source matching, digest generation and beta
onboarding — without inventing anything to make it so.

## The four refusals, bridged from Gate 103

```text
recognition_status_from_name_or_state
    federal, state, historic-affiliation and unrecognised are legally distinct,
    and a wrong guess reaches a real government's eligibility

federal_eligibility_from_state_recognition
    South Carolina recognising a Tribe says nothing about federal programme
    eligibility, and the inverse is equally false

operating_state_from_mailing_address
    a tenant may operate, serve and be eligible in a state it is not
    headquartered in

applicant_class_from_tenant_kind
    a tribal government may apply under several classes, and which one applies
    is per-opportunity
```

Imported from `tenant_beta_profile_service`, never restated. Two copies of a
refusal is how one of them quietly stops being enforced.

## operating_states decides; service_area describes

This is the validation that matters most in practice.

```text
operating_states   ["SC"]                     -> SC sources match
service_area       "the Pee Dee region"       -> matches nothing
mailing_address    "1 Main St, Columbia SC"   -> matches nothing
```

`state_source_matching_enabled` is true only when `operating_states` is
non-empty *and* its fact status is actionable. A description of a service area
is prose; it is not a list of states, and nothing here turns one into the other.

`mailing_address_considered` is a constant `False` and an invariant refuses any
result claiming otherwise — this service does not accept a mailing address as a
parameter at all, and the field exists so a reader of one result can see that.

## An unknown is a result, not a gap

```text
unknown            nobody has established this
needs_human_review somebody looked and could not settle it
verified           established by evidence
tenant_supplied    the tenant told us and we have not checked
demo_fixture       a fixture value, never actionable
```

`ACTIONABLE_FACT_STATUSES` is `{verified, tenant_supplied}`. A `demo_fixture`
value is deliberately excluded: a demo value must never drive a real decision,
which is Gate 103's rule and the reason the status vocabulary exists at all.

## The South Carolina requirement stays explicit

A tenant whose `operating_states` includes `SC` gets SC sources matched. That is
a *consequence* of the list, not a special case in code — and stating it that
way is what keeps it correct when the second state arrives.

What is explicit is the inverse: a tenant with `SC` in a service-area
description and nothing in `operating_states` matches no SC sources, and the
result says why.
"""

from __future__ import annotations

import json
import re
from typing import Any

from nativeforge.services.tenant_beta_profile_service import (
    ACTIONABLE_FACT_STATUSES,
    APPLICANT_CLASSES,
    DIGEST_FREQUENCIES,
    FACT_STATUSES,
    INFERENCE_PROHIBITED,
    RECOGNITION_STATUSES,
)

SCHEMA_VERSION = "nf_tenant_profile_persistence_validation_v1"

# Two-letter postal codes. A state is this shape or it is not a state - anything
# longer is a description somebody hoped would be parsed.
_STATE_CODE_RE = re.compile(r"^[A-Z]{2}$")

# Routing rules a tenant may declare. Bridged from Gate 103's alert audiences.
ROUTING_TARGETS = frozenset({"grants_admin", "program_staff", "leadership", "none"})

VALIDATION_FIELDS: tuple[str, ...] = (
    "recognition_status_known",
    "operating_states_valid",
    "service_area_present",
    "applicant_classes_present",
    "priority_topics_present",
    "excluded_topics_valid",
    "digest_frequency_valid",
    "routing_rules_valid",
    "source_watchlist_preferences_valid",
    "unknowns_labelled",
    "human_review_required",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _listed(value: Any) -> list[str]:
    """A list of non-empty strings. A bare string is not a list of anything."""
    if value is None or isinstance(value, str):
        return []
    try:
        return [str(v).strip() for v in value if str(v).strip()]
    except TypeError:
        return []


def _actionable(status: Any) -> bool:
    return str(status or "").strip().lower() in ACTIONABLE_FACT_STATUSES


def validate_tenant_profile(
    *,
    recognition_status: Any = None,
    recognition_status_fact_status: Any = None,
    operating_states: Any = None,
    operating_states_fact_status: Any = None,
    service_area: Any = None,
    applicant_classes: Any = None,
    applicant_classes_fact_status: Any = None,
    priority_topics: Any = None,
    excluded_topics: Any = None,
    digest_frequency: Any = None,
    routing_rules: Any = None,
    source_watchlist_preferences: Any = None,
) -> dict[str, Any]:
    """Is this profile fit to drive matching and digests? Deny by default.

    Nothing here infers. A field that was not supplied stays unknown, and a
    validation that could not run says so rather than defaulting to pass.
    """
    blocked_reasons: list[str] = []
    unknown_fields: list[str] = []

    # -- recognition status --------------------------------------------------
    recognition = str(recognition_status or "unknown").strip().lower()
    recognition_fact = str(recognition_status_fact_status or "unknown").strip().lower()
    if recognition not in RECOGNITION_STATUSES:
        blocked_reasons.append(f"recognition_status_not_recognised:{recognition}")
    if recognition_fact not in FACT_STATUSES:
        blocked_reasons.append(
            f"recognition_status_fact_status_not_recognised:{recognition_fact}"
        )

    recognition_status_known = bool(
        recognition in RECOGNITION_STATUSES
        and recognition != "unknown"
        and _actionable(recognition_fact)
    )
    if not recognition_status_known:
        unknown_fields.append("recognition_status")
        # Not inferred from a name, a state, or anything else. Named so the
        # refusal is inspectable.
        blocked_reasons.append("recognition_status_unestablished_and_never_inferred")

    # -- operating states, which decide state matching -----------------------
    states = _listed(operating_states)
    states_fact = str(operating_states_fact_status or "unknown").strip().lower()
    malformed = [s for s in states if not _STATE_CODE_RE.match(s.upper())]

    if isinstance(operating_states, str):
        blocked_reasons.append("operating_states_must_be_a_list_not_a_delimited_string")
    if malformed:
        blocked_reasons.append(
            f"operating_state_is_not_a_two_letter_code:{sorted(malformed)[0]}"
        )

    operating_states_valid = bool(states and not malformed and _actionable(states_fact))
    if not states:
        unknown_fields.append("operating_states")
        blocked_reasons.append("no_operating_states_so_no_state_source_matching")
    elif not _actionable(states_fact):
        blocked_reasons.append(
            f"operating_states_fact_status_is_not_actionable:{states_fact}"
        )

    # State matching is enabled by the list and by nothing else.
    state_source_matching_enabled = operating_states_valid
    matched_states = sorted({s.upper() for s in states}) if states else []

    # -- the service area describes and never decides ------------------------
    area = str(service_area or "").strip()
    service_area_present = bool(area)
    if area and not states:
        blocked_reasons.append(
            "service_area_described_without_operating_states_and_none_is_inferred"
        )

    # -- applicant classes ---------------------------------------------------
    classes = _listed(applicant_classes)
    classes_fact = str(applicant_classes_fact_status or "unknown").strip().lower()
    unrecognised = [c for c in classes if c not in APPLICANT_CLASSES]
    if unrecognised:
        blocked_reasons.append(
            f"applicant_class_not_recognised:{sorted(unrecognised)[0]}"
        )

    applicant_classes_present = bool(
        classes
        and not unrecognised
        and "unknown" not in classes
        and _actionable(classes_fact)
    )
    if not classes or "unknown" in classes:
        unknown_fields.append("applicant_classes")
        blocked_reasons.append("applicant_classes_unestablished_and_never_inferred")
    elif not _actionable(classes_fact):
        blocked_reasons.append(
            f"applicant_classes_fact_status_is_not_actionable:{classes_fact}"
        )

    # -- priorities and exclusions -------------------------------------------
    priorities = _listed(priority_topics)
    priority_topics_present = bool(priorities)
    if not priorities:
        unknown_fields.append("priority_topics")
        blocked_reasons.append("no_priority_topics_so_ranking_is_unweighted")

    exclusions = _listed(excluded_topics)
    overlap = sorted(set(priorities) & set(exclusions))
    excluded_topics_valid = not overlap
    if overlap:
        # A topic both wanted and excluded is a contradiction a human has to
        # settle; guessing which one wins would be inventing a preference.
        blocked_reasons.append(f"topic_both_prioritised_and_excluded:{overlap[0]}")

    # -- digest and routing --------------------------------------------------
    frequency = str(digest_frequency or "").strip().lower()
    digest_frequency_valid = frequency in DIGEST_FREQUENCIES
    if not digest_frequency_valid:
        blocked_reasons.append(f"digest_frequency_not_recognised:{frequency}")

    routes = _listed(routing_rules)
    unknown_routes = [r for r in routes if r not in ROUTING_TARGETS]
    routing_rules_valid = bool(routes and not unknown_routes)
    if not routes:
        unknown_fields.append("routing_rules")
        blocked_reasons.append("no_routing_rules_so_alerts_reach_nobody")
    if unknown_routes:
        blocked_reasons.append(
            f"routing_target_not_recognised:{sorted(unknown_routes)[0]}"
        )

    # -- the watchlist preference --------------------------------------------
    watchlist = _listed(source_watchlist_preferences)
    source_watchlist_preferences_valid = bool(watchlist)
    if not watchlist:
        unknown_fields.append("source_watchlist_preferences")
        blocked_reasons.append("no_source_watchlist_preferences_declared")

    # -- what none of it settles ---------------------------------------------
    unknowns_labelled = True  # every unknown above was named, not defaulted
    human_review_required = bool(unknown_fields or blocked_reasons)

    profile_ready_for_matching = bool(
        recognition_status_known
        and operating_states_valid
        and applicant_classes_present
        and digest_frequency_valid
        and routing_rules_valid
        and excluded_topics_valid
        and not blocked_reasons
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "recognition_status_known": recognition_status_known,
            "recognition_status": recognition,
            "operating_states_valid": operating_states_valid,
            "operating_states": matched_states,
            "state_source_matching_enabled": state_source_matching_enabled,
            "state_source_matching_states": matched_states,
            "service_area_present": service_area_present,
            "applicant_classes_present": applicant_classes_present,
            "priority_topics_present": priority_topics_present,
            "excluded_topics_valid": excluded_topics_valid,
            "digest_frequency_valid": digest_frequency_valid,
            "routing_rules_valid": routing_rules_valid,
            "source_watchlist_preferences_valid": (source_watchlist_preferences_valid),
            "unknowns_labelled": unknowns_labelled,
            "unknown_fields": sorted(set(unknown_fields)),
            "human_review_required": human_review_required,
            "profile_ready_for_matching": profile_ready_for_matching,
            "blocked_reasons": sorted(set(blocked_reasons)),
            "prohibited_inferences": [name for name, _ in INFERENCE_PROHIBITED],
            # Constants. This service reads what it was given and infers nothing.
            "mailing_address_considered": False,
            "recognition_status_inferred": False,
            "operating_states_inferred": False,
            "applicant_class_inferred": False,
            "priorities_inferred": False,
            "fabricated": False,
        }
    )


def matches_state_source(
    *, validation: dict[str, Any], source_state: Any
) -> dict[str, Any]:
    """Would a state-scoped source match this profile?

    The answer is the operating-states list and nothing else. A source in a
    state a tenant merely describes does not match, and the result says which
    rule decided.
    """
    state = str(source_state or "").strip().upper()
    enabled = bool(validation.get("state_source_matching_enabled"))
    states = [str(s).upper() for s in validation.get("operating_states") or []]

    matched = bool(enabled and state and state in states)
    blocked_reasons: list[str] = []
    if not enabled:
        blocked_reasons.append("state_source_matching_disabled_for_this_profile")
    elif not state:
        blocked_reasons.append("no_source_state_supplied")
    elif not matched:
        blocked_reasons.append(f"source_state_not_in_operating_states:{state}")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_state": state or None,
            "operating_states": states,
            "matched": matched,
            "decided_by": "operating_states",
            "mailing_address_considered": False,
            "service_area_considered": False,
            "blocked_reasons": blocked_reasons,
        }
    )


def validation_invariant_failures(result: dict[str, Any]) -> list[str]:
    """Contradictions this validation must never be able to produce."""
    failures: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        failures.append("schema_version_mismatch")

    for field in (
        "mailing_address_considered",
        "recognition_status_inferred",
        "operating_states_inferred",
        "applicant_class_inferred",
        "priorities_inferred",
        "fabricated",
    ):
        if result.get(field):
            failures.append(f"validation_claimed_{field}")

    if result.get("state_source_matching_enabled") and not result.get(
        "operating_states"
    ):
        failures.append("state_matching_enabled_without_any_operating_state")

    if result.get("state_source_matching_enabled") != result.get(
        "operating_states_valid"
    ):
        # These are the same fact by construction. If they ever diverge, one of
        # them has picked up a second source.
        failures.append("state_matching_diverged_from_operating_states_validity")

    if result.get("recognition_status_known") and result.get("recognition_status") in {
        "unknown",
        "",
    }:
        failures.append("an_unknown_recognition_status_was_reported_as_known")

    if result.get("profile_ready_for_matching"):
        for conjunct in (
            "recognition_status_known",
            "operating_states_valid",
            "applicant_classes_present",
            "digest_frequency_valid",
            "routing_rules_valid",
        ):
            if not result.get(conjunct):
                failures.append(f"ready_for_matching_without:{conjunct}")
        if result.get("blocked_reasons"):
            failures.append("ready_for_matching_with_blocked_reasons_present")
        if result.get("human_review_required"):
            failures.append("ready_for_matching_while_human_review_is_required")

    if result.get("unknown_fields") and not result.get("human_review_required"):
        failures.append("unknown_fields_without_human_review")

    if not result.get("unknowns_labelled"):
        failures.append("an_unknown_was_not_labelled")

    return sorted(set(failures))


def build_validation_matrix(*, cases: list[dict[str, Any]]) -> dict[str, Any]:
    """Run a set of cases and report what none of them established."""
    rows: list[dict[str, Any]] = []
    for case in cases:
        result = validate_tenant_profile(**case["profile"])
        rows.append(
            {
                "case": case["case"],
                "recognition_status_known": result["recognition_status_known"],
                "operating_states_valid": result["operating_states_valid"],
                "state_source_matching_enabled": result[
                    "state_source_matching_enabled"
                ],
                "applicant_classes_present": result["applicant_classes_present"],
                "digest_frequency_valid": result["digest_frequency_valid"],
                "routing_rules_valid": result["routing_rules_valid"],
                "profile_ready_for_matching": result["profile_ready_for_matching"],
                "human_review_required": result["human_review_required"],
                "unknown_fields": result["unknown_fields"],
                "blocked_reasons": result["blocked_reasons"],
                "invariant_failures": validation_invariant_failures(result),
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "case_count": len(rows),
            "rows": rows,
            "ready_count": sum(1 for r in rows if r["profile_ready_for_matching"]),
            "state_matching_count": sum(
                1 for r in rows if r["state_source_matching_enabled"]
            ),
            "invariant_failures": sorted(
                {f for r in rows for f in r["invariant_failures"]}
            ),
        }
    )
