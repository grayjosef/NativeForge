"""Microsoft login must not start a Google authorization.

The identity/session suite (154 tests, including Gates 60/118/132) can be
green while `/api/auth/login?provider=microsoft` 302s to
accounts.google.com. Those tests never GET that route with Google configured
and a production-ready signing key: they cover session/OIDC-verify internals
and registry booleans, not the login route's provider dispatch.

This file is the missing guard. It does not pretend to be an Entra E2E.
"""

from __future__ import annotations

from urllib.parse import parse_qs, urlsplit

from fastapi.testclient import TestClient

from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app

GOOGLE_ISSUER = "https://accounts.google.com"
GOOGLE_CLIENT = "google-client.apps.googleusercontent.com"
MICROSOFT_ISSUER = "https://login.microsoftonline.com/a-tenant-id/v2.0"
MICROSOFT_CLIENT = "11111111-2222-3333-4444-555555555555"
SIGNING_KEY = "microsoft-login-regression-key-" + ("z" * 24)
FAKE_GOOGLE_AUTHORIZE = (
    "https://accounts.google.com/o/oauth2/v2/auth?client_id=google-client"
    "&redirect_uri=https://nativeforge.example/api/auth/callback/google"
)


def _google_only(monkeypatch) -> None:
    monkeypatch.setenv("OIDC_ISSUER", GOOGLE_ISSUER)
    monkeypatch.setenv("OIDC_CLIENT_ID", GOOGLE_CLIENT)
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "google-secret-value-xx")
    monkeypatch.setenv("OIDC_AUDIENCE", GOOGLE_CLIENT)
    monkeypatch.setenv(
        "OIDC_CALLBACK_URL",
        "https://nativeforge.example/api/auth/callback/google",
    )
    monkeypatch.setenv("NF_PUBLIC_ORIGIN", "https://nativeforge.example")
    monkeypatch.setenv("NF_SESSION_SIGNING_KEY", SIGNING_KEY)
    for key in (
        "NF_OIDC_MICROSOFT_ISSUER",
        "NF_OIDC_MICROSOFT_CLIENT_ID",
        "NF_OIDC_MICROSOFT_CLIENT_SECRET",
        "NF_OIDC_MICROSOFT_CALLBACK_URL",
        "NF_OIDC_MICROSOFT_AUDIENCE",
    ):
        monkeypatch.delenv(key, raising=False)
    get_settings.cache_clear()


def _client() -> TestClient:
    return TestClient(create_app())


def _fake_google_authorize_url(**kwargs):
    """Make the Google URL branch reachable without discovery or network.

    Live 302'd because persist + signing + a resolvable authorize URL all
    succeeded. Tests without this stub never reach the Location header, so
    they never saw the defect.
    """
    return {
        "schema_version": "nf_customer_auth_authorization_url_v1",
        "provider_configured": True,
        "issuer": kwargs.get("issuer") or GOOGLE_ISSUER,
        "authorization_endpoint_configured": True,
        "client_id_configured": True,
        "redirect_uri_configured": True,
        "scope": "openid profile email",
        "state_bound": True,
        "pkce_bound": True,
        "authorization_url_available": True,
        "authorization_url_returned": True,
        "authorization_url": FAKE_GOOGLE_AUTHORIZE,
        "authorization_url_redacted": FAKE_GOOGLE_AUTHORIZE,
        "provider_called": False,
        "secret_exposed": False,
        "blocked_reasons": [],
    }


def test_unconfigured_microsoft_login_does_not_redirect_to_google(monkeypatch):
    """Google-only env + a reachable authorize URL must still refuse Microsoft.

    Before the login-route dispatch fix, this issued Location:
    accounts.google.com because the activation gate's Google
    `provider_configured` stood in for every named provider.
    """
    _google_only(monkeypatch)
    monkeypatch.setattr(
        "nativeforge.api.auth.build_authorization_url",
        _fake_google_authorize_url,
    )
    response = _client().get(
        "/api/auth/login?provider=microsoft",
        follow_redirects=False,
    )
    location = response.headers.get("location") or ""
    assert "accounts.google.com" not in location
    assert "googleusercontent.com" not in location
    assert response.status_code != 302
    body = response.json()
    assert body.get("authorization_redirect_issued") is False
    assert body.get("redirect_ready") is False


def test_configured_microsoft_login_authorizes_at_microsoft_not_google(monkeypatch):
    """When Microsoft keys exist, the authorize URL must name Microsoft."""
    _google_only(monkeypatch)
    monkeypatch.setenv("NF_OIDC_MICROSOFT_ISSUER", MICROSOFT_ISSUER)
    monkeypatch.setenv("NF_OIDC_MICROSOFT_CLIENT_ID", MICROSOFT_CLIENT)
    monkeypatch.setenv("NF_OIDC_MICROSOFT_CLIENT_SECRET", "ms-secret-value-xx")
    monkeypatch.setenv("NF_OIDC_MICROSOFT_AUDIENCE", MICROSOFT_CLIENT)
    monkeypatch.setenv(
        "NF_OIDC_MICROSOFT_CALLBACK_URL",
        "https://nativeforge.example/api/auth/callback/microsoft",
    )
    get_settings.cache_clear()

    captured: dict[str, str | None] = {}

    def capture(**kwargs):
        captured["issuer"] = kwargs.get("issuer")
        captured["client_id"] = kwargs.get("client_id")
        captured["redirect_uri"] = kwargs.get("redirect_uri")
        endpoint = f"{MICROSOFT_ISSUER}/authorize"
        query = (
            f"client_id={MICROSOFT_CLIENT}"
            "&redirect_uri=https://nativeforge.example/api/auth/callback/microsoft"
            "&response_type=code"
        )
        return {
            "schema_version": "nf_customer_auth_authorization_url_v1",
            "provider_configured": True,
            "issuer": kwargs.get("issuer") or "",
            "authorization_endpoint_configured": True,
            "client_id_configured": True,
            "redirect_uri_configured": True,
            "scope": "openid profile email",
            "state_bound": True,
            "pkce_bound": True,
            "authorization_url_available": True,
            "authorization_url_returned": True,
            "authorization_url": f"{endpoint}?{query}",
            "authorization_url_redacted": f"{endpoint}?{query}",
            "provider_called": False,
            "secret_exposed": False,
            "blocked_reasons": [],
        }

    monkeypatch.setattr("nativeforge.api.auth.build_authorization_url", capture)
    response = _client().get(
        "/api/auth/login?provider=microsoft",
        follow_redirects=False,
    )
    assert captured.get("issuer") == MICROSOFT_ISSUER
    assert captured.get("client_id") == MICROSOFT_CLIENT
    assert captured.get("redirect_uri") == (
        "https://nativeforge.example/api/auth/callback/microsoft"
    )
    location = response.headers.get("location") or ""
    assert response.status_code == 302
    host = urlsplit(location).hostname or ""
    assert host == "login.microsoftonline.com"
    assert "accounts.google.com" not in location
    params = parse_qs(urlsplit(location).query)
    redirect_uri = (params.get("redirect_uri") or [""])[0]
    assert redirect_uri.endswith("/api/auth/callback/microsoft")
