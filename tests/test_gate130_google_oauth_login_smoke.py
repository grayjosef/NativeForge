"""Gate 130: Google's endpoints are not Auth0's, and guessing sends a 404.

The defect this file defends against is one this campaign has now found eight
times: a constant that was accidentally correct for the provider in front of it
and silently wrong for the next one.

```text
                 concatenated under issuer          Google publishes
authorization    accounts.google.com/authorize      accounts.google.com/o/oauth2/v2/auth
token            accounts.google.com/oauth/token    oauth2.googleapis.com/token
jwks             accounts.google.com/.well-known/   www.googleapis.com/oauth2/v3/certs
                   jwks.json
```

Two of three are on a different host, so no path concatenation reaches them.
"""

from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

from nativeforge.services.customer_auth_authorization_url_service import (
    build_authorization_url,
)
from nativeforge.services.customer_auth_environment_preflight_service import (
    CALLBACK_ROUTE_PATH,
    build_environment_preflight,
)
from nativeforge.services.oidc_provider_discovery_service import (
    KNOWN_NON_CONVENTIONAL_ISSUERS,
    build_provider_endpoints,
    discovery_url,
    fetch_provider_metadata,
    provider_discovery_invariant_failures,
)

GOOGLE = "https://accounts.google.com"
AUTH0ISH = "https://tenant.example.auth0.com"
PUBLIC_ORIGIN = "https://nf-dev.mayhem-nc.dev"
CALLBACK = f"{PUBLIC_ORIGIN}{CALLBACK_ROUTE_PATH}"
PLACEHOLDER_CLIENT_ID = "placeholder-client-id.apps.googleusercontent.com"

#: Google's real endpoints, as published at its discovery URL. Injected rather
#: than fetched so this file needs no network.
GOOGLE_METADATA = {
    "issuer": GOOGLE,
    "authorization_endpoint": "https://accounts.google.com/o/oauth2/v2/auth",
    "token_endpoint": "https://oauth2.googleapis.com/token",
    "jwks_uri": "https://www.googleapis.com/oauth2/v3/certs",
}

ARTIFACT_DIR = Path("artifacts/google_oauth_login_smoke")


# ------------------------------------------------- the callback URL


def test_the_callback_url_has_no_trailing_slash() -> None:
    assert CALLBACK == "https://nf-dev.mayhem-nc.dev/api/auth/callback"
    assert not CALLBACK.endswith("/")
    assert urlsplit(CALLBACK).path == CALLBACK_ROUTE_PATH


def test_the_bare_auth_callback_path_is_refused() -> None:
    result = build_environment_preflight(
        configured_callback_url=f"{PUBLIC_ORIGIN}/auth/callback",
    )
    assert result["callback_path_matches_route"] is False
    assert (
        "callback_url_path_does_not_match_any_callback_route"
        in result["blocked_reasons"]
    )


def test_the_api_callback_path_is_accepted() -> None:
    result = build_environment_preflight(configured_callback_url=CALLBACK)
    assert result["callback_path_matches_route"] is True
    assert (
        "callback_url_path_does_not_match_any_callback_route"
        not in result["blocked_reasons"]
    )


# ------------------------------------------------- discovery


def test_the_discovery_url_is_the_well_known_document() -> None:
    assert discovery_url(GOOGLE) == f"{GOOGLE}/.well-known/openid-configuration"
    assert discovery_url(f"{GOOGLE}/") == f"{GOOGLE}/.well-known/openid-configuration"
    assert discovery_url("") == ""


def test_network_is_denied_by_default() -> None:
    result = fetch_provider_metadata(GOOGLE)
    assert result["attempted"] is False
    assert result["succeeded"] is False
    assert result["metadata"] is None
    assert "network_not_allowed_so_nothing_fetched" in result["blocked_reasons"]


def test_google_offline_refuses_rather_than_guessing() -> None:
    """The whole point. A guess here is a 404 with every gate reporting ready."""
    result = build_provider_endpoints(GOOGLE)
    assert result["endpoints_available"] is False
    assert result["endpoints_discovered"] is False
    assert result["endpoints_are_conventional"] is False
    assert result["authorization_endpoint"] == ""
    assert any(
        r.startswith("issuer_does_not_follow_the_conventional_shape")
        for r in result["blocked_reasons"]
    )
    assert provider_discovery_invariant_failures(result) == []


def test_google_with_metadata_yields_googles_real_endpoints() -> None:
    result = build_provider_endpoints(GOOGLE, metadata=GOOGLE_METADATA)
    assert result["endpoints_discovered"] is True
    assert result["endpoints_are_conventional"] is False
    assert result["authorization_endpoint"] == (
        "https://accounts.google.com/o/oauth2/v2/auth"
    )
    assert result["token_endpoint"] == "https://oauth2.googleapis.com/token"
    assert result["jwks_uri"] == "https://www.googleapis.com/oauth2/v3/certs"
    assert provider_discovery_invariant_failures(result) == []


def test_googles_token_and_jwks_are_not_on_the_issuer_host() -> None:
    """Why concatenation could never have worked, asserted rather than asserted
    in a comment."""
    result = build_provider_endpoints(GOOGLE, metadata=GOOGLE_METADATA)
    issuer_host = urlsplit(GOOGLE).netloc
    assert urlsplit(result["token_endpoint"]).netloc != issuer_host
    assert urlsplit(result["jwks_uri"]).netloc != issuer_host


def test_a_conventional_issuer_still_works_offline() -> None:
    """The fallback is a fallback, not a removal."""
    result = build_provider_endpoints(AUTH0ISH)
    assert result["endpoints_available"] is True
    assert result["endpoints_are_conventional"] is True
    assert result["endpoints_discovered"] is False
    assert result["authorization_endpoint"] == f"{AUTH0ISH}/authorize"
    assert provider_discovery_invariant_failures(result) == []


def test_discovered_and_conventional_cannot_both_be_true() -> None:
    tampered = dict(build_provider_endpoints(AUTH0ISH))
    tampered["endpoints_discovered"] = True
    assert "discovered_and_conventional_at_once" in (
        provider_discovery_invariant_failures(tampered)
    )


def test_conventional_endpoints_for_google_are_refused_by_invariant() -> None:
    tampered = dict(build_provider_endpoints(AUTH0ISH))
    tampered["issuer"] = GOOGLE
    fails = provider_discovery_invariant_failures(tampered)
    assert any(
        f.startswith("conventional_endpoints_for_known_non_conventional") for f in fails
    )


def test_google_is_named_as_non_conventional() -> None:
    assert GOOGLE in KNOWN_NON_CONVENTIONAL_ISSUERS


def test_a_metadata_document_missing_an_endpoint_is_not_discovery() -> None:
    """A partial document is not a discovered document.

    Named for what it does. The earlier name said "different issuer" while the
    body removed an endpoint — a test whose name and body disagree is the shape
    this campaign keeps finding in the code it tests.
    """
    result = build_provider_endpoints(
        GOOGLE, metadata={**GOOGLE_METADATA, "authorization_endpoint": ""}
    )
    assert result["endpoints_discovered"] is False
    assert (
        "discovery_document_missing:authorization_endpoint"
        in (result["blocked_reasons"])
    )
    # And, because Google is known non-conventional, it must not fall back.
    assert result["endpoints_are_conventional"] is False
    assert result["authorization_endpoint"] == ""


# ------------------------------------------------- the authorization URL


def test_google_authorization_url_is_refused_without_discovery() -> None:
    result = build_authorization_url(
        issuer=GOOGLE,
        client_id=PLACEHOLDER_CLIENT_ID,
        redirect_uri=CALLBACK,
        state="placeholder-state",
        code_challenge="placeholder-challenge",
    )
    assert result["authorization_url_available"] is False
    assert result["authorization_endpoint_configured"] is False
    assert "no_authorization_endpoint_for_this_issuer" in result["blocked_reasons"]


def test_google_authorization_url_targets_googles_endpoint() -> None:
    result = build_authorization_url(
        issuer=GOOGLE,
        client_id=PLACEHOLDER_CLIENT_ID,
        redirect_uri=CALLBACK,
        state="placeholder-state",
        code_challenge="placeholder-challenge",
        provider_metadata=GOOGLE_METADATA,
    )
    assert result["authorization_url_available"] is True
    assert result["endpoints_discovered"] is True
    url = result["authorization_url"]
    assert url.startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    query = parse_qs(urlsplit(url).query)
    assert query["redirect_uri"] == [CALLBACK]
    assert query["code_challenge_method"] == ["S256"]
    assert query["response_type"] == ["code"]
    assert result["secret_exposed"] is False


def test_the_authorization_url_never_carries_a_client_secret() -> None:
    result = build_authorization_url(
        issuer=GOOGLE,
        client_id=PLACEHOLDER_CLIENT_ID,
        redirect_uri=CALLBACK,
        state="placeholder-state",
        code_challenge="placeholder-challenge",
        provider_metadata=GOOGLE_METADATA,
    )
    blob = json.dumps(result)
    assert "client_secret" not in blob
    assert result["secret_exposed"] is False


# ------------------------------------------------- liveness claims


def test_login_live_is_false_without_a_session() -> None:
    """login_live cannot be true on configuration alone."""
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )

    gate = build_customer_auth_activation_gate()
    assert gate["login_live"] is False
    assert gate["customer_auth_live"] is False
    assert gate["real_sessions_created"] is False
    assert gate["real_users_created"] is False


def test_customer_auth_live_requires_org_binding() -> None:
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )

    gate = build_customer_auth_activation_gate()
    assert gate["org_binding_passed"] is False
    assert gate["customer_auth_live"] is False
    assert "org_binding_passed" in gate["missing_auth_gates"]


def test_no_session_or_user_was_created_by_this_gate() -> None:
    from nativeforge.services.customer_auth_activation_gate_service import (
        build_customer_auth_activation_gate,
    )

    gate = build_customer_auth_activation_gate()
    for key in ("real_users_created", "real_sessions_created", "fabricated"):
        assert gate[key] is False


# ------------------------------------------------- the artifacts


@pytest.mark.skipif(
    not ARTIFACT_DIR.exists(), reason="artifacts not generated in this environment"
)
def test_artifacts_carry_no_secret_token_or_cookie() -> None:
    forbidden = (
        "client_secret=",
        "Bearer ",
        "Set-Cookie",
        "code_verifier",
        "id_token",
        "access_token",
    )
    for path in ARTIFACT_DIR.iterdir():
        content = path.read_text(encoding="utf-8")
        for needle in forbidden:
            assert needle not in content, f"{path.name} carries {needle}"


@pytest.mark.skipif(
    not ARTIFACT_DIR.exists(), reason="artifacts not generated in this environment"
)
def test_artifacts_record_the_exact_callback_url() -> None:
    blob = (ARTIFACT_DIR / "oauth_provider_config_status.json").read_text(
        encoding="utf-8"
    )
    document = json.loads(blob)
    assert document["callback_url"] == CALLBACK
    assert document["callback_url_has_trailing_slash"] is False
    assert document["client_secret_recorded"] is False
