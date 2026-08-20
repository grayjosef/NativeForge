"""Offline smoke for Campaign Block 03 pursuit workspace."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.pursuit_workspace_assembler_service import (
    build_pursuit_workspace_demo_surface,
    pursuit_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    DEMO_ROUTE_PATH,
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_campaign_block03_smoke_v1"


def _run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"nf_camp03_pursuit_smoke_{ts}_{uuid.uuid4().hex[:8]}"


def run_campaign_block03_smoke() -> dict[str, Any]:
    run_id = _run_id()
    surface = build_pursuit_workspace_demo_surface()
    payload = build_sc_customer_demo_bridge_payload()
    surfaces: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        surfaces.append(
            {"surface": name, "status": "PASS" if ok else "FAIL", "detail": detail}
        )

    sf = pursuit_demo_surface_invariant_failures(surface)
    bf = bridge_payload_invariant_failures(payload)
    add("demo_route", DEMO_ROUTE_PATH == "/?view=sc_customer_demo", DEMO_ROUTE_PATH)
    add(
        "workspaces_present",
        (surface.get("workspace_count") or 0) >= 1,
        str(surface.get("workspace_count")),
    )
    add(
        "no_submission_ready",
        surface.get("submission_ready_claimed") is False
        and surface.get("final_submission_allowed") is False,
        "false",
    )
    add(
        "no_proposal_drafting",
        surface.get("proposal_drafting_claimed") is False,
        "false",
    )
    add(
        "bridge_ok",
        bool(payload.get("pursuit_workspace")) and not bf and not sf,
        f"bf={bf} sf={sf}",
    )
    layers = {
        (w.get("workspace") or {}).get("opportunity_source_layer")
        for w in (surface.get("workspaces") or [])
    }
    add("sc_and_federal", "sc_state" in layers and "federal" in layers, str(layers))

    failed = [s for s in surfaces if s["status"] != "PASS"]
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "status": "PASS" if not failed else "FAIL",
        "demo_route_path": DEMO_ROUTE_PATH,
        "surfaces": surfaces,
        "failed_surfaces": [s["surface"] for s in failed],
    }
    out = Path("artifacts/campaign_block03_smoke")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{run_id}.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result
