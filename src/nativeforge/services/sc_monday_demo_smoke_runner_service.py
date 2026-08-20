"""Offline smoke runner for SC Monday customer demo lane."""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from nativeforge.services.sc_monday_demo_assembler_service import (
    build_sc_monday_demo_artifact,
    demo_artifact_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    DEMO_ROUTE_PATH,
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_sc_monday_demo_smoke_v1"
EXPECTED_SURFACES: tuple[str, ...] = (
    "sc_profiles_visible",
    "sc_opportunities_visible",
    "federal_opportunities_visible",
    "combined_state_federal_workflow",
    "eligibility_explanation",
    "missing_data_display",
    "human_review_display",
    "provenance_evidence_display",
    "buyer_what_nf_did",
    "buyer_next_actions",
    "no_live_ingest_claim",
    "no_final_eligibility_claim",
    "demo_route_present",
    "honest_data_labels",
)


def _run_id() -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"nf_sc_monday_smoke_{ts}_{uuid.uuid4().hex[:8]}"


def run_sc_monday_demo_smoke() -> dict[str, Any]:
    run_id = _run_id()
    art = build_sc_monday_demo_artifact()
    payload = build_sc_customer_demo_bridge_payload(artifact=art)
    surfaces: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        surfaces.append(
            {
                "surface": name,
                "status": "PASS" if ok else "FAIL",
                "detail": detail,
            }
        )

    af = demo_artifact_invariant_failures(art)
    bf = bridge_payload_invariant_failures(payload)
    add("sc_profiles_visible", art["profiles"]["profile_count"] >= 1, f"profiles={art['profiles']['profile_count']}")
    add(
        "sc_opportunities_visible",
        art["opportunities"]["south_carolina_count"] >= 1,
        f"sc={art['opportunities']['south_carolina_count']}",
    )
    add(
        "federal_opportunities_visible",
        art["opportunities"]["federal_count"] >= 1,
        f"federal={art['opportunities']['federal_count']}",
    )
    add(
        "combined_state_federal_workflow",
        art["combined_summary"]["south_carolina_row_count"] >= 1
        and art["combined_summary"]["federal_row_count"] >= 1,
        f"rows={art['combined_summary']['row_count']}",
    )
    add(
        "eligibility_explanation",
        any(r.get("blockers") is not None for r in art["rows"]),
        "blockers_field_present",
    )
    add(
        "missing_data_display",
        art["missing_data_summary"].get("hidden_missing_data") is False,
        "hidden_missing_data=false",
    )
    add(
        "human_review_display",
        art["combined_summary"]["human_review_required_count"] >= 1,
        f"human_review={art['combined_summary']['human_review_required_count']}",
    )
    add(
        "provenance_evidence_display",
        bool(art["provenance_evidence_summary"].get("notes_visible")),
        "notes_visible",
    )
    add("buyer_what_nf_did", bool(art.get("what_nativeforge_did")), "story_present")
    add("buyer_next_actions", bool(art.get("next_actions")), "next_actions_present")
    add("no_live_ingest_claim", art.get("live_ingestion") is False, "live_ingestion=false")
    add(
        "no_final_eligibility_claim",
        art.get("final_eligibility_claim_allowed") is False,
        "final_claim=false",
    )
    add("demo_route_present", payload.get("demo_route_path") == DEMO_ROUTE_PATH, DEMO_ROUTE_PATH)
    labels_ok = all(
        r.get("data_label") in {"curated_current", "fixture_demo", "rule_reference"}
        and r.get("live_ingest_not_claimed") is True
        for r in art["rows"]
    )
    add("honest_data_labels", labels_ok and not af and not bf, f"af={af} bf={bf}")

    failures = [s["surface"] for s in surfaces if s["status"] != "PASS"]
    overall = "PASS" if not failures else "FAIL"
    return {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "overall_status": overall,
        "smoke_mode": "offline_sc_monday_demo",
        "demo_route_path": DEMO_ROUTE_PATH,
        "content_digest": art.get("content_digest"),
        "surfaces": surfaces,
        "failures": failures,
        "expected_surfaces": list(EXPECTED_SURFACES),
    }


def write_sc_monday_demo_smoke_result(
    result: dict[str, Any] | None = None,
    *,
    out_dir: Path | None = None,
) -> Path:
    doc = result if result is not None else run_sc_monday_demo_smoke()
    directory = out_dir or Path("artifacts/sc_monday_smoke")
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{doc['run_id']}.json"
    path.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path
