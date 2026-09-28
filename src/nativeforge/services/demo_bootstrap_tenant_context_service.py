"""Open tenant context for one insert: the first membership of one demo org.

## The deadlock this exists to break

`nf_org_memberships` has `ENABLE` and `FORCE ROW LEVEL SECURITY` (migration
0027), and its policy's `WITH CHECK` requires
`app.current_org_id` and `app.current_org_is_demo` to match the row. The
application connects as `nf_app`, which is `rolsuper=false` and
`rolbypassrls=false` and is therefore subject to that policy.

During an OAuth callback for a brand-new organization there is no tenant
context, because establishing one is exactly what a membership would enable.
So the first membership can never be written, and the first person to sign in
can never get in.

There are three ways out and two of them are wrong:

```text
disable FORCE RLS            deletes the boundary for every tenant, forever
insert as the owner role     a second write path that RLS does not police
set the context, then insert the policy authorises it, on its own terms
```

This is the third. Nothing here bypasses RLS: it supplies the context the
policy asks for and lets the policy decide. `nf_app` stays non-superuser and
non-bypassing, the policy is unchanged, and an insert that does not satisfy it
still fails.

## Why this is a gate and not a setter

The dangerous version of this module is one that sets tenant context on
request. Then any caller that can name an organization can adopt it, and the
tenant boundary becomes a suggestion.

So `open_demo_bootstrap_context` refuses unless **every** one of these holds,
and it answers with reasons rather than raising:

```text
deployment named an org      NF_BOOTSTRAP_DEMO_ORG_ID is configured
it is THIS org               target == that configured id, exactly
the org exists               a row, not a hopeful uuid
the row says demo            org_type = 'demo', read from the database
nobody is in it yet          zero memberships - first one only, ever
the identity is verified     real OIDC verification completed
it is binding itself         the membership is for that same identity
```

`org_type` is read from the row and never inferred from the shape of the id.
The two real organizations fail the `demo` check on their own data, which is
the check that matters: a constant list of protected ids would be a second
source of truth, and the one that drifts.

The zero-membership rule is what makes this a *bootstrap* rather than an
escalation path. The moment the organization has one member, this door is
shut permanently, and every later membership goes through the ordinary
invite-and-approve flow.

## Transaction-local, always

`set_config(..., is_local => true)` ties the setting to the surrounding
transaction. It is gone at COMMIT or ROLLBACK, so the context cannot outlive
the insert it was opened for or leak into a later request on a pooled
connection. There is no non-local variant here and no parameter that asks for
one.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_demo_bootstrap_tenant_context_v1"

ORG_ID_KEY = "app.current_org_id"
IS_DEMO_KEY = "app.current_org_is_demo"

#: The only classification this path will ever open context for.
DEMO_ORG_TYPE = "demo"

#: How a read went, kept separate from what it found.
#:
#: `NOT_FOUND` and `ACCESS_DENIED` are different facts and collapsing them is
#: how a bootstrap that cannot SEE its organization reports that the
#: organization does not exist. Under RLS a refused read returns no rows
#: rather than an error, so "no rows" alone cannot tell them apart - the
#: distinction has to be made from something else, and here that is whether
#: the table is readable at all.
FOUND = "FOUND"
NOT_FOUND = "NOT_FOUND"
ACCESS_DENIED = "ACCESS_DENIED"
UNKNOWN = "UNKNOWN"

RESULT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "context_opened",
    "organization_id",
    "org_type",
    "org_lookup",
    "membership_count_lookup",
    "existing_membership_count",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _uuid_or_none(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except (ValueError, AttributeError, TypeError):
        return None


def _result(
    *,
    opened: bool,
    organization_id: Any = None,
    org_type: str | None = None,
    memberships: int | None = None,
    org_lookup: str = UNKNOWN,
    membership_count_lookup: str = UNKNOWN,
    blocked_reasons: list[str] | None = None,
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "context_opened": bool(opened),
            "organization_id": str(organization_id) if organization_id else None,
            "org_type": org_type,
            "org_lookup": org_lookup,
            "membership_count_lookup": membership_count_lookup,
            "existing_membership_count": memberships,
            "blocked_reasons": sorted(blocked_reasons or []),
        }
    )


def open_demo_org_lookup_context(
    *,
    connection: Any,
    organization_id: Any,
    identity_id: Any,
    membership_identity_id: Any,
    configured_organization_id: Any,
    identity_verified: bool,
) -> dict[str, Any]:
    """Set tenant context so an existing demo membership can be seen.

    FORCE RLS hides every membership while the no-tenant sentinel is the
    anchor. A returning demo member therefore looks like a stranger; the
    callback tries to bootstrap a first membership and is then refused
    because one already exists. Controlled-live produced exactly:

        existing_membership_count_zero: true
        insert_blocked_reasons: [self_approval_permitted_only_for_the_first_membership]

    The count was zero because it was taken under the sentinel, not because
    the organization was empty.

    This door still only opens for the configured demo org and a verified
    identity binding itself. It does not insert and it does not mint a
    session. It makes the row visible so the callback can resolve it.
    """
    return _open_demo_org_context(
        connection=connection,
        organization_id=organization_id,
        identity_id=identity_id,
        membership_identity_id=membership_identity_id,
        configured_organization_id=configured_organization_id,
        identity_verified=identity_verified,
        require_empty_membership=False,
    )


def open_demo_bootstrap_context(
    *,
    connection: Any,
    organization_id: Any,
    identity_id: Any,
    membership_identity_id: Any,
    configured_organization_id: Any,
    identity_verified: bool,
) -> dict[str, Any]:
    """Set transaction-local tenant context, or refuse and say why.

    Returns a decision either way. A caller that ignores the decision and
    inserts anyway gets the same refusal from the policy it would have got
    before, which is the point: this never becomes the thing that authorises
    the write.
    """
    return _open_demo_org_context(
        connection=connection,
        organization_id=organization_id,
        identity_id=identity_id,
        membership_identity_id=membership_identity_id,
        configured_organization_id=configured_organization_id,
        identity_verified=identity_verified,
        require_empty_membership=True,
    )


def _open_demo_org_context(
    *,
    connection: Any,
    organization_id: Any,
    identity_id: Any,
    membership_identity_id: Any,
    configured_organization_id: Any,
    identity_verified: bool,
    require_empty_membership: bool,
) -> dict[str, Any]:
    blocked: list[str] = []

    configured = _uuid_or_none(configured_organization_id)
    target = _uuid_or_none(organization_id)
    ident = _uuid_or_none(identity_id)
    member_ident = _uuid_or_none(membership_identity_id)

    if (
        configured_organization_id is None
        or not str(configured_organization_id).strip()
    ):
        # The deployment never named an organization, so there is no bootstrap
        # to authorise. This is the default state and it is not an error.
        blocked.append("no_bootstrap_organization_configured")
    elif configured is None:
        blocked.append("configured_bootstrap_organization_is_not_uuid_shaped")

    if target is None:
        blocked.append("target_organization_is_not_uuid_shaped")
    elif configured is not None and target != configured:
        # Named one organization, asked for another.
        blocked.append("target_organization_is_not_the_configured_bootstrap_org")

    if not identity_verified:
        blocked.append("identity_not_verified_by_the_provider")
    if ident is None:
        blocked.append("identity_is_not_uuid_shaped")
    if member_ident is None:
        blocked.append("membership_identity_is_not_uuid_shaped")
    elif ident is not None and member_ident != ident:
        # Bootstrapping somebody else into an organization is not a bootstrap.
        blocked.append("membership_identity_is_not_the_verified_identity")

    if connection is None:
        blocked.append("no_connection_supplied")

    if blocked:
        return _result(opened=False, organization_id=target, blocked_reasons=blocked)

    # -- the database's own account of this organization --------------------
    #
    # Each read reports HOW it went as well as what it saw, because under RLS
    # a refusal and an absence look identical from the row count.
    org_type: str | None = None
    memberships: int | None = None
    org_lookup = UNKNOWN
    membership_count_lookup = UNKNOWN

    try:
        row = connection.execute(
            sa.text("SELECT org_type FROM organizations WHERE id = :i"),
            {"i": str(target)},
        ).first()
        if row is None:
            # The query ran. Whether the row is absent or merely invisible is
            # settled below by asking whether the table is readable at all.
            probe = connection.execute(
                sa.text("SELECT count(*) FROM organizations")
            ).scalar_one()
            org_lookup = NOT_FOUND if int(probe) else ACCESS_DENIED
        else:
            org_type = str(row[0])
            org_lookup = FOUND
    except Exception as exc:  # noqa: BLE001 - a read that errors is a refusal
        return _result(
            opened=False,
            organization_id=target,
            org_lookup=ACCESS_DENIED,
            blocked_reasons=[f"organization_lookup_failed:{type(exc).__name__}"],
        )

    try:
        memberships = int(
            connection.execute(
                sa.text(
                    "SELECT count(*) FROM nf_org_memberships WHERE organization_id = :i"
                ),
                {"i": str(target)},
            ).scalar_one()
        )
        membership_count_lookup = FOUND
    except Exception as exc:  # noqa: BLE001
        # A count this cannot read is not a count of zero. Saying so is the
        # whole reason these two fields exist.
        return _result(
            opened=False,
            organization_id=target,
            org_type=org_type,
            org_lookup=org_lookup,
            membership_count_lookup=ACCESS_DENIED,
            blocked_reasons=[f"membership_count_unreadable:{type(exc).__name__}"],
        )

    if org_type is None:
        blocked.append(f"organization_not_readable:{org_lookup}")
    elif org_type != DEMO_ORG_TYPE:
        # Read from the row, never inferred from the id. The real
        # organizations fail here on their own data.
        blocked.append(f"organization_is_not_demo_classified:{org_type}")

    if require_empty_membership and memberships:
        # The insert door closes after the first member, permanently.
        # Lookup still opens: a returning member has to be able to see
        # their own row, and that is not an insert.
        blocked.append(f"organization_already_has_memberships:{memberships}")

    if blocked:
        return _result(
            opened=False,
            organization_id=target,
            org_type=org_type,
            memberships=memberships,
            org_lookup=org_lookup,
            membership_count_lookup=membership_count_lookup,
            blocked_reasons=blocked,
        )

    # -- transaction-local, and there is no other kind here -----------------
    connection.execute(
        sa.text("SELECT set_config(:k, :v, true)"),
        {"k": ORG_ID_KEY, "v": str(target)},
    )
    connection.execute(
        sa.text("SELECT set_config(:k, :v, true)"),
        {"k": IS_DEMO_KEY, "v": "true"},
    )

    return _result(
        opened=True,
        organization_id=target,
        org_type=org_type,
        memberships=memberships,
        org_lookup=org_lookup,
        membership_count_lookup=membership_count_lookup,
    )
