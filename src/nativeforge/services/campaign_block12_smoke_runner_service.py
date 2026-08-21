"""Offline smoke for Campaign Block 12 controlled drafting v0."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.controlled_drafting_assembler_service import (
    build_controlled_drafting_demo_surface,
    controlled_drafting_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_campaign_block12_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block12_smoke")


def _run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"nf_camp12_controlled_draft_smoke_{ts}_{uuid.uuid4().hex[:8]}"


def run_campaign_block12_smoke() -> dict[str, Any]:
    run_id = _run_id()
    fails: list[str] = []
    surface = build_controlled_drafting_demo_surface()
    fails.extend(controlled_drafting_demo_surface_invariant_failures(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    cd = bridge.get("controlled_drafting") or {}
    if not cd:
        fails.append("bridge_missing_controlled_drafting")
    else:
        fails.extend(controlled_drafting_demo_surface_invariant_failures(cd))

    screens = {
        "demo_route": "/?view=sc_customer_demo",
        "workspaces": (surface.get("workspace_count") or 0) >= 1,
        "no_complete_proposal": surface.get("complete_proposal_claimed") is False,
        "not_submission_ready": surface.get("submission_ready_claimed") is False,
        "not_final": surface.get("final_text_claimed") is False,
        "bridge_ok": "bridge_missing_controlled_drafting" not in fails,
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
        "campaign_block": 12,
        "fails": fails,
        "screens": screens,
        "demo_route_path": "/?view=sc_customer_demo",
    }
    DEFAULT_OUT.mkdir(parents=True, exist_ok=True)
    path = DEFAULT_OUT / f"{run_id}.json"
    path.write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    result["artifact"] = str(path)
    return result
