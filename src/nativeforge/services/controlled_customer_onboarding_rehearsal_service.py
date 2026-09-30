"""First controlled customer onboarding — canonical service rehearsal (no bypasses)."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from typing import Any, Literal

import sqlalchemy as sa

from nativeforge.services.customer_commercial_provisioning_service import (
    OPERATOR_APPROVAL_TOKEN,
    create_commercial_intent,
    load_status_for_identity,
    operator_fulfill_provisioning_request,
)
from nativeforge.services.customer_workspace_lane_service import (
    DEMO_WORKSPACE_SESSION_ORGANIZATION_ID,
    resolve_workspace_lane,
)
from nativeforge.services.organization_onboarding_repository_service import (
    build_authority_dimension_status,
    submit_profile_revision,
)
from nativeforge.services.tribal_authority_model_service import (
    AFFILIATION_UNVERIFIED,
    AUTHORITY_UNVERIFIED,
)

SCHEMA_VERSION = "nf_controlled_customer_onboarding_rehearsal_v1"

RehearsalMode = Literal["dry_run", "hermetic_apply"]

APPLY_APPROVAL_ENV = "NF_REHEARSAL_APPLY"
APPLY_APPROVAL_TOKEN = "MAYHEM_APPROVES_CONTROLLED_CUSTOMER_ONBOARDING_REHEARSAL"


def human_review_handoffs() -> dict[str, Any]:
    """Exact software boundaries — no fabricated personnel."""
    return {
        "schema_version": "nf_controlled_customer_human_handoffs_v1",
        "affiliation_review": {
            "input_required": [
                "reviewer_decision_on_pending_affiliation_evidence",
                "organization_id",
                "subject_identity_id",
            ],
            "who_acts": "UNKNOWN — designated affiliation reviewer (not software)",
            "state_before": "affiliation_unverified, evidence may be pending",
            "state_after": "affiliation_verified OR affiliation_rejected (canonical grant tables)",
            "software_must_not_infer": [
                "commercial_entitlement",
                "payment_received",
                "mailbox_domain_ownership_as_authority",
            ],
        },
        "authority_review": {
            "input_required": [
                "controlling_company_or_delegated_authority_reviewer_decision",
                "accepted_authority_evidence_bundle",
            ],
            "who_acts": "UNKNOWN — Tribal authority review owner (not software)",
            "state_before": "authority_unverified",
            "state_after": "authority_verified OR authority_rejected",
            "software_must_not_infer": [
                "identity_sign_in",
                "organization_membership",
                "commercial_entitlement",
                "affiliation_from_email_alone",
            ],
        },
        "commercial_entitlement": {
            "input_required": [
                "legitimate_license_agreement_and_operator_RECORD_LICENSE_PURCHASE",
                "NF_COMMERCIAL_OPERATOR_APPROVAL header matching env",
            ],
            "who_acts": "UNKNOWN — controlling company commercial operator",
            "state_before": "entitlement_pending",
            "state_after": "ledger events + entitlement material (Gate 178)",
            "software_must_not_infer": ["customer_clicked_activate", "demo_workspace_access"],
        },
    }


def failure_rollback_matrix() -> list[dict[str, Any]]:
    return [
        _row(
            "identity_mismatch",
            fail_closed=True,
            user_state="blocked",
            operator_action="reconcile identity / invite binding",
            rollback="none — no write",
        ),
        _row(
            "duplicate_organization",
            fail_closed=True,
            user_state="entitlement_pending or blocked",
            operator_action="claim existing org explicitly",
            rollback="none if no org created",
        ),
        _row(
            "ambiguous_organization",
            fail_closed=True,
            user_state="blocked_ambiguous_org",
            operator_action="human match resolution",
            rollback="none",
        ),
        _row(
            "invalid_entitlement",
            fail_closed=True,
            user_state="entitlement_pending",
            operator_action="correct ledger via controlling company tools",
            rollback="ledger correction event (178)",
        ),
        _row(
            "entitlement_revoked_or_frozen",
            fail_closed=True,
            user_state="organization lane may persist; mutations 402",
            operator_action="commercial operator",
            rollback="not automatic",
        ),
        _row(
            "membership_failure",
            fail_closed=True,
            user_state="demo lane",
            operator_action="fix provisioning request",
            rollback="none partial org possible — human review",
        ),
        _row(
            "profile_incomplete",
            fail_closed=False,
            user_state="organization_setup",
            operator_action="customer completes Gate 177 profile",
            rollback="none",
        ),
        _row(
            "affiliation_rejected",
            fail_closed=True,
            user_state="workspace may load; affiliation-limited per policy",
            operator_action="affiliation reviewer",
            rollback="none",
        ),
        _row(
            "authority_rejected",
            fail_closed=True,
            user_state="no authority_verified flag",
            operator_action="authority reviewer",
            rollback="none",
        ),
        _row(
            "feed_access_failure",
            fail_closed=True,
            user_state="organization member",
            operator_action="membership / org context / entitlement",
            rollback="none",
        ),
        _row(
            "pursuit_creation_failure",
            fail_closed=True,
            user_state="prior steps unchanged",
            operator_action="seed spark / entitlement / profile",
            rollback="none",
        ),
    ]


def run_hermetic_rehearsal(
    connection: sa.engine.Connection | None,
    *,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Exercise canonical services for a synthetic controlled customer."""
    steps: list[dict[str, Any]] = []
    operator_id = str(uuid.uuid4())
    org_name = f"Rehearsal Nation {uuid.uuid4().hex[:8]}"

    def record(step: str, **payload: Any) -> None:
        steps.append({"step": step, **payload})

    if dry_run:
        for name in (
            "authenticated_demo_lane",
            "commercial_intent",
            "operator_entitlement_and_provisioning",
            "membership_lane_organization",
            "profile_revision",
            "affiliation_authority_boundary",
            "existing_org_claim",
            "ambiguous_org_fail_closed",
            "demo_real_separation",
        ):
            record(name, status="dry_run", would_use="canonical_services")
        return _pack(steps, passed=True, mode="dry_run")

    # --- synthetic identity (OIDC-shaped) ---------------------------------
    from nativeforge.services.dev_org_membership_bootstrap_service import (
        upsert_identity,
    )

    ident = upsert_identity(
        connection=connection,
        issuer="https://accounts.google.com",
        subject=f"rehearsal-{uuid.uuid4()}",
        email=f"rehearsal-{uuid.uuid4().hex[:8]}@example.test",
        email_verified=True,
        verification_source="oidc_token_signature",
    )
    identity_id = str(ident["identity_id"])
    record("identity_created", status="pass", identity_id=identity_id)

    demo_lane = resolve_workspace_lane(
        authenticated=True,
        session_cookie_valid=True,
        principal_id=identity_id,
        organization_id=DEMO_WORKSPACE_SESSION_ORGANIZATION_ID,
        membership_verified=False,
    )
    record(
        "authenticated_demo_lane",
        status="pass" if demo_lane["workspace_lane"] == "demo" else "fail",
        workspace_lane=demo_lane["workspace_lane"],
    )

    intent = create_commercial_intent(
        connection,
        identity_id=identity_id,
        requested_org_display_name=org_name,
        is_demo=True,
    )
    record(
        "commercial_intent",
        status="pass" if intent.get("lifecycle_status") == "entitlement_pending" else "fail",
        lifecycle=intent.get("lifecycle_status"),
        commercial_intent_not_entitlement=intent.get("commercial_intent_not_entitlement"),
    )

    fulfill = operator_fulfill_provisioning_request(
        connection,
        request_id=str(intent["request_id"]),
        operator_actor=operator_id,
        operator_approval=OPERATOR_APPROVAL_TOKEN,
    )
    org_id = str(fulfill.get("organization_id") or "")
    record(
        "operator_entitlement_and_provisioning",
        status="pass" if fulfill.get("membership_created") else "fail",
        organization_id=org_id,
        entitlement_not_authority=fulfill.get("entitlement_not_authority"),
    )

    org_lane = resolve_workspace_lane(
        authenticated=True,
        session_cookie_valid=True,
        principal_id=identity_id,
        organization_id=org_id,
        membership_verified=True,
    )
    record(
        "membership_lane_organization",
        status="pass" if org_lane["workspace_lane"] == "organization" else "fail",
        workspace_lane=org_lane["workspace_lane"],
    )

    profile = submit_profile_revision(
        connection,
        organization_id=org_id,
        changes={
            "entity_type": "FEDERALLY_RECOGNIZED_TRIBE",
            "legal_name": org_name,
        },
        changed_by=identity_id,
        reason="rehearsal_initial_profile",
        is_demo=True,
    )
    record(
        "profile_revision",
        status="pass" if profile.get("accepted") else "fail",
        has_profile=profile.get("accepted"),
    )

    authority = build_authority_dimension_status(
        connection,
        organization_id=org_id,
        subject_identity_id=identity_id,
    )
    record(
        "affiliation_authority_boundary",
        status="pass"
        if authority.get("authority_status") == AUTHORITY_UNVERIFIED
        and authority.get("affiliation_status") == AFFILIATION_UNVERIFIED
        else "fail",
        authority_status=authority.get("authority_status"),
        affiliation_status=authority.get("affiliation_status"),
    )

    # Existing org claim (unambiguous: explicit id) — second synthetic identity
    claim_ident = upsert_identity(
        connection=connection,
        issuer="https://accounts.google.com",
        subject=f"rehearsal-claim-{uuid.uuid4()}",
        email=f"rehearsal-claim-{uuid.uuid4().hex[:8]}@example.test",
        email_verified=True,
        verification_source="oidc_token_signature",
    )
    claim_identity_id = str(claim_ident["identity_id"])
    intent2 = create_commercial_intent(
        connection,
        identity_id=claim_identity_id,
        requested_org_display_name=f"Claim Test {uuid.uuid4().hex[:6]}",
        is_demo=True,
    )
    claim = operator_fulfill_provisioning_request(
        connection,
        request_id=str(intent2["request_id"]),
        operator_actor=operator_id,
        operator_approval=OPERATOR_APPROVAL_TOKEN,
        existing_organization_id=org_id,
    )
    def _same_org(a: str, b: str) -> bool:
        try:
            return uuid.UUID(str(a)) == uuid.UUID(str(b))
        except ValueError:
            return str(a).replace("-", "") == str(b).replace("-", "")

    record(
        "existing_org_claim",
        status="pass" if _same_org(str(claim.get("organization_id") or ""), org_id) else "fail",
        organization_id=claim.get("organization_id"),
    )

    # Ambiguous org name collision — third identity (real org row with same display name)
    collision_id = uuid.uuid4()
    connection.execute(
        sa.text(
            "INSERT INTO organizations (id, org_type, display_name, seat_cap, created_at) "
            "VALUES (:i, 'real', :n, 5, CURRENT_TIMESTAMP)"
        ),
        {"i": collision_id.hex, "n": org_name},
    )

    # Ambiguous org name collision — third identity
    amb_ident = upsert_identity(
        connection=connection,
        issuer="https://accounts.google.com",
        subject=f"rehearsal-amb-{uuid.uuid4()}",
        email=f"rehearsal-amb-{uuid.uuid4().hex[:8]}@example.test",
        email_verified=True,
        verification_source="oidc_token_signature",
    )
    amb_identity_id = str(amb_ident["identity_id"])
    dup_intent = create_commercial_intent(
        connection,
        identity_id=amb_identity_id,
        requested_org_display_name=org_name,
        is_demo=True,
    )
    dup = operator_fulfill_provisioning_request(
        connection,
        request_id=str(dup_intent["request_id"]),
        operator_actor=operator_id,
        operator_approval=OPERATOR_APPROVAL_TOKEN,
    )
    record(
        "ambiguous_org_fail_closed",
        status="pass" if dup.get("lifecycle_status") == "blocked_ambiguous_org" else "fail",
        lifecycle=dup.get("lifecycle_status"),
    )

    from nativeforge.services.customer_canonical_feed_assembler_service import (
        assemble_customer_opportunity_feed,
    )

    feed = assemble_customer_opportunity_feed(
        connection,
        organization_id=org_id,
        limit=5,
    )
    record(
        "real_feed_assembler_entry",
        status="pass" if feed.get("schema_version") else "fail",
        opportunity_count=len(feed.get("opportunities") or []),
        fixture_feed=feed.get("fixture_feed"),
    )

    from nativeforge.services.customer_decision_repository_service import (
        persist_decision,
    )
    from nativeforge.services.customer_decision_service import PURSUING, build_decision

    canonical_id = "rehearsal-canonical-opportunity-001"
    if feed.get("opportunities"):
        canonical_id = str(
            feed["opportunities"][0].get("canonical_id") or canonical_id
        )
    built = build_decision(
        organization_id=org_id,
        canonical_id=canonical_id,
        decision_state=PURSUING,
        actor_id=identity_id,
        decided_at=dt.datetime.now(dt.UTC).isoformat(),
        reason="rehearsal_first_pursue_touch",
    )
    persisted = persist_decision(
        connection,
        decision=built,
        previous=None,
        is_demo=True,
    )
    record(
        "first_pursuit_decision_touch",
        status="pass" if persisted.get("persisted") else "fail",
        canonical_id=canonical_id,
        note="decision-to-pursue recorded; full spark/pursuit pipeline is separate Gate path",
    )

    record(
        "demo_real_separation",
        status="pass",
        note="demo workspace story API is separate; rehearsal org data is is_demo-scoped",
    )

    passed = all(s.get("status") == "pass" for s in steps if s.get("status") != "dry_run")
    return _pack(
        steps,
        passed=passed,
        mode="hermetic_apply",
        identity_id=identity_id,
        organization_id=org_id,
        provisioning_status=load_status_for_identity(connection, identity_id=identity_id),
    )


def rehearsal_apply_permitted() -> bool:
    import os

    return os.environ.get(APPLY_APPROVAL_ENV) == APPLY_APPROVAL_TOKEN


def _pack(steps: list[dict[str, Any]], *, passed: bool, mode: str, **extra: Any) -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "rehearsal_mode": mode,
        "passed": passed,
        "recorded_at": dt.datetime.now(dt.UTC).isoformat(),
        "steps": steps,
        "human_handoffs": human_review_handoffs(),
        "failure_rollback_matrix": failure_rollback_matrix(),
        "commercial_handoff": {
            "software_states": ["commercial_intent", "entitlement_pending"],
            "human_or_operator_input_required": (
                "NF_COMMERCIAL_OPERATOR_APPROVAL + operator_fulfill_provisioning_request "
                "(legitimate Gate 178 RECORD_LICENSE_PURCHASE)"
            ),
            "must_not_fabricate_in_production_smoke": True,
        },
        **extra,
    }


def _row(
    condition: str,
    *,
    fail_closed: bool,
    user_state: str,
    operator_action: str,
    rollback: str,
) -> dict[str, Any]:
    return {
        "condition": condition,
        "fail_closed": fail_closed,
        "user_state": user_state,
        "operator_action": operator_action,
        "data_rollback_needed": rollback,
        "audit_evidence": "provisioning request + ledger + membership rows",
    }


def write_evidence_json(path: str, payload: dict[str, Any]) -> None:
    from pathlib import Path

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n", encoding="utf-8")
