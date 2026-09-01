"""HTTP Layer 3 demo vs real separation (NF-001), through a session.

Gate 133F converted these two routes off the dev header. The separation they
prove is unchanged; where the organization comes from is not.

```text
before   X-NF-Org-Id -> isolation_deps -> NF_DEMO_ORG_IDS -> org_type
after    nf_session  -> membership row -> organizations.org_type -> org_type
```

The old tests set the allowlist and sent a header. They passed while the live
deployment had that same combination backwards — an empty allowlist made the
demo organization classify `real`, so the demo-only route refused it. The tests
could not catch that because they set the allowlist themselves.

These read `organizations.org_type`, which is the column the deployment reads.
"""

from __future__ import annotations

import uuid

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.services import dev_org_membership_bootstrap_service as boot_svc

DEMO_ORG = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL_ORG = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = "https://accounts.google.com"

#: Long enough and not the committed fixture key, so a session can be valid.
SIGNING_KEY = "isolation-routes-test-key-" + ("k" * 40)


def _seed(org_type: str, organization_id: str, subject: str) -> str:
    """One organization, one identity, one active membership. Returns the id.

    The demo membership goes through `insert_membership`, which is the real
    write path. The real-org one cannot: that service refuses any organization
    whose `org_type` is not `demo`
    (`bootstrap_membership_refused_for_a_non_demo_organization`), which is Gate
    132's scope enforcement working. There is no write path for a real-org
    membership anywhere in `src/` — deliberately — so this inserts the row
    directly to give the real-org branch of the separation something to stand on.

    Stated rather than worked around quietly: if a real-org membership write path
    ever appears, this helper should use it, and a test asserting the refusal
    lives in Gate 132's file.
    """
    from datetime import UTC, datetime

    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        session.execute(
            sa.text(
                "INSERT INTO organizations (id, org_type, seat_cap, created_at) "
                "VALUES (:i, :t, 5, CURRENT_TIMESTAMP)"
            ),
            {"i": uuid.UUID(organization_id).hex, "t": org_type},
        )
        connection = session.connection()
        identity = boot_svc.upsert_identity(
            connection=connection,
            issuer=ISSUER,
            subject=subject,
            email_verified=True,
            verification_source="oidc_token_signature",
        )
        identity_id = identity["identity_id"]

        if org_type == "demo":
            result = boot_svc.insert_membership(
                connection=connection,
                organization_id=organization_id,
                identity_id=identity_id,
                state="active",
                role="org_owner",
                # `verified_directory` needs no approver, which keeps these
                # tests off the bootstrap self-approval path - that rule is
                # Gate 132's and is tested there.
                membership_source="verified_directory",
                approved_by=None,
            )
            assert result["rows_written"] == 1, result["blocked_reasons"]
        else:
            connection.execute(
                sa.insert(boot_svc.MEMBERSHIPS).values(
                    id=uuid.uuid4(),
                    organization_id=uuid.UUID(organization_id),
                    identity_id=uuid.UUID(identity_id),
                    is_demo=False,
                    state="active",
                    membership_source="verified_directory",
                    role="org_owner",
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


def _cookie(identity_id: str, organization_id: str) -> str:
    import time

    from nativeforge.services.customer_session_format_service import build_session

    issued = int(time.time())
    built = build_session(
        principal_id=identity_id,
        organization_id=organization_id,
        roles=["org_owner"],
        issued_at=issued,
        expires_at=issued + 3600,
        auth_source="oidc_authorization_code",
        session_id=str(uuid.uuid4()),
    )
    assert built["session_cookie_valid"] is True, built["blocked_reasons"]
    return built["session_cookie_value"]


@pytest.fixture
def isolation_client(monkeypatch: pytest.MonkeyPatch):
    """A client, a signing key, and a database with no organizations in it."""
    from nativeforge.db.session import SessionLocal

    monkeypatch.setenv("NF_SESSION_SIGNING_KEY", SIGNING_KEY)
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()

    def _clear() -> None:
        with SessionLocal() as session:
            session.execute(sa.text("DELETE FROM nf_org_memberships"))
            session.execute(sa.text("DELETE FROM nf_identities"))
            session.execute(sa.text("DELETE FROM organizations"))
            session.commit()

    _clear()
    with TestClient(create_app()) as client:
        yield client
    _clear()
    get_settings.cache_clear()


def test_demo_only_route_200_for_a_demo_org_session(isolation_client) -> None:
    identity_id = _seed("demo", DEMO_ORG, "demo-subject")
    isolation_client.cookies.set("nf_session", _cookie(identity_id, DEMO_ORG))
    response = isolation_client.get("/v1/isolation/demo-only")
    assert response.status_code == 200
    assert response.json() == {"scope": "demo", "org_id": DEMO_ORG}


def test_real_only_route_403_for_a_demo_org_session(isolation_client) -> None:
    identity_id = _seed("demo", DEMO_ORG, "demo-subject")
    isolation_client.cookies.set("nf_session", _cookie(identity_id, DEMO_ORG))
    assert isolation_client.get("/v1/isolation/real-only").status_code == 403


def test_real_only_route_200_for_a_real_org_session(isolation_client) -> None:
    identity_id = _seed("real", REAL_ORG, "real-subject")
    isolation_client.cookies.set("nf_session", _cookie(identity_id, REAL_ORG))
    response = isolation_client.get("/v1/isolation/real-only")
    assert response.status_code == 200
    assert response.json() == {"scope": "real", "org_id": REAL_ORG}


def test_demo_only_route_403_for_a_real_org_session(isolation_client) -> None:
    identity_id = _seed("real", REAL_ORG, "real-subject")
    isolation_client.cookies.set("nf_session", _cookie(identity_id, REAL_ORG))
    assert isolation_client.get("/v1/isolation/demo-only").status_code == 403


def test_the_org_type_comes_from_the_row_not_the_allowlist(
    isolation_client, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The defect the old tests could not see.

    `NF_DEMO_ORG_IDS` is emptied, which is the state the live deployment was in.
    On the old chain that classified the demo organization `real` and the
    demo-only route refused it. The row says `demo`, so the route answers.
    """
    monkeypatch.setenv("NF_DEMO_ORG_IDS", "")
    get_settings.cache_clear()
    identity_id = _seed("demo", DEMO_ORG, "demo-subject")
    isolation_client.cookies.set("nf_session", _cookie(identity_id, DEMO_ORG))
    assert isolation_client.get("/v1/isolation/demo-only").status_code == 200


def test_no_session_returns_401(isolation_client) -> None:
    assert isolation_client.get("/v1/isolation/demo-only").status_code == 401
    assert isolation_client.get("/v1/isolation/real-only").status_code == 401


def test_the_dev_header_no_longer_opens_these_routes(isolation_client) -> None:
    """The conversion, asserted as a refusal rather than as an absence.

    The header still exists, is still enabled, and still names a real demo
    organization. It gets 401 because it authenticates nobody.
    """
    _seed("demo", DEMO_ORG, "demo-subject")
    response = isolation_client.get(
        "/v1/isolation/demo-only", headers={"X-NF-Org-Id": DEMO_ORG}
    )
    assert response.status_code == 401


def test_a_session_for_an_organization_that_does_not_exist_is_refused(
    isolation_client,
) -> None:
    identity_id = _seed("demo", DEMO_ORG, "demo-subject")
    absent = "99999999-8888-4777-8666-555555555555"
    isolation_client.cookies.set("nf_session", _cookie(identity_id, absent))
    assert isolation_client.get("/v1/isolation/demo-only").status_code == 401


def test_a_forged_cookie_is_refused(isolation_client) -> None:
    _seed("demo", DEMO_ORG, "demo-subject")
    isolation_client.cookies.set("nf_session", "v1.bm90LWEtcGF5bG9hZA.bm90LWEtc2ln")
    assert isolation_client.get("/v1/isolation/demo-only").status_code == 401


def test_a_cookie_claiming_an_organization_the_holder_is_not_in_is_refused(
    isolation_client,
) -> None:
    """Gate 132's cross-tenant fix, at the dependency this gate converted.

    The identity is a member of the demo organization. The cookie names the real
    one. Some membership exists, and it is not a membership of what the cookie
    claims.
    """
    from nativeforge.db.session import SessionLocal

    identity_id = _seed("demo", DEMO_ORG, "demo-subject")
    with SessionLocal() as session:
        session.execute(
            sa.text(
                "INSERT INTO organizations (id, org_type, seat_cap, created_at) "
                "VALUES (:i, 'real', 5, CURRENT_TIMESTAMP)"
            ),
            {"i": uuid.UUID(REAL_ORG).hex},
        )
        session.commit()

    isolation_client.cookies.set("nf_session", _cookie(identity_id, REAL_ORG))
    assert isolation_client.get("/v1/isolation/real-only").status_code == 401
    assert isolation_client.get("/v1/isolation/demo-only").status_code == 401
