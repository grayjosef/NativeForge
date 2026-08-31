"""Gate 128: the callback URL is derived, not frozen.

Block 39 froze `http://localhost:5173/auth/callback` into the OIDC config
schema. Gate 121 found the path matched no route and could only report it. The
port was never right either, and no frontend route ever declared that path.

The defect these tests guard is neither the port nor the path: it is that a
value nobody configured reported as configured. `redirect_uri_configured` was
true for a URL pointing at nothing.
"""

from __future__ import annotations

import ast
import inspect
from urllib.parse import urlsplit

import pytest

from nativeforge.services import oidc_config_schema_service as svc
from nativeforge.services.customer_auth_environment_preflight_service import (
    CALLBACK_ROUTE_PATH,
)
from nativeforge.services.oidc_config_schema_service import (
    build_oidc_config_schema,
    oidc_config_schema_invariant_failures,
)

AUTH_ENV_KEYS = (
    "OIDC_ISSUER",
    "OIDC_CLIENT_ID",
    "OIDC_CLIENT_SECRET",
    "OIDC_AUDIENCE",
    "OIDC_CALLBACK_URL",
    "OIDC_LOGOUT_URL",
    "NF_PUBLIC_ORIGIN",
)


@pytest.fixture
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """No auth environment at all. The state the runtime is actually in."""
    for key in AUTH_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


# -- the literal is gone --------------------------------------------------


def _string_constants(module) -> list[str]:
    """Every string literal in the module's code, excluding docstrings.

    Parsed rather than grepped. A substring search over the source would match
    this module's own prose, which is the false positive this campaign has now
    hit seven times.
    """
    tree = ast.parse(inspect.getsource(module))
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef)):
            body = getattr(node, "body", None)
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstrings.add(id(body[0].value))
    return [
        node.value
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and id(node) not in docstrings
    ]


def test_no_hardcoded_callback_url_remains_in_the_code() -> None:
    literals = _string_constants(svc)
    offenders = [s for s in literals if "5173" in s or "/auth/callback" in s]
    assert offenders == [], f"a frozen callback literal is back: {offenders}"


def test_the_route_path_is_imported_rather_than_restated() -> None:
    """Bridged, so the derived callback cannot drift from the served route."""
    cfg = build_oidc_config_schema()
    assert cfg["callback_route_path"] == CALLBACK_ROUTE_PATH
    assert CALLBACK_ROUTE_PATH not in _string_constants(svc)


# -- absence reports as absence -------------------------------------------


def test_unconfigured_environment_yields_no_callback(clean_env: None) -> None:
    cfg = build_oidc_config_schema()
    assert cfg["callback_url"] is None
    assert cfg["logout_url"] is None
    assert cfg["allowed_redirect_uris"] == []
    assert cfg["allowed_origins"] == []
    assert cfg["allowed_web_origins"] == []
    assert cfg["allowed_logout_urls"] == []
    assert cfg["public_origin_configured"] is False


def test_force_unconfigured_does_not_invent_a_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """It zeroed the env flags and returned the frozen callback anyway."""
    monkeypatch.setenv("NF_PUBLIC_ORIGIN", "https://configured.example.test")
    cfg = build_oidc_config_schema(force_unconfigured=True)
    assert cfg["callback_url"] is None
    assert cfg["allowed_redirect_uris"] == []
    assert cfg["public_origin_configured"] is False


# -- derivation ------------------------------------------------------------


def test_public_origin_derives_the_route_path(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NF_PUBLIC_ORIGIN", "https://app.example.test")
    cfg = build_oidc_config_schema()
    assert cfg["callback_url"] == f"https://app.example.test{CALLBACK_ROUTE_PATH}"
    assert urlsplit(cfg["callback_url"]).path == CALLBACK_ROUTE_PATH
    assert cfg["allowed_redirect_uris"] == [cfg["callback_url"]]
    assert cfg["public_origin_configured"] is True


def test_trailing_slash_on_the_origin_is_not_doubled(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NF_PUBLIC_ORIGIN", "https://app.example.test/")
    cfg = build_oidc_config_schema()
    assert cfg["callback_url"] == f"https://app.example.test{CALLBACK_ROUTE_PATH}"
    assert "//api" not in urlsplit(cfg["callback_url"]).path


def test_explicit_callback_url_overrides_the_derivation(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A callback off the public origin has to remain expressible."""
    monkeypatch.setenv("NF_PUBLIC_ORIGIN", "https://app.example.test")
    monkeypatch.setenv(
        "OIDC_CALLBACK_URL", f"https://other.example.test{CALLBACK_ROUTE_PATH}"
    )
    cfg = build_oidc_config_schema()
    assert cfg["callback_url"] == f"https://other.example.test{CALLBACK_ROUTE_PATH}"


def test_logout_url_is_not_derived_from_the_api_route(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The API's /logout is a POST; a post-logout redirect is a page."""
    monkeypatch.setenv("NF_PUBLIC_ORIGIN", "https://app.example.test")
    cfg = build_oidc_config_schema()
    assert cfg["logout_url"] is None
    assert cfg["allowed_logout_urls"] == []

    monkeypatch.setenv("OIDC_LOGOUT_URL", "https://app.example.test/goodbye")
    cfg = build_oidc_config_schema()
    assert cfg["logout_url"] == "https://app.example.test/goodbye"


# -- the invariant, in both directions ------------------------------------


def test_invariant_fires_on_the_exact_literal_that_used_to_be_frozen(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OIDC_CALLBACK_URL", "http://localhost:5173/auth/callback")
    cfg = build_oidc_config_schema()
    failures = oidc_config_schema_invariant_failures(cfg)
    assert "callback_path_does_not_match_route" in failures


def test_invariant_does_not_fire_on_absence(clean_env: None) -> None:
    """An unset callback is honestly unset, not a violation."""
    cfg = build_oidc_config_schema()
    assert cfg["callback_url"] is None
    assert oidc_config_schema_invariant_failures(cfg) == []


def test_invariant_does_not_fire_on_a_correct_callback(
    clean_env: None, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("NF_PUBLIC_ORIGIN", "https://app.example.test")
    cfg = build_oidc_config_schema()
    assert oidc_config_schema_invariant_failures(cfg) == []


@pytest.mark.parametrize(
    "bad_path",
    ["/auth/callback", "/callback", "/api/callback", "/api/auth/cb", "/"],
)
def test_invariant_fires_on_any_path_that_is_not_the_route(
    clean_env: None, monkeypatch: pytest.MonkeyPatch, bad_path: str
) -> None:
    monkeypatch.setenv("OIDC_CALLBACK_URL", f"https://app.example.test{bad_path}")
    cfg = build_oidc_config_schema()
    failures = oidc_config_schema_invariant_failures(cfg)
    assert "callback_path_does_not_match_route" in failures


# -- the boundary that predates this gate and must survive it -------------


def test_the_client_secret_value_is_never_returned(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "a-value-that-must-not-appear")
    cfg = build_oidc_config_schema()
    assert cfg["client_secret_value"] is None
    assert cfg["client_secret_present"] is True
    assert "a-value-that-must-not-appear" not in repr(cfg)


def test_configuration_is_still_never_a_liveness_claim(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for key in ("OIDC_ISSUER", "OIDC_CLIENT_ID", "OIDC_CLIENT_SECRET"):
        monkeypatch.setenv(key, "set")
    monkeypatch.setenv("NF_PUBLIC_ORIGIN", "https://app.example.test")
    cfg = build_oidc_config_schema()
    assert cfg["configured_status"] is True
    assert cfg["validated_status"] is False
    assert cfg["login_live_claimed"] is False
    assert cfg["production_auth_claimed"] is False
    assert oidc_config_schema_invariant_failures(cfg) == []
