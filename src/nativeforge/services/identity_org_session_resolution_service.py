"""Gate 132: which organization does this verified identity act for?

The question Gate 131 stopped on. Google proved who the person is; it has no
opinion about which Tribal government they represent, and
`customer_session_format_service` refuses a session that cannot say
(`session_without_an_organization_id`).

## The answer comes from a membership row and nowhere else

```text
nf_org_memberships   state='active', revoked_at IS NULL, not expired
```

Not the email domain - Gate 112 settled that, and `gmail.com` is not a Tribe.
Not a header, not a claim, not a caller argument. A membership is the record
this product keeps of who belongs where, and it is the only thing here that
resolves an organization.

## Exactly one, or none

Zero active memberships resolves nothing. Two resolve nothing either, and that
is the less obvious half: picking one would be picking which tenant's data the
session may read, and a coin flip is not an authorization. A person legitimately
in two organizations needs to be asked which, and that ask does not exist yet -
so the refusal is named `identity_has_multiple_active_memberships` rather than
quietly resolved.

## Expiry is checked here, not left to the row

`state='active'` and `expires_at` in the past can both be true at once - nothing
sweeps the table. A membership past its expiry does not resolve, and the state
column is not taken at its word.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

from nativeforge.services.dev_org_membership_bootstrap_service import (
    IDENTITIES,
    MEMBERSHIPS,
    STORABLE_ROLES,
)
from nativeforge.services.membership_directory_service import (
    ACTING_STATES,
    TRUSTED_MEMBERSHIP_SOURCES,
    TRUSTED_ROLE_SOURCES,
)

SCHEMA_VERSION = "nf_identity_org_session_resolution_v1"

RESULT_FIELDS: tuple[str, ...] = (
    "schema_version",
    "identity_id",
    "identity_found",
    "identity_disabled",
    "membership_rows_considered",
    "active_membership_count",
    "organization_id",
    "organization_id_resolved",
    "membership_verified",
    "is_demo",
    "roles",
    "membership_source",
    "role_source",
    "resolution_available",
    "blocked_reasons",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value or "").strip())
    except (ValueError, AttributeError, TypeError):
        return None


def _aware(moment: Any) -> datetime | None:
    if moment is None:
        return None
    if isinstance(moment, datetime):
        return moment if moment.tzinfo else moment.replace(tzinfo=UTC)
    try:
        parsed = datetime.fromisoformat(str(moment))
    except (ValueError, TypeError):
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def find_identity_id(
    *,
    connection: Any = None,
    issuer: Any = None,
    subject: Any = None,
) -> str | None:
    """The internal id for a verified ``(issuer, subject)``, or None.

    Keyed on the pair rather than the subject alone: subjects are unique per
    issuer, and two providers may legitimately mint the same string.
    """
    if connection is None:
        return None
    iss = str(issuer or "").strip()
    sub = str(subject or "").strip()
    if not iss or not sub:
        return None
    row = (
        connection.execute(
            sa.select(IDENTITIES.c.id).where(
                IDENTITIES.c.issuer == iss, IDENTITIES.c.subject == sub
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    resolved = _as_uuid(row["id"])
    return str(resolved) if resolved else None


def resolve_session_organization(
    *,
    connection: Any = None,
    identity_id: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Resolve one identity to one organization. Deny by default."""
    ident = _as_uuid(identity_id)
    blocked_reasons: list[str] = []

    if not str(identity_id or "").strip():
        blocked_reasons.append("resolution_without_an_identity_id")
    elif ident is None:
        blocked_reasons.append("identity_id_is_not_uuid_shaped")
    if connection is None:
        blocked_reasons.append("no_connection_supplied_so_nothing_was_read")

    identity_found = False
    identity_disabled = False
    considered = 0
    active: list[dict[str, Any]] = []
    moment = now or datetime.now(UTC)

    if connection is not None and ident is not None:
        identity_row = (
            connection.execute(
                sa.select(IDENTITIES.c.id, IDENTITIES.c.disabled_at).where(
                    IDENTITIES.c.id == ident
                )
            )
            .mappings()
            .first()
        )
        if identity_row is None:
            blocked_reasons.append("identity_not_found")
        else:
            identity_found = True
            identity_disabled = identity_row["disabled_at"] is not None
            if identity_disabled:
                blocked_reasons.append("identity_is_disabled")

        rows = (
            connection.execute(
                sa.select(
                    MEMBERSHIPS.c.organization_id,
                    MEMBERSHIPS.c.is_demo,
                    MEMBERSHIPS.c.state,
                    MEMBERSHIPS.c.role,
                    MEMBERSHIPS.c.role_source,
                    MEMBERSHIPS.c.membership_source,
                    MEMBERSHIPS.c.revoked_at,
                    MEMBERSHIPS.c.expires_at,
                ).where(MEMBERSHIPS.c.identity_id == ident)
            )
            .mappings()
            .all()
        )
        considered = len(rows)

        for row in rows:
            if str(row["state"] or "").strip().lower() not in ACTING_STATES:
                continue
            if row["revoked_at"] is not None:
                continue
            expires = _aware(row["expires_at"])
            # The column says active and the clock disagrees. Nothing sweeps
            # this table, so the clock wins.
            if expires is not None and expires <= moment:
                continue
            if (
                str(row["membership_source"] or "").strip().lower()
                not in TRUSTED_MEMBERSHIP_SOURCES
            ):
                # A row the database should not contain. It is on disk, so it
                # is refused here rather than assumed impossible.
                blocked_reasons.append("active_membership_from_an_untrusted_source")
                continue
            if (
                str(row["role_source"] or "").strip().lower()
                not in TRUSTED_ROLE_SOURCES
            ):
                blocked_reasons.append(
                    "active_membership_with_an_untrusted_role_source"
                )
                continue
            active.append(dict(row))

    if connection is not None and ident is not None and identity_found:
        if not active:
            blocked_reasons.append("identity_has_no_active_membership")
        elif len(active) > 1:
            # Choosing would be choosing whose data this session may read.
            blocked_reasons.append("identity_has_multiple_active_memberships")

    organization_id = ""
    is_demo = False
    roles: list[str] = []
    membership_source = ""
    role_source = ""

    if len(active) == 1 and not blocked_reasons:
        row = active[0]
        org = _as_uuid(row["organization_id"])
        if org is None:
            blocked_reasons.append("membership_organization_id_is_not_uuid_shaped")
        else:
            organization_id = str(org)
            is_demo = bool(row["is_demo"])
            role = str(row["role"] or "").strip().lower()
            if role and role not in STORABLE_ROLES:
                blocked_reasons.append(f"membership_role_not_recognised:{role}")
            else:
                roles = [role] if role else []
            membership_source = str(row["membership_source"] or "")
            role_source = str(row["role_source"] or "")

    resolution_available = bool(organization_id and not blocked_reasons)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "identity_id": str(ident) if ident else "",
            "identity_found": identity_found,
            "identity_disabled": identity_disabled,
            "membership_rows_considered": considered,
            "active_membership_count": len(active),
            "organization_id": organization_id if resolution_available else "",
            "organization_id_resolved": resolution_available,
            # The same fact the session verifier asks for. It is true here only
            # because a row was read, which is what Gate 112 required and what
            # `membership_verified=False` in the route stood in for.
            "membership_verified": resolution_available,
            "is_demo": bool(is_demo and resolution_available),
            "roles": roles if resolution_available else [],
            "membership_source": membership_source if resolution_available else "",
            "role_source": role_source if resolution_available else "",
            "resolution_available": resolution_available,
            "blocked_reasons": sorted(set(blocked_reasons)),
        }
    )


def resolution_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("organization_id_resolved") and not result.get("organization_id"):
        fails.append("resolved_without_an_organization_id")
    if result.get("organization_id") and not result.get("organization_id_resolved"):
        fails.append("organization_id_carried_by_an_unresolved_result")
    if result.get("organization_id_resolved") and result.get("blocked_reasons"):
        fails.append("resolved_alongside_blockers")
    if (
        result.get("organization_id_resolved")
        and result.get("active_membership_count") != 1
    ):
        fails.append("resolved_without_exactly_one_active_membership")
    if result.get("membership_verified") and not result.get("organization_id_resolved"):
        fails.append("membership_verified_without_a_resolved_organization")
    if result.get("organization_id_resolved") and not result.get("identity_found"):
        fails.append("resolved_for_an_identity_that_was_not_found")
    if result.get("identity_disabled") and result.get("organization_id_resolved"):
        fails.append("resolved_for_a_disabled_identity")
    if result.get("membership_source") and (
        result["membership_source"] not in TRUSTED_MEMBERSHIP_SOURCES
    ):
        fails.append("resolution_carries_an_untrusted_membership_source")

    return fails
