"""Sprint 6: form package lifecycle + SF-424 preview snapshot."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.db.models import (
    NfFormPackage,
    NfGrantSpark,
    NfReviewArtifact,
    Organization,
    is_demo_for_org_type,
)
from nativeforge.domain.enums import AuditAction, ReviewArtifactType
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import form_packages as fp_repo
from nativeforge.repositories import nofo_extraction as ne_repo
from nativeforge.repositories import pursuits as pursuit_repo
from nativeforge.repositories import review_artifacts as ra_repo
from nativeforge.repositories import tribal_profiles as tp_repo
from nativeforge.services.pursuit_service import PursuitNotFoundError
from nativeforge.services.sf424_preview_builder import (
    PACKAGE_ENGINE,
    build_sf424_preview,
)


class TribalProfileRequiredError(Exception):
    """Org must have a tribal profile to build federal forms."""


class FormPackageAlreadyExistsError(Exception):
    """At most one form package row per pursuit (M0)."""


class FormPackageNotFoundError(Exception):
    """No nf_form_packages row for this pursuit."""


def _dt(v: object | None) -> str | None:
    if v is None:
        return None
    if hasattr(v, "isoformat"):
        return v.isoformat()  # type: ignore[no-any-return]
    return str(v)


def form_package_to_dict(row: NfFormPackage) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "organization_id": str(row.organization_id),
        "grant_pursuit_id": str(row.grant_pursuit_id),
        "review_artifact_id": str(row.review_artifact_id),
        "package_engine": row.package_engine,
        "input_digest": row.input_digest,
        "sf424_preview": row.sf424_preview,
        "created_at": _dt(row.created_at),
        "updated_at": _dt(row.updated_at),
    }


def create_form_package(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    pursuit_id: uuid.UUID,
    actor_id: uuid.UUID | None,
) -> NfFormPackage:
    pursuit = pursuit_repo.get_grant_pursuit_scoped(
        session=session,
        pursuit_id=pursuit_id,
        org_id=org.id,
        org_type=org_type,
    )
    if pursuit is None:
        raise PursuitNotFoundError("pursuit not found")

    profile = tp_repo.get_tribal_profile_for_org(
        session=session,
        org_id=org.id,
        org_type=org_type,
    )
    if profile is None:
        raise TribalProfileRequiredError(
            "Create a tribal profile before opening a form package."
        )

    existing = fp_repo.get_form_package_for_pursuit(
        session=session,
        pursuit_id=pursuit_id,
        org_id=org.id,
        org_type=org_type,
    )
    if existing is not None:
        raise FormPackageAlreadyExistsError(
            "A form package already exists for this pursuit."
        )

    spark = session.get(NfGrantSpark, pursuit.grant_spark_id)
    if spark is None:
        raise PursuitNotFoundError("grant spark not found for pursuit")

    nofo = ne_repo.get_latest_extraction_run(
        session=session,
        spark_id=spark.id,
        org_id=org.id,
        org_type=org_type,
    )

    preview, digest = build_sf424_preview(
        profile=profile,
        spark=spark,
        pursuit=pursuit,
        nofo_run=nofo,
    )

    art = ra_repo.create_review_artifact(
        session,
        org=org,
        actor_id=actor_id,
        artifact_type=ReviewArtifactType.form_package,
    )

    is_demo = is_demo_for_org_type(org.org_type)
    row = NfFormPackage(
        id=uuid.uuid4(),
        organization_id=org.id,
        grant_pursuit_id=pursuit.id,
        review_artifact_id=art.id,
        is_demo=is_demo,
        package_engine=PACKAGE_ENGINE,
        sf424_preview=preview,
        input_digest=digest,
    )
    session.add(row)
    session.flush()

    ra_repo.append_audit(
        session,
        artifact=art,
        action=AuditAction.form_package_created,
        payload={
            "nf_form_package_id": str(row.id),
            "grant_pursuit_id": str(pursuit.id),
            "input_digest": digest,
        },
        actor_id=actor_id,
    )
    session.flush()
    return row


def get_form_package(
    session: Session,
    *,
    org_id: uuid.UUID,
    org_type: OrgType,
    pursuit_id: uuid.UUID,
) -> NfFormPackage:
    row = fp_repo.get_form_package_for_pursuit(
        session=session,
        pursuit_id=pursuit_id,
        org_id=org_id,
        org_type=org_type,
    )
    if row is None:
        raise FormPackageNotFoundError("form package not found")
    return row


def regenerate_sf424_preview(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    pursuit_id: uuid.UUID,
    actor_id: uuid.UUID | None,
) -> NfFormPackage:
    pkg = fp_repo.get_form_package_for_pursuit(
        session=session,
        pursuit_id=pursuit_id,
        org_id=org.id,
        org_type=org_type,
    )
    if pkg is None:
        raise FormPackageNotFoundError("form package not found")

    pursuit = pursuit_repo.get_grant_pursuit_scoped(
        session=session,
        pursuit_id=pursuit_id,
        org_id=org.id,
        org_type=org_type,
    )
    if pursuit is None:
        raise PursuitNotFoundError("pursuit not found")

    profile = tp_repo.get_tribal_profile_for_org(
        session=session,
        org_id=org.id,
        org_type=org_type,
    )
    if profile is None:
        raise TribalProfileRequiredError("tribal profile required")

    spark = session.get(NfGrantSpark, pursuit.grant_spark_id)
    if spark is None:
        raise PursuitNotFoundError("grant spark not found")

    nofo = ne_repo.get_latest_extraction_run(
        session=session,
        spark_id=spark.id,
        org_id=org.id,
        org_type=org_type,
    )

    preview, digest = build_sf424_preview(
        profile=profile,
        spark=spark,
        pursuit=pursuit,
        nofo_run=nofo,
    )

    pkg.sf424_preview = preview
    pkg.input_digest = digest
    session.flush()

    art = session.get(NfReviewArtifact, pkg.review_artifact_id)
    if art is not None:
        ra_repo.append_audit(
            session,
            artifact=art,
            action=AuditAction.sf424_preview_regenerated,
            payload={
                "nf_form_package_id": str(pkg.id),
                "input_digest": digest,
            },
            actor_id=actor_id,
        )
        session.flush()
    return pkg
