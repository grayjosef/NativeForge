"""Sprint 248: Stage 12 guided demo path advisory bundle (synthetic fixtures only)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.funding_opportunity_intake_hardened_record_service import (
    build_hardened_opportunity_record,
)
from nativeforge.services.matching_readiness_record_service import (
    build_matching_readiness_record,
)
from nativeforge.services.native_relevance_classification_record_service import (
    build_native_relevance_classification_record,
)
from nativeforge.services.org_applicant_profile_hardened_record_service import (
    build_hardened_org_applicant_profile_record,
)
from nativeforge.services.stage12_demo_dataset_service import (
    STAGE12_NAMESPACE,
    load_stage12_dataset_bundle,
    load_stage12_opportunities,
    load_stage12_profile,
    load_stage12_sources,
)
from nativeforge.services.stage12_guided_flow_step_vocabulary_service import (
    GUIDED_FLOW_STEPS,
    STEP_LABELS,
    build_guided_flow_step_contract,
)

SCHEMA_VERSION = "nf_stage12_guided_demo_path_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _activation_readiness_preview(sources: list[dict[str, Any]]) -> dict[str, Any]:
    """Preview-only activation readiness — no execution."""
    items = []
    for src in sources:
        posture = str(src.get("quality_posture") or "unknown")
        ready = posture in {"strong", "adequate"}
        items.append(
            {
                "source_fixture_key": src["fixture_key"],
                "source_name": src["source_name"],
                "quality_posture": posture,
                "activation_readiness_preview": (
                    "ready_for_future_activation_review_packet"
                    if ready
                    else "not_ready"
                ),
                "may_activate_now": False,
                "may_execute_activation_now": False,
                "preview_only": True,
            }
        )
    return {
        "schema_version": "nf_stage12_activation_readiness_preview_v1",
        "source_previews": items,
        "no_source_activation_execution": True,
        "human_gate_required": True,
    }


def _operator_decision_preview(
    *,
    primary_opp: dict[str, Any],
    match_record: dict[str, Any],
) -> dict[str, Any]:
    return {
        "schema_version": "nf_stage12_operator_decision_preview_v1",
        "primary_opportunity_fixture_key": primary_opp["fixture_key"],
        "match_label": match_record["match_label"],
        "readiness_label": match_record["readiness_label"],
        "needs_operator_review": match_record["match_label"] == "needs_operator_review",
        "final_eligibility_claim_blocked": True,
        "verified_or_approved": False,
        "operator_action_required": True,
        "preview_only": True,
    }


def _evidence_audit_preview(
    *,
    org_id: uuid.UUID | None,
    steps_completed: list[str],
) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat()
    return {
        "schema_version": "nf_stage12_evidence_audit_preview_v1",
        "org_id": str(org_id) if org_id else None,
        "demo_namespace": STAGE12_NAMESPACE,
        "audit_events": [
            {
                "event_type": "stage12_guided_step_viewed",
                "step_id": step,
                "timestamp": now,
                "synthetic": True,
            }
            for step in steps_completed
        ],
        "evidence_pack_available": True,
        "no_live_ingestion": True,
        "preview_only": True,
    }


def build_stage12_guided_demo_path(
    *,
    org_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    dataset = load_stage12_dataset_bundle()
    sources = load_stage12_sources()
    profile = load_stage12_profile()
    opportunities = load_stage12_opportunities()
    profile_record = build_hardened_org_applicant_profile_record(profile)

    intake_previews = [
        build_hardened_opportunity_record(
            opp,
            fixture_key=opp["fixture_key"],
            batch_candidates=opportunities,
        )
        for opp in opportunities
    ]
    relevance_previews = [
        build_native_relevance_classification_record(opp) for opp in opportunities
    ]
    match_records = [
        build_matching_readiness_record(
            opp,
            profile,
            pair_meta={
                "fixture_key": f"nf_stage12_pair_{opp['fixture_key']}",
                "human_confirmation_present": False,
                "operator_review_completed": False,
                "profile_mutation_requested": False,
            },
        )
        for opp in opportunities
    ]
    primary_opp = next(
        o
        for o in opportunities
        if o["demo_archetype"] == "native_specific_tribal_government"
    )
    primary_match = next(
        r
        for r in match_records
        if r["fixture_key"] == f"nf_stage12_pair_{primary_opp['fixture_key']}"
    )

    step_payloads = {
        "source-discovery": {
            "sources": sources,
            "source_count": len(sources),
            "fictional_only": True,
        },
        "source-quality-review": {
            "sources": sources,
            "quality_summary": {
                s["fixture_key"]: s.get("quality_posture") for s in sources
            },
        },
        "activation-readiness-preview": _activation_readiness_preview(sources),
        "opportunity-intake": {
            "intake_previews": intake_previews,
            "stale_opportunities_shown": [
                o["fixture_key"] for o in opportunities if o.get("stale")
            ],
        },
        "native-relevance-review": {
            "relevance_previews": relevance_previews,
            "broad_vs_specific_labels_honest": True,
        },
        "profile-match-readiness": {
            "profile_preview": profile_record,
            "match_records": match_records,
            "no_final_eligibility_without_operator": True,
        },
        "operator-decision": _operator_decision_preview(
            primary_opp=primary_opp,
            match_record=primary_match,
        ),
        "evidence-audit-trail": _evidence_audit_preview(
            org_id=org_id,
            steps_completed=list(GUIDED_FLOW_STEPS),
        ),
    }

    steps = []
    for step_id in GUIDED_FLOW_STEPS:
        steps.append(
            {
                "step_id": step_id,
                "label": STEP_LABELS[step_id],
                "payload": step_payloads[step_id],
                "hard_invariants_preserved": True,
            }
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "org_id": str(org_id) if org_id else None,
            "demo_namespace": STAGE12_NAMESPACE,
            "dataset": dataset,
            "guided_flow": build_guided_flow_step_contract(),
            "steps": steps,
            "reconciliation": {
                "operator_guidance": (
                    "canonical_operator_guidance_reconciliation_service"
                ),
                "readiness_terminology": (
                    "readiness_terminology_reconciliation_service"
                ),
            },
            "isolated": True,
            "fictional_only": True,
            "preview_only": True,
            "no_live_ingestion": True,
            "no_source_activation_execution": True,
            "synthetic_fixtures_only": True,
        }
    )
