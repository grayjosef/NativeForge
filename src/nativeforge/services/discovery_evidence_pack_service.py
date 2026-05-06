"""Sprint 19: deterministic Discovery evidence packs + provenance trace (backend only)."""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from nativeforge.db.models import (
    NfDiscoveryIntakeCandidate,
    NfDiscoveryReviewItem,
    NfGrantSpark,
    NfOperatorAction,
    NfOpportunitySource,
    Organization,
    is_demo_for_org_type,
)
from nativeforge.domain.enums import (
    DiscoveryCandidateStatus,
    DiscoveryReviewQueueStatus,
    EvidencePackSectionType,
    EvidencePackSubjectType,
    EvidencePackWarningSeverity,
    EvidencePackWarningType,
    OperatorActionStatus,
    OpportunityVerificationStatus,
    SourceCheckRunStatus,
    SourceHealthStatus,
    SourceLastCheckStatus,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import discovery_intake_runs as intake_repo
from nativeforge.repositories import discovery_review_items as rev_repo
from nativeforge.repositories import evidence_pack as ep_repo
from nativeforge.repositories import grant_sparks as gs_repo
from nativeforge.repositories import operator_actions as oa_repo
from nativeforge.repositories import opportunity_sources as os_repo
from nativeforge.repositories import source_check_runs as scr_repo
from nativeforge.repositories import spark_scores as score_repo
from nativeforge.repositories.audit_events import audit_event_to_dict
from nativeforge.repositories.scoping import nf_discovery_intake_candidate_scope
from nativeforge.services import discovery_coverage_gap_service as dcg_svc
from nativeforge.services import discovery_intake_service as d_intake
from nativeforge.services import discovery_quality_service as dq
from nativeforge.services import discovery_review_service as d_review
from nativeforge.services import grant_spark_service as gss
from nativeforge.services import operator_action_service as oa_svc
from nativeforge.services import opportunity_discovery_service as ods
from nativeforge.services import source_freshness_service as sfs
from nativeforge.services.discovery_operator_workbench_service import (
    DECISION_PACK_SCHEMA_VERSION,
)

EVIDENCE_PACK_SCHEMA_VERSION = "nf_discovery_evidence_pack_v1"

_QUALITY_LOW = 50
_DUP_RISK_HIGH = 70
_OPEN_REVIEW = frozenset(
    {
        DiscoveryReviewQueueStatus.open.value,
        DiscoveryReviewQueueStatus.in_review.value,
    },
)
_UNRESOLVED_OA = frozenset(
    {
        OperatorActionStatus.open.value,
        OperatorActionStatus.in_progress.value,
        OperatorActionStatus.deferred.value,
        OperatorActionStatus.reopened.value,
    },
)


def _dt(v: object | None) -> str | None:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.isoformat()
    return str(v)


def _digest_json_blob(blob: object | None) -> str | None:
    if blob is None:
        return None
    try:
        raw = json.dumps(blob, sort_keys=True, default=str).encode()
    except TypeError:
        return None
    return hashlib.sha256(raw).hexdigest()


def _warn(
    warning_type: EvidencePackWarningType,
    severity: EvidencePackWarningSeverity,
    title: str,
    rationale: str,
    recommended_action: str,
) -> dict[str, Any]:
    return {
        "warning_type": warning_type.value,
        "severity": severity.value,
        "title": title,
        "rationale": rationale,
        "recommended_action": recommended_action,
    }


def _section(
    section_type: EvidencePackSectionType,
    title: str,
    summary: str,
    records: list[Any],
    warnings: list[dict[str, Any]],
    *,
    generated_at: str,
) -> dict[str, Any]:
    return {
        "section_type": section_type.value,
        "title": title,
        "summary": summary,
        "records": records,
        "warnings": warnings,
        "generated_at": generated_at,
    }


def _find_candidate_for_created_spark(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    spark_id: uuid.UUID,
) -> NfDiscoveryIntakeCandidate | None:
    scope = nf_discovery_intake_candidate_scope(org_id=org_id, org_type=org_type)
    stmt = (
        select(NfDiscoveryIntakeCandidate)
        .where(
            NfDiscoveryIntakeCandidate.created_spark_id == spark_id,
            *scope,
        )
        .limit(1)
    )
    return session.scalar(stmt)


def _count_model_scoped(
    session: Session,
    *,
    model: type,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> int:
    is_demo = org_type == "demo"
    scope = (
        model.organization_id == org_id,
        model.is_demo.is_(is_demo),
    )
    stmt = select(func.count()).select_from(model).where(*scope)
    return int(session.scalar(stmt) or 0)


def subject_path_to_type(path_segment: str) -> EvidencePackSubjectType | None:
    mapping = {
        "sources": EvidencePackSubjectType.opportunity_source,
        "intake-runs": EvidencePackSubjectType.intake_run,
        "intake-candidates": EvidencePackSubjectType.intake_candidate,
        "grant-sparks": EvidencePackSubjectType.grant_spark,
        "review-items": EvidencePackSubjectType.discovery_review_item,
        "source-check-runs": EvidencePackSubjectType.source_check_run,
        "operator-actions": EvidencePackSubjectType.operator_action,
    }
    return mapping.get(path_segment)


def build_evidence_pack_export_summary(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Compact rollup for org_data_snapshot (no full packs)."""
    ref = now or datetime.now(UTC)

    counts = {
        "opportunity_sources": _count_model_scoped(
            session, model=NfOpportunitySource, org_id=org_id, org_type=org_type
        ),
        "intake_candidates": _count_model_scoped(
            session, model=NfDiscoveryIntakeCandidate, org_id=org_id, org_type=org_type
        ),
        "grant_sparks": _count_model_scoped(
            session, model=NfGrantSpark, org_id=org_id, org_type=org_type
        ),
        "discovery_review_items": _count_model_scoped(
            session, model=NfDiscoveryReviewItem, org_id=org_id, org_type=org_type
        ),
        "operator_actions": _count_model_scoped(
            session, model=NfOperatorAction, org_id=org_id, org_type=org_type
        ),
    }
    evidence_total = sum(counts.values())
    unresolved_review = session.scalar(
        select(func.count())
        .select_from(NfDiscoveryReviewItem)
        .where(
            NfDiscoveryReviewItem.organization_id == org_id,
            NfDiscoveryReviewItem.is_demo.is_(org_type == "demo"),
            NfDiscoveryReviewItem.review_status.in_(_OPEN_REVIEW),
        )
    )
    unresolved_oa = session.scalar(
        select(func.count())
        .select_from(NfOperatorAction)
        .where(
            NfOperatorAction.organization_id == org_id,
            NfOperatorAction.is_demo.is_(org_type == "demo"),
            NfOperatorAction.status.in_(_UNRESOLVED_OA),
        )
    )
    sample_refs: list[dict[str, str]] = []
    src = session.scalars(
        select(NfOpportunitySource.id)
        .where(
            NfOpportunitySource.organization_id == org_id,
            NfOpportunitySource.is_demo.is_(org_type == "demo"),
        )
        .limit(1)
    ).first()
    if src:
        sample_refs.append(
            {
                "subject_type": EvidencePackSubjectType.opportunity_source.value,
                "subject_id": str(src),
            }
        )
    spark = session.scalars(
        select(NfGrantSpark.id)
        .where(
            NfGrantSpark.organization_id == org_id,
            NfGrantSpark.is_demo.is_(org_type == "demo"),
        )
        .limit(1)
    ).first()
    if spark:
        sample_refs.append(
            {
                "subject_type": EvidencePackSubjectType.grant_spark.value,
                "subject_id": str(spark),
            }
        )

    return {
        "schema_version": f"{EVIDENCE_PACK_SCHEMA_VERSION}_export_summary_v1",
        "generated_at": ref.isoformat(),
        "evidence_pack_summary": {
            "schema_version": EVIDENCE_PACK_SCHEMA_VERSION,
            "description": (
                "Counts of rows that can be addressed via discovery evidence-pack routes."
            ),
        },
        "evidence_subjects_sample": sample_refs,
        "counts": {
            "evidence_subjects_available": evidence_total,
            "by_subject_family": counts,
            "unresolved_review_items": int(unresolved_review or 0),
            "unresolved_operator_actions": int(unresolved_oa or 0),
        },
    }


def build_discovery_evidence_pack(
    session: Session,
    org: Organization,
    org_type: OrgType,
    subject_type: EvidencePackSubjectType,
    subject_id: uuid.UUID,
    *,
    include_audit_trail: bool = True,
    include_linked_records: bool = True,
    include_sections: bool = True,
    audit_limit: int = 50,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Assemble nf_discovery_evidence_pack_v1 for a single subject."""
    ref = now or datetime.now(UTC)
    generated_at = ref.isoformat()
    is_demo = is_demo_for_org_type(org.org_type)
    audit_limit = max(0, min(audit_limit, 200))

    if subject_type == EvidencePackSubjectType.opportunity_source:
        return _pack_opportunity_source(
            session,
            org=org,
            org_type=org_type,
            is_demo=is_demo,
            source_id=subject_id,
            include_audit_trail=include_audit_trail,
            include_linked_records=include_linked_records,
            include_sections=include_sections,
            audit_limit=audit_limit,
            generated_at=generated_at,
            ref=ref,
        )
    if subject_type == EvidencePackSubjectType.intake_candidate:
        return _pack_intake_candidate(
            session,
            org=org,
            org_type=org_type,
            is_demo=is_demo,
            candidate_id=subject_id,
            include_audit_trail=include_audit_trail,
            include_linked_records=include_linked_records,
            include_sections=include_sections,
            audit_limit=audit_limit,
            generated_at=generated_at,
            ref=ref,
        )
    if subject_type == EvidencePackSubjectType.grant_spark:
        return _pack_grant_spark(
            session,
            org=org,
            org_type=org_type,
            is_demo=is_demo,
            spark_id=subject_id,
            include_audit_trail=include_audit_trail,
            include_linked_records=include_linked_records,
            include_sections=include_sections,
            audit_limit=audit_limit,
            generated_at=generated_at,
            ref=ref,
        )
    if subject_type == EvidencePackSubjectType.discovery_review_item:
        return _pack_review_item(
            session,
            org=org,
            org_type=org_type,
            is_demo=is_demo,
            review_item_id=subject_id,
            include_audit_trail=include_audit_trail,
            include_linked_records=include_linked_records,
            include_sections=include_sections,
            audit_limit=audit_limit,
            generated_at=generated_at,
            ref=ref,
        )
    if subject_type == EvidencePackSubjectType.operator_action:
        return _pack_operator_action(
            session,
            org=org,
            org_type=org_type,
            is_demo=is_demo,
            operator_action_id=subject_id,
            include_audit_trail=include_audit_trail,
            include_linked_records=include_linked_records,
            include_sections=include_sections,
            audit_limit=audit_limit,
            generated_at=generated_at,
            ref=ref,
        )
    if subject_type == EvidencePackSubjectType.intake_run:
        return _pack_intake_run(
            session,
            org=org,
            org_type=org_type,
            is_demo=is_demo,
            intake_run_id=subject_id,
            include_audit_trail=include_audit_trail,
            include_linked_records=include_linked_records,
            include_sections=include_sections,
            audit_limit=audit_limit,
            generated_at=generated_at,
            ref=ref,
        )
    if subject_type == EvidencePackSubjectType.source_check_run:
        return _pack_source_check_run(
            session,
            org=org,
            org_type=org_type,
            is_demo=is_demo,
            check_run_id=subject_id,
            include_audit_trail=include_audit_trail,
            include_linked_records=include_linked_records,
            include_sections=include_sections,
            audit_limit=audit_limit,
            generated_at=generated_at,
            ref=ref,
        )

    raise ValueError(f"unsupported evidence subject_type: {subject_type}")


def _reference_ids_base(*parts: str | None) -> set[str]:
    out: set[str] = set()
    for p in parts:
        if p:
            out.add(str(p))
    return out


def _finalize_pack(
    *,
    organization_id: uuid.UUID,
    is_demo: bool,
    generated_at: str,
    subject: dict[str, Any],
    provenance_summary: dict[str, Any],
    quality_summary: dict[str, Any],
    review_summary: dict[str, Any],
    freshness_summary: dict[str, Any],
    coverage_summary: dict[str, Any],
    decision_summary: dict[str, Any],
    operator_action_summary: dict[str, Any],
    audit_trail: list[dict[str, Any]],
    linked_records: dict[str, Any],
    trust_warnings: list[dict[str, Any]],
    evidence_sections: list[dict[str, Any]],
) -> dict[str, Any]:
    trust_warnings_sorted = sorted(
        trust_warnings, key=lambda w: w.get("warning_type", "")
    )
    return {
        "schema_version": EVIDENCE_PACK_SCHEMA_VERSION,
        "organization_id": str(organization_id),
        "is_demo": is_demo,
        "generated_at": generated_at,
        "subject": subject,
        "provenance_summary": provenance_summary,
        "quality_summary": quality_summary,
        "review_summary": review_summary,
        "freshness_summary": freshness_summary,
        "coverage_summary": coverage_summary,
        "decision_summary": decision_summary,
        "operator_action_summary": operator_action_summary,
        "audit_trail": audit_trail,
        "linked_records": linked_records,
        "trust_warnings": trust_warnings_sorted,
        "evidence_sections": evidence_sections,
    }


def _pack_opportunity_source(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    is_demo: bool,
    source_id: uuid.UUID,
    include_audit_trail: bool,
    include_linked_records: bool,
    include_sections: bool,
    audit_limit: int,
    generated_at: str,
    ref: datetime,
) -> dict[str, Any]:
    src = os_repo.get_opportunity_source_scoped(
        session=session,
        source_id=source_id,
        org_id=org.id,
        org_type=org_type,
    )
    if src is None:
        raise ValueError("opportunity source not found")

    warnings: list[dict[str, Any]] = []
    if not (src.source_url or "").strip():
        warnings.append(
            _warn(
                EvidencePackWarningType.missing_source_url,
                EvidencePackWarningSeverity.medium,
                "Source URL missing",
                "The registry row has no source_url; provenance is weaker.",
                "Add or verify the canonical listing URL for this source.",
            )
        )
    if src.verification_status == OpportunityVerificationStatus.unverified.value:
        warnings.append(
            _warn(
                EvidencePackWarningType.unverified_source,
                EvidencePackWarningSeverity.medium,
                "Source is unverified",
                "This opportunity source has not yet been operator-verified.",
                "Verify the source before relying on downstream opportunities.",
            )
        )
    health = src.source_health_status
    if health in (
        SourceHealthStatus.stale.value,
        SourceHealthStatus.degraded.value,
        SourceHealthStatus.failing.value,
        SourceHealthStatus.attention_needed.value,
    ):
        warnings.append(
            _warn(
                EvidencePackWarningType.stale_source,
                EvidencePackWarningSeverity.medium,
                "Source health is degraded",
                f"source_health_status={health}",
                "Inspect scheduling, check runs, and registry metadata.",
            )
        )
    if src.last_check_status == SourceLastCheckStatus.failed.value:
        warnings.append(
            _warn(
                EvidencePackWarningType.failed_source_checks,
                EvidencePackWarningSeverity.high,
                "Last source check failed",
                "The most recent scheduled or manual check did not succeed.",
                "Review error metadata and re-run a source check.",
            )
        )
    if (src.consecutive_failure_count or 0) > 0:
        warnings.append(
            _warn(
                EvidencePackWarningType.failed_source_checks,
                EvidencePackWarningSeverity.medium,
                "Repeated source check failures",
                f"consecutive_failure_count={src.consecutive_failure_count}",
                "Investigate connectivity or upstream changes.",
            )
        )

    intake_runs = intake_repo.list_discovery_intake_runs_for_org_source(
        session=session,
        org_id=org.id,
        org_type=org_type,
        source_registry_id=source_id,
    )[:25]
    check_runs = ep_repo.list_related_source_check_runs_for_source(
        session,
        org_id=org.id,
        org_type=org_type,
        source_registry_id=source_id,
        limit=15,
    )
    rev_items = ep_repo.list_related_review_items_for_source(
        session,
        org_id=org.id,
        org_type=org_type,
        source_registry_id=source_id,
        limit=80,
    )
    op_rows = ep_repo.list_related_operator_actions_for_source(
        session,
        org_id=org.id,
        org_type=org_type,
        source_registry_id=source_id,
        limit=80,
    )

    for r in rev_items:
        if r.review_status in _OPEN_REVIEW:
            warnings.append(
                _warn(
                    EvidencePackWarningType.unresolved_review_item,
                    EvidencePackWarningSeverity.medium,
                    "Unresolved discovery review item",
                    f"review_item_id={r.id} status={r.review_status}",
                    "Resolve or approve the queued review item.",
                )
            )
            break
    for oa in op_rows:
        if oa.status in _UNRESOLVED_OA:
            warnings.append(
                _warn(
                    EvidencePackWarningType.unresolved_operator_action,
                    EvidencePackWarningSeverity.medium,
                    "Unresolved operator action",
                    f"operator_action_id={oa.id} status={oa.status}",
                    "Complete or dismiss the linked operator action.",
                )
            )
            break

    gap_intel = dcg_svc.build_coverage_gap_intelligence(
        session,
        org_id=org.id,
        org_type=org_type,
        now=ref,
    )
    related_gaps = [
        g
        for g in gap_intel.get("coverage_gaps", [])
        if str(g.get("source_registry_id") or "") == str(source_id)
    ][:20]

    fresh_d = sfs.opportunity_source_freshness_detail(src, now=ref)

    ref_ids = _reference_ids_base(str(src.id))
    audit_rows: list[dict[str, Any]] = []
    if include_audit_trail and audit_limit > 0:
        raw = ep_repo.list_related_audit_events(
            session,
            org_id=org.id,
            org_type=org_type,
            reference_ids=ref_ids,
            limit=audit_limit,
        )
        audit_rows = [audit_event_to_dict(e) for e in raw]
        if not audit_rows:
            warnings.append(
                _warn(
                    EvidencePackWarningType.no_audit_trail,
                    EvidencePackWarningSeverity.low,
                    "No matching audit events in recent tail",
                    "No audit payloads in the scanned window referenced this source id.",
                    "Confirm audit retention or scope; actions may still be recorded elsewhere.",
                )
            )

    linked: dict[str, Any] = {}
    if include_linked_records:
        linked = {
            "opportunity_source": ods.opportunity_source_to_dict(src),
            "source_freshness_detail": fresh_d,
            "intake_runs_sample": [d_intake.intake_run_to_dict(r) for r in intake_runs],
            "source_check_runs_sample": [sfs.check_run_to_dict(r) for r in check_runs],
            "discovery_review_items_sample": [
                d_review.review_item_to_dict(x) for x in rev_items[:30]
            ],
            "operator_actions_sample": [
                oa_svc.operator_action_to_dict(x) for x in op_rows[:30]
            ],
            "coverage_gap_intel_sample": related_gaps,
        }

    subject = {
        "subject_type": EvidencePackSubjectType.opportunity_source.value,
        "subject_id": str(src.id),
        "title": src.source_name,
        "status": src.verification_status,
        "source_registry_id": str(src.id),
        "intake_run_id": None,
        "intake_candidate_id": None,
    }
    prov = {
        "source_name": src.source_name,
        "source_type": src.source_type,
        "source_url": src.source_url,
        "publisher_name": src.publisher_name,
        "discovered_at": None,
        "last_verified_at": None,
        "duplicate_key": None,
        "input_digest": _digest_json_blob(
            {
                "source_name": src.source_name,
                "source_type": src.source_type,
                "publisher_name": src.publisher_name,
            }
        ),
    }
    sections: list[dict[str, Any]] = []
    if include_sections:
        sections = [
            _section(
                EvidencePackSectionType.freshness,
                "Source freshness",
                f"Health={src.source_health_status or 'unset'}; last_check={src.last_check_status or 'unset'}.",
                [fresh_d],
                [],
                generated_at=generated_at,
            ),
            _section(
                EvidencePackSectionType.coverage,
                "Coverage intelligence (source-filtered)",
                f"{len(related_gaps)} gap row(s) reference this source.",
                related_gaps,
                [],
                generated_at=generated_at,
            ),
            _section(
                EvidencePackSectionType.review,
                "Discovery review (source scope)",
                f"{len(rev_items)} review item(s) linked to this source.",
                [d_review.review_item_to_dict(x) for x in rev_items[:15]],
                [],
                generated_at=generated_at,
            ),
            _section(
                EvidencePackSectionType.action_ledger,
                "Operator actions (source scope)",
                f"{len(op_rows)} ledger row(s) linked to this source.",
                [oa_svc.operator_action_to_dict(x) for x in op_rows[:15]],
                [],
                generated_at=generated_at,
            ),
            _section(
                EvidencePackSectionType.intake_history,
                "Intake history",
                f"{len(intake_runs)} intake run(s) for this source (sample).",
                [d_intake.intake_run_to_dict(r) for r in intake_runs[:10]],
                [],
                generated_at=generated_at,
            ),
        ]
        if include_audit_trail:
            sections.append(
                _section(
                    EvidencePackSectionType.audit_trail,
                    "Audit trail",
                    f"{len(audit_rows)} event(s) matched reference ids.",
                    audit_rows,
                    [],
                    generated_at=generated_at,
                )
            )
        sections.append(
            _section(
                EvidencePackSectionType.trust_warnings,
                "Trust warnings",
                f"{len(warnings)} warning(s) generated.",
                [],
                warnings,
                generated_at=generated_at,
            )
        )

    return _finalize_pack(
        organization_id=org.id,
        is_demo=is_demo,
        generated_at=generated_at,
        subject=subject,
        provenance_summary=prov,
        quality_summary={},
        review_summary={
            "total_linked": len(rev_items),
            "open_review_items": sum(
                1 for r in rev_items if r.review_status in _OPEN_REVIEW
            ),
        },
        freshness_summary=fresh_d,
        coverage_summary={
            "coverage_gap_rows_for_source": len(related_gaps),
            "coverage_intel_schema": gap_intel.get("schema_version"),
        },
        decision_summary={
            "decision_pack_schema_version": DECISION_PACK_SCHEMA_VERSION,
            "note": "Decision pack is built separately; this section links registry context only.",
        },
        operator_action_summary={
            "total_linked": len(op_rows),
            "open_actions": sum(1 for r in op_rows if r.status in _UNRESOLVED_OA),
        },
        audit_trail=audit_rows,
        linked_records=linked,
        trust_warnings=warnings,
        evidence_sections=sections,
    )


def _quality_and_warnings_from_summary(
    qs: dict[str, Any],
    *,
    duplicate_key: str | None,
    duplicate_status: str | None,
    has_deadlines: bool,
) -> list[dict[str, Any]]:
    w: list[dict[str, Any]] = []
    q = int(qs.get("quality_score") or 0)
    if q < _QUALITY_LOW:
        w.append(
            _warn(
                EvidencePackWarningType.low_quality_score,
                EvidencePackWarningSeverity.medium,
                "Discovery quality score is below threshold",
                f"quality_score={q} (threshold {_QUALITY_LOW})",
                "Review fields, deadlines, and duplicate signals.",
            )
        )
    dr = int(qs.get("duplicate_risk_score") or 0)
    if (
        dr >= _DUP_RISK_HIGH
        or duplicate_status == DiscoveryCandidateStatus.duplicate.value
    ):
        w.append(
            _warn(
                EvidencePackWarningType.duplicate_risk,
                EvidencePackWarningSeverity.medium,
                "Elevated duplicate risk",
                f"duplicate_risk_score={dr}; duplicate_key={duplicate_key!r}",
                "Confirm deduplication against existing sparks.",
            )
        )
    if not has_deadlines and "missing_deadline" in (qs.get("reason_codes") or []):
        w.append(
            _warn(
                EvidencePackWarningType.missing_deadline,
                EvidencePackWarningSeverity.medium,
                "Application deadline missing",
                "Quality scoring flagged a missing deadline.",
                "Set or verify deadlines before pursuit decisions.",
            )
        )
    return w


def _pack_intake_candidate(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    is_demo: bool,
    candidate_id: uuid.UUID,
    include_audit_trail: bool,
    include_linked_records: bool,
    include_sections: bool,
    audit_limit: int,
    generated_at: str,
    ref: datetime,
) -> dict[str, Any]:
    cand = intake_repo.get_discovery_intake_candidate_scoped(
        session=session,
        candidate_id=candidate_id,
        org_id=org.id,
        org_type=org_type,
    )
    if cand is None:
        raise ValueError("intake candidate not found")

    run = intake_repo.get_discovery_intake_run_scoped(
        session=session,
        run_id=cand.intake_run_id,
        org_id=org.id,
        org_type=org_type,
    )
    if run is None:
        raise ValueError("parent intake run not found")

    registry = None
    if cand.source_registry_id is not None:
        registry = os_repo.get_opportunity_source_scoped(
            session=session,
            source_id=cand.source_registry_id,
            org_id=org.id,
            org_type=org_type,
        )

    qs = dq.quality_summary_for_intake_candidate(cand, registry, now=ref)
    warnings = _quality_and_warnings_from_summary(
        qs,
        duplicate_key=cand.duplicate_key,
        duplicate_status=cand.candidate_status,
        has_deadlines=_deadline_present_candidate(cand),
    )
    if cand.source_registry_id is None:
        warnings.append(
            _warn(
                EvidencePackWarningType.weak_provenance,
                EvidencePackWarningSeverity.medium,
                "Weak provenance",
                "Intake candidate has no source_registry_id.",
                "Link to a registry source where possible.",
            )
        )
    if (
        registry
        and registry.verification_status
        == OpportunityVerificationStatus.unverified.value
    ):
        warnings.append(
            _warn(
                EvidencePackWarningType.unverified_source,
                EvidencePackWarningSeverity.medium,
                "Linked source is unverified",
                "Registry verification_status is unverified.",
                "Verify the opportunity source.",
            )
        )

    rev_items = rev_repo.list_review_items_for_intake_candidate(
        session,
        org_id=org.id,
        org_type=org_type,
        intake_candidate_id=cand.id,
        limit=50,
    )
    for r in rev_items:
        if r.review_status in _OPEN_REVIEW:
            warnings.append(
                _warn(
                    EvidencePackWarningType.unresolved_review_item,
                    EvidencePackWarningSeverity.medium,
                    "Unresolved discovery review item",
                    f"review_item_id={r.id}",
                    "Resolve the queued review item.",
                )
            )
            break

    op_rows = oa_repo.list_operator_actions_for_org(
        session,
        org_id=org.id,
        org_type=org_type,
        intake_candidate_id=cand.id,
        limit=50,
    )
    for oa in op_rows:
        if oa.status in _UNRESOLVED_OA:
            warnings.append(
                _warn(
                    EvidencePackWarningType.unresolved_operator_action,
                    EvidencePackWarningSeverity.medium,
                    "Unresolved operator action",
                    f"operator_action_id={oa.id}",
                    "Complete the linked operator action.",
                )
            )
            break

    spark_row = None
    if cand.created_spark_id is not None:
        spark_row = gs_repo.get_grant_spark_scoped(
            session=session,
            spark_id=cand.created_spark_id,
            org_id=org.id,
            org_type=org_type,
        )

    ref_ids = _reference_ids_base(
        str(cand.id),
        str(run.id),
        str(cand.source_registry_id) if cand.source_registry_id else None,
        str(cand.created_spark_id) if cand.created_spark_id else None,
    )
    audit_rows: list[dict[str, Any]] = []
    if include_audit_trail and audit_limit > 0:
        raw = ep_repo.list_related_audit_events(
            session,
            org_id=org.id,
            org_type=org_type,
            reference_ids=ref_ids,
            limit=audit_limit,
        )
        audit_rows = [audit_event_to_dict(e) for e in raw]
        if not audit_rows:
            warnings.append(
                _warn(
                    EvidencePackWarningType.no_audit_trail,
                    EvidencePackWarningSeverity.low,
                    "No matching audit events in recent tail",
                    "No audit payloads referenced this candidate in the scanned window.",
                    "Confirm audit coverage for intake scoring events.",
                )
            )

    linked: dict[str, Any] = {}
    if include_linked_records:
        linked = {
            "intake_candidate": d_intake.intake_candidate_to_dict(cand),
            "intake_run": d_intake.intake_run_to_dict(run),
            "opportunity_source": ods.opportunity_source_to_dict(registry)
            if registry
            else None,
            "grant_spark_created": gss.spark_to_dict(spark_row) if spark_row else None,
        }

    subject = {
        "subject_type": EvidencePackSubjectType.intake_candidate.value,
        "subject_id": str(cand.id),
        "title": _candidate_title(cand),
        "status": cand.candidate_status,
        "source_registry_id": str(cand.source_registry_id)
        if cand.source_registry_id
        else None,
        "intake_run_id": str(run.id),
        "intake_candidate_id": str(cand.id),
    }
    prov = {
        "source_name": registry.source_name if registry else None,
        "source_type": registry.source_type if registry else None,
        "source_url": registry.source_url if registry else None,
        "publisher_name": registry.publisher_name if registry else None,
        "discovered_at": _dt(cand.created_at),
        "last_verified_at": None,
        "duplicate_key": cand.duplicate_key,
        "input_digest": _digest_json_blob(cand.raw_candidate_json),
    }

    sections: list[dict[str, Any]] = []
    if include_sections:
        sections = [
            _section(
                EvidencePackSectionType.quality,
                "Discovery quality",
                f"Quality score {qs.get('quality_score')}; review_required={qs.get('review_required')}.",
                [qs],
                [],
                generated_at=generated_at,
            ),
            _section(
                EvidencePackSectionType.review,
                "Discovery review",
                f"{len(rev_items)} review item(s) for this candidate.",
                [d_review.review_item_to_dict(x) for x in rev_items[:15]],
                [],
                generated_at=generated_at,
            ),
            _section(
                EvidencePackSectionType.action_ledger,
                "Operator actions",
                f"{len(op_rows)} ledger row(s) referencing this candidate.",
                [oa_svc.operator_action_to_dict(x) for x in op_rows[:15]],
                [],
                generated_at=generated_at,
            ),
        ]
        if include_audit_trail:
            sections.append(
                _section(
                    EvidencePackSectionType.audit_trail,
                    "Audit trail",
                    f"{len(audit_rows)} event(s).",
                    audit_rows,
                    [],
                    generated_at=generated_at,
                )
            )

    return _finalize_pack(
        organization_id=org.id,
        is_demo=is_demo,
        generated_at=generated_at,
        subject=subject,
        provenance_summary=prov,
        quality_summary=qs,
        review_summary={
            "items": [d_review.review_item_to_dict(x) for x in rev_items[:20]]
        },
        freshness_summary={},
        coverage_summary={},
        decision_summary={},
        operator_action_summary={
            "rows": [oa_svc.operator_action_to_dict(x) for x in op_rows[:10]]
        },
        audit_trail=audit_rows,
        linked_records=linked,
        trust_warnings=warnings,
        evidence_sections=sections,
    )


def _candidate_title(cand: NfDiscoveryIntakeCandidate) -> str:
    raw = cand.normalized_candidate_json or cand.raw_candidate_json
    if isinstance(raw, dict):
        t = raw.get("opportunity_title")
        if isinstance(t, str) and t.strip():
            return t.strip()
    return "Intake candidate"


def _deadline_present_candidate(cand: NfDiscoveryIntakeCandidate) -> bool:
    raw = cand.normalized_candidate_json or cand.raw_candidate_json
    if not isinstance(raw, dict):
        return False
    return bool(raw.get("application_deadline") or raw.get("loi_deadline"))


def _pack_grant_spark(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    is_demo: bool,
    spark_id: uuid.UUID,
    include_audit_trail: bool,
    include_linked_records: bool,
    include_sections: bool,
    audit_limit: int,
    generated_at: str,
    ref: datetime,
) -> dict[str, Any]:
    spark = gs_repo.get_grant_spark_scoped(
        session=session,
        spark_id=spark_id,
        org_id=org.id,
        org_type=org_type,
    )
    if spark is None:
        raise ValueError("grant spark not found")

    registry = None
    if spark.source_registry_id is not None:
        registry = os_repo.get_opportunity_source_scoped(
            session=session,
            source_id=spark.source_registry_id,
            org_id=org.id,
            org_type=org_type,
        )

    qs = dq.quality_summary_for_grant_spark(spark, registry, now=ref)
    warnings = _quality_and_warnings_from_summary(
        qs,
        duplicate_key=spark.duplicate_key,
        duplicate_status=None,
        has_deadlines=spark.application_deadline is not None
        or spark.loi_deadline is not None,
    )
    if spark.source_registry_id is None:
        warnings.append(
            _warn(
                EvidencePackWarningType.weak_provenance,
                EvidencePackWarningSeverity.medium,
                "Weak provenance",
                "Grant Spark has no source_registry_id.",
                "Attach registry provenance when available.",
            )
        )
    if (
        registry
        and registry.verification_status
        == OpportunityVerificationStatus.unverified.value
    ):
        warnings.append(
            _warn(
                EvidencePackWarningType.unverified_source,
                EvidencePackWarningSeverity.medium,
                "Linked source is unverified",
                "Registry verification_status is unverified.",
                "Verify the opportunity source.",
            )
        )

    cand = _find_candidate_for_created_spark(
        session, org_id=org.id, org_type=org_type, spark_id=spark.id
    )

    rev_items = rev_repo.list_review_items_for_grant_spark(
        session,
        org_id=org.id,
        org_type=org_type,
        grant_spark_id=spark.id,
        limit=50,
    )
    for r in rev_items:
        if r.review_status in _OPEN_REVIEW:
            warnings.append(
                _warn(
                    EvidencePackWarningType.unresolved_review_item,
                    EvidencePackWarningSeverity.medium,
                    "Unresolved discovery review item",
                    f"review_item_id={r.id}",
                    "Resolve the queued review item.",
                )
            )
            break

    op_rows = oa_repo.list_operator_actions_for_org(
        session,
        org_id=org.id,
        org_type=org_type,
        grant_spark_id=spark.id,
        limit=50,
    )
    for oa in op_rows:
        if oa.status in _UNRESOLVED_OA:
            warnings.append(
                _warn(
                    EvidencePackWarningType.unresolved_operator_action,
                    EvidencePackWarningSeverity.medium,
                    "Unresolved operator action",
                    f"operator_action_id={oa.id}",
                    "Complete the linked operator action.",
                )
            )
            break

    score = score_repo.get_latest_spark_score(
        session=session,
        spark_id=spark.id,
        org_id=org.id,
        org_type=org_type,
    )
    decision_summary: dict[str, Any] = {
        "decision_pack_schema_version": DECISION_PACK_SCHEMA_VERSION,
        "latest_spark_score": {
            "composite": float(score.composite) if score is not None else None,
            "recommendation": score.recommendation if score is not None else None,
            "disqualified": score.disqualified if score is not None else None,
        }
        if score
        else None,
        "discovery_recommended_action": qs.get("recommended_action"),
    }

    ref_ids = _reference_ids_base(
        str(spark.id),
        str(spark.source_registry_id) if spark.source_registry_id else None,
        str(cand.id) if cand else None,
    )
    audit_rows: list[dict[str, Any]] = []
    if include_audit_trail and audit_limit > 0:
        raw = ep_repo.list_related_audit_events(
            session,
            org_id=org.id,
            org_type=org_type,
            reference_ids=ref_ids,
            limit=audit_limit,
        )
        audit_rows = [audit_event_to_dict(e) for e in raw]
        if not audit_rows:
            warnings.append(
                _warn(
                    EvidencePackWarningType.no_audit_trail,
                    EvidencePackWarningSeverity.low,
                    "No matching audit events in recent tail",
                    "No audit payloads referenced this spark in the scanned window.",
                    "Confirm scoring and review audits are present.",
                )
            )

    linked: dict[str, Any] = {}
    if include_linked_records:
        linked = {
            "grant_spark": gss.spark_to_dict(spark),
            "opportunity_source": ods.opportunity_source_to_dict(registry)
            if registry
            else None,
            "intake_candidate": d_intake.intake_candidate_to_dict(cand)
            if cand
            else None,
        }

    subject = {
        "subject_type": EvidencePackSubjectType.grant_spark.value,
        "subject_id": str(spark.id),
        "title": spark.opportunity_title,
        "status": spark.pipeline_stage,
        "source_registry_id": str(spark.source_registry_id)
        if spark.source_registry_id
        else None,
        "intake_run_id": str(cand.intake_run_id) if cand else None,
        "intake_candidate_id": str(cand.id) if cand else None,
    }
    prov = {
        "source_name": registry.source_name if registry else spark.publisher_name,
        "source_type": registry.source_type if registry else spark.source_type,
        "source_url": (registry.source_url if registry else None) or spark.source_url,
        "publisher_name": spark.publisher_name,
        "discovered_at": _dt(spark.discovered_at),
        "last_verified_at": _dt(spark.last_verified_at),
        "duplicate_key": spark.duplicate_key,
        "input_digest": _digest_json_blob(
            {
                "title": spark.opportunity_title,
                "agency": spark.agency,
                "source_id": spark.source_id,
            }
        ),
    }

    sections: list[dict[str, Any]] = []
    if include_sections:
        sections = [
            _section(
                EvidencePackSectionType.quality,
                "Discovery quality",
                f"Quality score {qs.get('quality_score')}.",
                [qs],
                [],
                generated_at=generated_at,
            ),
            _section(
                EvidencePackSectionType.decision,
                "Scoring / recommendation",
                "Latest deterministic spark score snapshot (if present).",
                [decision_summary["latest_spark_score"]] if score else [],
                [],
                generated_at=generated_at,
            ),
            _section(
                EvidencePackSectionType.review,
                "Discovery review",
                f"{len(rev_items)} review item(s) for this spark.",
                [d_review.review_item_to_dict(x) for x in rev_items[:15]],
                [],
                generated_at=generated_at,
            ),
            _section(
                EvidencePackSectionType.action_ledger,
                "Operator actions",
                f"{len(op_rows)} ledger row(s) referencing this spark.",
                [oa_svc.operator_action_to_dict(x) for x in op_rows[:15]],
                [],
                generated_at=generated_at,
            ),
        ]
        if include_audit_trail:
            sections.append(
                _section(
                    EvidencePackSectionType.audit_trail,
                    "Audit trail",
                    f"{len(audit_rows)} event(s).",
                    audit_rows,
                    [],
                    generated_at=generated_at,
                )
            )

    return _finalize_pack(
        organization_id=org.id,
        is_demo=is_demo,
        generated_at=generated_at,
        subject=subject,
        provenance_summary=prov,
        quality_summary=qs,
        review_summary={
            "items": [d_review.review_item_to_dict(x) for x in rev_items[:20]]
        },
        freshness_summary={"spark_freshness_status": spark.freshness_status},
        coverage_summary={},
        decision_summary=decision_summary,
        operator_action_summary={
            "rows": [oa_svc.operator_action_to_dict(x) for x in op_rows[:10]]
        },
        audit_trail=audit_rows,
        linked_records=linked,
        trust_warnings=warnings,
        evidence_sections=sections,
    )


def _pack_review_item(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    is_demo: bool,
    review_item_id: uuid.UUID,
    include_audit_trail: bool,
    include_linked_records: bool,
    include_sections: bool,
    audit_limit: int,
    generated_at: str,
    ref: datetime,
) -> dict[str, Any]:
    row = rev_repo.get_review_item_scoped(
        session,
        review_item_id=review_item_id,
        org_id=org.id,
        org_type=org_type,
    )
    if row is None:
        raise ValueError("discovery review item not found")

    warnings: list[dict[str, Any]] = []
    if row.review_status in _OPEN_REVIEW:
        warnings.append(
            _warn(
                EvidencePackWarningType.unresolved_review_item,
                EvidencePackWarningSeverity.medium,
                "Review item is unresolved",
                f"status={row.review_status}",
                "Complete operator review for this queue row.",
            )
        )

    qs: dict[str, Any] = {}
    cand = None
    spark = None
    registry = None

    if row.intake_candidate_id is not None:
        cand = intake_repo.get_discovery_intake_candidate_scoped(
            session=session,
            candidate_id=row.intake_candidate_id,
            org_id=org.id,
            org_type=org_type,
        )
        if cand:
            if cand.source_registry_id:
                registry = os_repo.get_opportunity_source_scoped(
                    session=session,
                    source_id=cand.source_registry_id,
                    org_id=org.id,
                    org_type=org_type,
                )
            qs = dq.quality_summary_for_intake_candidate(cand, registry, now=ref)
            warnings.extend(
                _quality_and_warnings_from_summary(
                    qs,
                    duplicate_key=cand.duplicate_key,
                    duplicate_status=cand.candidate_status,
                    has_deadlines=_deadline_present_candidate(cand),
                )
            )

    if row.grant_spark_id is not None:
        spark = gs_repo.get_grant_spark_scoped(
            session=session,
            spark_id=row.grant_spark_id,
            org_id=org.id,
            org_type=org_type,
        )
        if spark:
            if spark.source_registry_id:
                registry = os_repo.get_opportunity_source_scoped(
                    session=session,
                    source_id=spark.source_registry_id,
                    org_id=org.id,
                    org_type=org_type,
                )
            qs = dq.quality_summary_for_grant_spark(spark, registry, now=ref)
            warnings.extend(
                _quality_and_warnings_from_summary(
                    qs,
                    duplicate_key=spark.duplicate_key,
                    duplicate_status=None,
                    has_deadlines=spark.application_deadline is not None
                    or spark.loi_deadline is not None,
                )
            )

    if row.source_registry_id and registry is None:
        registry = os_repo.get_opportunity_source_scoped(
            session=session,
            source_id=row.source_registry_id,
            org_id=org.id,
            org_type=org_type,
        )
    if (
        registry
        and registry.verification_status
        == OpportunityVerificationStatus.unverified.value
    ):
        warnings.append(
            _warn(
                EvidencePackWarningType.unverified_source,
                EvidencePackWarningSeverity.medium,
                "Linked source is unverified",
                "Registry verification_status is unverified.",
                "Verify the opportunity source.",
            )
        )

    op_rows = ep_repo.list_related_operator_actions_for_review_item(
        session,
        org_id=org.id,
        org_type=org_type,
        review_item_id=row.id,
        limit=50,
    )
    for oa in op_rows:
        if oa.status in _UNRESOLVED_OA:
            warnings.append(
                _warn(
                    EvidencePackWarningType.unresolved_operator_action,
                    EvidencePackWarningSeverity.medium,
                    "Unresolved operator action linked to review item",
                    f"operator_action_id={oa.id}",
                    "Resolve linked operator actions.",
                )
            )
            break

    ref_ids = _reference_ids_base(
        str(row.id),
        str(row.source_registry_id) if row.source_registry_id else None,
        str(row.intake_candidate_id) if row.intake_candidate_id else None,
        str(row.grant_spark_id) if row.grant_spark_id else None,
    )
    audit_rows: list[dict[str, Any]] = []
    if include_audit_trail and audit_limit > 0:
        raw = ep_repo.list_related_audit_events(
            session,
            org_id=org.id,
            org_type=org_type,
            reference_ids=ref_ids,
            limit=audit_limit,
        )
        audit_rows = [audit_event_to_dict(e) for e in raw]
        if not audit_rows:
            warnings.append(
                _warn(
                    EvidencePackWarningType.no_audit_trail,
                    EvidencePackWarningSeverity.low,
                    "No matching audit events in recent tail",
                    "No audit payloads referenced this review item in the scanned window.",
                    "Confirm discovery_review_item audits.",
                )
            )

    linked: dict[str, Any] = {}
    if include_linked_records:
        linked = {
            "discovery_review_item": d_review.review_item_to_dict(row),
            "opportunity_source": ods.opportunity_source_to_dict(registry)
            if registry
            else None,
            "intake_candidate": d_intake.intake_candidate_to_dict(cand)
            if cand
            else None,
            "grant_spark": gss.spark_to_dict(spark) if spark else None,
        }

    subject = {
        "subject_type": EvidencePackSubjectType.discovery_review_item.value,
        "subject_id": str(row.id),
        "title": f"Review {row.review_item_type}",
        "status": row.review_status,
        "source_registry_id": str(row.source_registry_id)
        if row.source_registry_id
        else None,
        "intake_run_id": str(row.intake_run_id) if row.intake_run_id else None,
        "intake_candidate_id": str(row.intake_candidate_id)
        if row.intake_candidate_id
        else None,
    }
    prov = {
        "source_name": registry.source_name if registry else None,
        "source_type": registry.source_type if registry else None,
        "source_url": registry.source_url if registry else None,
        "publisher_name": registry.publisher_name if registry else None,
        "discovered_at": None,
        "last_verified_at": None,
        "duplicate_key": None,
        "input_digest": _digest_json_blob(d_review.review_item_to_dict(row)),
    }

    sections: list[dict[str, Any]] = []
    if include_sections:
        sections = [
            _section(
                EvidencePackSectionType.quality,
                "Discovery quality",
                "Quality summary derived from linked candidate or spark when present.",
                [qs] if qs else [],
                [],
                generated_at=generated_at,
            ),
            _section(
                EvidencePackSectionType.review,
                "Review item",
                f"Type={row.review_item_type}; status={row.review_status}.",
                [d_review.review_item_to_dict(row)],
                [],
                generated_at=generated_at,
            ),
            _section(
                EvidencePackSectionType.action_ledger,
                "Operator actions",
                f"{len(op_rows)} ledger row(s) linked to this review item.",
                [oa_svc.operator_action_to_dict(x) for x in op_rows[:15]],
                [],
                generated_at=generated_at,
            ),
        ]
        if include_audit_trail:
            sections.append(
                _section(
                    EvidencePackSectionType.audit_trail,
                    "Audit trail",
                    f"{len(audit_rows)} event(s).",
                    audit_rows,
                    [],
                    generated_at=generated_at,
                )
            )

    return _finalize_pack(
        organization_id=org.id,
        is_demo=is_demo,
        generated_at=generated_at,
        subject=subject,
        provenance_summary=prov,
        quality_summary=qs,
        review_summary={"primary": d_review.review_item_to_dict(row)},
        freshness_summary={},
        coverage_summary={},
        decision_summary={},
        operator_action_summary={
            "rows": [oa_svc.operator_action_to_dict(x) for x in op_rows[:10]]
        },
        audit_trail=audit_rows,
        linked_records=linked,
        trust_warnings=warnings,
        evidence_sections=sections,
    )


def _pack_operator_action(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    is_demo: bool,
    operator_action_id: uuid.UUID,
    include_audit_trail: bool,
    include_linked_records: bool,
    include_sections: bool,
    audit_limit: int,
    generated_at: str,
    ref: datetime,
) -> dict[str, Any]:
    row = oa_repo.get_operator_action_scoped(
        session,
        action_id=operator_action_id,
        org_id=org.id,
        org_type=org_type,
    )
    if row is None:
        raise ValueError("operator action not found")

    warnings: list[dict[str, Any]] = []
    if row.status in _UNRESOLVED_OA:
        warnings.append(
            _warn(
                EvidencePackWarningType.unresolved_operator_action,
                EvidencePackWarningSeverity.medium,
                "Operator action is not resolved",
                f"status={row.status}",
                "Resolve or dismiss this ledger entry.",
            )
        )

    registry = None
    if row.source_registry_id:
        registry = os_repo.get_opportunity_source_scoped(
            session=session,
            source_id=row.source_registry_id,
            org_id=org.id,
            org_type=org_type,
        )
    if registry:
        if not (registry.source_url or "").strip():
            warnings.append(
                _warn(
                    EvidencePackWarningType.missing_source_url,
                    EvidencePackWarningSeverity.low,
                    "Linked source URL missing",
                    "Operator action references a registry row without source_url.",
                    "Backfill registry metadata.",
                )
            )
        if (
            registry.verification_status
            == OpportunityVerificationStatus.unverified.value
        ):
            warnings.append(
                _warn(
                    EvidencePackWarningType.unverified_source,
                    EvidencePackWarningSeverity.medium,
                    "Linked source is unverified",
                    "Registry verification_status is unverified.",
                    "Verify the opportunity source.",
                )
            )
        if registry.source_health_status in (
            SourceHealthStatus.stale.value,
            SourceHealthStatus.degraded.value,
            SourceHealthStatus.failing.value,
        ):
            warnings.append(
                _warn(
                    EvidencePackWarningType.stale_source,
                    EvidencePackWarningSeverity.medium,
                    "Linked source health is degraded",
                    f"source_health_status={registry.source_health_status}",
                    "Inspect monitoring and check-run outcomes.",
                )
            )
        if registry.last_check_status == SourceLastCheckStatus.failed.value:
            warnings.append(
                _warn(
                    EvidencePackWarningType.failed_source_checks,
                    EvidencePackWarningSeverity.high,
                    "Linked source check failed",
                    "Last check status on the registry row is failed.",
                    "Investigate connectivity or upstream changes.",
                )
            )

    ref_ids = _reference_ids_base(
        str(row.id),
        str(row.source_registry_id) if row.source_registry_id else None,
        str(row.review_item_id) if row.review_item_id else None,
        str(row.intake_candidate_id) if row.intake_candidate_id else None,
        str(row.grant_spark_id) if row.grant_spark_id else None,
        str(row.intake_run_id) if row.intake_run_id else None,
        str(row.source_check_run_id) if row.source_check_run_id else None,
        row.decision_id,
    )
    audit_rows: list[dict[str, Any]] = []
    if include_audit_trail and audit_limit > 0:
        raw = ep_repo.list_related_audit_events(
            session,
            org_id=org.id,
            org_type=org_type,
            reference_ids=ref_ids,
            limit=audit_limit,
        )
        audit_rows = [audit_event_to_dict(e) for e in raw]
        if not audit_rows:
            warnings.append(
                _warn(
                    EvidencePackWarningType.no_audit_trail,
                    EvidencePackWarningSeverity.low,
                    "No matching audit events in recent tail",
                    "No audit payloads referenced this operator action in the scanned window.",
                    "Confirm operator_action_* audits.",
                )
            )

    linked: dict[str, Any] = {}
    if include_linked_records:
        rev = (
            rev_repo.get_review_item_scoped(
                session,
                review_item_id=row.review_item_id,
                org_id=org.id,
                org_type=org_type,
            )
            if row.review_item_id
            else None
        )
        cand = (
            intake_repo.get_discovery_intake_candidate_scoped(
                session=session,
                candidate_id=row.intake_candidate_id,
                org_id=org.id,
                org_type=org_type,
            )
            if row.intake_candidate_id
            else None
        )
        spark = (
            gs_repo.get_grant_spark_scoped(
                session=session,
                spark_id=row.grant_spark_id,
                org_id=org.id,
                org_type=org_type,
            )
            if row.grant_spark_id
            else None
        )
        run = (
            intake_repo.get_discovery_intake_run_scoped(
                session=session,
                run_id=row.intake_run_id,
                org_id=org.id,
                org_type=org_type,
            )
            if row.intake_run_id
            else None
        )

        check_run = (
            scr_repo.get_source_check_run_scoped(
                session,
                check_run_id=row.source_check_run_id,
                org_id=org.id,
                org_type=org_type,
            )
            if row.source_check_run_id
            else None
        )

        linked = {
            "operator_action": oa_svc.operator_action_to_dict(row),
            "opportunity_source": ods.opportunity_source_to_dict(registry)
            if registry
            else None,
            "discovery_review_item": d_review.review_item_to_dict(rev) if rev else None,
            "intake_run": d_intake.intake_run_to_dict(run) if run else None,
            "intake_candidate": d_intake.intake_candidate_to_dict(cand)
            if cand
            else None,
            "grant_spark": gss.spark_to_dict(spark) if spark else None,
            "source_check_run": sfs.check_run_to_dict(check_run) if check_run else None,
        }

    subject = {
        "subject_type": EvidencePackSubjectType.operator_action.value,
        "subject_id": str(row.id),
        "title": row.action_title,
        "status": row.status,
        "source_registry_id": str(row.source_registry_id)
        if row.source_registry_id
        else None,
        "intake_run_id": str(row.intake_run_id) if row.intake_run_id else None,
        "intake_candidate_id": str(row.intake_candidate_id)
        if row.intake_candidate_id
        else None,
    }
    prov = {
        "source_name": registry.source_name if registry else None,
        "source_type": registry.source_type if registry else None,
        "source_url": registry.source_url if registry else None,
        "publisher_name": registry.publisher_name if registry else None,
        "discovered_at": None,
        "last_verified_at": None,
        "duplicate_key": None,
        "input_digest": _digest_json_blob(row.source_decision_item_json),
    }

    decision_summary = {
        "decision_pack_schema_version": DECISION_PACK_SCHEMA_VERSION,
        "decision_id": row.decision_id,
        "decision_schema_version": row.decision_schema_version,
        "source_decision_item_json": row.source_decision_item_json,
    }

    sections: list[dict[str, Any]] = []
    if include_sections:
        sections = [
            _section(
                EvidencePackSectionType.decision,
                "Decision / ledger context",
                "Operator action with embedded decision item JSON when present.",
                [decision_summary],
                [],
                generated_at=generated_at,
            ),
            _section(
                EvidencePackSectionType.action_ledger,
                "Operator action",
                f"status={row.status}; severity={row.severity}.",
                [oa_svc.operator_action_to_dict(row)],
                [],
                generated_at=generated_at,
            ),
        ]
        if include_audit_trail:
            sections.append(
                _section(
                    EvidencePackSectionType.audit_trail,
                    "Audit trail",
                    f"{len(audit_rows)} event(s).",
                    audit_rows,
                    [],
                    generated_at=generated_at,
                )
            )

    return _finalize_pack(
        organization_id=org.id,
        is_demo=is_demo,
        generated_at=generated_at,
        subject=subject,
        provenance_summary=prov,
        quality_summary={},
        review_summary={},
        freshness_summary={},
        coverage_summary={"coverage_gap_id": row.coverage_gap_id},
        decision_summary=decision_summary,
        operator_action_summary={"primary": oa_svc.operator_action_to_dict(row)},
        audit_trail=audit_rows,
        linked_records=linked,
        trust_warnings=warnings,
        evidence_sections=sections,
    )


def _pack_intake_run(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    is_demo: bool,
    intake_run_id: uuid.UUID,
    include_audit_trail: bool,
    include_linked_records: bool,
    include_sections: bool,
    audit_limit: int,
    generated_at: str,
    ref: datetime,
) -> dict[str, Any]:
    run = intake_repo.get_discovery_intake_run_scoped(
        session=session,
        run_id=intake_run_id,
        org_id=org.id,
        org_type=org_type,
    )
    if run is None:
        raise ValueError("intake run not found")
    src = os_repo.get_opportunity_source_scoped(
        session=session,
        source_id=run.source_registry_id,
        org_id=org.id,
        org_type=org_type,
    )
    if src is None:
        raise ValueError("opportunity source for intake run not found")

    cands = intake_repo.list_discovery_intake_candidates_for_run(
        session=session,
        org_id=org.id,
        org_type=org_type,
        intake_run_id=run.id,
    )[:50]

    warnings: list[dict[str, Any]] = []
    if src.verification_status == OpportunityVerificationStatus.unverified.value:
        warnings.append(
            _warn(
                EvidencePackWarningType.unverified_source,
                EvidencePackWarningSeverity.medium,
                "Source is unverified",
                "Linked registry row is unverified.",
                "Verify the source.",
            )
        )

    ref_ids = _reference_ids_base(str(run.id), str(run.source_registry_id))
    audit_rows: list[dict[str, Any]] = []
    if include_audit_trail and audit_limit > 0:
        raw = ep_repo.list_related_audit_events(
            session,
            org_id=org.id,
            org_type=org_type,
            reference_ids=ref_ids,
            limit=audit_limit,
        )
        audit_rows = [audit_event_to_dict(e) for e in raw]

    linked: dict[str, Any] = {}
    if include_linked_records:
        linked = {
            "intake_run": d_intake.intake_run_to_dict(run),
            "opportunity_source": ods.opportunity_source_to_dict(src),
            "candidates_sample": [
                d_intake.intake_candidate_to_dict(c) for c in cands[:15]
            ],
        }

    subject = {
        "subject_type": EvidencePackSubjectType.intake_run.value,
        "subject_id": str(run.id),
        "title": f"Intake run {run.run_status}",
        "status": run.run_status,
        "source_registry_id": str(run.source_registry_id),
        "intake_run_id": str(run.id),
        "intake_candidate_id": None,
    }
    prov = {
        "source_name": src.source_name,
        "source_type": src.source_type,
        "source_url": src.source_url,
        "publisher_name": src.publisher_name,
        "discovered_at": _dt(run.started_at),
        "last_verified_at": None,
        "duplicate_key": None,
        "input_digest": _digest_json_blob(run.run_summary_json),
    }

    sections: list[dict[str, Any]] = []
    if include_sections:
        sections = [
            _section(
                EvidencePackSectionType.intake_history,
                "Intake run",
                f"Candidates={run.candidate_count}; status={run.run_status}.",
                [d_intake.intake_run_to_dict(run)],
                [],
                generated_at=generated_at,
            ),
        ]
        if include_audit_trail:
            sections.append(
                _section(
                    EvidencePackSectionType.audit_trail,
                    "Audit trail",
                    f"{len(audit_rows)} event(s).",
                    audit_rows,
                    [],
                    generated_at=generated_at,
                )
            )

    return _finalize_pack(
        organization_id=org.id,
        is_demo=is_demo,
        generated_at=generated_at,
        subject=subject,
        provenance_summary=prov,
        quality_summary={},
        review_summary={},
        freshness_summary=sfs.opportunity_source_freshness_detail(src, now=ref),
        coverage_summary={},
        decision_summary={},
        operator_action_summary={},
        audit_trail=audit_rows,
        linked_records=linked,
        trust_warnings=warnings,
        evidence_sections=sections,
    )


def _pack_source_check_run(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    is_demo: bool,
    check_run_id: uuid.UUID,
    include_audit_trail: bool,
    include_linked_records: bool,
    include_sections: bool,
    audit_limit: int,
    generated_at: str,
    ref: datetime,
) -> dict[str, Any]:
    run = scr_repo.get_source_check_run_scoped(
        session,
        check_run_id=check_run_id,
        org_id=org.id,
        org_type=org_type,
    )
    if run is None:
        raise ValueError("source check run not found")

    src = os_repo.get_opportunity_source_scoped(
        session=session,
        source_id=run.source_registry_id,
        org_id=org.id,
        org_type=org_type,
    )
    if src is None:
        raise ValueError("opportunity source for check run not found")

    warnings: list[dict[str, Any]] = []
    if run.check_status == SourceCheckRunStatus.failed.value:
        warnings.append(
            _warn(
                EvidencePackWarningType.failed_source_checks,
                EvidencePackWarningSeverity.high,
                "Source check run failed",
                f"check_run_id={run.id}",
                "Inspect error metadata and retry.",
            )
        )

    ref_ids = _reference_ids_base(str(run.id), str(run.source_registry_id))
    audit_rows: list[dict[str, Any]] = []
    if include_audit_trail and audit_limit > 0:
        raw = ep_repo.list_related_audit_events(
            session,
            org_id=org.id,
            org_type=org_type,
            reference_ids=ref_ids,
            limit=audit_limit,
        )
        audit_rows = [audit_event_to_dict(e) for e in raw]

    linked: dict[str, Any] = {}
    if include_linked_records:
        linked = {
            "source_check_run": sfs.check_run_to_dict(run),
            "opportunity_source": ods.opportunity_source_to_dict(src),
        }

    subject = {
        "subject_type": EvidencePackSubjectType.source_check_run.value,
        "subject_id": str(run.id),
        "title": f"Source check ({run.check_mode})",
        "status": run.check_status,
        "source_registry_id": str(run.source_registry_id),
        "intake_run_id": None,
        "intake_candidate_id": None,
    }
    prov = {
        "source_name": src.source_name,
        "source_type": src.source_type,
        "source_url": src.source_url,
        "publisher_name": src.publisher_name,
        "discovered_at": _dt(run.started_at),
        "last_verified_at": None,
        "duplicate_key": None,
        "input_digest": _digest_json_blob(run.result_summary_json),
    }

    sections: list[dict[str, Any]] = []
    if include_sections:
        sections = [
            _section(
                EvidencePackSectionType.freshness,
                "Source check run",
                f"Status={run.check_status}; mode={run.check_mode}.",
                [sfs.check_run_to_dict(run)],
                [],
                generated_at=generated_at,
            ),
        ]
        if include_audit_trail:
            sections.append(
                _section(
                    EvidencePackSectionType.audit_trail,
                    "Audit trail",
                    f"{len(audit_rows)} event(s).",
                    audit_rows,
                    [],
                    generated_at=generated_at,
                )
            )

    return _finalize_pack(
        organization_id=org.id,
        is_demo=is_demo,
        generated_at=generated_at,
        subject=subject,
        provenance_summary=prov,
        quality_summary={},
        review_summary={},
        freshness_summary=sfs.opportunity_source_freshness_detail(src, now=ref),
        coverage_summary={},
        decision_summary={},
        operator_action_summary={},
        audit_trail=audit_rows,
        linked_records=linked,
        trust_warnings=warnings,
        evidence_sections=sections,
    )
