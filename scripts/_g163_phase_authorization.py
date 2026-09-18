"""Gate 163X: authorization with fresh in-process runtime evidence.

Asserts the exact-one-source property before anything is opted in. Writes
nothing except the exerciser's own fixture rows, which it cleans up.

## Why the exhaustive check does not exercise 178 times

`runtime_status` is a property of the RUNTIME, not of a source: one reading
applies to every source. So threading the exercise through `project_allowlist`
would exercise the lanes once per source - 180 write-and-clean cycles to
measure one global fact - and passing a pre-computed readiness into each
authorize call would recreate exactly the "caller supplies the fact" hazard
Gate 162 exists to prevent.

Instead: resolve every real source COLD, and count those whose only unrecorded
fact is `runtime_status`. Those are precisely the sources that become
allowlisted when the runtime is ready. One exercise proves the runtime; the
cold sweep proves how many sources that unblocks. Exhaustive over all 178, and
no fact is ever handed to the resolver.

Both directions are measured. Without the exercise, `runtime_status` must still
be `not_ready` - otherwise the flag is not what produced the readiness and the
derivation is decorative.
"""

from __future__ import annotations

import json
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_authorization_fact_resolver_service import (  # noqa: E402
    resolve_source_authorization_facts,
)
from nativeforge.services.source_live_authorization_service import (  # noqa: E402
    authorization_invariant_failures,
    authorize_source_for_live_access,
)
from nativeforge.services.source_live_fetch_opt_in_service import (  # noqa: E402
    describe_opt_in_state,
)
from nativeforge.services.source_live_warrant_service import (  # noqa: E402
    AUTHORIZED_SOURCE_IDS,
)
from nativeforge.services.source_monitoring_approved_source_service import (  # noqa: E402
    load_registry_rows,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
SOURCE = "nf-seed-2026-api-grants-gov-search2"

out: dict[str, object] = {}
detail: list[str] = []

session = SessionLocal()
try:
    # ---- the cold reading must STILL be not_ready ---------------------
    cold = authorize_source_for_live_access(
        connection=session, organization_id=DEMO, source_id=SOURCE
    )
    cold_runtime = (
        (cold.get("resolution") or {})
        .get("resolved_facts", {})
        .get("runtime_status", {})
    )
    out["without_exercising_the_runtime_is_not_ready"] = (
        cold_runtime.get("value") == "not_ready"
    )
    out["without_exercising_authorization_is_refused"] = not cold.get("authorized")
    if cold.get("authorized"):
        detail.append("authorization succeeded WITHOUT exercising the runtime")

    # ---- with fresh evidence -----------------------------------------
    hot = authorize_source_for_live_access(
        connection=session,
        organization_id=DEMO,
        source_id=SOURCE,
        exercise_runtime=True,
    )
    detail.extend(authorization_invariant_failures(hot))
    facts = (hot.get("resolution") or {}).get("resolved_facts", {})
    runtime_facts = (hot.get("resolution") or {}).get("runtime_facts") or {}

    out["authorized"] = bool(hot.get("authorized"))
    out["authorization_status"] = hot.get("authorization_status")
    out["refusal_reasons"] = hot.get("refusal_reasons") or []
    out["authorization_status_is_approved"] = (
        str(hot.get("authorization_status") or "") == "approved"
    )

    statuses = {
        name: {"value": fact.get("value"), "fact_status": fact.get("fact_status")}
        for name, fact in sorted(facts.items())
    }
    out["fact_statuses"] = statuses
    out["every_fact_is_recorded"] = all(
        fact["fact_status"] == "recorded" for fact in statuses.values()
    )
    out["facts_not_recorded"] = sorted(
        name for name, fact in statuses.items() if fact["fact_status"] != "recorded"
    )

    out["runtime_status"] = (facts.get("runtime_status") or {}).get("value")
    out["runtime_status_is_ready"] = (facts.get("runtime_status") or {}).get(
        "value"
    ) == "ready"
    out["runtime_was_exercised"] = bool(runtime_facts.get("was_exercised"))
    out["runtime_derivation"] = runtime_facts.get("derivation")
    out["runtime_is_not_a_stored_claim"] = (
        runtime_facts.get("is_a_stored_claim") is False
    )
    out["exercise_fixture_rows_cleaned"] = runtime_facts.get(
        "exercise_fixture_rows_cleaned"
    )
    out["exercise_fixture_residue"] = runtime_facts.get("exercise_fixture_residue")
    out["the_exercise_left_no_residue"] = (
        runtime_facts.get("exercise_fixture_residue") == 0
    )
    out["collector_status"] = (facts.get("collector_status") or {}).get("value")
    out["robots_status"] = (facts.get("robots_status") or {}).get("value")

    # ---- exhaustive: how many real sources does readiness unblock? ----
    real_ids = sorted(load_registry_rows())
    out["real_sources_swept"] = len(real_ids)

    unblocked: list[str] = []
    blocked_by_more: dict[str, int] = {}
    for source_id in real_ids:
        resolution = resolve_source_authorization_facts(
            connection=session, organization_id=DEMO, source_id=source_id
        )
        pending = sorted(
            name
            for name, fact in (resolution.get("resolved_facts") or {}).items()
            if fact.get("fact_status") != "recorded"
        )
        if pending == ["runtime_status"]:
            unblocked.append(source_id)
        elif not pending:
            # Nothing pending at all, cold - which would mean runtime_status
            # was already recorded without an exercise.
            unblocked.append(source_id)
            detail.append(f"{source_id} had NO pending facts cold")
        else:
            blocked_by_more[source_id] = len(pending)

    out["sources_unblocked_by_runtime_readiness"] = sorted(unblocked)
    out["real_allowlisted_count"] = len(unblocked)
    out["exactly_one_real_source_is_allowlisted"] = len(unblocked) == 1
    out["the_allowlisted_source_is_the_authorized_one"] = sorted(unblocked) == [SOURCE]
    out["the_allowlist_matches_the_authorized_set"] = set(unblocked) == set(
        AUTHORIZED_SOURCE_IDS
    )
    out["other_real_sources_still_blocked"] = len(blocked_by_more)
    out["every_other_real_source_remains_denied"] = len(blocked_by_more) == (
        len(real_ids) - 1
    )
    if sorted(unblocked) != [SOURCE]:
        detail.append(f"unblocked was {sorted(unblocked)}, expected [{SOURCE}]")

    # ---- nothing has been opted in yet -------------------------------
    opt_in = describe_opt_in_state(connection=session, organization_id=DEMO)
    out["live_fetch_opted_in_count"] = opt_in["opted_in_count"]
    out["nothing_is_opted_in_yet"] = int(opt_in["opted_in_count"]) == 0
finally:
    session.close()

for key in (
    "without_exercising_the_runtime_is_not_ready",
    "without_exercising_authorization_is_refused",
    "authorized",
    "authorization_status_is_approved",
    "every_fact_is_recorded",
    "runtime_status_is_ready",
    "runtime_was_exercised",
    "runtime_is_not_a_stored_claim",
    "the_exercise_left_no_residue",
    "exactly_one_real_source_is_allowlisted",
    "the_allowlisted_source_is_the_authorized_one",
    "the_allowlist_matches_the_authorized_set",
    "every_other_real_source_remains_denied",
    "nothing_is_opted_in_yet",
):
    out.setdefault(key, False)

out["detail"] = "; ".join(sorted(set(detail))) if detail else None
print(json.dumps(out, sort_keys=True))
