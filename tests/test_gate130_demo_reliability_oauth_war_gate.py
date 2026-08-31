"""Gate 130: the demo stack is verifiable, and the verifier can fail.

A demo showed Cloudflare Error 1033 while every service reported active. That is
the gap these tests defend: `systemctl is-active` answers a question adjacent to
the one that matters, and the only place 1033 is visible is from outside.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

from nativeforge.services import demo_reliability_oauth_artifact_service as art

VERIFIER = Path("scripts/verify_nativeforge_demo_live_stack.sh")
TALK_TRACK = Path("artifacts/demo_live_operating_shell/post_demo_talk_track_v2.md")
ARTIFACT_DIR = Path(art.ARTIFACT_DIR)

REQUIRED_SERVICES = (
    "nativeforge-demo-preview",
    "nativeforge-backend",
    "nativeforge-mayhem-tunnel",
)


# ------------------------------------------------- the verifier


def test_the_verifier_exists_and_is_executable() -> None:
    """A verifier nobody can run is a verifier that never runs.

    Editing a shell script through the Windows UNC path into WSL strips the
    executable bit, which has now happened twice in this campaign.
    """
    import os

    assert VERIFIER.exists()
    assert os.access(VERIFIER, os.X_OK), "chmod +x and git update-index --chmod=+x"


def test_the_verifier_refuses_1033() -> None:
    body = VERIFIER.read_text(encoding="utf-8")
    assert "1033" in body
    assert "public_demo_not_1033" in body


def test_the_verifier_fails_any_5xx_rather_than_a_named_list() -> None:
    """An earlier version enumerated 530/502/000 and passed a 525 while the
    origin was unreachable. Cloudflare has a family of 52x origin errors and
    this must not depend on having listed the right ones."""
    body = VERIFIER.read_text(encoding="utf-8")
    assert '"${demo_code:0:1}" = "5"' in body


def test_the_verifier_requires_the_public_callback_to_reach_the_api() -> None:
    body = VERIFIER.read_text(encoding="utf-8")
    assert "public_callback_reaches_api" in body
    # An Access redirect on the callback breaks OAuth: a browser arriving from
    # a provider carries no Access session.
    assert "access_redirect_would_break_oauth" in body


def test_the_verifier_checks_every_demo_service() -> None:
    body = VERIFIER.read_text(encoding="utf-8")
    for svc in REQUIRED_SERVICES:
        assert svc in body, svc


def test_the_verifier_checks_edge_connections() -> None:
    """Zero registered connectors is 1033 about to happen, and it is only
    visible from inside the host."""
    body = VERIFIER.read_text(encoding="utf-8")
    assert "tunnel_edge_connections" in body
    assert "cloudflared_tunnel_ha_connections" in body


def test_the_verifier_emits_a_machine_readable_result() -> None:
    body = VERIFIER.read_text(encoding="utf-8")
    assert "RESULT=PASS" in body
    assert "RESULT=FAIL" in body
    assert "failed_check=" in body


def test_the_verifier_prints_no_environment_values() -> None:
    body = VERIFIER.read_text(encoding="utf-8")
    for forbidden in ("printenv", "set -x", "cat .env", "$OIDC_", "$NF_SESSION"):
        assert forbidden not in body, forbidden


# ------------------------------------------------- service matrix


def test_the_service_matrix_covers_preview_backend_and_tunnel() -> None:
    assert tuple(art.SERVICES) == REQUIRED_SERVICES


@pytest.mark.skipif(
    not (ARTIFACT_DIR / "service_reliability_matrix.json").exists(),
    reason="artifacts not generated in this environment",
)
def test_the_committed_matrix_names_all_three_services() -> None:
    doc = json.loads(
        (ARTIFACT_DIR / "service_reliability_matrix.json").read_text(encoding="utf-8")
    )
    for svc in REQUIRED_SERVICES:
        assert svc in doc["services"], svc
        assert "restart_policy" in doc["services"][svc]


# ------------------------------------------------- restart policy


def test_the_tracked_units_restart_on_a_clean_exit() -> None:
    """`on-failure` ignores exit code 0, and cloudflared exits 0 when it gives
    up on its edge connections. That is the 1033 the demo hit."""
    units = [
        Path("ops/systemd/nativeforge-cloudflared.service"),
        Path("ops/systemd/nativeforge-demo-preview.service"),
        Path("deploy/systemd/nativeforge-backend.service"),
        Path("ops/systemd/nativeforge-mayhem-tunnel.service"),
    ]
    for unit in units:
        assert unit.exists(), f"missing tracked unit: {unit}"
        body = unit.read_text(encoding="utf-8")
        assert re.search(r"^Restart=always$", body, re.M), f"{unit} is not always"
        assert not re.search(r"^Restart=on-failure$", body, re.M), unit


def test_the_tunnel_unit_actually_serving_the_demo_is_tracked() -> None:
    """The repository tracked a cloudflared unit that was not the one serving
    nf-dev.mayhem-nc.dev, so reviewing it said nothing about production."""
    unit = Path("ops/systemd/nativeforge-mayhem-tunnel.service")
    assert unit.exists()
    body = unit.read_text(encoding="utf-8")
    assert "nativeforge-mayhem.yml" in body


def test_no_tracked_unit_carries_a_credential() -> None:
    for unit in Path("ops/systemd").glob("*.service"):
        body = unit.read_text(encoding="utf-8").lower()
        for needle in ("token=", "secret=", "password=", "tunneltoken"):
            assert needle not in body, f"{unit} carries {needle}"


# ------------------------------------------------- the callback URL


def test_the_callback_url_has_no_trailing_slash() -> None:
    assert art.CALLBACK_URL == "https://nf-dev.mayhem-nc.dev/api/auth/callback"
    assert not art.CALLBACK_URL.endswith("/")
    assert art.CALLBACK_PATH == "/api/auth/callback"


# ------------------------------------------------- liveness claims


def test_auth_and_login_cannot_be_live_without_session_proof() -> None:
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )

    gate = build_customer_auth_activation_gate()
    assert gate["customer_auth_live"] is False
    assert gate["login_live"] is False
    assert gate["real_sessions_created"] is False
    assert gate["real_users_created"] is False
    assert gate["callback_session_validated"] is False


def test_the_smoke_result_records_no_session_and_no_binding() -> None:
    doc = json.loads(
        (ARTIFACT_DIR / "oauth_login_smoke_result.json").read_text(encoding="utf-8")
    )
    assert doc["session_created"] is False
    assert doc["identity_validated"] is False
    assert doc["customer_auth_live"] is False
    assert doc["login_live"] is False
    assert doc["fake_users_created"] is False
    assert doc["fake_sessions_created"] is False
    assert doc["fake_bindings_created"] is False
    # The parts that DID work, so a later gate does not re-litigate them.
    assert doc["google_accepted_redirect_uri"] is True
    assert doc["redirect_uri_mismatch"] is False
    assert doc["callback_reached_api"] is True


# ------------------------------------------------- artifacts


def test_the_artifact_set_is_six_files_and_clean() -> None:
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        result = art.write_demo_reliability_artifacts(repo_root=tmp)
    assert result["file_count"] == len(art.ARTIFACT_FILES)
    assert result["secret_values_found"] == []
    assert art.demo_reliability_artifact_invariant_failures(result) == []


def test_no_artifact_carries_a_secret_token_cookie_or_code() -> None:
    forbidden = (
        "GOCSPX-",
        "Bearer ",
        "Set-Cookie",
        "code_verifier=",
        "id_token",
        "access_token",
        "refresh_token",
        "?code=",
    )
    for name in art.ARTIFACT_FILES:
        content = (ARTIFACT_DIR / name).read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in content, f"{name} carries {needle}"


def test_no_artifact_carries_an_environment_value() -> None:
    import os

    for name in art.ARTIFACT_FILES:
        content = (ARTIFACT_DIR / name).read_text(encoding="utf-8")
        for key in art.AUTH_ENV_KEY_NAMES:
            value = (os.environ.get(key) or "").strip()
            if value:
                assert value not in content, f"{name} carries {key}"


# ------------------------------------------------- the talk track


def test_the_talk_track_exists_and_names_what_is_not_live() -> None:
    body = TALK_TRACK.read_text(encoding="utf-8")
    assert "not live" in body.lower()
    for claim in ("login", "source monitoring", "document storage"):
        assert claim in body.lower(), claim


def test_the_talk_track_owns_the_failure_rather_than_deflecting() -> None:
    """Non-defensive means naming it as ours. A talk track that blames the
    tooling is the same overstatement this campaign exists to prevent, aimed
    outward instead of inward."""
    body = TALK_TRACK.read_text(encoding="utf-8").lower()
    assert "on us" in body or "that is on us" in body
    for deflection in ("not our fault", "unforeseeable", "nothing we could"):
        assert deflection not in body, deflection


# ------------------------------------------------- hermeticity


def test_the_suite_does_not_read_the_machine_s_dotenv() -> None:
    """Gate 130. Gate 129C routed every auth detector through Settings, which
    reads `.env`. The moment a real Google client was configured, 25 tests
    failed - gates 115 to 118 assert unconfigured behaviour and were reading
    live credentials. A suite whose result depends on the developer's `.env` is
    not testing the code.

    Parsed rather than grepped: this file's own prose mentions `env_file`.
    """
    source = Path("tests/conftest.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assigns = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Assign)
        and any(
            isinstance(t, ast.Subscript)
            and isinstance(t.slice, ast.Constant)
            and t.slice.value == "env_file"
            for t in node.targets
        )
    ]
    assert assigns, "conftest must disable Settings' env_file"

    from nativeforge.lib.settings import Settings

    assert Settings.model_config.get("env_file") is None


def test_an_unconfigured_provider_is_what_the_suite_sees() -> None:
    """The observable consequence of the fix above."""
    from nativeforge.lib.settings import auth_environment_presence

    presence = auth_environment_presence()
    assert not any(presence.values()), (
        "the suite is reading a configured provider from somewhere; "
        f"present: {[k for k, v in presence.items() if v]}"
    )
