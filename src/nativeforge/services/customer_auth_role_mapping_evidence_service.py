"""Gate 133C: role mapping, measured from the rows that already prove it.

## Why this needs no new table

Gate 133B had to build storage because the JWKS validation result was a local
that stopped existing when the request ended. Role mapping is different: its
evidence is a **membership row**, and a row is the thing itself rather than a
report about an event. It survives because it is not a memory of anything.

So `role_mapping_passed` was false for the same reason `org_binding_passed` was
false before Gate 132 - a parameter of `run_auth0_live_validation` that no
caller ever passed - and the fix is a query, not a migration.

## What "mapped" has to mean

```text
role comes from       nf_org_memberships.role
role_source           'membership_record', and only that
membership_source     verified_directory | operator_approved | org_owner_approved
organization_id       nf_org_memberships.organization_id
```

And what it must never mean:

```text
a cookie's org claim      Gate 132's cross-tenant fix. The cookie says which
                         organization it thinks it is for; the membership says
                         which one the holder belongs to. When they disagree the
                         membership wins and the request gets nothing.
an email domain          Gate 112. gmail.com is not a Tribe.
a token claim            'token_claim' is in the role-source vocabulary and is
                         not in the trusted subset. An IdP group claim is the
                         provider's opinion, not this product's record.
a header                 the dev header selects an organization and authenticates
                         nobody.
a caller argument        there is no role parameter on anything here.
```

## The cookie-override check is a real test, not a restatement

`cookie_claim_can_override_membership` is derived by actually comparing a
claimed organization against the resolved one and reporting whether the resolver
let the claim through. It is false because Gate 132's fix makes it false - and
if somebody reintroduces that defect this function reports `True` and the
invariant fires, rather than a docstring continuing to say it cannot happen.
"""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa

from nativeforge.services.dev_org_membership_bootstrap_service import (
    MEMBERSHIPS,
    STORABLE_ROLES,
)
from nativeforge.services.membership_directory_service import (
    ACTING_STATES,
    TRUSTED_MEMBERSHIP_SOURCES,
    TRUSTED_ROLE_SOURCES,
)

SCHEMA_VERSION = "nf_customer_auth_role_mapping_evidence_v1"

MEMBERSHIP_TABLE = "nf_org_memberships"

#: The only place a role may come from.
ROLE_MAPPING_SOURCE = "nf_org_memberships"

#: Sources that are real values in this codebase and grant nothing. Named so a
#: test can assert each is refused rather than merely absent.
UNTRUSTED_ROLE_SOURCES: tuple[str, ...] = (
    "token_claim",
    "client_header",
    "email_domain",
    "none",
    "unknown",
)

RESULT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "connection_supplied",
    "role_mapping_source",
    "mapped_identities",
    "mapped_organizations",
    "roles_observed",
    "membership_sources_observed",
    "role_sources_observed",
    "role_mapping_passed",
    "cookie_claim_can_override_membership",
    "email_domain_can_map_a_role",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


#: Parameter names a claim could arrive under. If the resolver ever accepts one,
#: a cookie's organization becomes an input to the answer instead of a value
#: checked against it.
CLAIM_PARAMETER_NAMES: tuple[str, ...] = (
    "organization_id",
    "org_claim",
    "claimed_organization_id",
    "claimed_org",
    "cookie_organization_id",
)


def _cookie_claim_can_override(
    connection: Any, identity_id: Any, resolved: str
) -> bool:
    """Can a claimed organization displace the resolved one? Try it and see.

    Two checks, because either alone would be weak. The resolver's signature is
    inspected for any parameter a claim could arrive under, and then a claim is
    actually offered: a resolver that refuses it raises `TypeError`, which is
    the answer. A resolver that accepts it and returns the claimed organization
    is Gate 132's cross-tenant defect, reintroduced.
    """
    import inspect

    from nativeforge.services.identity_org_session_resolution_service import (
        resolve_session_organization,
    )

    parameters = set(inspect.signature(resolve_session_organization).parameters)
    if set(CLAIM_PARAMETER_NAMES) & parameters:
        return True

    other = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    if other == resolved:  # pragma: no cover - the demo org is never this one
        other = "cccccccc-dddd-eeee-ffff-000000000000"
    try:
        forced = resolve_session_organization(
            connection=connection,
            identity_id=identity_id,
            organization_id=other,
        )
    except TypeError:
        return False
    return bool(forced.get("organization_id") == other)


def build_role_mapping_evidence(*, connection: Any = None) -> dict[str, Any]:
    """Is an authenticated identity mapped to roles from membership rows?"""
    from nativeforge.services.identity_org_session_resolution_service import (
        resolve_session_organization,
    )

    if connection is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "connection_supplied": False,
                "role_mapping_source": ROLE_MAPPING_SOURCE,
                "mapped_identities": 0,
                "mapped_organizations": [],
                "roles_observed": [],
                "membership_sources_observed": [],
                "role_sources_observed": [],
                "role_mapping_passed": False,
                "cookie_claim_can_override_membership": False,
                "email_domain_can_map_a_role": False,
                "blocked_reasons": ["no_connection_supplied"],
            }
        )

    blocked_reasons: list[str] = []
    mapped = 0
    organizations: list[str] = []
    roles: list[str] = []
    membership_sources: list[str] = []
    role_sources: list[str] = []
    override_possible = False

    try:
        rows = (
            connection.execute(
                sa.select(
                    MEMBERSHIPS.c.identity_id,
                    MEMBERSHIPS.c.organization_id,
                    MEMBERSHIPS.c.role,
                    MEMBERSHIPS.c.role_source,
                    MEMBERSHIPS.c.membership_source,
                ).where(
                    MEMBERSHIPS.c.state.in_(sorted(ACTING_STATES)),
                    MEMBERSHIPS.c.revoked_at.is_(None),
                )
            )
            .mappings()
            .all()
        )
    except Exception:
        blocked_reasons.append("membership_table_unreadable")
        rows = []

    for row in rows:
        role = str(row["role"] or "").strip().lower()
        role_source = str(row["role_source"] or "").strip().lower()
        membership_source = str(row["membership_source"] or "").strip().lower()

        resolution = resolve_session_organization(
            connection=connection, identity_id=row["identity_id"]
        )
        if not resolution["organization_id_resolved"]:
            # A membership row that does not resolve is not a mapping. Say why,
            # from the row, rather than reporting only that nothing mapped.
            #
            # The resolver already refuses an untrusted role_source or
            # membership_source - it filters on both before counting a
            # membership as active. A first version of this loop re-checked them
            # *after* asking the resolver, which made both checks unreachable:
            # the resolver had already dropped the row, so the loop `continue`d
            # one branch earlier and the named refusals could never fire. A
            # guard that cannot fire reads as coverage and is worse than none
            # (Gate 126). So they are reported here as observations about the
            # row, and the refusal itself stays in the resolver where it belongs.
            if role_source not in TRUSTED_ROLE_SOURCES:
                blocked_reasons.append(f"role_source_not_trusted:{role_source}")
            elif membership_source not in TRUSTED_MEMBERSHIP_SOURCES:
                blocked_reasons.append(
                    f"membership_source_not_trusted:{membership_source}"
                )
            else:
                blocked_reasons.extend(
                    f"membership_did_not_resolve:{reason}"
                    for reason in resolution["blocked_reasons"]
                )
            continue

        if role and role not in STORABLE_ROLES:
            blocked_reasons.append(f"role_not_recognised:{role}")
            continue
        if not role:
            # A membership with no role maps nobody to anything. It is a
            # membership, not a mapping.
            blocked_reasons.append("active_membership_carries_no_role")
            continue

        mapped += 1
        for value, bucket in (
            (resolution["organization_id"], organizations),
            (role, roles),
            (membership_source, membership_sources),
            (role_source, role_sources),
        ):
            if value and value not in bucket:
                bucket.append(value)

        if _cookie_claim_can_override(
            connection, row["identity_id"], resolution["organization_id"]
        ):
            override_possible = True
            blocked_reasons.append("a_cookie_claim_could_displace_the_membership")

    if not mapped:
        blocked_reasons.append("no_active_membership_maps_an_identity_to_a_role")

    # Derived affirmatively. Every conjunct.
    passed = bool(
        mapped
        and organizations
        and roles
        and role_sources
        and not override_possible
        and not blocked_reasons
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "connection_supplied": True,
            "role_mapping_source": ROLE_MAPPING_SOURCE,
            "mapped_identities": mapped,
            "mapped_organizations": sorted(organizations),
            "roles_observed": sorted(roles),
            "membership_sources_observed": sorted(membership_sources),
            "role_sources_observed": sorted(role_sources),
            "role_mapping_passed": passed,
            "cookie_claim_can_override_membership": override_possible,
            # There is no code path from an email domain to a role. Reported as
            # a constant because the absence is structural: the resolver takes
            # no email, and a test asserts its signature.
            "email_domain_can_map_a_role": False,
            "blocked_reasons": sorted(set(blocked_reasons)),
        }
    )


def role_mapping_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("role_mapping_passed"):
        if not result.get("connection_supplied"):
            fails.append("role_mapping_passed_without_reading_anything")
        if not result.get("mapped_identities"):
            fails.append("role_mapping_passed_without_a_mapped_identity")
        if not result.get("roles_observed"):
            fails.append("role_mapping_passed_without_a_role")
        if not result.get("mapped_organizations"):
            fails.append("role_mapping_passed_without_an_organization")
        if result.get("blocked_reasons"):
            fails.append("role_mapping_passed_alongside_blockers")
        if result.get("cookie_claim_can_override_membership"):
            fails.append("role_mapping_passed_while_a_cookie_claim_could_override")
        if result.get("email_domain_can_map_a_role"):
            fails.append("role_mapping_passed_while_an_email_domain_could_map")

    if result.get("role_mapping_source") != ROLE_MAPPING_SOURCE:
        fails.append("role_mapping_source_is_not_the_membership_table")

    for source in result.get("role_sources_observed") or []:
        if source not in TRUSTED_ROLE_SOURCES:
            fails.append(f"untrusted_role_source_observed:{source}")
    for source in result.get("membership_sources_observed") or []:
        if source not in TRUSTED_MEMBERSHIP_SOURCES:
            fails.append(f"untrusted_membership_source_observed:{source}")

    return fails
