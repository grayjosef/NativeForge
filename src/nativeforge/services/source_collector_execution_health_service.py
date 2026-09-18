"""Collector execution health (Gate 161K).

## The lane, and the four things it must say at once

```text
execution_envelope_ready      = True    the machinery composes end to end
hermetic_execution_proven     = True    against a REGISTERED FIXTURE
live_transport_available      = False   no implementation exists
approved_source_count         = 0       and nothing may be called anyway
source_monitoring_live        = False
```

Gate 160's health service said a working landing zone is the most plausible
thing to mistake for a working collector. This gate is worse: the envelope now
genuinely transports bytes, persists them and issues a proof, and the only thing
separating that from collection is which transport was injected.

So this service reports the four facts separately and never derives one from
another. `execution_envelope_ready` is about machinery. `hermetic_execution_
proven` is about a fixture. `live_transport_available` is about an
implementation that does not exist. `approved_source_count` is about permission
nobody has granted. All four are true at once, and any one of them read alone
gives the wrong answer.

## Every condition is MEASURED

`live_transport_available` is not a constant. It is derived by asking the
transport boundary to parse itself - `describe_boundary()` - and reading whether
`live` is in `DISPATCHABLE_KINDS`. A constant `False` would be correct today and
wrong the day somebody adds a live transport, without anything changing in the
code that says so, which is exactly the defect this campaign keeps finding.

The same goes for `approved_source_count`, which asks `evaluate_registry`
rather than counting registry rows - the registry knows about 177 sources and
has approved none of them, and `len()` of the row list reported 177 approved
until the lane's own invariant refused it.

## What ready does not mean

`execution_envelope_ready` means the envelope works in `controlled_dev_demo`
against fixtures. It does not mean a source may be called: that needs Gate 162's
allowlist, an approved source, and a human before either.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.repositories.source_collection_execution_attempt_repository import (
    EXECUTION_STATUSES,
    attempt_invariant_failures,
    count_attempts,
)
from nativeforge.services.hermetic_source_transport_service import (
    describe_hermetic_transport,
)
from nativeforge.services.source_collection_execution_proof_service import (
    PROOF_REQUIREMENTS,
)
from nativeforge.services.source_collection_transport_service import (
    HERMETIC,
    LIVE,
    describe_boundary,
)

SCHEMA_VERSION = "nf_source_collector_execution_health_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: What must hold for the envelope to be called ready. Each is measured.
CONDITIONS: tuple[str, ...] = (
    "attempt_table_exists",
    "transport_boundary_reaches_no_host",
    "hermetic_transport_reaches_no_host",
    "live_transport_requires_an_authorization",
    "no_attempt_claims_a_live_call",
    "no_live_attempt_rows_exist",
    "proof_requirements_are_defined",
)

#: Said plainly, because each is a thing a reader might otherwise infer.
NOT_IMPLIED: tuple[str, ...] = (
    "a ready envelope is not an approved source",
    "a hermetic proof is not a source having responded",
    "a persisted payload is not a successful collection",
    "an attempt row is not a network call",
    "zero live attempts is not a live transport that refused - there is none",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def detect_live_transport_available() -> bool:
    """Ask the boundary whether a live transport could dispatch.

    Derived, never declared. A constant `False` would be right today and wrong
    the day somebody adds one, with nothing in the code changing to say so.
    """
    try:
        boundary = describe_boundary()
    except Exception:  # noqa: BLE001 - an unanswerable boundary is not available
        return False
    return bool(
        LIVE in set(boundary.get("dispatchable_kinds") or ())
        or boundary.get("live_transport_implemented_here")
        or boundary.get("live_transport_enabled")
    )


def detect_source_counts() -> dict[str, int]:
    """How many sources the registry KNOWS, and how many are APPROVED.

    Two different numbers, and conflating them was this module's first bug: the
    registry holds 177 rows, and `len()` of it reported 177 approved sources.
    Approval is what `evaluate_registry` decides, by running each row through
    terms, activation, human review and credentials - so that is what gets
    asked, and the row count is reported beside it rather than hidden.

    A registry that is full and approves nothing is the true state of this
    campaign, and a reader should be able to see both halves of it.
    """
    try:
        from nativeforge.services.source_monitoring_approved_source_service import (
            evaluate_registry,
        )

        evaluated = evaluate_registry()
        return {
            "known": int(evaluated.get("registry_row_count") or 0),
            "approved": int(evaluated.get("activation_approved_count") or 0),
            "monitorable": int(evaluated.get("monitorable_count") or 0),
            "terms_blocked": int(evaluated.get("terms_blocked_count") or 0),
            "human_review_blocked": int(
                evaluated.get("human_review_blocked_count") or 0
            ),
        }
    except Exception:  # noqa: BLE001 - an unanswerable registry approves nothing
        return {
            "known": 0,
            "approved": 0,
            "monitorable": 0,
            "terms_blocked": 0,
            "human_review_blocked": 0,
        }


def _live_requires_a_warrant() -> bool:
    """Does the boundary refuse LIVE when the policy does not permit it?

    Gate 161 asserted `live` was not in DISPATCHABLE_KINDS at all. Gate 163
    made it dispatchable for an authorized source, so the question became
    whether an UNAUTHORIZED live dispatch is still refused - which is the
    property that was actually worth having.

    Measured by attempting one, with a hermetic fixture request that reaches
    no host even if the refusal failed.
    """
    try:
        from nativeforge.services.source_collection_request_builder_service import (
            build_source_request,
        )
        from nativeforge.services.source_collection_transport_service import (
            LIVE,
            execute_request,
        )

        built = build_source_request(
            source_definition={
                "source_id": "nf163.probe.unauthorized",
                "endpoint": "https://fixtures.invalid/nf163/probe",
                "method": "GET",
            }
        )
        if not built.get("usable"):
            return False

        dispatched = execute_request(
            request=built["transport_request"],
            transport_kind=LIVE,
            # A policy that permits NOTHING. The boundary must refuse.
            policy={
                "execution_allowed": False,
                "live_transport_allowed": False,
                "hermetic_transport_allowed": False,
            },
            transport=lambda request: None,
        )
        return not dispatched.get("dispatched")
    except Exception:  # noqa: BLE001 - an unmeasurable refusal is not one
        return False


def build_execution_health(
    *, connection: Any = None, organization_id: Any = None
) -> dict[str, Any]:
    """Measure the lane. Contacts nothing; reads what is already recorded."""
    failures: list[str] = []
    blocked: list[str] = []

    boundary = describe_boundary()
    hermetic = describe_hermetic_transport()

    counts = count_attempts(connection=connection, organization_id=organization_id)
    failures.extend(attempt_invariant_failures(counts))
    blocked.extend(counts.get("blocked_reasons") or [])
    table_readable = not counts.get("blocked_reasons")

    live_available = detect_live_transport_available()
    sources = detect_source_counts()

    measured = {
        "attempt_table_exists": bool(table_readable),
        # Both modules parse THEMSELVES for network imports. A module that
        # imports nothing network-capable cannot reach a host, and that is
        # derived rather than asserted.
        # `[...]`, not `.get(...)`. A missing key must raise rather than
        # answer None, which `not None` then reports as a pass - the health
        # lane did exactly that for the hermetic module until the two
        # descriptions were given the same name for the same fact.
        "transport_boundary_reaches_no_host": not boundary["reaches_a_host"],
        "hermetic_transport_reaches_no_host": not hermetic["reaches_a_host"],
        # Gate 163 replaced "live cannot dispatch" with "live cannot dispatch
        # without a warrant". MEASURED, not assumed: a LIVE request is put
        # through the boundary with a policy that does not permit it, and the
        # condition holds only if the boundary refuses.
        "live_transport_requires_an_authorization": _live_requires_a_warrant(),
        "no_attempt_claims_a_live_call": int(
            counts.get("rows_claiming_a_live_call") or 0
        )
        == 0,
        "no_live_attempt_rows_exist": int(counts.get("live_attempts") or 0) == 0,
        "proof_requirements_are_defined": len(PROOF_REQUIREMENTS) > 0,
    }

    unmet = sorted(name for name, ok in measured.items() if not ok)
    ready = all(measured.values())

    total = int(counts.get("total") or 0)
    proofs = int(counts.get("proofs_available") or 0)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            # ---- machinery -------------------------------------------------
            "execution_envelope_ready": ready,
            "conditions": measured,
            "conditions_expected": list(CONDITIONS),
            "conditions_not_met": unmet,
            "blocked_reasons": sorted(set(blocked)),
            "invariant_failures": sorted(set(failures)),
            # ---- what has actually happened -------------------------------
            "attempts_recorded": total,
            "attempts_by_status": counts.get("by_status") or {},
            "attempts_by_transport_kind": counts.get("by_transport_kind") or {},
            "hermetic_attempts": int(counts.get("hermetic_attempts") or 0),
            "execution_proofs_available": proofs,
            "payloads_linked": int(counts.get("payloads_linked") or 0),
            "bytes_received_total": int(counts.get("total_bytes_received") or 0),
            # A proof exists and it is a HERMETIC proof. Named so that reading
            # the count alone cannot be mistaken for a source having answered.
            "hermetic_execution_proven": bool(proofs > 0),
            "live_execution_proven": False,
            # ---- what is not available ------------------------------------
            "transport_kinds": list(boundary.get("transport_kinds") or ()),
            "dispatchable_kinds": list(boundary.get("dispatchable_kinds") or ()),
            "live_transport_available": live_available,
            "live_transport_enabled": False,
            "approved_source_count": sources["approved"],
            # Reported beside it, because a registry that is FULL and approves
            # NOTHING is the true state, and one number alone tells half of it.
            "known_source_count": sources["known"],
            "monitorable_source_count": sources["monitorable"],
            "terms_blocked_source_count": sources["terms_blocked"],
            "human_review_blocked_source_count": sources["human_review_blocked"],
            "known_is_not_approved": (
                "the registry knows about many sources. Knowing a source exists "
                "is not permission to call it, and the two counts are separate "
                "for exactly that reason."
            ),
            "default_transport_kind": HERMETIC,
            # ---- constants -------------------------------------------------
            "collectors_invoked": 0,
            "live_source_calls": 0,
            "network_calls": 0,
            "urls_fetched": 0,
            "dns_resolved": False,
            "credentials_required": False,
            "source_monitoring_live": False,
            "execution_statuses": list(EXECUTION_STATUSES),
            "proof_requirements": list(PROOF_REQUIREMENTS),
            "not_implied": list(NOT_IMPLIED),
            "next_step_owner": (
                "Gate 162 owns activation and the allowlist. Gate 163 is the "
                "first approved live source. Neither is unlocked by this lane "
                "being ready."
            ),
        }
    )


def execution_health_invariant_failures(health: dict[str, Any]) -> list[str]:
    """Refuse a health report that would read as a working collector."""
    fails: list[str] = list(health.get("invariant_failures") or [])

    for counter in (
        "collectors_invoked",
        "live_source_calls",
        "network_calls",
        "urls_fetched",
        "approved_source_count",
    ):
        if int(health.get(counter) or 0):
            fails.append(f"health_counted:{counter}={health.get(counter)}")

    # `live_transport_available` is deliberately NOT in this list. Gate 161
    # refused a true value because no implementation existed, so claiming one
    # was a false claim. Gate 163 built it. Refusing it now would refuse the
    # true state, and a lane that refuses the truth gets edited until it
    # stops, which is how an invariant becomes a formality.
    #
    # The property that was actually worth having - that an UNAUTHORIZED live
    # dispatch is still refused - is asserted below as
    # `live_transport_requires_an_authorization`, measured by attempting one.
    #
    # `live_transport_enabled` STAYS. Available is not enabled: an
    # implementation existing is not a standing permission to use it.
    for flag in (
        "live_transport_enabled",
        "live_execution_proven",
        "source_monitoring_live",
        "dns_resolved",
        "credentials_required",
    ):
        if health.get(flag):
            fails.append(f"health_claimed:{flag}")

    if int(health.get("monitorable_source_count") or 0):
        fails.append(
            f"health_counted:monitorable_source_count="
            f"{health.get('monitorable_source_count')}"
        )

    # The registry is allowed to KNOW about sources. That is not an approval,
    # so `known_source_count` is deliberately absent from the zero checks -
    # and the lane must say so rather than leave the difference implied.
    if int(health.get("known_source_count") or 0) and not str(
        health.get("known_is_not_approved") or ""
    ).strip():
        fails.append("known_sources_without_saying_that_knowing_is_not_approving")

    # `live` may be NAMED so refusing it is expressible; it may not be
    # dispatchable.
    # `live` being dispatchable is no longer a failure - Gate 163 made it
    # so deliberately, for one authorized source. What IS a failure is a
    # live dispatch that no authorization permits, which the condition
    # above measures directly.
    if not (health.get("conditions") or {}).get(
        "live_transport_requires_an_authorization"
    ):
        fails.append("live_can_dispatch_without_an_authorization")

    if int(health.get("hermetic_attempts") or 0) != int(
        health.get("attempts_recorded") or 0
    ):
        fails.append("some_attempt_was_not_hermetic")

    # ready and not-met must agree, both directions.
    if health.get("execution_envelope_ready") and health.get("conditions_not_met"):
        fails.append("ready_alongside_unmet_conditions")
    if not health.get("execution_envelope_ready") and not health.get(
        "conditions_not_met"
    ):
        fails.append("not_ready_without_naming_an_unmet_condition")

    conditions = health.get("conditions") or {}
    expected = set(health.get("conditions_expected") or ())
    if expected and set(conditions) != expected:
        fails.append("conditions_do_not_match_the_declared_set")

    # A proof count and the proven flag must agree, both directions. One of
    # them alone is how "the pipeline ran" becomes "the source answered".
    proven = bool(health.get("hermetic_execution_proven"))
    if proven != bool(int(health.get("execution_proofs_available") or 0) > 0):
        fails.append("hermetic_execution_proven_disagrees_with_the_proof_count")

    if int(health.get("execution_proofs_available") or 0) > int(
        health.get("payloads_linked") or 0
    ):
        fails.append("more_proofs_than_linked_payloads")

    if not health.get("not_implied"):
        fails.append("the_lane_did_not_say_what_it_does_not_imply")

    return sorted(set(fails))
