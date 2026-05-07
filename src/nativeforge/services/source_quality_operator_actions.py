"""Sprint 35: optional operator-ledger bridge for source quality recommendations."""

from __future__ import annotations

import hashlib
import uuid
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.domain.enums import (
    OperatorDecisionAction,
    OperatorDecisionItemType,
    OperatorDecisionSeverity,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import organizations as org_repo
from nativeforge.services import operator_action_service as oa_svc


def decision_id_for_source_quality_action(
    org_id: uuid.UUID,
    action_type: str,
    focus_lanes: list[str],
) -> str:
    """Stable id for dedupe when persisting a recommendation."""
    lane_key = ",".join(sorted({str(x).strip() for x in focus_lanes if str(x).strip()}))
    digest = hashlib.sha256(f"{org_id}:{action_type}:{lane_key}".encode()).hexdigest()[
        :16
    ]
    return f"nf_srcq:{action_type}:{org_id}:{digest}"


def _map_action_type_to_operator_enums(action_type: str) -> tuple[str, str]:
    if action_type in {
        "expand_native_priority_coverage",
        "target_lane_coverage",
        "diversify_source_mix",
    }:
        return (
            OperatorDecisionAction.expand_coverage.value,
            OperatorDecisionItemType.coverage_gap.value,
        )
    if action_type == "maintain_source_health":
        return (
            OperatorDecisionAction.improve_source_quality.value,
            OperatorDecisionItemType.source_recommendation.value,
        )
    if action_type == "clear_overdue_source_checks":
        return (
            OperatorDecisionAction.check_source.value,
            OperatorDecisionItemType.source_overdue.value,
        )
    return (
        OperatorDecisionAction.monitor.value,
        OperatorDecisionItemType.source_recommendation.value,
    )


def _coerce_severity(priority: str | None) -> str:
    raw = str(priority or "").strip()
    try:
        return OperatorDecisionSeverity(raw).value
    except ValueError:
        return OperatorDecisionSeverity.medium.value


def persist_source_quality_recommendations(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    recommended_operator_actions: list[dict[str, Any]],
    create_operator_actions: bool = False,
) -> list[dict[str, Any]]:
    """Create nf_operator_actions rows only when ``create_operator_actions`` is true.

    Rows are skipped when ``should_create_action`` is false on a recommendation, or when
    an active ledger row already exists for the deterministic ``decision_id`` (via the
    operator action repository).
    """
    if not create_operator_actions:
        return []

    org = org_repo.get_organization(session, org_id)
    if org is None:
        raise ValueError("organization not found")

    created: list[dict[str, Any]] = []
    for rec in recommended_operator_actions:
        if not isinstance(rec, dict):
            continue
        if not bool(rec.get("should_create_action")):
            continue
        action_type = str(rec.get("action_type") or "").strip()
        if not action_type:
            continue
        focus = [str(x) for x in (rec.get("focus_lanes") or []) if str(x).strip()]
        decision_id = decision_id_for_source_quality_action(org_id, action_type, focus)
        act, item_type = _map_action_type_to_operator_enums(action_type)
        sev = _coerce_severity(str(rec.get("priority")))
        title = str(rec.get("title") or action_type).strip()[:512] or action_type
        rationale = str(rec.get("rationale") or "")

        row, outcome = oa_svc.create_operator_action_from_decision_item(
            session,
            org=org,
            org_type=org_type,
            decision_item={
                "decision_id": decision_id,
                "item_type": item_type,
                "severity": sev,
                "recommended_action": act,
                "title": title,
                "rationale": rationale,
                "refs": {},
            },
        )
        if outcome == "created":
            created.append(row)
    return created
