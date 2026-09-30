"""Operator path for affiliation/authority evidence review (Gate 177)."""

from __future__ import annotations

import os
from typing import Any

import sqlalchemy as sa

from nativeforge.services.organization_onboarding_repository_service import (
    list_pending_evidence,
    load_evidence_by_id,
    persist_authority_grant,
    sync_authority_grant_from_evidence,
    update_evidence_decision,
)
from nativeforge.services.tribal_authority_evidence_service import (
    DECISION_ACCEPTED,
    DECISION_PENDING,
    decide_evidence,
)

SCHEMA_VERSION = "nf_tribal_authority_operator_review_v1"

OPERATOR_APPROVAL_ENV = "NF_AUTHORITY_REVIEW_OPERATOR_APPROVAL"
OPERATOR_APPROVAL_TOKEN = "MAYHEM_APPROVES_NATIVEFORGE_AUTHORITY_REVIEW"


def operator_approval_configured() -> bool:
    return os.environ.get(OPERATOR_APPROVAL_ENV) == OPERATOR_APPROVAL_TOKEN


def verify_operator_approval(approval_value: str | None) -> bool:
    return approval_value == OPERATOR_APPROVAL_TOKEN


def operator_list_pending(
    connection: sa.engine.Connection,
    *,
    organization_id: str | None = None,
    limit: int = 50,
    operator_approval: str | None,
) -> dict[str, Any]:
    if not verify_operator_approval(operator_approval):
        return {
            "accepted": False,
            "why": "operator_approval_required",
            "env_var": OPERATOR_APPROVAL_ENV,
        }
    rows = list_pending_evidence(
        connection, organization_id=organization_id, limit=limit
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "accepted": True,
        "pending_count": len(rows),
        "pending_evidence": rows,
    }


def operator_decide_evidence(
    connection: sa.engine.Connection,
    *,
    evidence_id: str,
    decision: str,
    reviewer: str,
    reason: str,
    operator_actor: str,
    operator_approval: str | None,
) -> dict[str, Any]:
    if not verify_operator_approval(operator_approval):
        return {
            "accepted": False,
            "why": "operator_approval_required",
            "env_var": OPERATOR_APPROVAL_ENV,
        }
    if not reviewer or not str(reviewer).strip():
        return {"accepted": False, "why": "reviewer_required"}
    if not reason or not str(reason).strip():
        return {"accepted": False, "why": "reason_required"}
    if not operator_actor or not str(operator_actor).strip():
        return {"accepted": False, "why": "operator_actor_required"}

    loaded = load_evidence_by_id(connection, evidence_id=evidence_id)
    if not loaded:
        return {"accepted": False, "why": "evidence_not_found", "evidence_id": evidence_id}
    if str(loaded.get("decision")) != DECISION_PENDING:
        return {
            "accepted": False,
            "why": "evidence_not_pending",
            "current_decision": loaded.get("decision"),
        }
    subject = str(loaded.get("subject_identity_id") or "")
    if subject and str(reviewer).strip() == subject:
        return {
            "accepted": False,
            "why": "self_approval_forbidden",
            "subject_identity_id": subject,
        }

    decided = decide_evidence(
        evidence=loaded,
        decision=decision,
        reviewer=reviewer,
        reason=reason,
    )
    if not decided.get("accepted"):
        return {"accepted": False, "why": decided.get("why"), "evidence_id": evidence_id}

    updated = update_evidence_decision(
        connection, evidence=decided["evidence"]
    )
    if not updated.get("updated"):
        return {
            "accepted": False,
            "why": "evidence_update_failed",
            "detail": updated,
        }

    org_id = str(loaded.get("organization_id") or "")
    sync = sync_authority_grant_from_evidence(
        connection,
        organization_id=org_id,
        subject_identity_id=subject,
    )
    if not sync.get("accepted") and str(decision) == DECISION_ACCEPTED:
        return {
            "accepted": False,
            "why": sync.get("why") or "grant_sync_failed",
            "evidence_decision_recorded": True,
            "grant_sync": sync,
        }

    return {
        "schema_version": SCHEMA_VERSION,
        "accepted": True,
        "evidence_id": evidence_id,
        "decision": decision,
        "reviewer": reviewer,
        "operator_actor": operator_actor,
        "organization_id": org_id,
        "subject_identity_id": subject,
        "grant_sync": sync,
        "audit_event": {
            "action": "authority.evidence_reviewed",
            "evidence_id": evidence_id,
            "decision": decision,
            "reviewer": reviewer,
            "operator_actor": operator_actor,
            "organization_id": org_id,
            "subject_identity_id": subject,
            "reason": reason,
        },
    }


def operator_verify_authority_manually(
    connection: sa.engine.Connection,
    *,
    organization_id: str,
    identity_id: str,
    verified_by: str,
    reason: str,
    operator_actor: str,
    operator_approval: str | None,
    customer_relationship_ref: str | None = None,
    is_demo: bool = False,
) -> dict[str, Any]:
    """Controlling-company manual authority verification (177D) with persistence."""
    from nativeforge.services.tribal_authority_evidence_service import (
        verify_authority_manually,
    )

    if not verify_operator_approval(operator_approval):
        return {
            "accepted": False,
            "why": "operator_approval_required",
            "env_var": OPERATOR_APPROVAL_ENV,
        }
    if str(verified_by).strip() == str(identity_id).strip():
        return {"accepted": False, "why": "self_approval_forbidden"}

    result = verify_authority_manually(
        organization_id=organization_id,
        identity_id=identity_id,
        verified_by=verified_by,
        verified_by_is_controlling_company=True,
        reason=reason,
        customer_relationship_ref=customer_relationship_ref,
        is_demo=is_demo,
    )
    if not result.get("accepted"):
        return result

    evidence = result.get("evidence")
    grant = result.get("grant")
    if evidence:
        from nativeforge.services.organization_onboarding_repository_service import (
            persist_evidence,
        )

        persist_evidence(connection, evidence=evidence)
    if grant:
        persisted = persist_authority_grant(connection, grant=grant)
        if not persisted.get("persisted"):
            return {
                "accepted": False,
                "why": "grant_persist_failed",
                "detail": persisted,
            }

    return {
        "schema_version": SCHEMA_VERSION,
        "accepted": True,
        "operator_actor": operator_actor,
        "organization_id": organization_id,
        "identity_id": identity_id,
        "grant": grant,
        "audit_event": result.get("audit_event"),
    }
