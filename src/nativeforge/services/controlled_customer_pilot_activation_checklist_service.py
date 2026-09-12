"""Gate 149B: what must be true before a controlled customer pilot may start?

## The pilot is not a value that is false

It is not a value at all. No table records a pilot approval, no environment flag
exists, and no code path sets it true — every occurrence in this codebase is a
literal `False` written into a response.

This checklist therefore answers "what must be true", and says so plainly rather
than implying there is a switch. A reader given prerequisites assumes satisfying
them flips something, and then goes looking; building that switch before its
prerequisites exist is how one gets flipped early.

## Eight prerequisites, one satisfied

```text
real_customer_organization_exists    no  - the front of the queue
second_person_event_complete         no  - Gate 146
customer_auth_live                   no
verified_operational_binding         no  - Gate 147, five refusals
consent_boundary_documented          no  - Gate 148, no consent table exists
customer_beta_scope_approved         no  - Gate 145's fourth approval
customer_data_write_guard_ready      YES - Gate 148
support_and_rollback_owner_named     no  - the cheapest of the missing seven
```

## Four things that are deliberately NOT prerequisites

`source_monitoring_live`, `email_delivery`, `object_store_configured` and
`production_rollout` are not required for a pilot and must not be activated by
one. A pilot that quietly turned on email because "a pilot obviously needs
notifications" would undo four gates in one sentence. They are reported beside
the prerequisites, marked as separately gated, so nobody reads their absence as
an outstanding pilot blocker.

## Readiness is not live

The seventh instance of the distinction this campaign keeps drawing:

```text
email_delivery_readiness           is not  email_delivery
source_monitoring_preflight_ready  is not  source_monitoring_live
customer_data_write_guard_ready    is not  customer data writes allowed
activation_package_ready           is not  controlled_customer_pilot
```

The last one is this gate's own. A complete, correct activation package is not
an activated pilot, and the checklist reports both.

## No writes, no external calls, nothing activated

`build_pilot_activation_checklist` reads its arguments and returns. There is no
connection parameter, and `controlled_customer_pilot` is derived — never a
parameter — so a caller cannot assert the thing this module exists to measure.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_controlled_customer_pilot_activation_checklist_v1"

GO = "GO"
LIMITED_GO = "LIMITED_GO"
NO_GO = "NO_GO"

#: Every prerequisite, in the order they have to be cleared.
PREREQ_REAL_CUSTOMER_ORG = "real_customer_organization_exists"
PREREQ_SECOND_PERSON = "second_person_event_complete"
PREREQ_AUTH_LIVE = "customer_auth_live"
PREREQ_VERIFIED_BINDING = "verified_operational_binding"
PREREQ_CONSENT = "consent_boundary_documented"
PREREQ_BETA_SCOPE = "customer_beta_scope_approved"
PREREQ_WRITE_GUARD = "customer_data_write_guard_ready"
PREREQ_SUPPORT_OWNER = "support_and_rollback_owner_named"
PREREQ_SCOPE_LIMITS = "pilot_scope_limitations_documented"

PREREQUISITES: tuple[str, ...] = (
    PREREQ_REAL_CUSTOMER_ORG,
    PREREQ_SECOND_PERSON,
    PREREQ_AUTH_LIVE,
    PREREQ_VERIFIED_BINDING,
    PREREQ_CONSENT,
    PREREQ_BETA_SCOPE,
    PREREQ_WRITE_GUARD,
    PREREQ_SUPPORT_OWNER,
    PREREQ_SCOPE_LIMITS,
)

#: Each prerequisite, what kind of thing satisfies it, and who owns it.
PREREQUISITE_OWNERS: dict[str, dict[str, str]] = {
    PREREQ_REAL_CUSTOMER_ORG: {
        "kind": "a_customer",
        "owner": "nobody in this repository",
        "gate": "147",
        "satisfied_by": (
            "a real customer organization existing. There is none in this "
            "deployment other than the refused one, and no approval supplies "
            "a customer."
        ),
    },
    PREREQ_SECOND_PERSON: {
        "kind": "an_event",
        "owner": "the second person, then the operator",
        "gate": "146",
        "satisfied_by": (
            "a real second Google account completing real OAuth, being "
            "invited, and having that invite accepted"
        ),
    },
    PREREQ_AUTH_LIVE: {
        "kind": "derived_from_an_event",
        "owner": "follows the second-person event",
        "gate": "146",
        "satisfied_by": "invite_binding_passed becoming true",
    },
    PREREQ_VERIFIED_BINDING: {
        "kind": "five_refusals",
        "owner": "Mayhem, and only after a real customer organization exists",
        "gate": "147",
        "satisfied_by": "all five refusals clearing; one of them never does",
    },
    PREREQ_CONSENT: {
        "kind": "a_document_then_a_record",
        "owner": "Mayhem writes it; each tenant agrees to it",
        "gate": "148",
        "satisfied_by": (
            "deciding what is collected, retained, exported and deleted, "
            "writing it down, and recording that a tenant agreed"
        ),
    },
    PREREQ_BETA_SCOPE: {
        "kind": "recorded_decision",
        "owner": "Mayhem",
        "gate": "145",
        "satisfied_by": "approving the controlled customer beta scope",
    },
    PREREQ_WRITE_GUARD: {
        "kind": "code",
        "owner": "done",
        "gate": "148",
        "satisfied_by": "already satisfied - the guard is built and proved",
    },
    PREREQ_SUPPORT_OWNER: {
        "kind": "two_names",
        "owner": "Mayhem",
        "gate": "149",
        "satisfied_by": (
            "naming who a pilot customer calls when something breaks, and who "
            "can end the pilot. The cheapest of the missing prerequisites, and "
            "worth doing early: a pilot without a named owner is a pilot whose "
            "first incident has no addressee."
        ),
    },
    PREREQ_SCOPE_LIMITS: {
        "kind": "a_document",
        "owner": "Mayhem",
        "gate": "149",
        "satisfied_by": "this gate's docs, plus an owner accepting them",
    },
}

#: Capabilities that are NOT prerequisites and must not be activated by a
#: pilot. Reported beside the prerequisites so their absence is not read as an
#: outstanding pilot blocker.
SEPARATELY_GATED: dict[str, dict[str, str]] = {
    "source_monitoring_live": {
        "why_separate": (
            "171 sources need a human terms review, robots.txt per source, and "
            "an activation approval per source"
        ),
        "gate": "143",
    },
    "email_delivery": {
        "why_separate": (
            "a provider, a verified sender domain, unsubscribe and bounce "
            "handling"
        ),
        "gate": "142",
    },
    "object_store_configured": {
        "why_separate": (
            "five settings, an injected client, an owner decision and an "
            "external verification"
        ),
        "gate": "141",
    },
    "production_rollout": {
        "why_separate": "always NO_GO; not a computation",
        "gate": "145",
    },
}

#: What a pilot would and would not unlock. Both halves, because the second is
#: what a customer conversation gets wrong.
WOULD_UNLOCK: tuple[str, ...] = (
    "a real customer organization using the product, with their own data",
    "customer identifying and operational data writes, under a recorded "
    "consent and an approved scope",
    "the awarded-grants workspace, requirements, proof events and audit trail "
    "against real awards",
    "a weekly digest preview - rendered and read in the product, not sent",
)

WOULD_NOT_UNLOCK: tuple[str, ...] = (
    "any email leaving the system",
    "any live grant source being monitored",
    "any document body being stored",
    "production rollout",
    "a second customer, unless separately scoped",
)

#: Claims this module never makes.
NOT_APPROVED: tuple[str, ...] = (
    "controlled_customer_pilot",
    "production_rollout",
    "customer_auth_live",
    "verified_operational_binding",
    "consent_boundary_documented",
    "customer_beta_scope_approved",
    "source_monitoring_live",
    "email_delivery",
    "object_store_configured",
)

_FORBIDDEN_SHAPES: tuple[tuple[str, str], ...] = (
    ("email_address", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("bearer_token", r"\beyJ[A-Za-z0-9_-]{8,}"),
    ("session_cookie", r"nf_session="),
    ("set_cookie", r"(?i)set-cookie:"),
    ("google_client_secret", r"GOCSPX-"),
    ("private_key", r"BEGIN PRIVATE KEY"),
    ("aws_key", r"AKIA"),
)
_PROVIDER_SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _leaked_shapes(payload: dict[str, Any]) -> list[str]:
    body = json.dumps(payload, default=str, sort_keys=True)
    found = [name for name, pattern in _FORBIDDEN_SHAPES if re.search(pattern, body)]
    if _PROVIDER_SUBJECT_SHAPE.search(body):
        found.append("provider_subject")
    return sorted(set(found))


def build_pilot_activation_checklist(
    *,
    real_customer_organization_exists: bool | None = None,
    second_person_event_complete: bool | None = None,
    customer_auth_live: bool | None = None,
    verified_operational_binding: bool | None = None,
    consent_boundary_documented: bool | None = None,
    customer_beta_scope_approved: bool | None = None,
    customer_data_write_guard_ready: bool | None = None,
    support_and_rollback_owner: dict[str, Any] | None = None,
    pilot_scope_limitations_documented: bool | None = None,
    internal_demo_beta: str | None = None,
    controlled_customer_beta: str | None = None,
    source_monitoring_live: bool | None = None,
    email_delivery: bool | None = None,
    object_store_configured: bool | None = None,
) -> dict[str, Any]:
    """Report every prerequisite, and what a pilot would and would not unlock.

    `controlled_customer_pilot` is **not** a parameter. It is derived, and it is
    derived to false unless every prerequisite is satisfied — which is the
    structural rule Gates 145 through 148 applied to their own headline flags.
    """
    owner_named = bool(
        isinstance(support_and_rollback_owner, dict)
        and str(support_and_rollback_owner.get("support_contact") or "").strip()
        and str(support_and_rollback_owner.get("rollback_owner") or "").strip()
    )

    satisfied = {
        PREREQ_REAL_CUSTOMER_ORG: bool(real_customer_organization_exists),
        PREREQ_SECOND_PERSON: bool(second_person_event_complete),
        PREREQ_AUTH_LIVE: bool(customer_auth_live),
        PREREQ_VERIFIED_BINDING: bool(verified_operational_binding),
        PREREQ_CONSENT: bool(consent_boundary_documented),
        PREREQ_BETA_SCOPE: bool(customer_beta_scope_approved),
        PREREQ_WRITE_GUARD: bool(customer_data_write_guard_ready),
        PREREQ_SUPPORT_OWNER: owner_named,
        PREREQ_SCOPE_LIMITS: bool(pilot_scope_limitations_documented),
    }

    missing = [name for name in PREREQUISITES if not satisfied[name]]

    # Derived. Never supplied, and false while anything is missing.
    controlled_customer_pilot = not missing

    # The package being correct is a different fact from the pilot being live.
    activation_package_ready = True

    capabilities = {
        "source_monitoring_live": bool(source_monitoring_live),
        "email_delivery": bool(email_delivery),
        "object_store_configured": bool(object_store_configured),
        "production_rollout": False,
    }

    next_action: dict[str, Any] | None = None
    if missing:
        first = missing[0]
        next_action = {"prerequisite": first, **PREREQUISITE_OWNERS[first]}

    payload = _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            # The headline, derived.
            "controlled_customer_pilot": controlled_customer_pilot,
            "activation_package_ready": activation_package_ready,
            "package_ready_is_not_an_activated_pilot": (
                "activation_package_ready says the prerequisites are stated "
                "and measurable; controlled_customer_pilot says a pilot is "
                "running. They are different facts and both are reported."
            ),
            # The decisions, reported not computed here.
            "internal_demo_beta": internal_demo_beta or NO_GO,
            "controlled_customer_beta": controlled_customer_beta or NO_GO,
            "production_rollout": NO_GO,
            "production_is_never_computed": True,
            # The prerequisites.
            "prerequisites": list(PREREQUISITES),
            "prerequisites_satisfied": satisfied,
            "prerequisites_missing": missing,
            "prerequisite_count": len(PREREQUISITES),
            "prerequisites_satisfied_count": len(PREREQUISITES) - len(missing),
            "prerequisite_owners": {
                name: PREREQUISITE_OWNERS[name] for name in PREREQUISITES
            },
            "next_human_action": next_action,
            # What is not a prerequisite.
            "separately_gated": {
                name: {**entry, "value": capabilities.get(name, False)}
                for name, entry in SEPARATELY_GATED.items()
            },
            "separately_gated_are_not_pilot_blockers": True,
            "capabilities": capabilities,
            # What a pilot means.
            "would_unlock": list(WOULD_UNLOCK),
            "would_not_unlock": list(WOULD_NOT_UNLOCK),
            # How it would be recorded: not yet decided, and deliberately so.
            "activation_mechanism_exists": False,
            "why_no_mechanism": (
                "no table records a pilot approval, no environment flag exists, "
                "and no code path sets the value true. A switch that exists "
                "before its prerequisites do is a switch somebody flips early."
            ),
            "not_approved": list(NOT_APPROVED),
            # Constants.
            "pilot_activated_by_this_module": False,
            "approval_recorded_by_this_module": False,
            "rows_written": 0,
            "real_organization_touched": False,
            "leaked_shapes": [],
        }
    )
    payload["leaked_shapes"] = _leaked_shapes(payload)
    return payload


def checklist_invariant_failures(checklist: dict[str, Any]) -> list[str]:
    """Refuse a checklist that claims more than its evidence supports."""
    fails: list[str] = []

    if checklist.get("controlled_customer_pilot"):
        if checklist.get("prerequisites_missing"):
            fails.append("pilot_true_with_missing_prerequisites")
        for name in (
            PREREQ_REAL_CUSTOMER_ORG,
            PREREQ_AUTH_LIVE,
            PREREQ_VERIFIED_BINDING,
            PREREQ_CONSENT,
            PREREQ_BETA_SCOPE,
            PREREQ_SUPPORT_OWNER,
        ):
            if not (checklist.get("prerequisites_satisfied") or {}).get(name):
                fails.append(f"pilot_true_without:{name}")

    if checklist.get("production_rollout") != NO_GO:
        fails.append("production_rollout_is_not_no_go")

    # A capability that is not a prerequisite must never be reported as one.
    separately = checklist.get("separately_gated") or {}
    for name in SEPARATELY_GATED:
        if name in (checklist.get("prerequisites") or []):
            fails.append(f"separately_gated_capability_listed_as_prerequisite:{name}")
        if name not in separately:
            fails.append(f"separately_gated_capability_missing:{name}")

    if checklist.get("activation_mechanism_exists"):
        fails.append("an_activation_mechanism_appeared")

    for flag in (
        "pilot_activated_by_this_module",
        "approval_recorded_by_this_module",
        "real_organization_touched",
    ):
        if checklist.get(flag):
            fails.append(f"module_claimed_to_have:{flag}")

    if checklist.get("rows_written"):
        fails.append("checklist_wrote_rows")

    for name in checklist.get("leaked_shapes") or []:
        fails.append(f"leaked:{name}")

    return sorted(set(fails))
