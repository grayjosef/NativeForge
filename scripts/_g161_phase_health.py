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
    # Gate 163: a live transport now EXISTS and is dispatchable for an
    # authorized source. The property that still matters is that it cannot
    # dispatch without an authorizing policy - measured by the health lane
    # attempting exactly that and requiring refusal.
    out["live_transport_requires_an_authorization"] = bool(
        health["conditions"].get("live_transport_requires_an_authorization")
        and health["live_execution_proven"] is False
    )
    out["approved_source_count_is_zero"] = bool(
        health["approved_source_count"] == 0 and health["monitorable_source_count"] == 0
    )
    # The registry KNOWS about sources, and the lane says so. A zero that came
    # from an empty registry rather than from nothing being approved would be
    # the same number for a different reason - which is a green check with two
    # possible causes.
    out["known_is_not_approved"] = bool(
        health["known_source_count"] > 0
        and str(health.get("known_is_not_approved") or "").strip()
    )
    # Read by name, so a rename raises rather than reporting a quiet False.
    # Gate 163 renamed both: the property is "no UNAUTHORIZED live attempt
    # row", and the authorized Gate 163 collection is a row that legitimately
    # exists.
    out["no_unauthorized_live_attempt_rows"] = bool(
        health["conditions"]["no_unauthorized_live_attempt_rows_exist"]
        and health["conditions"]["no_unauthorized_attempt_claims_a_live_call"]
    )
    # Reported beside it, because "how much live activity has there been" is
    # still worth seeing and is no longer the thing that decides readiness.
    out["live_attempts"] = int(health.get("live_attempts") or 0)
    out["authorized_live_attempts"] = int(health.get("authorized_live_attempts") or 0)
    out["unauthorized_live_attempts"] = int(
        health.get("unauthorized_live_attempts") or 0
    )
    out["health_invariants_clean"] = not fails
finally:
    session.rollback()
    session.close()

for key in (
    "execution_envelope_ready",
    "live_transport_requires_an_authorization",
    "approved_source_count_is_zero",
    "known_is_not_approved",
    "no_unauthorized_live_attempt_rows",
    "health_invariants_clean",
):
    out.setdefault(key, False)

out["detail"] = "; ".join(detail) if detail else None
print(json.dumps(out, sort_keys=True))
