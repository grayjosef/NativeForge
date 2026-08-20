"""Offline smoke for Campaign Block 02 eligibility evidence."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.combined_opportunity_workflow_service import (
    build_combined_opportunity_workflow,
    combined_workflow_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    DEMO_ROUTE_PATH,
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_campaign_block02_smoke_v1"


def _run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"nf_camp02_eligibility_smoke_{ts}_{uuid.uuid4().hex[:8]}"


def run_campaign_block02_smoke() -> dict[str, Any]:
    run_id = _run_id()
    wf = build_combined_opportunity_workflow()
    payload = build_sc_customer_demo_bridge_payload()
    surfaces: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        surfaces.append(
            {"surface": name, "status": "PASS" if ok else "FAIL", "detail": detail}
        )

    wf_fails = combined_workflow_invariant_failures(wf)
    bf = bridge_payload_invariant_failures(payload)
    eeh = wf.get("eligibility_evidence_handoff") or {}
    engine = payload.get("opportunity_engine") or {}
    bridge_eeh = (engine.get("combined_workflow") or {}).get(
        "eligibility_evidence_handoff"
    ) or {}

    add("demo_route", DEMO_ROUTE_PATH == "/?view=sc_customer_demo", DEMO_ROUTE_PATH)
    add(
        "eligibility_handoff_present",
        bool(eeh.get("sample_pairs")),
        f"pairs={eeh.get('pair_count')}",
    )
    add(
        "federal_visible",
        eeh.get("federal_pairs_visible") is True,
        "federal_pairs_visible",
    )
    add(
        "no_final_eligibility",
        eeh.get("final_eligibility_claimed") is False,
        "false",
    )
    add(
        "scoring_unchanged",
        eeh.get("scoring_math_changed") is False,
        "false",
    )
    add(
        "bridge_surface",
        bool(bridge_eeh.get("sample_pairs")) and not bf and not wf_fails,
        f"bf={bf} wf={wf_fails}",
    )
    add(
        "human_review",
        eeh.get("human_review_required") is True,
        "required",
    )

    failed = [s for s in surfaces if s["status"] != "PASS"]
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "status": "PASS" if not failed else "FAIL",
        "demo_route_path": DEMO_ROUTE_PATH,
        "surfaces": surfaces,
        "failed_surfaces": [s["surface"] for s in failed],
    }
    out = Path("artifacts/campaign_block02_smoke")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{run_id}.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result
