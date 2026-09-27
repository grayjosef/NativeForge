"""Read a notice the customer already has as a file.

The third way in, beside the link and the paste. A funder emails a PDF, and
the customer should not have to select 40 pages of it, copy, and hope the
column order survived.

It reads and returns. Nothing is stored: the document goes through the same
reader a fetched page does, the text comes back for review, and the ordinary
create path makes the opportunity. That is deliberate - storing a customer's
document means a bucket, a retention answer and a deletion story, and this
route needs none of them to be useful.

## Why base64 in JSON and not a multipart upload

Multipart is the better shape and needs `python-multipart`, a dependency this
application does not have. Adding one to a deployment the day before it is
demonstrated buys a nicer request body and a new way for a build to fail.

So the bytes arrive base64-encoded, capped before they are decoded, and the
route is otherwise identical to the link one. When multipart is worth adding,
this becomes a thin wrapper and the reader below does not change.

## The cap is checked twice, and the first check is the encoded length

Decoding first and measuring afterwards means allocating whatever was sent.
The encoded length bounds the decoded length, so it is checked first.
"""

from __future__ import annotations

import base64
import binascii
import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from nativeforge.api.customer_org_context_dependency import (
    require_demo_org_session,
    require_real_org_session,
)
from nativeforge.api.customer_url_intake_routes import (
    FALLBACK_COPY,
    REFUSAL_COPY,
    reading_caveat,
)
from nativeforge.api.org_context import OrgContext
from nativeforge.api.tenant_guard import guard_same_org_403
from nativeforge.services import opportunity_contact_extraction_service as extract
from nativeforge.services.customer_url_notice_text_service import (
    notice_text_from_response,
)
from nativeforge.services.customer_url_safety_service import (
    ALLOWED_CONTENT_TYPES,
    MAX_RESPONSE_BYTES,
)

demo_document_intake_router = APIRouter(
    prefix="/v1/nf/demo/orgs", tags=["customer-document-intake-demo"]
)
real_document_intake_router = APIRouter(
    prefix="/v1/nf/real/orgs", tags=["customer-document-intake-real"]
)

#: base64 is four characters per three bytes, plus padding and any newlines a
#: client inserts. A little headroom, and still a bound.
MAX_ENCODED_CHARS = (MAX_RESPONSE_BYTES // 3 + 1) * 4 + 1024

DOCUMENT_REFUSAL_COPY: dict[str, str] = {
    "document_is_empty": "That file is empty.",
    "document_too_large": "That document is too large for NativeForge to read.",
    "document_not_decodable": "That file did not arrive intact. Try again.",
    "content_type_not_allowed": (
        "NativeForge cannot read that kind of file. It reads PDFs, web pages and "
        "plain text."
    ),
}


class DocumentIntakeBody(BaseModel):
    """One document, as the browser read it off disk."""

    filename: str = Field(default="", max_length=512)
    content_type: str = Field(min_length=1, max_length=255)
    #: The file's bytes, base64-encoded.
    #:
    #: No minimum length. A zero-byte file is something a customer can really
    #: pick, and it deserves "that file is empty" rather than a validation
    #: error about a field they have never heard of.
    content_base64: str = Field(default="", max_length=MAX_ENCODED_CHARS)


def _reason(reasons: list[str]) -> str:
    for raw in reasons:
        key = raw.split(":", 1)[0]
        if key in DOCUMENT_REFUSAL_COPY:
            return DOCUMENT_REFUSAL_COPY[key]
        if key in REFUSAL_COPY:
            return REFUSAL_COPY[key]
    return FALLBACK_COPY


def _refused(body: DocumentIntakeBody, reason: str) -> dict[str, Any]:
    return {
        "read": False,
        "filename": body.filename,
        "content_type": body.content_type,
        "message": _reason([reason]),
        "blocked_reasons": [reason],
    }


def _read(
    org_id: uuid.UUID, ctx: OrgContext, body: DocumentIntakeBody
) -> dict[str, Any]:
    guard_same_org_403(org_id, ctx)

    kind = body.content_type.split(";", 1)[0].strip().lower()
    if kind not in ALLOWED_CONTENT_TYPES:
        # The same list the fetcher enforces. A file the customer chose is not
        # a reason to read a format nothing here knows how to read.
        return _refused(body, f"content_type_not_allowed:{kind or 'unknown'}")

    try:
        raw = base64.b64decode(body.content_base64, validate=True)
    except (binascii.Error, ValueError):
        return _refused(body, "document_not_decodable")

    if not raw:
        return _refused(body, "document_is_empty")
    if len(raw) > MAX_RESPONSE_BYTES:
        return _refused(body, "document_too_large")

    notice = notice_text_from_response(content_type=kind, content_bytes=raw)

    opened = {
        "read": True,
        "filename": body.filename,
        "content_type": kind,
        "bytes_read": len(raw),
        "reading": notice.as_dict(),
    }

    if not notice.usable:
        return {
            **opened,
            "read": False,
            "message": _reason(list(notice.blocked_reasons)),
            "blocked_reasons": list(notice.blocked_reasons),
        }

    found = extract.extract(notice.text, text_complete=notice.status == "extracted")

    return {
        **opened,
        "message": reading_caveat(notice),
        "blocked_reasons": [],
        "notice_text": notice.text,
        "extracted": found.as_dict(),
    }


@demo_document_intake_router.post("/{org_id}/opportunity-intake/read-document")
def demo_read_document(
    org_id: uuid.UUID,
    body: DocumentIntakeBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    return _read(org_id, ctx, body)


@real_document_intake_router.post("/{org_id}/opportunity-intake/read-document")
def real_read_document(
    org_id: uuid.UUID,
    body: DocumentIntakeBody,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
) -> dict[str, Any]:
    return _read(org_id, ctx, body)
