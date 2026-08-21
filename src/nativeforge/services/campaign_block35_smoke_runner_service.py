"""Campaign Block 35 smoke."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.rbac_enforcement_assembler_service import (
    build_rbac_enforcement_demo_surface,
    rbac_enforcement_demo_surface_invariant_failures,
)
from nativeforge.services.rbac_enforcement_service import run_rbac_enforcement_suite
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_campaign_block35_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block35_smoke")


def run_campaign_block35_smoke() -> dict[str, Any]:
    run_id = (
        f"nf_camp35_rbac_enforcement_smoke_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    fails: list[str] = []
    suite = run_rbac_enforcement_suite()
    if suite.get("overall_status") != "PASS":
        fails.extend(suite.get("fails") or ["suite_fail"])
    surface = build_rbac_enforcement_demo_surface()
    fails.extend(rbac_enforcement_demo_surface_invariant_failures(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    if not bridge.get("rbac_enforcement"):
        fails.append("bridge_missing_rbac_enforcement")
    status = "PASS" if not fails else "FAIL"
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "overall_status": status,
        "campaign_block": 35,
        "fails": fails,
        "login_live_claimed": False,
        "rbac_enforced_claimed": True,
        "demo_route_path": "/?view=sc_customer_demo",
    }
    DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
    path = DEFAULT_OUT / f"{run_id}.json"
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result["artifact"] = str(path)
    return result
