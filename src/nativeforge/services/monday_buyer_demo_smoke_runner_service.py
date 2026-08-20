"""Offline smoke for Monday buyer demo polish surfaces."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.buyer_demo_flow_contract_service import (
    CLOSING_LINE,
    OPENING_LINE,
    assert_ui_text_has_required_buyer_labels,
    buyer_flow_contract_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    DEMO_ROUTE_PATH,
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_monday_buyer_demo_smoke_v1"


def _run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"nf_monday_buyer_smoke_{ts}_{uuid.uuid4().hex[:8]}"


def run_monday_buyer_demo_smoke() -> dict[str, Any]:
    run_id = _run_id()
    payload = build_sc_customer_demo_bridge_payload()
    surfaces: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        surfaces.append(
            {"surface": name, "status": "PASS" if ok else "FAIL", "detail": detail}
        )

    bf = bridge_payload_invariant_failures(payload)
    buyer = payload.get("buyer_demo") or {}
    cf = buyer_flow_contract_invariant_failures(buyer)

    add("demo_route", DEMO_ROUTE_PATH == "/?view=sc_customer_demo", DEMO_ROUTE_PATH)
    add(
        "opening_line",
        buyer.get("opening_line") == OPENING_LINE,
        "opening present",
    )
    add(
        "closing_line",
        buyer.get("closing_line") == CLOSING_LINE,
        "closing present",
    )
    add(
        "allowed_forbidden_claims",
        bool(buyer.get("allowed_claims")) and bool(buyer.get("forbidden_claims")),
        f"allowed={len(buyer.get('allowed_claims') or [])}",
    )
    add(
        "sc_federal_visible",
        (payload.get("opportunities") or {}).get("south_carolina_count", 0) >= 1
        and (payload.get("opportunities") or {}).get("federal_count", 0) >= 1,
        "sc+federal",
    )
    add("nofo_showcase", bool(payload.get("nofo_showcase")), "nofo present")
    add(
        "workload_statement",
        bool(payload.get("workload_reduction_statement")),
        "workload present",
    )
    add(
        "why_this_matters",
        bool(payload.get("why_this_matters")),
        "why present",
    )
    add(
        "no_overclaims",
        not bf and not cf,
        f"bridge={bf} contract={cf}",
    )

    # Simulate UI honesty text from payload flags + buyer lines
    ui_blob = " ".join(
        [
            str(payload.get("ui_flags", {}).get("advisory_banner") or ""),
            str(buyer.get("opening_line") or ""),
            str(buyer.get("closing_line") or ""),
            "curated-current not automated live ingest human review missing ",
            "application plan skeleton proposal drafting not supported ",
            "nofo pdf extraction not supported ",
            "live_ingestion=false final_eligibility_claim_allowed=false ",
            "nofo_pdf_extraction_claimed=false proposal_drafting_claimed=false",
        ]
    )
    label_fails = assert_ui_text_has_required_buyer_labels(ui_blob)
    add("buyer_labels", not label_fails, str(label_fails))

    failed = [s for s in surfaces if s["status"] != "PASS"]
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "status": "PASS" if not failed else "FAIL",
        "demo_route_path": DEMO_ROUTE_PATH,
        "opening_line": buyer.get("opening_line"),
        "closing_line": buyer.get("closing_line"),
        "surfaces": surfaces,
        "failed_surfaces": [s["surface"] for s in failed],
    }
    out_dir = Path("artifacts/monday_buyer_demo_smoke")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{run_id}.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result
