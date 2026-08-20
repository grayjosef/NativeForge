"""Offline smoke for Campaign Block 07 package readiness + operator queue."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.package_readiness_queue_assembler_service import (
    build_package_readiness_demo_surface,
    package_readiness_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_campaign_block07_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block07_smoke")


def _run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"nf_camp07_readiness_smoke_{ts}_{uuid.uuid4().hex[:8]}"


def run_campaign_block07_smoke() -> dict[str, Any]:
    run_id = _run_id()
    fails: list[str] = []
    surface = build_package_readiness_demo_surface()
    fails.extend(package_readiness_demo_surface_invariant_failures(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    readiness = bridge.get("package_readiness_queue") or {}
    if not readiness:
        fails.append("bridge_missing_package_readiness_queue")
    else:
        fails.extend(package_readiness_demo_surface_invariant_failures(readiness))

    screens = {
        "demo_route": "/?view=sc_customer_demo",
        "workspaces_present": (surface.get("workspace_count") or 0) >= 1,
        "no_submission_ready": surface.get("submission_ready_claimed") is False,
        "no_final_eligibility": surface.get("final_eligibility_claimed") is False,
        "no_proposal": surface.get("proposal_drafting_claimed") is False,
        "no_live_ingest": surface.get("live_ingest_claimed") is False,
        "queue_present": any(
            (w.get("review_item_count") or 0) > 0
            for w in (surface.get("workspaces") or [])
        ),
        "unsupported_visible": any(
            (w.get("unsupported_capability_count") or 0) > 0
            for w in (surface.get("workspaces") or [])
        ),
        "bridge_ok": "bridge_missing_package_readiness_queue" not in fails,
        "sc_and_federal": "need_sc_and_federal_workspaces" not in fails,
    }
    for name, ok in screens.items():
        if name == "demo_route":
            continue
        if not ok:
            fails.append(f"screen:{name}")

    status = "PASS" if not fails else "FAIL"
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "overall_status": status,
        "campaign_block": 7,
        "fails": fails,
        "screens": screens,
        "workspace_count": surface.get("workspace_count"),
        "demo_route_path": "/?view=sc_customer_demo",
    }
    out_dir = DEFAULT_OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{run_id}.json"
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result["artifact"] = str(path)
    return result
