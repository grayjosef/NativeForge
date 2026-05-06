"""SQLAlchemy models — NativeForge `nf_*` namespace (Sprint 0 foundation)."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    Uuid,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nativeforge.db.base import Base
from nativeforge.domain.enums import (
    GrantAwardType,
    GrantPipelineStage,
    GrantSparkSource,
    OrganizationOrgType,
    RecommendationTier,
    SamRegistrationStatus,
    SparkRequirementKind,
    TribalEntityType,
)


def _tribal_entity_type_in_sql() -> str:
    vals = ", ".join(f"'{e.value}'" for e in TribalEntityType)
    return f"entity_type IN ({vals})"


def _grant_spark_source_in_sql() -> str:
    vals = ", ".join(f"'{s.value}'" for s in GrantSparkSource)
    return f"source IN ({vals})"


def _grant_award_type_in_sql() -> str:
    vals = ", ".join(f"'{a.value}'" for a in GrantAwardType)
    return f"award_type IN ({vals})"


def _grant_pipeline_stage_in_sql() -> str:
    vals = ", ".join(f"'{p.value}'" for p in GrantPipelineStage)
    return f"pipeline_stage IN ({vals})"


def _spark_requirement_kind_in_sql() -> str:
    vals = ", ".join(f"'{k.value}'" for k in SparkRequirementKind)
    return f"requirement_type IN ({vals})"


def _recommendation_tier_in_sql() -> str:
    vals = ", ".join(f"'{t.value}'" for t in RecommendationTier)
    return f"recommendation IN ({vals})"


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


class NfTribalProfile(Base):
    """Tribal / organizational entity profile (Sprint 1). One row per organization."""

    __tablename__ = "nf_tribal_profiles"
    __table_args__ = (
        CheckConstraint(
            _tribal_entity_type_in_sql(),
            name="ck_nf_tribal_profiles_entity_type",
        ),
        CheckConstraint(
            "sam_registration_status IN ("
            + ", ".join(f"'{s.value}'" for s in SamRegistrationStatus)
            + ")",
            name="ck_nf_tribal_profiles_sam_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    legal_name: Mapped[str] = mapped_column(String(512), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    uei: Mapped[str | None] = mapped_column(String(32), nullable=True)
    ein: Mapped[str | None] = mapped_column(String(32), nullable=True)
    sam_registration_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SamRegistrationStatus.unknown.value,
    )
    sam_expiration_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    physical_address: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    mailing_address: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    service_area_description: Mapped[str | None] = mapped_column(
        String(4096), nullable=True
    )
    authorized_representative: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    grants_manager: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    finance_contact: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    indirect_cost_rate: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    certifications: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    standard_narratives: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    attachment_index: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
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


class NfGrantSpark(Base):
    """Grant opportunity (Spark) tracked for an organization (Sprint 2)."""

    __tablename__ = "nf_grant_sparks"
    __table_args__ = (
        CheckConstraint(
            _grant_spark_source_in_sql(),
            name="ck_nf_grant_sparks_source",
        ),
        CheckConstraint(
            _grant_award_type_in_sql(),
            name="ck_nf_grant_sparks_award_type",
        ),
        CheckConstraint(
            _grant_pipeline_stage_in_sql(),
            name="ck_nf_grant_sparks_pipeline_stage",
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
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_id: Mapped[str] = mapped_column(String(256), nullable=False)
    agency: Mapped[str] = mapped_column(String(512), nullable=False)
    sub_agency: Mapped[str | None] = mapped_column(String(512), nullable=True)
    program_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    opportunity_title: Mapped[str] = mapped_column(String(512), nullable=False)
    opportunity_number: Mapped[str | None] = mapped_column(String(128), nullable=True)
    cfda_assistance_listing: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )
    url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    funding_floor: Mapped[object | None] = mapped_column(Numeric(18, 2), nullable=True)
    funding_ceiling: Mapped[object | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    total_program_funding: Mapped[object | None] = mapped_column(
        Numeric(18, 2), nullable=True
    )
    expected_awards: Mapped[int | None] = mapped_column(Integer, nullable=True)
    award_type: Mapped[str] = mapped_column(String(32), nullable=False)
    match_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    match_percent: Mapped[object | None] = mapped_column(Numeric(5, 2), nullable=True)
    match_waiver_available: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    indirect_cost_allowable: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    posted_date: Mapped[object | None] = mapped_column(Date, nullable=True)
    loi_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    application_deadline: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    performance_period_start: Mapped[object | None] = mapped_column(Date, nullable=True)
    performance_period_end: Mapped[object | None] = mapped_column(Date, nullable=True)
    raw_nofo_text: Mapped[str | None] = mapped_column(Text(), nullable=True)
    raw_nofo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    eligibility_tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    tribal_eligible: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    pipeline_stage: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=GrantPipelineStage.new.value,
    )
    ingested_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
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


class NfNofoExtractionRun(Base):
    """Auditable NOFO extraction run (stub or future LLM pipeline)."""

    __tablename__ = "nf_nofo_extraction_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    grant_spark_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_grant_sparks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    review_artifact_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_review_artifacts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    extractor_engine: Mapped[str] = mapped_column(String(64), nullable=False)
    source_text_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    nofo_summary: Mapped[str] = mapped_column(Text(), nullable=False)
    structured_requirements: Mapped[dict] = mapped_column(JSON, nullable=False)
    checklist_snapshot: Mapped[list | dict] = mapped_column(JSON, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    grant_spark: Mapped[NfGrantSpark] = relationship()
    review_artifact: Mapped[NfReviewArtifact | None] = relationship()


class NfSparkRequirement(Base):
    """Checklist-ready projection row for one extraction run."""

    __tablename__ = "nf_spark_requirements"
    __table_args__ = (
        CheckConstraint(
            _spark_requirement_kind_in_sql(),
            name="ck_nf_spark_requirements_kind",
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
    grant_spark_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_grant_sparks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    extraction_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_nofo_extraction_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    requirement_type: Mapped[str] = mapped_column(String(32), nullable=False)
    label: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    page_limit: Mapped[int | None] = mapped_column(Integer, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)

    extraction_run: Mapped[NfNofoExtractionRun] = relationship()


class NfSparkScore(Base):
    """Deterministic pursuit-readiness score for a Grant Spark (Sprint 4)."""

    __tablename__ = "nf_spark_scores"
    __table_args__ = (
        CheckConstraint(
            _recommendation_tier_in_sql(),
            name="ck_nf_spark_scores_recommendation",
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
    grant_spark_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_grant_sparks.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tribal_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_tribal_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    nofo_extraction_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_nofo_extraction_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    scorer_engine: Mapped[str] = mapped_column(String(64), nullable=False)
    dimension_scores: Mapped[dict] = mapped_column(JSON, nullable=False)
    weights_used: Mapped[dict] = mapped_column(JSON, nullable=False)
    composite: Mapped[object] = mapped_column(Numeric(5, 2), nullable=False)
    recommendation: Mapped[str] = mapped_column(String(32), nullable=False)
    explanation_text: Mapped[str] = mapped_column(Text(), nullable=False)
    rationale_detail: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    disqualified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    disqualification_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    override_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    override_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        nullable=True,
    )
    overridden_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    grant_spark: Mapped[NfGrantSpark] = relationship()


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
    tribal_profile_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_tribal_profiles.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    extraction_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_nofo_extraction_runs.id", ondelete="SET NULL"),
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
    tribal_profile: Mapped[NfTribalProfile | None] = relationship()
    extraction_run: Mapped[NfNofoExtractionRun | None] = relationship()


def is_demo_for_org_type(org_type: str) -> bool:
    return org_type == OrganizationOrgType.demo.value
