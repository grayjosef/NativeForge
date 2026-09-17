"""The execution policy (Gate 161D).

## This composes Gate 94B's guard. It does not re-decide.

`live_network_guard_service.build_live_network_decision` already owns the live
question: deny by default, requirements derived from `purpose` and
`collector_type`, no input that means "skip this one". Writing a second set of
those rules here would give the codebase two answers to one question, and the
Gate 93 defect this campaign keeps citing is exactly a caller deciding for
itself what it needed.

So the live verdict is **the guard's verdict, unmodified**. This module adds one
thing the guard has no opinion about: whether a HERMETIC transport may run.

```text
live_transport_allowed      = the guard said allowed        (currently false)
hermetic_transport_allowed  = the scope is controlled dev/demo AND the source
                              is a synthetic fixture
execution_allowed           = one of the two is allowed
```

## Hermetic permission is not a weaker live permission

A hermetic execution reads registered bytes. It contacts nothing, so terms,
robots, activation and credentials are not what gates it — asking whether a
fixture has cleared `TERMS_REVIEW_REQUIRED` is the same category error the guard
names for a JWKS URL.

What gates it instead is that the source really is synthetic. A hermetic
execution against a REAL source definition would produce evidence labelled as
if it came from that source, and Gate 160's store cannot tell the difference. So
`hermetic_transport_allowed` requires `is_synthetic_fixture`, and a real
`source_id` is refused by name.

That is the one place this gate could quietly go wrong, and it is the reason
that check exists rather than trusting callers to pass fixtures.

## Nothing here infers approval

Explicitly not treated as permission, each named so a reader can check:

```text
the source exists in the registry     177 do; none is approved
the scheduler judged it eligible      eligibility is not approval
a job is queued                       a queue is a plan
a job is claimed                      a claim is not a grant
a source URL is known                 knowing where is not being allowed
an adapter exists for it              capability is not permission
```

Gate 156 established that list for the scheduler. It applies here unchanged,
because the thing being decided is the same thing.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.live_network_guard_service import (
    build_live_network_decision,
    guard_invariant_failures,
)
from nativeforge.services.source_collection_transport_service import (
    HERMETIC,
    LIVE,
    TRANSPORT_KINDS,
)

SCHEMA_VERSION = "nf_source_collection_execution_policy_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: The scope in which a hermetic execution may run at all. A production scope
#: has no business running fixtures against source definitions.
HERMETIC_SCOPES: frozenset[str] = frozenset({"controlled_dev_demo"})

#: Refused by name, as every gate in this block does.
REAL_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

#: Things that are NOT permission. Named so the refusal can cite one.
NOT_PERMISSION: tuple[str, ...] = (
    "the source exists in the registry",
    "the scheduler judged it eligible",
    "a job is queued",
    "a job is claimed",
    "a source URL is known",
    "an adapter exists for it",
    "a collector module is importable",
)

BLOCK_NOT_SYNTHETIC = "hermetic_execution_requires_a_synthetic_fixture_source"
BLOCK_SCOPE = "hermetic_execution_is_not_permitted_in_this_scope"
BLOCK_REAL_ORG = "real_organization_refused_by_name"
BLOCK_NO_SOURCE = "no_source_id_supplied"
BLOCK_LIVE_REFUSED = "the_live_network_guard_refused"
BLOCK_NO_KIND = "no_transport_kind_requested"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def build_execution_policy(
    *,
    source_id: Any = None,
    organization_id: Any = None,
    is_synthetic_fixture: bool = False,
    scope: str = CONTROLLED_SCOPE,
    transport_kind: str = HERMETIC,
    # ---- everything below is handed straight to the guard ---------------
    activation_status: Any = None,
    terms_status: Any = None,
    human_review_state: Any = None,
    collector_status: Any = None,
    collector_type: Any = None,
    robots_status: Any = None,
    credential_status: Any = None,
    rate_limit_status: Any = None,
    attribution_status: Any = None,
    user_agent_status: Any = None,
    allow_live_fetch: bool = False,
    target_url: Any = None,
    caller: str = "source_collection_execution_envelope",
) -> dict[str, Any]:
    """May this execution run, and with which transport?"""
    source = str(source_id or "").strip()
    kind = str(transport_kind or "").strip()

    blocked: list[str] = []
    if not source:
        blocked.append(BLOCK_NO_SOURCE)
    if str(organization_id or "").strip().lower() == REAL_ORGANIZATION_ID:
        blocked.append(BLOCK_REAL_ORG)
    if kind not in TRANSPORT_KINDS:
        blocked.append(f"transport_kind_outside_vocabulary:{kind or 'none'}")

    # ---- the live question, answered by the guard ----------------------
    #
    # Handed through unmodified. Whatever the guard decides is the answer; this
    # module neither softens nor re-derives it.
    guard = build_live_network_decision(
        purpose="source_collection",
        target_url=target_url,
        caller=caller,
        source_id=source or None,
        method="GET",
        allow_live_fetch=bool(allow_live_fetch),
        terms_status=terms_status,
        activation_status=activation_status,
        collector_status=collector_status,
        robots_status=robots_status,
        credential_status=credential_status,
        rate_limit_status=rate_limit_status,
        user_agent_status=user_agent_status,
        attribution_status=attribution_status,
        collector_type=collector_type,
    )
    guard_failures = guard_invariant_failures(guard)
    live_allowed = bool(guard.get("allowed"))

    # ---- the hermetic question, which the guard has no opinion about ---
    hermetic_blocked: list[str] = []
    if str(scope) not in HERMETIC_SCOPES:
        hermetic_blocked.append(f"{BLOCK_SCOPE}:{scope}")
    if not is_synthetic_fixture:
        # THE check that keeps this gate honest. A hermetic execution against
        # a real source definition would produce evidence labelled as if it
        # came from that source, and Gate 160's store cannot tell.
        hermetic_blocked.append(BLOCK_NOT_SYNTHETIC)
    if str(organization_id or "").strip().lower() == REAL_ORGANIZATION_ID:
        hermetic_blocked.append(BLOCK_REAL_ORG)

    hermetic_allowed = not hermetic_blocked and not blocked

    if kind == LIVE and not live_allowed:
        blocked.append(BLOCK_LIVE_REFUSED)
    if kind == HERMETIC and hermetic_blocked:
        blocked.extend(hermetic_blocked)

    execution_allowed = (
        (kind == HERMETIC and hermetic_allowed)
        or (kind == LIVE and live_allowed)
    ) and not blocked

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": str(scope),
            "execution_allowed": execution_allowed,
            "transport_kind_requested": kind or None,
            # The two verdicts, separately, so a caller can see which door is
            # open without inferring it from the other.
            "live_transport_allowed": live_allowed,
            "hermetic_transport_allowed": hermetic_allowed,
            "refusal_reasons": sorted(set(blocked)),
            "hermetic_refusal_reasons": sorted(set(hermetic_blocked)),
            # ---- the guard's own answer, carried verbatim ---------------
            "guard_decision_status": guard.get("decision_status"),
            "guard_allowed": live_allowed,
            "guard_blocked_reasons": guard.get("blocked_reasons") or [],
            "guard_invariant_failures": guard_failures,
            "guard_purpose": "source_collection",
            # ---- what is NOT permission --------------------------------
            "not_permission": list(NOT_PERMISSION),
            "source_id": source or None,
            "is_synthetic_fixture": bool(is_synthetic_fixture),
            # ---- the standing boundary ---------------------------------
            "approved_source_count": 0,
            "live_transport_implemented": False,
            "collectors_invoked": 0,
            "live_source_calls": 0,
            "source_monitoring_live": False,
        }
    )


def execution_policy_invariant_failures(policy: dict[str, Any]) -> list[str]:
    """Refuse a verdict that contradicts itself or the guard."""
    fails: list[str] = list(policy.get("guard_invariant_failures") or [])

    # THE invariant of Gate 161.
    if policy.get("live_transport_allowed"):
        fails.append("the_policy_permitted_a_live_transport")
    if policy.get("live_transport_implemented"):
        fails.append("the_policy_claimed_a_live_transport_exists")
    if policy.get("source_monitoring_live"):
        fails.append("the_policy_claimed:source_monitoring_live")
    if int(policy.get("approved_source_count") or 0) != 0:
        fails.append("the_policy_reported_an_approved_source")
    for counter in ("collectors_invoked", "live_source_calls"):
        if int(policy.get(counter) or 0) != 0:
            fails.append(f"the_policy_counted:{counter}")

    # The policy must agree with the guard about the live answer. Two values
    # for one fact is how they come to disagree.
    if bool(policy.get("guard_allowed")) is not bool(
        policy.get("live_transport_allowed")
    ):
        fails.append("live_transport_allowed_disagrees_with_the_guard")

    # allowed and refused, both directions.
    if policy.get("execution_allowed") and policy.get("refusal_reasons"):
        fails.append("execution_allowed_alongside_refusal_reasons")
    if not policy.get("execution_allowed") and not policy.get("refusal_reasons"):
        fails.append("execution_refused_without_naming_a_reason")

    # A hermetic permission against a non-synthetic source is the one mistake
    # that would make this gate produce mislabelled evidence.
    if policy.get("hermetic_transport_allowed") and not policy.get(
        "is_synthetic_fixture"
    ):
        fails.append("hermetic_permitted_for_a_source_that_is_not_a_fixture")
    if policy.get("hermetic_transport_allowed") and policy.get(
        "hermetic_refusal_reasons"
    ):
        fails.append("hermetic_allowed_alongside_hermetic_refusals")

    kind = policy.get("transport_kind_requested")
    if kind is not None and kind not in TRANSPORT_KINDS:
        fails.append(f"transport_kind_outside_vocabulary:{kind}")

    # A live execution may never be allowed while this gate stands.
    if policy.get("execution_allowed") and kind == LIVE:
        fails.append("a_live_execution_was_permitted")

    if not policy.get("not_permission"):
        fails.append("the_policy_did_not_state_what_is_not_permission")

    return sorted(set(fails))
