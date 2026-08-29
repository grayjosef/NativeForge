"""Customer auth principal contract (Gate 111B).

Who is acting, and what their authentication actually establishes.

## Authenticated is not the same as verified-org

The distinction the whole contract turns on, and it is not pedantic. Gate 111A
found that `oidc_identity_mapper_service` resolves a claim to an
`organization_profile_id` — a `String(128)` with no foreign key, on a table with
no row-level security. It never produces the `organization_id` UUID that every
RLS policy enforces on.

So even a real, provider-validated login would establish *a person* without
establishing *which organization they may act for*. Those are two facts and this
contract keeps them in two fields:

```text
claims_verified      the provider vouched for the subject
org_claim_verified   somebody established which organization_id that means
```

An `authenticated_unverified_org` principal is a normal, expected state — not a
degraded one. Collapsing the two into a single "logged in" boolean is how a
verified person ends up acting for an organization nobody checked.

## Demo auth is not production auth

`demo_fixture` is a source, not a lesser tier of the real thing. A demo principal
gets `authenticated_demo`, never `authenticated_verified_org`, and
`is_production_authenticated` is False on it however many roles it carries.

## Cloudflare Access is a front door

It controls who reaches the host. It says nothing about which organization a
request may act for and it sets no RLS context, so `cloudflare_access` alone
yields `authenticated_unverified_org` at best — and a blocked reason saying why.

Treating edge access as application auth is the specific mistake this refuses:
everyone who can open the site would otherwise look like a customer.

## RLS context requires a UUID organization_id

`rls_context_allowed` needs a verified org claim **and** a UUID-shaped
`organization_id`, checked through Gate 110's role contract rather than
re-implemented here. `tenant_id` and `customer_org_id` cannot produce it at all;
that refusal lives in the claim guard (Gate 111D) and is not duplicated.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.org_identity_role_contract_service import (
    classify_identity_value_shape,
    is_demo_identity_value,
)

SCHEMA_VERSION = "nf_customer_auth_principal_contract_v1"

AUTH_SOURCES = frozenset(
    {
        "demo_fixture",
        "cloudflare_access",
        "oidc",
        "auth0",
        "local_dev",
        "unknown",
    }
)

# Sources that can, in principle, establish a production-authenticated person.
# Cloudflare Access is deliberately absent: it is edge access, not app auth.
PRODUCTION_CAPABLE_SOURCES = frozenset({"oidc", "auth0"})

AUTH_STATUSES = frozenset(
    {
        "unauthenticated",
        "authenticated_demo",
        "authenticated_unverified_org",
        "authenticated_verified_org",
        "expired",
        "revoked",
        "unknown",
    }
)

# The only status under which production operational work may proceed.
OPERATIONAL_AUTH_STATUSES = frozenset({"authenticated_verified_org"})

# Statuses where the principal is not usable at all.
DEAD_AUTH_STATUSES = frozenset({"unauthenticated", "expired", "revoked", "unknown"})

ROLES = frozenset(
    {
        "platform_admin",
        "tenant_admin",
        "grants_manager",
        "grants_viewer",
        "auditor",
        "unknown",
    }
)

# Gate 111's roles mapped onto the vocabularies that already exist. Imported and
# checked, so a role added to either source stops this being complete and a test
# says so. Nothing is renamed and nothing is forked.
RBAC_ROLE_TO_PRINCIPAL_ROLE: dict[str, str] = {
    "operator_admin": "platform_admin",
    "operator_reviewer": "auditor",
    "tribal_admin": "tenant_admin",
    "grant_manager": "grants_manager",
    "authorized_signer": "tenant_admin",
    "draft_contributor": "grants_manager",
    "viewer": "grants_viewer",
    "unknown": "unknown",
}

ORG_ROLE_TO_PRINCIPAL_ROLE: dict[str, str] = {
    "org_owner": "tenant_admin",
    "org_admin": "tenant_admin",
    "authorized_representative": "tenant_admin",
    "grant_lead": "grants_manager",
    "reviewer": "auditor",
    "viewer": "grants_viewer",
}

PERMISSIONS = frozenset(
    {
        "verify_binding",
        "inspect_binding",
        "read_operational",
        "write_operational",
        "read_demo",
        "write_demo",
    }
)

# Which permissions each role carries, before any auth status is considered.
ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "platform_admin": frozenset(
        {
            "verify_binding",
            "inspect_binding",
            "read_operational",
            "write_operational",
            "read_demo",
            "write_demo",
        }
    ),
    "tenant_admin": frozenset(
        {
            "verify_binding",
            "inspect_binding",
            "read_operational",
            "write_operational",
            "read_demo",
            "write_demo",
        }
    ),
    "grants_manager": frozenset(
        {"inspect_binding", "read_operational", "write_operational", "read_demo"}
    ),
    "grants_viewer": frozenset({"read_operational", "read_demo"}),
    "auditor": frozenset({"inspect_binding", "read_operational", "read_demo"}),
    "unknown": frozenset(),
}

PRINCIPAL_FIELDS: tuple[str, ...] = (
    "principal_id",
    "subject",
    "email",
    "display_name",
    "auth_source",
    "auth_status",
    "organization_id",
    "organization_membership_status",
    "roles",
    "permissions",
    "claims_verified",
    "org_claim_verified",
    "rls_context_allowed",
    "human_review_required",
    "blocked_reasons",
)

MEMBERSHIP_STATUSES = frozenset(
    {"verified_member", "claimed_unverified", "not_a_member", "unknown"}
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    if value is None:
        return fallback
    text = str(value).strip()
    return text if text in vocabulary else fallback


def build_principal_id(*, auth_source: Any, subject: Any) -> str:
    """Deterministic, and scoped to the source that issued the subject."""
    return hashlib.sha256(
        f"{auth_source}|{subject}".encode()
    ).hexdigest()


def role_mappings_are_complete() -> bool:
    """Every existing role has a mapping here. Detected, not assumed."""
    from nativeforge.services.org_tenant_seat_model_service import ORG_ROLES
    from nativeforge.services.rbac_policy_contract_service import ROLES as RBAC_ROLES

    return set(RBAC_ROLES) == set(RBAC_ROLE_TO_PRINCIPAL_ROLE) and set(
        ORG_ROLES
    ) == set(ORG_ROLE_TO_PRINCIPAL_ROLE)


def build_principal(
    *,
    subject: Any = None,
    auth_source: Any = None,
    email: Any = None,
    display_name: Any = None,
    organization_id: Any = None,
    roles: list[str] | None = None,
    claims_verified: bool = False,
    org_claim_verified: bool = False,
    # Gate 112. Verified-org auth establishes *which* organization was asserted
    # and checked. It does not establish that this person belongs to it - that
    # comes from nf_org_memberships and is a separate fact from a separate
    # source. Defaults False, so an RLS context is never granted on an
    # organization claim alone.
    membership_verified: bool = False,
    session_expired: bool = False,
    revoked: bool = False,
    demo_label: Any = None,
) -> dict[str, Any]:
    """One acting principal. Nothing about their authority is inferred."""
    source = _norm(auth_source, AUTH_SOURCES, fallback="unknown")
    supplied_roles = [
        _norm(role, ROLES, fallback="unknown") for role in (roles or [])
    ] or ["unknown"]

    blocked_reasons: list[str] = []

    has_subject = bool(str(subject or "").strip())
    if not has_subject:
        blocked_reasons.append("principal_without_a_subject")
    if source == "unknown":
        blocked_reasons.append("auth_source_unknown")

    org_shape = classify_identity_value_shape(organization_id)
    org_is_demo = is_demo_identity_value(organization_id)
    is_demo_source = source == "demo_fixture"

    if is_demo_source and str(demo_label or "").strip() != "demo_fixture":
        blocked_reasons.append("demo_principal_without_its_label")

    # Edge access is not application auth.
    if source == "cloudflare_access":
        blocked_reasons.append("cloudflare_access_is_edge_access_not_app_auth")

    # An org claim is only verified if somebody established a real
    # organization_id behind it. The OIDC path today produces an
    # organization_profile_id instead, which is why this is a separate fact.
    org_verified = bool(
        org_claim_verified
        and org_shape == "uuid"
        and not org_is_demo
        and has_subject
    )
    if org_claim_verified and not org_verified:
        if org_shape != "uuid":
            blocked_reasons.append(
                f"org_claim_is_not_a_uuid_organization_id:{org_shape}"
            )
        if org_is_demo:
            blocked_reasons.append("org_claim_is_a_demo_identity")

    # Status is derived. A caller supplies facts; the record decides.
    if revoked:
        status = "revoked"
    elif session_expired:
        status = "expired"
    elif not has_subject:
        status = "unauthenticated"
    elif is_demo_source:
        status = "authenticated_demo"
    elif not claims_verified:
        status = "unauthenticated"
        blocked_reasons.append("claims_not_verified_by_a_provider")
    elif source not in PRODUCTION_CAPABLE_SOURCES:
        status = "authenticated_unverified_org"
    elif org_verified:
        status = "authenticated_verified_org"
    else:
        status = "authenticated_unverified_org"

    if status == "authenticated_unverified_org" and not blocked_reasons:
        blocked_reasons.append("organization_membership_not_verified")

    membership_status = (
        "verified_member"
        if status == "authenticated_verified_org"
        else "claimed_unverified"
        if organization_id
        else "unknown"
    )

    # Permissions are the union of the roles' grants, then cut down by status.
    granted: set[str] = set()
    for role in supplied_roles:
        granted |= ROLE_PERMISSIONS.get(role, frozenset())
    if status in DEAD_AUTH_STATUSES:
        granted = set()
    elif status == "authenticated_demo":
        granted = {p for p in granted if p.endswith("_demo")} | (
            {"inspect_binding"} if "inspect_binding" in granted else set()
        )
    elif status == "authenticated_unverified_org":
        # Nothing operational until somebody establishes the organization.
        granted = {p for p in granted if not p.endswith("_operational")}
        granted.discard("verify_binding")

    rls_context_allowed = bool(
        status in OPERATIONAL_AUTH_STATUSES
        and org_shape == "uuid"
        and not org_is_demo
        and membership_verified
    )
    if status in OPERATIONAL_AUTH_STATUSES and not membership_verified:
        blocked_reasons.append("organization_membership_not_verified_for_rls")

    human_review_required = bool(
        blocked_reasons or status in {"expired", "revoked", "unknown"}
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "principal_id": build_principal_id(auth_source=source, subject=subject),
            "subject": subject,
            "email": email,
            "display_name": display_name,
            "auth_source": source,
            "auth_status": status,
            "organization_id": organization_id,
            "organization_id_shape": org_shape,
            "organization_membership_status": membership_status,
            "roles": sorted(set(supplied_roles)),
            "permissions": sorted(granted),
            "claims_verified": bool(claims_verified),
            "org_claim_verified": org_verified,
            "membership_verified": bool(membership_verified),
            "rls_context_allowed": rls_context_allowed,
            "is_demo_principal": status == "authenticated_demo",
            # A demo principal is never production authentication.
            "is_production_authenticated": status == "authenticated_verified_org",
            "demo_label": demo_label if is_demo_source else None,
            "human_review_required": human_review_required,
            "blocked_reasons": sorted(set(blocked_reasons)),
            # Constants: this describes a principal, it does not log anyone in.
            "customer_auth_live": False,
            "login_live": False,
            "session_created": False,
            "identity_provider_contacted": False,
            "fabricated": False,
            "persisted": False,
        }
    )


def principal_invariant_failures(principal: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if principal.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for field in PRINCIPAL_FIELDS:
        if field not in principal:
            fails.append(f"principal_missing_field:{field}")

    for constant in (
        "customer_auth_live",
        "login_live",
        "session_created",
        "identity_provider_contacted",
        "fabricated",
        "persisted",
    ):
        if principal.get(constant) is not False:
            fails.append(f"principal_claimed:{constant}")

    status = principal.get("auth_status")
    source = principal.get("auth_source")

    if status not in AUTH_STATUSES:
        fails.append("auth_status_out_of_vocabulary")
    if source not in AUTH_SOURCES:
        fails.append("auth_source_out_of_vocabulary")
    if principal.get("organization_membership_status") not in MEMBERSHIP_STATUSES:
        fails.append("membership_status_out_of_vocabulary")
    for role in principal.get("roles") or []:
        if role not in ROLES:
            fails.append(f"role_out_of_vocabulary:{role}")
    for permission in principal.get("permissions") or []:
        if permission not in PERMISSIONS:
            fails.append(f"permission_out_of_vocabulary:{permission}")

    # A demo principal is never production authentication.
    if status == "authenticated_demo":
        if principal.get("is_production_authenticated"):
            fails.append("demo_principal_claimed_production_authentication")
        if principal.get("rls_context_allowed"):
            fails.append("demo_principal_permitted_rls_context")
        if principal.get("demo_label") != "demo_fixture":
            fails.append("demo_principal_without_its_label")

    # Cloudflare Access alone never reaches verified-org.
    if source == "cloudflare_access" and status == "authenticated_verified_org":
        fails.append("edge_access_treated_as_verified_org_auth")

    # Verified-org requires both a verified claim and a UUID organization_id.
    if status == "authenticated_verified_org":
        if not principal.get("org_claim_verified"):
            fails.append("verified_org_status_without_a_verified_org_claim")
        if principal.get("organization_id_shape") != "uuid":
            fails.append("verified_org_status_without_a_uuid_organization_id")

    # RLS context needs verified-org auth, a UUID, and verified membership.
    if principal.get("rls_context_allowed"):
        if status not in OPERATIONAL_AUTH_STATUSES:
            fails.append("rls_context_permitted_without_verified_org_auth")
        if principal.get("organization_id_shape") != "uuid":
            fails.append("rls_context_permitted_for_a_non_uuid_organization_id")
        # Gate 112: an organization claim says which organization was asserted.
        # Membership says they belong to it. Both, or no context.
        if not principal.get("membership_verified"):
            fails.append("rls_context_permitted_without_verified_membership")

    # A dead principal carries nothing.
    if status in DEAD_AUTH_STATUSES and principal.get("permissions"):
        fails.append(f"inactive_principal_retained_permissions:{status}")

    # Unverified org means no operational permission and no binding verification.
    if status == "authenticated_unverified_org":
        for permission in principal.get("permissions") or []:
            if permission.endswith("_operational") or permission == "verify_binding":
                fails.append(f"unverified_org_principal_granted:{permission}")

    # is_production_authenticated must agree with the status.
    if principal.get("is_production_authenticated") is not (
        status == "authenticated_verified_org"
    ):
        fails.append("production_authentication_disagrees_with_the_status")

    # A refusal must name itself.
    if status in {"unauthenticated", "authenticated_unverified_org"} and not (
        principal.get("blocked_reasons")
    ):
        fails.append("principal_refusal_without_a_reason")

    # Identity reproducible from the record's own fields.
    expected_id = build_principal_id(
        auth_source=principal.get("auth_source"), subject=principal.get("subject")
    )
    if principal.get("principal_id") != expected_id:
        fails.append("principal_id_not_derivable_from_its_fields")

    return fails
