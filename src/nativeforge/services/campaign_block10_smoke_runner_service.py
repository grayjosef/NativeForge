"""Offline smoke for Campaign Block 10 source freshness pilot."""

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
from nativeforge.services.source_freshness_pilot_checker_service import (
    build_source_freshness_demo_surface,
    source_freshness_demo_surface_invariant_failures,
)

SCHEMA_VERSION = "nf_campaign_block10_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block10_smoke")


def _run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"nf_camp10_freshness_smoke_{ts}_{uuid.uuid4().hex[:8]}"


def run_campaign_block10_smoke() -> dict[str, Any]:
    run_id = _run_id()
    fails: list[str] = []
    surface = build_source_freshness_demo_surface()
    fails.extend(source_freshness_demo_surface_invariant_failures(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    sf = bridge.get("source_freshness_pilot") or {}
    if not sf:
        fails.append("bridge_missing_source_freshness_pilot")
    else:
        fails.extend(source_freshness_demo_surface_invariant_failures(sf))

    screens = {
        "demo_route": "/?view=sc_customer_demo",
        "sources_present": (surface.get("source_count") or 0) >= 1,
        "external_not_run": surface.get("external_live_check_not_run") is True,
        "no_live_ingest": surface.get("live_ingest_claimed") is False,
        "no_continuous": surface.get("continuous_monitoring_claimed") is False,
        "no_activation": surface.get("production_activation_claimed") is False,
        "bridge_ok": "bridge_missing_source_freshness_pilot" not in fails,
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
        "campaign_block": 10,
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
