"""Sprint 7: trust manifest, review visibility, org-wide data export."""

from __future__ import annotations

from collections import Counter
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from nativeforge.db.models import (
    NfFormPackage,
    NfNofoExtractionRun,
    NfSparkScore,
    Organization,
    is_demo_for_org_type,
)
from nativeforge.domain.enums import AuditAction
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import audit_events as audit_repo
from nativeforge.repositories import discovery_review_items as nf_rev_repo
from nativeforge.repositories import form_packages as fp_repo
from nativeforge.repositories import grant_sparks as gs_repo
from nativeforge.repositories import nofo_extraction as ne_repo
from nativeforge.repositories import pursuits as pursuit_repo
from nativeforge.repositories import review_artifacts as ra_repo
from nativeforge.repositories import spark_scores as score_repo
from nativeforge.services import discovery_review_service as dr_svc
from nativeforge.services import grant_spark_service as gss
from nativeforge.services import pursuit_service as psvc
from nativeforge.services import tribal_profile_service as tps

MANIFEST_SCHEMA_VERSION = "m0_trust_v1"
ORG_DATA_SNAPSHOT_VERSION = "org_data_snapshot_v1"


def _dt(v: object | None) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()  # type: ignore[no-any-return]
    return str(v)


def _num(v: object | None) -> float | None:
    if v is None:
        return None
    if isinstance(v, Decimal):
        return float(v)
    return float(v)  # type: ignore[arg-type]


def build_trust_manifest(*, org_type: OrgType) -> dict[str, Any]:
    """Deterministic policy payload for buyer-trust surfaces (M0)."""
    is_demo = org_type == "demo"
    return {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "organization_context": {
            "request_plane": "demo" if is_demo else "real",
            "demo_data_isolation": {
                "enforced": True,
                "detail": (
                    "Demo organizations use the demo API plane and row-level "
                    "demo flags; they do not share persistence with real org rows."
                ),
            },
        },
        "data_ownership": {
            "statement": (
                "Your organization retains authority over data stored under "
                "your tenant; NativeForge acts as processor under your direction "
                "for M0 features described in documentation."
            ),
        },
        "submission_policy": {
            "automatic_submission_enabled": False,
            "grants_gov_auto_submit": False,
            "statement": (
                "M0 does not submit applications to Grants.gov or any agency "
                "portal. Submission stays manual outside NativeForge."
            ),
        },
        "review_gate_policy": {
            "draft_outputs_require_human_review": True,
            "generated_form_previews_are_non_final": True,
            "statement": (
                "Review artifacts remain in draft until your team transitions "
                "them through the review workflow; autofilled SF-424 previews "
                "are not submission-ready PDFs."
            ),
        },
        "ai_training_policy": {
            "train_on_customer_data": False,
            "statement": (
                "NativeForge does not use your tribal profile, sparks, NOFO "
                "extractions, scores, pursuits, or audit events to train models."
            ),
        },
        "export_policy": {
            "org_wide_json_snapshot_available": True,
            "tribal_profile_json_export_available": True,
            "audit_log_export_available": True,
        },
        "commitments_enforced_m0": [
            "tenant-scoped APIs with org context headers",
            "append-only audit trail for configured actions",
            "review-gated artifacts for extraction and form packages",
            "deterministic scoring and previews without silent submission",
        ],
        "commitments_deferred_post_m0": [
            "SOC 2 Type II attestation",
            "configurable audit retention windows",
            "private deployment / on-premises option",
        ],
    }


def build_review_gate_summary(
    session: Session,
    *,
    org_id: UUID,
    org_type: OrgType,
) -> dict[str, Any]:
    arts = ra_repo.list_review_artifacts(
        session=session,
        org_id=org_id,
        org_type=org_type,
    )
    by_status = Counter(a.review_status for a in arts)
    by_type = Counter(a.artifact_type for a in arts)
    _epoch = datetime(1970, 1, 1, tzinfo=UTC)
    sorted_arts = sorted(
        arts,
        key=lambda a: a.created_at if a.created_at is not None else _epoch,
    )
    items = [
        {
            "id": str(a.id),
            "artifact_type": a.artifact_type,
            "review_status": a.review_status,
            "created_at": _dt(a.created_at),
            "updated_at": _dt(a.updated_at),
        }
        for a in sorted_arts
    ]
    return {
        "review_artifact_count": len(arts),
        "by_review_status": dict(by_status),
        "by_artifact_type": dict(by_type),
        "artifacts": items,
    }


def _spark_score_brief(row: NfSparkScore) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "grant_spark_id": str(row.grant_spark_id),
        "composite": _num(row.composite),
        "recommendation": row.recommendation,
        "disqualified": row.disqualified,
        "created_at": _dt(row.created_at),
    }


def _nofo_run_brief(row: NfNofoExtractionRun) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "grant_spark_id": str(row.grant_spark_id),
        "extractor_engine": row.extractor_engine,
        "source_text_digest": row.source_text_digest,
        "created_at": _dt(row.created_at),
    }


def _form_pkg_brief(row: NfFormPackage, *, include_sf424: bool) -> dict[str, Any]:
    out: dict[str, Any] = {
        "id": str(row.id),
        "grant_pursuit_id": str(row.grant_pursuit_id),
        "review_artifact_id": str(row.review_artifact_id),
        "package_engine": row.package_engine,
        "input_digest": row.input_digest,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }
    if include_sf424:
        out["sf424_preview"] = row.sf424_preview
    return out


def export_org_data_snapshot(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    actor_id: UUID | None,
    include_sf424_previews: bool,
    audit_event_sample_limit: int,
) -> dict[str, Any]:
    """JSON bundle of org-owned NF rows (M0 export foundation)."""
    org_id = org.id
    is_demo = is_demo_for_org_type(org.org_type)

    profile = tps.get_tribal_profile(session, org_id=org_id, org_type=org_type)
    sparks = gs_repo.list_grant_sparks_for_org(
        session=session,
        org_id=org_id,
        org_type=org_type,
    )
    pursuits = pursuit_repo.list_grant_pursuits(
        session=session,
        org_id=org_id,
        org_type=org_type,
    )
    scores = score_repo.list_spark_scores_for_org(
        session=session,
        org_id=org_id,
        org_type=org_type,
    )
    runs = ne_repo.list_extraction_runs_for_org(
        session=session,
        org_id=org_id,
        org_type=org_type,
    )
    packages = fp_repo.list_form_packages_for_org(
        session=session,
        org_id=org_id,
        org_type=org_type,
    )
    review_arts = ra_repo.list_review_artifacts(
        session=session,
        org_id=org_id,
        org_type=org_type,
    )
    rev_rows = nf_rev_repo.list_review_items_for_org(
        session,
        org_id=org_id,
        org_type=org_type,
        limit=5000,
    )
    rev_by_status = Counter(r.review_status for r in rev_rows)
    manifest = build_trust_manifest(org_type=org_type)
    spark_title_by_id = {s.id: s.opportunity_title for s in sparks}
    audit_tail = audit_repo.list_audit_events_for_org(
        session=session,
        org_id=org_id,
        org_type=org_type,
        limit=audit_event_sample_limit,
    )

    snapshot_core = {
        "snapshot_schema_version": ORG_DATA_SNAPSHOT_VERSION,
        "exported_at": datetime.now(UTC).isoformat(),
        "organization": {
            "id": str(org.id),
            "org_type": org.org_type,
            "is_demo_data_plane": is_demo,
        },
        "trust_manifest_summary": {
            "manifest_schema_version": manifest["manifest_schema_version"],
            "submission_policy": manifest["submission_policy"],
            "review_gate_policy": manifest["review_gate_policy"],
        },
        "tribal_profile": tps.profile_to_dict(profile) if profile else None,
        "grant_sparks": [gss.spark_to_dict(s) for s in sparks],
        "pursuits": [
            psvc.pursuit_to_dict(
                p,
                spark_title=spark_title_by_id.get(p.grant_spark_id),
            )
            for p in pursuits
        ],
        "spark_scores": [_spark_score_brief(s) for s in scores],
        "nofo_extraction_runs": [_nofo_run_brief(r) for r in runs],
        "form_packages": [
            _form_pkg_brief(pkg, include_sf424=include_sf424_previews)
            for pkg in packages
        ],
        "discovery_review_summary": {
            "total": len(rev_rows),
            "by_review_status": dict(rev_by_status),
        },
        "discovery_review_items_sample": [
            dr_svc.review_item_to_dict(r) for r in rev_rows[:50]
        ],
        "counts": {
            "grant_sparks": len(sparks),
            "pursuits": len(pursuits),
            "spark_scores": len(scores),
            "nofo_extraction_runs": len(runs),
            "form_packages": len(packages),
            "review_artifacts": len(review_arts),
            "discovery_review_items": len(rev_rows),
        },
        "audit_events_sample": [audit_repo.audit_event_to_dict(e) for e in audit_tail],
    }

    audit_repo.append_org_audit_event(
        session,
        organization_id=org_id,
        is_demo=is_demo,
        action=AuditAction.org_data_snapshot_exported,
        payload={
            "snapshot_schema_version": ORG_DATA_SNAPSHOT_VERSION,
            "include_sf424_previews": include_sf424_previews,
            "audit_sample_limit": audit_event_sample_limit,
        },
        actor_id=actor_id,
    )
    session.flush()
    return snapshot_core
