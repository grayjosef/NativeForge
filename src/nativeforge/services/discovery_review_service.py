"""Discovery review queue — list, resolve, audit, quality-triggered creates."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.db.models import (
    NfDiscoveryIntakeCandidate,
    NfDiscoveryReviewItem,
    NfGrantSpark,
    NfOpportunitySource,
    Organization,
    is_demo_for_org_type,
)
from nativeforge.domain.enums import (
    AuditAction,
    DiscoveryCandidateStatus,
    DiscoveryRecommendedAction,
    DiscoveryReviewItemType,
    DiscoveryReviewQueueStatus,
    OpportunityVerificationStatus,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import audit_events as audit_repo
from nativeforge.repositories import discovery_intake_runs as intake_repo
from nativeforge.repositories import discovery_review_items as rev_repo
from nativeforge.repositories import grant_sparks as gs_repo
from nativeforge.repositories import opportunity_sources as os_repo
from nativeforge.services import discovery_quality_service as dq

# Conservative deterministic gates — queue when signals exceed these bounds.
QUEUE_QUALITY_SCORE_AT_OR_BELOW = 62
QUEUE_CONFIDENCE_SCORE_BELOW = 62
QUEUE_DUPLICATE_RISK_SCORE_AT_OR_ABOVE = 48

INTAKE_HIGH_DUP_RISK = 40
INTAKE_LOW_NATIVE_SCORE = 36

REVIEW_ITEM_SCHEMA_VERSION = "nf_discovery_review_item_v1"

_TERMINAL_STATUSES = frozenset(
    {
        DiscoveryReviewQueueStatus.approved.value,
        DiscoveryReviewQueueStatus.rejected.value,
        DiscoveryReviewQueueStatus.merged.value,
        DiscoveryReviewQueueStatus.deferred.value,
    }
)


def review_item_to_dict(row: NfDiscoveryReviewItem) -> dict[str, Any]:
    def _dt(v: object | None) -> str | None:
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)

    return {
        "schema_version": REVIEW_ITEM_SCHEMA_VERSION,
        "id": str(row.id),
        "organization_id": str(row.organization_id),
        "is_demo": row.is_demo,
        "source_registry_id": str(row.source_registry_id)
        if row.source_registry_id
        else None,
        "intake_run_id": str(row.intake_run_id) if row.intake_run_id else None,
        "intake_candidate_id": str(row.intake_candidate_id)
        if row.intake_candidate_id
        else None,
        "grant_spark_id": str(row.grant_spark_id) if row.grant_spark_id else None,
        "review_item_type": row.review_item_type,
        "review_status": row.review_status,
        "priority": row.priority,
        "reason_codes_json": row.reason_codes_json,
        "quality_score": row.quality_score,
        "confidence_score": row.confidence_score,
        "duplicate_risk_score": row.duplicate_risk_score,
        "native_relevance_score": row.native_relevance_score,
        "recommended_action": row.recommended_action,
        "review_notes": row.review_notes,
        "assigned_to": row.assigned_to,
        "resolved_at": _dt(row.resolved_at),
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }


def list_review_items(
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
) -> list[dict[str, Any]]:
    rows = rev_repo.list_review_items_for_org(
        session,
        org_id=org_id,
        org_type=org_type,
        review_status=review_status,
        review_item_type=review_item_type,
        priority=priority,
        source_registry_id=source_registry_id,
        intake_run_id=intake_run_id,
        intake_candidate_id=intake_candidate_id,
        grant_spark_id=grant_spark_id,
        open_queue_only=open_queue_only,
        limit=limit,
    )
    return [review_item_to_dict(r) for r in rows]


def append_discovery_quality_scored_audit(
    session: Session,
    org: Organization,
    payload: dict[str, Any],
) -> None:
    audit_repo.append_org_audit_event(
        session,
        organization_id=org.id,
        is_demo=is_demo_for_org_type(org.org_type),
        action=AuditAction.discovery_quality_scored,
        payload=payload,
        actor_id=None,
    )


def get_review_item(
    session: Session,
    *,
    review_item_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> dict[str, Any] | None:
    row = rev_repo.get_review_item_scoped(
        session,
        review_item_id=review_item_id,
        org_id=org_id,
        org_type=org_type,
    )
    if row is None:
        return None
    return review_item_to_dict(row)


def should_create_review_item_from_quality(quality_summary: dict[str, Any]) -> bool:
    """Deterministic gate — avoids spamming the queue."""
    if "quality_score" not in quality_summary:
        return False
    action = quality_summary.get("recommended_action")
    if action == DiscoveryRecommendedAction.approve.value:
        return False
    if quality_summary.get("review_required") is True:
        return True
    dup = int(quality_summary.get("duplicate_risk_score") or 0)
    conf = int(quality_summary.get("confidence_score") or 0)
    qual = int(quality_summary.get("quality_score") or 0)
    if dup >= QUEUE_DUPLICATE_RISK_SCORE_AT_OR_ABOVE:
        return True
    if conf < QUEUE_CONFIDENCE_SCORE_BELOW:
        return True
    if qual <= QUEUE_QUALITY_SCORE_AT_OR_BELOW:
        return True
    return False


def maybe_create_review_item_from_quality_summary(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    quality_summary: dict[str, Any],
    review_item_type: DiscoveryReviewItemType,
    source_registry_id: uuid.UUID | None = None,
    intake_run_id: uuid.UUID | None = None,
    intake_candidate_id: uuid.UUID | None = None,
    grant_spark_id: uuid.UUID | None = None,
    native_relevance_score: int | None = None,
) -> NfDiscoveryReviewItem | None:
    """Insert a queue row when quality signals warrant operator attention."""
    if not should_create_review_item_from_quality(quality_summary):
        return None
    if intake_candidate_id is not None:
        if (
            rev_repo.count_active_review_items_for_candidate(
                session,
                org_id=org.id,
                org_type=org_type,
                intake_candidate_id=intake_candidate_id,
            )
            > 0
        ):
            return None
    if grant_spark_id is not None:
        if (
            rev_repo.count_active_review_items_for_spark(
                session,
                org_id=org.id,
                org_type=org_type,
                grant_spark_id=grant_spark_id,
            )
            > 0
        ):
            return None

    rc_raw = quality_summary.get("reason_codes")
    rc_list: list[Any] = list(rc_raw) if isinstance(rc_raw, list) else []

    priority = max(
        0,
        min(100, int(quality_summary.get("duplicate_risk_score") or 0)),
    )
    row = rev_repo.create_review_item(
        session,
        org=org,
        review_item_type=review_item_type.value,
        review_status=DiscoveryReviewQueueStatus.open.value,
        priority=priority,
        reason_codes_json=rc_list,
        quality_score=quality_summary.get("quality_score"),
        confidence_score=quality_summary.get("confidence_score"),
        duplicate_risk_score=quality_summary.get("duplicate_risk_score"),
        native_relevance_score=native_relevance_score,
        recommended_action=quality_summary.get("recommended_action"),
        review_notes=None,
        assigned_to=None,
        source_registry_id=source_registry_id,
        intake_run_id=intake_run_id,
        intake_candidate_id=intake_candidate_id,
        grant_spark_id=grant_spark_id,
        resolved_at=None,
    )
    audit_repo.append_org_audit_event(
        session,
        organization_id=org.id,
        is_demo=is_demo_for_org_type(org.org_type),
        action=AuditAction.discovery_review_item_created,
        payload={
            "discovery_review_item_id": str(row.id),
            "review_item_type": row.review_item_type,
            "quality_summary_keys": sorted(quality_summary.keys()),
        },
        actor_id=None,
    )
    session.flush()
    return row


def patch_review_item(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    review_item_id: uuid.UUID,
    patch: dict[str, Any],
) -> dict[str, Any] | None:
    """Validate patch dict (caller passes model_dump exclude_unset) and persist."""
    row = rev_repo.get_review_item_scoped(
        session,
        review_item_id=review_item_id,
        org_id=org.id,
        org_type=org_type,
    )
    if row is None:
        return None

    before = review_item_to_dict(row)
    now = datetime.now(UTC)

    kwargs: dict[str, Any] = {}
    if "review_status" in patch:
        st = patch["review_status"]
        try:
            DiscoveryReviewQueueStatus(str(st))
        except ValueError as e:
            raise ValueError("invalid review_status") from e
        kwargs["review_status"] = str(st)

    if "review_notes" in patch:
        kwargs["review_notes"] = patch["review_notes"]

    if "assigned_to" in patch:
        at = patch["assigned_to"]
        if at is not None and len(str(at)) > 512:
            raise ValueError("assigned_to too long")
        kwargs["assigned_to"] = None if at is None or at == "" else str(at)

    if "recommended_action" in patch:
        ra = patch["recommended_action"]
        if ra is not None:
            try:
                DiscoveryRecommendedAction(str(ra))
            except ValueError as e:
                raise ValueError("invalid recommended_action") from e
            kwargs["recommended_action"] = str(ra)
        else:
            kwargs["recommended_action"] = None

    if "priority" in patch and patch["priority"] is not None:
        kwargs["priority"] = int(patch["priority"])

    new_status = kwargs.get("review_status", row.review_status)
    if "review_status" in patch:
        if new_status in _TERMINAL_STATUSES:
            kwargs["resolved_at"] = row.resolved_at or now
        else:
            kwargs["resolved_at"] = row.resolved_at

    rev_repo.update_review_item(session, row, **kwargs)
    session.refresh(row)
    after = review_item_to_dict(row)

    audit_repo.append_org_audit_event(
        session,
        organization_id=org.id,
        is_demo=is_demo_for_org_type(org.org_type),
        action=AuditAction.discovery_review_item_updated,
        payload={
            "discovery_review_item_id": str(row.id),
            "before": before,
            "after": after,
        },
        actor_id=None,
    )
    session.flush()
    return after


def build_quality_endpoint_response(
    session: Session,
    org: Organization,
    org_type: OrgType,
    quality_summary: dict[str, Any],
    *,
    create_review_item: bool,
    review_item_type_default: DiscoveryReviewItemType,
    source_registry_id: uuid.UUID | None,
    intake_run_id: uuid.UUID | None,
    intake_candidate_id: uuid.UUID | None,
    grant_spark_id: uuid.UUID | None,
    native_relevance_score: int | None,
) -> dict[str, Any]:
    """Quality GET payload + optional queue row (reuse active row when present)."""
    review_dict: dict[str, Any] | None = None
    reused = False

    if create_review_item:
        existing: NfDiscoveryReviewItem | None = None
        if intake_candidate_id is not None:
            existing = rev_repo.get_active_review_item_for_candidate(
                session,
                org_id=org.id,
                org_type=org_type,
                intake_candidate_id=intake_candidate_id,
            )
        elif grant_spark_id is not None:
            existing = rev_repo.get_active_review_item_for_grant_spark(
                session,
                org_id=org.id,
                org_type=org_type,
                grant_spark_id=grant_spark_id,
            )
        if existing is not None:
            review_dict = review_item_to_dict(existing)
            reused = True
        else:
            row = maybe_create_review_item_from_quality_summary(
                session,
                org=org,
                org_type=org_type,
                quality_summary=quality_summary,
                review_item_type=review_item_type_default,
                source_registry_id=source_registry_id,
                intake_run_id=intake_run_id,
                intake_candidate_id=intake_candidate_id,
                grant_spark_id=grant_spark_id,
                native_relevance_score=native_relevance_score,
            )
            if row is not None:
                review_dict = review_item_to_dict(row)

    append_discovery_quality_scored_audit(
        session,
        org,
        {
            "quality_schema_version": quality_summary.get("quality_schema_version"),
            "create_review_item": create_review_item,
            "review_item_reused": reused,
            "discovery_review_item_id": review_dict["id"] if review_dict else None,
            "intake_candidate_id": str(intake_candidate_id)
            if intake_candidate_id
            else None,
            "grant_spark_id": str(grant_spark_id) if grant_spark_id else None,
            "quality_score": quality_summary.get("quality_score"),
            "duplicate_risk_score": quality_summary.get("duplicate_risk_score"),
        },
    )
    session.flush()
    return {
        "quality_summary": quality_summary,
        "review_item": review_dict,
        "review_item_reused": reused,
    }


def get_intake_candidate_quality_bundle(
    session: Session,
    org: Organization,
    org_type: OrgType,
    candidate_id: uuid.UUID,
    *,
    create_review_item: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    cand = intake_repo.get_discovery_intake_candidate_scoped(
        session=session,
        candidate_id=candidate_id,
        org_id=org.id,
        org_type=org_type,
    )
    if cand is None:
        raise ValueError("intake candidate not found")
    registry: NfOpportunitySource | None = None
    if cand.source_registry_id is not None:
        registry = os_repo.get_opportunity_source_scoped(
            session=session,
            source_id=cand.source_registry_id,
            org_id=org.id,
            org_type=org_type,
        )
    summary = dq.quality_summary_for_intake_candidate(
        cand,
        registry,
        now=now or datetime.now(UTC),
    )
    return build_quality_endpoint_response(
        session,
        org,
        org_type,
        summary,
        create_review_item=create_review_item,
        review_item_type_default=DiscoveryReviewItemType.candidate_quality,
        source_registry_id=cand.source_registry_id,
        intake_run_id=cand.intake_run_id,
        intake_candidate_id=cand.id,
        grant_spark_id=cand.created_spark_id,
        native_relevance_score=cand.native_relevance_score,
    )


def get_grant_spark_quality_bundle(
    session: Session,
    org: Organization,
    org_type: OrgType,
    spark_id: uuid.UUID,
    *,
    create_review_item: bool,
    now: datetime | None = None,
) -> dict[str, Any]:
    spark = gs_repo.get_grant_spark_scoped(
        session=session,
        spark_id=spark_id,
        org_id=org.id,
        org_type=org_type,
    )
    if spark is None:
        raise ValueError("grant spark not found")
    registry: NfOpportunitySource | None = None
    if spark.source_registry_id is not None:
        registry = os_repo.get_opportunity_source_scoped(
            session=session,
            source_id=spark.source_registry_id,
            org_id=org.id,
            org_type=org_type,
        )
    summary = dq.quality_summary_for_grant_spark(
        spark,
        registry,
        now=now or datetime.now(UTC),
    )
    return build_quality_endpoint_response(
        session,
        org,
        org_type,
        summary,
        create_review_item=create_review_item,
        review_item_type_default=DiscoveryReviewItemType.candidate_quality,
        source_registry_id=spark.source_registry_id,
        intake_run_id=None,
        intake_candidate_id=None,
        grant_spark_id=spark.id,
        native_relevance_score=spark.native_relevance_score,
    )


def _create_forced_intake_review_item(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    candidate: NfDiscoveryIntakeCandidate,
    registry: NfOpportunitySource,
    review_item_type: DiscoveryReviewItemType,
    reason_codes: list[str],
    quality_summary: dict[str, Any],
    review_notes: str | None,
) -> None:
    if (
        rev_repo.count_active_review_items_for_candidate(
            session,
            org_id=org.id,
            org_type=org_type,
            intake_candidate_id=candidate.id,
        )
        > 0
    ):
        return
    rc = list(reason_codes)
    qrc = quality_summary.get("reason_codes")
    if isinstance(qrc, list):
        rc.extend(str(x) for x in qrc)
    row = rev_repo.create_review_item(
        session,
        org=org,
        review_item_type=review_item_type.value,
        review_status=DiscoveryReviewQueueStatus.open.value,
        priority=min(
            100,
            max(
                0,
                int(quality_summary.get("duplicate_risk_score") or 40),
            ),
        ),
        reason_codes_json=rc,
        quality_score=quality_summary.get("quality_score"),
        confidence_score=quality_summary.get("confidence_score"),
        duplicate_risk_score=quality_summary.get("duplicate_risk_score"),
        native_relevance_score=candidate.native_relevance_score,
        recommended_action=quality_summary.get("recommended_action"),
        review_notes=review_notes,
        assigned_to=None,
        source_registry_id=candidate.source_registry_id,
        intake_run_id=candidate.intake_run_id,
        intake_candidate_id=candidate.id,
        grant_spark_id=candidate.created_spark_id,
        resolved_at=None,
    )
    audit_repo.append_org_audit_event(
        session,
        organization_id=org.id,
        is_demo=is_demo_for_org_type(org.org_type),
        action=AuditAction.discovery_review_item_created,
        payload={
            "discovery_review_item_id": str(row.id),
            "review_item_type": row.review_item_type,
            "intake_trigger": True,
        },
        actor_id=None,
    )
    session.flush()


def process_intake_candidate_review_side_effects(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    candidate: NfDiscoveryIntakeCandidate,
    registry: NfOpportunitySource,
    now: datetime,
) -> None:
    """Non-blocking review queue hooks after each intake candidate row is flushed."""
    summary = dq.quality_summary_for_intake_candidate(
        candidate,
        registry,
        now=now,
    )
    st = candidate.candidate_status

    if st == DiscoveryCandidateStatus.duplicate.value:
        _create_forced_intake_review_item(
            session,
            org=org,
            org_type=org_type,
            candidate=candidate,
            registry=registry,
            review_item_type=DiscoveryReviewItemType.duplicate_review,
            reason_codes=["intake_duplicate"],
            quality_summary=summary,
            review_notes=candidate.decision_reason,
        )
        return

    if st == DiscoveryCandidateStatus.rejected.value:
        _create_forced_intake_review_item(
            session,
            org=org,
            org_type=org_type,
            candidate=candidate,
            registry=registry,
            review_item_type=DiscoveryReviewItemType.candidate_quality,
            reason_codes=["intake_rejected"],
            quality_summary=summary,
            review_notes=candidate.decision_reason,
        )
        return

    if st != DiscoveryCandidateStatus.accepted.value:
        return

    if (
        rev_repo.count_active_review_items_for_candidate(
            session,
            org_id=org.id,
            org_type=org_type,
            intake_candidate_id=candidate.id,
        )
        > 0
    ):
        return

    spark: NfGrantSpark | None = None
    if candidate.created_spark_id is not None:
        spark = session.get(NfGrantSpark, candidate.created_spark_id)

    reg_u = (
        registry.verification_status == OpportunityVerificationStatus.unverified.value
    )
    spark_u = (
        spark is not None
        and spark.verification_status == OpportunityVerificationStatus.unverified.value
    )
    unverified = reg_u or spark_u
    rc_summary = summary.get("reason_codes")
    rc_list = list(rc_summary) if isinstance(rc_summary, list) else []
    missing_dl = "missing_deadline" in rc_list
    high_dup = int(summary.get("duplicate_risk_score") or 0) >= INTAKE_HIGH_DUP_RISK
    low_native = candidate.native_relevance_score is None or (
        candidate.native_relevance_score < INTAKE_LOW_NATIVE_SCORE
    )
    qual_need = should_create_review_item_from_quality(summary)

    flags = {
        "unverified_source": unverified,
        "missing_deadline": missing_dl,
        "high_duplicate_risk": high_dup,
        "uncertain_native_relevance": low_native,
        "quality_requires_review": qual_need,
    }
    if not any(flags.values()):
        return

    only_unverified = unverified and not (
        missing_dl or high_dup or low_native or qual_need
    )
    only_native = low_native and not (unverified or missing_dl or high_dup or qual_need)
    if only_unverified:
        rtype = DiscoveryReviewItemType.source_verification
    elif only_native:
        rtype = DiscoveryReviewItemType.native_relevance_review
    else:
        rtype = DiscoveryReviewItemType.candidate_quality

    extra = [f"intake_flag:{k}" for k, v in flags.items() if v]
    reason_codes = extra + rc_list

    row = rev_repo.create_review_item(
        session,
        org=org,
        review_item_type=rtype.value,
        review_status=DiscoveryReviewQueueStatus.open.value,
        priority=min(
            100,
            max(0, int(summary.get("duplicate_risk_score") or 0)),
        ),
        reason_codes_json=reason_codes,
        quality_score=summary.get("quality_score"),
        confidence_score=summary.get("confidence_score"),
        duplicate_risk_score=summary.get("duplicate_risk_score"),
        native_relevance_score=candidate.native_relevance_score,
        recommended_action=summary.get("recommended_action"),
        review_notes=None,
        assigned_to=None,
        source_registry_id=candidate.source_registry_id,
        intake_run_id=candidate.intake_run_id,
        intake_candidate_id=candidate.id,
        grant_spark_id=candidate.created_spark_id,
        resolved_at=None,
    )
    audit_repo.append_org_audit_event(
        session,
        organization_id=org.id,
        is_demo=is_demo_for_org_type(org.org_type),
        action=AuditAction.discovery_review_item_created,
        payload={
            "discovery_review_item_id": str(row.id),
            "review_item_type": row.review_item_type,
            "intake_accepted_trigger": sorted(k for k, v in flags.items() if v),
        },
        actor_id=None,
    )
    session.flush()
