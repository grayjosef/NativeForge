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
