"""Campaign Block 38 smoke."""

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
from nativeforge.services.storage_sca_pentest_assembler_service import (
    build_storage_sca_pentest_demo_surface,
    storage_sca_pentest_demo_surface_invariant_failures,
)

SCHEMA_VERSION = "nf_campaign_block38_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block38_smoke")


def run_campaign_block38_smoke(*, run_python_sca: bool = True) -> dict[str, Any]:
    run_id = (
        f"nf_camp38_storage_sca_smoke_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    fails: list[str] = []
    surface = build_storage_sca_pentest_demo_surface(run_python_sca=run_python_sca)
    fails.extend(storage_sca_pentest_demo_surface_invariant_failures(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    if not bridge.get("storage_sca_pentest"):
        fails.append("bridge_missing_storage_sca_pentest")
    status = "PASS" if not fails else "FAIL"
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "overall_status": status,
        "campaign_block": 38,
        "fails": fails,
        "python_sca_run": bool(surface.get("python_sca_run")),
        "python_sca_passed": bool(surface.get("python_sca_passed")),
        "full_sca_passed_claimed": bool(surface.get("full_sca_passed_claimed")),
        "production_storage_approved": False,
        "demo_route_path": "/?view=sc_customer_demo",
    }
    DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
    path = DEFAULT_OUT / f"{run_id}.json"
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result["artifact"] = str(path)
    return result
