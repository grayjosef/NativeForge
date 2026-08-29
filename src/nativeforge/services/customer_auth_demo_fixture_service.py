"""Customer auth demo principals (Gate 111F).

Nine labelled principals, one per state the binder authorization has to handle.

## Every case is a refusal except two

```text
unauthenticated              nobody is acting
demo_platform_admin          demo surfaces only
demo_tenant_admin            demo surfaces only
demo_grants_manager          demo surfaces only
verified_org_tenant_admin    the one that may verify a production binding
unverified_org_tenant_admin  authenticated, organization not established
grants_viewer                may read, may not verify
auditor                      may inspect, may not verify
revoked                      was a principal, is not now
```

The pair worth looking at together is `verified_org_tenant_admin` and
`unverified_org_tenant_admin`. Same person, same role, same provider - and one
may verify a binding while the other may not. The difference is whether anybody
established which organization they act for, which is the distinction Gate 111A
found the real claim path does not currently make.

## The verified-org fixture is a fixture

`verified_org_tenant_admin` carries `authenticated_verified_org`, which is what
lets the binder authorization demonstrate a permitted verification. It is still
labelled `demo_fixture` and it never claims customer auth is live.

That combination is deliberate and slightly uncomfortable, so it is stated
plainly: the fixture shows what a verified principal *would* be allowed to do.
It is not evidence that any such principal exists. `customer_auth_live` is False
on the fixture set, on every principal, and in the artifact.

## No real users, no sessions, no provider

Every subject is invented and prefixed `nf-demo-`. Nothing here creates a
session, contacts an identity provider, or stores a credential.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.customer_auth_principal_contract_service import (
    build_principal,
)

SCHEMA_VERSION = "nf_customer_auth_demo_fixture_v1"

FIXTURE_LABEL = "demo_fixture"

# A UUID that is not demo-prefixed, so the verified-org fixture can demonstrate
# a real RLS-eligible shape. It corresponds to no organization anywhere.
DEMO_ORGANIZATION_ID = "00000000-0000-4000-8000-000000000111"

# Cases the fixture set must demonstrate. Asserted by test.
REQUIRED_PRINCIPAL_CASES: frozenset[str] = frozenset(
    {
        "unauthenticated",
        "demo_platform_admin",
        "demo_tenant_admin",
        "demo_grants_manager",
        "verified_org_tenant_admin",
        "unverified_org_tenant_admin",
        "grants_viewer",
        "auditor",
        "revoked",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _demo(case: str, **kwargs: Any) -> dict[str, Any]:
    return {
        **build_principal(**kwargs),
        "fixture_label": FIXTURE_LABEL,
        "case": case,
    }


def build_demo_principals() -> list[dict[str, Any]]:
    """One principal per state the binder authorization has to handle."""
    return [
        _demo("unauthenticated"),
        _demo(
            "demo_platform_admin",
            subject="nf-demo-subject-01",
            auth_source="demo_fixture",
            email="demo-platform-admin@example.invalid",
            display_name="Demo Platform Admin",
            roles=["platform_admin"],
            demo_label=FIXTURE_LABEL,
        ),
        _demo(
            "demo_tenant_admin",
            subject="nf-demo-subject-02",
            auth_source="demo_fixture",
            email="demo-tenant-admin@example.invalid",
            display_name="Demo Tenant Admin",
            roles=["tenant_admin"],
            demo_label=FIXTURE_LABEL,
        ),
        _demo(
            "demo_grants_manager",
            subject="nf-demo-subject-03",
            auth_source="demo_fixture",
            email="demo-grants-manager@example.invalid",
            display_name="Demo Grants Manager",
            roles=["grants_manager"],
            demo_label=FIXTURE_LABEL,
        ),
        # The one principal that may verify a production binding.
        _demo(
            "verified_org_tenant_admin",
            subject="nf-demo-subject-04",
            auth_source="oidc",
            email="demo-verified-admin@example.invalid",
            display_name="Demo Verified Tenant Admin",
            organization_id=DEMO_ORGANIZATION_ID,
            roles=["tenant_admin"],
            claims_verified=True,
            org_claim_verified=True,
        ),
        # Same person, same role, organization never established.
        _demo(
            "unverified_org_tenant_admin",
            subject="nf-demo-subject-05",
            auth_source="oidc",
            email="demo-unverified-admin@example.invalid",
            display_name="Demo Unverified Tenant Admin",
            roles=["tenant_admin"],
            claims_verified=True,
        ),
        _demo(
            "grants_viewer",
            subject="nf-demo-subject-06",
            auth_source="oidc",
            email="demo-viewer@example.invalid",
            display_name="Demo Grants Viewer",
            organization_id=DEMO_ORGANIZATION_ID,
            roles=["grants_viewer"],
            claims_verified=True,
            org_claim_verified=True,
        ),
        _demo(
            "auditor",
            subject="nf-demo-subject-07",
            auth_source="oidc",
            email="demo-auditor@example.invalid",
            display_name="Demo Auditor",
            organization_id=DEMO_ORGANIZATION_ID,
            roles=["auditor"],
            claims_verified=True,
            org_claim_verified=True,
        ),
        _demo(
            "revoked",
            subject="nf-demo-subject-08",
            auth_source="oidc",
            email="demo-revoked@example.invalid",
            display_name="Demo Revoked Principal",
            organization_id=DEMO_ORGANIZATION_ID,
            roles=["platform_admin"],
            claims_verified=True,
            org_claim_verified=True,
            revoked=True,
        ),
    ]


def measure_principal_cases(principals: list[dict[str, Any]]) -> set[str]:
    """Which cases the supplied set demonstrates.

    Given its input so the measurement can be tested. The real fixture covers
    every case, so a function returning `REQUIRED_PRINCIPAL_CASES` would look
    correct; feeding it a short set is the only way to prove it counts.
    """
    return {str(p.get("case")) for p in principals if p.get("case")}


def build_demo_auth_fixture_set() -> dict[str, Any]:
    """Principals, the binder matrix over them, and the coverage it claims."""
    from nativeforge.services.rls_context_claim_guard_service import (
        build_claim_guard_matrix,
    )
    from nativeforge.services.verified_binder_authorization_service import (
        build_binder_authorization_matrix,
    )

    principals = build_demo_principals()
    covered = measure_principal_cases(principals)

    production_matrix = build_binder_authorization_matrix(principals=principals)
    demo_matrix = build_binder_authorization_matrix(
        principals=principals, target_binding_status="demo_fixture"
    )

    verified = next(
        p for p in principals if p["case"] == "verified_org_tenant_admin"
    )
    claim_matrix = build_claim_guard_matrix(principal=verified)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_label": FIXTURE_LABEL,
            "demo_organization_id": DEMO_ORGANIZATION_ID,
            "principals": principals,
            "principal_count": len(principals),
            "principal_cases_covered": sorted(covered),
            "principal_cases_missing": sorted(REQUIRED_PRINCIPAL_CASES - covered),
            "production_binder_matrix": production_matrix,
            "demo_binder_matrix": demo_matrix,
            "claim_guard_matrix": claim_matrix,
            # Constants: invented principals, no sessions, no provider.
            "customer_auth_live": False,
            "login_live": False,
            "real_user_data": False,
            "real_sessions_created": False,
            "identity_provider_contacted": False,
            "credentials_stored": False,
            "fabricated": False,
            "persisted": False,
        }
    )


def demo_auth_invariant_failures(fixture: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for constant in (
        "customer_auth_live",
        "login_live",
        "real_user_data",
        "real_sessions_created",
        "identity_provider_contacted",
        "credentials_stored",
        "fabricated",
        "persisted",
    ):
        if fixture.get(constant) is not False:
            fails.append(f"demo_auth_claimed:{constant}")

    if fixture.get("fixture_label") != FIXTURE_LABEL:
        fails.append("fixture_set_not_labelled")

    for principal in fixture.get("principals") or []:
        if principal.get("fixture_label") != FIXTURE_LABEL:
            fails.append(f"unlabelled_demo_principal:{principal.get('case')}")
        if principal.get("customer_auth_live"):
            fails.append(f"demo_principal_claimed_auth_live:{principal.get('case')}")

    for case in fixture.get("principal_cases_missing") or []:
        fails.append(f"principal_case_not_covered:{case}")

    # No demo-sourced principal is ever production authenticated.
    for principal in fixture.get("principals") or []:
        if principal.get("auth_source") == "demo_fixture" and principal.get(
            "is_production_authenticated"
        ):
            fails.append(
                f"demo_sourced_principal_claimed_production_auth:{principal.get('case')}"
            )

    # In the production binder matrix, no demo-sourced principal is authorized.
    production = fixture.get("production_binder_matrix") or {}
    for row in production.get("rows") or []:
        if row.get("is_demo_principal") and row.get("binding_authorized"):
            fails.append(
                f"demo_principal_authorized_against_production:{row.get('binding_operation')}"
            )

    # No claim in the guard matrix sets the context from an untrusted source.
    claims = fixture.get("claim_guard_matrix") or {}
    if claims.get("tenant_id_claims_permitted"):
        fails.append("tenant_id_claim_permitted_to_set_the_rls_context")
    if claims.get("current_org_id_set"):
        fails.append("demo_fixture_set_the_rls_context")

    return fails
