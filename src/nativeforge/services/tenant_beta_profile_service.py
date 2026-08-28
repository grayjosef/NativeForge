"""Tenant beta profile (Gate 103B).

A beta Tribe/tenant profile, built without fabricating tenant facts.

## Every fact carries how it is known

```text
verified            checked against an authoritative source
tenant_supplied     the tenant told us
demo_fixture        invented for a demo, and labelled as such
unknown             nobody has established it
needs_human_review  established but disputed, or too consequential to assume
```

A profile field is never a bare value. It is a value **and** a status, because a
service area a tenant told us and a service area we made up for a screenshot
carry completely different weight and the difference disappears the moment they
are stored the same way.

Absent input is `unknown`, never a plausible default. The four beta tenants have
no verified facts in this repository, so a profile built today is honest about
being empty rather than helpfully pre-filled.

## What may not be inferred

**Recognition status is never inferred.** Not from the tenant's name, not from
its state, not from the presence of a `.gov` domain, not from another tenant.
Federal recognition, state recognition, historic affiliation and unrecognised
are legally distinct and a wrong guess reaches a real government's eligibility.

**Federal eligibility is never inferred from state recognition.** South Carolina
recognising a Tribe says nothing about federal programme eligibility, and the
inverse is equally false. `INFERENCE_PROHIBITED` records both, and an invariant
fails any profile whose recognition status is `verified` without a source.

**Operating state is not mailing address.** A tenant headquartered in one state
may operate, serve, and be eligible in another. They are separate fields and a
profile that fills one from the other is refused.

## SC priority is tenant-specific

South Carolina is the beta's immediate priority, but it is a property of
*these* tenants, not of NativeForge. `sc_priority` is derived from a tenant's
own `operating_states`, so a tenant that does not operate in SC does not get SC
sources prioritised for it. An invariant fails any profile claiming SC priority
without SC in its operating states.

## A profile is not coverage

Naming sources on a watchlist does not monitor them. Every profile carries
`live_source_coverage: False` and `source_monitoring_live: False`, held by
invariants, because a tenant with a fully configured watchlist and no collectors
is exactly the state this repository is in.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_tenant_beta_profile_v1"

FACT_STATUSES = frozenset(
    {
        "verified",
        "tenant_supplied",
        "demo_fixture",
        "unknown",
        "needs_human_review",
    }
)

# Statuses that may be acted on without a human first looking. `demo_fixture` is
# deliberately excluded - a demo value must never drive a real decision.
ACTIONABLE_FACT_STATUSES = frozenset({"verified", "tenant_supplied"})

# Statuses that mean nobody has established the fact.
UNESTABLISHED_FACT_STATUSES = frozenset({"unknown", "needs_human_review"})

TENANT_KINDS = frozenset(
    {
        "tribal_government",
        "tribal_college",
        "native_nonprofit",
        "native_business",
        "intertribal_organization",
        "unknown",
    }
)

# Legally distinct, never interchangeable. Gate 92's rule, carried into the
# tenant model.
RECOGNITION_STATUSES = frozenset(
    {
        "federally_recognized",
        "state_recognized",
        "historic_affiliation",
        "unrecognized",
        "unknown",
    }
)

APPLICANT_CLASSES = frozenset(
    {
        "federally_recognized_tribe",
        "state_recognized_tribe",
        "tribal_consortium",
        "tribal_college_or_university",
        "native_nonprofit",
        "native_business",
        "tribal_government_department",
        "unknown",
    }
)

DIGEST_FREQUENCIES = frozenset({"weekly", "daily", "none"})
DEFAULT_DIGEST_FREQUENCY = "weekly"
# Monday morning, per the product requirement. A day name, not a schedule - no
# scheduler consumes this, and Gate 98-102 established there is nothing to.
DEFAULT_DIGEST_DAY = "monday"

ALERT_AUDIENCES = frozenset({"grants_admin", "program_staff", "leadership", "none"})

# Inferences this service refuses to make, recorded so the refusals are
# inspectable rather than buried in branches.
INFERENCE_PROHIBITED: tuple[tuple[str, str], ...] = (
    (
        "recognition_status_from_name_or_state",
        "federal, state, historic-affiliation and unrecognised are legally "
        "distinct; a wrong guess reaches a real government's eligibility",
    ),
    (
        "federal_eligibility_from_state_recognition",
        "South Carolina recognising a Tribe says nothing about federal "
        "programme eligibility, and the inverse is equally false",
    ),
    (
        "operating_state_from_mailing_address",
        "a tenant may operate, serve and be eligible in a state it is not "
        "headquartered in",
    ),
    (
        "applicant_class_from_tenant_kind",
        "a tribal government may apply under several classes, and which one "
        "applies is per-opportunity",
    ),
)

PROFILE_FIELDS: tuple[str, ...] = (
    "tenant_id",
    "tenant_name",
    "tenant_kind",
    "recognition_status",
    "operating_states",
    "service_area",
    "applicant_classes",
    "program_priorities",
    "excluded_applicant_classes",
    "source_watchlist",
    "digest_preferences",
    "routing_rules",
    "alert_rules",
    "document_library_requirements",
    "awarded_grants_enabled",
    "reporting_tracking_enabled",
    "human_review_notes",
    "profile_fact_status",
    "blocked_reasons",
)

# The fields whose status is tracked individually. A profile's overall
# `profile_fact_status` is the weakest of these.
TRACKED_FACT_FIELDS: tuple[str, ...] = (
    "tenant_name",
    "tenant_kind",
    "recognition_status",
    "operating_states",
    "service_area",
    "applicant_classes",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text in vocabulary else fallback


def _fact(value: Any, status: Any, *, vocabulary: frozenset[str] | None = None) -> dict:
    """One field, plus how it is known. Absent input is unknown, not a default."""
    resolved_status = _norm(status, FACT_STATUSES, fallback="unknown")
    empty = value is None or (isinstance(value, str | list | dict) and not value)
    if empty:
        return {"value": None, "status": "unknown"}
    if vocabulary is not None and isinstance(value, str):
        if value.strip() not in vocabulary:
            # A value outside the vocabulary is not silently coerced to a
            # neighbour - somebody wrote something this model cannot read.
            return {"value": None, "status": "needs_human_review"}
    if resolved_status == "unknown":
        # A value supplied with no provenance is not nothing, but it is not
        # actionable either.
        return {"value": value, "status": "needs_human_review"}
    return {"value": value, "status": resolved_status}


def _weakest_status(facts: list[dict[str, Any]]) -> str:
    """The overall status is the weakest field's. A profile is as known as its
    least known load-bearing fact."""
    order = [
        "unknown",
        "needs_human_review",
        "demo_fixture",
        "tenant_supplied",
        "verified",
    ]
    present = [f.get("status", "unknown") for f in facts]
    for candidate in order:
        if candidate in present:
            return candidate
    return "unknown"


def build_tenant_beta_profile(
    *,
    tenant_id: Any,
    tenant_name: Any = None,
    tenant_name_status: Any = None,
    tenant_kind: Any = None,
    tenant_kind_status: Any = None,
    recognition_status: Any = None,
    recognition_status_status: Any = None,
    recognition_source: Any = None,
    operating_states: list[Any] | None = None,
    operating_states_status: Any = None,
    mailing_state: Any = None,
    service_area: Any = None,
    service_area_status: Any = None,
    applicant_classes: list[Any] | None = None,
    applicant_classes_status: Any = None,
    program_priorities: list[Any] | None = None,
    excluded_applicant_classes: list[Any] | None = None,
    source_watchlist: list[Any] | None = None,
    digest_frequency: Any = None,
    digest_day: Any = None,
    daily_alerts_audience: Any = None,
    routing_rules: list[Any] | None = None,
    alert_rules: list[Any] | None = None,
    document_library_requirements: list[Any] | None = None,
    awarded_grants_enabled: bool = False,
    reporting_tracking_enabled: bool = False,
    human_review_notes: list[Any] | None = None,
) -> dict[str, Any]:
    """One tenant profile. Nothing is inferred and nothing is monitored."""
    name = _fact(tenant_name, tenant_name_status)
    kind = _fact(tenant_kind, tenant_kind_status, vocabulary=TENANT_KINDS)
    recognition = _fact(
        recognition_status, recognition_status_status, vocabulary=RECOGNITION_STATUSES
    )

    states = [
        str(s).strip().upper() for s in (operating_states or []) if str(s).strip()
    ]
    operating = _fact(sorted(set(states)) or None, operating_states_status)
    area = _fact(service_area, service_area_status)

    classes = [
        str(c).strip() for c in (applicant_classes or []) if str(c).strip()
    ]
    recognised_classes = [c for c in classes if c in APPLICANT_CLASSES]
    unrecognised_classes = sorted(set(classes) - set(recognised_classes))
    applicant = _fact(sorted(set(recognised_classes)) or None, applicant_classes_status)

    excluded = sorted(
        {str(c).strip() for c in (excluded_applicant_classes or []) if str(c).strip()}
    )
    watchlist = sorted(
        {str(s).strip() for s in (source_watchlist or []) if str(s).strip()}
    )

    frequency = _norm(
        digest_frequency, DIGEST_FREQUENCIES, fallback=DEFAULT_DIGEST_FREQUENCY
    )
    audience = _norm(daily_alerts_audience, ALERT_AUDIENCES, fallback="none")

    blocked_reasons: list[str] = []

    # Recognition may never be inferred, and a verified status needs a source.
    if recognition["status"] == "verified" and not recognition_source:
        blocked_reasons.append("recognition_verified_without_a_source")
        recognition = {"value": recognition["value"], "status": "needs_human_review"}
    if recognition["status"] in UNESTABLISHED_FACT_STATUSES:
        blocked_reasons.append(f"recognition_status_{recognition['status']}")

    # Operating state is not mailing address.
    if not states and mailing_state:
        blocked_reasons.append("mailing_state_supplied_without_operating_states")

    if unrecognised_classes:
        blocked_reasons.append(
            f"applicant_class_out_of_vocabulary:{len(unrecognised_classes)}"
        )

    for field, fact in (
        ("tenant_name", name),
        ("tenant_kind", kind),
        ("operating_states", operating),
        ("service_area", area),
        ("applicant_classes", applicant),
    ):
        if fact["status"] in UNESTABLISHED_FACT_STATUSES:
            blocked_reasons.append(f"{field}_{fact['status']}")

    tracked = [name, kind, recognition, operating, area, applicant]
    overall = _weakest_status(tracked)

    # SC priority is derived from this tenant's own operating states, never
    # assumed. A tenant that does not operate in SC does not get SC priority.
    sc_priority = "SC" in (operating["value"] or []) and operating[
        "status"
    ] in ACTIONABLE_FACT_STATUSES | {"demo_fixture"}

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_id": tenant_id,
            "tenant_name": name,
            "tenant_kind": kind,
            "recognition_status": recognition,
            "recognition_source": recognition_source,
            "operating_states": operating,
            "mailing_state": mailing_state,
            "service_area": area,
            "applicant_classes": applicant,
            "unrecognised_applicant_classes": unrecognised_classes,
            "program_priorities": sorted(
                {str(p).strip() for p in (program_priorities or []) if str(p).strip()}
            ),
            "excluded_applicant_classes": excluded,
            "source_watchlist": watchlist,
            "digest_preferences": {
                "frequency": frequency,
                "day": _norm(
                    digest_day,
                    frozenset(
                        {
                            "monday",
                            "tuesday",
                            "wednesday",
                            "thursday",
                            "friday",
                            "saturday",
                            "sunday",
                        }
                    ),
                    fallback=DEFAULT_DIGEST_DAY,
                ),
                "daily_alerts_audience": audience,
                "daily_alerts_enabled": audience != "none",
            },
            "routing_rules": list(routing_rules or []),
            "alert_rules": list(alert_rules or []),
            "document_library_requirements": list(document_library_requirements or []),
            "awarded_grants_enabled": bool(awarded_grants_enabled),
            "reporting_tracking_enabled": bool(reporting_tracking_enabled),
            "human_review_notes": list(human_review_notes or []),
            "profile_fact_status": overall,
            "sc_priority": bool(sc_priority),
            "blocked_reasons": sorted(set(blocked_reasons)),
            "inference_prohibited": [
                {"inference": name_, "why": why}
                for name_, why in INFERENCE_PROHIBITED
            ],
            # A profile is a description, not a capability.
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "collectors_active": 0,
            "eligibility_determined": False,
            "fabricated": False,
        }
    )


def summarise_profiles(profiles: list[dict[str, Any]]) -> dict[str, Any]:
    by_status = {status: 0 for status in sorted(FACT_STATUSES)}
    for profile in profiles:
        status = profile.get("profile_fact_status")
        if status in by_status:
            by_status[status] += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_count": len(profiles),
            "by_profile_fact_status": by_status,
            "sc_priority_count": sum(1 for p in profiles if p.get("sc_priority")),
            "verified_profile_count": by_status.get("verified", 0),
            "source_monitoring_live": False,
            "live_source_coverage": False,
            "collectors_active": 0,
            "fabricated": False,
        }
    )


def profile_invariant_failures(profile: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if profile.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if profile.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in (
        "source_monitoring_live",
        "live_source_coverage",
        "eligibility_determined",
    ):
        if profile.get(constant) is not False:
            fails.append(f"profile_claimed:{constant}")
    if profile.get("collectors_active") != 0:
        fails.append("profile_claimed_active_collectors")

    # Every tracked fact carries a status from the vocabulary.
    for field in TRACKED_FACT_FIELDS:
        fact = profile.get(field)
        if not isinstance(fact, dict):
            fails.append(f"fact_without_a_status:{field}")
            continue
        if fact.get("status") not in FACT_STATUSES:
            fails.append(f"fact_status_out_of_vocabulary:{field}")
        # A status without a value is only honest as unknown.
        if fact.get("value") is None and fact.get("status") not in (
            UNESTABLISHED_FACT_STATUSES
        ):
            fails.append(f"empty_fact_claimed_as_known:{field}")

    # Recognition is the field a wrong guess hurts most.
    recognition = profile.get("recognition_status") or {}
    if recognition.get("value") is not None:
        if recognition["value"] not in RECOGNITION_STATUSES:
            fails.append("recognition_status_out_of_vocabulary")
    if recognition.get("status") == "verified" and not profile.get(
        "recognition_source"
    ):
        fails.append("recognition_verified_without_a_source")

    # SC priority is derived from this tenant's operating states.
    operating = profile.get("operating_states") or {}
    states = operating.get("value") or []
    if profile.get("sc_priority") and "SC" not in states:
        fails.append("sc_priority_without_sc_in_operating_states")
    if profile.get("sc_priority") and operating.get("status") == "unknown":
        fails.append("sc_priority_from_an_unknown_operating_state")

    # Mailing address is not an operating state.
    if profile.get("mailing_state") and not states:
        if "mailing_state_supplied_without_operating_states" not in (
            profile.get("blocked_reasons") or []
        ):
            fails.append("mailing_state_used_without_being_flagged")

    # The overall status may not be stronger than its weakest tracked fact.
    tracked = [
        profile.get(field)
        for field in TRACKED_FACT_FIELDS
        if isinstance(profile.get(field), dict)
    ]
    if tracked:
        expected = _weakest_status(tracked)
        if profile.get("profile_fact_status") != expected:
            fails.append("profile_status_stronger_than_its_weakest_fact")

    # The refusals must stay on the record.
    listed = {
        item.get("inference") for item in profile.get("inference_prohibited") or []
    }
    if listed != {name for name, _ in INFERENCE_PROHIBITED}:
        fails.append("prohibited_inference_dropped_from_the_record")

    # A profile with an unestablished tracked fact must say so.
    unestablished = [
        field
        for field in TRACKED_FACT_FIELDS
        if isinstance(profile.get(field), dict)
        and profile[field].get("status") in UNESTABLISHED_FACT_STATUSES
    ]
    if unestablished and not profile.get("blocked_reasons"):
        fails.append("unestablished_facts_without_a_reason")

    return fails
