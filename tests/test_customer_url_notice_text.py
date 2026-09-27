"""Turning a fetched response into prose, and refusing to pretend.

The failure this file exists to prevent is silent: `decode("utf-8",
errors="replace")` on a PDF does not raise, it returns a page of replacement
characters with fragments of legible text in it. Contact extraction over that
returns a confident, wrong answer.

Nothing here opens a socket. The PDFs are built byte by byte so the readable
path is exercised for real rather than mocked into agreement.
"""

from __future__ import annotations

import pytest

from nativeforge.services.customer_url_notice_text_service import (
    notice_text_from_response,
)

NOTICE_HTML = """<!doctype html>
<html>
  <head>
    <title>Indian Housing Block Grant</title>
    <style>.x { color: red }</style>
    <script>var contact = "script.person@example.com";</script>
  </head>
  <body>
    <nav>Home | Grants | Contact Us</nav>
    <h1>Indian Housing Block Grant Competitive</h1>
    <p>Applications are due January 15, 2027 at 11:59 PM Eastern Time.</p>
    <h2>Program Contact</h2>
    <p>Jane Doe, Program Officer</p>
    <p>Office of Native American Programs</p>
    <p>jane.doe@hud.gov</p>
    <p>(202) 555-0143</p>
    <!-- comment.person@example.com -->
  </body>
</html>
"""


def build_pdf(lines: list[str]) -> bytes:
    """A minimal one-page PDF with a real text stream.

    Hand-built rather than fixtured so the test carries its own input and the
    extraction it proves is the real one.
    """
    stream_lines = ["BT", "/F1 12 Tf", "72 720 Td", "14 TL"]
    for line in lines:
        escaped = line.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream_lines.extend([f"({escaped}) Tj", "T*"])
    stream_lines.append("ET")
    content = "\n".join(stream_lines).encode("latin-1")

    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Resources << /Font << /F1 5 0 R >> >> /Contents 4 0 R >>",
        b"<< /Length "
        + str(len(content)).encode()
        + b" >>\nstream\n"
        + content
        + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]

    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += str(i).encode() + b" 0 obj\n" + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 " + str(len(objects) + 1).encode() + b"\n0000000000 65535 f \n"
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += (
        b"trailer\n<< /Size "
        + str(len(objects) + 1).encode()
        + b" /Root 1 0 R >>\nstartxref\n"
        + str(xref).encode()
        + b"\n%%EOF\n"
    )
    return bytes(out)


CONTACT_LINES = [
    "Program Contact",
    "Jane Doe, Program Officer",
    "Office of Native American Programs",
    "jane.doe@hud.gov",
]


# ------------------------------------------------------------------- HTML


def test_a_notice_page_becomes_readable_text():
    notice = notice_text_from_response(
        content_type="text/html; charset=utf-8",
        content_bytes=NOTICE_HTML.encode(),
    )
    assert notice.status == "extracted"
    assert notice.usable is True
    assert notice.method == "stdlib_html_parser"
    assert "Program Contact" in notice.text
    assert "jane.doe@hud.gov" in notice.text


def test_script_and_comment_text_never_reach_the_extractor():
    """Both look like contact details and neither is one.

    An address out of a `<script>` body is not something a human wrote into
    the notice, and extraction downstream cannot tell the difference.
    """
    notice = notice_text_from_response(
        content_type="text/html", content_bytes=NOTICE_HTML.encode()
    )
    assert "script.person@example.com" not in notice.text
    assert "comment.person@example.com" not in notice.text


def test_the_content_type_parameters_do_not_confuse_the_reader():
    for header in ("text/html;charset=UTF-8", "TEXT/HTML", " text/html ; x=y"):
        assert notice_text_from_response(
            content_type=header, content_bytes=NOTICE_HTML.encode()
        ).status == "extracted"


def test_a_page_with_no_text_is_refused_rather_than_returned_empty():
    notice = notice_text_from_response(
        content_type="text/html",
        content_bytes=b"<html><head><script>x=1</script></head><body></body></html>",
    )
    assert notice.usable is False
    assert notice.status == "blocked"


# -------------------------------------------------------------- plain text


def test_plain_text_is_taken_as_it_is():
    notice = notice_text_from_response(
        content_type="text/plain",
        content_bytes=b"Program Contact\n\n\n\nJane Doe    (202) 555-0143\n",
    )
    assert notice.status == "extracted"
    assert notice.method == "plain_text"
    assert "Jane Doe (202) 555-0143" in notice.text
    # No headings to section on, so it is never presented as fully understood.
    assert notice.human_review_required is True


def test_whitespace_only_text_is_refused():
    notice = notice_text_from_response(
        content_type="text/plain", content_bytes=b"   \n\n \t\n"
    )
    assert notice.usable is False
    assert "no_text_after_extraction" in notice.blocked_reasons


# --------------------------------------------------------------------- PDF


def test_a_text_bearing_pdf_is_read():
    notice = notice_text_from_response(
        content_type="application/pdf", content_bytes=build_pdf(CONTACT_LINES * 30)
    )
    assert notice.status == "extracted"
    assert notice.usable is True
    assert notice.method == "pdf_text_extraction"
    assert notice.page_count == 1
    assert "jane.doe@hud.gov" in notice.text


def test_a_pdf_is_never_decoded_as_utf8():
    """The whole reason this module exists.

    The naive path does not raise; it produces replacement characters and a
    few legible fragments, which extraction downstream reads as a document.
    """
    pdf = build_pdf(CONTACT_LINES * 30)
    naive = pdf.decode("utf-8", errors="replace")
    notice = notice_text_from_response(
        content_type="application/pdf", content_bytes=pdf
    )
    assert "�" not in notice.text
    assert notice.text != naive
    # And the real text is there, which the naive decode would have buried.
    assert "Office of Native American Programs" in notice.text


def test_a_pdf_with_no_text_asks_for_a_human_rather_than_guessing():
    """A scanned notice. OCR is out of scope here, so it says so."""
    notice = notice_text_from_response(
        content_type="application/pdf", content_bytes=build_pdf([])
    )
    assert notice.status == "needs_ocr_or_manual_review"
    assert notice.human_review_required is True
    assert notice.usable is False


def test_something_that_is_not_a_pdf_is_refused():
    notice = notice_text_from_response(
        content_type="application/pdf", content_bytes=b"<html>not a pdf</html>"
    )
    assert notice.usable is False
    assert "not_a_pdf_missing_magic_bytes" in notice.blocked_reasons


def test_the_staged_pdf_file_does_not_outlive_the_extraction(tmp_path, monkeypatch):
    """The bytes are written down; they must not stay written down."""
    monkeypatch.setattr("tempfile.tempdir", str(tmp_path))
    notice_text_from_response(
        content_type="application/pdf", content_bytes=build_pdf(CONTACT_LINES * 30)
    )
    assert list(tmp_path.iterdir()) == []


# ------------------------------------------------------------- the refusals


@pytest.mark.parametrize(
    "content_type", ["application/zip", "image/png", "", "application/octet-stream"]
)
def test_an_unreadable_type_is_named_rather_than_attempted(content_type: str):
    notice = notice_text_from_response(
        content_type=content_type, content_bytes=b"\x00\x01\x02"
    )
    assert notice.usable is False
    assert any(
        r.startswith("content_type_not_readable") for r in notice.blocked_reasons
    )


def test_an_empty_body_is_refused():
    notice = notice_text_from_response(content_type="text/html", content_bytes=b"")
    assert notice.usable is False
    assert "empty_response_body" in notice.blocked_reasons


def test_the_summary_shape_carries_no_document_text():
    """It goes into the audit line; the notice does not belong there."""
    payload = notice_text_from_response(
        content_type="text/html", content_bytes=NOTICE_HTML.encode()
    ).as_dict()
    assert payload["status"] == "extracted"
    assert payload["text_chars"] > 0
    assert "text" not in payload
    assert "jane.doe@hud.gov" not in repr(payload)
