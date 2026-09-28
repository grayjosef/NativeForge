"""Who belongs to an organization, without the addresses that identify them.

A member list that returned mailbox values would become a directory of people
to mail. NativeForge does not send mail, and the invite table is built so it
cannot. This directory reports roles, states, and the domain half of a pending
invite — enough for an owner to see who is here and who is waiting.
"""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa

from nativeforge.services.dev_org_membership_bootstrap_service import MEMBERSHIPS
from nativeforge.services.membership_invite_repository_service import INVITES

SCHEMA_VERSION = "nf_customer_membership_directory_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _text(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def list_organization_people(
    *,
    connection: Any = None,
    organization_id: Any = None,
    viewer_identity_id: Any = None,
) -> dict[str, Any]:
    """Active members and open invites for one organization.

    ``viewer_identity_id`` only marks which row is the caller. It is not a
    second authority: the route already required a session for this org.
    """
    blocked: list[str] = []
    members: list[dict[str, Any]] = []
    invites: list[dict[str, Any]] = []

    if connection is None:
        blocked.append("no_connection_supplied")
    if not organization_id:
        blocked.append("organization_id_missing")

    if connection is not None and organization_id and not blocked:
        member_rows = (
            connection.execute(
                sa.select(
                    MEMBERSHIPS.c.id,
                    MEMBERSHIPS.c.role,
                    MEMBERSHIPS.c.state,
                    MEMBERSHIPS.c.membership_source,
                    MEMBERSHIPS.c.identity_id,
                    MEMBERSHIPS.c.created_at,
                    MEMBERSHIPS.c.invite_id,
                ).where(
                    MEMBERSHIPS.c.organization_id == organization_id,
                    MEMBERSHIPS.c.revoked_at.is_(None),
                )
            )
            .mappings()
            .all()
        )
        viewer = _text(viewer_identity_id)
        for row in member_rows:
            identity = _text(row["identity_id"])
            members.append(
                {
                    "membership_id": _text(row["id"]),
                    "role": _text(row["role"]) or "unknown",
                    "state": _text(row["state"]) or "unknown",
                    "membership_source": _text(row["membership_source"]),
                    "invite_id": _text(row["invite_id"]),
                    "created_at": _text(row["created_at"]),
                    "is_viewer": bool(viewer and identity == viewer),
                    "email_recorded": False,
                }
            )

        invite_rows = (
            connection.execute(
                sa.select(
                    INVITES.c.invite_id,
                    INVITES.c.requested_role,
                    INVITES.c.invited_email_domain,
                    INVITES.c.invite_state,
                    INVITES.c.approval_state,
                    INVITES.c.expires_at,
                    INVITES.c.created_at,
                    INVITES.c.accepted_at,
                    INVITES.c.revoked_at,
                ).where(
                    INVITES.c.organization_id == organization_id,
                )
            )
            .mappings()
            .all()
        )
        for row in invite_rows:
            invites.append(
                {
                    "invite_id": _text(row["invite_id"]),
                    "requested_role": _text(row["requested_role"]) or "unknown",
                    "invited_email_domain": _text(row["invited_email_domain"]),
                    "invite_state": _text(row["invite_state"]) or "unknown",
                    "approval_state": _text(row["approval_state"]) or "unknown",
                    "expires_at": _text(row["expires_at"]),
                    "created_at": _text(row["created_at"]),
                    "accepted": row["accepted_at"] is not None,
                    "revoked": row["revoked_at"] is not None,
                    "email_recorded": False,
                }
            )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "member_count": len(members),
        "invite_count": len(invites),
        "members": members,
        "invites": invites,
        "email_recorded": False,
        "email_sent": False,
        "fabricated": False,
        "blocked_reasons": sorted(set(blocked)),
    }
    blob = json.dumps(payload)
    if "@" in blob:
        payload["blocked_reasons"] = sorted(
            set([*blocked, "directory_payload_carried_an_at_sign"])
        )
        payload["members"] = []
        payload["invites"] = []
        payload["member_count"] = 0
        payload["invite_count"] = 0
    return _json_safe(payload)
