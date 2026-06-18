"""Sprint 163: discovery operator continuity rollup (offline, deterministic).

Stitches Sprint 36–38 artifacts (source coverage plan, candidate registry, onboarding
decision pack) into one operator continuity rollup for discovery-engine pivot review.
Does not activate sources, scrape, or perform network I/O.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.lib.demo_isolation import OrgType
from nativeforge.services import discovery_source_quality_service as dsq_svc
from nativeforge.services import source_candidate_registry_service as scr_svc
from nativeforge.services import source_coverage_plan_service as scp_svc
from nativeforge.services import source_onboarding_decision_pack_service as sodp_svc

SCHEMA_VERSION = "nf_discovery_operator_continuity_rollup_v1"

_BLOCKED_ACTIONS: tuple[str, ...] = (
    "Continuity rollup is review-only; may_activate_sources remains false in onboarding pack.",
    "No source activation, scraping, live ingestion, or customer data access from this rollup.",
    "Registry candidates are planning seeds only—not eligibility confirmation.",
    "Activation boundary flags in onboarding pack must be honored before any future activation.",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _ensure_child_artifacts(sq: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    base = dict(sq)
    plan = base.get("source_coverage_plan")
    if not isinstance(plan, dict) or not plan.get("schema_version"):
        plan = scp_svc.build_source_coverage_plan(base)
        base["source_coverage_plan"] = plan
    reg = base.get("source_candidate_registry")
    if not isinstance(reg, dict) or not reg.get("candidate_sources"):
        reg = scr_svc.build_source_candidate_registry(base)
        base["source_candidate_registry"] = reg
    pack = base.get("source_onboarding_decision_pack")
    if not isinstance(pack, dict) or not pack.get("candidate_reviews"):
        pack = sodp_svc.build_source_onboarding_decision_pack(base)
        base["source_onboarding_decision_pack"] = pack
    return plan, reg, pack


def _gap_flags(
    plan: dict[str, Any],
    reg: dict[str, Any],
    pack: dict[str, Any],
    sq: dict[str, Any],
) -> list[str]:
    flags: list[str] = []
    missing = list(sq.get("missing_lanes") or [])
    if missing:
        flags.append(f"missing_priority_lanes:{len(missing)}")
    weak = list(sq.get("weak_lanes") or [])
    if weak:
        flags.append(f"weak_priority_lanes:{len(weak)}")
    posture = str(plan.get("coverage_posture", {}).get("posture") or sq.get("posture") or "")
    if posture in {"weak", "critical"}:
        flags.append(f"coverage_posture:{posture}")
    decision = pack.get("decision_posture") or {}
    if int(decision.get("legal_tos_review_count") or 0) > 0:
        flags.append("legal_tos_review_candidates_present")
    if int(decision.get("deferred_count") or 0) > 0:
        flags.append("deferred_onboarding_candidates_present")
    reg_summary = reg.get("registry_posture") or {}
    if int(reg_summary.get("candidate_count") or 0) == 0:
        flags.append("empty_candidate_registry")
    plan_risk = plan.get("risk_flags") or []
    for rf in plan_risk[:5]:
        if isinstance(rf, str) and rf.strip():
            flags.append(f"plan_risk:{rf}")
    return flags


def build_discovery_operator_continuity_rollup(
    source_quality: dict[str, Any],
) -> dict[str, Any]:
    """Return nf_discovery_operator_continuity_rollup_v1 from source_quality lineage."""
    sq = dict(source_quality)
    plan, reg, pack = _ensure_child_artifacts(sq)

    org_id = str(sq.get("organization_id") or "")
    gen_at = str(sq.get("generated_at") or "")
    posture = str(sq.get("posture") or "adequate")
    dqs = int(sq.get("data_quality_score") or 0)
    active_n = int((sq.get("source_counts") or {}).get("active") or 0)

    reg_summary = dict(reg.get("registry_posture") or {})
    decision = dict(pack.get("decision_posture") or {})
    activation = dict(pack.get("activation_boundary") or {})

    ready_ids = [
        str(r.get("candidate_id") or "")
        for r in (pack.get("candidate_reviews") or [])
        if str(r.get("review_recommendation") or "") == "ready_for_operator_review"
    ]
    blocked_ids = [
        str(r.get("candidate_id") or "")
        for r in (pack.get("candidate_reviews") or [])
        if str(r.get("review_recommendation") or "") != "ready_for_operator_review"
    ]

    out: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "organization_scope": {
            "organization_id": org_id,
            "generated_at": gen_at,
            "plane": str((sq.get("organization_scope") or {}).get("plane") or ""),
            "is_demo": bool(sq.get("is_demo")),
        },
        "lineage": {
            "source_quality_schema_version": str(sq.get("schema_version") or ""),
            "source_coverage_plan_schema_version": str(plan.get("schema_version") or ""),
            "source_candidate_registry_schema_version": str(reg.get("schema_version") or ""),
            "source_onboarding_decision_pack_schema_version": str(
                pack.get("schema_version") or ""
            ),
        },
        "coverage_continuity_summary": {
            "posture": posture,
            "data_quality_score": dqs,
            "active_source_count": active_n,
            "missing_lane_count": len(sq.get("missing_lanes") or []),
            "sequenced_plan_steps": len(plan.get("sequenced_plan") or []),
            "plan_summary": str(plan.get("summary") or ""),
        },
        "registry_continuity_summary": {
            "candidate_count": int(reg_summary.get("candidate_count") or 0),
            "high_priority_candidate_count": int(
                reg_summary.get("high_priority_candidate_count") or 0
            ),
            "registry_summary": str(reg.get("summary") or ""),
        },
        "onboarding_continuity_summary": {
            "ready_for_review_count": int(decision.get("ready_for_review_count") or 0),
            "legal_tos_review_count": int(decision.get("legal_tos_review_count") or 0),
            "deferred_count": int(decision.get("deferred_count") or 0),
            "may_activate_sources": bool(activation.get("may_activate_sources")),
            "requires_human_approval": bool(activation.get("requires_human_approval")),
            "pack_summary": str(pack.get("summary") or ""),
        },
        "ready_onboarding_candidate_ids": ready_ids[:50],
        "blocked_onboarding_candidate_ids": blocked_ids[:50],
        "gap_flags": _gap_flags(plan, reg, pack, sq),
        "blocked_action_summary": list(_BLOCKED_ACTIONS),
        "recommended_next_safe_action": (
            "Review-only: walk coverage plan sequenced steps, registry candidates, and "
            "onboarding candidate reviews as a desk exercise; honor activation_boundary "
            "flags before any separate human-approved activation process."
        ),
    }
    return _json_safe(out)


def build_discovery_operator_continuity_rollup_from_session(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Build rollup from persisted registry via discovery source quality."""
    sq = dsq_svc.build_discovery_source_quality(
        session,
        org_id=org_id,
        org_type=org_type,
        now=now or datetime.now(UTC),
    )
    return build_discovery_operator_continuity_rollup(sq)
