"""Offline smoke for Campaign Block 08 organization evidence memory."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.organization_evidence_memory_assembler_service import (
    build_organization_evidence_demo_surface,
    organization_evidence_demo_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_campaign_block08_smoke_v1"
DEFAULT_OUT = Path("artifacts/campaign_block08_smoke")


def _run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"nf_camp08_orgmem_smoke_{ts}_{uuid.uuid4().hex[:8]}"


def run_campaign_block08_smoke() -> dict[str, Any]:
    run_id = _run_id()
    fails: list[str] = []
    surface = build_organization_evidence_demo_surface()
    fails.extend(organization_evidence_demo_surface_invariant_failures(surface))
    bridge = build_sc_customer_demo_bridge_payload()
    fails.extend(bridge_payload_invariant_failures(bridge))
    oem = bridge.get("organization_evidence_memory") or {}
    if not oem:
        fails.append("bridge_missing_organization_evidence_memory")
    else:
        fails.extend(organization_evidence_demo_surface_invariant_failures(oem))

    screens = {
        "demo_route": "/?view=sc_customer_demo",
        "profiles_present": (surface.get("profile_count") or 0) >= 1,
        "federal_and_state": (surface.get("federal_count") or 0) >= 1
        and (surface.get("state_only_count") or 0) >= 1,
        "no_persistence_claim": surface.get("customer_data_persistence_claimed")
        is False,
        "no_final_eligibility": surface.get("final_eligibility_claimed") is False,
        "prohibited_visible": all(
            (c.get("prohibited_org_claims") or []) for c in (surface.get("cards") or [])
        ),
        "bridge_ok": "bridge_missing_organization_evidence_memory" not in fails,
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
        "campaign_block": 8,
        "fails": fails,
        "screens": screens,
        "profile_count": surface.get("profile_count"),
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
