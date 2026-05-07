"""Sprint 18: operator action ledger — create, lifecycle, summary, exports."""

from __future__ import annotations

import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.db.models import NfOperatorAction, Organization, is_demo_for_org_type
from nativeforge.domain.enums import (
    AuditAction,
    OperatorActionCreatedFrom,
    OperatorActionResolutionCode,
    OperatorActionStatus,
    OperatorDecisionAction,
    OperatorDecisionItemType,
    OperatorDecisionSeverity,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import audit_events as audit_repo
from nativeforge.repositories import operator_actions as oa_repo
from nativeforge.services.discovery_operator_workbench_service import (
    DECISION_PACK_SCHEMA_VERSION,
)

NF_OPERATOR_ACTION_SCHEMA_VERSION = "nf_operator_action_v1"

_ACTIVE = frozenset(
    {
        OperatorActionStatus.open.value,
        OperatorActionStatus.in_progress.value,
        OperatorActionStatus.deferred.value,
        OperatorActionStatus.reopened.value,
    }
)


def _coerce_dt(v: object | None) -> datetime | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v
    if isinstance(v, str):
        return datetime.fromisoformat(v.replace("Z", "+00:00"))
    raise TypeError("expected datetime or iso string")


def _dt(v: object | None) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def _parse_uuid_val(v: object | None) -> uuid.UUID | None:
    if v is None:
        return None
    try:
        return uuid.UUID(str(v))
    except ValueError:
        return None


def _decision_action_from_item(item: dict[str, Any]) -> str:
    for key in ("recommended_action", "action"):
        raw = item.get(key)
        if raw is not None and str(raw).strip():
            return str(raw)
    return OperatorDecisionAction.monitor.value


def _refs_block(row: NfOperatorAction) -> dict[str, Any]:
    return {
        "source_registry_id": str(row.source_registry_id)
        if row.source_registry_id
        else None,
        "review_item_id": str(row.review_item_id) if row.review_item_id else None,
        "intake_run_id": str(row.intake_run_id) if row.intake_run_id else None,
        "intake_candidate_id": str(row.intake_candidate_id)
        if row.intake_candidate_id
        else None,
        "grant_spark_id": str(row.grant_spark_id) if row.grant_spark_id else None,
        "source_check_run_id": str(row.source_check_run_id)
        if row.source_check_run_id
        else None,
        "coverage_gap_id": row.coverage_gap_id,
    }


def operator_action_to_dict(row: NfOperatorAction) -> dict[str, Any]:
    return {
        "schema_version": NF_OPERATOR_ACTION_SCHEMA_VERSION,
        "id": str(row.id),
        "organization_id": str(row.organization_id),
        "is_demo": row.is_demo,
        "decision_id": row.decision_id,
        "decision_schema_version": row.decision_schema_version,
        "source_decision_item_json": row.source_decision_item_json,
        "status": row.status,
        "severity": row.severity,
        "item_type": row.item_type,
        "action": row.action,
        "action_title": row.action_title,
        "action_summary": row.action_summary,
        "operator_action": row.operator_action,
        "assigned_to": row.assigned_to,
        "due_at": _dt(row.due_at),
        "started_at": _dt(row.started_at),
        "resolved_at": _dt(row.resolved_at),
        "deferred_until": _dt(row.deferred_until),
        "dismissed_at": _dt(row.dismissed_at),
        "resolution_notes": row.resolution_notes,
        "operator_notes": row.operator_notes,
        "resolution_code": row.resolution_code,
        "refs": _refs_block(row),
        "created_from": row.created_from,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }


def _coverage_gap_key_from_refs(refs: dict[str, Any]) -> str | None:
    for k in ("gap_id", "recommendation_id", "coverage_gap_id"):
        v = refs.get(k)
        if v is not None and str(v).strip():
            return str(v)[:256]
    return None


def _populate_fks_from_refs(row: NfOperatorAction, refs: dict[str, Any]) -> None:
    row.source_registry_id = _parse_uuid_val(
        refs.get("source_registry_id"),
    )
    row.review_item_id = _parse_uuid_val(
        refs.get("review_item_id") or refs.get("discovery_review_item_id"),
    )
    row.intake_run_id = _parse_uuid_val(refs.get("intake_run_id"))
    row.intake_candidate_id = _parse_uuid_val(refs.get("intake_candidate_id"))
    row.grant_spark_id = _parse_uuid_val(refs.get("grant_spark_id"))
    row.source_check_run_id = _parse_uuid_val(refs.get("source_check_run_id"))
    row.coverage_gap_id = _coverage_gap_key_from_refs(refs)


def _validate_enum_value(label: str, value: str, enum_cls: type) -> str:
    try:
        return enum_cls(value).value  # type: ignore[arg-type]
    except ValueError as e:
        raise ValueError(f"invalid {label}: {value}") from e


def create_operator_action_from_decision_item(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    decision_item: dict[str, Any],
    assigned_to: str | None = None,
    due_at: datetime | None = None,
    operator_notes: str | None = None,
    force_new: bool = False,
) -> tuple[dict[str, Any], str]:
    """Returns (serialized dict, outcome: 'created'|'reused'|'superseded')."""
    did = str(decision_item.get("decision_id") or "").strip()
    if not did:
        raise ValueError("decision_item.decision_id is required")
    existing = oa_repo.find_active_operator_action_by_decision_id(
        session,
        org_id=org.id,
        org_type=org_type,
        decision_id=did,
    )
    if existing is not None and not force_new:
        return operator_action_to_dict(existing), "reused"

    if existing is not None and force_new:
        now = datetime.now(UTC)
        existing.status = OperatorActionStatus.resolved.value
        existing.resolved_at = existing.resolved_at or now
        existing.resolution_code = OperatorActionResolutionCode.duplicate.value
        existing.resolution_notes = (
            (existing.resolution_notes or "").strip()
            + "\nSuperseded by new operator action (force_new)."
        ).strip()
        oa_repo.update_operator_action(session, existing)
        _audit(
            session,
            org=org,
            action=AuditAction.operator_action_resolved,
            payload={
                "operator_action_id": str(existing.id),
                "decision_id": existing.decision_id,
                "reason": "force_new_supersede",
            },
        )

    item_type = _validate_enum_value(
        "item_type",
        str(decision_item.get("item_type") or ""),
        OperatorDecisionItemType,
    )
    severity = _validate_enum_value(
        "severity",
        str(decision_item.get("severity") or OperatorDecisionSeverity.medium.value),
        OperatorDecisionSeverity,
    )
    act = _validate_enum_value(
        "action",
        _decision_action_from_item(decision_item),
        OperatorDecisionAction,
    )
    title = str(decision_item.get("title") or "Operator action").strip()[:512]
    summary = decision_item.get("rationale")
    op_act = (
        decision_item.get("operator_action") or decision_item.get("rationale") or None
    )
    if op_act is not None:
        op_act = str(op_act)

    row = NfOperatorAction(
        id=uuid.uuid4(),
        organization_id=org.id,
        is_demo=is_demo_for_org_type(org.org_type),
        decision_id=did,
        decision_schema_version=DECISION_PACK_SCHEMA_VERSION,
        source_decision_item_json=decision_item,
        action_title=title or "Operator action",
        action_summary=str(summary) if summary is not None else None,
        operator_action=op_act,
        item_type=item_type,
        severity=severity,
        action=act,
        status=OperatorActionStatus.open.value,
        assigned_to=assigned_to,
        due_at=due_at,
        operator_notes=operator_notes,
        created_from=OperatorActionCreatedFrom.decision_pack.value,
    )
    refs = decision_item.get("refs") or {}
    if isinstance(refs, dict):
        _populate_fks_from_refs(row, refs)

    oa_repo.create_operator_action(session, row)
    _audit(
        session,
        org=org,
        action=AuditAction.operator_action_created,
        payload={
            "operator_action_id": str(row.id),
            "decision_id": row.decision_id,
            "from": "decision_pack",
        },
    )
    out = operator_action_to_dict(row)
    return out, "created"


def create_operator_action_manual(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    decision_id: str,
    action_title: str,
    operator_action: str | None,
    item_type: str,
    severity: str,
    action: str,
    assigned_to: str | None = None,
    due_at: datetime | None = None,
    operator_notes: str | None = None,
    action_summary: str | None = None,
    source_registry_id: uuid.UUID | None = None,
    review_item_id: uuid.UUID | None = None,
    intake_run_id: uuid.UUID | None = None,
    source_check_run_id: uuid.UUID | None = None,
) -> dict[str, Any]:
    did = decision_id.strip()
    if not did:
        raise ValueError("decision_id is required")
    existing = oa_repo.find_active_operator_action_by_decision_id(
        session,
        org_id=org.id,
        org_type=org_type,
        decision_id=did,
    )
    if existing is not None:
        raise ValueError(
            "An active operator action already exists for this decision_id",
        )

    it = _validate_enum_value("item_type", item_type, OperatorDecisionItemType)
    sev = _validate_enum_value("severity", severity, OperatorDecisionSeverity)
    act = _validate_enum_value("action", action, OperatorDecisionAction)

    row = NfOperatorAction(
        id=uuid.uuid4(),
        organization_id=org.id,
        is_demo=is_demo_for_org_type(org.org_type),
        decision_id=did,
        decision_schema_version=None,
        source_decision_item_json=None,
        action_title=action_title.strip()[:512],
        action_summary=action_summary,
        operator_action=operator_action,
        item_type=it,
        severity=sev,
        action=act,
        status=OperatorActionStatus.open.value,
        assigned_to=assigned_to,
        due_at=due_at,
        operator_notes=operator_notes,
        source_registry_id=source_registry_id,
        review_item_id=review_item_id,
        intake_run_id=intake_run_id,
        source_check_run_id=source_check_run_id,
        created_from=OperatorActionCreatedFrom.manual.value,
    )
    oa_repo.create_operator_action(session, row)
    _audit(
        session,
        org=org,
        action=AuditAction.operator_action_created,
        payload={
            "operator_action_id": str(row.id),
            "decision_id": row.decision_id,
            "from": "manual",
        },
    )
    return operator_action_to_dict(row)


def patch_operator_action(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    operator_action_id: uuid.UUID,
    patch: dict[str, Any],
) -> dict[str, Any] | None:
    row = oa_repo.get_operator_action_scoped(
        session,
        action_id=operator_action_id,
        org_id=org.id,
        org_type=org_type,
    )
    if row is None:
        return None

    prev_status = row.status
    now = datetime.now(UTC)

    if "assigned_to" in patch:
        row.assigned_to = patch["assigned_to"]
    if "due_at" in patch:
        row.due_at = _coerce_dt(patch["due_at"])
    if "operator_notes" in patch:
        row.operator_notes = patch["operator_notes"]
    if "resolution_notes" in patch:
        row.resolution_notes = patch["resolution_notes"]
    if "resolution_code" in patch and patch["resolution_code"] is not None:
        row.resolution_code = str(patch["resolution_code"])
    if "deferred_until" in patch:
        row.deferred_until = _coerce_dt(patch["deferred_until"])

    status_in = patch.get("status")
    transition_action: AuditAction | None = None

    if status_in is not None:
        new_s = str(status_in)
        if new_s not in {s.value for s in OperatorActionStatus}:
            raise ValueError(f"invalid status: {new_s}")
        row.status = new_s

        if new_s == OperatorActionStatus.in_progress.value:
            if row.started_at is None:
                row.started_at = now

        elif new_s == OperatorActionStatus.resolved.value:
            if row.resolved_at is None:
                row.resolved_at = now
            transition_action = AuditAction.operator_action_resolved

        elif new_s == OperatorActionStatus.dismissed.value:
            row.dismissed_at = row.dismissed_at or now
            row.resolved_at = row.resolved_at or now
            transition_action = AuditAction.operator_action_dismissed

        elif new_s == OperatorActionStatus.deferred.value:
            transition_action = AuditAction.operator_action_deferred

        elif new_s in (
            OperatorActionStatus.open.value,
            OperatorActionStatus.reopened.value,
        ):
            row.dismissed_at = None
            row.deferred_until = None
            row.resolved_at = None
            transition_action = AuditAction.operator_action_reopened

    if (
        status_in is not None
        and str(status_in) == OperatorActionStatus.in_progress.value
        and prev_status != row.status
    ):
        transition_action = AuditAction.operator_action_updated

    oa_repo.update_operator_action(session, row)

    audit_payload = {
        "operator_action_id": str(row.id),
        "decision_id": row.decision_id,
        "previous_status": prev_status,
        "status": row.status,
    }

    if transition_action is not None:
        _audit(session, org=org, action=transition_action, payload=audit_payload)
    elif patch.keys() & {
        "assigned_to",
        "due_at",
        "operator_notes",
        "resolution_notes",
        "resolution_code",
        "deferred_until",
    }:
        _audit(
            session,
            org=org,
            action=AuditAction.operator_action_updated,
            payload=audit_payload,
        )

    return operator_action_to_dict(row)


def _audit(
    session: Session,
    *,
    org: Organization,
    action: AuditAction,
    payload: dict[str, Any],
) -> None:
    audit_repo.append_org_audit_event(
        session,
        organization_id=org.id,
        is_demo=is_demo_for_org_type(org.org_type),
        action=action,
        payload=payload,
        actor_id=None,
    )


def build_ledger_summary(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    now: datetime | None = None,
) -> dict[str, Any]:
    ref = now or datetime.now(UTC)
    rows = oa_repo.list_operator_actions_for_org(
        session,
        org_id=org_id,
        org_type=org_type,
        limit=10_000,
    )
    by_status = Counter(r.status for r in rows)
    by_sev = Counter(r.severity for r in rows)
    by_item = Counter(r.item_type for r in rows)
    active_rows = [r for r in rows if r.status in _ACTIVE]
    overdue = sum(1 for r in active_rows if r.due_at is not None and r.due_at < ref)
    soon_cut = ref + timedelta(hours=72)
    due_soon = sum(
        1 for r in active_rows if r.due_at is not None and ref <= r.due_at <= soon_cut
    )
    assigned = sum(1 for r in active_rows if (r.assigned_to or "").strip())
    unassigned = len(active_rows) - assigned

    return {
        "schema_version": NF_OPERATOR_ACTION_SCHEMA_VERSION,
        "generated_at": ref.isoformat(),
        "counts_by_status": dict(sorted(by_status.items())),
        "counts_by_severity": dict(sorted(by_sev.items())),
        "counts_by_item_type": dict(sorted(by_item.items())),
        "open_operator_actions": len(active_rows),
        "overdue_action_count": overdue,
        "due_soon_count": due_soon,
        "assigned_count": assigned,
        "unassigned_count": unassigned,
        "total_actions": len(rows),
    }


def ledger_export_blocks(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    sample_limit: int = 50,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    summary = build_ledger_summary(session, org_id=org_id, org_type=org_type)
    rows = oa_repo.list_operator_actions_for_org(
        session,
        org_id=org_id,
        org_type=org_type,
        limit=max(1, min(sample_limit, 200)),
    )
    return summary, [operator_action_to_dict(r) for r in rows]


def enrich_decision_pack_with_ledger(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    pack: dict[str, Any],
) -> dict[str, Any]:
    """Mutates pack in place: ledger_context + optional decision_item annotations."""
    ref_now = datetime.now(UTC)
    recent_cut = ref_now - timedelta(days=7)

    active_rows = oa_repo.list_operator_actions_for_org(
        session,
        org_id=org_id,
        org_type=org_type,
        open_only=True,
        limit=5000,
    )
    active_ids = {r.decision_id for r in active_rows}
    by_decision: dict[str, uuid.UUID] = {r.decision_id: r.id for r in active_rows}

    resolved_recent = oa_repo.count_resolved_since(
        session,
        org_id=org_id,
        org_type=org_type,
        since=recent_cut,
    )

    pack["ledger_context"] = {
        "open_operator_actions": len(active_rows),
        "active_decision_ids": sorted(active_ids),
        "resolved_recently_count": resolved_recent,
    }

    for item in pack.get("decision_items") or []:
        if not isinstance(item, dict):
            continue
        did = str(item.get("decision_id") or "")
        item["has_active_operator_action"] = did in active_ids
        oid = by_decision.get(did)
        item["operator_action_id"] = str(oid) if oid else None

    return pack
