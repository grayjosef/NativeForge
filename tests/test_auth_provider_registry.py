"""The provider dimension, and the two things it must not get wrong.

NativeForge's auth stack was built for one provider. These tests cover the
seam that added a second without touching the flow: which keys a provider may
override, and whether "configured" means what it says.
"""

from __future__ import annotations

from nativeforge.services.auth_provider_registry_service import (
    PROVIDER_KEYS,
    available_providers,
    callback_path,
    provider_configured,
    provider_env,
)

GOOGLE_ISSUER = "https://accounts.google.com"
MICROSOFT_ISSUER = "https://login.microsoftonline.com/a-tenant-id/v2.0"


def _base(**overrides: str) -> dict[str, str]:
    env = {
        "OIDC_ISSUER": GOOGLE_ISSUER,
        "OIDC_CLIENT_ID": "google-client",
        "OIDC_CLIENT_SECRET": "google-secret",
        "OIDC_AUDIENCE": "google-client",
        "OIDC_CALLBACK_URL": "https://nativeforge.example/api/auth/callback/google",
        "NF_PUBLIC_ORIGIN": "https://nativeforge.example",
        "NF_SESSION_SIGNING_KEY": "deployment-wide-key",
    }
    env.update(overrides)
    return env


# ------------------------------------------------------------ which keys


def test_only_oidc_keys_are_per_provider():
    """The session signing key is the deployment's, not a provider's.

    It signs NativeForge's own cookie, which has nothing to do with who proved
    the identity. Per-provider keys would sign a customer out by choosing a
    different button, and rotating one would invalidate half the sessions.
    """
    assert "NF_SESSION_SIGNING_KEY" not in PROVIDER_KEYS
    assert "NF_PUBLIC_ORIGIN" not in PROVIDER_KEYS
    assert all(k.startswith("OIDC_") for k in PROVIDER_KEYS)


def test_a_provider_cannot_override_the_signing_key():
    env = _base()
    env["NF_OIDC_MICROSOFT_NF_SESSION_SIGNING_KEY"] = "a-provider-key"
    resolved = provider_env("microsoft", env)
    assert resolved["NF_SESSION_SIGNING_KEY"] == "deployment-wide-key"


def test_a_provider_cannot_move_the_public_origin():
    env = _base()
    env["NF_OIDC_MICROSOFT_NF_PUBLIC_ORIGIN"] = "https://somewhere-else.example"
    resolved = provider_env("microsoft", env)
    assert resolved["NF_PUBLIC_ORIGIN"] == "https://nativeforge.example"


# --------------------------------------------------------- what resolves


def test_prefixed_keys_win_and_the_rest_falls_through():
    env = _base(
        NF_OIDC_MICROSOFT_ISSUER=MICROSOFT_ISSUER,
        NF_OIDC_MICROSOFT_CLIENT_ID="ms-client",
        NF_OIDC_MICROSOFT_CLIENT_SECRET="ms-secret",
    )
    resolved = provider_env("microsoft", env)
    assert resolved["OIDC_ISSUER"] == MICROSOFT_ISSUER
    assert resolved["OIDC_CLIENT_ID"] == "ms-client"
    # Not overridden, so the base value stands.
    assert resolved["OIDC_AUDIENCE"] == "google-client"


def test_an_unknown_provider_gets_the_base_environment_unchanged():
    env = _base()
    assert provider_env("nobody", env)["OIDC_ISSUER"] == GOOGLE_ISSUER
    assert provider_env(None, env)["OIDC_ISSUER"] == GOOGLE_ISSUER


# ----------------------------------------------------- what "configured" means


def test_the_base_configuration_only_counts_for_the_provider_it_names():
    """The fall-through must not make every provider look available.

    Without the issuer check, a deployment holding only Google credentials
    reports Microsoft as configured, because Microsoft inherits every base
    key. The button would then send a customer to a provider that refuses
    them on arrival, which reads as NativeForge being broken.
    """
    env = _base()
    assert provider_configured("google", env) is True
    assert provider_configured("microsoft", env) is False


def test_both_configured_when_both_are_supplied():
    env = _base(
        NF_OIDC_MICROSOFT_ISSUER=MICROSOFT_ISSUER,
        NF_OIDC_MICROSOFT_CLIENT_ID="ms-client",
        NF_OIDC_MICROSOFT_CLIENT_SECRET="ms-secret",
        NF_OIDC_MICROSOFT_CALLBACK_URL=(
            "https://nativeforge.example/api/auth/callback/microsoft"
        ),
    )
    assert provider_configured("google", env) is True
    assert provider_configured("microsoft", env) is True


def test_half_a_configuration_is_not_configured():
    """A missing secret fails at the token endpoint, not at the button."""
    for missing in (
        "OIDC_ISSUER",
        "OIDC_CLIENT_ID",
        "OIDC_CLIENT_SECRET",
        "OIDC_CALLBACK_URL",
    ):
        env = _base()
        env[missing] = ""
        assert provider_configured("google", env) is False, missing


def test_a_blank_value_is_unset_rather_than_configured():
    env = _base(OIDC_CLIENT_SECRET="   ")
    assert provider_configured("google", env) is False


# ------------------------------------------------------------ the listing


def test_the_listing_carries_no_secret_and_no_client_id():
    """A sign-in page draws buttons. It has no business knowing the rest."""
    env = _base()
    listing = available_providers(env, public_origin="https://nativeforge.example")
    blob = repr(listing)
    for secret in ("google-secret", "google-client", GOOGLE_ISSUER):
        assert secret not in blob


def test_the_listing_reports_every_known_provider_not_only_the_ready_ones():
    """Hiding Microsoft leaves a Microsoft customer unsure we support them."""
    env = _base()
    listing = available_providers(env)
    keys = {entry["key"] for entry in listing["providers"]}
    assert keys == {"google", "microsoft"}
    assert listing["any_configured"] is True


def test_each_provider_returns_to_its_own_path():
    """The path is how the callback knows whose secret to present."""
    assert callback_path("google") == "/api/auth/callback/google"
    assert callback_path("microsoft") == "/api/auth/callback/microsoft"

    listing = available_providers(_base(), public_origin="https://nativeforge.example/")
    by_key = {e["key"]: e for e in listing["providers"]}
    assert by_key["google"]["redirect_uri"] == (
        "https://nativeforge.example/api/auth/callback/google"
    )
    # The trailing slash on the origin does not become a double slash.
    assert "//api" not in by_key["google"]["redirect_uri"]


def test_no_origin_yields_no_guessed_redirect_uri():
    listing = available_providers(_base(), public_origin="")
    assert all(entry["redirect_uri"] == "" for entry in listing["providers"])
