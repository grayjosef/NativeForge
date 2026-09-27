"""Fetching one customer-named URL, without a network.

The interesting cases are chains no real host would serve: a public page that
redirects to `169.254.169.254`, a body that keeps arriving past the cap, a
content type that is not a document. The resolver and the HTTP client are
both injected so every one of them can be exercised deterministically.

If these needed a network they would not be run, and the redirect rule — the
one that stops a public host walking this server somewhere internal — is
exactly the rule that has to be tested.
"""

from __future__ import annotations

import httpx
import pytest

from nativeforge.services.customer_supplied_url_fetch_service import fetch_customer_url
from nativeforge.services.customer_url_safety_service import MAX_RESPONSE_BYTES

PUBLIC_IP = "93.184.216.34"
INTERNAL_IP = "169.254.169.254"

PUBLIC = "https://www.hud.gov/notice"
INTERNAL = "https://metadata.internal/latest"


def resolver_for(mapping: dict[str, list[str]]):
    """DNS, as a dictionary."""

    def resolve(host: str) -> list[str]:
        return mapping.get(host, [])

    return resolve


ALL_PUBLIC = resolver_for(
    {"www.hud.gov": [PUBLIC_IP], "metadata.internal": [PUBLIC_IP]}
)
HONEST = resolver_for({"www.hud.gov": [PUBLIC_IP], "metadata.internal": [INTERNAL_IP]})


class FakeResponse:
    def __init__(self, status: int, headers: dict[str, str], chunks: list[bytes]):
        self.status_code = status
        self.headers = httpx.Headers(headers)
        self._chunks = chunks

    @property
    def is_redirect(self) -> bool:
        return self.status_code in (301, 302, 303, 307, 308)

    def iter_bytes(self):
        yield from self._chunks

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class FakeClient:
    """Serves a scripted map of URL -> response, and records what was asked."""

    def __init__(self, routes: dict[str, FakeResponse]):
        self.routes = routes
        self.requested: list[str] = []

    def stream(self, _method: str, url: str):
        self.requested.append(url)
        if url not in self.routes:
            raise httpx.ConnectError(f"no route for {url}")
        return self.routes[url]

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def client_for(routes: dict[str, FakeResponse]):
    client = FakeClient(routes)
    return (lambda: client), client


def html(body: str = "<html>notice</html>", **headers) -> FakeResponse:
    merged = {"content-type": "text/html; charset=utf-8"}
    merged.update(headers)
    return FakeResponse(200, merged, [body.encode()])


def redirect(to: str, status: int = 302) -> FakeResponse:
    return FakeResponse(status, {"location": to}, [])


# ------------------------------------------------------------ happy path


def test_a_public_document_is_read():
    factory, client = client_for({PUBLIC: html("<html>HUD notice</html>")})
    result = fetch_customer_url(PUBLIC, resolver=ALL_PUBLIC, client_factory=factory)
    assert result.fetched is True
    assert "HUD notice" in result.body
    assert result.final_url == PUBLIC
    assert result.hops == (PUBLIC,)
    assert client.requested == [PUBLIC]


# ---------------------------------------------------- the destination gate


def test_a_host_resolving_internally_is_never_requested():
    """Refused before a socket opens, not after."""
    factory, client = client_for({INTERNAL: html()})
    result = fetch_customer_url(INTERNAL, resolver=HONEST, client_factory=factory)
    assert result.fetched is False
    assert client.requested == []
    assert any("destination_not_public" in r for r in result.blocked_reasons)


def test_a_host_that_does_not_resolve_is_refused():
    factory, client = client_for({})
    result = fetch_customer_url(
        "https://nowhere.example/x", resolver=resolver_for({}), client_factory=factory
    )
    assert result.fetched is False
    assert "host_was_not_resolved" in result.blocked_reasons
    assert client.requested == []


@pytest.mark.parametrize(
    "url",
    ["http://www.hud.gov/x", "file:///etc/passwd", "https://www.hud.gov:8080/x"],
)
def test_a_url_that_fails_safety_is_never_requested(url: str):
    factory, client = client_for({})
    result = fetch_customer_url(url, resolver=ALL_PUBLIC, client_factory=factory)
    assert result.fetched is False
    assert client.requested == []


# --------------------------------------------------------- the redirects


def test_a_public_page_cannot_redirect_this_server_somewhere_internal():
    """The rule this module exists for.

    hud.gov is public and stays public. It answers 302 to an address that
    resolves to the cloud metadata endpoint. The first host's being public
    does not vouch for the second, so the hop is re-resolved and refused.
    """
    factory, client = client_for(
        {PUBLIC: redirect(INTERNAL), INTERNAL: html("secrets")}
    )
    result = fetch_customer_url(PUBLIC, resolver=HONEST, client_factory=factory)

    assert result.fetched is False
    assert "redirect_destination_refused" in result.blocked_reasons
    # It was never asked for.
    assert client.requested == [PUBLIC]
    assert "secrets" not in result.body


def test_a_redirect_to_another_public_page_is_followed():
    second = "https://www.hud.gov/notice-final"
    factory, client = client_for({PUBLIC: redirect(second), second: html("final")})
    result = fetch_customer_url(PUBLIC, resolver=ALL_PUBLIC, client_factory=factory)
    assert result.fetched is True
    assert result.final_url == second
    assert result.hops == (PUBLIC, second)


def test_a_relative_redirect_is_resolved_against_the_current_url():
    target = "https://www.hud.gov/elsewhere"
    factory, _ = client_for({PUBLIC: redirect("/elsewhere"), target: html("moved")})
    result = fetch_customer_url(PUBLIC, resolver=ALL_PUBLIC, client_factory=factory)
    assert result.fetched is True
    assert result.final_url == target


def test_a_redirect_loop_terminates():
    other = "https://www.hud.gov/b"
    factory, client = client_for({PUBLIC: redirect(other), other: redirect(PUBLIC)})
    result = fetch_customer_url(PUBLIC, resolver=ALL_PUBLIC, client_factory=factory)
    assert result.fetched is False
    assert "too_many_redirects" in result.blocked_reasons
    assert len(client.requested) <= 7


def test_a_redirect_with_no_location_is_refused():
    factory, _ = client_for({PUBLIC: FakeResponse(302, {}, [])})
    result = fetch_customer_url(PUBLIC, resolver=ALL_PUBLIC, client_factory=factory)
    assert result.fetched is False
    assert "redirect_without_location" in result.blocked_reasons


def test_a_redirect_to_a_different_scheme_is_refused():
    factory, _ = client_for({PUBLIC: redirect("http://www.hud.gov/plain")})
    result = fetch_customer_url(PUBLIC, resolver=ALL_PUBLIC, client_factory=factory)
    assert result.fetched is False
    assert "redirect_destination_refused" in result.blocked_reasons


# ------------------------------------------------------------ the response


def test_a_non_document_content_type_is_refused():
    factory, _ = client_for(
        {PUBLIC: FakeResponse(200, {"content-type": "application/zip"}, [b"PK"])}
    )
    result = fetch_customer_url(PUBLIC, resolver=ALL_PUBLIC, client_factory=factory)
    assert result.fetched is False
    assert any("content_type_not_allowed" in r for r in result.blocked_reasons)


def test_an_overlong_body_stops_being_read():
    """The declared length can lie, so the cap is enforced as bytes arrive."""
    chunk = b"x" * (1024 * 1024)
    oversized = FakeResponse(
        200,
        {"content-type": "text/html"},
        [chunk] * (MAX_RESPONSE_BYTES // len(chunk) + 2),
    )
    factory, _ = client_for({PUBLIC: oversized})
    result = fetch_customer_url(PUBLIC, resolver=ALL_PUBLIC, client_factory=factory)
    assert result.fetched is False
    assert "response_exceeded_size_limit" in result.blocked_reasons


def test_an_honestly_declared_oversized_body_is_refused_before_transfer():
    factory, _ = client_for(
        {
            PUBLIC: FakeResponse(
                200,
                {
                    "content-type": "text/html",
                    "content-length": str(MAX_RESPONSE_BYTES + 1),
                },
                [b"x"],
            )
        }
    )
    result = fetch_customer_url(PUBLIC, resolver=ALL_PUBLIC, client_factory=factory)
    assert result.fetched is False
    assert any("response_too_large" in r for r in result.blocked_reasons)


def test_a_non_200_is_reported_rather_than_parsed():
    factory, _ = client_for(
        {PUBLIC: FakeResponse(404, {"content-type": "text/html"}, [])}
    )
    result = fetch_customer_url(PUBLIC, resolver=ALL_PUBLIC, client_factory=factory)
    assert result.fetched is False
    assert "http_status:404" in result.blocked_reasons


def test_a_transport_error_names_the_type_and_not_the_address():
    """An error message carries the address it tried, which is the one thing
    a refusal handed back to whoever supplied the URL must not contain."""
    factory, _ = client_for({})
    result = fetch_customer_url(PUBLIC, resolver=ALL_PUBLIC, client_factory=factory)
    assert result.fetched is False
    assert any(r.startswith("transport_error:") for r in result.blocked_reasons)
    assert PUBLIC_IP not in repr(result.blocked_reasons)


def test_the_audit_shape_carries_no_document_body():
    factory, _ = client_for({PUBLIC: html("<html>sensitive notice text</html>")})
    payload = fetch_customer_url(
        PUBLIC, resolver=ALL_PUBLIC, client_factory=factory
    ).as_dict()
    assert payload["fetched"] is True
    assert "body" not in payload
    assert "sensitive" not in repr(payload)
