"""The allowlist, projected from facts (Gate 162G).

## A projection, not a source of truth

There is no `allowlisted` column anywhere and this module does not add one. A
source is allowlisted exactly when its recorded facts authorize it, computed
every time it is asked.

A stored boolean would be a second truth that can drift from the first. The
drift is not hypothetical: `nf_active_opportunity_sources` already carries
`activation_approved_by`, and if an allowlist flag existed beside it, revoking
the activation and forgetting the flag would leave a source allowlisted with
nothing behind it. A projection cannot go stale because it has nothing to go
stale from.

`nf_active_opportunity_sources.activation_approved_*` remains the one place an
activation decision is STORED. This reads it; it does not shadow it.

## What `allowlisted` means here

```text
allowlisted = authorization_status == approved
```

And nothing else. Not "could be allowlisted", not "is a candidate", not "has
an adapter". A source is on the list when eleven recorded facts say so.

## Expected shape today

```text
evaluated     179   (177 shipped + 2 synthetic fixtures)
allowlisted     0   with no decisions recorded
```

The fixture count is deliberate: with decisions recorded for the permittable
fixture, exactly one source becomes allowlisted and it is synthetic. Without
something able to appear on this list, "the list is empty" would be
indistinguishable from "the list cannot be populated".
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_authorization_fixture_registry_service import (
    FIXTURE_IDS,
    is_fixture_source,
    merge_fixture_rows,
)
from nativeforge.services.source_live_authorization_service import (
    STATUS_APPROVED,
    authorization_invariant_failures,
    authorize_source_for_live_access,
)

SCHEMA_VERSION = "nf_source_allowlist_projection_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: Said once. A stored flag beside these would be a second truth to drift.
IS_A_PROJECTION = (
    "allowlisted is computed from recorded facts every time it is asked. No "
    "column stores it, so it cannot disagree with the facts underneath it. "
    "nf_active_opportunity_sources.activation_approved_* remains the one place "
    "an activation decision is stored; this reads it."
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def project_source(
    *,
    connection: Any = None,
    organization_id: Any = None,
    source_id: Any = None,
    now: Any = None,
) -> dict[str, Any]:
    """One source's allowlist standing, and what it is waiting on."""
    decision = authorize_source_for_live_access(
        connection=connection,
        organization_id=organization_id,
        source_id=source_id,
        now=now,
    )
    failures = list(authorization_invariant_failures(decision))

    allowlisted = decision["authorization_status"] == STATUS_APPROVED

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "source_id": decision.get("source_id"),
            "allowlisted": allowlisted,
            "authorization_state": decision["authorization_status"],
            "is_synthetic_fixture": is_fixture_source(source_id),
            # Separated, because "a human refused this" and "the platform is
            # not ready" have different owners.
            "missing_requirements": decision.get("blocking_decisions") or [],
            "denied_requirements": (
                decision.get("blocking_decisions") or []
                if decision.get("denial_is_a_decision")
                else []
            ),
            "blocking_prerequisites": decision.get("blocking_prerequisites") or [],
            "evidence_refs": decision.get("evidence_refs") or [],
            "denial_is_a_decision": bool(decision.get("denial_is_a_decision")),
            # An allowlisted source still has nothing to be called with.
            "live_transport_permitted": False,
            "invariant_failures": sorted(set(failures)),
            "is_a_projection": IS_A_PROJECTION,
            "live_source_call": False,
            "source_monitoring_live": False,
        }
    )


def project_allowlist(
    *,
    connection: Any = None,
    organization_id: Any = None,
    now: Any = None,
    limit: int | None = None,
) -> dict[str, Any]:
    """Every source's standing. Expected: many evaluated, none allowlisted."""
    try:
        from nativeforge.services.source_monitoring_approved_source_service import (
            load_registry_rows,
        )

        shipped = load_registry_rows()
    except Exception:  # noqa: BLE001 - an unreadable registry lists nothing
        shipped = {}

    registry = merge_fixture_rows(shipped)
    source_ids = sorted(registry)
    if limit is not None:
        source_ids = source_ids[: int(limit)]

    projections: list[dict[str, Any]] = []
    failures: list[str] = []
    for source_id in source_ids:
        projection = project_source(
            connection=connection,
            organization_id=organization_id,
            source_id=source_id,
            now=now,
        )
        failures.extend(projection["invariant_failures"])
        projections.append(projection)

    allowlisted = [p for p in projections if p["allowlisted"]]
    real_allowlisted = [
        p for p in allowlisted if not p["is_synthetic_fixture"]
    ]

    by_state: dict[str, int] = {}
    for projection in projections:
        state = projection["authorization_state"]
        by_state[state] = by_state.get(state, 0) + 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "evaluated": len(projections),
            "shipped_registry_count": len(shipped),
            "fixture_count": len(FIXTURE_IDS),
            "allowlisted": len(allowlisted),
            "allowlisted_source_ids": sorted(
                str(p["source_id"]) for p in allowlisted
            ),
            # THE number. A synthetic fixture on the list is the falsifiability
            # proof; a real source on it would be a breach of this gate.
            "real_sources_allowlisted": len(real_allowlisted),
            "synthetic_fixtures_allowlisted": len(allowlisted)
            - len(real_allowlisted),
            "by_authorization_state": by_state,
            "projections": projections,
            "invariant_failures": sorted(set(failures)),
            "is_a_projection": IS_A_PROJECTION,
            "live_transport_permitted": False,
            "live_source_call": False,
            "network_calls": 0,
            "approved_source_count": len(real_allowlisted),
            "source_monitoring_live": False,
        }
    )


def allowlist_projection_invariant_failures(
    projection: dict[str, Any],
) -> list[str]:
    """Refuse a projection that allowlists a real source, or stores a flag."""
    fails: list[str] = list(projection.get("invariant_failures") or [])

    # THE invariant of this gate. A real source on the allowlist is the one
    # outcome Gate 162 was forbidden to produce.
    real = int(projection.get("real_sources_allowlisted") or 0)
    if real:
        fails.append(f"real_sources_allowlisted:{real}")
    if int(projection.get("approved_source_count") or 0):
        fails.append(
            f"approved_source_count:{projection.get('approved_source_count')}"
        )

    # allowlisted and the id list must agree, both directions.
    listed = projection.get("allowlisted_source_ids")
    if listed is not None and len(listed) != int(
        projection.get("allowlisted") or 0
    ):
        fails.append("allowlisted_count_disagrees_with_the_id_list")

    # The state histogram must account for every source evaluated.
    by_state = projection.get("by_authorization_state")
    if by_state is not None and sum(by_state.values()) != int(
        projection.get("evaluated") or 0
    ):
        fails.append("the_state_histogram_does_not_account_for_every_source")

    # Every allowlisted source must be `approved`, per-projection.
    for entry in projection.get("projections") or []:
        if entry.get("allowlisted") and entry.get(
            "authorization_state"
        ) != STATUS_APPROVED:
            fails.append(
                f"allowlisted_without_approval:{entry.get('source_id')}"
            )
        if entry.get("allowlisted") and not entry.get("is_synthetic_fixture"):
            fails.append(
                f"a_real_source_is_allowlisted:{entry.get('source_id')}"
            )
        if entry.get("live_transport_permitted"):
            fails.append(
                f"a_projection_permitted_a_live_transport:{entry.get('source_id')}"
            )

    if not str(projection.get("is_a_projection") or "").strip():
        fails.append("the_projection_did_not_say_it_is_a_projection")

    if projection.get("live_transport_permitted"):
        fails.append("the_allowlist_permitted_a_live_transport")
    for flag in ("live_source_call", "source_monitoring_live"):
        if projection.get(flag):
            fails.append(f"allowlist_claimed:{flag}")

    return sorted(set(fails))
