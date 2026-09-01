"""Gate 132: the first identity, the first membership, the first session.

Two tables that had existed since Gate 62 with no write path got one, and a
verified Google identity became a session that `/api/auth/current-user` answers.

The tests are grouped by what they would catch:

```text
reconciliation  three sources disagreeing about which orgs are demo
authority       an org resolved from anything but a membership row
derivation      is_demo, or an organization, supplied by a caller
bootstrap       self-approval used as a way in rather than a way to start
session         a cookie authorizing an organization it does not belong to
exposure        a token, a subject or an email leaving the database
artifacts       a secret reaching a file, or a file that will not regenerate
```
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.services import customer_auth_binding_evidence_service as evidence_svc
from nativeforge.services import demo_org_classification_service as cls_svc
from nativeforge.services import dev_org_membership_bootstrap_service as boot_svc
from nativeforge.services import first_dev_org_binding_artifact_service as art
from nativeforge.services import identity_org_session_resolution_service as res_svc
from nativeforge.services import (
    tenant_customer_org_binding_repository_service as binding_svc,
)

DEMO_ORG = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL_ORG = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = "https://accounts.google.com"
SUBJECT = "gate132-test-subject"
NOW = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)

#: Long enough and not the committed fixture, so a production session is
#: reachable. It signs nothing outside this file.
TEST_SIGNING_KEY = "gate132-test-signing-key-" + ("z" * 40)

_ORG_META = sa.MetaData()
ORGANIZATIONS = sa.Table(
    "organizations",
    _ORG_META,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("org_type", sa.String(length=16), nullable=False),
    sa.Column("seat_cap", sa.Integer(), nullable=False),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
)


@pytest.fixture
def bootstrap_db():
    """Organizations, identities, memberships and bindings, for one test."""
    engine = sa.create_engine("sqlite://")
    ORGANIZATIONS.create(engine)
    boot_svc.IDENTITIES.create(engine)
    boot_svc.MEMBERSHIPS.create(engine)
    binding_svc.BINDINGS.create(engine)
    with engine.begin() as conn:
        for org_id, org_type in ((REAL_ORG, "real"), (DEMO_ORG, "demo")):
            conn.execute(
                sa.insert(ORGANIZATIONS).values(
                    id=uuid.UUID(org_id),
                    org_type=org_type,
                    seat_cap=5,
                    created_at=NOW,
                )
            )
        yield conn
    engine.dispose()


def _identity(conn, subject=SUBJECT, **overrides):
    fields = {
        "issuer": ISSUER,
        "subject": subject,
        "email": "someone@example.test",
        "email_verified": True,
        "verification_source": "oidc_token_signature",
    }
    fields.update(overrides)
    return boot_svc.upsert_identity(connection=conn, now=NOW, **fields)


def _membership(conn, identity_id, organization_id=DEMO_ORG, **overrides):
    fields = {
        "state": "active",
        "role": "org_owner",
        "membership_source": "org_owner_approved",
        "approved_by": identity_id,
    }
    fields.update(overrides)
    return boot_svc.insert_membership(
        connection=conn,
        organization_id=organization_id,
        identity_id=identity_id,
        now=NOW,
        **fields,
    )


# ---------------------------------------------------------------------------
# reconciliation: three sources, one answer
# ---------------------------------------------------------------------------


def test_the_organization_row_decides_not_the_settings_allowlist(bootstrap_db):
    """The defect this gate opened with: an empty allowlist called everything real.

    `org_type_for()` classifies by allowlist alone. With `NF_DEMO_ORG_IDS`
    unset the allowlist is empty, so the organization typed `demo` in its own
    column was classified `real` - and `is_demo` pairs with the RLS predicate.
    """
    result = cls_svc.classify_organization(
        DEMO_ORG, connection=bootstrap_db, demo_org_ids=frozenset()
    )
    assert result["org_type_in_database"] == "demo"
    assert result["is_demo"] is True
    assert result["classification_available"] is True
    assert cls_svc.classification_invariant_failures(result) == []


def test_an_allowlist_that_disagrees_with_the_database_refuses_rather_than_wins(
    bootstrap_db,
):
    """A misconfiguration somebody needs to see, not a tie to break quietly."""
    result = cls_svc.classify_organization(
        DEMO_ORG,
        connection=bootstrap_db,
        demo_org_ids=frozenset({uuid.UUID(REAL_ORG)}),
    )
    assert result["sources_agree"] is False
    assert result["classification_available"] is False
    assert result["is_demo"] is False
    assert "settings_says_real_database_says_demo" in result["blocked_reasons"]


def test_an_agreeing_allowlist_permits_the_classification(bootstrap_db):
    """The permitted branch, so the refusal above is not the only reachable one."""
    result = cls_svc.classify_organization(
        DEMO_ORG,
        connection=bootstrap_db,
        demo_org_ids=frozenset({uuid.UUID(DEMO_ORG)}),
    )
    assert result["sources_agree"] is True
    assert result["is_demo"] is True


def test_an_unknown_organization_classifies_as_nothing(bootstrap_db):
    result = cls_svc.classify_organization(
        "99999999-8888-4777-8666-555555555555", connection=bootstrap_db
    )
    assert result["organization_found"] is False
    assert result["is_demo"] is False
    assert "organization_not_found" in result["blocked_reasons"]


def test_is_demo_cannot_be_supplied_by_a_caller():
    """The argument for the module existing: there is no parameter to pass.

    A value that cannot be supplied cannot be supplied wrongly, and `is_demo`
    decides which RLS partition a row lands in.
    """
    import inspect

    for func in (cls_svc.classify_organization, boot_svc.prepare_membership_insert):
        assert "is_demo" not in inspect.signature(func).parameters


def test_a_forged_is_demo_fires_the_invariant():
    result = cls_svc.classify_organization(REAL_ORG, org_type_in_database="real")
    result["is_demo"] = True
    assert (
        "is_demo_true_without_the_database_saying_demo"
        in cls_svc.classification_invariant_failures(result)
    )


def test_the_reconciliation_scan_names_the_allowlist_that_would_agree(bootstrap_db):
    report = cls_svc.reconcile_demo_org_allowlist(
        bootstrap_db, demo_org_ids=frozenset()
    )
    assert report["allowlist_matches_database"] is False
    assert report["allowlist_that_would_agree"] == [DEMO_ORG]
    agreed = cls_svc.reconcile_demo_org_allowlist(
        bootstrap_db, demo_org_ids=frozenset({uuid.UUID(DEMO_ORG)})
    )
    assert agreed["allowlist_matches_database"] is True
    assert agreed["disagreements"] == []


# ---------------------------------------------------------------------------
# identities
# ---------------------------------------------------------------------------


def test_an_identity_row_is_written_from_a_verified_claim(bootstrap_db):
    result = _identity(bootstrap_db)
    assert result["rows_written"] == 1
    assert result["identity_existed"] is False
    assert boot_svc.bootstrap_invariant_failures(identity_result=result) == []


def test_signing_in_twice_is_one_person(bootstrap_db):
    first = _identity(bootstrap_db)
    again = _identity(bootstrap_db)
    assert again["rows_written"] == 0
    assert again["identity_existed"] is True
    assert again["identity_id"] == first["identity_id"]


def test_an_untrusted_verification_source_writes_nothing(bootstrap_db):
    """Gate 112: an email domain, a header and a caller's word are not authority."""
    for source in ("email_domain", "client_header", "cloudflare_access", ""):
        result = _identity(
            bootstrap_db, subject=f"s-{source}", verification_source=source
        )
        assert result["rows_written"] == 0
        assert any(
            r.startswith("verification_source_not_trusted")
            for r in result["blocked_reasons"]
        )


def test_an_identity_without_an_issuer_or_subject_writes_nothing(bootstrap_db):
    no_issuer = _identity(bootstrap_db, issuer="")
    no_subject = _identity(bootstrap_db, subject="")
    assert no_issuer["rows_written"] == 0
    assert "identity_without_an_issuer" in no_issuer["blocked_reasons"]
    assert no_subject["rows_written"] == 0
    assert "identity_without_a_subject" in no_subject["blocked_reasons"]


def test_the_identity_result_carries_no_email_and_no_subject(bootstrap_db):
    """Booleans, not values. A decision record gets pasted into tickets."""
    result = _identity(bootstrap_db, email="someone@example.test")
    assert result["subject_recorded"] is True
    assert result["email_recorded"] is True
    blob = json.dumps(result)
    assert SUBJECT not in blob
    assert "someone@example.test" not in blob
    assert boot_svc.bootstrap_invariant_failures(identity_result=result) == []


# ---------------------------------------------------------------------------
# memberships: the authorization, enforced rather than remembered
# ---------------------------------------------------------------------------


def test_the_bootstrap_refuses_a_non_demo_organization(bootstrap_db):
    """The authorization was demo-only, and a transcript is not an enforcement."""
    identity_id = _identity(bootstrap_db)["identity_id"]
    result = _membership(bootstrap_db, identity_id, organization_id=REAL_ORG)
    assert result["rows_written"] == 0
    assert (
        "bootstrap_membership_refused_for_a_non_demo_organization"
        in result["blocked_reasons"]
    )


def test_a_membership_on_the_demo_organization_is_written_with_is_demo_derived(
    bootstrap_db,
):
    identity_id = _identity(bootstrap_db)["identity_id"]
    result = _membership(bootstrap_db, identity_id)
    assert result["rows_written"] == 1
    assert result["is_demo"] is True
    assert result["org_type_in_database"] == "demo"
    assert result["bootstrap_membership"] is True
    assert boot_svc.bootstrap_invariant_failures(membership_result=result) == []

    row = (
        bootstrap_db.execute(
            sa.select(
                boot_svc.MEMBERSHIPS.c.is_demo,
                boot_svc.MEMBERSHIPS.c.role_source,
                boot_svc.MEMBERSHIPS.c.membership_source,
            )
        )
        .mappings()
        .one()
    )
    assert bool(row["is_demo"]) is True
    assert row["role_source"] == "membership_record"
    assert row["membership_source"] == "org_owner_approved"


def test_a_membership_without_an_organization_id_writes_nothing(bootstrap_db):
    identity_id = _identity(bootstrap_db)["identity_id"]
    result = _membership(bootstrap_db, identity_id, organization_id="")
    assert result["rows_written"] == 0
    assert "membership_without_an_organization_id_anchor" in result["blocked_reasons"]


def test_a_label_shaped_organization_id_is_refused(bootstrap_db):
    """`tenant_id` and `customer_org_id` are labels. Neither is UUID-shaped."""
    identity_id = _identity(bootstrap_db)["identity_id"]
    for label in ("nf-dev-demo-tenant", "customer-org-7", "profile-42"):
        result = _membership(bootstrap_db, identity_id, organization_id=label)
        assert result["rows_written"] == 0
        assert "organization_id_anchor_is_not_uuid_shaped" in result["blocked_reasons"]


def test_an_untrusted_membership_source_writes_nothing(bootstrap_db):
    identity_id = _identity(bootstrap_db)["identity_id"]
    for source in ("email_domain_only", "client_header", "dev_header"):
        result = _membership(bootstrap_db, identity_id, membership_source=source)
        assert result["rows_written"] == 0
        assert any(
            r.startswith("membership_source_not_trusted")
            for r in result["blocked_reasons"]
        )


def test_self_approval_is_permitted_once_and_then_refused(bootstrap_db):
    """Otherwise "the approver must be a member" becomes "approve yourself"."""
    first = _identity(bootstrap_db)["identity_id"]
    assert _membership(bootstrap_db, first)["rows_written"] == 1

    second = _identity(bootstrap_db, subject="second-subject")["identity_id"]
    result = _membership(bootstrap_db, second, role="viewer")
    assert result["rows_written"] == 0
    assert (
        "self_approval_permitted_only_for_the_first_membership"
        in result["blocked_reasons"]
    )


def test_self_approval_cannot_be_cleared_without_a_connection():
    """Proving it is the first membership is a database question."""
    identity_id = str(uuid.uuid4())
    result = boot_svc.prepare_membership_insert(
        organization_id=DEMO_ORG,
        identity_id=identity_id,
        state="active",
        role="org_owner",
        membership_source="org_owner_approved",
        approved_by=identity_id,
        org_type_in_database="demo",
    )
    assert result["storage_allowed"] is False
    assert (
        "self_approval_needs_a_connection_to_prove_it_is_the_first_membership"
        in result["blocked_reasons"]
    )


def test_a_source_needing_no_approver_does_not_need_one(bootstrap_db):
    """The permitted branch of the approver rule, so it is not vacuous."""
    identity_id = _identity(bootstrap_db)["identity_id"]
    result = _membership(
        bootstrap_db,
        identity_id,
        membership_source="verified_directory",
        approved_by=None,
    )
    assert result["rows_written"] == 1
    assert result["self_approved"] is False


# ---------------------------------------------------------------------------
# resolution: an organization comes from a membership row and nothing else
# ---------------------------------------------------------------------------


def test_an_identity_alone_resolves_no_organization(bootstrap_db):
    """A Google account is not a membership. Login one proved this for real."""
    identity_id = _identity(bootstrap_db)["identity_id"]
    result = res_svc.resolve_session_organization(
        connection=bootstrap_db, identity_id=identity_id
    )
    assert result["organization_id_resolved"] is False
    assert result["membership_verified"] is False
    assert "identity_has_no_active_membership" in result["blocked_reasons"]
    assert res_svc.resolution_invariant_failures(result) == []


def test_an_email_domain_resolves_no_organization(bootstrap_db):
    """There is no parameter for it, and no column read from it.

    Gate 112 settled this and `gmail.com` is not a Tribe. Asserted structurally
    because a test that passed an email domain and watched it be ignored would
    pass just as well if the parameter were added later.
    """
    import inspect

    params = set(inspect.signature(res_svc.resolve_session_organization).parameters)
    assert params == {"connection", "identity_id", "now"}

    source = inspect.getsource(res_svc.resolve_session_organization)
    assert "email" not in source


def test_a_membership_resolves_exactly_one_organization(bootstrap_db):
    identity_id = _identity(bootstrap_db)["identity_id"]
    _membership(bootstrap_db, identity_id)
    result = res_svc.resolve_session_organization(
        connection=bootstrap_db, identity_id=identity_id
    )
    assert result["organization_id_resolved"] is True
    assert result["organization_id"] == DEMO_ORG
    assert result["membership_verified"] is True
    assert result["is_demo"] is True
    assert result["roles"] == ["org_owner"]
    assert res_svc.resolution_invariant_failures(result) == []


def test_two_active_memberships_resolve_nothing(bootstrap_db):
    """Picking one would be picking whose data the session may read."""
    identity_id = _identity(bootstrap_db)["identity_id"]
    _membership(bootstrap_db, identity_id)
    # A second organization typed demo, so the refusal is about the count
    # rather than about the organization type.
    other = "cccccccc-dddd-eeee-ffff-000000000000"
    bootstrap_db.execute(
        sa.insert(ORGANIZATIONS).values(
            id=uuid.UUID(other), org_type="demo", seat_cap=5, created_at=NOW
        )
    )
    _membership(
        bootstrap_db,
        identity_id,
        organization_id=other,
        membership_source="verified_directory",
        approved_by=None,
    )
    result = res_svc.resolve_session_organization(
        connection=bootstrap_db, identity_id=identity_id
    )
    assert result["organization_id_resolved"] is False
    assert "identity_has_multiple_active_memberships" in result["blocked_reasons"]


def test_a_revoked_or_expired_membership_resolves_nothing(bootstrap_db):
    """`state='active'` and an expiry in the past can both be true at once."""
    identity_id = _identity(bootstrap_db)["identity_id"]
    _membership(bootstrap_db, identity_id)
    bootstrap_db.execute(
        sa.update(boot_svc.MEMBERSHIPS).values(expires_at=NOW - timedelta(days=1))
    )
    result = res_svc.resolve_session_organization(
        connection=bootstrap_db, identity_id=identity_id, now=NOW
    )
    assert result["organization_id_resolved"] is False

    bootstrap_db.execute(
        sa.update(boot_svc.MEMBERSHIPS).values(expires_at=None, revoked_at=NOW)
    )
    revoked = res_svc.resolve_session_organization(
        connection=bootstrap_db, identity_id=identity_id, now=NOW
    )
    assert revoked["organization_id_resolved"] is False


def test_a_disabled_identity_resolves_nothing(bootstrap_db):
    identity_id = _identity(bootstrap_db)["identity_id"]
    _membership(bootstrap_db, identity_id)
    bootstrap_db.execute(sa.update(boot_svc.IDENTITIES).values(disabled_at=NOW))
    result = res_svc.resolve_session_organization(
        connection=bootstrap_db, identity_id=identity_id
    )
    assert result["organization_id_resolved"] is False
    assert "identity_is_disabled" in result["blocked_reasons"]
    assert res_svc.resolution_invariant_failures(result) == []


# ---------------------------------------------------------------------------
# the binding, and the verified binding that a demo organization cannot have
# ---------------------------------------------------------------------------


def test_a_demo_organization_cannot_hold_a_verified_binding(bootstrap_db):
    """Gate 113's contract, and the reason `verified_operational_binding` is false.

    The authorization was demo-only. A demo binding may not carry a verifier and
    may not be a `verified_binding`, so the only storable status is
    `demo_fixture` - which is not a verified operational binding, by design.
    """
    identity_id = _identity(bootstrap_db)["identity_id"]
    result = binding_svc.insert_binding(
        connection=bootstrap_db,
        organization_id=DEMO_ORG,
        tenant_id="nf-dev-demo-tenant",
        customer_org_id="nf-dev-demo-customer-org",
        binding_status="verified_binding",
        binding_source="admin_verified",
        binding_confidence="verified",
        verified_by_identity_id=identity_id,
        verified_at=NOW.isoformat(),
        is_demo=True,
        human_review_required=False,
    )
    assert result["rows_written"] == 0
    assert result["production_verified_binding"] is False
    assert "demo_fixture_binding_cannot_carry_a_verifier" in result["blocked_reasons"]
    assert "demo_fixture_cannot_be_a_verified_binding" in result["blocked_reasons"]


def test_the_demo_fixture_binding_is_written_and_names_no_verifier(bootstrap_db):
    result = binding_svc.insert_binding(
        connection=bootstrap_db,
        organization_id=DEMO_ORG,
        tenant_id="nf-dev-demo-tenant",
        customer_org_id="nf-dev-demo-customer-org",
        binding_status="demo_fixture",
        binding_source="demo_fixture",
        binding_confidence="demo_only",
        is_demo=True,
        human_review_required=False,
        created_at=NOW,
    )
    assert result["rows_written"] == 1
    assert result["demo_fixture"] is True
    assert result["production_verified_binding"] is False
    assert result["verified_by_identity_id"] is None
    assert result["real_customer_rows_written"] == 0


def test_a_label_cannot_anchor_a_binding(bootstrap_db):
    """`tenant_id`, `customer_org_id` and `organization_profile_id` never select."""
    for kwargs in (
        {"organization_id": "", "tenant_id": "nf-dev-demo-tenant"},
        {"organization_id": "nf-dev-demo-tenant"},
        {"organization_id": DEMO_ORG, "organization_profile_id": str(uuid.uuid4())},
    ):
        fields = {
            "tenant_id": "nf-dev-demo-tenant",
            "customer_org_id": "nf-dev-demo-customer-org",
            "binding_status": "demo_fixture",
            "binding_source": "demo_fixture",
            "binding_confidence": "demo_only",
            "is_demo": True,
        }
        fields.update(kwargs)
        result = binding_svc.insert_binding(connection=bootstrap_db, **fields)
        assert result["rows_written"] == 0
        assert result["blocked_reasons"]


# ---------------------------------------------------------------------------
# the two activation gates that used to be literals
# ---------------------------------------------------------------------------


def test_no_connection_means_no_evidence():
    """What keeps the activation gate deterministic for committed artifacts."""
    result = evidence_svc.build_binding_evidence()
    assert result["org_binding_passed"] is False
    assert result["callback_session_validated"] is False
    assert result["blocked_reasons"] == ["no_connection_supplied"]
    assert evidence_svc.evidence_invariant_failures(result) == []


def test_evidence_needs_a_resolvable_identity(bootstrap_db):
    identity_id = _identity(bootstrap_db)["identity_id"]
    bare = evidence_svc.build_binding_evidence(connection=bootstrap_db)
    assert bare["org_binding_passed"] is False
    assert "no_identity_resolves_to_an_organization" in bare["blocked_reasons"]

    _membership(bootstrap_db, identity_id)
    bound = evidence_svc.build_binding_evidence(connection=bootstrap_db)
    assert bound["org_binding_passed"] is True
    # No state has been consumed in this database, so the stricter gate holds.
    assert bound["callback_session_validated"] is False
    assert evidence_svc.evidence_invariant_failures(bound) == []


def test_callback_session_validated_needs_a_consumed_state():
    """The half a script cannot manufacture.

    Only a callback can spend a redirect state. Without that requirement this
    gate would be satisfiable by inserting two rows.
    """
    forged = {
        "connection_supplied": True,
        "org_binding_passed": True,
        "resolvable_identities": 1,
        "active_membership_rows": 1,
        "consumed_redirect_state_rows": 0,
        "callback_session_validated": True,
    }
    assert (
        "callback_session_validated_without_a_consumed_state"
        in evidence_svc.evidence_invariant_failures(forged)
    )


def test_the_activation_gate_stays_false_without_evidence():
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )

    gate = build_customer_auth_activation_gate()
    assert gate["org_binding_passed"] is False
    assert gate["callback_session_validated"] is False
    assert gate["customer_auth_live"] is False
    assert gate["login_live"] is False


def test_evidence_cannot_turn_customer_auth_live_on_by_itself():
    """Two gates moving is not sixteen gates and an owner's approval."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )

    gate = build_customer_auth_activation_gate(
        binding_evidence={
            "org_binding_passed": True,
            "callback_session_validated": True,
        }
    )
    assert gate["org_binding_passed"] is True
    assert gate["callback_session_validated"] is True
    assert gate["customer_auth_live"] is False
    assert gate["login_live"] is False


# ---------------------------------------------------------------------------
# the routes
# ---------------------------------------------------------------------------


@pytest.fixture
def live_app(monkeypatch):
    """The application, against the suite's database, with a signing key."""
    from nativeforge.db.session import SessionLocal
    from nativeforge.lib.settings import get_settings
    from nativeforge.main import app

    monkeypatch.setenv("NF_SESSION_SIGNING_KEY", TEST_SIGNING_KEY)
    get_settings.cache_clear()

    with SessionLocal() as s:
        for table in (
            "nf_org_memberships",
            "nf_identities",
            "nf_tenant_customer_org_bindings",
        ):
            s.execute(sa.text(f"DELETE FROM {table}"))
        s.execute(sa.text("DELETE FROM organizations"))
        s.execute(
            sa.text(
                "INSERT INTO organizations (id, org_type, seat_cap, created_at) "
                "VALUES (:i, 'demo', 5, :t)"
            ),
            {"i": uuid.UUID(DEMO_ORG).hex, "t": NOW},
        )
        s.commit()

    with TestClient(app) as client:
        yield client

    with SessionLocal() as s:
        for table in (
            "nf_org_memberships",
            "nf_identities",
            "nf_tenant_customer_org_bindings",
        ):
            s.execute(sa.text(f"DELETE FROM {table}"))
        s.execute(sa.text("DELETE FROM organizations"))
        s.commit()
    get_settings.cache_clear()


def _seed_bound_identity():
    """One identity with one active membership, in the suite's database."""
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as s:
        conn = s.connection()
        identity = _identity(conn, subject="route-subject")
        _membership(conn, identity["identity_id"])
        s.commit()
    return identity["identity_id"]


def _session_cookie(identity_id, organization_id=DEMO_ORG, roles=("org_owner",)):
    from nativeforge.services.customer_session_format_service import build_session

    issued = int(NOW.timestamp())
    built = build_session(
        principal_id=identity_id,
        subject=identity_id,
        organization_id=organization_id,
        roles=list(roles),
        issued_at=issued,
        expires_at=issued + 3600,
        auth_source="oidc_authorization_code",
        session_id=str(uuid.uuid4()),
        now=issued + 1,
    )
    return built


def test_current_user_is_401_without_a_session(live_app):
    assert live_app.get("/api/auth/current-user").status_code == 401


def test_current_user_is_401_with_a_forged_cookie(live_app):
    live_app.cookies.set("nf_session", "v1.bm90LWEtcGF5bG9hZA.bm90LWEtc2ln")
    assert live_app.get("/api/auth/current-user").status_code == 401


def test_a_session_mints_only_after_a_membership_exists(live_app):
    """Identity, then membership, then a session. Not before."""
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as s:
        conn = s.connection()
        identity = _identity(conn, subject="route-subject")
        s.commit()
    identity_id = identity["identity_id"]

    unbound = _session_cookie(identity_id)
    assert unbound["session_cookie_valid"] is True
    live_app.cookies.set("nf_session", unbound["session_cookie_value"])
    body = live_app.get("/api/auth/current-user").json()
    # The cookie is ours and the principal is real; the organization is not
    # backed by a membership, so none is reported.
    assert body["organization_id"] is None
    assert body["membership_verified"] is False

    with SessionLocal() as s:
        conn = s.connection()
        _membership(conn, identity_id)
        s.commit()

    body = live_app.get("/api/auth/current-user").json()
    assert body["organization_id"] == DEMO_ORG
    assert body["membership_verified"] is True
    assert body["roles"] == ["org_owner"]


def test_current_user_answers_with_the_organization_and_the_role(live_app):
    identity_id = _seed_bound_identity()
    built = _session_cookie(identity_id)
    live_app.cookies.set("nf_session", built["session_cookie_value"])

    response = live_app.get("/api/auth/current-user")
    assert response.status_code == 200
    body = response.json()
    assert body["authenticated"] is True
    assert body["organization_id"] == DEMO_ORG
    assert body["organization_id_resolved"] is True
    assert body["membership_verified"] is True
    assert body["least_privilege_role"] == "org_owner"


def test_a_cookie_claiming_another_organization_authorizes_nothing(live_app):
    """The defect Gate 132's own probe caught.

    A first pass read `organization_id` out of the cookie payload, so a session
    naming an organization the holder does not belong to came back reported as
    that organization. Declared, not derived.
    """
    identity_id = _seed_bound_identity()
    built = _session_cookie(identity_id, organization_id=REAL_ORG)
    live_app.cookies.set("nf_session", built["session_cookie_value"])

    body = live_app.get("/api/auth/current-user").json()
    assert body["organization_id"] is None
    assert body["membership_verified"] is False
    assert body["roles"] == []


def test_a_cookie_signed_with_another_key_is_refused(live_app):
    """A session cannot be forged without the signing key."""
    identity_id = _seed_bound_identity()
    from nativeforge.services.customer_session_format_service import build_session

    issued = int(NOW.timestamp())
    forged = build_session(
        principal_id=identity_id,
        organization_id=DEMO_ORG,
        roles=["org_owner"],
        issued_at=issued,
        expires_at=issued + 3600,
        auth_source="oidc_authorization_code",
        session_id=str(uuid.uuid4()),
        signing_key="a-different-key-entirely-" + ("q" * 40),
        now=issued + 1,
    )
    live_app.cookies.set("nf_session", forged["session_cookie_value"])
    assert live_app.get("/api/auth/current-user").status_code == 401


def test_no_token_reaches_the_session_or_current_user(live_app):
    """Tokens are locals in the callback. Nothing carries them outward."""
    identity_id = _seed_bound_identity()
    built = _session_cookie(identity_id)

    # The session payload itself.
    import base64

    payload = json.loads(
        base64.urlsafe_b64decode(built["session_cookie_value"].split(".")[1] + "==")
    )
    assert payload["email_omitted"] is True
    for key, value in payload.items():
        assert isinstance(key, str)
        if isinstance(value, str):
            assert "@" not in value

    live_app.cookies.set("nf_session", built["session_cookie_value"])
    body = live_app.get("/api/auth/current-user").json()

    # A token is a value, never a key. Gate 131 was bitten eight times by
    # matching a marker against a field NAME whose job was asserting absence.
    def _values(node):
        if isinstance(node, dict):
            for item in node.values():
                yield from _values(item)
        elif isinstance(node, list):
            for item in node:
                yield from _values(item)
        elif isinstance(node, str):
            yield node

    for value in _values(body):
        assert "ey" != value[:2] or "." not in value, value
        assert built["session_cookie_value"] not in value
    assert body["email"] is None
    assert body["subject"] == identity_id


def test_the_response_envelope_no_longer_lies_about_what_happened():
    """Three constants Gate 132 falsified, now derived.

    `real_session_created`, `real_user_created` and `provider_contacted` were
    hardcoded `False` on every response and all three were true when the
    callback ran.
    """
    from nativeforge.api import auth as auth_api

    gate = {
        "customer_auth_live": False,
        "login_live": False,
        "blocked_reasons": [],
        "next_required_actions": [],
    }
    quiet = auth_api._envelope("session", "unauthenticated", gate)
    assert quiet["real_session_created"] is False
    assert quiet["real_user_created"] is False
    assert quiet["provider_contacted"] is False

    loud = auth_api._envelope(
        "callback",
        "session_created",
        gate,
        real_session_created=True,
        real_user_created=True,
        provider_contacted=True,
    )
    assert loud["real_session_created"] is True
    assert loud["real_user_created"] is True
    assert loud["provider_contacted"] is True


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------


def test_the_artifact_set_is_the_one_the_gate_asked_for():
    files = art.build_first_dev_org_binding_artifacts()
    assert set(files) == set(art.ARTIFACT_FILES)
    assert len(art.ARTIFACT_FILES) == 6


def test_artifacts_regenerate_deterministically():
    first = art.build_first_dev_org_binding_artifacts()
    second = art.build_first_dev_org_binding_artifacts()
    assert first == second


def test_artifacts_carry_no_token_cookie_state_or_secret(tmp_path):
    result = art.write_first_dev_org_binding_artifacts(repo_root=tmp_path)
    assert result["file_count"] == 6
    assert result["marker_hits"] == []
    assert result["env_value_hits"] == []
    assert art.first_dev_org_binding_artifact_invariant_failures(result) == []


def test_the_artifact_scan_would_catch_an_environment_value(monkeypatch, tmp_path):
    """A scanner nobody has seen fire is a scanner nobody should trust."""
    marker = "nf-gate132-scanner-probe-value"
    monkeypatch.setenv("OIDC_CLIENT_SECRET", marker)

    original = art.build_first_dev_org_binding_artifacts

    def _leaky():
        files = dict(original())
        files["dev_org_binding_result.json"] = json.dumps({"oops": marker})
        return files

    monkeypatch.setattr(art, "build_first_dev_org_binding_artifacts", _leaky)
    with pytest.raises(AssertionError):
        result = art.write_first_dev_org_binding_artifacts(repo_root=tmp_path)
        assert result["env_value_hits"] == [], result["env_value_hits"]


def test_no_artifact_carries_the_provider_subject_or_an_email(tmp_path):
    """The readiness file publishes the marker vocabulary, so it contains every
    marker by design - the same "scanner refusing its own output" shape Gates
    127 and 131 hit. It is exempted from the marker check by name and still
    checked for an address, because listing a marker is not carrying a value."""
    art.write_first_dev_org_binding_artifacts(repo_root=tmp_path)
    out = tmp_path / art.ARTIFACT_DIR
    email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    publishes_the_vocabulary = "auth_readiness_after_binding.json"
    for name in art.ARTIFACT_FILES:
        text = (out / name).read_text(encoding="utf-8")
        assert email.search(text) is None, f"{name} carries an address"
        if name == publishes_the_vocabulary:
            continue
        assert "sub=" not in text
        assert "nf_session=" not in text


def test_the_artifacts_do_not_claim_a_readiness_flag_moved(tmp_path):
    art.write_first_dev_org_binding_artifacts(repo_root=tmp_path)
    readiness = json.loads(
        (tmp_path / art.ARTIFACT_DIR / "auth_readiness_after_binding.json").read_text(
            encoding="utf-8"
        )
    )
    unmoved = readiness["flags_this_gate_did_not_move"]
    assert unmoved == dict.fromkeys(unmoved, False)
    assert readiness["deterministic_gate_no_evidence_supplied"]["login_live"] is False
    assert (
        readiness["deterministic_gate_no_evidence_supplied"]["customer_auth_live"]
        is False
    )


def test_the_recorded_smoke_does_not_claim_a_verified_binding():
    """The demo organization cannot hold one, so the recording must not say it did."""
    assert art.LIVE_SMOKE["binding_verified"] is False
    assert art.LIVE_SMOKE["session_created"] is True
    assert art.LIVE_SMOKE["login_live"] is False
    assert art.LIVE_SMOKE["customer_auth_live"] is False
    assert art.LIVE_SMOKE_BEFORE_MEMBERSHIP["session_created"] is False


# ---------------------------------------------------------------------------
# the service constants against the migrations that own them
# ---------------------------------------------------------------------------


def _migration_source(prefix):
    root = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    matches = sorted(root.glob(f"{prefix}_*.py"))
    assert matches, f"migration {prefix} not found"
    return matches[0].read_text(encoding="utf-8")


def test_the_vocabularies_match_the_migrations_that_enforce_them():
    """A restated constant drifting from its CHECK is this campaign's shape.

    Parsed from the migration rather than imported, because importing an
    Alembic version module runs its module body.
    """
    import ast

    tree = ast.parse(_migration_source("0024"))
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in {"MEMBERSHIP_STATES", "TRUSTED_SOURCES", "ROLES"}:
                found[name] = set(ast.literal_eval(node.value))

    assert found["ROLES"] == set(boot_svc.STORABLE_ROLES)
    assert found["MEMBERSHIP_STATES"] == set(boot_svc.STORABLE_STATES)
    assert found["TRUSTED_SOURCES"] == set(boot_svc.TRUSTED_MEMBERSHIP_SOURCES)

    identities = _migration_source("0023")
    assert "verification_source IN ('oidc_token_signature')" in identities
    assert set(boot_svc.VERIFICATION_SOURCES) == {"oidc_token_signature"}


def test_the_core_tables_carry_the_columns_the_migrations_define():
    """Gate 119C shipped a Core table weaker than production and passed on it."""
    for prefix, table, skip in (
        ("0023", boot_svc.IDENTITIES, set()),
        ("0024", boot_svc.MEMBERSHIPS, set()),
    ):
        source = _migration_source(prefix)
        for column in table.columns:
            assert f'"{column.name}"' in source, f"{table.name}.{column.name}"
        assert skip == set()


def test_a_scratch_database_is_never_the_real_one(bootstrap_db):
    """The fixture is in-memory. A test that wrote to the dev database would
    leave the first real identity binding behind it."""
    url = str(bootstrap_db.engine.url)
    assert url == "sqlite://"
