"""Gate 133: login_live becomes honest, and the dev-header kill begins.

Three facts that were literals became measurements, one approval was split into
the two decisions it had been standing in for, and the first of fifteen
dev-header route modules moved onto a session.

The tests are grouped by what they would catch:

```text
evidence     a token, a key, a subject or a claim reaching a stored row
derivation   a gate satisfied by a constant instead of by a row
authority    a role or an organization coming from a cookie, a header or an email
scope        one approval quietly covering a second, broader decision
exposure     a detector modelling one hop of two, or a plan that omits a module
artifacts    a secret reaching a file, or a file that will not regenerate
```
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from pathlib import Path

import pytest
import sqlalchemy as sa

from nativeforge.services import customer_auth_activation_gate_service as gate_svc
from nativeforge.services import (
    customer_auth_jwks_validation_evidence_service as jwks_svc,
)
from nativeforge.services import (
    customer_auth_owner_activation_decision_service as owner_svc,
)
from nativeforge.services import (
    customer_auth_role_mapping_evidence_service as role_svc,
)
from nativeforge.services import dev_header_exposure_matrix_service as matrix_svc
from nativeforge.services import dev_org_membership_bootstrap_service as boot_svc
from nativeforge.services import login_live_dev_header_kill_artifact_service as art

DEMO_ORG = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL_ORG = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
ISSUER = "https://accounts.google.com"
NOW = datetime(2026, 9, 1, 12, 0, 0, tzinfo=UTC)

#: A compact JWS shape. Never a real token; it exists to be refused.
FAKE_TOKEN = "eyJhbGciOiJSUzI1NiJ9.eyJzdWIiOiIxMjMifQ.c2lnbmF0dXJl"

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
def evidence_db():
    """Organizations, identities, memberships and validation events."""
    engine = sa.create_engine("sqlite://")
    ORGANIZATIONS.create(engine)
    boot_svc.IDENTITIES.create(engine)
    boot_svc.MEMBERSHIPS.create(engine)
    jwks_svc.VALIDATION_EVENTS.create(engine)
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


def _verified(**overrides):
    """What `verify_oidc_token` returns on success, subject and email included."""
    result = {
        "state": "verified",
        "verified": True,
        "subject": "a-real-provider-subject",
        "email": "someone@example.test",
        "email_verified": True,
        "issuer": ISSUER,
        "audience": "000000000000-notarealclient.apps.googleusercontent.com",
        "kid": "abc123kid",
        "algorithm": "RS256",
        "verification_source": "oidc_token_signature",
    }
    result.update(overrides)
    return result


def _jwks_fetch(ok=True):
    return {
        "ok": ok,
        "jwks": {"keys": [{"kid": "abc123kid", "kty": "RSA"}]} if ok else None,
        "network_access_attempted": ok,
    }


def _bound_identity(conn, subject="gate133-subject", organization_id=DEMO_ORG):
    identity = boot_svc.upsert_identity(
        connection=conn,
        issuer=ISSUER,
        subject=subject,
        email_verified=True,
        verification_source="oidc_token_signature",
        now=NOW,
    )
    boot_svc.insert_membership(
        connection=conn,
        organization_id=organization_id,
        identity_id=identity["identity_id"],
        state="active",
        role="org_owner",
        membership_source="verified_directory",
        approved_by=None,
        now=NOW,
    )
    return identity["identity_id"]


# ---------------------------------------------------------------------------
# evidence: what a stored row may hold
# ---------------------------------------------------------------------------


def test_the_validation_event_stores_no_token_subject_or_claim():
    """The verification result carries a subject and an email. The row cannot."""
    result = jwks_svc.build_validation_event(
        verification=_verified(), jwks_fetch=_jwks_fetch(), provider_called=True
    )
    event = result["event"]

    assert set(event) == set(jwks_svc.EVENT_FIELDS)
    for forbidden in jwks_svc.FORBIDDEN_EVENT_KEYS:
        assert forbidden not in event

    blob = json.dumps(event)
    assert "a-real-provider-subject" not in blob
    assert "someone@example.test" not in blob
    assert "apps.googleusercontent.com" not in blob
    assert "abc123kid" not in blob, "the kid is fingerprinted, not stored"
    assert jwks_svc.event_invariant_failures(result) == []


def test_a_token_shaped_value_in_an_event_fires_the_invariant():
    """A scanner nobody has seen fire is a scanner nobody should trust.

    Matched on the value, not the key: Gate 131 was bitten eight times by
    matching a marker against a field NAME whose job was asserting absence.
    """
    result = jwks_svc.build_validation_event(
        verification=_verified(), jwks_fetch=_jwks_fetch(), provider_called=True
    )
    result["event"]["algorithm"] = FAKE_TOKEN
    fails = jwks_svc.event_invariant_failures(result)
    assert "event_carries_a_token_in:algorithm" in fails

    leaky = jwks_svc.build_validation_event(
        verification=_verified(), jwks_fetch=_jwks_fetch(), provider_called=True
    )
    leaky["event"]["issuer"] = "someone@example.test"
    assert "event_carries_an_email_in:issuer" in jwks_svc.event_invariant_failures(
        leaky
    )


def test_the_event_is_written_and_read_back_as_evidence(evidence_db):
    written = jwks_svc.record_validation_evidence(
        connection=evidence_db,
        verification=_verified(),
        jwks_fetch=_jwks_fetch(),
        provider_called=True,
        now=NOW,
    )
    assert written["rows_written"] == 1

    evidence = jwks_svc.build_jwks_validation_evidence(connection=evidence_db)
    assert evidence["issuer_jwks_validated"] is True
    assert evidence["issuers_validated"] == [ISSUER]
    assert evidence["provider_called"] is True
    assert jwks_svc.validation_evidence_invariant_failures(evidence) == []


def test_a_failed_verification_records_an_event_that_validates_nothing(evidence_db):
    written = jwks_svc.record_validation_evidence(
        connection=evidence_db,
        verification=_verified(state="signature_invalid", verified=False),
        jwks_fetch=_jwks_fetch(),
        provider_called=True,
        now=NOW,
    )
    assert written["rows_written"] == 1

    evidence = jwks_svc.build_jwks_validation_evidence(connection=evidence_db)
    assert evidence["event_rows"] == 1
    assert evidence["verified_event_rows"] == 0
    assert evidence["issuer_jwks_validated"] is False
    assert "no_verified_validation_event_recorded" in evidence["blocked_reasons"]


def test_an_offline_verification_is_not_a_live_validation(evidence_db):
    """A verified event that never reached the provider is a replay, not a check."""
    jwks_svc.record_validation_evidence(
        connection=evidence_db,
        verification=_verified(),
        jwks_fetch=_jwks_fetch(),
        provider_called=False,
        now=NOW,
    )
    evidence = jwks_svc.build_jwks_validation_evidence(connection=evidence_db)
    assert evidence["issuer_jwks_validated"] is False
    assert "no_validation_event_reached_the_provider" in evidence["blocked_reasons"]


def test_a_verified_event_without_a_jwks_document_is_refused():
    result = jwks_svc.build_validation_event(
        verification=_verified(), jwks_fetch=_jwks_fetch(ok=False), provider_called=True
    )
    assert result["storage_allowed"] is False
    assert "verified_without_a_jwks_document" in result["blocked_reasons"]


def test_no_connection_means_no_jwks_evidence():
    """What keeps the activation gate deterministic for committed artifacts."""
    evidence = jwks_svc.build_jwks_validation_evidence()
    assert evidence["issuer_jwks_validated"] is False
    assert evidence["blocked_reasons"] == ["no_connection_supplied"]


def test_the_service_vocabulary_matches_the_migration():
    """A restated constant drifting from its CHECK is this campaign's shape."""
    import ast

    root = Path(__file__).resolve().parents[1] / "alembic" / "versions"
    source = (root / "0037_nf_auth_validation_events.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    found = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
            name = node.targets[0].id
            if name in {"EVIDENCE_SOURCES", "VERIFICATION_STATES"}:
                found[name] = set(ast.literal_eval(node.value))

    assert found["EVIDENCE_SOURCES"] == set(jwks_svc.EVIDENCE_SOURCES)
    assert found["VERIFICATION_STATES"] == set(jwks_svc.VERIFICATION_STATES)

    for column in jwks_svc.VALIDATION_EVENTS.columns:
        assert f'"{column.name}"' in source, column.name


# ---------------------------------------------------------------------------
# authority: where a role and an organization come from
# ---------------------------------------------------------------------------


def test_role_mapping_comes_from_the_membership_row(evidence_db):
    _bound_identity(evidence_db)
    evidence = role_svc.build_role_mapping_evidence(connection=evidence_db)

    assert evidence["role_mapping_source"] == "nf_org_memberships"
    assert evidence["role_mapping_passed"] is True
    assert evidence["mapped_identities"] == 1
    assert evidence["mapped_organizations"] == [DEMO_ORG]
    assert evidence["roles_observed"] == ["org_owner"]
    assert evidence["role_sources_observed"] == ["membership_record"]
    assert role_svc.role_mapping_invariant_failures(evidence) == []


def test_a_cookie_claim_cannot_override_the_membership_row(evidence_db):
    """Gate 132's cross-tenant fix, asserted by exercise rather than by comment.

    A claim is offered to the resolver. It has no parameter for one, so the call
    raises and the answer is no. If somebody adds one, this reports True and the
    invariant fires.
    """
    identity_id = _bound_identity(evidence_db)
    assert (
        role_svc._cookie_claim_can_override(evidence_db, identity_id, DEMO_ORG) is False
    )

    evidence = role_svc.build_role_mapping_evidence(connection=evidence_db)
    assert evidence["cookie_claim_can_override_membership"] is False

    forged = dict(evidence)
    forged["cookie_claim_can_override_membership"] = True
    assert (
        "role_mapping_passed_while_a_cookie_claim_could_override"
        in role_svc.role_mapping_invariant_failures(forged)
    )


def test_an_email_domain_cannot_map_a_role_or_an_organization():
    """Structural, because a test that passes an email and watches it be ignored
    would pass just as well if the parameter were added later.

    Checked as *attribute access on the membership table*, not as the substring
    "email": both of these modules carry field names like
    `email_domain_can_map_a_role`, whose job is asserting the absence. Ninth
    time this campaign has had to separate a substring from a meaning.
    """
    import ast
    import inspect

    from nativeforge.services.identity_org_session_resolution_service import (
        resolve_session_organization,
    )

    parameters = set(inspect.signature(resolve_session_organization).parameters)
    assert parameters == {"connection", "identity_id", "now"}
    assert "email" not in set(
        inspect.signature(role_svc.build_role_mapping_evidence).parameters
    )

    for function in (
        resolve_session_organization,
        role_svc.build_role_mapping_evidence,
    ):
        tree = ast.parse(inspect.getsource(function).lstrip())
        read = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
        assert "email" not in read, function.__name__
        subscripts = {
            node.slice.value
            for node in ast.walk(tree)
            if isinstance(node, ast.Subscript)
            and isinstance(node.slice, ast.Constant)
            and isinstance(node.slice.value, str)
        }
        assert not {key for key in subscripts if "email" in key}, function.__name__


@pytest.mark.parametrize(
    ("column", "value", "reason"),
    [
        ("role_source", "token_claim", "role_source_not_trusted:token_claim"),
        ("role_source", "email_domain", "role_source_not_trusted:email_domain"),
        ("role_source", "client_header", "role_source_not_trusted:client_header"),
        (
            "membership_source",
            "email_domain_only",
            "membership_source_not_trusted:email_domain_only",
        ),
        (
            "membership_source",
            "dev_header",
            "membership_source_not_trusted:dev_header",
        ),
    ],
)
def test_an_untrusted_source_maps_nothing_and_says_which(
    evidence_db, column, value, reason
):
    """The resolver refuses first; the evidence names what it saw on the row.

    An earlier version of the evidence builder re-checked these *after* asking
    the resolver, which had already dropped the row - so the named refusals were
    unreachable and read as coverage. Gate 126 settled that a guard which cannot
    fire is worse than none.
    """
    identity_id = _bound_identity(evidence_db)
    evidence_db.execute(
        sa.update(boot_svc.MEMBERSHIPS)
        .where(boot_svc.MEMBERSHIPS.c.identity_id == uuid.UUID(identity_id))
        .values(**{column: value})
    )
    evidence = role_svc.build_role_mapping_evidence(connection=evidence_db)
    assert evidence["role_mapping_passed"] is False
    assert reason in evidence["blocked_reasons"]


def test_a_membership_with_no_role_maps_nobody(evidence_db):
    identity_id = _bound_identity(evidence_db)
    evidence_db.execute(
        sa.update(boot_svc.MEMBERSHIPS)
        .where(boot_svc.MEMBERSHIPS.c.identity_id == uuid.UUID(identity_id))
        .values(role=None)
    )
    evidence = role_svc.build_role_mapping_evidence(connection=evidence_db)
    assert evidence["role_mapping_passed"] is False
    assert "active_membership_carries_no_role" in evidence["blocked_reasons"]


def test_no_connection_means_no_role_mapping_evidence():
    evidence = role_svc.build_role_mapping_evidence()
    assert evidence["role_mapping_passed"] is False
    assert evidence["blocked_reasons"] == ["no_connection_supplied"]


# ---------------------------------------------------------------------------
# scope: one approval must not cover the other decision
# ---------------------------------------------------------------------------


def test_the_owner_decision_is_demo_scoped():
    decision = owner_svc.build_owner_activation_decision(
        organization_id=DEMO_ORG, provider=ISSUER, app_env="dev"
    )
    assert decision["approves_login_live"] is True
    assert decision["organization_in_scope"] is True
    assert decision["blocked_reasons"] == []
    assert owner_svc.decision_invariant_failures(decision) == []


def test_the_owner_decision_refuses_the_real_organization():
    decision = owner_svc.build_owner_activation_decision(
        organization_id=REAL_ORG, provider=ISSUER, app_env="dev"
    )
    assert decision["approves_login_live"] is False
    assert (
        "organization_is_the_explicitly_refused_real_org" in decision["blocked_reasons"]
    )


def test_the_owner_decision_refuses_production():
    for environment in ("production", "prod", "", "staging"):
        decision = owner_svc.build_owner_activation_decision(
            organization_id=DEMO_ORG, provider=ISSUER, app_env=environment
        )
        assert decision["approves_login_live"] is False, environment
        assert any(
            reason.startswith("environment_outside_the_approved_scope")
            for reason in decision["blocked_reasons"]
        )


def test_the_owner_decision_refuses_another_provider():
    decision = owner_svc.build_owner_activation_decision(
        organization_id=DEMO_ORG,
        provider="https://login.microsoftonline.com",
        app_env="dev",
    )
    assert decision["approves_login_live"] is False


def test_the_owner_decision_can_never_approve_customer_auth():
    """No parameter, no env var, no branch."""
    import inspect

    assert owner_svc.approves_customer_auth_live() is False
    assert inspect.signature(owner_svc.approves_customer_auth_live).parameters == {}

    for environment in ("dev", "local", "test", "production"):
        decision = owner_svc.build_owner_activation_decision(
            organization_id=DEMO_ORG, provider=ISSUER, app_env=environment
        )
        assert decision["approves_customer_auth_live"] is False

    forged = dict(
        owner_svc.build_owner_activation_decision(
            organization_id=DEMO_ORG, provider=ISSUER, app_env="dev"
        )
    )
    forged["approves_customer_auth_live"] = True
    assert (
        "decision_approved_customer_auth_live"
        in owner_svc.decision_invariant_failures(forged)
    )


def test_the_owner_decision_is_revocable_and_not_grantable(monkeypatch):
    monkeypatch.setenv(owner_svc.REVOCATION_ENV, "true")
    decision = owner_svc.build_owner_activation_decision(
        organization_id=DEMO_ORG, provider=ISSUER, app_env="dev"
    )
    assert decision["revoked"] is True
    assert decision["approves_login_live"] is False

    # One environment variable is read, and it can only turn the decision off.
    # Parsed rather than counted: the module docstring quotes the old
    # `os.environ.get(APPROVAL_ENV, ...)` line it replaced, so a substring count
    # sees two and means one.
    import ast

    tree = ast.parse(Path(owner_svc.__file__).read_text(encoding="utf-8"))
    env_reads = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr == "environ"
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    ]
    assert len(env_reads) == 1

    names = {
        node.id
        for node in ast.walk(tree)
        if isinstance(node, ast.Name) and node.id == "REVOCATION_ENV"
    }
    assert names == {"REVOCATION_ENV"}


def test_the_decision_enumerates_what_it_does_not_approve():
    decision = owner_svc.build_owner_activation_decision(
        organization_id=DEMO_ORG, provider=ISSUER, app_env="dev"
    )
    for claim in (
        "customer_auth_live",
        "production_rollout",
        "real_organization_binding",
        "verified_operational_binding",
        "customer_persistence_live",
    ):
        assert claim in decision["not_approved"]

    short = dict(decision)
    short["not_approved"] = ["customer_auth_live"]
    assert any(
        fail.startswith("not_approved_list_lost_entries")
        for fail in owner_svc.decision_invariant_failures(short)
    )


# ---------------------------------------------------------------------------
# derivation: login_live true only on the facts
# ---------------------------------------------------------------------------


def _login_facts(**overrides):
    """Everything `login_live` needs, injected. No database, no network."""
    facts = {
        "preflight": {
            "validation_possible": True,
            "client_secret_present": True,
            "issuer_url_present": True,
            "audience_present": True,
            "jwks_reachable": None,
        },
        "route_readiness": {
            "callback_route_available": True,
            "session_cookie_policy_available": True,
        },
        "signing_key_readiness": {"can_sign_production_session": True},
        "binding_evidence": {
            "org_binding_passed": True,
            "callback_session_validated": True,
        },
        "jwks_validation_evidence": {
            "issuer_jwks_validated": True,
            "provider_called": True,
        },
        "role_mapping_evidence": {"role_mapping_passed": True},
        "login_activation_decision": {"approves_login_live": True},
        "dev_header_disabled_for_production": False,
        "owner_approval": False,
    }
    facts.update(overrides)
    return gate_svc.build_customer_auth_activation_gate(**facts)


def test_login_live_becomes_true_when_the_measured_facts_pass():
    gate = _login_facts()
    assert gate["login_live"] is True
    assert gate["login_activation_approved"] is True
    assert gate["missing_login_gates"] == []
    assert gate_svc.activation_gate_invariant_failures(gate) == []


def test_login_live_needs_each_of_the_three_new_facts():
    for override, missing in (
        ({"jwks_validation_evidence": {}}, "issuer_jwks_validated"),
        ({"role_mapping_evidence": {}}, "role_mapping_passed"),
    ):
        gate = _login_facts(**override)
        assert gate["login_live"] is False, override
        assert missing in gate["missing_login_gates"]

    no_decision = _login_facts(login_activation_decision={})
    assert no_decision["login_live"] is False
    assert no_decision["missing_login_gates"] == []
    assert any(
        entry["gate"] == "login_activation_decision"
        for entry in no_decision["next_required_actions"]
    )


def test_a_recorded_event_is_the_network_check_the_preflight_cannot_see():
    """The preflight runs offline; the check happened inside a callback."""
    gate = _login_facts()
    assert gate["issuer_jwks_network_check_performed"] is True
    assert gate_svc.activation_gate_invariant_failures(gate) == []

    offline = _login_facts(
        jwks_validation_evidence={
            "issuer_jwks_validated": True,
            "provider_called": False,
        }
    )
    assert offline["issuer_jwks_network_check_performed"] is False


def test_login_live_without_any_approval_fires_the_invariant():
    gate = dict(_login_facts())
    gate["login_activation_approved"] = False
    gate["owner_approval_present"] = False
    assert (
        "login_live_without_a_login_activation_decision"
        in gate_svc.activation_gate_invariant_failures(gate)
    )


def test_customer_auth_live_stays_false_while_the_dev_header_is_exposed():
    gate = _login_facts(owner_approval=True, dev_header_disabled_for_production=False)
    assert gate["login_live"] is True
    assert gate["customer_auth_live"] is False
    assert "dev_header_disabled_for_production" in gate["missing_auth_gates"]
    assert gate_svc.activation_gate_invariant_failures(gate) == []


def test_customer_auth_live_stays_false_on_a_login_only_decision():
    """The narrow approval must not reach the broad claim."""
    gate = _login_facts(
        dev_header_disabled_for_production=True,
        validation={
            "provider_validated": True,
            "callback_session_validated": True,
            "invite_binding_passed": True,
            "org_binding_passed": True,
            "role_mapping_passed": True,
        },
        owner_approval=False,
    )
    assert gate["login_live"] is True
    assert gate["customer_auth_live"] is False
    assert (
        "owner_has_not_authorized_customer_auth_activation" in gate["blocked_reasons"]
    )

    forged = dict(gate)
    forged["customer_auth_live"] = True
    assert (
        "customer_auth_live_on_a_login_only_decision"
        in gate_svc.activation_gate_invariant_failures(forged)
    )


def test_customer_auth_live_stays_false_while_the_verified_binding_is_false():
    """Not a gate in the list, and it must not be read as one.

    `verified_operational_binding` is refused by Gate 113's contract on a demo
    organization, and no gate here can grant it. The artifacts say so and this
    asserts the artifact does.
    """
    readiness = json.loads(
        art.build_login_live_artifacts(repo_root=".")[
            "login_live_readiness_after_gate133.json"
        ]
    )
    unmoved = readiness["flags_this_gate_did_not_move"]
    assert unmoved["verified_operational_binding"] is False
    assert unmoved["customer_auth_live"] is False
    assert unmoved == dict.fromkeys(unmoved, False)


def test_the_deterministic_gate_claims_nothing():
    gate = gate_svc.build_customer_auth_activation_gate()
    assert gate["login_live"] is False
    assert gate["customer_auth_live"] is False
    assert gate["login_activation_approved"] is False
    assert gate["jwks_validation_evidence_supplied"] is False
    assert gate["role_mapping_evidence_supplied"] is False


# ---------------------------------------------------------------------------
# exposure: the hop the containment detector does not model
# ---------------------------------------------------------------------------


def test_the_matrix_detects_a_live_tunnel_config(tmp_path):
    """Every config in the directory, not a chosen filename.

    Gate 130's detector named `~/.cloudflared/config.yml` while the live tunnel
    ran `nativeforge-mayhem.yml`, and reported containment it did not have.
    """
    (tmp_path / "unused.yml").write_text(
        "ingress:\n  - hostname: other.example\n    service: http://127.0.0.1:9999\n",
        encoding="utf-8",
    )
    (tmp_path / "nativeforge-live.yml").write_text(
        "ingress:\n"
        "  - hostname: nf-dev.example\n"
        "    path: ^/api/.*\n"
        "    service: http://127.0.0.1:8000\n"
        "  - hostname: nf-dev.example\n"
        "    service: http://127.0.0.1:5175\n"
        "  - service: http_status:404\n",
        encoding="utf-8",
    )
    patterns = matrix_svc.read_tunnel_backend_paths(detect_root=tmp_path)
    assert patterns == ["^/api/.*"]

    empty = matrix_svc.read_tunnel_backend_paths(detect_root=tmp_path / "absent")
    assert empty == []


def test_the_matrix_reads_the_preview_proxy_not_the_dev_server_proxy():
    """The hop the containment detector misses, and one it must not invent.

    `/health` is proxied to the API by the dev server and deliberately not by
    the preview - the config says so in a comment. A first version of this
    scanner reported it as publicly proxied to the backend, which would have
    shown up in a security matrix as a route that is not there.
    """
    prefixes = matrix_svc.read_preview_proxy_prefixes(repo_root=".")
    assert "/v1" in prefixes
    assert "/health" not in prefixes


def test_the_preview_proxy_is_still_the_hop_the_containment_detector_misses():
    """Gate 133's finding, now that there is nothing left exposed by it.

    This asserted `dev_header_route_count > 0` and that every one of those
    routes was reached through the preview proxy rather than the tunnel ingress
    rule. Gate 134 converted all 207, so the count is zero - and the finding it
    recorded is about the topology, not about the routes, so it is asserted
    against the topology directly.
    """
    matrix = matrix_svc.build_dev_header_exposure_matrix(
        repo_root=".", ingress_patterns=["^/api/.*"], behind_access=True
    )
    assert matrix["dev_header_route_count"] == 0
    assert matrix["exposed_only_via_preview_proxy"] == []
    assert matrix["containment_detector_models_preview_proxy"] is False

    # /v1 still reaches the backend through the preview, and the ingress rule
    # still covers only /api. A converted route is not an unreachable one.
    assert "/v1" in matrix["preview_proxy_prefixes"]
    v1_rows = [row for row in matrix["rows"] if row["path_root"] == "/v1"]
    assert v1_rows
    assert all(row["exposure_hop"] == "preview_proxy" for row in v1_rows)
    assert matrix_svc.matrix_invariant_failures(matrix) == []


def test_the_matrix_refuses_to_report_containment_it_did_not_measure(tmp_path):
    """A matrix that found no way in has failed to read a config."""
    matrix = matrix_svc.build_dev_header_exposure_matrix(
        repo_root=tmp_path, ingress_patterns=[]
    )
    assert (
        "no_exposure_path_detected_so_nothing_was_read"
        in matrix_svc.matrix_invariant_failures(matrix)
    )


def test_isolation_routes_is_converted_and_no_longer_a_consumer():
    matrix = matrix_svc.build_dev_header_exposure_matrix(
        repo_root=".", ingress_patterns=["^/api/.*"]
    )
    assert "isolation_routes" in matrix["converted_modules"]
    assert "isolation_routes" not in matrix["dev_header_modules"]

    row = next(r for r in matrix["rows"] if r["module"] == "isolation_routes")
    assert row["consumes_dev_header"] is False
    assert row["replacement_available"] == "converted"


def test_the_isolation_deps_chain_has_no_route_consumers_left():
    """What makes deleting it a deletion rather than a rewrite."""
    from fastapi.routing import APIRoute

    from nativeforge.main import app

    allowlist_chain = {"get_org_context_dev", "require_demo_org", "require_real_org"}
    consumers = []
    for route in matrix_svc._api_routes(app.routes):
        assert isinstance(route, APIRoute)
        if matrix_svc._dependency_names(route.dependant) & allowlist_chain:
            consumers.append(route.path)
    assert consumers == []


def test_every_remaining_consumer_is_classified_and_ordered():
    matrix = matrix_svc.build_dev_header_exposure_matrix(
        repo_root=".", ingress_patterns=["^/api/.*"]
    )
    dev_rows = [row for row in matrix["rows"] if row["consumes_dev_header"]]
    # Gate 134 converted every module, so there is nothing left to order. The
    # classification still has to hold for whatever remains, which is how this
    # keeps working if a consumer ever comes back.
    orders = sorted(row["recommended_order"] for row in dev_rows)
    assert orders == list(range(1, len(dev_rows) + 1)), "the order is a permutation"
    for row in dev_rows:
        assert row["conversion_risk"] != "unknown", row["module"]
        assert row["conversion_note"] != "not classified", row["module"]

    converted = [
        row for row in matrix["rows"] if row["replacement_available"] == "converted"
    ]
    assert len(converted) >= 15, "every route module is on the session dependency"


def test_the_kill_plan_names_every_remaining_consumer():
    files = art.build_login_live_artifacts(repo_root=".")
    plan = files["dev_header_kill_plan.md"]
    matrix = matrix_svc.build_dev_header_exposure_matrix(
        repo_root=".", ingress_patterns=list(art.LIVE_TUNNEL_INGRESS)
    )
    for module in matrix["dev_header_modules"]:
        assert f"`{module}`" in plan, module


def test_the_exposure_matrix_csv_has_the_declared_columns():
    files = art.build_login_live_artifacts(repo_root=".")
    csv_text = files["dev_header_exposure_matrix.csv"]
    header = csv_text.splitlines()[0]
    assert header == ",".join(matrix_svc.MATRIX_COLUMNS)
    assert len(csv_text.strip().splitlines()) > 1


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------


def test_the_artifact_set_is_the_one_the_gate_asked_for():
    files = art.build_login_live_artifacts(repo_root=".")
    assert set(files) == set(art.ARTIFACT_FILES)
    assert len(art.ARTIFACT_FILES) == 8


def test_artifacts_regenerate_deterministically():
    first = art.build_login_live_artifacts(repo_root=".")
    second = art.build_login_live_artifacts(repo_root=".")
    assert first == second


def test_artifacts_carry_no_token_cookie_state_or_secret(tmp_path):
    result = art.write_login_live_artifacts(repo_root=tmp_path)
    assert result["file_count"] == 8
    assert result["marker_hits"] == []
    assert result["env_value_hits"] == []
    assert art.login_live_artifact_invariant_failures(result) == []


def test_the_artifact_scan_would_catch_an_environment_value(monkeypatch, tmp_path):
    marker = "nf-gate133-scanner-probe-value"
    monkeypatch.setenv("OIDC_CLIENT_SECRET", marker)

    original = art.build_login_live_artifacts

    def _leaky(**kwargs):
        files = dict(original(**kwargs))
        files["role_mapping_evidence.json"] = json.dumps({"oops": marker})
        return files

    monkeypatch.setattr(art, "build_login_live_artifacts", _leaky)
    result = art.write_login_live_artifacts(repo_root=tmp_path)
    assert result["env_value_hits"] == ["role_mapping_evidence.json:OIDC_CLIENT_SECRET"]
    assert (
        "environment_value_reached_an_artifact"
        in art.login_live_artifact_invariant_failures(result)
    )


def test_no_artifact_carries_a_provider_subject_or_an_email(tmp_path):
    import re

    art.write_login_live_artifacts(repo_root=tmp_path)
    out = tmp_path / art.ARTIFACT_DIR
    email = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
    publishes_the_vocabulary = "login_live_readiness_after_gate133.json"
    for name in art.ARTIFACT_FILES:
        text = (out / name).read_text(encoding="utf-8")
        assert email.search(text) is None, f"{name} carries an address"
        if name == publishes_the_vocabulary:
            continue
        assert "nf_session=" not in text
        assert "sub=" not in text


def test_the_recorded_smoke_does_not_claim_customer_auth():
    assert art.LIVE_SMOKE["session_created"] is True
    assert art.LIVE_SMOKE["current_user_status_code"] == 200
    assert art.LIVE_SMOKE["login_live_on_the_next_request"] is True
    assert art.LIVE_SMOKE["customer_auth_live"] is False
    assert art.LIVE_SMOKE["current_user_email_returned"] is False
    assert art.LIVE_REFUSALS["current_user_no_cookie_loopback"] == 401
