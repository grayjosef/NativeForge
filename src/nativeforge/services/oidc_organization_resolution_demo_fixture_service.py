"""OIDC organization resolution demo fixtures (Gate 112G).

Eight labelled claim cases, one per outcome the resolution contract must reach.

## Every case is a refusal except one

```text
verified_uuid_org_with_membership   the only path to an RLS context
verified_profile_only               what the current mapper actually produces
unverified_claims_uuid_org          a plausible org claim nobody vouched for
verified_invalid_uuid_org           an org claim that cannot survive ::uuid
verified_missing_membership         a real organization, no membership record
verified_conflicting_profile_org    profile and org claims disagree
demo_fixture_resolution             a demo path, never production
revoked_membership                  the relationship was withdrawn
```

The pair worth reading together is the first two. Same provider, same verified
claims — and one resolves to the `organization_id` RLS enforces on while the
other stops at a profile id. That is the exact distance Gate 111 found the real
claim path falls short by.

## The permitted case is a fixture, not evidence

`verified_uuid_org_with_membership` reaches `resolved_verified_organization_id`
so the matrix can demonstrate a permitted resolution. It is labelled
`demo_fixture` and reports `customer_auth_live: false`.

Stated plainly, as in Gate 111: it shows what a resolved principal *would* be
allowed to do. It is not evidence that any such principal exists, and no
provider was contacted to build it.

## No real users, no sessions, no secrets

Every subject, issuer and email is invented. The organization UUIDs correspond to
no organization anywhere.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.customer_org_membership_verification_service import (
    build_membership_matrix,
)
from nativeforge.services.oidc_organization_id_resolution_service import (
    build_resolution_matrix,
)

SCHEMA_VERSION = "nf_oidc_organization_resolution_demo_fixture_v1"

FIXTURE_LABEL = "demo_fixture"

DEMO_ISSUER = "https://demo-issuer.example.invalid/"
DEMO_AUDIENCE = "nf-demo-audience"

# UUIDs that correspond to no organization anywhere.
DEMO_ORGANIZATION_ID = "00000000-0000-4000-8000-000000000112"
OTHER_ORGANIZATION_ID = "00000000-0000-4000-8000-0000000001ff"
DEMO_PROFILE_ID = "nf-demo-org-profile-112"

REQUIRED_RESOLUTION_CASES: frozenset[str] = frozenset(
    {
        "verified_uuid_org_with_membership",
        "verified_profile_only",
        "unverified_claims_uuid_org",
        "verified_invalid_uuid_org",
        "verified_missing_membership",
        "verified_conflicting_profile_org",
        "demo_fixture_resolution",
        "revoked_membership",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _active_membership(organization_id: str, role: str = "org_admin"):
    return [
        {
            "organization_id": organization_id,
            "identity_id": "nf-demo-identity-01",
            "state": "active",
            "role": role,
            "membership_source": "nf_org_memberships",
        }
    ]


def build_demo_resolution_cases() -> list[dict[str, Any]]:
    """One claim case per resolution outcome, each carrying its label."""
    base = {
        "issuer": DEMO_ISSUER,
        "audience": DEMO_AUDIENCE,
        "auth_source": "oidc",
        "organization_claim_name": "https://nativeforge.example/org",
    }
    return [
        {
            "case": "verified_uuid_org_with_membership",
            "fixture_label": FIXTURE_LABEL,
            "claim": {
                **base,
                "subject": "nf-demo-subject-101",
                "email": "demo-101@example.invalid",
                "claims_verified": True,
                "organization_claim_value": DEMO_ORGANIZATION_ID,
                "membership_records": _active_membership(DEMO_ORGANIZATION_ID),
            },
        },
        {
            "case": "verified_profile_only",
            "fixture_label": FIXTURE_LABEL,
            "claim": {
                **base,
                "subject": "nf-demo-subject-102",
                "email": "demo-102@example.invalid",
                "claims_verified": True,
                "organization_profile_id": DEMO_PROFILE_ID,
            },
        },
        {
            "case": "unverified_claims_uuid_org",
            "fixture_label": FIXTURE_LABEL,
            "claim": {
                **base,
                "subject": "nf-demo-subject-103",
                "email": "demo-103@example.invalid",
                "claims_verified": False,
                "organization_claim_value": DEMO_ORGANIZATION_ID,
                "membership_records": _active_membership(DEMO_ORGANIZATION_ID),
            },
        },
        {
            "case": "verified_invalid_uuid_org",
            "fixture_label": FIXTURE_LABEL,
            "claim": {
                **base,
                "subject": "nf-demo-subject-104",
                "email": "demo-104@example.invalid",
                "claims_verified": True,
                "organization_claim_value": "not-a-uuid-at-all",
            },
        },
        {
            "case": "verified_missing_membership",
            "fixture_label": FIXTURE_LABEL,
            "claim": {
                **base,
                "subject": "nf-demo-subject-105",
                "email": "demo-105@example.invalid",
                "claims_verified": True,
                "organization_claim_value": DEMO_ORGANIZATION_ID,
                "membership_records": _active_membership(OTHER_ORGANIZATION_ID),
            },
        },
        {
            "case": "verified_conflicting_profile_org",
            "fixture_label": FIXTURE_LABEL,
            "claim": {
                **base,
                "subject": "nf-demo-subject-106",
                "email": "demo-106@example.invalid",
                "claims_verified": True,
                "organization_profile_id": DEMO_PROFILE_ID,
                "organization_claim_value": DEMO_PROFILE_ID,
            },
        },
        {
            "case": "demo_fixture_resolution",
            "fixture_label": FIXTURE_LABEL,
            "claim": {
                **base,
                "auth_source": "demo_fixture",
                "subject": "nf-demo-subject-107",
                "email": "demo-107@example.invalid",
                "claims_verified": True,
                "organization_claim_value": DEMO_ORGANIZATION_ID,
                "membership_records": _active_membership(DEMO_ORGANIZATION_ID),
            },
        },
        {
            "case": "revoked_membership",
            "fixture_label": FIXTURE_LABEL,
            "claim": {
                **base,
                "subject": "nf-demo-subject-108",
                "email": "demo-108@example.invalid",
                "claims_verified": True,
                "organization_claim_value": DEMO_ORGANIZATION_ID,
                "membership_records": [
                    {
                        "organization_id": DEMO_ORGANIZATION_ID,
                        "state": "active",
                        "role": "org_admin",
                        "revoked_at": "2026-01-15T00:00:00+00:00",
                    }
                ],
            },
        },
    ]


def build_demo_membership_cases() -> list[dict[str, Any]]:
    """The membership shapes the verification contract must handle."""
    return [
        {
            "principal_id": "nf-demo-principal-01",
            "organization_id": DEMO_ORGANIZATION_ID,
            "membership_source": "nf_org_memberships",
            "membership_records": _active_membership(
                DEMO_ORGANIZATION_ID, role="grant_lead"
            ),
        },
        {
            "principal_id": "nf-demo-principal-02",
            "organization_id": DEMO_ORGANIZATION_ID,
            "membership_source": "nf_org_memberships",
            "membership_records": _active_membership(DEMO_ORGANIZATION_ID),
        },
        {
            "principal_id": "nf-demo-principal-03",
            "organization_id": DEMO_ORGANIZATION_ID,
            "membership_source": "invite_approval",
            "membership_records": [
                {"organization_id": DEMO_ORGANIZATION_ID, "state": "pending"}
            ],
        },
        {
            "principal_id": "nf-demo-principal-04",
            "organization_id": DEMO_ORGANIZATION_ID,
            "membership_source": "nf_org_memberships",
            "membership_records": [],
        },
        {
            "principal_id": "nf-demo-principal-05",
            "organization_id": DEMO_ORGANIZATION_ID,
            "membership_source": "nf_org_memberships",
            "membership_records": [
                {
                    "organization_id": DEMO_ORGANIZATION_ID,
                    "state": "active",
                    "revoked_at": "2026-01-15T00:00:00+00:00",
                }
            ],
        },
        {
            "principal_id": "nf-demo-principal-06",
            "organization_id": "nf-demo-org-01",
            "membership_source": "demo_fixture",
            "membership_records": [],
        },
    ]


def measure_resolution_cases(cases: list[dict[str, Any]]) -> set[str]:
    """Which cases the supplied set demonstrates. Given its input so it can be
    tested against a set that is missing one."""
    return {str(c.get("case")) for c in cases if c.get("case")}


def build_resolution_demo_fixture_set() -> dict[str, Any]:
    """Claim cases, membership cases, and the matrices over both."""
    cases = build_demo_resolution_cases()
    membership_cases = build_demo_membership_cases()
    covered = measure_resolution_cases(cases)

    resolution_matrix = build_resolution_matrix(
        cases=[dict(c["claim"]) for c in cases]
    )
    membership_matrix = build_membership_matrix(cases=membership_cases)

    labelled_rows = [
        {**row, "case": case["case"], "fixture_label": FIXTURE_LABEL}
        for case, row in zip(cases, resolution_matrix["rows"], strict=True)
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "fixture_label": FIXTURE_LABEL,
            "demo_issuer": DEMO_ISSUER,
            "demo_organization_id": DEMO_ORGANIZATION_ID,
            "demo_profile_id": DEMO_PROFILE_ID,
            "cases": cases,
            "case_count": len(cases),
            "resolution_rows": labelled_rows,
            "resolution_matrix": resolution_matrix,
            "membership_matrix": membership_matrix,
            "resolution_cases_covered": sorted(covered),
            "resolution_cases_missing": sorted(REQUIRED_RESOLUTION_CASES - covered),
            # Constants: invented claims, no provider, no session, no secret.
            "customer_auth_live": False,
            "login_live": False,
            "real_user_data": False,
            "real_sessions_created": False,
            "identity_provider_contacted": False,
            "secrets_stored": False,
            "current_org_id_set": False,
            "fabricated": False,
            "persisted": False,
        }
    )


def resolution_demo_invariant_failures(fixture: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if fixture.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    for constant in (
        "customer_auth_live",
        "login_live",
        "real_user_data",
        "real_sessions_created",
        "identity_provider_contacted",
        "secrets_stored",
        "current_org_id_set",
        "fabricated",
        "persisted",
    ):
        if fixture.get(constant) is not False:
            fails.append(f"resolution_demo_claimed:{constant}")

    if fixture.get("fixture_label") != FIXTURE_LABEL:
        fails.append("fixture_set_not_labelled")

    for case in fixture.get("cases") or []:
        if case.get("fixture_label") != FIXTURE_LABEL:
            fails.append(f"unlabelled_demo_case:{case.get('case')}")

    for case in fixture.get("resolution_cases_missing") or []:
        fails.append(f"resolution_case_not_covered:{case}")

    # A profile-only case never resolves an organization id.
    for row in fixture.get("resolution_rows") or []:
        if row.get("case") == "verified_profile_only":
            if row.get("resolved_organization_id"):
                fails.append("profile_only_case_resolved_an_organization_id")
            if row.get("rls_context_allowed"):
                fails.append("profile_only_case_permitted_rls")
        if row.get("case") == "demo_fixture_resolution" and row.get(
            "rls_context_allowed"
        ):
            fails.append("demo_resolution_case_permitted_rls")

    # Exactly one case may reach an RLS context.
    permitted = [
        row for row in fixture.get("resolution_rows") or [] if row.get(
            "rls_context_allowed"
        )
    ]
    if len(permitted) > 1:
        fails.append(f"more_than_one_case_permitted_rls:{len(permitted)}")

    return fails
