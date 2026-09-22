"""Adapter: Bureau of Indian Affairs program page (HTML, single document).

The document-shaped half of Gate 171's heterogeneity requirement. One GET, one
HTML page, one record, no pagination and no link following.

## What this adapter does NOT do

It extracts links and it does not fetch them. `max_crawl_depth` is 0 and every
`DocumentReference` it emits carries `fetched=False`, so a later gate that
wants attachments has to authorize that separately rather than inherit it. A
program page links to the rest of the agency; following those links is how one
bounded collection becomes a crawl of bia.gov.

## Field extraction is deliberately shallow

Title and the page's own headings are structural and safe to read. Dates,
eligibility and amounts are NOT extracted by pattern-matching prose here: this
adapter reports the fields it can see structurally and declares only those in
`supported_fields`. A regex that finds "March 3" in a paragraph about last
year's award cycle and files it as a deadline is worse than no deadline, and
Gate 170 would then classify the resulting move as a CRITICAL amendment.

The response shape is a hypothesis until a real collection confirms it. See
the Gate 171E approval packet.
"""

from __future__ import annotations

import hashlib
import re
from html.parser import HTMLParser
from typing import Any

from nativeforge.services.html_notice_text_adapter_service import (
    extract_html_notice_text,
)
from nativeforge.services.source_adapter_contract_service import (
    MEDIA_HTML,
    DocumentReference,
    PageCursor,
    SourceDescriptor,
    SourceRecord,
    canonical_url,
    deduplicate_documents,
)

ADAPTER_KEY = "bia_program_page_html"
ADAPTER_VERSION = "gate171_v1"

#: One page, one record. Declared so the generic bounds check can refuse a
#: descriptor that later tries to widen this by configuration.
MAX_PAGES = 1
MAX_RECORDS = 1
MAX_CRAWL_DEPTH = 0

#: Declared, because an adapter that has not decided what to do on a 429
#: hammers the source at fleet scale. One attempt: a program page that is
#: momentarily unavailable is a fact about the page, and the scheduler owns
#: trying again later.
RETRY_POLICY = {
    "max_attempts": 1,
    "retry_on": [],
    "backoff": "none",
    "why": "a_scheduled_recheck_is_the_retry_for_a_static_page",
}
RATE_LIMIT_POLICY = {
    "requests_per_run": 1,
    "minimum_seconds_between_runs": 86400,
    "honors_retry_after": True,
    "on_429": "abandon_run_and_record_the_status",
}

#: Attachment-ish document types worth NAMING when linked. Naming is not
#: fetching.
_DOCUMENT_SUFFIXES = (".pdf", ".doc", ".docx", ".xls", ".xlsx")

_TITLE = re.compile(r"<title[^>]*>(.*?)</title>", re.I | re.S)


class _LinkReader(HTMLParser):
    """Collects hrefs. Opens nothing."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.links: list[tuple[str, str]] = []
        self._href: str | None = None
        self._text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() != "a":
            return
        for name, value in attrs:
            if name.lower() == "href" and value:
                self._href = value
                self._text = []

    def handle_data(self, data: str) -> None:
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._href is not None:
            self.links.append((self._href, " ".join(self._text).strip()))
            self._href = None
            self._text = []


def build_descriptor(
    *,
    source_id: str = "nf-seed-2026-fed-007",
    source_url: str = "https://www.bia.gov/service/grants/ttgp/apply-ttgp-grant",
) -> SourceDescriptor:
    """`source_id` and `source_url` are the uniform binding every adapter takes.

    The caller passes the registry's id and URL so a descriptor cannot drift
    from the row it is supposed to describe. The defaults are the approved
    values, not a second source of truth.
    """
    page_url = source_url
    return SourceDescriptor(
        source_id=source_id,
        adapter_key=ADAPTER_KEY,
        display_name="BIA program page",
        publisher="Bureau of Indian Affairs, U.S. Department of the Interior",
        base_url=page_url,
        transport_method="GET",
        auth_mode="none",
        pagination_model="single_document",
        expected_media_types=(MEDIA_HTML,),
        max_pages=MAX_PAGES,
        max_records=MAX_RECORDS,
        max_crawl_depth=MAX_CRAWL_DEPTH,
        attribution_required=True,
        attribution_text=(
            "Source: Bureau of Indian Affairs, U.S. Department of the Interior"
        ),
        request_shape={"method": "GET", "url": page_url, "query": {}, "body": None},
    )


def build_request(
    *,
    descriptor: SourceDescriptor,
    authorization: Any,
    cursor: PageCursor | None = None,
) -> Any:
    """One GET at the descriptor's URL. Refuses without an authorization."""
    if authorization is None:
        raise PermissionError(
            "bia_program_page_html_refuses_to_build_a_request_without_an_authorization"
        )
    if cursor is not None and cursor.page_index >= MAX_PAGES:
        raise ValueError("bia_program_page_html_is_a_single_document_source")

    from nativeforge.services.source_collection_transport_service import (
        TransportRequest,
    )

    return TransportRequest(
        method="GET",
        url=descriptor.base_url,
        headers={"Accept": "text/html"},
    )


def _absolute(href: str, base: str) -> str:
    text = str(href or "").strip()
    if not text or text.startswith(("#", "mailto:", "javascript:")):
        return ""
    if text.startswith("http"):
        return text
    match = re.match(r"^(https?://[^/]+)", base)
    root = match.group(1) if match else ""
    if text.startswith("/"):
        return root + text
    return base.rstrip("/") + "/" + text


def read_records(
    *,
    descriptor: SourceDescriptor,
    body_bytes: bytes,
    media_type: str | None,
    cursor: PageCursor | None = None,
) -> list[SourceRecord]:
    """One HTML page becomes at most one record."""
    if media_type is not None and media_type != MEDIA_HTML:
        raise ValueError(f"bia_program_page_html_expects_html_not:{media_type}")

    payload = bytes(body_bytes or b"")
    if not payload.strip():
        return []

    text = payload.decode("utf-8", errors="replace")
    if "<" not in text:
        raise ValueError("bia_program_page_html_received_no_markup")

    extracted = extract_html_notice_text(html=text)
    if extracted.get("blocked_reasons"):
        raise ValueError(
            "bia_program_page_html_could_not_extract:"
            + ",".join(str(r) for r in extracted["blocked_reasons"])
        )

    title_match = _TITLE.search(text)
    title = (title_match.group(1).strip() if title_match else "") or None

    reader = _LinkReader()
    reader.feed(text)
    documents: list[DocumentReference] = []
    for href, label in reader.links:
        absolute = _absolute(href, descriptor.base_url)
        if not absolute:
            continue
        lowered = absolute.lower()
        relationship = (
            "attachment"
            if lowered.endswith(_DOCUMENT_SUFFIXES)
            else "related"
        )
        documents.append(
            DocumentReference(
                url=absolute,
                relationship=relationship,
                title=label or None,
                depth=0,
                fetched=False,
            )
        )
    documents, suppressed = deduplicate_documents(documents)

    page_url = canonical_url(descriptor.base_url)
    # Derived, not allocated: the same page yields the same record id, which
    # is what makes a re-collection a replay rather than a new record.
    record_id = hashlib.sha256(page_url.encode("utf-8")).hexdigest()[:32]

    # Canonical fields only. `funder_agency_name` is the canonical spelling -
    # `funder_agency` is not in the vocabulary and would have been refused by
    # the normalizer as an invented field.
    fields: dict[str, Any] = {
        "source_record_id": record_id,
        "source_url": page_url,
        "title": title,
        "funder_agency_name": descriptor.publisher,
    }
    # Measured, but not canonical opportunity facts.
    metrics = {
        "document_count": len(documents),
        "duplicate_documents_suppressed": suppressed,
        "page_text_chars": int(extracted.get("text_chars") or 0),
        "extraction_warnings": list(extracted.get("warnings") or []),
    }
    # A field nobody could read is absent, not empty. The graph must be able
    # to tell "this source does not publish a deadline" from "the deadline is
    # blank", because only the second one can ever be a conflict.
    supported = tuple(name for name, value in fields.items() if value is not None)

    return [
        SourceRecord(
            source_record_id=record_id,
            fields={k: v for k, v in fields.items() if k in supported},
            supported_fields=supported,
            evidence_sha256=hashlib.sha256(payload).hexdigest(),
            documents=tuple(documents),
            page_index=0 if cursor is None else cursor.page_index,
            metrics=metrics,
        )
    ]
