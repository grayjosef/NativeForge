"""Gate 134: a session cookie for an organization, for tests that used a header.

Fifty-one test files shared the same one-liner:

```python
def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}
```

The routes those tests exercise now derive their organization from a membership
row instead. `session_headers(oid)` is the replacement with the same shape - a
header dict, so the call sites do not change - and it returns a `Cookie` header
carrying a real signed session for a real identity with a real membership.

## Everything it creates is real

There is no fake session here and no fake user. It writes an `organizations`
row, an `nf_identities` row through the actual upsert path, and an
`nf_org_memberships` row - and then mints a session through
`customer_session_format_service`, which refuses one that would not verify.
A test that passes has proved the whole chain, not a stub of it.

`membership_source='verified_directory'` needs no approver, which keeps these
seeds off Gate 132's bootstrap self-approval path - that rule is tested where it
lives.

## Why the signing key is set here

`tests/conftest.py` blanks `NF_SESSION_SIGNING_KEY` so the suite cannot read a
developer's provider configuration. A session cannot be signed without one, so
this sets a key of its own the first time it is asked. It is long enough not to
be refused and is not the committed fixture key, so `production_session` is
reachable; it signs nothing outside the test process.
"""

from __future__ import annotations

import os
import time
import uuid
from datetime import UTC, datetime

import sqlalchemy as sa

#: Long enough, and not the committed local-dev fixture key.
TEST_SIGNING_KEY = "gate134-test-session-key-" + ("s" * 40)

ISSUER = "https://accounts.google.com"

#: Session lifetime. Generous, and minted against the real clock: Gate 132's
#: route tests used a fixed timestamp with a one-hour window and started failing
#: at that hour on the day it named.
SESSION_SECONDS = 3600


def ensure_signing_key() -> None:
    """A signing key exists for this process. Idempotent."""
    if os.environ.get("NF_SESSION_SIGNING_KEY") != TEST_SIGNING_KEY:
        os.environ["NF_SESSION_SIGNING_KEY"] = TEST_SIGNING_KEY
        from nativeforge.lib.settings import get_settings

        get_settings.cache_clear()


def ensure_org(organization_id: uuid.UUID | str, org_type: str = "demo") -> str:
    """An `organizations` row with this id. Returns the type it actually has.

    An existing row is **never** rewritten. Most callers of `session_headers`
    are tests that created their own organization and know what type it is; a
    helper that quietly flipped `real` to `demo` because of its own default
    would change what the test was testing, and the demo/real separation is
    exactly what several of them assert.

    So `org_type` is what to create when there is no row, and the row wins
    when there is one.
    """
    from nativeforge.db.session import SessionLocal

    oid = uuid.UUID(str(organization_id))
    with SessionLocal() as session:
        existing = session.execute(
            sa.text("SELECT org_type FROM organizations WHERE id = :i"),
            {"i": oid.hex},
        ).first()
        if existing is not None:
            return str(existing[0])
        session.execute(
            sa.text(
                "INSERT INTO organizations (id, org_type, seat_cap, created_at) "
                "VALUES (:i, :t, 5, CURRENT_TIMESTAMP)"
            ),
            {"i": oid.hex, "t": org_type},
        )
        session.commit()
    return org_type


def ensure_member(
    organization_id: uuid.UUID | str,
    *,
    org_type: str = "demo",
    role: str = "org_owner",
) -> str:
    """An identity with an active membership in this organization.

    Returns the identity id. Idempotent per organization: the subject is derived
    from it, so asking twice yields the same person rather than a second one.
    """
    from nativeforge.db.session import SessionLocal
    from nativeforge.services import dev_org_membership_bootstrap_service as boot

    oid = uuid.UUID(str(organization_id))
    # The row wins. A test that made a real org gets a real-org membership.
    org_type = ensure_org(oid, org_type)

    with SessionLocal() as session:
        connection = session.connection()
        identity = boot.upsert_identity(
            connection=connection,
            issuer=ISSUER,
            subject=f"gate134-member-of-{oid}",
            email_verified=True,
            verification_source="oidc_token_signature",
        )
        identity_id = identity["identity_id"]

        already = session.execute(
            sa.text(
                "SELECT COUNT(*) FROM nf_org_memberships "
                "WHERE organization_id = :o AND identity_id = :i"
            ),
            {"o": oid.hex, "i": uuid.UUID(identity_id).hex},
        ).scalar_one()

        if not already:
            if org_type == "demo":
                result = boot.insert_membership(
                    connection=connection,
                    organization_id=str(oid),
                    identity_id=identity_id,
                    state="active",
                    role=role,
                    membership_source="verified_directory",
                    approved_by=None,
                )
                assert result["rows_written"] == 1, result["blocked_reasons"]
            else:
                # Gate 132's bootstrap refuses any organization whose org_type is
                # not `demo`, which is its scope enforcement working. There is no
                # write path for a real-org membership anywhere in `src/`, so the
                # real-org half of every demo/real separation test has to insert
                # the row directly. Stated rather than worked around quietly.
                connection.execute(
                    sa.insert(boot.MEMBERSHIPS).values(
                        id=uuid.uuid4(),
                        organization_id=oid,
                        identity_id=uuid.UUID(identity_id),
                        is_demo=False,
                        state="active",
                        membership_source="verified_directory",
                        role=role,
                        role_source="membership_record",
                        invited_by=None,
                        approved_by=None,
                        created_at=datetime.now(UTC),
                        revoked_at=None,
                        expires_at=None,
                    )
                )
        session.commit()
    return identity_id


def session_cookie_value(
    organization_id: uuid.UUID | str,
    *,
    org_type: str = "demo",
    role: str = "org_owner",
    identity_id: str | None = None,
) -> str:
    """A signed session for a member of this organization."""
    from nativeforge.services.customer_session_format_service import build_session

    ensure_signing_key()
    principal = identity_id or ensure_member(
        organization_id, org_type=org_type, role=role
    )

    issued = int(time.time())
    built = build_session(
        principal_id=principal,
        organization_id=str(uuid.UUID(str(organization_id))),
        roles=[role],
        issued_at=issued,
        expires_at=issued + SESSION_SECONDS,
        auth_source="oidc_authorization_code",
        session_id=str(uuid.uuid4()),
        now=issued + 1,
    )
    assert built["session_cookie_valid"] is True, built["blocked_reasons"]
    return built["session_cookie_value"]


def session_headers(
    organization_id: uuid.UUID | str,
    *,
    org_type: str = "demo",
    role: str = "org_owner",
) -> dict[str, str]:
    """The drop-in for `_hdr(oid)`: same shape, a session instead of a header.

    Deliberately returns no `X-NF-Org-Id`. A test that still passes after this
    swap has proved the route reads the session; one that keeps the header as
    well would prove nothing about which of the two the route used.
    """
    value = session_cookie_value(organization_id, org_type=org_type, role=role)
    return {"Cookie": f"nf_session={value}"}


def forged_header_only(organization_id: uuid.UUID | str) -> dict[str, str]:
    """The old header, with no session. What a converted route must refuse."""
    return {"X-NF-Org-Id": str(organization_id)}


def session_plus_forged_header(
    organization_id: uuid.UUID | str,
    forged_organization_id: uuid.UUID | str,
    *,
    org_type: str = "demo",
) -> dict[str, str]:
    """A real session for one organization and a header naming another.

    The header must change nothing. This is the shape of the attack the
    conversion exists to remove.
    """
    headers = session_headers(organization_id, org_type=org_type)
    headers["X-NF-Org-Id"] = str(forged_organization_id)
    return headers
