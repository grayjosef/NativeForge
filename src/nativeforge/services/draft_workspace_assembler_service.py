"""Assemble draft workspace demo surface (Campaign Block 11)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.draft_workspace_builder_service import (
    build_draft_workspace_for_pair,
)
from nativeforge.services.draft_workspace_contract_service import (
    draft_workspace_invariant_failures,
)
from nativeforge.services.nofo_showcase_intelligence_pack_service import (
    SHOWCASE_OPPORTUNITY_IDS,
    load_selected_intelligence_pack,
)
from nativeforge.services.sc_monday_curated_pack_service import (
    grants_from_pack,
    load_sc_curated_opportunity_pack,
)
from nativeforge.services.sc_pilot_fixture_loader_service import load_sc_tribal_profiles

SCHEMA_VERSION = "nf_draft_workspace_assembler_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_draft_workspace_demo_surface(*, max_workspaces: int = 2) -> dict[str, Any]:
    profiles = load_sc_tribal_profiles()
    grants_by_id = {
        str(g.get("grant_id") or g.get("opportunity_id")): g
        for g in grants_from_pack(load_sc_curated_opportunity_pack())
    }
    pack = load_selected_intelligence_pack(require_file=False)
    intel_by_id = {
        o.get("opportunity_id"): o for o in (pack.get("opportunities") or [])
    }
    workspaces: list[dict[str, Any]] = []
    for oid in SHOWCASE_OPPORTUNITY_IDS[:max_workspaces]:
        opp = grants_by_id.get(oid)
        if not opp:
            continue
        profile = profiles[0]
        ws = build_draft_workspace_for_pair(
            profile, opp, nofo_intelligence=intel_by_id.get(oid)
        )
        workspaces.append(ws)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 11,
            "title": "Draft workspace (human-authored)",
            "workspace_count": len(workspaces),
            "workspaces": workspaces,
            "buyer_summary": [
                "Human-authored / imported prose organized by narrative scaffold sections",
                "Unsupported claims and missing citations are flagged — text is not rewritten",
                "AI drafting and generated prose remain disabled in this workspace",
                "Customer prose persistence is not claimed; human review is required",
                "Not submission-ready; not a final application",
            ],
            "ai_drafting_enabled": False,
            "generated_prose_present": False,
            "customer_prose_persistence_claimed": False,
            "final_application_claimed": False,
            "submission_ready_claimed": False,
            "proposal_drafting_claimed": False,
            "live_ingest_claimed": False,
            "human_review_required": True,
        }
    )


def draft_workspace_demo_surface_invariant_failures(
    surface: dict[str, Any],
) -> list[str]:
    fails: list[str] = []
    for key in (
        "ai_drafting_enabled",
        "generated_prose_present",
        "customer_prose_persistence_claimed",
        "final_application_claimed",
        "submission_ready_claimed",
        "proposal_drafting_claimed",
        "live_ingest_claimed",
    ):
        if surface.get(key) is True:
            fails.append(key)
    if (surface.get("workspace_count") or 0) < 1:
        fails.append("no_workspaces")
    for ws in surface.get("workspaces") or []:
        fails.extend(draft_workspace_invariant_failures(ws))
    return fails
