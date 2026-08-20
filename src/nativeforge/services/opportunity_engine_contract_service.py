"""Durable opportunity/source contracts for NativeForge campaign Block 01.

Offline / curated-current foundation. Does not claim live ingest or activate sources.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.sc_monday_go_contract_service import (
    go_contract_invariant_failures,
    normalize_opportunity_to_go_contract,
)

SCHEMA_VERSION = "nf_opportunity_engine_contract_v1"

SOURCE_LAYERS: frozenset[str] = frozenset({"sc_state", "federal", "other_state"})
DATA_MODES: frozenset[str] = frozenset(
    {
        "curated_current",
        "fixture_demo",
        "live_ingest",
        "live_ingest_not_claimed",
    }
)
SOURCE_HEALTH_LABELS: frozenset[str] = frozenset(
    {
        "unknown",
        "healthy",
        "stale",
        "degraded",
        "failing",
        "attention_needed",
        "curated_offline",
    }
)
LIFECYCLE_STATES: frozenset[str] = frozenset(
    {
        "discovered",
        "normalized",
        "curated_current",
        "needs_confirmation",
        "ready_for_human_review",
        "paused",
        "retired",
        "live_ingest_blocked",
    }
)
ELIGIBILITY_HANDOFF_STATES: frozenset[str] = frozenset(
    {
        "not_started",
        "evidence_partial",
        "needs_human_review",
        "blocked_missing_evidence",
        "ready_for_pursuit_decision",
    }
)

BLOCK01_ALLOWED_DATA_MODES: frozenset[str] = frozenset(
    {"curated_current", "fixture_demo", "live_ingest_not_claimed"}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_opportunity_engine_contract_vocab() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_layers": sorted(SOURCE_LAYERS),
            "data_modes": sorted(DATA_MODES),
            "block01_allowed_data_modes": sorted(BLOCK01_ALLOWED_DATA_MODES),
            "source_health_labels": sorted(SOURCE_HEALTH_LABELS),
            "lifecycle_states": sorted(LIFECYCLE_STATES),
            "eligibility_handoff_states": sorted(ELIGIBILITY_HANDOFF_STATES),
            "live_ingest_default": False,
            "source_activation_default": False,
            "final_eligibility_claim_allowed_default": False,
        }
    )


def _derive_lifecycle(row: dict[str, Any]) -> str:
    if row.get("data_mode") == "live_ingest":
        return "live_ingest_blocked"  # Block 01 never promotes to live
    if row.get("current_round_status") == "needs_confirmation":
        return "needs_confirmation"
    if row.get("missing_fields"):
        return "ready_for_human_review"
    if row.get("data_mode") in {"curated_current", "fixture_demo"}:
        return "curated_current"
    return "normalized"


def _derive_eligibility_handoff(row: dict[str, Any]) -> str:
    missing = list(row.get("missing_fields") or [])
    if not row.get("needs_operator_review") and not missing:
        return "ready_for_pursuit_decision"
    if "eligibility_summary" in missing:
        return "blocked_missing_evidence"
    if missing:
        return "evidence_partial"
    return "needs_human_review"


def normalize_to_durable_opportunity(row: dict[str, Any]) -> dict[str, Any]:
    """Normalize a raw/curated row into durable opportunity engine fields."""
    attempted_live = (
        str(row.get("data_mode") or "") == "live_ingest"
        or row.get("live_ingest_claimed") is True
        or row.get("live_ingestion_claimed") is True
    )
    base = normalize_opportunity_to_go_contract(row)
    data_mode = str(base.get("data_mode") or "curated_current")
    if attempted_live or data_mode == "live_ingest":
        # Block 01 refuses silent live mode — force honest denial label
        data_mode = "live_ingest_not_claimed"
        base["data_mode"] = data_mode
        base["live_ingest_claimed"] = False
        base["live_ingestion_claimed"] = False
        base["live_ingest_not_claimed"] = True
        base["automated_refresh_claimed"] = False

    source_id = str(
        base.get("source_id")
        or base.get("source_name")
        or base.get("agency")
        or "unknown_source"
    )
    retrieval_method = str(
        base.get("retrieval_method") or "curated_pack_offline_normalize_v1"
    )
    source_health = str(base.get("source_health") or "curated_offline")
    if source_health not in SOURCE_HEALTH_LABELS:
        source_health = "unknown"

    lifecycle = _derive_lifecycle(base)
    handoff = _derive_eligibility_handoff(base)

    # Preserve missing freshness/deadline visibility — never drop the lists
    missing = list(base.get("missing_fields") or [])
    if not base.get("freshness_label"):
        if "freshness_label" not in missing:
            missing.append("freshness_label")
    if base.get("deadline_status") in {None, "", "unknown"}:
        if "deadline_date" not in missing:
            missing.append("deadline_date")

    base.update(
        {
            "engine_schema_version": SCHEMA_VERSION,
            "source_id": source_id,
            "retrieval_method": retrieval_method,
            "source_health": source_health,
            "opportunity_lifecycle_state": lifecycle,
            "eligibility_handoff_state": handoff,
            "missing_fields": missing,
            "final_eligibility_claim_allowed": False,
            "live_ingest_claimed": False,
            "source_activation_claimed": False,
            "upgrade_path_to_live_ingest": (
                "Requires explicit Mayhem approval, validated connector, "
                "and live_ingest evidence — not claimed in Block 01"
            ),
        }
    )
    return _json_safe(base)


def durable_opportunity_invariant_failures(row: dict[str, Any]) -> list[str]:
    fails = [
        f
        for f in go_contract_invariant_failures(row)
        if f != "data_mode_not_curated_current"
    ]
    if (
        row.get("source_layer") not in SOURCE_LAYERS
        and row.get("source_layer") != "unknown"
    ):
        fails.append(f"bad_source_layer:{row.get('source_layer')}")
    mode = row.get("data_mode")
    if mode not in BLOCK01_ALLOWED_DATA_MODES:
        fails.append(f"data_mode_not_allowed_in_block01:{mode}")
    if mode == "live_ingest" or row.get("live_ingest_claimed") is True:
        fails.append("curated_cannot_claim_live_automation")
    if row.get("source_activation_claimed") is True:
        fails.append("source_activation_claimed")
    if row.get("final_eligibility_claim_allowed") is True:
        fails.append("final_eligibility_true")
    if "missing_fields" not in row:
        fails.append("missing_fields_key_absent")
    # Freshness/deadline must remain visible when unknown
    if row.get("deadline_status") == "unknown":
        if "deadline_date" not in (row.get("missing_fields") or []):
            fails.append("unknown_deadline_not_in_missing_fields")
    if not row.get("freshness_label"):
        fails.append("freshness_label_missing")
    for key in (
        "source_id",
        "retrieval_method",
        "source_health",
        "opportunity_lifecycle_state",
        "eligibility_handoff_state",
        "demo_real_isolation_label",
    ):
        if not row.get(key):
            fails.append(f"missing_{key}")
    return fails
