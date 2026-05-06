"""Sprint 3: orchestrate stub NOFO extraction + review artifact linkage."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.db.models import (
    NfNofoExtractionRun,
    NfReviewArtifact,
    NfSparkRequirement,
    Organization,
    is_demo_for_org_type,
)
from nativeforge.domain.enums import AuditAction, ReviewArtifactType
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import grant_sparks as gs_repo
from nativeforge.repositories import nofo_extraction as ne_repo
from nativeforge.repositories import review_artifacts as ra_repo
from nativeforge.services.nofo_stub_extractor import ENGINE_KEY, extract_stub


def requirement_row_to_dict(row: NfSparkRequirement) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "requirement_type": row.requirement_type,
        "label": row.label,
        "description": row.description,
        "required": row.required,
        "page_limit": row.page_limit,
        "sort_order": row.sort_order,
        "notes": row.notes,
    }


def extraction_run_to_dict(run: NfNofoExtractionRun) -> dict[str, Any]:
    return {
        "id": str(run.id),
        "grant_spark_id": str(run.grant_spark_id),
        "review_artifact_id": str(run.review_artifact_id)
        if run.review_artifact_id
        else None,
        "extractor_engine": run.extractor_engine,
        "source_text_digest": run.source_text_digest,
        "created_at": run.created_at.isoformat() if run.created_at else None,
    }


def run_stub_extraction(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    spark_id: uuid.UUID,
    actor_id: uuid.UUID | None,
) -> tuple[NfNofoExtractionRun, NfReviewArtifact]:
    spark = gs_repo.get_grant_spark_scoped(
        session=session,
        spark_id=spark_id,
        org_id=org.id,
        org_type=org_type,
    )
    if spark is None:
        raise ValueError("grant spark not found")

    art = ra_repo.create_review_artifact(
        session,
        org=org,
        actor_id=actor_id,
        artifact_type=ReviewArtifactType.nofo_extraction,
    )

    bundle = extract_stub(spark, spark.raw_nofo_text)
    is_demo = is_demo_for_org_type(org.org_type)

    run = NfNofoExtractionRun(
        organization_id=org.id,
        grant_spark_id=spark.id,
        is_demo=is_demo,
        review_artifact_id=art.id,
        extractor_engine=ENGINE_KEY,
        source_text_digest=bundle["digest"],
        nofo_summary=bundle["nofo_summary"],
        structured_requirements=bundle["structured_requirements"],
        checklist_snapshot=bundle["checklist_snapshot"],
    )
    session.add(run)
    session.flush()

    for row in bundle["checklist_rows"]:
        session.add(
            NfSparkRequirement(
                organization_id=org.id,
                grant_spark_id=spark.id,
                extraction_run_id=run.id,
                is_demo=is_demo,
                requirement_type=row["requirement_type"],
                label=row["label"],
                description=row.get("description"),
                required=bool(row.get("required", True)),
                page_limit=row.get("page_limit"),
                sort_order=int(row.get("sort_order", 0)),
                notes=row.get("notes"),
            )
        )

    ra_repo.append_audit(
        session,
        artifact=art,
        action=AuditAction.nofo_extraction_completed,
        payload={
            "extraction_run_id": str(run.id),
            "grant_spark_id": str(spark.id),
            "digest": bundle["digest"],
        },
        actor_id=actor_id,
        extraction_run_id=run.id,
    )
    session.flush()
    return run, art


def build_latest_payload(
    session: Session,
    *,
    spark_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> dict[str, Any] | None:
    run = ne_repo.get_latest_extraction_run(
        session=session,
        spark_id=spark_id,
        org_id=org_id,
        org_type=org_type,
    )
    if run is None:
        return None
    art: NfReviewArtifact | None = None
    if run.review_artifact_id:
        art = session.get(NfReviewArtifact, run.review_artifact_id)
    return {
        "extraction_run": extraction_run_to_dict(run),
        "review_artifact": (
            {
                "id": str(art.id),
                "artifact_type": art.artifact_type,
                "review_status": art.review_status,
            }
            if art
            else None
        ),
        "nofo_summary": run.nofo_summary,
        "structured_requirements": run.structured_requirements,
        "checklist_snapshot": run.checklist_snapshot,
        "review_gate": {
            "note": (
                "Extraction output is draft until the linked review artifact is "
                "approved or finalized."
            ),
            "is_final": art.review_status in ("approved", "finalized")
            if art
            else False,
        },
    }


def list_checklist_requirements(
    session: Session,
    *,
    spark_id: uuid.UUID,
    org_id: uuid.UUID,
    org_type: OrgType,
) -> list[dict[str, Any]] | None:
    run = ne_repo.get_latest_extraction_run(
        session=session,
        spark_id=spark_id,
        org_id=org_id,
        org_type=org_type,
    )
    if run is None:
        return None
    rows = ne_repo.list_requirements_for_run(
        session=session,
        extraction_run_id=run.id,
        org_id=org_id,
        org_type=org_type,
    )
    return [requirement_row_to_dict(r) for r in rows]
