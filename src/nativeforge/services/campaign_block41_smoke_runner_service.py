"""Campaign Block 41 smoke."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.auth0_validation_assembler_service import (
    auth0_validation_demo_surface_invariant_failures,
    build_auth0_validation_demo_surface,
)
from nativeforge.services.auth0_validation_smoke_service import (
    run_auth0_validation_smoke,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_campaign_block41_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block41_smoke")


def run_campaign_block41_smoke() -> dict[str, Any]:
    run_id = (
        f"nf_camp41_auth0_validation_smoke_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    fails: list[str] = []
    smoke = run_auth0_validation_smoke()
    if smoke.get("overall_status") != "PASS":
        fails.append("auth0_smoke_fail")
    if smoke.get("secret_value_printed"):
        fails.append("secret_printed")
    surface = build_auth0_validation_demo_surface()
    fails.extend(auth0_validation_demo_surface_invariant_failures(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    if not bridge.get("auth0_validation"):
        fails.append("bridge_missing_auth0_validation")
    status = "PASS" if not fails else "FAIL"
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "overall_status": status,
        "campaign_block": 41,
        "fails": fails,
        "login_live_claimed": False,
        "demo_route_path": "/?view=sc_customer_demo",
    }
    DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
    path = DEFAULT_OUT / f"{run_id}.json"
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result["artifact"] = str(path)
    return result
