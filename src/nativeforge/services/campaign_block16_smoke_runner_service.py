"""Offline smoke for Campaign Block 16 forms/attachments map."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.forms_attachments_mapper_service import (
    build_forms_attachments_demo_surface,
    forms_attachments_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_campaign_block16_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block16_smoke")


def _run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"nf_camp16_forms_map_smoke_{ts}_{uuid.uuid4().hex[:8]}"


def run_campaign_block16_smoke() -> dict[str, Any]:
    run_id = _run_id()
    fails: list[str] = []
    surface = build_forms_attachments_demo_surface()
    fails.extend(forms_attachments_demo_surface_invariant_failures(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    fa = bridge.get("forms_attachments_map") or {}
    if not fa:
        fails.append("bridge_missing_forms_attachments_map")
    else:
        fails.extend(forms_attachments_demo_surface_invariant_failures(fa))

    screens = {
        "demo_route": "/?view=sc_customer_demo",
        "workspaces": (surface.get("workspace_count") or 0) >= 1,
        "no_upload": surface.get("binary_upload_supported") is False,
        "no_persistence": surface.get("attachment_persistence_claimed") is False,
        "no_form_complete": surface.get("form_completion_claimed") is False,
        "bridge_ok": "bridge_missing_forms_attachments_map" not in fails,
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
        "campaign_block": 16,
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
