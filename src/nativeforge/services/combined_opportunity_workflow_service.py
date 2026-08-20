"""Combined SC state + federal opportunity workflow service (durable, offline).

Feeds customer workflow with normalized layers, handoff, and honesty labels.
Does not change scoring/match math.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.federal_opportunity_foundation_service import (
    enrich_federal_opportunity_for_sc_customer,
)
from nativeforge.services.opportunity_engine_contract_service import (
    durable_opportunity_invariant_failures,
    normalize_to_durable_opportunity,
)
from nativeforge.services.sc_monday_curated_pack_service import (
    grants_from_pack,
    load_sc_curated_opportunity_pack,
)
from nativeforge.services.sc_state_source_adapter_config_service import (
    build_sc_state_source_adapter_config,
    sc_state_adapter_invariant_failures,
)

SCHEMA_VERSION = "nf_combined_opportunity_workflow_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _order_key(row: dict[str, Any]) -> tuple[Any, ...]:
    # Deterministic: SC state first, then federal; within layer by title
    layer_rank = 0 if row.get("source_layer") == "sc_state" else 1
    title = str(row.get("title") or row.get("opportunity_id") or "").lower()
    oid = str(row.get("opportunity_id") or "")
    return (layer_rank, title, oid)


def build_combined_opportunity_workflow(
    *,
    pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Return combined state+federal workflow payload for SC customers."""
    doc = pack if pack is not None else load_sc_curated_opportunity_pack()
    grants = grants_from_pack(doc)
    sc_cfg = build_sc_state_source_adapter_config()

    state_opps: list[dict[str, Any]] = []
    federal_opps: list[dict[str, Any]] = []
    for g in grants:
        geo = str(g.get("funding_geography") or "")
        layer = str(g.get("source_layer") or "")
        if geo == "south_carolina" or layer == "sc_state":
            state_opps.append(normalize_to_durable_opportunity(g))
        elif geo == "federal" or layer == "federal":
            federal_opps.append(enrich_federal_opportunity_for_sc_customer(g))

    combined = sorted([*state_opps, *federal_opps], key=_order_key)
    by_layer = {
        "sc_state": [o for o in combined if o.get("source_layer") == "sc_state"],
        "federal": [o for o in combined if o.get("source_layer") == "federal"],
        "other_state": [o for o in combined if o.get("source_layer") == "other_state"],
    }

    missing_summary = {
        "opportunities_with_missing_fields": sum(
            1 for o in combined if o.get("missing_fields")
        ),
        "hidden_missing_data": False,
        "common_missing_fields": sorted(
            {f for o in combined for f in (o.get("missing_fields") or [])}
        )[:20],
    }
    human_review = {
        "required_count": sum(1 for o in combined if o.get("needs_operator_review")),
        "all_require_human_review": all(
            o.get("needs_operator_review") for o in combined
        )
        if combined
        else True,
    }
    next_checks = sorted(
        {c for o in combined for c in (o.get("operator_next_check") or [])}
    )[:25]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "title": "Combined SC state + federal opportunity workflow",
            "customer_reference_state": "SC",
            "live_ingest_claimed": False,
            "source_activation_claimed": False,
            "final_eligibility_claim_allowed": False,
            "organization_geography_filters_federal": False,
            "state_adapter": {
                "adapter_key": sc_cfg.get("adapter_key"),
                "is_reference_state_implementation": True,
            },
            "counts": {
                "total": len(combined),
                "sc_state": len(by_layer["sc_state"]),
                "federal": len(by_layer["federal"]),
                "other_state": len(by_layer["other_state"]),
            },
            "state_opportunities": by_layer["sc_state"],
            "federal_opportunities": by_layer["federal"],
            "combined_ordering": [
                {
                    "opportunity_id": o.get("opportunity_id"),
                    "source_layer": o.get("source_layer"),
                    "title": o.get("title"),
                    "data_mode": o.get("data_mode"),
                    "eligibility_handoff_state": o.get("eligibility_handoff_state"),
                    "opportunity_lifecycle_state": o.get("opportunity_lifecycle_state"),
                }
                for o in combined
            ],
            "source_layer_grouping": {
                k: [o.get("opportunity_id") for o in v] for k, v in by_layer.items()
            },
            "eligibility_readiness_handoff": {
                "by_state": {
                    s: sum(
                        1 for o in combined if o.get("eligibility_handoff_state") == s
                    )
                    for s in sorted(
                        {o.get("eligibility_handoff_state") for o in combined}
                    )
                },
                "no_final_eligibility_claim": True,
            },
            "missing_data_summary": missing_summary,
            "human_review": human_review,
            "next_checks": next_checks,
            "provenance_summary": {
                "notes_visible": True,
                "capture_dates_present": all(
                    bool(o.get("captured_at") or o.get("retrieved_at"))
                    for o in combined
                )
                if combined
                else False,
                "demo_real_isolation_labels": sorted(
                    {str(o.get("demo_real_isolation_label")) for o in combined}
                ),
            },
            "opportunities": combined,
        }
    )


def combined_workflow_invariant_failures(workflow: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if workflow.get("live_ingest_claimed") is True:
        fails.append("live_ingest_claimed")
    if workflow.get("source_activation_claimed") is True:
        fails.append("source_activation_claimed")
    if workflow.get("final_eligibility_claim_allowed") is True:
        fails.append("final_eligibility")
    if workflow.get("organization_geography_filters_federal") is True:
        fails.append("org_geo_filters_federal")
    counts = workflow.get("counts") or {}
    if (counts.get("sc_state") or 0) < 1:
        fails.append("missing_sc_state")
    if (counts.get("federal") or 0) < 1:
        fails.append("missing_federal")
    ordering = workflow.get("combined_ordering") or []
    # SC state entries should appear before federal in deterministic ordering
    saw_federal = False
    for item in ordering:
        if item.get("source_layer") == "federal":
            saw_federal = True
        if item.get("source_layer") == "sc_state" and saw_federal:
            fails.append("ordering_sc_after_federal")
            break
    for o in workflow.get("opportunities") or []:
        fails.extend(durable_opportunity_invariant_failures(o))
    if (workflow.get("missing_data_summary") or {}).get("hidden_missing_data") is True:
        fails.append("hidden_missing_data")
    if not (workflow.get("human_review") or {}).get("all_require_human_review"):
        # For curated Block 01 packs, all should need review
        fails.append("human_review_not_universal")
    cfg_fails = sc_state_adapter_invariant_failures(
        build_sc_state_source_adapter_config()
    )
    fails.extend([f"adapter:{f}" for f in cfg_fails])
    return fails
