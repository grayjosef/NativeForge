"""Offline smoke for Campaign Block 19 multi-org pilot."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.multi_org_pilot_assembler_service import (
    build_multi_org_pilot_demo_surface,
    multi_org_pilot_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_campaign_block19_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block19_smoke")


def run_campaign_block19_smoke() -> dict[str, Any]:
    run_id = (
        f"nf_camp19_multiorg_smoke_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    fails: list[str] = []
    surface = build_multi_org_pilot_demo_surface()
    fails.extend(multi_org_pilot_demo_surface_invariant_failures(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    mo = bridge.get("multi_org_pilot") or {}
    if not mo:
        fails.append("bridge_missing_multi_org_pilot")
    else:
        fails.extend(multi_org_pilot_demo_surface_invariant_failures(mo))
    status = "PASS" if not fails else "FAIL"
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "overall_status": status,
        "campaign_block": 19,
        "fails": fails,
        "org_count": (surface.get("cohort") or {}).get("organization_count"),
        "demo_route_path": "/?view=sc_customer_demo",
        "production_multi_tenant_claimed": False,
        "live_customer_login_claimed": False,
    }
    DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
    path = DEFAULT_OUT / f"{run_id}.json"
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result["artifact"] = str(path)
    return result
