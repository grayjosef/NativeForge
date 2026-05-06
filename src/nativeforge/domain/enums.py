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
