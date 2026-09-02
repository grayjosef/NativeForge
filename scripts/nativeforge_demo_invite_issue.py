#!/usr/bin/env python3
"""Gate 136B: issue and approve one demo-organization invite.

    ./scripts/nativeforge_demo_invite_issue.py --email person@example.com

The address is taken at runtime and is never printed, never written to an
artifact, and never stored. What reaches the database is its domain half and a
fingerprint; what reaches your terminal is neither.

## Scope, enforced here and not only asserted

```text
organization  bbbbbbbb-cccc-dddd-eeee-ffffffffffff, and no other
refused       aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee, by name
environment   local | dev | test. production refuses and exits 2.
demo          derived from organizations.org_type, not from a flag
```

The `--organization` flag exists so the refusals are reachable, which is the
only reason to have it. It cannot widen the scope.

## What this does not do

No email is sent. Nothing in NativeForge can send one, and the table this
writes to has no column for an address to send to. Telling the invited person
is a message you send yourself, which is also why the invite id is printed.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import sqlalchemy as sa  # noqa: E402

from nativeforge.services.customer_auth_owner_activation_decision_service import (  # noqa: E402
    APPROVED_ENVIRONMENTS,
    APPROVED_ORGANIZATION_ID,
    REFUSED_ORGANIZATION_ID,
)
from nativeforge.services.membership_invite_repository_service import (  # noqa: E402
    insert_invite,
)

DEFAULT_ROLE = "grant_lead"
DEFAULT_TTL_DAYS = 14


def _environment() -> str:
    from nativeforge.lib.settings import get_settings

    return str(get_settings().app_env or "").strip().lower()


def _owner_identity(connection: object, organization_id: str) -> tuple[str, str] | None:
    """The demo organization's owner, read rather than supplied.

    An invite is issued *by* somebody, and letting the operator name them would
    let the operator forge who authorized a membership - which is the fact the
    whole invite gate exists to establish.
    """
    row = (
        connection.execute(  # type: ignore[attr-defined]
            sa.text(
                "SELECT identity_id, role FROM nf_org_memberships "
                "WHERE organization_id = :o AND state = 'active' "
                "AND revoked_at IS NULL AND role = 'org_owner' "
                "ORDER BY created_at LIMIT 1"
            ),
            {"o": uuid.UUID(organization_id).hex},
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    return str(uuid.UUID(str(row["identity_id"]))), str(row["role"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--email",
        required=True,
        help="the invited person's address. Never printed, never stored.",
    )
    parser.add_argument(
        "--organization",
        default=APPROVED_ORGANIZATION_ID,
        help="demo organization id. Present so the refusals are reachable.",
    )
    parser.add_argument("--role", default=DEFAULT_ROLE)
    parser.add_argument("--invite-id", default=None)
    parser.add_argument("--ttl-days", type=int, default=DEFAULT_TTL_DAYS)
    parser.add_argument(
        "--json", action="store_true", help="machine-readable status on stdout"
    )
    args = parser.parse_args(argv)

    organization = str(args.organization).strip().lower()
    environment = _environment()
    refusals: list[str] = []

    if organization == REFUSED_ORGANIZATION_ID:
        refusals.append("organization_is_the_explicitly_refused_real_org")
    elif organization != APPROVED_ORGANIZATION_ID:
        refusals.append("organization_outside_the_approved_scope")
    if environment not in APPROVED_ENVIRONMENTS:
        refusals.append(
            f"environment_outside_the_approved_scope:{environment or 'unset'}"
        )

    if refusals:
        _report(
            {
                "issued": False,
                "organization_id": organization,
                "environment": environment or None,
                "blocked_reasons": sorted(refusals),
            },
            as_json=args.json,
        )
        return 2

    invite_id = str(args.invite_id or f"nf-invite-{uuid.uuid4().hex[:12]}")
    now = datetime.now(UTC)
    expires = now + timedelta(days=max(1, int(args.ttl_days)))

    from nativeforge.db.session import engine

    with engine.begin() as connection:
        owner = _owner_identity(connection, organization)
        if owner is None:
            _report(
                {
                    "issued": False,
                    "organization_id": organization,
                    "environment": environment,
                    "blocked_reasons": [
                        "organization_has_no_active_owner_to_invite_by"
                    ],
                },
                as_json=args.json,
            )
            return 2

        owner_id, owner_role = owner
        result = insert_invite(
            connection=connection,
            organization_id=organization,
            created_at=now,
            invite_id=invite_id,
            requested_role=str(args.role),
            requested_by=owner_id,
            requested_by_role=owner_role,
            invited_email=args.email,
            invite_state="approved",
            approval_required=True,
            approval_state="approved",
            approved_by=owner_id,
            approved_by_role=owner_role,
            seat_cap=5,
            seat_count=_seat_count(connection, organization),
            expires_at=expires.isoformat(),
            now=now.isoformat(),
        )

    status = {
        "issued": bool(result["rows_written"]),
        "invite_id": invite_id,
        "organization_id": organization,
        "environment": environment,
        "requested_role": str(args.role),
        "expires_at": expires.isoformat(),
        # Reported as refusals kept, not as an absence.
        "invited_email_recorded": bool(result["email_address_recorded"]),
        "provider_subject_recorded": bool(result["provider_subject_recorded"]),
        "email_sent": bool(result["email_sent"]),
        "blocked_reasons": list(result["blocked_reasons"]),
    }
    _report(status, as_json=args.json)
    return 0 if status["issued"] else 1


def _seat_count(connection: object, organization_id: str) -> int:
    return int(
        connection.execute(  # type: ignore[attr-defined]
            sa.text(
                "SELECT COUNT(*) FROM nf_org_memberships "
                "WHERE organization_id = :o AND state = 'active' "
                "AND revoked_at IS NULL"
            ),
            {"o": uuid.UUID(organization_id).hex},
        ).scalar_one()
    )


def _report(status: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(status, indent=2, sort_keys=True))
        return

    for key in sorted(status):
        if key == "blocked_reasons":
            continue
        print(f"{key:28} {status[key]}")
    for reason in status.get("blocked_reasons") or []:  # type: ignore[union-attr]
        print(f"blocked                      {reason}")

    if status.get("issued"):
        print()
        print("next:")
        print("  1  the invited person signs in once, so their identity exists:")
        print("       https://nf-dev.mayhem-nc.dev/api/auth/login")
        print("     they will not get a session yet. That is correct.")
        print("  2  then accept the invite for them:")
        print(
            "       ./scripts/nativeforge_demo_invite_accept.py"
            f" --invite-id {status['invite_id']} --email <the same address>"
        )
        print("  3  then verify:")
        print("       ./scripts/verify_nativeforge_customer_auth_live.sh")


if __name__ == "__main__":
    raise SystemExit(main())
