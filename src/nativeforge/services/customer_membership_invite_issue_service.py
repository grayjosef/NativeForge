"""A seated member issues an invite. The address never stays.

The operator script already does this for one demo organization. This is the
same write, for the organization the session actually belongs to: fingerprint
and domain only, no mail, no token, no echo of the mailbox.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import sqlalchemy as sa

from nativeforge.services.dev_org_membership_bootstrap_service import MEMBERSHIPS
from nativeforge.services.membership_invite_repository_service import (
    email_fingerprint,
    insert_invite,
)
from nativeforge.services.org_tenant_seat_model_service import (
    DEFAULT_SEAT_CAP,
    ORG_ROLES,
)

SCHEMA_VERSION = "nf_customer_membership_invite_issue_v1"
DEFAULT_TTL_DAYS = 14
DEFAULT_ROLE = "grant_lead"
INVITABLE_ROLES = frozenset(ORG_ROLES - {"org_owner"})


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value or "").strip())
    except (ValueError, AttributeError, TypeError):
        return None


def issue_customer_invite(
    *,
    connection: Any = None,
    organization_id: Any = None,
    requested_by: Any = None,
    invited_email: Any = None,
    requested_role: Any = None,
    ttl_days: int = DEFAULT_TTL_DAYS,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Write one approved invite from the caller's membership, or nothing."""
    blocked: list[str] = []
    organization = _as_uuid(organization_id)
    requester = _as_uuid(requested_by)
    role = str(requested_role or DEFAULT_ROLE).strip() or DEFAULT_ROLE
    moment = now or datetime.now(UTC)
    expires = moment + timedelta(days=max(1, int(ttl_days or DEFAULT_TTL_DAYS)))
    invite_id = f"nf-invite-{uuid.uuid4().hex[:12]}"

    if connection is None:
        blocked.append("no_connection_supplied")
    if organization is None:
        blocked.append("organization_id_missing")
    if requester is None:
        blocked.append("requester_missing")
    if role not in INVITABLE_ROLES:
        blocked.append(f"requested_role_not_invitable:{role}")
    if email_fingerprint(invited_email) is None:
        blocked.append("invited_email_not_an_address")

    requester_role: str | None = None
    seat_count = 0
    seat_cap = DEFAULT_SEAT_CAP
    if connection is not None and organization is not None and requester is not None:
        row = (
            connection.execute(
                sa.select(MEMBERSHIPS.c.role).where(
                    MEMBERSHIPS.c.organization_id == organization,
                    MEMBERSHIPS.c.identity_id == requester,
                    MEMBERSHIPS.c.state == "active",
                    MEMBERSHIPS.c.revoked_at.is_(None),
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            blocked.append("requester_is_not_an_active_member")
        else:
            requester_role = str(row["role"] or "") or None
        seat_count = int(
            connection.execute(
                sa.select(sa.func.count())
                .select_from(MEMBERSHIPS)
                .where(
                    MEMBERSHIPS.c.organization_id == organization,
                    MEMBERSHIPS.c.state == "active",
                    MEMBERSHIPS.c.revoked_at.is_(None),
                )
            ).scalar_one()
        )
        cap_row = connection.execute(
            sa.text("SELECT seat_cap FROM organizations WHERE id = :o"),
            {"o": organization.hex},
        ).first()
        if cap_row is not None and cap_row[0]:
            seat_cap = int(cap_row[0])

    result: dict[str, Any] = {
        "rows_written": 0,
        "email_address_recorded": False,
        "provider_subject_recorded": False,
        "email_sent": False,
        "blocked_reasons": list(blocked),
    }
    if not blocked:
        result = insert_invite(
            connection=connection,
            organization_id=str(organization),
            created_at=moment,
            invite_id=invite_id,
            requested_role=role,
            requested_by=str(requester),
            requested_by_role=requester_role or "unknown",
            invited_email=invited_email,
            invite_state="approved",
            approval_required=True,
            approval_state="approved",
            approved_by=str(requester),
            approved_by_role=requester_role or "unknown",
            seat_cap=seat_cap,
            seat_count=seat_count,
            expires_at=expires.isoformat(),
            now=moment.isoformat(),
        )

    payload = {
        "schema_version": SCHEMA_VERSION,
        "issued": bool(result.get("rows_written")),
        "invite_id": invite_id if result.get("rows_written") else None,
        "requested_role": role,
        "expires_at": expires.isoformat(),
        "email_recorded": False,
        "email_sent": False,
        "blocked_reasons": sorted(set(result.get("blocked_reasons") or blocked)),
    }
    blob = json.dumps(payload)
    if "@" in blob:
        return _json_safe(
            {
                **payload,
                "issued": False,
                "invite_id": None,
                "blocked_reasons": sorted(
                    set([*payload["blocked_reasons"], "issue_payload_carried_an_at_sign"])
                ),
            }
        )
    return _json_safe(payload)
