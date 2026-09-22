"""Adapter: Federal Register documents (JSON API, paginated).

The API-shaped half of Gate 171's heterogeneity requirement, and a materially
different workload from the document adapter beside it: a POST-free structured
query, many records per response, explicit paging, and a continuation decided
by a field in the body rather than by there being nothing left to read.

## Why this source

The repository's own federal seed catalog names it, with the rationale that it
is the "authoritative channel for funding notices, deadline extensions and
amendments" and the evidence source behind the Gate 76 freshness rules. That
makes it the one candidate whose value is specifically Gate 170's: a second
witness to a deadline moving.

## What is established and what is a hypothesis

ESTABLISHED in this repository: the host, and that the catalog classes it as
`public_api`. Everything else here - the path, the parameter names, the
response envelope - is the intended request shape written down so a human can
approve or correct it, NOT a fact this repository has verified. Gate 171E
lists it as UNKNOWN, and `read_records` stays a hypothesis until a real
collection confirms the envelope.

## Per-page bound

`per_page` is pinned small and `max_pages` to one for the FIRST collection.
The point of the first request is evidence that the seam works, not coverage.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from nativeforge.services.source_adapter_contract_service import (
    MEDIA_JSON,
    PageCursor,
    SourceDescriptor,
    SourceRecord,
)

ADAPTER_KEY = "federal_register_documents_json"
ADAPTER_VERSION = "gate171_v1"

#: The first collection is deliberately one small page.
MAX_PAGES = 1
MAX_RECORDS = 20
PER_PAGE = 20

#: PROPOSED, not established by this repository. Named here so the approval
#: packet can carry an exact request rather than an intention.
PROPOSED_PATH = "/api/v1/documents.json"
PROPOSED_FIELDS = (
    "document_number",
    "title",
    "type",
    "publication_date",
    "agencies",
    "html_url",
    "comments_close_on",
)

RETRY_POLICY = {
    "max_attempts": 1,
    "retry_on": [],
    "backoff": "none",
    "why": "the_first_collection_records_what_happened_rather_than_retrying_it",
}
RATE_LIMIT_POLICY = {
    "requests_per_run": MAX_PAGES,
    "minimum_seconds_between_runs": 3600,
    "honors_retry_after": True,
    "on_429": "abandon_run_and_record_the_status",
}


def build_descriptor(
    *,
    source_id: str = "nf-seed-2026-api-federal-register-documents",
    source_url: str = "https://www.federalregister.gov" + PROPOSED_PATH,
) -> SourceDescriptor:
    """`source_id` and `source_url` are the uniform binding every adapter takes.

    The caller passes the registry's id and URL so a descriptor cannot drift
    from the row it is supposed to describe.
    """
    return SourceDescriptor(
        source_id=source_id,
        adapter_key=ADAPTER_KEY,
        display_name="Federal Register documents",
        publisher="Office of the Federal Register, National Archives",
        base_url=source_url,
        transport_method="GET",
        auth_mode="none",
        pagination_model="page_number",
        expected_media_types=(MEDIA_JSON,),
        max_pages=MAX_PAGES,
        max_records=MAX_RECORDS,
        max_crawl_depth=0,
        attribution_required=True,
        attribution_text=(
            "Source: Office of the Federal Register, National Archives and "
            "Records Administration"
        ),
        request_shape={
            "method": "GET",
            "path": PROPOSED_PATH,
            "query": {
                "per_page": PER_PAGE,
                "page": 1,
                "order": "newest",
                "conditions[type][]": "NOTICE",
                "fields[]": list(PROPOSED_FIELDS),
            },
            "body": None,
            "status": "PROPOSED_NOT_VERIFIED_BY_THIS_REPOSITORY",
        },
    )


def _query(page: int) -> str:
    parts = [
        f"per_page={PER_PAGE}",
        f"page={int(page)}",
        "order=newest",
        "conditions%5Btype%5D%5B%5D=NOTICE",
    ]
    parts.extend(f"fields%5B%5D={name}" for name in PROPOSED_FIELDS)
    return "&".join(parts)


def build_request(
    *,
    descriptor: SourceDescriptor,
    authorization: Any,
    cursor: PageCursor | None = None,
) -> Any:
    """One GET for one page. Refuses without an authorization."""
    if authorization is None:
        raise PermissionError(
            "federal_register_documents_json_refuses_to_build_a_request"
            "_without_an_authorization"
        )
    page = 1 if cursor is None else int(cursor.page_index) + 1
    if page > MAX_PAGES:
        raise ValueError(f"federal_register_documents_json_page_bound:{page}")

    from nativeforge.services.source_collection_transport_service import (
        TransportRequest,
    )

    return TransportRequest(
        method="GET",
        url=f"{descriptor.base_url}?{_query(page)}",
        headers={"Accept": "application/json"},
    )


def read_records(
    *,
    descriptor: SourceDescriptor,
    body_bytes: bytes,
    media_type: str | None,
    cursor: PageCursor | None = None,
) -> list[SourceRecord]:
    """Read the documents array. Refuses anything that is not that shape."""
    if media_type is not None and media_type != MEDIA_JSON:
        raise ValueError(
            f"federal_register_documents_json_expects_json_not:{media_type}"
        )

    payload = bytes(body_bytes or b"")
    if not payload.strip():
        return []

    document = json.loads(payload.decode("utf-8", errors="replace"))
    if not isinstance(document, dict):
        raise ValueError("federal_register_documents_json_expected_an_object")
    results = document.get("results")
    if not isinstance(results, list):
        raise ValueError("federal_register_documents_json_expected_a_results_array")

    evidence = hashlib.sha256(payload).hexdigest()
    page_index = 0 if cursor is None else cursor.page_index
    records: list[SourceRecord] = []

    for entry in results[:MAX_RECORDS]:
        if not isinstance(entry, dict):
            continue
        number = str(entry.get("document_number") or "").strip()
        if not number:
            # A record with no publisher identifier has no identity this
            # adapter is entitled to invent.
            continue
        agencies = entry.get("agencies")
        agency_name = None
        if isinstance(agencies, list) and agencies:
            first = agencies[0]
            if isinstance(first, dict):
                agency_name = first.get("name") or first.get("raw_name")
            elif isinstance(first, str):
                agency_name = first

        fields: dict[str, Any] = {
            "source_record_id": number,
            "opportunity_number": number,
            "title": entry.get("title"),
            "doc_type": entry.get("type"),
            "open_date": entry.get("publication_date"),
            "close_date": entry.get("comments_close_on"),
            # The canonical spelling. `funder_agency` is not in the
            # vocabulary and the normalizer refuses an invented field.
            "funder_agency_name": agency_name,
            "source_url": entry.get("html_url"),
        }
        supported = tuple(
            name for name, value in fields.items() if value not in (None, "")
        )
        records.append(
            SourceRecord(
                source_record_id=number,
                fields={k: v for k, v in fields.items() if k in supported},
                supported_fields=supported,
                evidence_sha256=evidence,
                documents=(),
                page_index=page_index,
            )
        )
    return records


def source_says_more(*, body_bytes: bytes) -> bool:
    """Whether the envelope claims another page. Believed only with the cursor.

    The cursor still owns termination - this reports what the source SAID,
    and `PageCursor.should_continue` decides whether that matters.
    """
    try:
        document = json.loads(bytes(body_bytes or b"").decode("utf-8", "replace"))
    except Exception:  # noqa: BLE001
        return False
    if not isinstance(document, dict):
        return False
    return bool(document.get("next_page_url"))
