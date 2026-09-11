"""Gate 145B: can a controlled customer beta start, and under what constraints?

## Three scopes, decided separately

```text
internal_demo_beta        operators, the demo organization, fixture rows
controlled_customer_beta  a real person, a real organization, real data
production_rollout        everyone
```

A single "are we ready" answer would be useless, because the three differ not in
how much software works but in **who is on the other side**. Everything the
first scope needs is built; the second needs two human decisions and a consent
boundary nobody has written; the third needs both of those and an owner saying
yes.

## The four conflations this module exists to prevent

Each pair reads as the same thing to anyone who has not followed the gates, and
each is the difference between a true statement and a false one:

```text
email_delivery_readiness         !=  email_delivery
source_monitoring_preflight_ready !=  source_monitoring_live
document_metadata_operational    !=  document_body_storage_ready
customer_persistence_live        !=  customer_auth_live
```

plus a fifth that is about identity rather than capability:

```text
the demo organization            !=  a customer organization
```

`CONFLATIONS` names all five, every decision reports them, and an invariant
fails if a decision ever rests on one.

## Production is NO_GO, and not because something is missing

`production_rollout` has no branch that returns anything else. Production is not
the sum of the technical gates; it is those gates **and** a decision nobody has
made. A service that could compute its way to GO would be a service that had
mistaken one for the other.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_controlled_beta_readiness_decision_v1"

GO = "GO"
LIMITED_GO = "LIMITED_GO"
NO_GO = "NO_GO"

DECISIONS: tuple[str, ...] = (GO, LIMITED_GO, NO_GO)

INTERNAL_DEMO_BETA = "internal_demo_beta"
CONTROLLED_CUSTOMER_BETA = "controlled_customer_beta"
PRODUCTION_ROLLOUT = "production_rollout"

SCOPES: tuple[str, ...] = (
    INTERNAL_DEMO_BETA,
    CONTROLLED_CUSTOMER_BETA,
    PRODUCTION_ROLLOUT,
)

#: The scope that may never be GO. Not because something is missing - because
#: production is a decision and not a computation.
NEVER_GO_SCOPES: frozenset[str] = frozenset({PRODUCTION_ROLLOUT})

#: The scope that may never be unconditionally GO while a real person has not
#: signed in and a real organization is not bound.
NEVER_UNCONDITIONAL_GO_SCOPES: frozenset[str] = frozenset({CONTROLLED_CUSTOMER_BETA})

#: What the internal demo beta requires. Every one is measured by a verifier.
INTERNAL_DEMO_CONDITIONS: tuple[str, ...] = (
    "login_live",
    "customer_persistence_live",
    "awarded_operational_tracking",
    "tenant_digest_operational",
    "document_metadata_operational",
    "email_delivery_readiness",
    "source_monitoring_preflight_ready",
    "beta_onboarding_cockpit_route_live",
)

#: What must be FALSE for the internal demo beta to be honest. A demo that had
#: quietly switched one of these on would not be a demo.
INTERNAL_DEMO_MUST_BE_FALSE: tuple[str, ...] = (
    "source_monitoring_live",
    "email_delivery",
    "object_store_configured",
    "customer_auth_live",
    "verified_operational_binding",
    "controlled_customer_pilot",
    "production_rollout",
)

#: What a controlled customer beta needs beyond the internal one. None is a
#: code change.
CUSTOMER_BETA_CONDITIONS: tuple[str, ...] = (
    "customer_auth_live",
    "verified_operational_binding",
    "consent_and_data_boundary_documented",
    "customer_beta_scope_approved",
)

#: The five things that must never be treated as one another.
CONFLATIONS: tuple[dict[str, str], ...] = (
    {
        "readiness": "email_delivery_readiness",
        "capability": "email_delivery",
        "difference": (
            "a digest can be rendered, a recipient validated and an intent "
            "recorded - and no mail has anywhere to go"
        ),
    },
    {
        "readiness": "source_monitoring_preflight_ready",
        "capability": "source_monitoring_live",
        "difference": (
            "every source can be evaluated and classified - and none is "
            "cleared for collection, because nobody has read their terms"
        ),
    },
    {
        "readiness": "document_metadata_operational",
        "capability": "document_body_storage_ready",
        "difference": (
            "a document reference records and reads back - and its bytes have "
            "nowhere to live"
        ),
    },
    {
        "readiness": "customer_persistence_live",
        "capability": "customer_auth_live",
        "difference": (
            "rows persist against an organization - and no second real person "
            "has ever signed in"
        ),
    },
    {
        "readiness": "the demo organization",
        "capability": "a customer organization",
        "difference": (
            "bbbbbbbb-... is a demo org with fixture-labelled rows; treating it "
            "as a customer org is the substitution Gates 110-113 prevented"
        ),
    },
)

#: Sentences somebody could reasonably say after reading a green cockpit, each
#: of which is false today. Named so they can be refused rather than discovered.
UNSAFE_CLAIMS: tuple[dict[str, str], ...] = (
    {
        "claim": "we monitor grant sources for you",
        "why_unsafe": "source_monitoring_live is false; zero sources are cleared",
        "true_statement": (
            "every source in the registry can be evaluated, and none has been "
            "cleared for collection"
        ),
    },
    {
        "claim": "you will get a weekly digest by email",
        "why_unsafe": "email_delivery is false; no provider exists",
        "true_statement": (
            "a weekly digest can be previewed in the product, and nothing is "
            "sent anywhere"
        ),
    },
    {
        "claim": "upload your award documents",
        "why_unsafe": "document body storage is not configured",
        "true_statement": (
            "a document reference can be recorded; its bytes are not stored"
        ),
    },
    {
        "claim": "sign your team in",
        "why_unsafe": "customer_auth_live is false",
        "true_statement": (
            "one owner identity signs in through Google; a second person has "
            "not yet accepted an invite"
        ),
    },
    {
        "claim": "your data is in our system",
        "why_unsafe": "no real customer data is written anywhere",
        "true_statement": "the demo organization holds fixture-labelled rows",
    },
    {
        "claim": "we cover N grant sources",
        "why_unsafe": (
            "the registry lists 177 sources and covers none of them; a catalogue "
            "is not coverage"
        ),
        "true_statement": "177 sources are catalogued and none is monitored",
    },
    {
        "claim": "a 65% improvement in anything",
        "why_unsafe": (
            "never measured, not measurable from this system, and this campaign "
            "has refused it at every gate"
        ),
        "true_statement": "no improvement figure is claimed",
    },
)

#: Decisions a person makes. No code change moves any of them.
HUMAN_APPROVALS: tuple[dict[str, str], ...] = (
    {
        "approval": "a second real person accepts a real invite",
        "unlocks": "customer_auth_live",
        "owner": "the organization owner, and the person invited",
        "why_not_automatable": (
            "Gate 136 built the path and refused to fake the person; an invite "
            "accepted by nobody is not an invite"
        ),
    },
    {
        "approval": "the two-part verified operational binding decision",
        "unlocks": "verified_operational_binding",
        "owner": "the owner",
        "why_not_automatable": "Gate 137 made it a decision on purpose",
    },
    {
        "approval": "a documented consent and data boundary",
        "unlocks": "real customer data",
        "owner": "the owner, with whoever advises on data handling",
        "why_not_automatable": (
            "Gate 142 named this gap and did not fill it: nothing in this "
            "repository records that a tenant asked for anything"
        ),
    },
    {
        "approval": "a terms review per source",
        "unlocks": "source_monitoring_live",
        "owner": "a human reading each publisher's terms",
        "why_not_automatable": (
            "171 sources are UNKNOWN and 6 served no policy text at all; "
            "'we could not read them' is not permission"
        ),
    },
    {
        "approval": "an email provider choice and a send activation",
        "unlocks": "email_delivery",
        "owner": "the owner",
        "why_not_automatable": (
            "Gate 142's preflight refuses an activation setting that arrives "
            "without an approval"
        ),
    },
    {
        "approval": "an object store choice and an external verification",
        "unlocks": "object_store_configured",
        "owner": "the owner",
        "why_not_automatable": (
            "five settings being filled in and five settings reaching a bucket "
            "that accepts writes are different claims"
        ),
    },
    {
        "approval": "the controlled customer pilot decision",
        "unlocks": "controlled_customer_pilot",
        "owner": "Mayhem",
        "why_not_automatable": "it is a business decision about real people",
    },
    {
        "approval": "the production rollout decision",
        "unlocks": "production_rollout",
        "owner": "Mayhem",
        "why_not_automatable": (
            "production is not the sum of the technical gates; it is those "
            "gates and somebody saying yes"
        ),
    },
)

#: Things a later gate can build. Separate from the approvals above, because an
#: operator reading a blocker needs to know whether to write code or to decide.
TECHNICAL_BLOCKERS: tuple[dict[str, str], ...] = (
    {
        "blocker": "five scheduler components absent",
        "blocks": "source_monitoring_live",
        "detail": (
            "background worker, periodic trigger, persistent backend, "
            "production raw payload store, scheduler runtime"
        ),
    },
    {
        "blocker": "no email delivery service module",
        "blocks": "email_delivery",
        "detail": "tenant_beta_readiness_service already looks for one",
    },
    {
        "blocker": "no object storage client",
        "blocks": "object_store_configured",
        "detail": "no SDK is installed and this campaign added none",
    },
    {
        "blocker": "no digest persistence table",
        "blocks": "auditing a digest after a missed deadline",
        "detail": (
            "delivery intents are persisted and name a digest nobody kept; "
            "nf_tenant_digest_records does not exist"
        ),
    },
    {
        "blocker": "no consent record model",
        "blocks": "real customer data",
        "detail": "named in Gate 142, deliberately not filled",
    },
    {
        "blocker": "robots.txt never fetched",
        "blocks": "source_monitoring_live",
        "detail": "unknown is not in ROBOTS_SATISFYING, so it blocks",
    },
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _decision(
    scope: str,
    *,
    decision: str,
    conditions_met: list[str],
    conditions_missing: list[str],
    blockers: list[str],
    constraints: list[str],
    summary: str,
) -> dict[str, Any]:
    return {
        "scope": scope,
        "decision": decision,
        "conditions_met": sorted(set(conditions_met)),
        "conditions_missing": sorted(set(conditions_missing)),
        "blockers": sorted(set(blockers)),
        "constraints": list(constraints),
        "summary": summary,
    }


def build_controlled_beta_decision(
    *,
    login_live: bool | None = None,
    customer_persistence_live: bool | None = None,
    awarded_operational_tracking: bool | None = None,
    tenant_digest_operational: bool | None = None,
    document_metadata_operational: bool | None = None,
    email_delivery_readiness: bool | None = None,
    source_monitoring_preflight_ready: bool | None = None,
    beta_onboarding_cockpit_route_live: bool | None = None,
    customer_auth_live: bool | None = None,
    verified_operational_binding: bool | None = None,
    consent_and_data_boundary_documented: bool | None = None,
    customer_beta_scope_approved: bool | None = None,
) -> dict[str, Any]:
    """Three decisions, from measured facts. Activates and approves nothing.

    Every parameter is supplied by a caller that measured it. Absent evidence is
    absent - false, never optimistic - and a scope whose conditions are not
    established does not get the benefit of the doubt.
    """
    from nativeforge.services.document_storage_readiness_service import (
        build_document_storage_readiness,
    )
    from nativeforge.services.email_provider_configuration_preflight_service import (
        build_email_provider_preflight,
    )
    from nativeforge.services.source_scheduler_readiness_service import (
        build_scheduler_readiness,
    )

    # -- the capability flags, measured here and not taken on trust ---------
    storage = build_document_storage_readiness(metadata_route_smoke=None)
    email = build_email_provider_preflight()
    scheduler = build_scheduler_readiness()

    measured = {
        "source_monitoring_live": bool(scheduler.get("source_monitoring_live")),
        "email_delivery": bool(email.get("email_delivery")),
        "object_store_configured": bool(storage.get("object_store_configured")),
        "document_body_storage_ready": bool(storage.get("document_body_storage_ready")),
        # These two are human decisions, and no service can measure them true.
        "customer_auth_live": bool(customer_auth_live),
        "verified_operational_binding": bool(verified_operational_binding),
        "controlled_customer_pilot": False,
        "production_rollout": False,
    }

    supplied = {
        "login_live": bool(login_live),
        "customer_persistence_live": bool(customer_persistence_live),
        "awarded_operational_tracking": bool(awarded_operational_tracking),
        "tenant_digest_operational": bool(tenant_digest_operational),
        "document_metadata_operational": bool(document_metadata_operational),
        "email_delivery_readiness": bool(email_delivery_readiness),
        "source_monitoring_preflight_ready": bool(source_monitoring_preflight_ready),
        "beta_onboarding_cockpit_route_live": bool(beta_onboarding_cockpit_route_live),
    }

    # -- internal / demo beta ------------------------------------------------
    demo_met = [name for name in INTERNAL_DEMO_CONDITIONS if supplied.get(name)]
    demo_missing = [name for name in INTERNAL_DEMO_CONDITIONS if not supplied.get(name)]
    # Two kinds, and only the first propagates.
    #
    # A condition failure means the software does not work, which is true for
    # every scope. A demo-scope honesty violation means a capability is on that
    # a DEMO must not have - and the customer scope requires two of those same
    # flags to be on. Propagating them made the customer beta return GO
    # carrying blockers that said its own conditions must be false.
    demo_condition_blockers = [f"condition_not_met:{name}" for name in demo_missing]
    dishonest = [name for name in INTERNAL_DEMO_MUST_BE_FALSE if measured.get(name)]
    demo_honesty_blockers = [f"must_be_false_but_is_true:{name}" for name in dishonest]
    demo_blockers = demo_condition_blockers + demo_honesty_blockers

    if not demo_missing and not dishonest:
        demo_decision = GO
        demo_summary = (
            "every lane an internal operator needs is proved, in the demo "
            "organization, with fixture-labelled rows and every capability "
            "flag honestly false"
        )
    elif demo_met:
        demo_decision = LIMITED_GO
        demo_summary = (
            "some lanes are proved and some are not; the unproved ones are "
            "named rather than assumed"
        )
    else:
        demo_decision = NO_GO
        demo_summary = "no lane was proved by this run"

    demo_constraints = [
        "demo organization only (bbbbbbbb-cccc-dddd-eeee-ffffffffffff)",
        "fixture-labelled rows only",
        "no real customer data",
        "digest is preview_only; nothing is sent",
        "no source is monitored and none is cleared for collection",
        "document references only; no bytes are stored",
    ]

    # -- controlled customer beta --------------------------------------------
    customer_inputs = {
        "customer_auth_live": measured["customer_auth_live"],
        "verified_operational_binding": measured["verified_operational_binding"],
        "consent_and_data_boundary_documented": bool(
            consent_and_data_boundary_documented
        ),
        "customer_beta_scope_approved": bool(customer_beta_scope_approved),
    }
    customer_met = [n for n in CUSTOMER_BETA_CONDITIONS if customer_inputs.get(n)]
    customer_missing = [
        n for n in CUSTOMER_BETA_CONDITIONS if not customer_inputs.get(n)
    ]
    customer_blockers = [f"approval_absent:{name}" for name in customer_missing]
    # Condition failures only. The demo scope's honesty conditions are the
    # opposite of this scope's requirements on the same two flags.
    customer_blockers.extend(demo_condition_blockers)

    if demo_decision == NO_GO:
        customer_decision = NO_GO
        customer_summary = (
            "the internal beta is not established, so a customer beta cannot be"
        )
    elif customer_missing:
        # LIMITED_GO, not NO_GO: the software works. What is missing is a
        # person's decision, and naming it as a blocker rather than a failure
        # is the difference between "fix this" and "decide this".
        customer_decision = LIMITED_GO
        customer_summary = (
            "the software supports a controlled beta in the demo organization; "
            "a REAL customer beta needs decisions no code change can make"
        )
    else:
        customer_decision = GO
        customer_summary = (
            "every condition including the human approvals is established"
        )

    customer_constraints = [
        "demo organization scope only, until verified_operational_binding",
        "no real customer data until a consent and data boundary is documented",
        "no email is sent under any scope",
        "no live source is monitored under any scope",
        "no document bytes are stored under any scope",
        "every product surface must avoid the unsafe claims listed here",
    ]

    # -- production rollout ---------------------------------------------------
    production_blockers = [f"approval_absent:{n}" for n in customer_missing]
    production_blockers.extend(demo_condition_blockers)
    production_blockers.extend(
        [
            "approval_absent:production_rollout_decision",
            "capability_absent:source_monitoring_live",
            "capability_absent:email_delivery",
            "capability_absent:object_store_configured",
        ]
    )
    production = _decision(
        PRODUCTION_ROLLOUT,
        decision=NO_GO,
        conditions_met=[],
        conditions_missing=["production_rollout_decision"],
        blockers=production_blockers,
        constraints=["not approved, and this service cannot approve it"],
        summary=(
            "production is not the sum of the technical gates; it is those "
            "gates and somebody saying yes, and nobody has"
        ),
    )

    decisions = {
        INTERNAL_DEMO_BETA: _decision(
            INTERNAL_DEMO_BETA,
            decision=demo_decision,
            conditions_met=demo_met,
            conditions_missing=demo_missing,
            blockers=demo_blockers,
            constraints=demo_constraints,
            summary=demo_summary,
        ),
        CONTROLLED_CUSTOMER_BETA: _decision(
            CONTROLLED_CUSTOMER_BETA,
            decision=customer_decision,
            conditions_met=customer_met,
            conditions_missing=customer_missing,
            blockers=customer_blockers,
            constraints=customer_constraints,
            summary=customer_summary,
        ),
        PRODUCTION_ROLLOUT: production,
    }

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scopes": list(SCOPES),
            "decisions": list(DECISIONS),
            "by_scope": decisions,
            "internal_demo_beta": demo_decision,
            "controlled_customer_beta": customer_decision,
            "production_rollout": NO_GO,
            "measured_capabilities": measured,
            "supplied_readiness": supplied,
            "conflations": [dict(c) for c in CONFLATIONS],
            "unsafe_claims": [dict(c) for c in UNSAFE_CLAIMS],
            "human_approvals": [dict(a) for a in HUMAN_APPROVALS],
            "technical_blockers": [dict(b) for b in TECHNICAL_BLOCKERS],
            # Constants. No branch sets any of them.
            "controlled_customer_pilot_activated": False,
            "production_approved": False,
            "customer_auth_live": measured["customer_auth_live"],
            "source_monitoring_live": measured["source_monitoring_live"],
            "email_delivery": measured["email_delivery"],
            "object_store_configured": measured["object_store_configured"],
            "live_source_calls": 0,
            "emails_sent": 0,
            "object_store_calls": 0,
            "collectors_activated": 0,
            "real_customer_data_written": False,
            "real_organization_touched": False,
            "customer_names_reported": False,
            "improvement_claims": [],
        }
    )


def decision_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of a controlled beta decision."""
    fails: list[str] = []

    by_scope = result.get("by_scope") or {}
    for scope in SCOPES:
        if scope not in by_scope:
            fails.append(f"scope_missing:{scope}")

    for scope, entry in by_scope.items():
        if entry.get("decision") not in DECISIONS:
            fails.append(f"decision_not_recognised:{scope}:{entry.get('decision')}")
        if entry.get("decision") == GO and entry.get("blockers"):
            fails.append(f"go_alongside_blockers:{scope}")
        if entry.get("decision") != GO and not entry.get("blockers"):
            fails.append(f"not_go_with_no_blocker:{scope}")
        if not entry.get("constraints"):
            fails.append(f"decision_without_constraints:{scope}")

    # The two load-bearing rules.
    for scope in NEVER_GO_SCOPES:
        if (by_scope.get(scope) or {}).get("decision") != NO_GO:
            fails.append(f"a_never_go_scope_was_not_no_go:{scope}")
    for scope in NEVER_UNCONDITIONAL_GO_SCOPES:
        entry = by_scope.get(scope) or {}
        if entry.get("decision") == GO and not result.get("customer_auth_live"):
            fails.append(f"unconditional_go_without_customer_auth:{scope}")

    # The conflations. A decision resting on one is the failure this module
    # exists to prevent.
    measured = result.get("measured_capabilities") or {}
    supplied = result.get("supplied_readiness") or {}
    for readiness, capability in (
        ("email_delivery_readiness", "email_delivery"),
        ("source_monitoring_preflight_ready", "source_monitoring_live"),
        ("document_metadata_operational", "document_body_storage_ready"),
        ("customer_persistence_live", "customer_auth_live"),
    ):
        if supplied.get(readiness) and measured.get(capability):
            # Not an error in itself - but it must have been measured, never
            # inferred from the readiness flag beside it.
            if capability in ("email_delivery", "source_monitoring_live"):
                fails.append(f"a_readiness_flag_implied_a_capability:{capability}")

    if len(result.get("conflations") or []) != len(CONFLATIONS):
        fails.append("the_conflation_list_lost_entries")
    if len(result.get("unsafe_claims") or []) != len(UNSAFE_CLAIMS):
        fails.append("the_unsafe_claim_list_lost_entries")
    if not result.get("human_approvals"):
        fails.append("no_human_approvals_were_listed")
    if not result.get("technical_blockers"):
        fails.append("no_technical_blockers_were_listed")

    for field in (
        "controlled_customer_pilot_activated",
        "production_approved",
        "real_customer_data_written",
        "real_organization_touched",
        "customer_names_reported",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")
    for field in (
        "live_source_calls",
        "emails_sent",
        "object_store_calls",
        "collectors_activated",
    ):
        if result.get(field):
            fails.append(f"nonzero:{field}")
    if result.get("improvement_claims"):
        fails.append("an_improvement_figure_was_claimed")

    if result.get("production_rollout") != NO_GO:
        fails.append(
            f"production_rollout_was_not_no_go:{result.get('production_rollout')}"
        )

    return fails
