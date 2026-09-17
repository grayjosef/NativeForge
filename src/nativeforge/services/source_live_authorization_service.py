"""The only path to a live-network decision (Gate 162H/I).

## Why this is a separate module rather than a new function on the guard

`live_network_guard_service` cannot import the resolver: the resolver imports
the fact model, and the fact model imports the guard's vocabularies. Putting
the bridge inside the guard makes that a cycle.

So the guard keeps its job — a pure decision function over named inputs — and
this module is the public runtime path that *earns* those inputs from records
before asking. `build_live_network_decision` becomes the low-level primitive it
always was; `authorize_source_for_live_access` is what runtime code calls.

## What changed about reachability

Before Gate 162, the guard's permitted branch was reachable only by handing it
ten booleans. Gate 161 measured that and called it by design, because Gate 162
was going to do it deliberately. It turned out to be worse than that: eight of
the ten inputs had no record anywhere to come from, so the only way to reach
`allowed=true` was to invent them.

Now there is exactly one way, and it runs through
`resolve_source_authorization_facts`, whose signature has no parameter capable
of asserting anything.

## The bypass this module refuses

A caller can still import `build_live_network_decision` and pass ten
affirmative strings. That call will return `allowed=true`, because it is a pure
function and that is what it is for.

What such a caller cannot do is make a live request. The permitted branch of
the guard is not the thing that opens a socket:

```text
Gate 161's transport boundary    live is not in DISPATCHABLE_KINDS
Gate 161's execution policy      refuses transport_kind=live
Gate 161's migration 0047        CHECK (transport_kind = 'hermetic')
                                 CHECK (live_source_call = 0)
this module                      returns authorized=false unless every fact
                                 is a signed record
```

So a fabricated guard decision is a fabricated *opinion*. It authorizes
nothing, it cannot be recorded, and it cannot be dispatched. `authorized_by`
on this module's output names the resolution that produced it, and a decision
with no resolution behind it fails `authorization_invariant_failures`.

## Status vocabulary

```text
approved       every fact is a signed, fresh, affirmative record
               (which is NOT the same as the guard permitting a request -
                that additionally needs a live fetch to be opted in, and
                Gate 162 opts nothing in)
denied         at least one fact is an explicit refusal
needs_review   at least one fact defers to a human who has not answered
missing_fact   at least one fact has no record at all
stale          at least one affirmative record has expired
unknown        a fact exists and does not answer
```

Reported in that precedence order, worst first, so a source blocked by a denial
is not described as merely missing a fact.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.live_network_guard_service import (
    build_live_network_decision,
    guard_invariant_failures,
)
from nativeforge.services.source_authorization_fact_model_service import (
    FACT_DENIED,
    FACT_MISSING,
    FACT_NEEDS_REVIEW,
    FACT_RECORDED,
    FACT_STALE,
    FACT_UNKNOWN,
)
from nativeforge.services.source_authorization_fact_resolver_service import (
    resolve_source_authorization_facts,
    resolver_invariant_failures,
)

SCHEMA_VERSION = "nf_source_live_authorization_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

STATUS_APPROVED = "approved"
STATUS_DENIED = "denied"
STATUS_NEEDS_REVIEW = "needs_review"
STATUS_MISSING_FACT = "missing_fact"
STATUS_STALE = "stale"
STATUS_UNKNOWN = "unknown"

AUTHORIZATION_STATUSES: tuple[str, ...] = (
    STATUS_APPROVED,
    STATUS_DENIED,
    STATUS_NEEDS_REVIEW,
    STATUS_MISSING_FACT,
    STATUS_STALE,
    STATUS_UNKNOWN,
)

#: Worst first. A source blocked by an explicit denial should not be described
#: as merely missing a fact - the two have different owners and different fixes.
STATUS_PRECEDENCE: tuple[tuple[str, str], ...] = (
    (FACT_DENIED, STATUS_DENIED),
    (FACT_STALE, STATUS_STALE),
    (FACT_NEEDS_REVIEW, STATUS_NEEDS_REVIEW),
    (FACT_MISSING, STATUS_MISSING_FACT),
    (FACT_UNKNOWN, STATUS_UNKNOWN),
)

#: Precedence is applied to DECISION facts first.
#:
#: `collector_status=not_active` and `runtime_status=not_ready` are measured
#: technical states, not anybody's decision. Letting them set
#: `authorization_status=denied` told an operator that a human had refused a
#: source when nothing of the kind had happened - so a measured shortfall is
#: reported as a blocking PREREQUISITE and the headline status reflects the
#: strongest HUMAN signal.
DECISION_STRENGTH = "recorded_decision"

#: The guard's inputs this module supplies from the resolution. Keys are the
#: guard's own parameter names; values are the fact that answers each.
GUARD_INPUT_FROM_FACT: dict[str, str] = {
    "terms_status": "terms_status",
    "activation_status": "activation_status",
    "collector_status": "collector_status",
    "robots_status": "robots_status",
    "credential_status": "credential_status",
    "rate_limit_status": "rate_limit_status",
    "user_agent_status": "user_agent_status",
    "attribution_status": "attribution_status",
}

#: Said plainly. Every one of these is a thing somebody might otherwise infer
#: from a green authorization.
NOT_IMPLIED: tuple[str, ...] = (
    "an authorized source is not a called source",
    "an authorized source has no live transport to be called with",
    "authorization is per-source and is not a global switch",
    "a fabricated guard decision authorizes nothing and cannot be dispatched",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def authorize_source_for_live_access(
    *,
    connection: Any = None,
    organization_id: Any = None,
    source_id: Any = None,
    purpose: str = "source_collection",
    method: str = "GET",
    now: Any = None,
) -> dict[str, Any]:
    """Resolve the facts, then ask the guard. The only runtime path.

    Six parameters. `purpose` and `method` describe the REQUEST being
    contemplated, not the source's standing - the guard uses them to decide
    which requirements apply. None of the six can assert a fact about whether
    the source is permitted.
    """
    resolution = resolve_source_authorization_facts(
        connection=connection,
        organization_id=organization_id,
        source_id=source_id,
        now=now,
    )
    failures = list(resolver_invariant_failures(resolution))

    facts = resolution.get("resolved_facts") or {}

    # ---- the status, by precedence over DECISION facts ------------------
    statuses = {name: fact.get("fact_status") for name, fact in facts.items()}
    strengths = resolution.get("derivation_strengths") or {}

    decision_statuses = {
        name: fact.get("fact_status")
        for name, fact in facts.items()
        if strengths.get(name) == DECISION_STRENGTH
    }
    other_statuses = {
        name: fact.get("fact_status")
        for name, fact in facts.items()
        if strengths.get(name) != DECISION_STRENGTH
    }

    status = STATUS_APPROVED
    denial_is_a_decision = False
    for fact_status, mapped in STATUS_PRECEDENCE:
        if fact_status in decision_statuses.values():
            status = mapped
            denial_is_a_decision = fact_status == FACT_DENIED
            break
    else:
        # No decision fact blocks. Anything left is a technical prerequisite,
        # and `missing_fact` is the honest headline for one - nobody refused
        # this source, the platform is not ready to collect from it.
        for fact_status, mapped in STATUS_PRECEDENCE:
            if fact_status in other_statuses.values():
                status = (
                    STATUS_MISSING_FACT if mapped == STATUS_DENIED else mapped
                )
                break

    blocking_decisions = sorted(
        f"{name}:{value}"
        for name, value in decision_statuses.items()
        if value != FACT_RECORDED
    )
    blocking_prerequisites = sorted(
        f"{name}:{value}"
        for name, value in other_statuses.items()
        if value != FACT_RECORDED
    )
    refusal_reasons = sorted(blocking_decisions + blocking_prerequisites)

    # ---- the guard, fed ONLY resolved values ---------------------------
    #
    # A fact that is not `recorded` contributes None, and the guard refuses on
    # its own terms. Passing a permitting default for an unresolved fact is the
    # single thing this module exists to prevent.
    guard_kwargs: dict[str, Any] = {}
    for guard_input, fact_name in GUARD_INPUT_FROM_FACT.items():
        fact = facts.get(fact_name) or {}
        guard_kwargs[guard_input] = (
            fact.get("value") if fact.get("fact_status") == FACT_RECORDED else None
        )

    registry_row_url = None
    for fact in facts.values():
        if fact.get("fact_name") == "source_registered":
            registry_row_url = fact.get("evidence_ref")
            break

    guard_decision = build_live_network_decision(
        purpose=purpose,
        target_url=registry_row_url,
        caller="source_live_authorization_service",
        source_id=source_id,
        method=method,
        # Hardcoded False. This gate opts nothing in, and the parameter exists
        # so that Gate 163 has to change code rather than pass an argument.
        allow_live_fetch=False,
        **guard_kwargs,
    )
    failures.extend(guard_invariant_failures(guard_decision))

    authorized = bool(status == STATUS_APPROVED)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "source_id": resolution.get("source_id"),
            # ---- the per-question answers -----------------------------
            "terms_decision": statuses.get("terms_status"),
            "human_review_decision": statuses.get("human_review_status"),
            "activation_decision": statuses.get("activation_status"),
            "attribution_decision": statuses.get("attribution_status"),
            "runtime_decision": statuses.get("runtime_status"),
            "robots_decision": statuses.get("robots_status"),
            # ---- the verdict -------------------------------------------
            "authorization_status": status,
            "authorized": authorized,
            "refusal_reasons": refusal_reasons,
            # A human said no, versus the platform is not ready. Same effect on
            # permission, entirely different owner and fix.
            "denial_is_a_decision": denial_is_a_decision,
            "blocking_decisions": blocking_decisions,
            "blocking_prerequisites": blocking_prerequisites,
            "evidence_refs": sorted(
                str(fact.get("evidence_ref"))
                for fact in facts.values()
                if fact.get("evidence_ref")
            ),
            # Names the resolution this verdict came from. A decision with no
            # resolution behind it fails the invariant checker.
            "authorized_by": resolution.get("schema_version"),
            "resolution": resolution,
            "guard_decision": guard_decision,
            "guard_allowed": bool(guard_decision.get("allowed")),
            "guard_inputs_supplied": sorted(guard_kwargs),
            "guard_inputs_withheld": sorted(
                name for name, value in guard_kwargs.items() if value is None
            ),
            # ---- what is still not permitted ---------------------------
            #
            # Hardcoded False regardless of authorization. Gate 161 built no
            # live transport, so there is nothing for an authorized source to
            # be called with, and authorization and capability are separate
            # questions.
            "live_transport_permitted": False,
            "why_live_transport_stays_refused": (
                "Gate 161's boundary has no live implementation and `live` is "
                "not in DISPATCHABLE_KINDS. An authorized source still has "
                "nothing to be called with."
            ),
            "not_implied": list(NOT_IMPLIED),
            "invariant_failures": sorted(set(failures)),
            "live_source_call": False,
            "network_calls": 0,
            "source_monitoring_live": False,
        }
    )


def authorization_invariant_failures(decision: dict[str, Any]) -> list[str]:
    """Refuse an authorization that outran its evidence."""
    fails: list[str] = list(decision.get("invariant_failures") or [])

    status = decision.get("authorization_status")
    if status not in AUTHORIZATION_STATUSES:
        fails.append(f"authorization_status_outside_vocabulary:{status}")

    authorized = bool(decision.get("authorized"))
    if authorized != (status == STATUS_APPROVED):
        fails.append("authorized_disagrees_with_authorization_status")

    # A refusal must name what it is waiting on.
    if not authorized and not decision.get("refusal_reasons"):
        fails.append("a_refusal_that_names_no_reason")

    # `denied` must mean somebody decided no. A technical shortfall reported as
    # a denial tells an operator to go and argue with a reviewer who never
    # said anything.
    if status == STATUS_DENIED and not decision.get("denial_is_a_decision"):
        fails.append("denied_without_a_recorded_denial")
    if decision.get("denial_is_a_decision") and status != STATUS_DENIED:
        fails.append("a_recorded_denial_not_reported_as_denied")
    if authorized and decision.get("refusal_reasons"):
        fails.append("authorized_alongside_refusal_reasons")

    # THE invariant of this module: an authorization must come from a
    # resolution. A verdict with no resolution behind it is an opinion.
    resolution = decision.get("resolution") or {}
    if authorized and not resolution.get("resolved_facts"):
        fails.append("authorized_with_no_resolved_facts")
    if authorized and not decision.get("authorized_by"):
        fails.append("authorized_without_naming_the_resolution")
    if authorized and not resolution.get("authorization_ready"):
        fails.append("authorized_while_the_resolver_said_not_ready")

    # The resolver's own verdict and this one must agree, both directions.
    if bool(resolution.get("authorization_ready")) != authorized:
        fails.append("authorization_disagrees_with_the_resolver")

    # A withheld guard input must never have been supplied a permitting
    # default. Measured by checking the guard actually refused whenever any
    # input was withheld.
    withheld = decision.get("guard_inputs_withheld") or []
    if withheld and decision.get("guard_allowed"):
        fails.append(
            f"the_guard_allowed_with_{len(withheld)}_inputs_withheld"
        )

    # The implication runs ONE WAY.
    #
    # `authorized` means every required fact is a signed, fresh record.
    # `guard_allowed` means that AND somebody opted this request in to a live
    # fetch. Gate 162 opts nothing in, so a fully authorized source sits at
    # `guard_allowed=false` with `live_fetch_not_opted_in` - which is correct,
    # and was the assertion my own probe got backwards.
    #
    # The reverse would be a breach: the guard permitting a request for a
    # source whose facts do not authorize it.
    if decision.get("guard_allowed") and not authorized:
        fails.append("the_guard_allowed_an_unauthorized_source")

    # Gate 162 permits no live transport, authorized or not.
    if decision.get("live_transport_permitted"):
        fails.append("the_authorization_permitted_a_live_transport")
    for flag in ("live_source_call", "source_monitoring_live"):
        if decision.get(flag):
            fails.append(f"authorization_claimed:{flag}")
    if int(decision.get("network_calls") or 0):
        fails.append("the_authorization_counted_a_network_call")

    if not decision.get("not_implied"):
        fails.append("the_authorization_did_not_say_what_it_does_not_imply")

    return sorted(set(fails))
