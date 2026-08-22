"""Campaign Block 78 smoke."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.gate33_runbook_assembler_service import (
    build_runbook_demo_surface,
    runbook_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_campaign_block78_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block78_smoke")


def run_campaign_block78_smoke() -> dict[str, Any]:
    run_id = (
        f"nf_camp78_runbook_smoke_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    fails: list[str] = []
    surface = build_runbook_demo_surface()
    fails.extend(runbook_demo_surface_invariant_failures(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    if not bridge.get("operator_runbooks"):
        fails.append("bridge_missing_operator_runbooks")
    status = "PASS" if not fails else "FAIL"
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "overall_status": status,
        "campaign_block": 78,
        "fails": fails,
        "demo_route_path": "/?view=sc_customer_demo",
    }
    DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
    path = DEFAULT_OUT / f"{run_id}.json"
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result["artifact"] = str(path)
    return result
