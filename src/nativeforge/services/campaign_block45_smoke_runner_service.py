"""Campaign Block 45 smoke."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.auth0_mode_b_assembler_service import (
    auth0_mode_b_demo_surface_invariant_failures,
    build_auth0_mode_b_demo_surface,
)
from nativeforge.services.auth0_mode_b_execution_service import (
    run_auth0_mode_b_execution_path,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_campaign_block45_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block45_smoke")


def run_campaign_block45_smoke() -> dict[str, Any]:
    run_id = (
        f"nf_camp45_auth0_mode_b_smoke_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    fails: list[str] = []
    execution = run_auth0_mode_b_execution_path()
    if execution.get("mode_detected") != "mode_a":
        fails.append("expected_mode_a")
    if execution.get("login_live_claimed"):
        fails.append("login_live")
    if execution.get("secret_value_printed"):
        fails.append("secret_printed")
    surface = build_auth0_mode_b_demo_surface()
    fails.extend(auth0_mode_b_demo_surface_invariant_failures(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    if not bridge.get("auth0_mode_b"):
        fails.append("bridge_missing_auth0_mode_b")
    status = "PASS" if not fails else "FAIL"
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "overall_status": status,
        "campaign_block": 45,
        "fails": fails,
        "mode_detected": execution.get("mode_detected"),
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
