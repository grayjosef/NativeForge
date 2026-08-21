"""Offline smoke for Campaign Block 09 NOFO extraction pilot."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.nofo_extraction_pilot_assembler_service import (
    build_nofo_extraction_demo_surface,
    nofo_extraction_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_campaign_block09_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block09_smoke")


def _run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"nf_camp09_nofo_extract_smoke_{ts}_{uuid.uuid4().hex[:8]}"


def run_campaign_block09_smoke() -> dict[str, Any]:
    run_id = _run_id()
    fails: list[str] = []
    surface = build_nofo_extraction_demo_surface()
    fails.extend(nofo_extraction_demo_surface_invariant_failures(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    nx = bridge.get("nofo_extraction_pilot") or {}
    if not nx:
        fails.append("bridge_missing_nofo_extraction_pilot")
    else:
        fails.extend(nofo_extraction_demo_surface_invariant_failures(nx))

    screens = {
        "demo_route": "/?view=sc_customer_demo",
        "pilot_opportunity": surface.get("pilot_opportunity_id") == "la-real-006",
        "sections_present": bool(surface.get("sections")),
        "requirements_present": bool(surface.get("requirements_map")),
        "no_full_pdf_claim": surface.get("full_pdf_extraction_claimed") is False,
        "no_broad_pdf_claim": surface.get("broad_pdf_support_claimed") is False,
        "no_drafting": surface.get("proposal_drafting_claimed") is False,
        "bridge_ok": "bridge_missing_nofo_extraction_pilot" not in fails,
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
        "campaign_block": 9,
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
