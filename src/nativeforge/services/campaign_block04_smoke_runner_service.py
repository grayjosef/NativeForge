"""Offline smoke for Campaign Block 04 application checklist workspace."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.application_plan_workspace_assembler_service import (
    application_plan_demo_surface_invariant_failures,
    build_application_plan_workspace_demo_surface,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_campaign_block04_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block04_smoke")


def _run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"nf_camp04_checklist_smoke_{ts}_{uuid.uuid4().hex[:8]}"


def run_campaign_block04_smoke() -> dict[str, Any]:
    run_id = _run_id()
    fails: list[str] = []
    surface = build_application_plan_workspace_demo_surface()
    fails.extend(application_plan_demo_surface_invariant_failures(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    plan = bridge.get("application_plan_workspace") or {}
    if not plan:
        fails.append("bridge_missing_application_plan_workspace")
    else:
        fails.extend(application_plan_demo_surface_invariant_failures(plan))

    screens = {
        "demo_route": "/?view=sc_customer_demo",
        "workspaces_present": (surface.get("workspace_count") or 0) >= 1,
        "no_submission_allowed": surface.get("submission_allowed") is False,
        "no_proposal_drafting": surface.get("proposal_drafting_claimed") is False,
        "no_application_complete": surface.get("application_complete_claimed") is False,
        "questions_present": any(
            (w.get("question_count") or 0) > 0
            for w in (surface.get("workspaces") or [])
        ),
        "bridge_ok": "bridge_missing_application_plan_workspace" not in fails
        and not any(f.startswith("submission") for f in fails if "bridge" in f),
        "sc_and_federal": "need_sc_and_federal_workspaces" not in fails,
    }
    for name, ok in screens.items():
        if name in {"demo_route"}:
            continue
        if not ok:
            fails.append(f"screen:{name}")

    status = "PASS" if not fails else "FAIL"
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "overall_status": status,
        "campaign_block": 4,
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
