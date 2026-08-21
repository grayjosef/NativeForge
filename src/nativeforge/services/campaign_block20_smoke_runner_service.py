"""Offline smoke for Campaign Block 20 collaboration dark-launch."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.collaboration_dark_launch_assembler_service import (
    build_collaboration_dark_launch_demo_surface,
    collaboration_dark_launch_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_campaign_block20_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block20_smoke")


def run_campaign_block20_smoke() -> dict[str, Any]:
    run_id = (
        f"nf_camp20_collab_dark_smoke_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    fails: list[str] = []
    surface = build_collaboration_dark_launch_demo_surface()
    fails.extend(collaboration_dark_launch_demo_surface_invariant_failures(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    cd = bridge.get("collaboration_dark_launch") or {}
    if not cd:
        fails.append("bridge_missing_collaboration_dark_launch")
    else:
        fails.extend(collaboration_dark_launch_demo_surface_invariant_failures(cd))
    status = "PASS" if not fails else "FAIL"
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "overall_status": status,
        "campaign_block": 20,
        "fails": fails,
        "demo_route_path": "/?view=sc_customer_demo",
        "collaboration_feature_enabled": False,
        "partner_matching_live_claimed": False,
    }
    DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
    path = DEFAULT_OUT / f"{run_id}.json"
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result["artifact"] = str(path)
    return result
