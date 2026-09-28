"""Tests: identity presentation from verified OIDC claims."""

from nativeforge.services.identity_presentation_service import (
    present_display_name,
    present_identity_provider,
    present_picture_url,
    presentation_from_claims,
)


def test_display_name_prefers_the_name_claim() -> None:
    assert present_display_name(name="Josef Gray", given_name="Jo") == "Josef Gray"


def test_display_name_falls_back_to_given_and_family() -> None:
    assert present_display_name(given_name="Josef", family_name="Gray") == "Josef Gray"


def test_display_name_rejects_an_email_address() -> None:
    assert present_display_name(name="josef@example.org") is None


def test_picture_url_accepts_google_https() -> None:
    url = "https://lh3.googleusercontent.com/a/abc"
    assert present_picture_url(url) == url


def test_picture_url_rejects_http_and_unknown_hosts() -> None:
    assert present_picture_url("http://lh3.googleusercontent.com/a/abc") is None
    assert present_picture_url("https://evil.example/photo.png") is None
    assert present_picture_url("javascript:alert(1)") is None


def test_provider_from_issuer() -> None:
    assert present_identity_provider("https://accounts.google.com") == "google"
    assert (
        present_identity_provider("https://login.microsoftonline.com/tenant/v2.0")
        == "microsoft"
    )
    assert present_identity_provider("google") == "google"


def test_presentation_from_google_claims() -> None:
    out = presentation_from_claims(
        {
            "iss": "https://accounts.google.com",
            "name": "Josef Gray",
            "picture": "https://lh3.googleusercontent.com/a/photo",
        }
    )
    assert out["display_name"] == "Josef Gray"
    assert out["picture_url"] == "https://lh3.googleusercontent.com/a/photo"
    assert out["identity_provider"] == "google"
