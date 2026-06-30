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
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from nativeforge.db.base import Base
from nativeforge.domain.enums import (
    DiscoveryCandidateStatus,
    DiscoveryIntakeMode,
    DiscoveryIntakeRunStatus,
    DiscoveryRecommendedAction,
    DiscoveryReviewItemType,
    DiscoveryReviewQueueStatus,
    ExpectedOpportunityFrequency,
    FundingInstrument,
    GrantAwardType,
    GrantPipelineStage,
    GrantSparkSource,
    OperatorActionCreatedFrom,
    OperatorActionResolutionCode,
    OperatorActionStatus,
    OperatorDecisionAction,
    OperatorDecisionItemType,
    OperatorDecisionSeverity,
    OpportunitySourceType,
    OpportunityVerificationStatus,
    OrganizationOrgType,
    PursuitCalendarKind,
    PursuitTaskStatus,
    PursuitWorkflowStatus,
    RecommendationTier,
    SamRegistrationStatus,
    SourceCheckMethod,
    SourceCheckMode,
    SourceCheckRunStatus,
    SourceHealthStatus,
    SourceLastCheckStatus,
    SourcePriorityLevel,
    SourceReliabilityRating,
    SparkFreshnessStatus,
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


def _pursuit_workflow_status_in_sql() -> str:
    vals = ", ".join(f"'{s.value}'" for s in PursuitWorkflowStatus)
    return f"status IN ({vals})"


def _pursuit_task_status_in_sql() -> str:
    vals = ", ".join(f"'{s.value}'" for s in PursuitTaskStatus)
    return f"status IN ({vals})"


def _pursuit_calendar_kind_in_sql() -> str:
    vals = ", ".join(f"'{k.value}'" for k in PursuitCalendarKind)
    return f"kind IN ({vals})"


def _opportunity_source_type_in_sql() -> str:
    vals = ", ".join(f"'{t.value}'" for t in OpportunitySourceType)
    return f"source_type IN ({vals})"


def _source_reliability_rating_in_sql() -> str:
    vals = ", ".join(f"'{r.value}'" for r in SourceReliabilityRating)
    return f"reliability_rating IN ({vals})"


def _opportunity_verification_status_in_sql() -> str:
    vals = ", ".join(f"'{v.value}'" for v in OpportunityVerificationStatus)
    return f"verification_status IN ({vals})"


def _grant_spark_optional_source_type_sql() -> str:
    vals = ", ".join(f"'{t.value}'" for t in OpportunitySourceType)
    return f"(source_type IS NULL OR source_type IN ({vals}))"


def _grant_spark_optional_freshness_sql() -> str:
    vals = ", ".join(f"'{f.value}'" for f in SparkFreshnessStatus)
    return f"(freshness_status IS NULL OR freshness_status IN ({vals}))"


def _grant_spark_optional_verification_sql() -> str:
    vals = ", ".join(f"'{v.value}'" for v in OpportunityVerificationStatus)
    return f"(verification_status IS NULL OR verification_status IN ({vals}))"


def _grant_spark_optional_funding_instrument_sql() -> str:
    vals = ", ".join(f"'{i.value}'" for i in FundingInstrument)
    return f"(funding_instrument IS NULL OR funding_instrument IN ({vals}))"


def _source_check_method_in_sql() -> str:
    vals = ", ".join(f"'{m.value}'" for m in SourceCheckMethod)
    return f"check_method IN ({vals})"


def _expected_opportunity_frequency_in_sql() -> str:
    vals = ", ".join(f"'{f.value}'" for f in ExpectedOpportunityFrequency)
    return f"expected_opportunity_frequency IN ({vals})"


def _source_priority_level_in_sql() -> str:
    vals = ", ".join(f"'{p.value}'" for p in SourcePriorityLevel)
    return f"priority_level IN ({vals})"


def _source_last_check_status_optional_sql() -> str:
    vals = ", ".join(f"'{s.value}'" for s in SourceLastCheckStatus)
    return f"(last_check_status IS NULL OR last_check_status IN ({vals}))"


def _source_health_status_optional_sql() -> str:
    vals = ", ".join(f"'{h.value}'" for h in SourceHealthStatus)
    return f"(source_health_status IS NULL OR source_health_status IN ({vals}))"


def _nf_active_opportunity_sources_source_health_status_sql() -> str:
    """Matches ``ck_nf_active_opportunity_sources_source_health_status`` (revision 0019)."""
    vals = ", ".join(f"'{h.value}'" for h in SourceHealthStatus)
    return f"source_health_status IN ({vals})"


def _source_check_run_status_in_sql() -> str:
    vals = ", ".join(f"'{s.value}'" for s in SourceCheckRunStatus)
    return f"check_status IN ({vals})"


def _source_check_mode_in_sql() -> str:
    vals = ", ".join(f"'{m.value}'" for m in SourceCheckMode)
    return f"check_mode IN ({vals})"


def _discovery_intake_run_status_in_sql() -> str:
    vals = ", ".join(f"'{s.value}'" for s in DiscoveryIntakeRunStatus)
    return f"run_status IN ({vals})"


def _discovery_intake_mode_in_sql() -> str:
    vals = ", ".join(f"'{m.value}'" for m in DiscoveryIntakeMode)
    return f"intake_mode IN ({vals})"


def _discovery_candidate_status_in_sql() -> str:
    vals = ", ".join(f"'{c.value}'" for c in DiscoveryCandidateStatus)
    return f"candidate_status IN ({vals})"


def _discovery_candidate_optional_freshness_sql() -> str:
    vals = ", ".join(f"'{f.value}'" for f in SparkFreshnessStatus)
    return f"(freshness_status IS NULL OR freshness_status IN ({vals}))"


def _discovery_review_item_type_in_sql() -> str:
    vals = ", ".join(f"'{t.value}'" for t in DiscoveryReviewItemType)
    return f"review_item_type IN ({vals})"


def _discovery_review_queue_status_in_sql() -> str:
    vals = ", ".join(f"'{s.value}'" for s in DiscoveryReviewQueueStatus)
    return f"review_status IN ({vals})"


def _discovery_recommended_action_optional_sql() -> str:
    vals = ", ".join(f"'{a.value}'" for a in DiscoveryRecommendedAction)
    return f"(recommended_action IS NULL OR recommended_action IN ({vals}))"


def _nf_operator_actions_status_sql() -> str:
    vals = ", ".join(f"'{s.value}'" for s in OperatorActionStatus)
    return f"status IN ({vals})"


def _operator_decision_item_type_in_sql() -> str:
    vals = ", ".join(f"'{t.value}'" for t in OperatorDecisionItemType)
    return f"item_type IN ({vals})"


def _nf_operator_actions_action_sql() -> str:
    vals = ", ".join(f"'{a.value}'" for a in OperatorDecisionAction)
    return f'"action" IN ({vals})'


def _operator_decision_severity_in_sql() -> str:
    vals = ", ".join(f"'{s.value}'" for s in OperatorDecisionSeverity)
    return f"severity IN ({vals})"


def _operator_action_resolution_code_optional_sql() -> str:
    vals = ", ".join(f"'{r.value}'" for r in OperatorActionResolutionCode)
    return f"(resolution_code IS NULL OR resolution_code IN ({vals}))"


def _operator_action_created_from_sql() -> str:
    vals = ", ".join(f"'{c.value}'" for c in OperatorActionCreatedFrom)
    return f"created_from IN ({vals})"


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


class NfOpportunitySource(Base):
    """Discovery Engine — opportunity source registry entry."""

    __tablename__ = "nf_opportunity_sources"
    __table_args__ = (
        CheckConstraint(
            _opportunity_source_type_in_sql(),
            name="ck_nf_opportunity_sources_source_type",
        ),
        CheckConstraint(
            _source_reliability_rating_in_sql(),
            name="ck_nf_opportunity_sources_reliability_rating",
        ),
        CheckConstraint(
            _opportunity_verification_status_in_sql(),
            name="ck_nf_opportunity_sources_verification_status",
        ),
        CheckConstraint(
            _source_check_method_in_sql(),
            name="ck_nf_opportunity_sources_check_method",
        ),
        CheckConstraint(
            _expected_opportunity_frequency_in_sql(),
            name="ck_nf_opportunity_sources_expected_frequency",
        ),
        CheckConstraint(
            _source_priority_level_in_sql(),
            name="ck_nf_opportunity_sources_priority_level",
        ),
        CheckConstraint(
            _source_last_check_status_optional_sql(),
            name="ck_nf_opportunity_sources_last_check_status",
        ),
        CheckConstraint(
            _source_health_status_optional_sql(),
            name="ck_nf_opportunity_sources_source_health_status",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    source_name: Mapped[str] = mapped_column(String(512), nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    publisher_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    geographic_scope_json: Mapped[dict | list | None] = mapped_column(
        JSON, nullable=True
    )
    native_relevance_notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    reliability_rating: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SourceReliabilityRating.unknown.value,
    )
    freshness_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_successful_check_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_error: Mapped[str | None] = mapped_column(Text(), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    verification_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=OpportunityVerificationStatus.unverified.value,
    )
    funding_domains_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    applicant_types_json: Mapped[list | dict | None] = mapped_column(
        JSON, nullable=True
    )
    covered_states_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    covered_regions_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    covered_tribal_groups_json: Mapped[list | None] = mapped_column(JSON, nullable=True)
    coverage_notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    check_method: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SourceCheckMethod.unknown.value,
    )
    expected_opportunity_frequency: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=ExpectedOpportunityFrequency.unknown.value,
    )
    priority_level: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=SourcePriorityLevel.medium.value,
    )
    check_interval_days: Mapped[int | None] = mapped_column(Integer, nullable=True)
    next_check_due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_check_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    last_check_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    last_check_summary_json: Mapped[dict | list | None] = mapped_column(
        JSON, nullable=True
    )
    consecutive_failure_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    consecutive_empty_check_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    source_health_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    freshness_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    seed_id: Mapped[str | None] = mapped_column(String(64), nullable=True, index=True)
    canonical_source_id: Mapped[str | None] = mapped_column(
        String(256), nullable=True
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

    organization: Mapped[Organization | None] = relationship()


class NfActiveOpportunitySource(Base):
    """Runtime active opportunity source row (table from Alembic revision 0019)."""

    __tablename__ = "nf_active_opportunity_sources"
    __table_args__ = (
        CheckConstraint(
            _nf_active_opportunity_sources_source_health_status_sql(),
            name="ck_nf_active_opportunity_sources_source_health_status",
        ),
        UniqueConstraint(
            "organization_id",
            "source_name",
            "source_type",
            "source_lane",
            name="uq_nf_active_opportunity_sources_org_name_type_lane",
        ),
        Index(
            "ix_nf_active_opportunity_sources_organization_id",
            "organization_id",
        ),
        Index(
            "ix_nf_active_opportunity_sources_source_status",
            "source_status",
        ),
        Index(
            "ix_nf_active_opportunity_sources_source_health_status",
            "source_health_status",
        ),
        Index("ix_nf_active_opportunity_sources_source_lane", "source_lane"),
        Index("ix_nf_active_opportunity_sources_source_type", "source_type"),
        Index(
            "ix_nf_active_opportunity_sources_last_checked_at",
            "last_checked_at",
        ),
        Index(
            "ix_nf_active_opportunity_sources_last_success_at",
            "last_success_at",
        ),
        Index(
            "ix_nf_active_opportunity_sources_rollback_contract_id",
            "rollback_contract_id",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    organization_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
    )
    source_name: Mapped[str] = mapped_column(String(512), nullable=False)
    source_type: Mapped[str] = mapped_column(String(128), nullable=False)
    source_lane: Mapped[str] = mapped_column(String(128), nullable=False)
    source_url_or_search_target: Mapped[str | None] = mapped_column(
        Text(), nullable=True
    )
    collection_method: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        server_default=text("'manual_review_only'"),
    )
    update_frequency: Mapped[str] = mapped_column(
        String(128),
        nullable=False,
        server_default=text("'unknown'"),
    )
    freshness_cadence_days: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        server_default=text("30"),
    )
    stale_threshold_days: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        server_default=text("30"),
    )
    last_checked_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_success_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_failure_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    consecutive_failure_count: Mapped[int] = mapped_column(
        Integer(),
        nullable=False,
        server_default=text("0"),
    )
    source_health_status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default=text(f"'{SourceHealthStatus.unknown.value}'"),
    )
    source_status: Mapped[str] = mapped_column(
        String(64),
        nullable=False,
        server_default=text("'activation_pending'"),
    )
    dedupe_key_strategy: Mapped[str] = mapped_column(
        String(256),
        nullable=False,
        server_default=text("'pending_operator_assignment'"),
    )
    provenance_capture_plan: Mapped[list | dict] = mapped_column(
        JSON(),
        nullable=False,
        server_default=text("'[]'"),
    )
    native_relevance_basis: Mapped[str | None] = mapped_column(Text(), nullable=True)
    broad_eligibility_human_review_required: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        server_default=text("true"),
    )
    keyword_only_not_confirmed_eligible: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        server_default=text("true"),
    )
    legal_tos_review_required: Mapped[bool] = mapped_column(
        Boolean(),
        nullable=False,
        server_default=text("true"),
    )
    public_access_basis: Mapped[str | None] = mapped_column(Text(), nullable=True)
    activation_approval_artifact_id: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    activation_command_id: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    activation_approved_by: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    activation_approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    activation_notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    rollback_contract_id: Mapped[str | None] = mapped_column(
        String(512), nullable=True
    )
    disabled_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    disabled_by: Mapped[str | None] = mapped_column(String(512), nullable=True)
    disabled_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
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


class NfSourceCheckRun(Base):
    """Operator-facing record of a discovery source check (Sprint 15)."""

    __tablename__ = "nf_source_check_runs"
    __table_args__ = (
        CheckConstraint(
            _source_check_run_status_in_sql(),
            name="ck_nf_source_check_runs_status",
        ),
        CheckConstraint(
            _source_check_mode_in_sql(),
            name="ck_nf_source_check_runs_mode",
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
    source_registry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_opportunity_sources.id", ondelete="RESTRICT"),
        nullable=False,
    )
    check_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    check_status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    checked_for_period_start: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    checked_for_period_end: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    opportunities_seen_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    new_candidates_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    review_items_created_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0
    )
    error_code: Mapped[str | None] = mapped_column(String(128), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text(), nullable=True)
    operator_notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    result_summary_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
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
        CheckConstraint(
            _grant_spark_optional_source_type_sql(),
            name="ck_nf_grant_sparks_source_type_discovery",
        ),
        CheckConstraint(
            _grant_spark_optional_freshness_sql(),
            name="ck_nf_grant_sparks_freshness_status",
        ),
        CheckConstraint(
            _grant_spark_optional_verification_sql(),
            name="ck_nf_grant_sparks_verification_status_discovery",
        ),
        CheckConstraint(
            _grant_spark_optional_funding_instrument_sql(),
            name="ck_nf_grant_sparks_funding_instrument",
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
    source_registry_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_opportunity_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    source_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    publisher_name: Mapped[str | None] = mapped_column(String(512), nullable=True)
    discovered_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    last_verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    freshness_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    verification_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    duplicate_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    duplicate_cluster_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True, index=True
    )
    native_relevance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    native_relevance_reasons_json: Mapped[list | dict | None] = mapped_column(
        JSON, nullable=True
    )
    eligibility_tags_json: Mapped[list | dict | None] = mapped_column(
        JSON, nullable=True
    )
    geographic_scope_json: Mapped[dict | list | None] = mapped_column(
        JSON, nullable=True
    )
    funding_instrument: Mapped[str | None] = mapped_column(String(32), nullable=True)
    applicant_types_json: Mapped[list | dict | None] = mapped_column(
        JSON, nullable=True
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
    source_registry: Mapped[NfOpportunitySource | None] = relationship(
        foreign_keys=[source_registry_id],
    )


class NfDiscoveryIntakeRun(Base):
    """Structured discovery intake attempt for one opportunity source (Sprint 12)."""

    __tablename__ = "nf_discovery_intake_runs"
    __table_args__ = (
        CheckConstraint(
            _discovery_intake_run_status_in_sql(),
            name="ck_nf_discovery_intake_runs_run_status",
        ),
        CheckConstraint(
            _discovery_intake_mode_in_sql(),
            name="ck_nf_discovery_intake_runs_intake_mode",
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
    source_registry_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_opportunity_sources.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    run_schema_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    run_status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=DiscoveryIntakeRunStatus.created.value,
    )
    intake_mode: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    candidate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    accepted_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    duplicate_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    rejected_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    run_summary_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
    error_summary_json: Mapped[dict | list | None] = mapped_column(JSON, nullable=True)
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
    source_registry: Mapped[NfOpportunitySource] = relationship(
        foreign_keys=[source_registry_id],
    )


class NfDiscoveryIntakeCandidate(Base):
    """One raw→normalized opportunity candidate within an intake run (audit trail)."""

    __tablename__ = "nf_discovery_intake_candidates"
    __table_args__ = (
        CheckConstraint(
            _discovery_candidate_status_in_sql(),
            name="ck_nf_discovery_intake_candidates_status",
        ),
        CheckConstraint(
            _discovery_candidate_optional_freshness_sql(),
            name="ck_nf_discovery_intake_candidates_freshness",
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
    intake_run_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_discovery_intake_runs.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    source_registry_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_opportunity_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    candidate_status: Mapped[str] = mapped_column(String(32), nullable=False)
    raw_candidate_json: Mapped[dict | list] = mapped_column(JSON, nullable=False)
    normalized_candidate_json: Mapped[dict | list | None] = mapped_column(
        JSON, nullable=True
    )
    normalization_errors_json: Mapped[list | dict | None] = mapped_column(
        JSON, nullable=True
    )
    duplicate_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    duplicate_of_spark_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_grant_sparks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    created_spark_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_grant_sparks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    decision_reason: Mapped[str | None] = mapped_column(Text(), nullable=True)
    native_relevance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    native_relevance_reasons_json: Mapped[list | dict | None] = mapped_column(
        JSON, nullable=True
    )
    freshness_status: Mapped[str | None] = mapped_column(String(32), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    intake_run: Mapped[NfDiscoveryIntakeRun] = relationship(
        foreign_keys=[intake_run_id],
    )
    duplicate_of_spark: Mapped[NfGrantSpark | None] = relationship(
        foreign_keys=[duplicate_of_spark_id],
    )
    created_spark: Mapped[NfGrantSpark | None] = relationship(
        foreign_keys=[created_spark_id],
    )


class NfDiscoveryReviewItem(Base):
    """Operator review queue for discovery QC, deduplication, promotion gates."""

    __tablename__ = "nf_discovery_review_items"
    __table_args__ = (
        CheckConstraint(
            _discovery_review_item_type_in_sql(),
            name="ck_nf_discovery_review_items_item_type",
        ),
        CheckConstraint(
            _discovery_review_queue_status_in_sql(),
            name="ck_nf_discovery_review_items_review_status",
        ),
        CheckConstraint(
            _discovery_recommended_action_optional_sql(),
            name="ck_nf_discovery_review_items_recommended_action",
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
    source_registry_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_opportunity_sources.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    intake_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_discovery_intake_runs.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    intake_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_discovery_intake_candidates.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    grant_spark_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_grant_sparks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    review_item_type: Mapped[str] = mapped_column(String(64), nullable=False)
    review_status: Mapped[str] = mapped_column(String(32), nullable=False)
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    reason_codes_json: Mapped[list | dict | None] = mapped_column(JSON, nullable=True)
    quality_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    confidence_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    duplicate_risk_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    native_relevance_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recommended_action: Mapped[str | None] = mapped_column(String(32), nullable=True)
    review_notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    assigned_to: Mapped[str | None] = mapped_column(String(512), nullable=True)
    resolved_at: Mapped[datetime | None] = mapped_column(
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
    source_registry: Mapped[NfOpportunitySource | None] = relationship(
        foreign_keys=[source_registry_id],
    )
    intake_run: Mapped[NfDiscoveryIntakeRun | None] = relationship(
        foreign_keys=[intake_run_id],
    )
    intake_candidate: Mapped[NfDiscoveryIntakeCandidate | None] = relationship(
        foreign_keys=[intake_candidate_id],
    )
    grant_spark: Mapped[NfGrantSpark | None] = relationship(
        foreign_keys=[grant_spark_id],
    )


class NfOperatorAction(Base):
    """Operator action ledger row (Sprint 18).

    Durable follow-up from decision pack or manual entry.
    """

    __tablename__ = "nf_operator_actions"
    __table_args__ = (
        CheckConstraint(
            _nf_operator_actions_status_sql(),
            name="ck_nf_operator_actions_status",
        ),
        CheckConstraint(
            _operator_decision_item_type_in_sql(),
            name="ck_nf_operator_actions_item_type",
        ),
        CheckConstraint(
            _nf_operator_actions_action_sql(),
            name="ck_nf_operator_actions_action",
        ),
        CheckConstraint(
            _operator_decision_severity_in_sql(),
            name="ck_nf_operator_actions_severity",
        ),
        CheckConstraint(
            _operator_action_resolution_code_optional_sql(),
            name="ck_nf_operator_actions_resolution_code",
        ),
        CheckConstraint(
            _operator_action_created_from_sql(),
            name="ck_nf_operator_actions_created_from",
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
    decision_id: Mapped[str] = mapped_column(String(256), nullable=False)
    decision_schema_version: Mapped[str | None] = mapped_column(
        String(80), nullable=True
    )
    source_decision_item_json: Mapped[dict | list | None] = mapped_column(
        JSON, nullable=True
    )
    action_title: Mapped[str] = mapped_column(String(512), nullable=False)
    action_summary: Mapped[str | None] = mapped_column(Text(), nullable=True)
    operator_action: Mapped[str | None] = mapped_column(Text(), nullable=True)
    item_type: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(32), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    assigned_to: Mapped[str | None] = mapped_column(String(512), nullable=True)
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    deferred_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    dismissed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    resolution_notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    operator_notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    resolution_code: Mapped[str | None] = mapped_column(String(80), nullable=True)
    source_registry_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_opportunity_sources.id", ondelete="SET NULL"),
        nullable=True,
    )
    review_item_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_discovery_review_items.id", ondelete="SET NULL"),
        nullable=True,
    )
    intake_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_discovery_intake_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    intake_candidate_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_discovery_intake_candidates.id", ondelete="SET NULL"),
        nullable=True,
    )
    grant_spark_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_grant_sparks.id", ondelete="SET NULL"),
        nullable=True,
    )
    source_check_run_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_source_check_runs.id", ondelete="SET NULL"),
        nullable=True,
    )
    coverage_gap_id: Mapped[str | None] = mapped_column(String(256), nullable=True)
    created_from: Mapped[str] = mapped_column(String(64), nullable=False)
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


class NfGrantPursuit(Base):
    """Active grant pursuit — handoff from scored Spark (Sprint 5)."""

    __tablename__ = "nf_grant_pursuits"
    __table_args__ = (
        CheckConstraint(
            _pursuit_workflow_status_in_sql(),
            name="ck_nf_grant_pursuits_status",
        ),
        UniqueConstraint(
            "grant_spark_id",
            name="uq_nf_grant_pursuits_grant_spark_id",
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
    spark_score_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_spark_scores.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PursuitWorkflowStatus.active.value,
    )
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    grant_spark: Mapped[NfGrantSpark] = relationship()


class NfPursuitTask(Base):
    """Work item under a grant pursuit."""

    __tablename__ = "nf_pursuit_tasks"
    __table_args__ = (
        CheckConstraint(
            _pursuit_task_status_in_sql(),
            name="ck_nf_pursuit_tasks_status",
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
    grant_pursuit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_grant_pursuits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    description: Mapped[str | None] = mapped_column(Text(), nullable=True)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=PursuitTaskStatus.pending.value,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    due_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    spark_requirement_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_spark_requirements.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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

    grant_pursuit: Mapped[NfGrantPursuit] = relationship()


class NfPursuitCalendarEvent(Base):
    """Calendar anchor — deadlines and milestones for a pursuit."""

    __tablename__ = "nf_pursuit_calendar_events"
    __table_args__ = (
        CheckConstraint(
            _pursuit_calendar_kind_in_sql(),
            name="ck_nf_pursuit_calendar_events_kind",
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
    grant_pursuit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_grant_pursuits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(512), nullable=False)
    occurs_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text(), nullable=True)
    pursuit_task_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_pursuit_tasks.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
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

    grant_pursuit: Mapped[NfGrantPursuit] = relationship()


class NfFormPackage(Base):
    """Review-gated SF-424 (and future forms) package tied to a pursuit (Sprint 6)."""

    __tablename__ = "nf_form_packages"
    __table_args__ = (
        UniqueConstraint(
            "grant_pursuit_id",
            name="uq_nf_form_packages_grant_pursuit_id",
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
    grant_pursuit_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_grant_pursuits.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    review_artifact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_review_artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    package_engine: Mapped[str] = mapped_column(String(64), nullable=False)
    sf424_preview: Mapped[dict] = mapped_column(JSON, nullable=False)
    input_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    grant_pursuit: Mapped[NfGrantPursuit] = relationship()
    review_artifact: Mapped[NfReviewArtifact] = relationship()


def _pursuit_brief_status_in_sql() -> str:
    return "status IN ('pending_review', 'finalized', 'superseded')"


class NfPursuitBrief(Base):
    """Deterministic pursuit brief — consolidated Grant Spark intelligence."""

    __tablename__ = "nf_pursuit_briefs"
    __table_args__ = (
        CheckConstraint(
            _pursuit_brief_status_in_sql(),
            name="ck_nf_pursuit_briefs_status",
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
    pursuit_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_grant_pursuits.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    review_artifact_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("nf_review_artifacts.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    brief_schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default="pending_review",
    )
    input_digest: Mapped[str] = mapped_column(String(64), nullable=False)
    readiness_summary_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    opportunity_summary_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    eligibility_fit_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    requirement_summary_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    score_summary_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    risks_and_gaps_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    required_documents_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    timeline_summary_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    recommended_next_actions_json: Mapped[dict] = mapped_column(JSON, nullable=False)
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


class NfActivationState(Base):
    """M7: per-workspace durable activation flags (default OFF)."""

    __tablename__ = "nf_activation_state"
    __table_args__ = (
        UniqueConstraint("organization_id", name="uq_nf_activation_state_org"),
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
    live_publish_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    live_attribution_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    auto_publish_enabled: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    kill_switch_engaged: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    current_auto_publish_config_version: Mapped[int | None] = mapped_column(
        Integer, nullable=True
    )
    state_version: Mapped[int] = mapped_column(
        Integer, nullable=False, server_default=text("1")
    )
    updated_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    updated_by_actor_role: Mapped[str | None] = mapped_column(
        String(32), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    organization: Mapped[Organization] = relationship()


class NfAutoPublishConfig(Base):
    """M7: append-only auto-publish policy versions per workspace."""

    __tablename__ = "nf_auto_publish_config"
    __table_args__ = (
        UniqueConstraint(
            "organization_id",
            "version",
            name="uq_nf_auto_publish_config_org_version",
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
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False)
    config_payload: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    created_by_actor_id: Mapped[uuid.UUID | None] = mapped_column(
        Uuid(as_uuid=True), nullable=True
    )
    created_by_actor_role: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    organization: Mapped[Organization] = relationship()


def is_demo_for_org_type(org_type: str) -> bool:
    return org_type == OrganizationOrgType.demo.value
