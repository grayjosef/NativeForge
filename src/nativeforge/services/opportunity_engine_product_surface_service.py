"""Product foundation surface for SC customer demo (Campaign Block 01)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.combined_opportunity_workflow_service import (
    build_combined_opportunity_workflow,
    combined_workflow_invariant_failures,
)
from nativeforge.services.opportunity_engine_contract_service import (
    build_opportunity_engine_contract_vocab,
)
from nativeforge.services.sc_state_source_adapter_config_service import (
    build_sc_state_source_adapter_config,
    write_sc_state_source_adapter_config,
)

SCHEMA_VERSION = "nf_opportunity_engine_product_surface_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_opportunity_engine_product_surface(
    *, write_config: bool = False
) -> dict[str, Any]:
    if write_config:
        write_sc_state_source_adapter_config()
    workflow = build_combined_opportunity_workflow()
    cfg = build_sc_state_source_adapter_config()
    vocab = build_opportunity_engine_contract_vocab()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 1,
            "block_name": "NF Campaign Block 01 — Durable SC + Federal Opportunity Engine Foundation",
            "live_ingest_claimed": False,
            "source_activation_claimed": False,
            "final_eligibility_claim_allowed": False,
            "vocab": vocab,
            "sc_state_adapter": {
                "adapter_key": cfg.get("adapter_key"),
                "state_code": cfg.get("state_code"),
                "is_reference_state_implementation": cfg.get(
                    "is_reference_state_implementation"
                ),
                "data_mode_default": cfg.get("data_mode_default"),
                "live_ingest_claimed": False,
            },
            "combined_workflow": {
                "counts": workflow.get("counts"),
                "organization_geography_filters_federal": workflow.get(
                    "organization_geography_filters_federal"
                ),
                "missing_data_summary": workflow.get("missing_data_summary"),
                "human_review": workflow.get("human_review"),
                "eligibility_readiness_handoff": workflow.get(
                    "eligibility_readiness_handoff"
                ),
                "provenance_summary": workflow.get("provenance_summary"),
                "combined_ordering_sample": (workflow.get("combined_ordering") or [])[
                    :12
                ],
                "next_checks_sample": (workflow.get("next_checks") or [])[:8],
            },
            "buyer_summary": [
                "Durable SC state + federal opportunity engine foundation (curated-current)",
                "SC is reference-state adapter/config — not a product fork",
                "Federal opportunities remain visible for SC organizations",
                "Missing freshness/deadline fields stay visible",
                "Live ingest and source activation are not claimed",
            ],
        }
    )


def opportunity_engine_surface_invariant_failures(surface: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if surface.get("live_ingest_claimed") is True:
        fails.append("live_ingest")
    if surface.get("source_activation_claimed") is True:
        fails.append("activation")
    if surface.get("final_eligibility_claim_allowed") is True:
        fails.append("final_eligibility")
    cw = surface.get("combined_workflow") or {}
    counts = cw.get("counts") or {}
    if (counts.get("sc_state") or 0) < 1:
        fails.append("sc_count")
    if (counts.get("federal") or 0) < 1:
        fails.append("fed_count")
    if cw.get("organization_geography_filters_federal") is True:
        fails.append("org_geo_filter")
    # Full workflow invariants via rebuild
    fails.extend(
        combined_workflow_invariant_failures(build_combined_opportunity_workflow())
    )
    return fails
