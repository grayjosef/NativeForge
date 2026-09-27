"""The one route on the `customer_supplied_url` purpose.

What a customer sees when they paste a link, including when it does not work.
The fetcher is substituted here on purpose: its own suite proves the network
behaviour without a socket, and repeating that through HTTP would only prove
it twice. What is left for this file is the part only the route decides —
who may ask, what gets said back, and what never gets said back.

Three endings, and the middle one is the one software usually gets wrong:

```text
could not open it    refused, with a sentence a grants manager can act on
opened, unreadable   said so, rather than showing an empty extraction
opened and read      the text, with the doubt still attached
```
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from nativeforge.api import customer_url_intake_routes as routes
from nativeforge.main import create_app
from nativeforge.services.customer_supplied_url_fetch_service import FetchResult
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER = "cccccccc-dddd-eeee-ffff-00000000d171"

URL = "https://www.hud.gov/program_offices/public_indian_housing/ih/codetalk"

NOTICE_HTML = b"""<html><body>
<h1>Indian Housing Block Grant Competitive</h1>
<p>Applications are due January 15, 2027 at 11:59 PM Eastern Time.</p>
<h2>Program Contact</h2>
<p>Jane Doe, Program Officer</p>
<p>Office of Native American Programs</p>
<p>jane.doe@hud.gov</p>
<p>(202) 555-0143</p>
<h2>How to Submit</h2>
<p>Submit your application at https://www.grants.gov/ under CFDA 14.867.</p>
</body></html>"""


def _path(org_id: str = DEMO) -> str:
    return f"/v1/nf/demo/orgs/{org_id}/opportunity-intake/read-url"


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def demo_session():
    soh.ensure_signing_key()
    soh.ensure_org(DEMO, "demo")
    soh.ensure_org(OTHER, "demo")
    soh.ensure_member(DEMO)
    return soh.session_headers(uuid.UUID(DEMO))


def serve(monkeypatch, result: FetchResult) -> list[str]:
    """Substitute the fetcher and record what it was asked for."""
    asked: list[str] = []

    def fake(url: str, **kwargs):
        asked.append(url)
        return result

    monkeypatch.setattr(routes, "fetch_customer_url", fake)
    return asked


def ok(body: bytes = NOTICE_HTML, content_type: str = "text/html") -> FetchResult:
    return FetchResult(
        fetched=True,
        url=URL,
        final_url=URL,
        status_code=200,
        content_type=content_type,
        body=body.decode("utf-8", errors="replace"),
        content_bytes=body,
        bytes_read=len(body),
        hops=(URL,),
    )


def refused(*reasons: str) -> FetchResult:
    return FetchResult(fetched=False, url=URL, blocked_reasons=reasons)


# ------------------------------------------------------------ who may ask


def test_an_anonymous_caller_cannot_make_this_server_fetch_anything(
    client, monkeypatch
):
    """The purpose means *a signed-in tenant user named this address*.

    Without the session there is nobody the purpose could be describing, and
    the route would be an open fetcher wearing NativeForge's user agent.
    """
    asked = serve(monkeypatch, ok())
    response = client.post(_path(), json={"url": URL})
    assert response.status_code == 401
    assert asked == []


def test_a_session_cannot_fetch_on_behalf_of_another_organization(
    client, demo_session, monkeypatch
):
    asked = serve(monkeypatch, ok())
    response = client.post(_path(OTHER), json={"url": URL}, headers=demo_session)
    assert response.status_code == 403
    assert asked == []


def test_a_signed_in_member_may_ask(client, demo_session, monkeypatch):
    asked = serve(monkeypatch, ok())
    response = client.post(_path(), json={"url": URL}, headers=demo_session)
    assert response.status_code == 200
    assert asked == [URL]


# --------------------------------------------------------- opened and read


def test_a_notice_page_comes_back_read(client, demo_session, monkeypatch):
    serve(monkeypatch, ok())
    body = client.post(_path(), json={"url": URL}, headers=demo_session).json()

    assert body["fetched"] is True
    assert body["readable"] is True
    assert body["final_url"] == URL
    assert "Program Contact" in body["notice_text"]

    found = body["extracted"]
    emails = [c.get("email") for c in found["contacts"]]
    assert "jane.doe@hud.gov" in emails


def test_nothing_is_created_by_reading(client, demo_session, monkeypatch):
    """A fetch that lands on the wrong page must cost a glance, not a record.

    The response carries no identifier because there is nothing to identify:
    the customer reviews this and the ordinary create path makes the
    opportunity.
    """
    serve(monkeypatch, ok())
    body = client.post(_path(), json={"url": URL}, headers=demo_session).json()
    assert "opportunity_id" not in body
    assert "spark_id" not in body
    assert "id" not in body


def test_the_reading_carries_its_own_confidence(client, demo_session, monkeypatch):
    serve(monkeypatch, ok())
    body = client.post(_path(), json={"url": URL}, headers=demo_session).json()
    reading = body["reading"]
    assert reading["status"] == "extracted"
    assert reading["method"] == "stdlib_html_parser"
    assert "confidence" in reading


# ------------------------------------------------------ opened, unreadable


def test_a_scanned_document_is_labelled_rather_than_shown_as_empty(
    client, demo_session, monkeypatch
):
    """The ending that gets conflated.

    An empty extraction rendered as a result reads like an opportunity with
    no contacts, rather than a document nobody could read.
    """
    serve(monkeypatch, ok(b"%PDF-1.4 not really", "application/pdf"))
    body = client.post(_path(), json={"url": URL}, headers=demo_session).json()

    assert body["fetched"] is True
    assert body["readable"] is False
    assert body["message"]
    assert "extracted" not in body
    assert "notice_text" not in body


def test_a_page_with_no_text_says_so(client, demo_session, monkeypatch):
    serve(monkeypatch, ok(b"<html><body></body></html>"))
    body = client.post(_path(), json={"url": URL}, headers=demo_session).json()
    assert body["readable"] is False
    assert "paste the notice text" in body["message"].lower()


# --------------------------------------------------------- could not open


@pytest.mark.parametrize(
    ("reason", "fragment"),
    [
        ("destination_not_public:link_local", "not a public web page"),
        ("scheme_not_allowed:http", "secure (https)"),
        ("host_was_not_resolved", "could not be found"),
        ("url_contains_credentials", "username or password"),
        ("response_exceeded_size_limit", "too large"),
        ("http_status:404", "could not be opened"),
        ("transport_error:ConnectError", "could not reach"),
        ("redirect_destination_refused", "redirected somewhere"),
        ("robots_does_not_permit", "automated readers"),
    ],
)
def test_each_refusal_is_a_sentence_not_a_code(
    client, demo_session, monkeypatch, reason: str, fragment: str
):
    serve(monkeypatch, refused(reason))
    body = client.post(_path(), json={"url": URL}, headers=demo_session).json()
    assert body["fetched"] is False
    assert body["readable"] is False
    assert fragment in body["message"]
    # The code survives for the operator surfaces; the page renders the sentence.
    assert reason in body["blocked_reasons"]


def test_a_refusal_never_puts_the_internal_address_in_front_of_the_customer(
    client, demo_session, monkeypatch
):
    """Whoever supplied the URL is who reads this message.

    A reason naming 169.254.169.254 would confirm to them what the address
    resolved to, which is a small map of the deployment's network.
    """
    serve(monkeypatch, refused("destination_not_public:link_local"))
    body = client.post(_path(), json={"url": URL}, headers=demo_session).json()
    assert "169.254" not in body["message"]
    assert "link_local" not in body["message"]


def test_an_unmapped_reason_still_gets_a_sentence(
    client, demo_session, monkeypatch
):
    """A refusal nobody wrote copy for must not render as an empty message."""
    serve(monkeypatch, refused("something_nobody_anticipated"))
    body = client.post(_path(), json={"url": URL}, headers=demo_session).json()
    assert body["message"] == routes.FALLBACK_COPY


def test_grants_gov_is_sent_to_discovery_rather_than_fetched():
    """Gate 77B owns Grants.gov, and this route must not read like a way round.

    Checked on the mapping rather than through the route, because reaching
    the real refusal would resolve a hostname.
    """
    message = routes._customer_reason(["gate77b_hermetic_guard_blocks_grants_gov"])
    assert "Discovery" in message


# ----------------------------------------------------------- the input


@pytest.mark.parametrize("value", ["", " " * 3000])
def test_an_unusable_url_is_rejected_before_anything_happens(
    client, demo_session, monkeypatch, value: str
):
    asked = serve(monkeypatch, ok())
    response = client.post(_path(), json={"url": value}, headers=demo_session)
    assert response.status_code == 422
    assert asked == []
