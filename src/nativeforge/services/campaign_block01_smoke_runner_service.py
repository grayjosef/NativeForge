"""Offline smoke for Campaign Block 01 opportunity engine foundation."""

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

SCHEMA_VERSION = "nf_campaign_block01_smoke_v1"


def _run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"nf_camp01_engine_smoke_{ts}_{uuid.uuid4().hex[:8]}"


def run_campaign_block01_smoke() -> dict[str, Any]:
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
    engine = payload.get("opportunity_engine") or {}

    add("demo_route", DEMO_ROUTE_PATH == "/?view=sc_customer_demo", DEMO_ROUTE_PATH)
    add(
        "sc_and_federal",
        (wf.get("counts") or {}).get("sc_state", 0) >= 1
        and (wf.get("counts") or {}).get("federal", 0) >= 1,
        str(wf.get("counts")),
    )
    add(
        "org_geo_does_not_filter_federal",
        wf.get("organization_geography_filters_federal") is False,
        "false",
    )
    add("no_live_ingest", wf.get("live_ingest_claimed") is False, "false")
    add(
        "engine_on_bridge",
        bool(engine) and not bf and not wf_fails,
        f"bf={bf} wf={wf_fails}",
    )
    add(
        "missing_visible",
        (wf.get("missing_data_summary") or {}).get("hidden_missing_data") is False,
        "visible",
    )
    add(
        "human_review",
        bool((wf.get("human_review") or {}).get("all_require_human_review")),
        "required",
    )

    failed = [s for s in surfaces if s["status"] != "PASS"]
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "status": "PASS" if not failed else "FAIL",
        "demo_route_path": DEMO_ROUTE_PATH,
        "counts": wf.get("counts"),
        "surfaces": surfaces,
        "failed_surfaces": [s["surface"] for s in failed],
    }
    out = Path("artifacts/campaign_block01_smoke")
    out.mkdir(parents=True, exist_ok=True)
    (out / f"{run_id}.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result
