"""Gate 161 verifier phase: the smoke route, through the real app.

`smoke_wrote_inside_the_savepoint` is why the rollback means anything. A route
that never wrote can report `rolled_back: true` forever, so the count taken
DURING the savepoint has to be higher than the one before it - otherwise the
rollback proves nothing and the check says so.

Writes nothing that survives: the route's own savepoint rolls back.
"""

from __future__ import annotations

import json
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from fastapi.testclient import TestClient  # noqa: E402
from tests import session_org_helper as soh  # noqa: E402

from nativeforge.main import create_app  # noqa: E402

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
BASE = f"/v1/nf/demo/orgs/{DEMO}/collector-execution"

out: dict[str, object] = {}
detail: list[str] = []

try:
    soh.ensure_org(DEMO, "demo")
    client = TestClient(create_app())
    headers = soh.session_headers(DEMO)

    response = client.post(f"{BASE}/smoke", headers=headers)
    out["smoke_ran"] = bool(response.status_code == 200)
    if response.status_code != 200:
        detail.append(f"http={response.status_code} {response.text[:200]}")
        body = {}
    else:
        payload = response.json()
        body = payload.get("data", payload)

    invariants = body.get("invariant_failures") or []
    if invariants:
        detail.append(f"invariants:{invariants}")

    # The rollback only means something if there was something to roll back.
    out["smoke_wrote_inside_the_savepoint"] = bool(
        int(body.get("attempt_rows_during") or 0)
        > int(body.get("attempt_rows_before") or 0)
    )
    out["smoke_rolled_back"] = bool(
        body.get("rolled_back")
        and body.get("attempt_rows_after") == body.get("attempt_rows_before")
    )
    out["smoke_produced_a_proof"] = bool(
        (body.get("smoke") or {}).get("execution_proof_available")
        and not invariants
    )
    out["smoke_denies_a_source_responded"] = bool(
        body.get("proves_a_source_responded") is False
        and (body.get("proof") or {}).get("proves_a_source_responded") is False
        and (body.get("proof") or {}).get("proves_the_envelope_works") is True
    )
    out["smoke_caller_cannot_supply_a_url"] = bool(
        body.get("caller_can_supply_a_url") is False
        and body.get("live_source_call") is False
        and int(body.get("network_calls") or 0) == 0
        and body.get("url_came_from") == "a constant in this module"
    )
except Exception as exc:  # noqa: BLE001 - the phase reports rather than raises
    detail.append(f"phase_error:{type(exc).__name__}:{exc}")

for key in (
    "smoke_ran", "smoke_wrote_inside_the_savepoint", "smoke_rolled_back",
    "smoke_produced_a_proof", "smoke_denies_a_source_responded",
    "smoke_caller_cannot_supply_a_url",
):
    out.setdefault(key, False)

out["detail"] = "; ".join(detail) if detail else None
print(json.dumps(out, sort_keys=True))
