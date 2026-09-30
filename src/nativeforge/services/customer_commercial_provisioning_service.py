"""Commercial intent → entitlement → org provisioning (reference implementation)."""

from __future__ import annotations

import datetime as dt
import os
import uuid
from typing import Any

import sqlalchemy as sa

from nativeforge.services.commercial_entitlement_persistence_service import (
    persist_license_purchase,
)
from nativeforge.services.commercial_entitlement_service import (
    ACTION_RECORD_LICENSE_PURCHASE,
    CONTROLLING_COMPANY_ADMIN,
    authorize_commercial_action,
)
from nativeforge.services.customer_commercial_provisioning_repository_service import (
    insert_request,
    load_latest_for_identity,
    load_request,
    update_request,
)
from nativeforge.services.customer_workspace_lane_service import WorkspaceLane
from nativeforge.services.demo_org_classification_service import ORG_TYPES
from nativeforge.services.dev_org_membership_bootstrap_service import MEMBERSHIPS, upsert_identity
from nativeforge.services.organization_onboarding_repository_service import (
    build_authority_dimension_status,
)
from nativeforge.services.tribal_authority_model_service import (
    AFFILIATION_UNVERIFIED,
    AUTHORITY_UNVERIFIED,
)

SCHEMA_VERSION = "nf_customer_commercial_provisioning_v1"

OPERATOR_APPROVAL_ENV = "NF_COMMERCIAL_OPERATOR_APPROVAL"
OPERATOR_APPROVAL_TOKEN = "MAYHEM_APPROVES_NATIVEFORGE_COMMERCIAL_PROVISIONING"

PRODUCT_NATIVEFORGE_PRO = "nativeforge_pro"

# Conceptual lifecycle (customer-facing labels in provisioning_status_for)
LIFECYCLE_COMMERCIAL_INTENT = "commercial_intent"
LIFECYCLE_ENTITLEMENT_PENDING = "entitlement_pending"
LIFECYCLE_PROVISIONING = "provisioning"
LIFECYCLE_ORGANIZATION_SETUP = "organization_setup"
LIFECYCLE_ACTIVE = "active"
LIFECYCLE_BLOCKED_AMBIGUOUS = "blocked_ambiguous_org"
LIFECYCLE_CANCELLED = "cancelled"

CUSTOMER_STATUS_LABELS: dict[str, str] = {
    LIFECYCLE_COMMERCIAL_INTENT: "Activation requested",
    LIFECYCLE_ENTITLEMENT_PENDING: "Awaiting commercial entitlement",
    LIFECYCLE_PROVISIONING: "Provisioning in progress",
    LIFECYCLE_ORGANIZATION_SETUP: "Organization setup required",
    LIFECYCLE_ACTIVE: "Workspace active",
    LIFECYCLE_BLOCKED_AMBIGUOUS: "Organization match needs review",
    LIFECYCLE_CANCELLED: "Activation cancelled",
}

def commercial_entitlement_granted_contract() -> dict[str, Any]:
    """Future payment/manual sales hook — documented only in this sprint."""
    return {
        "schema_version": "nf_commercial_entitlement_granted_contract_v1",
        "event_name": "commercial_entitlement_granted",
        "required_fields": [
            "identity_id",
            "product_code",
            "organization_id_or_provision_new",
            "license_agreement_ref",
            "effective_date",
            "recorded_by_controlling_company_admin",
        ],
        "must_not_imply": ["tribal_authority_verified", "automatic_org_membership"],
        "canonical_backend_entry": "operator_fulfill_provisioning_request",
    }


def create_commercial_intent(
    connection: sa.engine.Connection,
    *,
    identity_id: str,
    requested_org_display_name: str,
    requested_org_hint: str | None = None,
    product_code: str = PRODUCT_NATIVEFORGE_PRO,
    is_demo: bool = False,
) -> dict[str, Any]:
    name = (requested_org_display_name or "").strip()
    if not name:
        return _blocked("requested_org_display_name_required")
    latest = load_latest_for_identity(connection, identity_id=identity_id)
    if latest and latest["lifecycle_status"] not in {
        LIFECYCLE_CANCELLED,
        LIFECYCLE_BLOCKED_AMBIGUOUS,
    }:
        if latest["lifecycle_status"] != LIFECYCLE_COMMERCIAL_INTENT:
            return provisioning_status_for(latest)
    row = insert_request(
        connection,
        identity_id=identity_id,
        lifecycle_status=LIFECYCLE_COMMERCIAL_INTENT,
        product_code=product_code,
        requested_org_display_name=name,
        requested_org_hint=requested_org_hint,
        is_demo=is_demo,
        metadata={"source": "demo_workspace_upgrade_cta"},
    )
    advanced = update_request(
        connection,
        request_id=row["request_id"],
        lifecycle_status=LIFECYCLE_ENTITLEMENT_PENDING,
    )
    return provisioning_status_for(advanced)


def provisioning_status_for(request: dict[str, Any] | None) -> dict[str, Any]:
    if not request:
        return {
            "schema_version": SCHEMA_VERSION,
            "has_request": False,
            "lifecycle_status": None,
            "customer_status_label": "Demo",
            "workspace_lane_hint": "demo",
            "commercial_intent_not_entitlement": True,
        }
    status = str(request["lifecycle_status"])
    lane: WorkspaceLane = "demo"
    if status == LIFECYCLE_ACTIVE:
        lane = "organization"
    elif status == LIFECYCLE_ORGANIZATION_SETUP and request.get("organization_id"):
        lane = "demo"
    return {
        "schema_version": SCHEMA_VERSION,
        "has_request": True,
        "request_id": request["request_id"],
        "lifecycle_status": status,
        "customer_status_label": CUSTOMER_STATUS_LABELS.get(status, status),
        "product_code": request["product_code"],
        "requested_org_display_name": request.get("requested_org_display_name"),
        "organization_id": request.get("organization_id"),
        "blocked_reasons": list(request.get("blocked_reasons") or []),
        "workspace_lane_hint": lane,
        "authority_review_pending": True,
        "commercial_intent_not_entitlement": status
        in {LIFECYCLE_COMMERCIAL_INTENT, LIFECYCLE_ENTITLEMENT_PENDING},
        "next_step_summary": _next_step_summary(status),
    }


def load_status_for_identity(
    connection: sa.engine.Connection, *, identity_id: str
) -> dict[str, Any]:
    return provisioning_status_for(
        load_latest_for_identity(connection, identity_id=identity_id)
    )


def operator_approval_configured() -> bool:
    return os.environ.get(OPERATOR_APPROVAL_ENV) == OPERATOR_APPROVAL_TOKEN


def verify_operator_approval(*, approval_value: str | None) -> bool:
    if not operator_approval_configured():
        return False
    return approval_value == OPERATOR_APPROVAL_TOKEN


def operator_fulfill_provisioning_request(
    connection: sa.engine.Connection,
    *,
    request_id: str,
    operator_actor: str,
    operator_approval: str | None,
    existing_organization_id: str | None = None,
    purchased_at: str | dt.date | None = None,
) -> dict[str, Any]:
    if not verify_operator_approval(approval_value=operator_approval):
        return _blocked("operator_approval_required")

    authz = authorize_commercial_action(
        action=ACTION_RECORD_LICENSE_PURCHASE,
        actor_role=CONTROLLING_COMPANY_ADMIN,
    )
    if not authz.get("permitted"):
        return _blocked("commercial_action_not_permitted", extra=authz)

    req = load_request(connection, request_id=request_id)
    if not req:
        return _blocked("provisioning_request_not_found")
    if req["lifecycle_status"] not in {
        LIFECYCLE_ENTITLEMENT_PENDING,
        LIFECYCLE_COMMERCIAL_INTENT,
    }:
        return provisioning_status_for(req)

    identity_id = str(req["identity_id"])
    update_request(
        connection,
        request_id=request_id,
        lifecycle_status=LIFECYCLE_PROVISIONING,
        operator_actor=operator_actor,
    )

    org_result = _resolve_or_create_organization(
        connection,
        display_name=str(req.get("requested_org_display_name") or ""),
        existing_organization_id=existing_organization_id,
        is_demo=bool(req.get("is_demo")),
    )
    if org_result.get("blocked_reasons"):
        update_request(
            connection,
            request_id=request_id,
            lifecycle_status=LIFECYCLE_BLOCKED_AMBIGUOUS,
            blocked_reasons=org_result["blocked_reasons"],
        )
        return provisioning_status_for(load_request(connection, request_id=request_id))

    org_id = str(org_result["organization_id"])
    purchase_date = purchased_at or dt.date.today()
    persist_license_purchase(
        connection,
        organization_id=org_id,
        purchased_at=purchase_date,
        recorded_by=f"operator:{operator_actor}",
        is_demo=bool(req.get("is_demo")),
    )

    upsert_identity(
        connection=connection,
        issuer="nativeforge:commercial-operator",
        subject=f"operator:{operator_actor}",
        email=f"operator+{operator_actor[:8]}@nativeforge.internal",
        email_verified=False,
        verification_source="oidc_token_signature",
    )
    membership = _insert_provisioned_membership(
        connection,
        organization_id=org_id,
        identity_id=identity_id,
        operator_actor=operator_actor,
        is_demo=bool(req.get("is_demo")),
    )
    if membership.get("blocked_reasons"):
        update_request(
            connection,
            request_id=request_id,
            lifecycle_status=LIFECYCLE_BLOCKED_AMBIGUOUS,
            organization_id=org_id,
            blocked_reasons=membership["blocked_reasons"],
        )
        return provisioning_status_for(load_request(connection, request_id=request_id))

    authority = build_authority_dimension_status(
        connection, organization_id=org_id, subject_identity_id=identity_id
    )
    final_status = LIFECYCLE_ORGANIZATION_SETUP
    updated = update_request(
        connection,
        request_id=request_id,
        lifecycle_status=final_status,
        organization_id=org_id,
        metadata={
            "membership_id": membership.get("membership_id"),
            "authority_verified": authority.get("authority_verified"),
            "affiliation_verified": authority.get("affiliation_verified"),
        },
    )
    out = provisioning_status_for(updated)
    out["entitlement_recorded"] = True
    out["membership_created"] = True
    out["authority_verified"] = authority.get("authority_status") != AUTHORITY_UNVERIFIED
    out["affiliation_verified"] = authority.get("affiliation_status") != AFFILIATION_UNVERIFIED
    out["entitlement_not_authority"] = authority.get("authority_status") == AUTHORITY_UNVERIFIED
    return out


def _resolve_or_create_organization(
    connection: sa.engine.Connection,
    *,
    display_name: str,
    existing_organization_id: str | None,
    is_demo: bool,
) -> dict[str, Any]:
    if existing_organization_id:
        try:
            oid = uuid.UUID(str(existing_organization_id))
        except ValueError:
            return {"blocked_reasons": ["existing_organization_id_invalid"]}
        row = connection.execute(
            sa.text("SELECT id, org_type, display_name FROM organizations WHERE id = :i"),
            {"i": oid.hex},
        ).first()
        if not row:
            row = connection.execute(
                sa.text("SELECT id, org_type, display_name FROM organizations WHERE id = :i"),
                {"i": str(oid)},
            ).first()
        if not row:
            return {"blocked_reasons": ["existing_organization_not_found"]}
        return {"organization_id": str(row[0]), "created": False}

    matches = connection.execute(
        sa.text(
            "SELECT id, display_name FROM organizations "
            "WHERE lower(display_name) = lower(:n) AND org_type = 'real'"
        ),
        {"n": display_name},
    ).fetchall()
    if matches:
        return {
            "blocked_reasons": [
                "ambiguous_organization_match_requires_operator_claim",
                f"matching_organization_count:{len(matches)}",
            ],
        }

    new_id = uuid.uuid4()
    org_type = "demo" if is_demo else "real"
    if org_type not in ORG_TYPES:
        return {"blocked_reasons": ["org_type_outside_vocabulary"]}
    connection.execute(
        sa.text(
            "INSERT INTO organizations (id, org_type, display_name, seat_cap, created_at) "
            "VALUES (:i, :t, :n, 5, CURRENT_TIMESTAMP)"
        ),
        {"i": new_id.hex, "t": org_type, "n": display_name},
    )
    return {"organization_id": str(new_id), "created": True}


def _insert_provisioned_membership(
    connection: sa.engine.Connection,
    *,
    organization_id: str,
    identity_id: str,
    operator_actor: str,
    is_demo: bool,
) -> dict[str, Any]:
    try:
        org_uuid = uuid.UUID(str(organization_id))
        ident_uuid = uuid.UUID(str(identity_id))
        operator_uuid = uuid.UUID(str(operator_actor))
    except ValueError:
        return {"blocked_reasons": ["uuid_shape_invalid_for_provisioning"]}

    existing = connection.execute(
        sa.select(sa.func.count())
        .select_from(MEMBERSHIPS)
        .where(MEMBERSHIPS.c.organization_id == org_uuid)
        .where(MEMBERSHIPS.c.identity_id == ident_uuid)
    ).scalar_one()
    if int(existing or 0) > 0:
        return {
            "membership_id": None,
            "blocked_reasons": [],
            "already_member": True,
        }

    mid = uuid.uuid4()
    moment = dt.datetime.now(dt.UTC)
    connection.execute(
        sa.insert(MEMBERSHIPS).values(
            id=mid,
            organization_id=org_uuid,
            identity_id=ident_uuid,
            is_demo=is_demo,
            state="active",
            membership_source="operator_approved",
            role="grant_lead",
            role_source="membership_record",
            approved_by=operator_uuid,
            invited_by=operator_uuid,
            invite_id=None,
            created_at=moment,
            revoked_at=None,
            expires_at=None,
        )
    )
    return {"membership_id": str(mid), "blocked_reasons": [], "already_member": False}


def _next_step_summary(status: str) -> str:
    if status == LIFECYCLE_COMMERCIAL_INTENT:
        return "Your activation request was received."
    if status == LIFECYCLE_ENTITLEMENT_PENDING:
        return (
            "NativeForge will connect commercial entitlement before provisioning "
            "your organization workspace."
        )
    if status == LIFECYCLE_PROVISIONING:
        return "Your organization workspace is being prepared."
    if status == LIFECYCLE_ORGANIZATION_SETUP:
        return (
            "Complete your organization profile so NativeForge can evaluate "
            "opportunities against your organization's capabilities and eligibility."
        )
    if status == LIFECYCLE_BLOCKED_AMBIGUOUS:
        return "An operator must resolve the organization match before continuing."
    if status == LIFECYCLE_ACTIVE:
        return "Sign in again to enter your organization workspace."
    return "Explore the demo workspace while activation is pending."


def _blocked(code: str, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "storage_allowed": False,
        "blocked_reasons": [code],
    }
    if extra:
        payload["authorization"] = extra
    return payload
