"""Authority proof workflow (Gate 52).

A person must prove they may speak or apply for an organization before
authority-sensitive actions unlock.

Design rule that drives every branch below: **submitted is not verified**, and
verification can lapse. Nothing in this module asserts a tribal fact, a
registration status, or an eligibility determination — it only records what has
been evidenced and what that unlocks.

Composes with ``applicant_authority_contract_service`` (Block 28), which models
the per-opportunity authority record; this module models the organization-level
proof lifecycle that gates it.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_authority_proof_workflow_v1"

PROOF_STATES = frozenset(
    {
        "not_started",
        "requested",
        "submitted",
        "under_review",
        "verified",
        "rejected",
        "expired",
        "revoked",
        "unknown",
    }
)

# Only this state can unlock anything. Everything else blocks.
UNLOCKING_STATES = frozenset({"verified"})

BLOCKING_STATES = PROOF_STATES - UNLOCKING_STATES

PROOF_TYPES = frozenset(
    {
        "organizational_email_domain_evidence",
        "board_or_officer_attestation",
        "tribal_resolution_or_authorization_letter",
        "grant_office_assignment",
        "sam_uei_ebiz_aor_evidence",
        "state_portal_administrator_proof",
        "uploaded_governance_document",
        "operator_reviewed_exception",
        "unknown",
    }
)

AUTHORITY_SENSITIVE_ACTIONS = frozenset(
    {
        "final_eligibility_assertion",
        "official_submission_readiness",
        "official_package_approval",
        "certify_official_org_facts",
        "represent_board_resolution_approval",
        "authorized_representative_certification",
        "claim_sam_uei_ebiz_aor_status",
        "claim_state_portal_authority",
        "final_application_package_signoff",
    }
)

# Roles permitted to hold verified authority. A reviewer or viewer never can,
# and internal support never carries customer authority.
AUTHORITY_CAPABLE_ROLES = frozenset(
    {"org_owner", "org_admin", "authorized_representative"}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_authority_proof_id(person_id: str, organization_profile_id: str) -> str:
    raw = f"ap::{person_id}::{organization_profile_id}".encode()
    return f"ap_{hashlib.sha256(raw).hexdigest()[:16]}"


def build_authority_proof(
    *,
    person_id: str,
    organization_profile_id: str,
    role: str,
    state: str = "not_started",
    proof_types_submitted: list[str] | None = None,
    verified_by: str | None = None,
    verified_at: str | None = None,
    expires_at: str | None = None,
    revoked_reason: str | None = None,
    now: str | None = None,
) -> dict[str, Any]:
    """Build an organization-level authority proof record.

    ``now`` is caller-supplied rather than read from the clock so the record is
    deterministic and testable; expiry is evaluated against it when both are
    present.
    """
    st = state if state in PROOF_STATES else "unknown"
    types = [
        t if t in PROOF_TYPES else "unknown" for t in (proof_types_submitted or [])
    ]

    # Expiry is derived, never asserted: a verified proof past its expiry is
    # expired regardless of what the caller passed in.
    if st == "verified" and expires_at and now and str(now) >= str(expires_at):
        st = "expired"

    # A verified state with no verifier is not verification.
    if st == "verified" and not verified_by:
        st = "under_review"

    unlocks = st in UNLOCKING_STATES and role in AUTHORITY_CAPABLE_ROLES

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "authority_proof_id": make_authority_proof_id(
                person_id, organization_profile_id
            ),
            "person_id": person_id,
            "organization_profile_id": organization_profile_id,
            "role": role,
            "state": st,
            "proof_types_submitted": types,
            "verified_by": verified_by,
            "verified_at": verified_at,
            "expires_at": expires_at,
            "revoked_reason": revoked_reason,
            "unlocks_authority_sensitive_actions": unlocks,
            "role_is_authority_capable": role in AUTHORITY_CAPABLE_ROLES,
            # Honest boundaries — a proof record never asserts external status.
            "sam_uei_status_claimed": False,
            "aor_status_claimed": False,
            "portal_access_claimed": False,
            "tribal_facts_asserted": False,
            "final_eligibility_claimed": False,
        }
    )


def evaluate_authority_sensitive_action(
    *,
    action: str,
    proof: dict[str, Any],
    missing_evidence: list[str] | None = None,
) -> dict[str, Any]:
    """Decide whether an authority-sensitive action may proceed.

    Two independent gates, both of which must clear:
      1. verified, unexpired, unrevoked authority proof held by a capable role
      2. no missing evidence

    An authorized_representative clears gate 1 but can never bypass gate 2.
    """
    reasons: list[str] = []
    missing = [str(m) for m in (missing_evidence or [])]

    known_action = action in AUTHORITY_SENSITIVE_ACTIONS
    if not known_action:
        reasons.append("action_not_recognized_as_authority_sensitive")

    state = proof.get("state")
    if state not in PROOF_STATES:
        reasons.append("proof_state_unknown")
    elif state in BLOCKING_STATES:
        reasons.append(f"authority_proof_state_blocks:{state}")

    if not proof.get("role_is_authority_capable"):
        reasons.append("role_not_authority_capable")

    if not proof.get("unlocks_authority_sensitive_actions"):
        reasons.append("authority_not_unlocked")

    if missing:
        reasons.append("missing_evidence_present")

    allowed = known_action and not reasons

    audit_event = (
        None
        if allowed
        else {
            "event_type": "authority_sensitive_action_blocked",
            "action": action,
            "organization_profile_id": proof.get("organization_profile_id"),
            "person_id": proof.get("person_id"),
            "reasons": reasons,
        }
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "action": action,
            "allowed": allowed,
            "blocked_reasons": reasons,
            "missing_evidence": missing,
            "authority_state": state,
            # Even when allowed, none of these become true here.
            "final_eligibility_claimed": False,
            "submission_ready_claimed": False,
            "audit_event": audit_event,
        }
    )


def transition_authority_proof(
    *,
    proof: dict[str, Any],
    new_state: str,
    actor_id: str,
    reason: str | None = None,
) -> dict[str, Any]:
    """Apply a lifecycle transition and emit the matching audit event."""
    target = new_state if new_state in PROOF_STATES else "unknown"
    event_map = {
        "requested": "authority_proof_requested",
        "submitted": "authority_proof_submitted",
        "verified": "authority_proof_verified",
        "rejected": "authority_proof_rejected",
        "expired": "authority_proof_expired",
        "revoked": "authority_proof_revoked",
    }
    updated = dict(proof)
    updated["state"] = target
    # Any non-verified state immediately removes the unlock.
    updated["unlocks_authority_sensitive_actions"] = bool(
        target in UNLOCKING_STATES and proof.get("role_is_authority_capable")
    )
    if target == "revoked":
        updated["revoked_reason"] = reason

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "proof": updated,
            "audit_event": {
                "event_type": event_map.get(target, "authority_proof_requested"),
                "organization_profile_id": proof.get("organization_profile_id"),
                "person_id": proof.get("person_id"),
                "actor_id": actor_id,
                "new_state": target,
                "reason": reason,
                "persisted": False,
            },
        }
    )


def authority_proof_invariant_failures(proof: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if proof.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if proof.get("state") not in PROOF_STATES:
        fails.append("state_invalid")
    for t in proof.get("proof_types_submitted") or []:
        if t not in PROOF_TYPES:
            fails.append("proof_type_invalid")
    # Unlock must never be true outside a verified state held by a capable role.
    if proof.get("unlocks_authority_sensitive_actions"):
        if proof.get("state") not in UNLOCKING_STATES:
            fails.append("unlock_without_verified_state")
        if not proof.get("role_is_authority_capable"):
            fails.append("unlock_without_capable_role")
    for forbidden in (
        "sam_uei_status_claimed",
        "aor_status_claimed",
        "portal_access_claimed",
        "tribal_facts_asserted",
        "final_eligibility_claimed",
    ):
        if proof.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")
    return fails
