"""Gate 146: measure customer-auth activation under the approved demo org context.

Global activation facts (invite binding, org binding, role mapping) live in
tenant-scoped tables. Reading them on an RLS-cleared connection reports zero
rows on Postgres even when production has walked the path.

This module applies the same organizational context the operator invite scripts
use: the owner-approved demo organization only (`customer_auth_owner_activation_
decision_service.APPROVED_ORGANIZATION_ID`). That is not a privileged bypass;
RLS still applies, and any other organization remains invisible.

Per-request session routes must not confuse *system activation* with *this
caller's membership*. Callers authenticate without necessarily holding a
customer organization; affiliation is verified separately on org-scoped routes.
"""

from __future__ import annotations

import uuid
from typing import Any

from nativeforge.db.rls import apply_org_rls_gucs
from nativeforge.db.session import SessionLocal
from nativeforge.lib.settings import auth_environment_overlay
from nativeforge.services.customer_auth_activation_gate_service import (
    build_customer_auth_activation_gate,
)
from nativeforge.services.customer_auth_binding_evidence_service import (
    build_binding_evidence,
)
from nativeforge.services.customer_auth_jwks_validation_evidence_service import (
    build_jwks_validation_evidence,
)
from nativeforge.services.customer_auth_owner_activation_decision_service import (
    APPROVED_ORGANIZATION_ID,
    build_customer_auth_activation_decision,
    build_owner_activation_decision,
)
from nativeforge.services.customer_auth_role_mapping_evidence_service import (
    build_role_mapping_evidence,
)
from nativeforge.services.dev_header_exposure_matrix_service import (
    build_dev_header_exposure_matrix,
)
from nativeforge.services.membership_invite_repository_service import (
    build_invite_binding_evidence,
)

APPROVED_DEMO_ORG = uuid.UUID(APPROVED_ORGANIZATION_ID)

# Auth conjuncts that do not require the second-person invite event.
INFRASTRUCTURE_AUTH_GATES: tuple[str, ...] = (
    "provider_configured",
    "secret_present",
    "issuer_configured",
    "issuer_jwks_validated",
    "audience_configured",
    "callback_route_available",
    "callback_session_validated",
    "session_cookie_policy_available",
    "org_binding_passed",
    "role_mapping_passed",
    "organization_id_resolution_available",
    "membership_verification_available",
    "rls_claim_guard_available",
    "dev_header_disabled_for_production",
    "session_signing_key_ready",
)


def build_measured_customer_auth_activation_gate() -> dict[str, Any]:
    """Read activation evidence under the approved demo org and build the gate."""
    matrix = build_dev_header_exposure_matrix()
    provider = (auth_environment_overlay().get("OIDC_ISSUER") or "").strip()
    organization = APPROVED_DEMO_ORG

    session = SessionLocal()
    try:
        apply_org_rls_gucs(session, organization, "demo")
        connection = session.connection()
        binding_evidence = build_binding_evidence(connection=connection)
        jwks_evidence = build_jwks_validation_evidence(connection=connection)
        role_evidence = build_role_mapping_evidence(connection=connection)
        invite_evidence = build_invite_binding_evidence(connection=connection)
    except Exception:
        session.rollback()
        binding_evidence = jwks_evidence = role_evidence = invite_evidence = None
    finally:
        session.close()

    login_decision = build_owner_activation_decision(
        organization_id=organization, provider=provider
    )
    customer_auth_decision = build_customer_auth_activation_decision(
        organization_id=organization, provider=provider
    )

    gate = build_customer_auth_activation_gate(
        binding_evidence=binding_evidence,
        jwks_validation_evidence=jwks_evidence,
        role_mapping_evidence=role_evidence,
        invite_binding_evidence=invite_evidence,
        login_activation_decision=login_decision,
        customer_auth_activation_decision=customer_auth_decision,
        dev_header_exposure=matrix,
    )
    gate["measurement_scope_organization_id"] = APPROVED_ORGANIZATION_ID
    gate["measurement_performed"] = True
    gate["customer_auth_infrastructure_ready"] = _infrastructure_ready(gate)
    gate["customer_auth_owner_activation_approved"] = bool(
        gate.get("owner_approval_present")
    )
    return gate


def _infrastructure_ready(gate: dict[str, Any]) -> bool:
    for name in INFRASTRUCTURE_AUTH_GATES:
        if not gate.get(name):
            return False
    return True
