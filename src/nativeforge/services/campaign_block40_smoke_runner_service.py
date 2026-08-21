"""Campaign Block 40 smoke."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)
from nativeforge.services.storage_pentest_support_assembler_service import (
    build_storage_pentest_support_demo_surface,
    storage_pentest_support_demo_surface_invariant_failures,
)

SCHEMA_VERSION = "nf_campaign_block40_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block40_smoke")


def run_campaign_block40_smoke() -> dict[str, Any]:
    run_id = (
        f"nf_camp40_storage_pentest_smoke_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    fails: list[str] = []
    surface = build_storage_pentest_support_demo_surface()
    fails.extend(storage_pentest_support_demo_surface_invariant_failures(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    if not bridge.get("storage_pentest_support"):
        fails.append("bridge_missing_storage_pentest_support")
    status = "PASS" if not fails else "FAIL"
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "overall_status": status,
        "campaign_block": 40,
        "fails": fails,
        "production_storage_claimed": False,
        "pen_test_passed_claimed": False,
        "demo_route_path": "/?view=sc_customer_demo",
    }
    DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
    path = DEFAULT_OUT / f"{run_id}.json"
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result["artifact"] = str(path)
    return result
