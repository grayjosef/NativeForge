"""nf_discovery_review_items — org-scoped CRUD and filtered lists."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import and_, func, select
from sqlalchemy.orm import Session

from nativeforge.db.models import (
    NfDiscoveryReviewItem,
    Organization,
    is_demo_for_org_type,
)
from nativeforge.domain.enums import DiscoveryReviewQueueStatus
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories.scoping import (
    nf_discovery_review_item_scope,
    select_discovery_review_item_scoped,
    select_discovery_review_items_for_org,
)

_MISSING = object()

_OPEN_ACTIVE_STATUSES = frozenset(
    {
        DiscoveryReviewQueueStatus.open.value,
        DiscoveryReviewQueueStatus.in_review.value,
    }
)


def list_review_items_for_org(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    review_status: str | None = None,
    review_item_type: str | None = None,
    priority: int | None = None,
    source_registry_id: uuid.UUID | None = None,
    intake_run_id: uuid.UUID | None = None,
    intake_candidate_id: uuid.UUID | None = None,
    grant_spark_id: uuid.UUID | None = None,
    open_queue_only: bool = False,
    limit: int = 500,
) -> list[NfDiscoveryReviewItem]:
    """List review items for an org/plane with optional equality filters."""
    stmt = select_discovery_review_items_for_org(org_id=org_id, org_type=org_type)
    filters: list[Any] = []
    if review_status is not None:
        filters.append(NfDiscoveryReviewItem.review_status == review_status)
    if review_item_type is not None:
        filters.append(NfDiscoveryReviewItem.review_item_type == review_item_type)
    if priority is not None:
        filters.append(NfDiscoveryReviewItem.priority == priority)
    if source_registry_id is not None:
        filters.append(NfDiscoveryReviewItem.source_registry_id == source_registry_id)
    if intake_run_id is not None:
        filters.append(NfDiscoveryReviewItem.intake_run_id == intake_run_id)
    if intake_candidate_id is not None:
        filters.append(
            NfDiscoveryReviewItem.intake_candidate_id == intake_candidate_id,
        )
    if grant_spark_id is not None:
        filters.append(NfDiscoveryReviewItem.grant_spark_id == grant_spark_id)
    if open_queue_only:
        filters.append(NfDiscoveryReviewItem.review_status.in_(_OPEN_ACTIVE_STATUSES))
    q = stmt
    if filters:
        q = q.where(and_(*filters))
    q = q.limit(limit)
    return list(session.scalars(q))


def get_review_item_scoped(
    session: Session,
    *,
    review_item_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> NfDiscoveryReviewItem | None:
    stmt = select_discovery_review_item_scoped(
        org_id=org_id,
        org_type=org_type,
        review_item_id=review_item_id,
    )
    return session.scalar(stmt)


def list_open_review_items(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    limit: int = 500,
) -> list[NfDiscoveryReviewItem]:
    """Items still in operator queue (open or in_review)."""
    return list_review_items_for_org(
        session,
        org_id=org_id,
        org_type=org_type,
        open_queue_only=True,
        limit=limit,
    )


def list_review_items_for_source(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    source_registry_id: uuid.UUID,
    limit: int = 500,
) -> list[NfDiscoveryReviewItem]:
    return list_review_items_for_org(
        session,
        org_id=org_id,
        org_type=org_type,
        source_registry_id=source_registry_id,
        limit=limit,
    )


def list_review_items_for_intake_run(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    intake_run_id: uuid.UUID,
    limit: int = 500,
) -> list[NfDiscoveryReviewItem]:
    return list_review_items_for_org(
        session,
        org_id=org_id,
        org_type=org_type,
        intake_run_id=intake_run_id,
        limit=limit,
    )


def list_review_items_for_intake_candidate(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    intake_candidate_id: uuid.UUID,
    limit: int = 500,
) -> list[NfDiscoveryReviewItem]:
    return list_review_items_for_org(
        session,
        org_id=org_id,
        org_type=org_type,
        intake_candidate_id=intake_candidate_id,
        limit=limit,
    )


def list_review_items_for_grant_spark(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    grant_spark_id: uuid.UUID,
    limit: int = 500,
) -> list[NfDiscoveryReviewItem]:
    return list_review_items_for_org(
        session,
        org_id=org_id,
        org_type=org_type,
        grant_spark_id=grant_spark_id,
        limit=limit,
    )


def get_active_review_item_for_candidate(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    intake_candidate_id: uuid.UUID,
) -> NfDiscoveryReviewItem | None:
    """First open/in_review row for this candidate, if any."""
    scope = nf_discovery_review_item_scope(org_id=org_id, org_type=org_type)
    stmt = (
        select(NfDiscoveryReviewItem)
        .where(
            NfDiscoveryReviewItem.intake_candidate_id == intake_candidate_id,
            NfDiscoveryReviewItem.review_status.in_(_OPEN_ACTIVE_STATUSES),
            *scope,
        )
        .order_by(NfDiscoveryReviewItem.created_at.asc())
        .limit(1)
    )
    return session.scalar(stmt)


def get_active_review_item_for_grant_spark(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    grant_spark_id: uuid.UUID,
) -> NfDiscoveryReviewItem | None:
    scope = nf_discovery_review_item_scope(org_id=org_id, org_type=org_type)
    stmt = (
        select(NfDiscoveryReviewItem)
        .where(
            NfDiscoveryReviewItem.grant_spark_id == grant_spark_id,
            NfDiscoveryReviewItem.review_status.in_(_OPEN_ACTIVE_STATUSES),
            *scope,
        )
        .order_by(NfDiscoveryReviewItem.created_at.asc())
        .limit(1)
    )
    return session.scalar(stmt)


def create_review_item(
    session: Session,
    *,
    org: Organization,
    review_item_type: str,
    review_status: str,
    priority: int = 0,
    reason_codes_json: list[Any] | dict[Any, Any] | None = None,
    quality_score: int | None = None,
    confidence_score: int | None = None,
    duplicate_risk_score: int | None = None,
    native_relevance_score: int | None = None,
    recommended_action: str | None = None,
    review_notes: str | None = None,
    assigned_to: str | None = None,
    source_registry_id: uuid.UUID | None = None,
    intake_run_id: uuid.UUID | None = None,
    intake_candidate_id: uuid.UUID | None = None,
    grant_spark_id: uuid.UUID | None = None,
    resolved_at: Any | None = None,
) -> NfDiscoveryReviewItem:
    is_demo = is_demo_for_org_type(org.org_type)
    row = NfDiscoveryReviewItem(
        organization_id=org.id,
        is_demo=is_demo,
        review_item_type=review_item_type,
        review_status=review_status,
        priority=priority,
        reason_codes_json=reason_codes_json,
        quality_score=quality_score,
        confidence_score=confidence_score,
        duplicate_risk_score=duplicate_risk_score,
        native_relevance_score=native_relevance_score,
        recommended_action=recommended_action,
        review_notes=review_notes,
        assigned_to=assigned_to,
        source_registry_id=source_registry_id,
        intake_run_id=intake_run_id,
        intake_candidate_id=intake_candidate_id,
        grant_spark_id=grant_spark_id,
        resolved_at=resolved_at,
    )
    session.add(row)
    session.flush()
    return row


def update_review_item(
    session: Session,
    row: NfDiscoveryReviewItem,
    *,
    review_status: Any = _MISSING,
    review_notes: Any = _MISSING,
    assigned_to: Any = _MISSING,
    recommended_action: Any = _MISSING,
    priority: Any = _MISSING,
    resolved_at: Any = _MISSING,
) -> NfDiscoveryReviewItem:
    """Patch fields; _MISSING skips a column (explicit None is allowed)."""
    if review_status is not _MISSING:
        row.review_status = review_status
    if review_notes is not _MISSING:
        row.review_notes = review_notes
    if assigned_to is not _MISSING:
        row.assigned_to = assigned_to
    if recommended_action is not _MISSING:
        row.recommended_action = recommended_action
    if priority is not _MISSING:
        row.priority = priority
    if resolved_at is not _MISSING:
        row.resolved_at = resolved_at
    session.flush()
    return row


def count_active_review_items_for_candidate(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    intake_candidate_id: uuid.UUID,
) -> int:
    scope = nf_discovery_review_item_scope(org_id=org_id, org_type=org_type)
    stmt = (
        select(func.count())
        .select_from(NfDiscoveryReviewItem)
        .where(
            NfDiscoveryReviewItem.intake_candidate_id == intake_candidate_id,
            NfDiscoveryReviewItem.review_status.in_(_OPEN_ACTIVE_STATUSES),
            *scope,
        )
    )
    return int(session.scalar(stmt) or 0)


def count_active_review_items_for_spark(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    grant_spark_id: uuid.UUID,
) -> int:
    scope = nf_discovery_review_item_scope(org_id=org_id, org_type=org_type)
    stmt = (
        select(func.count())
        .select_from(NfDiscoveryReviewItem)
        .where(
            NfDiscoveryReviewItem.grant_spark_id == grant_spark_id,
            NfDiscoveryReviewItem.review_status.in_(_OPEN_ACTIVE_STATUSES),
            *scope,
        )
    )
    return int(session.scalar(stmt) or 0)
