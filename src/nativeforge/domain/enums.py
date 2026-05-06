"""Enums for Sprint 0 review artifacts and organizations."""

from __future__ import annotations

from enum import StrEnum


class OrganizationOrgType(StrEnum):
    """Layer 1: organization classification (immutable after creation in app policy)."""

    real = "real"
    demo = "demo"


class ReviewArtifactType(StrEnum):
    """Minimal artifact kinds for Sprint 0 scaffolding (expand in later sprints)."""

    sprint0_placeholder = "sprint0_placeholder"
    ai_generated = "ai_generated"
    form_preview = "form_preview"
    form_package = "form_package"
    nofo_extraction = "nofo_extraction"
    pursuit_brief = "pursuit_brief"


class ReviewStatus(StrEnum):
    """Human review gate — must approve before finalization."""

    draft = "draft"
    pending_review = "pending_review"
    approved = "approved"
    rejected = "rejected"
    finalized = "finalized"


class AuditAction(StrEnum):
    """Audit-log verb for nf_audit_events.action."""

    artifact_created = "artifact_created"
    review_requested = "review_requested"
    approved = "approved"
    rejected = "rejected"
    finalized = "finalized"
    reset_to_draft = "reset_to_draft"
    transition_rejected = "transition_rejected"
    profile_created = "profile_created"
    profile_updated = "profile_updated"
    profile_exported = "profile_exported"
    nofo_extraction_completed = "nofo_extraction_completed"
    spark_scored = "spark_scored"
    spark_score_overridden = "spark_score_overridden"
    grant_pursuit_created = "grant_pursuit_created"
    grant_pursuit_updated = "grant_pursuit_updated"
    pursuit_task_created = "pursuit_task_created"
    pursuit_task_updated = "pursuit_task_updated"
    pursuit_calendar_event_created = "pursuit_calendar_event_created"
    pursuit_calendar_event_updated = "pursuit_calendar_event_updated"
    form_package_created = "form_package_created"
    sf424_preview_regenerated = "sf424_preview_regenerated"
    org_data_snapshot_exported = "org_data_snapshot_exported"
    pursuit_brief_generated = "pursuit_brief_generated"
    discovery_intake_run_completed = "discovery_intake_run_completed"


class TribalEntityType(StrEnum):
    """Applicant organization classification for tribal grant pursuit."""

    federally_recognized_tribe = "federally_recognized_tribe"
    tribal_government = "tribal_government"
    tribal_organization = "tribal_organization"
    tribal_nonprofit = "tribal_nonprofit"
    tribal_college = "tribal_college"
    alaska_native_corporation = "alaska_native_corporation"
    alaska_native_village = "alaska_native_village"
    native_hawaiian_organization = "native_hawaiian_organization"
    native_serving_nonprofit = "native_serving_nonprofit"
    other = "other"


class SamRegistrationStatus(StrEnum):
    """SAM.gov registration snapshot on the profile (manual until API verification)."""

    active = "active"
    expired = "expired"
    unknown = "unknown"


class GrantSparkSource(StrEnum):
    """Where the opportunity record originated (ingestion source key)."""

    grants_gov = "grants_gov"
    sam_assistance = "sam_assistance"
    bia = "bia"
    ihs = "ihs"
    ana = "ana"
    ctas = "ctas"
    doe = "doe"
    hud = "hud"
    epa = "epa"
    usda = "usda"
    ntia = "ntia"
    manual = "manual"


class GrantAwardType(StrEnum):
    """SAM/Grants.gov-style assistance instrument."""

    grant = "grant"
    cooperative_agreement = "cooperative_agreement"
    formula = "formula"
    competitive = "competitive"


class GrantPipelineStage(StrEnum):
    """Org workflow stage for a tracked Spark."""

    new = "new"
    evaluating = "evaluating"
    pursuing = "pursuing"
    drafting = "drafting"
    submitted = "submitted"
    awarded = "awarded"
    not_pursuing = "not_pursuing"


class SparkRequirementKind(StrEnum):
    """Requirement row kind (denormalized NOFO extraction projection)."""

    form = "form"
    attachment = "attachment"
    narrative_section = "narrative_section"
    eligibility = "eligibility"
    match = "match"
    resolution = "resolution"
    reporting = "reporting"
    special_condition = "special_condition"


class RecommendationTier(StrEnum):
    """Deterministic pursuit recommendation from composite score."""

    strong_pursue = "strong_pursue"
    pursue = "pursue"
    pursue_with_conditions = "pursue_with_conditions"
    needs_review = "needs_review"
    do_not_pursue = "do_not_pursue"
    disqualified = "disqualified"


class PursuitWorkflowStatus(StrEnum):
    """Grant pursuit record status (Sprint 5 pipeline)."""

    active = "active"
    paused = "paused"
    submitted = "submitted"
    closed = "closed"


class PursuitTaskStatus(StrEnum):
    """Checklist task completion state."""

    pending = "pending"
    in_progress = "in_progress"
    blocked = "blocked"
    done = "done"
    cancelled = "cancelled"


class PursuitCalendarKind(StrEnum):
    """Calendar anchor type for pursuits."""

    application_deadline = "application_deadline"
    loi_deadline = "loi_deadline"
    internal_milestone = "internal_milestone"
    task_due = "task_due"
    custom = "custom"


# --- Discovery Engine (Sprint 10) ---


class OpportunitySourceType(StrEnum):
    """Taxonomy for opportunity source registry entries and Grant Spark attribution."""

    federal = "federal"
    state = "state"
    local = "local"
    tribal = "tribal"
    foundation = "foundation"
    nonprofit = "nonprofit"
    university = "university"
    corporate = "corporate"
    regional = "regional"
    philanthropic_network = "philanthropic_network"
    private = "private"
    other = "other"


class SourceReliabilityRating(StrEnum):
    """Qualitative reliability for an opportunity source registry row."""

    unknown = "unknown"
    low = "low"
    medium = "medium"
    high = "high"


class OpportunityVerificationStatus(StrEnum):
    """Verification status for registry rows and Grant Spark discovery metadata."""

    unverified = "unverified"
    operator_reviewed = "operator_reviewed"
    trusted = "trusted"
    deprecated = "deprecated"


class SparkFreshnessStatus(StrEnum):
    """Deterministic freshness classification for a Grant Spark."""

    fresh = "fresh"
    stale = "stale"
    unknown = "unknown"
    closed = "closed"


class FundingInstrument(StrEnum):
    """Funding instrument for discovery normalization (grant-forward vocabulary)."""

    grant = "grant"
    cooperative_agreement = "cooperative_agreement"
    formula = "formula"
    competitive = "competitive"
    loan = "loan"
    prize = "prize"
    other = "other"


# --- Discovery coverage (Sprint 11) ---


class FundingDomain(StrEnum):
    """Native-relevant funding domain tags for source coverage (also stored as JSON)."""

    broadband = "broadband"
    housing = "housing"
    public_safety = "public_safety"
    energy = "energy"
    water = "water"
    education = "education"
    health = "health"
    economic_development = "economic_development"
    climate_resilience = "climate_resilience"
    language_culture = "language_culture"
    infrastructure = "infrastructure"
    workforce = "workforce"
    food_sovereignty = "food_sovereignty"
    justice = "justice"
    governance = "governance"
    emergency_management = "emergency_management"
    other = "other"


class SourceCheckMethod(StrEnum):
    """How an opportunity source is checked for updates (intent, not live wiring)."""

    manual = "manual"
    rss = "rss"
    api = "api"
    web_page = "web_page"
    email_newsletter = "email_newsletter"
    pdf_bulletin = "pdf_bulletin"
    partner_feed = "partner_feed"
    unknown = "unknown"


class ExpectedOpportunityFrequency(StrEnum):
    """Typical publishing cadence for a source (planning metadata)."""

    daily = "daily"
    weekly = "weekly"
    monthly = "monthly"
    quarterly = "quarterly"
    annual = "annual"
    irregular = "irregular"
    unknown = "unknown"


class SourcePriorityLevel(StrEnum):
    """Operator priority for monitoring and expansion."""

    low = "low"
    medium = "medium"
    high = "high"
    critical = "critical"


# --- Discovery intake (Sprint 12) ---


class DiscoveryIntakeRunStatus(StrEnum):
    """Lifecycle for a discovery intake run."""

    created = "created"
    processing = "processing"
    completed = "completed"
    completed_with_errors = "completed_with_errors"
    failed = "failed"


class DiscoveryIntakeMode(StrEnum):
    """How raw candidates entered this intake run."""

    manual = "manual"
    structured_batch = "structured_batch"
    seed_catalog = "seed_catalog"
    partner_feed = "partner_feed"
    future_scrape = "future_scrape"
    future_api = "future_api"
    unknown = "unknown"


class DiscoveryCandidateStatus(StrEnum):
    """Per-candidate disposition after normalization."""

    pending = "pending"
    accepted = "accepted"
    duplicate = "duplicate"
    rejected = "rejected"
    error = "error"
