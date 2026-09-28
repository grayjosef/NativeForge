"""After a verified sign-in, bind any invite that already named this mailbox.

The invited person cannot hold an org session yet — that is what the invite
is for. The OIDC callback already proved the address. Matching that address
to a stored fingerprint, then running the existing activation join, is the
customer path that does not invent an unauthenticated accept route.

Still demo-scoped: ``accept_invite_and_create_membership`` refuses a real
organization. Still no mail: the person is already here.
"""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa

from nativeforge.services.membership_invite_activation_service import (
    accept_invite_and_create_membership,
)
from nativeforge.services.membership_invite_repository_service import (
    INVITES,
    email_fingerprint,
)

SCHEMA_VERSION = "nf_customer_invite_signin_activation_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def activate_invites_matching_signin(
    *,
    connection: Any = None,
    identity_id: Any = None,
    email: Any = None,
) -> dict[str, Any]:
    """Activate every approved invite whose fingerprint matches this sign-in."""
    blocked: list[str] = []
    fingerprint = email_fingerprint(email)
    if connection is None:
        blocked.append("no_connection_supplied")
    if not identity_id:
        blocked.append("identity_missing")
    if not fingerprint:
        blocked.append("signin_email_could_not_be_fingerprinted")

    matches: list[dict[str, Any]] = []
    activated = 0
    if connection is not None and identity_id and fingerprint and not blocked:
        rows = (
            connection.execute(
                sa.select(
                    INVITES.c.invite_id,
                    INVITES.c.organization_id,
                    INVITES.c.invite_state,
                    INVITES.c.approval_state,
                    INVITES.c.revoked_at,
                ).where(
                    INVITES.c.invited_email_fingerprint == fingerprint,
                    INVITES.c.invite_state != "accepted",
                    INVITES.c.revoked_at.is_(None),
                    INVITES.c.approval_state.in_(["approved", "not_required"]),
                )
            )
            .mappings()
            .all()
        )
        if not rows:
            blocked.append("no_approved_invite_matches_this_signin")
        for row in rows:
            result = accept_invite_and_create_membership(
                connection=connection,
                invite_id=str(row["invite_id"]),
                organization_id=row["organization_id"],
                accepted_by_identity_id=identity_id,
            )
            if result.get("membership_activated"):
                activated += 1
            matches.append(
                {
                    "invite_id": str(row["invite_id"]),
                    "membership_activated": bool(result.get("membership_activated")),
                    "blocked_reasons": list(result.get("blocked_reasons") or []),
                }
            )
            blocked.extend(result.get("blocked_reasons") or [])

    payload = {
        "schema_version": SCHEMA_VERSION,
        "attempted": True,
        "membership_activated": activated > 0,
        "activated_count": activated,
        "match_count": len(matches),
        "matches": matches,
        "email_recorded": False,
        "email_sent": False,
        "blocked_reasons": sorted(set(blocked)),
    }
    return _json_safe(payload)
