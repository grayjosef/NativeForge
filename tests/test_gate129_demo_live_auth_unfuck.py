"""Gate 129: the demo tells the truth, and the auth runtime is reachable.

Two things this gate had to make true at once, and they pull in opposite
directions. The demo has to look like a serious product, and it has to say
plainly that almost none of it is live. Every test here defends the second
against the first.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from nativeforge.lib.settings import (
    AUTH_ENV_KEYS,
    AUTH_SECRET_ENV_KEYS,
    Settings,
    auth_environment_overlay,
    auth_environment_presence,
)
from nativeforge.services import demo_live_operating_shell_artifact_service as art
from nativeforge.services.customer_auth_environment_preflight_service import (
    CALLBACK_ROUTE_PATH,
    build_environment_preflight,
)
from nativeforge.services.customer_demo_operating_shell_service import (
    SECTION_IDS,
    TRUTH_LABELS,
    build_customer_demo_operating_shell,
    operating_shell_invariant_failures,
)

REQUIRED_SECTIONS = (
    "tenant_profile",
    "source_watchlist",
    "weekly_digest",
    "pursuit_pipeline",
    "awarded_grants",
    "award_requirements",
    "proof_audit",
    "document_metadata",
    "readiness_blockers",
    "next_actions",
)

DEMO_JSON = Path("frontend/src/demo/sc_customer_demo.json")


@pytest.fixture
def clean_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in AUTH_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


# ------------------------------------------------- the operating shell


def test_the_shell_has_every_required_section() -> None:
    shell = build_customer_demo_operating_shell()
    assert tuple(shell["section_ids"]) == REQUIRED_SECTIONS
    assert tuple(SECTION_IDS) == REQUIRED_SECTIONS
    assert shell["section_count"] == len(REQUIRED_SECTIONS)


def test_the_shell_carries_every_truth_label() -> None:
    shell = build_customer_demo_operating_shell()
    names = {x["label"] for x in shell["truth_labels"]}
    for label in TRUTH_LABELS:
        assert label in names, label
    assert len(TRUTH_LABELS) == 6


def test_every_truth_label_is_active_today() -> None:
    """Not one of these is a claim the system can currently deny."""
    shell = build_customer_demo_operating_shell()
    assert sorted(shell["active_truth_labels"]) == sorted(TRUTH_LABELS)


def test_the_shell_does_not_claim_auth_is_live() -> None:
    shell = build_customer_demo_operating_shell()
    assert shell["customer_auth_live"] is False
    assert shell["login_live"] is False


def test_the_shell_does_not_claim_live_source_monitoring() -> None:
    shell = build_customer_demo_operating_shell()
    assert shell["live_source_monitoring_active"] is False


def test_the_shell_does_not_claim_email_delivery() -> None:
    shell = build_customer_demo_operating_shell()
    assert shell["email_delivery_active"] is False


def test_the_shell_does_not_claim_an_object_store() -> None:
    shell = build_customer_demo_operating_shell()
    assert shell["object_store_configured"] is False


def test_no_section_is_operational_and_none_holds_a_row() -> None:
    shell = build_customer_demo_operating_shell()
    assert shell["operational_section_count"] == 0
    assert shell["rows_written"] == 0
    for section in shell["sections"]:
        assert section["operational"] is False, section["section_id"]
        assert section["rows_written"] == 0
        assert section["data_source"] == "controlled_demo"


def test_the_shell_reports_no_invariant_failures() -> None:
    assert (
        operating_shell_invariant_failures(build_customer_demo_operating_shell()) == []
    )


# -- the labels are measured, not typed -----------------------------------


def test_a_label_deactivates_when_the_thing_it_names_goes_live() -> None:
    """Otherwise the six labels are six hardcoded strings.

    This is the whole reason `active` is computed. A demo that says AUTH NOT
    LIVE because someone typed it stays wrong forever after auth ships.
    """
    shell = build_customer_demo_operating_shell(
        activation_gate={"customer_auth_live": True, "login_live": True},
    )
    labels = {x["label"]: x["active"] for x in shell["truth_labels"]}
    assert labels["AUTH NOT LIVE"] is False
    assert shell["customer_auth_live"] is True


def test_a_label_that_disagrees_with_its_own_claim_is_refused() -> None:
    shell = build_customer_demo_operating_shell()
    tampered = json.loads(json.dumps(shell))
    tampered["customer_auth_live"] = True  # claim says live, label still active
    assert "label_disagrees_with_claim:AUTH NOT LIVE" in (
        operating_shell_invariant_failures(tampered)
    )


def test_an_operational_section_without_auth_is_refused() -> None:
    shell = build_customer_demo_operating_shell()
    tampered = json.loads(json.dumps(shell))
    tampered["sections"][0]["operational"] = True
    fails = operating_shell_invariant_failures(tampered)
    assert any(f.startswith("operational_without_auth:") for f in fails)


def test_a_shell_reporting_written_rows_is_refused() -> None:
    shell = build_customer_demo_operating_shell()
    tampered = json.loads(json.dumps(shell))
    tampered["rows_written"] = 1
    assert "rows_written_must_be_zero" in operating_shell_invariant_failures(tampered)


# ------------------------------------------------- the committed payload


def test_the_committed_demo_payload_carries_the_shell() -> None:
    payload = json.loads(DEMO_JSON.read_text(encoding="utf-8"))
    shell = payload.get("demo_operating_shell")
    assert shell is not None, "regenerate frontend/src/demo/sc_customer_demo.json"
    assert tuple(shell["section_ids"]) == REQUIRED_SECTIONS
    assert sorted(shell["active_truth_labels"]) == sorted(TRUTH_LABELS)
    assert shell["customer_auth_live"] is False
    assert shell["rows_written"] == 0


# ------------------------------------------------- auth settings plumbing


def test_settings_declares_every_auth_key() -> None:
    """Gate 128 found none of them were declared, so `.env` could not supply
    them and an operator following the runbook changed nothing, silently."""
    aliases = {
        str(f.validation_alias)
        for f in Settings.model_fields.values()
        if f.validation_alias
    }
    for key in AUTH_ENV_KEYS:
        assert key in aliases, key


def test_the_two_secrets_are_secret_typed_and_never_serialize() -> None:
    settings = Settings(
        OIDC_CLIENT_SECRET="client-secret-must-not-appear",
        NF_SESSION_SIGNING_KEY="signing-key-must-not-appear",
    )
    for probe in ("client-secret-must-not-appear", "signing-key-must-not-appear"):
        assert probe not in repr(settings)
        assert probe not in str(settings)
        assert probe not in settings.model_dump_json()
    assert AUTH_SECRET_ENV_KEYS == frozenset(
        {"OIDC_CLIENT_SECRET", "NF_SESSION_SIGNING_KEY"}
    )


def test_settings_backed_keys_are_detected_as_present(clean_auth_env: None) -> None:
    settings = Settings(
        OIDC_ISSUER="https://accounts.google.com",
        OIDC_CLIENT_ID="a-client-id",
        OIDC_CLIENT_SECRET="a-secret",
        NF_SESSION_SIGNING_KEY="a-key",
    )
    presence = auth_environment_presence({}, settings=settings)
    assert presence["OIDC_ISSUER"] is True
    assert presence["OIDC_CLIENT_ID"] is True
    assert presence["OIDC_CLIENT_SECRET"] is True
    assert presence["NF_SESSION_SIGNING_KEY"] is True
    assert presence["OIDC_AUDIENCE"] is False


def test_presence_reports_booleans_and_never_values(clean_auth_env: None) -> None:
    settings = Settings(OIDC_ISSUER="https://issuer.example.test")
    presence = auth_environment_presence({}, settings=settings)
    assert all(isinstance(v, bool) for v in presence.values())
    assert "https://issuer.example.test" not in json.dumps(presence)


def test_os_environ_still_overrides_settings(clean_auth_env: None) -> None:
    """An operator must be able to override the file for one process."""
    settings = Settings(OIDC_ISSUER="https://from-settings.example")
    env = auth_environment_overlay(
        {"OIDC_ISSUER": "https://from-environ.example"}, settings=settings
    )
    assert env["OIDC_ISSUER"] == "https://from-environ.example"


def test_a_blank_value_is_unset_not_configured(clean_auth_env: None) -> None:
    settings = Settings(OIDC_ISSUER="   ")
    assert auth_environment_presence({}, settings=settings)["OIDC_ISSUER"] is False


# ------------------------------------------------- the callback path


def test_the_wrong_callback_path_is_still_blocked() -> None:
    result = build_environment_preflight(
        configured_callback_url="https://nf-dev.mayhem-nc.dev/auth/callback",
    )
    assert result["callback_path_matches_route"] is False
    assert (
        "callback_url_path_does_not_match_any_callback_route"
        in result["blocked_reasons"]
    )


def test_the_correct_callback_path_passes_the_path_check() -> None:
    result = build_environment_preflight(
        configured_callback_url=f"https://nf-dev.mayhem-nc.dev{CALLBACK_ROUTE_PATH}",
    )
    assert result["callback_path_matches_route"] is True
    assert (
        "callback_url_path_does_not_match_any_callback_route"
        not in result["blocked_reasons"]
    )


def test_the_callback_route_exists_in_the_api() -> None:
    """A registered route, not a string in a document.

    Read from the OpenAPI schema rather than by walking `app.routes`. This
    FastAPI version wraps included routers in `_IncludedRouter` objects that
    expose no `.path`, so walking the route list finds only the four docs
    routes and would pass or fail for reasons unrelated to auth.
    """
    from nativeforge.main import create_app

    paths = create_app().openapi()["paths"]
    assert CALLBACK_ROUTE_PATH in paths
    assert "get" in paths[CALLBACK_ROUTE_PATH]
    for path in ("/api/auth/login", "/api/auth/session", "/api/auth/current-user"):
        assert path in paths, path
    assert "post" in paths["/api/auth/logout"]


def test_an_unauthenticated_current_user_is_refused() -> None:
    from fastapi.testclient import TestClient

    from nativeforge.main import create_app

    with TestClient(create_app(), raise_server_exceptions=False) as client:
        response = client.get("/api/auth/current-user")
    assert response.status_code == 401
    body = response.json()["detail"]
    assert body["status"] == "unauthenticated"
    assert body["customer_auth_live"] is False


def test_the_callback_refuses_rather_than_404ing() -> None:
    """404 would mean an OAuth redirect lands nowhere. A named refusal means
    the route exists and says why it will not mint a session."""
    from fastapi.testclient import TestClient

    from nativeforge.main import create_app

    with TestClient(create_app(), raise_server_exceptions=False) as client:
        response = client.get(CALLBACK_ROUTE_PATH)
    assert response.status_code != 404
    body = response.json()
    assert body["status"] == "callback_validation_not_passed"
    assert body["real_session_created"] is False
    assert body["real_user_created"] is False
    assert body["provider_contacted"] is False


# ------------------------------------------------- the artifacts


def test_the_artifact_set_is_five_files_and_clean() -> None:
    with tempfile.TemporaryDirectory() as tmp:
        result = art.write_demo_live_artifacts(repo_root=tmp)
    assert result["file_count"] == len(art.ARTIFACT_FILES)
    assert result["secret_values_found"] == []
    assert art.demo_live_artifact_invariant_failures(result) == []


def test_artifacts_regenerate_deterministically() -> None:
    """A committed artifact that disagrees with the code is a stale claim."""
    with tempfile.TemporaryDirectory() as tmp:
        art.write_demo_live_artifacts(repo_root=tmp)
        for path in (Path(tmp) / art.ARTIFACT_DIR).iterdir():
            fresh = path.read_text(encoding="utf-8")
            committed = (Path(art.ARTIFACT_DIR) / path.name).read_text(encoding="utf-8")
            assert fresh == committed, f"stale artifact: {path.name}"


def test_the_demo_script_exists_and_names_the_boundary() -> None:
    script = (Path(art.ARTIFACT_DIR) / "demo_script_for_mayhem.md").read_text(
        encoding="utf-8"
    )
    assert "controlled demo data" in script.lower()
    for label in TRUTH_LABELS:
        assert label in script, label
    assert art.DEMO_URL in script


def test_no_artifact_carries_an_environment_value() -> None:
    import os

    for name in art.ARTIFACT_FILES:
        content = (Path(art.ARTIFACT_DIR) / name).read_text(encoding="utf-8")
        for key in art.AUTH_ENV_KEY_NAMES:
            value = (os.environ.get(key) or "").strip()
            if value:
                assert value not in content, f"{name} carries {key}"
