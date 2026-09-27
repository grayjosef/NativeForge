"""Read a public opportunity page a signed-in customer named.

One POST per plane. It takes a URL, fetches it if and only if every layer
below agrees, reads it, and returns what was found — it creates nothing. The
customer reviews the result and the existing create path makes the
opportunity, so a fetch that lands on the wrong page costs a glance rather
than a record.

## Why the route does so little

The interesting decisions are all somewhere else and all testable without a
network: `customer_url_safety_service` decides whether the destination is
public, `live_network_guard_service` decides whether the request may proceed,
`customer_supplied_url_fetch_service` is the only module that opens a socket,
and `customer_url_notice_text_service` turns bytes into prose. This route
authenticates the caller, hands the URL down, and turns the answer into
something a page can render.

## Three ways this ends, and they are not the same

    could not open it    a refusal, and the reason is not the customer's fault
    opened, unreadable   a scanned PDF, an image, a page that is all script
    opened and read      text, with an honest confidence on it

Collapsing the middle case into either of the others is how a customer ends
up believing NativeForge read a document it could not read.

## Authentication is the authorization

The `customer_supplied_url` purpose means *a signed-in tenant user named this
address*. The session dependency is what makes that true, so it is not
optional and there is no unauthenticated variant: without it the purpose
would be a description of nobody.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from nativeforge.api.customer_org_context_dependency import (
    require_demo_org_session,
    require_real_org_session,
)
from nativeforge.api.org_context import OrgContext
from nativeforge.api.tenant_guard import guard_same_org_403
from nativeforge.services import opportunity_contact_extraction_service as extract
from nativeforge.services.customer_supplied_url_fetch_service import (
    fetch_customer_url,
)
from nativeforge.services.customer_url_notice_text_service import (
    notice_text_from_response,
)

demo_url_intake_router = APIRouter(
    prefix="/v1/nf/demo/orgs", tags=["customer-url-intake-demo"]
)
real_url_intake_router = APIRouter(
    prefix="/v1/nf/real/orgs", tags=["customer-url-intake-real"]
)

#: Customer-facing copy for the refusals this path can produce.
#:
#: Mapped rather than echoed. A reason like `destination_not_public:link_local`
#: is exactly right in an audit line and means nothing to a grants manager,
#: and the raw text would also tell whoever supplied the URL something about
#: the network it reached.
REFUSAL_COPY: dict[str, str] = {
    # Before the request.
    "url_is_empty": "Enter the address of the opportunity page.",
    "url_is_unparseable": "That does not look like a web address.",
    "url_has_no_host": "That does not look like a web address.",
    "url_contains_credentials": (
        "That link contains a username or password. Use the public address of the page."
    ),
    "host_was_not_resolved": "That address could not be found.",
    "destination_not_public": (
        "That address is not a public web page, so NativeForge will not open it."
    ),
    "scheme_not_allowed": "NativeForge only opens secure (https) addresses.",
    "port_not_allowed": "NativeForge only opens pages served on the standard web port.",
    "robots_does_not_permit": (
        "That site asks automated readers not to fetch this page. "
        "Paste the notice text instead."
    ),
    "gate77b_hermetic_guard_blocks_grants_gov": (
        "Grants.gov opportunities are read through NativeForge's own connection "
        "to Grants.gov rather than by opening the link. Search for it in "
        "Discovery instead."
    ),
    # During the request.
    "redirect_destination_refused": (
        "That page redirected somewhere NativeForge will not follow."
    ),
    "too_many_redirects": "That page redirected too many times.",
    "redirect_without_location": "That page redirected without saying where to.",
    "content_type_not_allowed": (
        "That address is not a web page or PDF. Paste the notice text instead."
    ),
    "content_type_missing": "That address did not say what kind of file it is.",
    "response_too_large": "That document is too large for NativeForge to read.",
    "response_exceeded_size_limit": "That document is too large for NativeForge to read.",
    "http_status": "That page could not be opened.",
    "transport_error": "NativeForge could not reach that address.",
    # After the request, while reading it.
    "empty_response_body": "That page came back empty.",
    "no_text_after_extraction": (
        "That page has no readable text. Paste the notice text instead."
    ),
    "no_html_supplied": "That page has no readable text. Paste the notice text instead.",
    "empty_html": "That page came back empty.",
    "content_type_not_readable": (
        "NativeForge cannot read that kind of file. Paste the notice text instead."
    ),
    "could_not_stage_document": "NativeForge could not open that document.",
    "no_pdf_backend_available": "NativeForge cannot read PDFs on this server yet.",
}

FALLBACK_COPY = "NativeForge could not read that address."

#: Said when the document opened but the text is not trustworthy enough to
#: present as complete. Neither is a refusal: the customer keeps what was
#: found, and is told which kind of doubt it carries, because "partly read"
#: and "read, but thin" call for different checks.
PARTIAL_COPY = (
    "This looks like a scanned document, so NativeForge could only read part of "
    "it. Check anything it filled in, and paste the notice text if it is wrong."
)
REVIEW_COPY = (
    "NativeForge read this page, but could not find much structure in it. "
    "Check what it filled in before you save."
)


class UrlIntakeBody(BaseModel):
    url: str = Field(min_length=1, max_length=2048)


def _customer_reason(raw_reasons: list[str]) -> str:
    """One sentence, from the first reason that has copy written for it."""
    for reason in raw_reasons:
        key = reason.split(":", 1)[0]
        if key in REFUSAL_COPY:
            return REFUSAL_COPY[key]
        if reason in REFUSAL_COPY:
            return REFUSAL_COPY[reason]
    return FALLBACK_COPY


def reading_caveat(notice) -> str:
    """Nothing, or the specific doubt - never a generic one."""
    if notice.status == "needs_ocr_or_manual_review":
        return PARTIAL_COPY
    if notice.human_review_required:
        return REVIEW_COPY
    return ""


def _read(org_id: uuid.UUID, ctx: OrgContext, body: UrlIntakeBody) -> dict[str, Any]:
    guard_same_org_403(org_id, ctx)

    result = fetch_customer_url(body.url)
    if not result.fetched:
        return {
            "fetched": False,
            "readable": False,
            "url": body.url,
            "message": _customer_reason(list(result.blocked_reasons)),
            # The machine-readable reasons stay, for the operator surfaces and
            # the audit trail. The page renders `message`.
            "blocked_reasons": list(result.blocked_reasons),
            "hops": list(result.hops),
        }

    notice = notice_text_from_response(
        content_type=result.content_type, content_bytes=result.content_bytes
    )

    opened = {
        "fetched": True,
        "url": body.url,
        "final_url": result.final_url,
        "content_type": result.content_type,
        "bytes_read": result.bytes_read,
        "hops": list(result.hops),
        "reading": notice.as_dict(),
    }

    if not notice.usable:
        # Opened, but there is nothing to extract from. Saying so is the whole
        # point: an empty extraction rendered as a result reads like an
        # opportunity with no contacts rather than a document nobody read.
        return {
            **opened,
            "readable": False,
            "message": _customer_reason(list(notice.blocked_reasons)),
            "blocked_reasons": list(notice.blocked_reasons),
        }

    # The same extractor every other notice goes through. A page NativeForge
    # fetched is not a different kind of evidence from one a customer pasted.
    found = extract.extract(notice.text, text_complete=notice.status == "extracted")

    return {
        **opened,
        "readable": True,
        "message": reading_caveat(notice),
        "blocked_reasons": [],
        # Handed back for the customer to review and, if they accept it,
        # submit through the ordinary create path. Nothing is stored here.
        "notice_text": notice.text,
        "extracted": found.as_dict(),
    }


@demo_url_intake_router.post("/{org_id}/opportunity-intake/read-url")
def demo_read_url(
    org_id: uuid.UUID,
    body: UrlIntakeBody,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    return _read(org_id, ctx, body)


@real_url_intake_router.post("/{org_id}/opportunity-intake/read-url")
def real_read_url(
    org_id: uuid.UUID,
    body: UrlIntakeBody,
    ctx: Annotated[OrgContext, Depends(require_real_org_session)],
) -> dict[str, Any]:
    return _read(org_id, ctx, body)
