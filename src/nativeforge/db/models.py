"""SQLAlchemy models — NativeForge `nf_*` namespace (Sprint 0 foundation)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nativeforge.db.base import Base
from nativeforge.domain.enums import OrganizationOrgType


class Organization(Base):
    """Tenant root — `org_type` distinguishes demo vs real (Layer 1)."""

    __tablename__ = "organizations"
    __table_args__ = (
        CheckConstraint(
            "org_type IN ('real', 'demo')",
            name="ck_organizations_org_type",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True)
    org_type: Mapped[str] = mapped_column(String(16), nullable=False)


class NfReviewArtifact(Base):
    """Review-gated artifact (AI/form outputs pass through here in later sprints)."""

    __tablename__ = "nf_review_artifacts"
    __table_args__ = (
        CheckConstraint(
            "review_status IN ("
            "'draft','pending_review','approved','rejected','finalized'"
            ")",
            name="ck_nf_review_artifacts_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    artifact_type: Mapped[str] = mapped_column(String(64), nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    organization: Mapped[Organization] = relationship()


class NfAuditEvent(Base):
    """Append-only audit trail for review transitions and artifact creation."""

    __tablename__ = "nf_audit_events"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_review_artifacts.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    review_artifact: Mapped[NfReviewArtifact | None] = relationship()


def is_demo_for_org_type(org_type: str) -> bool:
    return org_type == OrganizationOrgType.demo.value
