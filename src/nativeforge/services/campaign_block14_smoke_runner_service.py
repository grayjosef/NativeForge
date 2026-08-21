"""Offline smoke for Campaign Block 14 feedback loop."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.feedback_loop_assembler_service import (
    build_feedback_loop_demo_surface,
    feedback_loop_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_campaign_block14_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block14_smoke")


def _run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"nf_camp14_feedback_smoke_{ts}_{uuid.uuid4().hex[:8]}"


def run_campaign_block14_smoke() -> dict[str, Any]:
    run_id = _run_id()
    fails: list[str] = []
    surface = build_feedback_loop_demo_surface()
    fails.extend(feedback_loop_demo_surface_invariant_failures(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    fb = bridge.get("feedback_loop") or {}
    if not fb:
        fails.append("bridge_missing_feedback_loop")
    else:
        fails.extend(feedback_loop_demo_surface_invariant_failures(fb))

    screens = {
        "demo_route": "/?view=sc_customer_demo",
        "hooks": (surface.get("report_hook_count") or 0) >= 10,
        "no_slack_sent_claim": surface.get("slack_live_sent_claimed") is False,
        "no_persistence": surface.get("persistence_claimed") is False,
        "collab_off": (surface.get("collaboration") or {}).get(
            "collaboration_feature_enabled"
        )
        is False,
        "bridge_ok": "bridge_missing_feedback_loop" not in fails,
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
        "campaign_block": 14,
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
