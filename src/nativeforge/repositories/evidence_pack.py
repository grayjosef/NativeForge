"""Discovery evidence pack — scoped reads for audit + related rows (Sprint 19)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.db.models import NfAuditEvent
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import audit_events as audit_repo
from nativeforge.repositories import discovery_review_items as rev_repo
from nativeforge.repositories import operator_actions as oa_repo
from nativeforge.repositories import source_check_runs as scr_repo


def _walk_payload_values(payload: Any) -> list[str]:
    out: list[str] = []
    if payload is None:
        return out
    if isinstance(payload, dict):
        for v in payload.values():
            out.extend(_walk_payload_values(v))
        return out
    if isinstance(payload, list):
        for v in payload:
            out.extend(_walk_payload_values(v))
        return out
    out.append(str(payload))
    return out


def audit_event_matches_reference_ids(
    ev: NfAuditEvent, reference_ids: set[str]
) -> bool:
    """True if any reference UUID string appears in the serialized audit payload."""
    if not reference_ids:
        return False
    blob = " ".join(_walk_payload_values(ev.payload))
    return any(rid in blob for rid in reference_ids)


def list_related_audit_events(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    reference_ids: set[str],
    limit: int,
    fetch_cap: int = 4000,
) -> list[NfAuditEvent]:
    """Scan recent org audit tail and keep events whose payload mentions reference IDs."""
    if limit <= 0 or not reference_ids:
        return []
    cap = max(limit, min(fetch_cap, max(limit * 20, 200)))
    tail = audit_repo.list_audit_events_for_org(
        session=session,
        org_id=org_id,
        org_type=org_type,
        limit=cap,
    )
    out: list[NfAuditEvent] = []
    for ev in tail:
        if audit_event_matches_reference_ids(ev, reference_ids):
            out.append(ev)
            if len(out) >= limit:
                break
    return out


def list_related_review_items_for_source(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    source_registry_id: uuid.UUID,
    limit: int = 500,
):
    return rev_repo.list_review_items_for_source(
        session,
        org_id=org_id,
        org_type=org_type,
        source_registry_id=source_registry_id,
        limit=limit,
    )


def list_related_operator_actions_for_source(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    source_registry_id: uuid.UUID,
    limit: int = 200,
):
    return oa_repo.list_operator_actions_for_org(
        session,
        org_id=org_id,
        org_type=org_type,
        source_registry_id=source_registry_id,
        limit=limit,
    )


def list_related_source_check_runs_for_source(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    source_registry_id: uuid.UUID,
    limit: int = 50,
):
    return scr_repo.list_source_check_runs_for_source(
        session,
        org_id=org_id,
        org_type=org_type,
        source_registry_id=source_registry_id,
        limit=limit,
    )


def list_related_operator_actions_for_review_item(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    review_item_id: uuid.UUID,
    limit: int = 100,
):
    return oa_repo.list_operator_actions_for_org(
        session,
        org_id=org_id,
        org_type=org_type,
        review_item_id=review_item_id,
        limit=limit,
    )
