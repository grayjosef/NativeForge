"""The third way a notice gets in: as a file the customer already has.

The route stores nothing, so most of what matters here is what it refuses and
what it admits it could not read. A scanned NOFO that comes back as an
opportunity with no contacts is the failure this file is written against.
"""

from __future__ import annotations

import base64
import uuid

import pytest
from fastapi.testclient import TestClient

from nativeforge.api import customer_document_intake_routes as routes
from nativeforge.main import create_app
from tests import session_org_helper as soh
from tests.test_customer_url_notice_text import CONTACT_LINES, build_pdf

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER = "cccccccc-dddd-eeee-ffff-000000000001"

NOTICE_HTML = b"""<html><body>
<h1>Indian Housing Block Grant Competitive</h1>
<h2>Program Contact</h2>
<p>Jane Doe, Program Officer</p>
<p>jane.doe@hud.gov</p>
</body></html>"""


def _path(org_id: str = DEMO) -> str:
    return f"/v1/nf/demo/orgs/{org_id}/opportunity-intake/read-document"


def body(raw: bytes, content_type: str, filename: str = "notice.pdf") -> dict:
    return {
        "filename": filename,
        "content_type": content_type,
        "content_base64": base64.b64encode(raw).decode(),
    }


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


# ------------------------------------------------------------ who may ask


def test_an_anonymous_caller_cannot_have_a_document_read(client):
    response = client.post(_path(), json=body(NOTICE_HTML, "text/html"))
    assert response.status_code == 401


def test_a_session_cannot_read_into_another_organization(client, demo_session):
    response = client.post(
        _path(OTHER), json=body(NOTICE_HTML, "text/html"), headers=demo_session
    )
    assert response.status_code == 403


# ----------------------------------------------------------------- reading


def test_a_pdf_notice_is_read(client, demo_session):
    pdf = build_pdf(CONTACT_LINES * 30)
    out = client.post(
        _path(), json=body(pdf, "application/pdf"), headers=demo_session
    ).json()

    assert out["read"] is True
    assert out["bytes_read"] == len(pdf)
    assert "jane.doe@hud.gov" in out["notice_text"]
    emails = [c.get("email") for c in out["extracted"]["contacts"]]
    assert "jane.doe@hud.gov" in emails


def test_an_html_notice_is_read(client, demo_session):
    out = client.post(
        _path(), json=body(NOTICE_HTML, "text/html", "notice.html"), headers=demo_session
    ).json()
    assert out["read"] is True
    assert "Program Contact" in out["notice_text"]


def test_nothing_is_stored(client, demo_session):
    """The document is read and handed back. There is no record to identify."""
    out = client.post(
        _path(), json=body(NOTICE_HTML, "text/html"), headers=demo_session
    ).json()
    assert "document_id" not in out
    assert "opportunity_id" not in out
    assert "id" not in out


def test_a_scanned_document_is_labelled_rather_than_returned_empty(
    client, demo_session
):
    """A PDF with no text layer. The one that must not read as "no contacts"."""
    out = client.post(
        _path(), json=body(build_pdf([]), "application/pdf"), headers=demo_session
    ).json()

    assert out["read"] is False
    assert out["reading"]["status"] == "needs_ocr_or_manual_review"
    assert out["message"]
    assert "extracted" not in out


# --------------------------------------------------------------- refusals


@pytest.mark.parametrize(
    "content_type", ["application/zip", "image/png", "application/octet-stream"]
)
def test_a_format_nothing_can_read_is_refused_by_name(
    client, demo_session, content_type: str
):
    out = client.post(
        _path(), json=body(b"\x00\x01\x02", content_type), headers=demo_session
    ).json()
    assert out["read"] is False
    assert "PDFs, web pages and plain text" in out["message"]


def test_a_file_claiming_to_be_a_pdf_and_not_being_one_is_refused(
    client, demo_session
):
    out = client.post(
        _path(), json=body(b"<html>gotcha</html>", "application/pdf"), headers=demo_session
    ).json()
    assert out["read"] is False
    assert "not_a_pdf_missing_magic_bytes" in out["blocked_reasons"]


def test_an_empty_file_is_refused(client, demo_session):
    out = client.post(
        _path(), json=body(b"", "application/pdf"), headers=demo_session
    ).json()
    assert out["read"] is False


def test_something_that_is_not_base64_is_refused_rather_than_raising(
    client, demo_session
):
    payload = {
        "filename": "x.pdf",
        "content_type": "application/pdf",
        "content_base64": "this is not base64!!",
    }
    response = client.post(_path(), json=payload, headers=demo_session)
    assert response.status_code == 200
    assert response.json()["read"] is False


def test_an_oversized_document_is_refused_before_it_is_decoded(client, demo_session):
    """The encoded length bounds the decoded length, and is checked first.

    Decoding to find out how big it was means allocating whatever was sent.
    """
    payload = {
        "filename": "big.pdf",
        "content_type": "application/pdf",
        "content_base64": "A" * (routes.MAX_ENCODED_CHARS + 4),
    }
    response = client.post(_path(), json=payload, headers=demo_session)
    assert response.status_code == 422


def test_the_cap_matches_the_one_the_fetcher_enforces():
    """One limit for a document, however it arrived."""
    from nativeforge.services.customer_url_safety_service import MAX_RESPONSE_BYTES

    assert routes.MAX_RESPONSE_BYTES == MAX_RESPONSE_BYTES
    assert routes.MAX_ENCODED_CHARS > MAX_RESPONSE_BYTES
