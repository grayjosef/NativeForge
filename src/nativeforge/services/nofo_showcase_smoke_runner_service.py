"""Offline smoke for NOFO showcase on SC Monday demo lane."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from nativeforge.services.nofo_showcase_demo_surface_service import (
    build_nofo_showcase_demo_surface,
    nofo_showcase_surface_invariant_failures,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    DEMO_ROUTE_PATH,
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_nofo_showcase_smoke_v1"
EXPECTED_SURFACES: tuple[str, ...] = (
    "demo_route_present",
    "sc_intelligence_visible",
    "federal_intelligence_visible",
    "field_status_labels_visible",
    "application_plan_visible",
    "checklist_visible",
    "evidence_provenance_visible",
    "human_review_visible",
    "missing_info_questions_visible",
    "no_proposal_drafting_claim",
    "no_nofo_pdf_claim",
    "no_live_ingest_claim",
)


def _run_id() -> str:
    ts = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    return f"nf_nofo_showcase_smoke_{ts}_{uuid.uuid4().hex[:8]}"


def run_nofo_showcase_offline_smoke() -> dict[str, Any]:
    run_id = _run_id()
    surface = build_nofo_showcase_demo_surface(write_fixtures=True)
    payload = build_sc_customer_demo_bridge_payload()
    surfaces: list[dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str) -> None:
        surfaces.append(
            {"surface": name, "status": "PASS" if ok else "FAIL", "detail": detail}
        )

    sf = nofo_showcase_surface_invariant_failures(surface)
    bf = bridge_payload_invariant_failures(payload)
    cards = surface.get("cards") or []
    sc_cards = [c for c in cards if c.get("source_layer") == "sc_state"]
    fed_cards = [c for c in cards if c.get("source_layer") == "federal"]

    add(
        "demo_route_present",
        DEMO_ROUTE_PATH == "/?view=sc_customer_demo",
        DEMO_ROUTE_PATH,
    )
    add("sc_intelligence_visible", len(sc_cards) >= 1, f"sc={len(sc_cards)}")
    add(
        "federal_intelligence_visible",
        len(fed_cards) >= 1,
        f"federal={len(fed_cards)}",
    )

    labels_ok = False
    for card in cards:
        counts = card.get("field_status_counts") or {}
        if any(
            k in counts
            for k in (
                "known",
                "inferred",
                "missing",
                "needs_confirmation",
                "not_in_source",
                "not_supported",
            )
        ):
            labels_ok = True
            break
    add(
        "field_status_labels_visible",
        labels_ok,
        str(cards[0].get("field_status_counts") if cards else {}),
    )

    plan_ok = all(
        (c.get("application_plan") or {}).get("recommendation_label") for c in cards
    )
    add("application_plan_visible", plan_ok and len(cards) >= 1, f"cards={len(cards)}")

    checklist_ok = all(
        (c.get("application_plan") or {}).get("application_checklist") for c in cards
    )
    add("checklist_visible", checklist_ok, "checklist present on cards")

    evid_ok = all(
        (c.get("evidence_provenance") or {}).get("captured_at") for c in cards
    )
    add("evidence_provenance_visible", evid_ok, "captured_at present")

    hr_ok = all(c.get("human_review_required") is True for c in cards)
    add("human_review_visible", hr_ok, "human_review_required=true")

    q_ok = all(
        (c.get("application_plan") or {}).get("missing_information_questions")
        for c in cards
    )
    add("missing_info_questions_visible", q_ok, "questions present")

    add(
        "no_proposal_drafting_claim",
        surface.get("proposal_drafting_claimed") is False,
        "proposal_drafting_claimed=false",
    )
    add(
        "no_nofo_pdf_claim",
        surface.get("nofo_pdf_extraction_claimed") is False,
        "nofo_pdf_extraction_claimed=false",
    )
    add(
        "no_live_ingest_claim",
        surface.get("live_ingest_claimed") is False and not sf and not bf,
        f"surface_fails={sf} bridge_fails={bf}",
    )

    failed = [s for s in surfaces if s["status"] != "PASS"]
    result = {
        "schema_version": SCHEMA_VERSION,
        "run_id": run_id,
        "status": "PASS" if not failed else "FAIL",
        "demo_route_path": DEMO_ROUTE_PATH,
        "selected_count": surface.get("selected_count"),
        "sc_selected_count": surface.get("sc_selected_count"),
        "federal_selected_count": surface.get("federal_selected_count"),
        "surfaces": surfaces,
        "failed_surfaces": [s["surface"] for s in failed],
        "invariant_failures": {"surface": sf, "bridge": bf},
    }
    out_dir = Path("artifacts/nofo_showcase_smoke")
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / f"{run_id}.json").write_text(
        json.dumps(result, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return result
