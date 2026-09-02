"""Gate 134: every route module off `X-NF-Org-Id` and onto a session.

Fourteen modules and 207 routes moved from a header anybody can set to an
organization a membership row proves. The tests are grouped by what they would
catch:

```text
authority    a route reading the header, or a header changing an answer
refusal      a request that should fail closed answering anything
scope        a demo-only route serving a real organization, or the reverse
measurement  a count that is frozen rather than walked
readiness    customer_auth_live moving on the strength of one blocker clearing
artifacts    a secret reaching a file, or a file that will not regenerate
```
"""

from __future__ import annotations

import ast
import json
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.api import customer_org_context_dependency as dep
from nativeforge.services import customer_auth_activation_gate_service as gate_svc
from nativeforge.services import dev_header_exposure_matrix_service as matrix_svc
from nativeforge.services import dev_header_kill_artifact_service as art
from nativeforge.services import dev_org_header_shutdown_readiness_service as shutdown
from tests.session_org_helper import (
    ensure_member,
    ensure_org,
    forged_header_only,
    session_headers,
    session_plus_forged_header,
)

DEMO_ORG = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL_ORG = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER_DEMO_ORG = "cccccccc-dddd-eeee-ffff-000000000000"

#: A converted demo-only route with no side effects, used as the probe. The
#: flag keeps it a read.
DEMO_ROUTE = "/v1/nf/demo/orgs/{org}/discovery/stage12-guided-demo-path"
REAL_ROUTE = "/v1/nf/real/orgs/{org}/discovery/stage12-guided-demo-path"
FLAG = {"nf_stage12_demo": True}


@pytest.fixture
def client():
    from nativeforge.db.session import SessionLocal
    from nativeforge.main import create_app

    def _clear() -> None:
        with SessionLocal() as session:
            session.execute(sa.text("DELETE FROM nf_org_memberships"))
            session.execute(sa.text("DELETE FROM nf_identities"))
            session.execute(sa.text("DELETE FROM organizations"))
            session.commit()

    _clear()
    with TestClient(create_app()) as test_client:
        yield test_client
    _clear()


def _without_timestamps(value):
    """The response with every `timestamp` key dropped, at any depth."""
    if isinstance(value, dict):
        return {
            key: _without_timestamps(item)
            for key, item in value.items()
            if key != "timestamp"
        }
    if isinstance(value, list):
        return [_without_timestamps(item) for item in value]
    return value


# ---------------------------------------------------------------------------
# authority: what a converted route reads
# ---------------------------------------------------------------------------


def test_no_converted_route_module_reads_the_dev_header():
    """Structurally, not by outcome.

    A route that happened to ignore the header today could be made to trust it
    by one edit. None of them has a parameter it could arrive in.
    """
    matrix = matrix_svc.build_dev_header_exposure_matrix(
        repo_root=".", ingress_patterns=["^/api/.*"]
    )
    converted = [
        row["module"]
        for row in matrix["rows"]
        if row["replacement_available"] == "converted"
    ]
    assert len(converted) >= 15

    api = Path("src/nativeforge/api")
    for module in converted:
        source = (api / f"{module}.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        aliases = {
            keyword.value.value
            for node in ast.walk(tree)
            for keyword in getattr(node, "keywords", [])
            if keyword.arg == "alias"
            and isinstance(keyword.value, ast.Constant)
            and isinstance(keyword.value.value, str)
        }
        assert matrix_svc.DEV_HEADER_NAME not in aliases, module


def test_the_central_dependency_has_no_header_parameter():
    """It does not read the header, refuse it, or check it.

    Refusing a header requires reading it, and a dependency that reads it is one
    edit from trusting it.
    """
    source = Path(dep.__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)

    aliases = {
        keyword.value.value
        for node in ast.walk(tree)
        for keyword in getattr(node, "keywords", [])
        if keyword.arg == "alias"
        and isinstance(keyword.value, ast.Constant)
        and isinstance(keyword.value.value, str)
    }
    assert dep.DEV_HEADER_NAME not in aliases

    # The name appears only as the constant naming what is refused, and in prose.
    assignments = {
        node.targets[0].id
        for node in tree.body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and isinstance(node.value, ast.Constant)
        and node.value.value == dep.DEV_HEADER_NAME
    }
    assert assignments == {"DEV_HEADER_NAME"}


def test_a_converted_route_answers_a_session(client):
    identity_id = ensure_member(DEMO_ORG, org_type="demo")
    assert identity_id

    response = client.get(
        DEMO_ROUTE.format(org=DEMO_ORG),
        params=FLAG,
        headers=session_headers(DEMO_ORG),
    )
    assert response.status_code == 200
    assert response.json()["schema_version"] == "nf_stage12_guided_demo_path_v1"


def test_the_organization_comes_from_the_membership_row(client):
    """Not from the URL, and not from anything the caller sends.

    The route's own tenant guard compares the path organization against the
    context; the context comes from the row.
    """
    ensure_member(DEMO_ORG, org_type="demo")
    ensure_org(OTHER_DEMO_ORG, "demo")

    # A member of DEMO_ORG asking for OTHER_DEMO_ORG's URL.
    response = client.get(
        DEMO_ROUTE.format(org=OTHER_DEMO_ORG),
        params=FLAG,
        headers=session_headers(DEMO_ORG),
    )
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# refusal: everything that should fail closed
# ---------------------------------------------------------------------------


def test_an_unauthenticated_request_is_refused(client):
    ensure_member(DEMO_ORG, org_type="demo")
    response = client.get(DEMO_ROUTE.format(org=DEMO_ORG), params=FLAG)
    assert response.status_code == 401
    assert response.json()["detail"]["dev_header_consulted"] is False


def test_the_header_alone_opens_nothing(client):
    """The conversion, asserted as a refusal rather than as an absence.

    The header still exists and still names a real demo organization with a
    real membership. It gets 401 because it authenticates nobody.
    """
    ensure_member(DEMO_ORG, org_type="demo")
    response = client.get(
        DEMO_ROUTE.format(org=DEMO_ORG),
        params=FLAG,
        headers=forged_header_only(DEMO_ORG),
    )
    assert response.status_code == 401


def test_a_forged_header_cannot_override_the_session(client):
    """A real session for one organization, a header naming another.

    The header must change nothing - not the answer, not the status.
    """
    ensure_member(DEMO_ORG, org_type="demo")
    ensure_org(OTHER_DEMO_ORG, "demo")

    clean = client.get(
        DEMO_ROUTE.format(org=DEMO_ORG),
        params=FLAG,
        headers=session_headers(DEMO_ORG),
    )
    forged = client.get(
        DEMO_ROUTE.format(org=DEMO_ORG),
        params=FLAG,
        headers=session_plus_forged_header(DEMO_ORG, OTHER_DEMO_ORG),
    )
    assert clean.status_code == forged.status_code == 200

    # Compared with the clock removed. This body embeds wall-clock audit
    # timestamps, so two identical requests never match byte for byte - a first
    # version of this test compared the whole payloads and was measuring the
    # clock rather than the header.
    assert _without_timestamps(clean.json()) == _without_timestamps(forged.json())

    # And the header cannot open the organization it names, either.
    reach = client.get(
        DEMO_ROUTE.format(org=OTHER_DEMO_ORG),
        params=FLAG,
        headers=session_plus_forged_header(DEMO_ORG, OTHER_DEMO_ORG),
    )
    assert reach.status_code == 404


def test_a_session_without_a_membership_is_refused(client):
    """Authenticated, and still nothing. 403, not 401."""
    from nativeforge.db.session import SessionLocal
    from tests.session_org_helper import session_cookie_value

    ensure_member(DEMO_ORG, org_type="demo")
    cookie = session_cookie_value(DEMO_ORG, org_type="demo")

    with SessionLocal() as session:
        session.execute(sa.text("DELETE FROM nf_org_memberships"))
        session.commit()

    client.cookies.set("nf_session", cookie)
    response = client.get(DEMO_ROUTE.format(org=DEMO_ORG), params=FLAG)
    assert response.status_code == 403
    detail = response.json()["detail"]
    assert dep.NO_MEMBERSHIP in detail["blocked_reasons"]
    assert detail["dev_header_consulted"] is False


def test_a_forged_cookie_is_refused(client):
    ensure_member(DEMO_ORG, org_type="demo")
    client.cookies.set("nf_session", "v1.bm90LWEtcGF5bG9hZA.bm90LWEtc2ln")
    response = client.get(DEMO_ROUTE.format(org=DEMO_ORG), params=FLAG)
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# scope: demo and real stay apart
# ---------------------------------------------------------------------------


def test_a_demo_only_route_refuses_a_real_organization(client):
    ensure_member(REAL_ORG, org_type="real")
    response = client.get(
        DEMO_ROUTE.format(org=REAL_ORG),
        params=FLAG,
        headers=session_headers(REAL_ORG, org_type="real"),
    )
    assert response.status_code == 403
    assert dep.WRONG_ORG_TYPE_DEMO in response.json()["detail"]["blocked_reasons"]


def test_a_real_only_route_refuses_a_demo_organization(client):
    ensure_member(DEMO_ORG, org_type="demo")
    response = client.get(
        REAL_ROUTE.format(org=DEMO_ORG),
        params=FLAG,
        headers=session_headers(DEMO_ORG),
    )
    assert response.status_code == 403
    assert dep.WRONG_ORG_TYPE_REAL in response.json()["detail"]["blocked_reasons"]


def test_a_real_organization_reaches_the_real_route(client):
    """The permitted branch, so the refusals above are not the only reachable ones."""
    ensure_member(REAL_ORG, org_type="real")
    response = client.get(
        REAL_ROUTE.format(org=REAL_ORG),
        params=FLAG,
        headers=session_headers(REAL_ORG, org_type="real"),
    )
    assert response.status_code == 200


def test_the_org_type_comes_from_the_organizations_row(client):
    """Gate 132 made the row the authority; this is where routes read it."""
    ensure_member(DEMO_ORG, org_type="demo")
    headers = session_headers(DEMO_ORG)
    assert (
        client.get(
            DEMO_ROUTE.format(org=DEMO_ORG), params=FLAG, headers=headers
        ).status_code
        == 200
    )

    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        session.execute(
            sa.text("UPDATE organizations SET org_type = 'real' WHERE id = :i"),
            {"i": uuid.UUID(DEMO_ORG).hex},
        )
        session.commit()

    # Same session, same cookie. The row changed, so the answer changed.
    assert (
        client.get(
            DEMO_ROUTE.format(org=DEMO_ORG), params=FLAG, headers=headers
        ).status_code
        == 403
    )


# ---------------------------------------------------------------------------
# measurement: the counts are walked, not frozen
# ---------------------------------------------------------------------------


def test_no_route_consumes_the_dev_header():
    matrix = matrix_svc.build_dev_header_exposure_matrix(
        repo_root=".", ingress_patterns=["^/api/.*"]
    )
    assert matrix["dev_header_route_count"] == 0
    assert matrix["dev_header_modules"] == []
    assert matrix["publicly_routed_dev_header_routes"] == 0
    assert matrix["route_total"] > 200
    assert matrix_svc.matrix_invariant_failures(matrix) == []


def test_the_route_count_decreased_from_what_gate_133_measured():
    matrix = matrix_svc.build_dev_header_exposure_matrix(
        repo_root=".", ingress_patterns=["^/api/.*"]
    )
    assert art.BEFORE["dev_header_routes"] == 207
    assert matrix["dev_header_route_count"] < art.BEFORE["dev_header_routes"]


def test_a_regressed_module_would_be_counted_again(tmp_path):
    """The zero is measured, so it can go back up.

    Without this the zero could be a detector that stopped looking rather than a
    migration that finished.
    """
    module = tmp_path / "regressed_routes.py"
    module.write_text(
        "from nativeforge.api.deps_db import require_real_org_db\n"
        "@router.get('/x')\n"
        "def x(ctx=Depends(require_real_org_db)):\n"
        "    return {}\n",
        encoding="utf-8",
    )
    usage = shutdown.detect_dev_header_route_usage(tmp_path)
    assert usage["module_count"] == 1
    assert usage["modules"] == ["regressed_routes.py"]


def test_the_shutdown_readiness_sees_no_consumers():
    readiness = shutdown.build_dev_header_shutdown_readiness()
    assert readiness["dev_header_used_by_routes"] == 0
    assert readiness["dev_header_route_modules"] == []
    # Gate 134 left the chains standing with nobody calling them. Gate 135
    # deleted them, which is why the provider list is empty too.
    assert readiness["dev_header_provider_modules"] == []
    assert shutdown.shutdown_readiness_invariant_failures(readiness) == []


def test_the_exposure_matrix_still_detects_the_preview_proxy():
    """Converted is not unreachable. /v1 still reaches the backend."""
    matrix = matrix_svc.build_dev_header_exposure_matrix(
        repo_root=".", ingress_patterns=["^/api/.*"], behind_access=True
    )
    assert "/v1" in matrix["preview_proxy_prefixes"]
    assert "/health" not in matrix["preview_proxy_prefixes"]
    v1_rows = [row for row in matrix["rows"] if row["path_root"] == "/v1"]
    assert v1_rows
    assert all(row["exposure_hop"] == "preview_proxy" for row in v1_rows)


# ---------------------------------------------------------------------------
# readiness: one blocker clearing is not the claim
# ---------------------------------------------------------------------------


def test_the_dev_header_blocker_clears_only_on_a_measurement():
    matrix = matrix_svc.build_dev_header_exposure_matrix(
        repo_root=".", ingress_patterns=["^/api/.*"]
    )
    without = gate_svc.build_customer_auth_activation_gate()
    assert without["dev_header_disabled_for_production"] is False

    with_evidence = gate_svc.build_customer_auth_activation_gate(
        dev_header_exposure=matrix
    )
    assert with_evidence["dev_header_disabled_for_production"] is True
    assert gate_svc.activation_gate_invariant_failures(with_evidence) == []


def test_customer_auth_live_stays_false_with_the_header_gone():
    """Clearing one of three blockers is not the claim."""
    matrix = matrix_svc.build_dev_header_exposure_matrix(
        repo_root=".", ingress_patterns=["^/api/.*"]
    )
    gate = gate_svc.build_customer_auth_activation_gate(dev_header_exposure=matrix)
    assert gate["dev_header_disabled_for_production"] is True
    assert gate["customer_auth_live"] is False
    assert "invite_binding_passed" in gate["missing_auth_gates"]
    assert (
        "owner_has_not_authorized_customer_auth_activation" in gate["blocked_reasons"]
    )


def test_a_remaining_consumer_would_hold_the_blocker_shut():
    """The permitted branch is not the only reachable one."""
    gate = gate_svc.build_customer_auth_activation_gate(
        dev_header_exposure={"route_total": 217, "dev_header_route_count": 3}
    )
    assert gate["dev_header_disabled_for_production"] is False
    assert gate["customer_auth_live"] is False


def test_login_live_is_unaffected_by_the_conversion():
    """The conversion must not have broken the thing Gate 133 made true."""
    gate = gate_svc.build_customer_auth_activation_gate(
        preflight={
            "validation_possible": True,
            "client_secret_present": True,
            "issuer_url_present": True,
            "audience_present": True,
            "jwks_reachable": None,
        },
        route_readiness={
            "callback_route_available": True,
            "session_cookie_policy_available": True,
        },
        signing_key_readiness={"can_sign_production_session": True},
        binding_evidence={
            "org_binding_passed": True,
            "callback_session_validated": True,
        },
        jwks_validation_evidence={
            "issuer_jwks_validated": True,
            "provider_called": True,
        },
        role_mapping_evidence={"role_mapping_passed": True},
        login_activation_decision={"approves_login_live": True},
    )
    assert gate["login_live"] is True
    assert gate["customer_auth_live"] is False
    assert gate_svc.activation_gate_invariant_failures(gate) == []


def test_the_readiness_cycle_is_broken():
    """`route_org_resolution_enforced` required `customer_auth_live`, which
    required the dev header gone, which required this. Nothing could satisfy it.
    """
    from nativeforge.services.customer_auth_route_readiness_service import (
        build_route_readiness,
    )

    ready = build_route_readiness(
        principal_possible=True,
        session_signing_key_present=True,
        signing_key_readiness={"can_sign_production_session": True},
    )
    assert ready["route_org_resolution_enforced"] is True
    assert ready["ready_for_live_login"] is True

    blocked = build_route_readiness(
        principal_possible=False,
        session_signing_key_present=True,
        signing_key_readiness={"can_sign_production_session": True},
    )
    assert blocked["route_org_resolution_enforced"] is False


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------


def test_the_artifact_set_is_the_one_the_gate_asked_for():
    files = art.build_dev_header_kill_artifacts(repo_root=".")
    assert set(files) == set(art.ARTIFACT_FILES)
    assert len(art.ARTIFACT_FILES) == 7


def test_artifacts_regenerate_deterministically():
    first = art.build_dev_header_kill_artifacts(repo_root=".")
    second = art.build_dev_header_kill_artifacts(repo_root=".")
    assert first == second


def test_artifacts_carry_no_token_cookie_state_or_secret(tmp_path):
    result = art.write_dev_header_kill_artifacts(repo_root=tmp_path)
    assert result["file_count"] == 7
    assert result["marker_hits"] == []
    assert result["env_value_hits"] == []
    assert art.dev_header_kill_artifact_invariant_failures(result) == []


def test_the_artifact_scan_would_catch_an_environment_value(monkeypatch, tmp_path):
    marker = "nf-gate134-scanner-probe-value"
    monkeypatch.setenv("OIDC_CLIENT_SECRET", marker)

    original = art.build_dev_header_kill_artifacts

    def _leaky(**kwargs):
        files = dict(original(**kwargs))
        files["session_org_context_smoke.json"] = json.dumps({"oops": marker})
        return files

    monkeypatch.setattr(art, "build_dev_header_kill_artifacts", _leaky)
    result = art.write_dev_header_kill_artifacts(repo_root=tmp_path)
    assert result["env_value_hits"] == [
        "session_org_context_smoke.json:OIDC_CLIENT_SECRET"
    ]
    assert (
        "environment_value_reached_an_artifact"
        in art.dev_header_kill_artifact_invariant_failures(result)
    )


def test_the_before_after_artifact_reports_the_measured_zero(tmp_path):
    art.write_dev_header_kill_artifacts(repo_root=tmp_path)
    payload = json.loads(
        (
            tmp_path / art.ARTIFACT_DIR / "dev_header_conversion_before_after.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["before"]["dev_header_routes"] == 207
    assert payload["after"]["dev_header_routes"] == 0
    assert payload["after"]["measured_on_every_call"] is True
    assert payload["converted_in_this_gate"]["modules"] == 14
    assert payload["rows_written_by_this_gate"] == 0
    assert payload["fake_sessions_created"] is False


def test_the_remaining_consumers_csv_is_a_header_and_nothing_else(tmp_path):
    art.write_dev_header_kill_artifacts(repo_root=tmp_path)
    text = (
        tmp_path / art.ARTIFACT_DIR / "dev_header_remaining_consumers.csv"
    ).read_text(encoding="utf-8")
    lines = [line for line in text.strip().split("\n") if line]
    assert lines == [",".join(matrix_svc.MATRIX_COLUMNS)]


def test_the_readiness_artifact_claims_nothing_new(tmp_path):
    art.write_dev_header_kill_artifacts(repo_root=tmp_path)
    payload = json.loads(
        (
            tmp_path
            / art.ARTIFACT_DIR
            / "customer_auth_readiness_after_dev_header_conversion.json"
        ).read_text(encoding="utf-8")
    )
    unmoved = payload["flags_this_gate_did_not_move"]
    assert unmoved == dict.fromkeys(unmoved, False)
    assert payload["gate_with_measured_exposure"]["customer_auth_live"] is False
    assert payload["gate_with_measured_exposure"]["dev_header_routes_measured"] == 0
