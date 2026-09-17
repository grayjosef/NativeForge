"""Gate 161 verifier phase: the health lane. Writes nothing."""

from __future__ import annotations

import json
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_collector_execution_health_service import (  # noqa: E402,E501
    build_execution_health,
    execution_health_invariant_failures,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

out: dict[str, object] = {}
detail: list[str] = []
session = SessionLocal()

try:
    health = build_execution_health(connection=session, organization_id=DEMO)
    fails = execution_health_invariant_failures(health)
    if fails:
        detail.append(str(fails))

    out["execution_envelope_ready"] = bool(health["execution_envelope_ready"])
    out["live_transport_unavailable"] = bool(
        health["live_transport_available"] is False
        and "live" not in health["dispatchable_kinds"]
        and health["live_execution_proven"] is False
    )
    out["approved_source_count_is_zero"] = bool(
        health["approved_source_count"] == 0
        and health["monitorable_source_count"] == 0
    )
    # The registry KNOWS about sources, and the lane says so. A zero that came
    # from an empty registry rather than from nothing being approved would be
    # the same number for a different reason - which is a green check with two
    # possible causes.
    out["known_is_not_approved"] = bool(
        health["known_source_count"] > 0
        and str(health.get("known_is_not_approved") or "").strip()
    )
    out["no_live_attempt_rows"] = bool(
        health["conditions"]["no_live_attempt_rows_exist"]
        and health["conditions"]["no_attempt_claims_a_live_call"]
    )
    out["health_invariants_clean"] = not fails
finally:
    session.rollback()
    session.close()

for key in (
    "execution_envelope_ready", "live_transport_unavailable",
    "approved_source_count_is_zero", "known_is_not_approved",
    "no_live_attempt_rows", "health_invariants_clean",
):
    out.setdefault(key, False)

out["detail"] = "; ".join(detail) if detail else None
print(json.dumps(out, sort_keys=True))
