#!/usr/bin/env python3
"""Gate 136C: accept one demo-organization invite, for somebody who signed in.

    ./scripts/nativeforge_demo_invite_accept.py \\
        --invite-id nf-invite-abc123 --email person@example.com

## The invited person must have signed in first

Their first login through real Google OAuth writes an `nf_identities` row and
issues no session — the callback needs a membership before it sets a cookie, and
the membership is what this script is for. So the order is:

```text
1  they sign in            an identity row exists. No session yet.
2  you run this            the invite is accepted; a membership is written
3  they sign in again      now they get a session
```

If step 1 has not happened this refuses with
`no_identity_has_signed_in_with_that_address`, which is the honest answer and
not an error to work around. There is no flag that accepts on behalf of
somebody who has not authenticated: that would be the faked user this gate
exists to avoid.

## The operator cannot choose who accepts

The address is resolved against `nf_identities`, and the acceptance then
requires that identity to match the invite's own fingerprint. Both halves have
to agree, so running this with a different address does not redirect the
membership — it refuses.

The address is taken at runtime, never printed, never stored, never written to
an artifact.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
_SRC = ROOT / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from nativeforge.services.customer_auth_owner_activation_decision_service import (  # noqa: E402
    APPROVED_ENVIRONMENTS,
    APPROVED_ORGANIZATION_ID,
    REFUSED_ORGANIZATION_ID,
)
from nativeforge.services.membership_invite_activation_service import (  # noqa: E402
    accept_invite_and_create_membership,
    activation_invariant_failures,
    resolve_invited_identity,
)


def _environment() -> str:
    from nativeforge.lib.settings import get_settings

    return str(get_settings().app_env or "").strip().lower()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--invite-id", required=True)
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
    parser.add_argument("--json", action="store_true")
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
                "membership_activated": False,
                "invite_id": str(args.invite_id),
                "organization_id": organization,
                "environment": environment or None,
                "blocked_reasons": sorted(refusals),
            },
            as_json=args.json,
        )
        return 2

    from nativeforge.db.session import engine

    # One transaction. `accept_invite_and_create_membership` raises if the
    # membership fails after the acceptance, and this is what rolls it back.
    with engine.begin() as connection:
        resolved = resolve_invited_identity(connection=connection, email=args.email)
        if not resolved["identity_resolved"]:
            _report(
                {
                    "membership_activated": False,
                    "invite_id": str(args.invite_id),
                    "organization_id": organization,
                    "environment": environment,
                    "identity_resolved": False,
                    "identity_candidates": resolved["candidates"],
                    "blocked_reasons": list(resolved["blocked_reasons"]),
                },
                as_json=args.json,
            )
            return 1

        result = accept_invite_and_create_membership(
            connection=connection,
            invite_id=str(args.invite_id),
            organization_id=organization,
            accepted_by_identity_id=resolved["identity_id"],
            now=datetime.now(UTC),
            membership_id=uuid.uuid4(),
        )

    fails = activation_invariant_failures(result)
    status = {
        "membership_activated": bool(result["membership_activated"]),
        "invite_accepted": bool(result["invite_accepted"]),
        "invite_id": result["invite_id"],
        "organization_id": result["organization_id"],
        "environment": environment,
        "is_demo": bool(result["is_demo"]),
        "identity_resolved": True,
        "accepter_matched_the_invite": bool(result["accepter_matched_the_invite"]),
        "membership_rows_written": int(result["membership_rows_written"]),
        "provenance": result["provenance"],
        "invite_binding_passed": bool(result["invite_binding_passed"]),
        "invited_email_recorded": bool(result["invited_email_recorded"]),
        "provider_subject_recorded": bool(result["provider_subject_recorded"]),
        "email_sent": bool(result["email_sent"]),
        "invariant_failures": fails,
        "blocked_reasons": list(result["blocked_reasons"]),
    }
    _report(status, as_json=args.json)
    if fails:
        return 3
    return 0 if status["membership_activated"] else 1


def _report(status: dict[str, object], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps(status, indent=2, sort_keys=True))
        return

    for key in sorted(status):
        if key in {"blocked_reasons", "invariant_failures"}:
            continue
        print(f"{key:28} {status[key]}")
    for reason in status.get("blocked_reasons") or []:  # type: ignore[union-attr]
        print(f"blocked                      {reason}")
    for fail in status.get("invariant_failures") or []:  # type: ignore[union-attr]
        print(f"INVARIANT FAILED             {fail}")

    if status.get("membership_activated"):
        print()
        print("next:")
        print("  1  the invited person signs in again — they get a session now:")
        print("       https://nf-dev.mayhem-nc.dev/api/auth/login")
        print("  2  verify:")
        print("       ./scripts/verify_nativeforge_customer_auth_live.sh")
    elif status.get("blocked_reasons"):
        print()
        print("nothing was written. The blocker above is the reason.")


if __name__ == "__main__":
    raise SystemExit(main())
