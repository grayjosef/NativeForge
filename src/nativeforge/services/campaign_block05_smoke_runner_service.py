"""Offline smoke for Campaign Block 05 intake + approval workflow."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.intake_approval_workspace_assembler_service import (
    build_intake_approval_demo_surface,
    intake_approval_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_campaign_block05_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block05_smoke")


def _run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"nf_camp05_intake_smoke_{ts}_{uuid.uuid4().hex[:8]}"


def run_campaign_block05_smoke() -> dict[str, Any]:
    run_id = _run_id()
    fails: list[str] = []
    surface = build_intake_approval_demo_surface()
    fails.extend(intake_approval_demo_surface_invariant_failures(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    intake = bridge.get("intake_approval_workspace") or {}
    if not intake:
        fails.append("bridge_missing_intake_approval_workspace")
    else:
        fails.extend(intake_approval_demo_surface_invariant_failures(intake))

    screens = {
        "demo_route": "/?view=sc_customer_demo",
        "workspaces_present": (surface.get("workspace_count") or 0) >= 1,
        "no_upload_claim": surface.get("binary_upload_persistence_claimed") is False,
        "no_approval_persist_claim": surface.get("approval_persistence_claimed")
        is False,
        "no_submission_ready": surface.get("submission_ready_claimed") is False,
        "no_package_unlock": surface.get("package_readiness_unlocked") is False,
        "approvals_present": any(
            (w.get("approval_count") or 0) > 0
            for w in (surface.get("workspaces") or [])
        ),
        "bridge_ok": "bridge_missing_intake_approval_workspace" not in fails,
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
        "campaign_block": 5,
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
