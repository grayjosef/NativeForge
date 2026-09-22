"""Gate 171C: the generic adapter boundary.

The campaign's first live source was wired end to end before this boundary
existed, which was the right order - a contract drawn before anything real had
been collected would have been a guess. Now that one source has been collected,
normalized, identified and diffed, the shape of the seam is known, and this
module writes it down BEFORE a second and third source arrive to bend it.

## What is generic and what is not

```text
generic      descriptor, transport envelope, evidence envelope, cursor,
             record, document reference, outcome, the refusals
adapter      how to build a request for ONE source family and how to read
             its bytes back into records
```

**This module names no source.** Not in a constant, not in a branch, not in a
docstring example, not in an attribution string. Gate 171Q proves that by
scanning the file rather than by trusting this paragraph - which is the only
kind of proof worth having, because a sentence claiming genericity is exactly
what a leaked source name hides behind.

## Nullable status is a fact, not a gap

`RawEvidenceEnvelope.http_status` is `int | None` and None means **the status
was not captured**. It is never backfilled to 200, never inferred from an
empty error field, and never filled in by a second request issued to improve
the evidence. The campaign already holds one real payload whose status is NULL
for exactly this reason.

## Adapters do not write

An adapter returns records. The canonical graph is downstream and stays
downstream: identity, versioning, provenance and change events are decisions
the graph makes about what an adapter reported, not decisions an adapter is
allowed to make about the graph. `adapter_contract_failures` refuses an
adapter module that imports a repository.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any

SCHEMA_VERSION = "nf_source_adapter_contract_v1"

# ---- vocabularies -------------------------------------------------

TRANSPORT_METHODS = ("GET", "POST")

#: How a source is reached. `none` is not "unknown" - it is the positive fact
#: that no credential is involved, which is what makes a source cheap to
#: authorize and is worth distinguishing from "nobody has checked".
AUTH_MODES = ("none", "api_key", "oauth", "unknown")

#: How a source hands over the next page. `single_document` is a first-class
#: model, not a degenerate case: a document source that returns one page and
#: is finished must be able to say so without a cursor pretending to exist.
PAGINATION_MODELS = (
    "single_document",
    "page_number",
    "offset_limit",
    "continuation_token",
    "link_header",
    "unknown",
)

#: Why a collection stopped. Every one of these is a deliberate stop; a
#: collection that ran out of pages by accident is not representable.
TERMINATION_REASONS = (
    "source_reported_last_page",
    "max_pages_reached",
    "max_records_reached",
    "repeated_page_detected",
    "empty_page",
    "transport_failed",
    "refused_before_request",
)

#: What an adapter may say about a document it found without fetching it.
DOCUMENT_RELATIONSHIPS = (
    "primary",
    "attachment",
    "amendment",
    "related",
    "unknown",
)

MEDIA_HTML = "text/html"
MEDIA_JSON = "application/json"
MEDIA_XML = "application/xml"
MEDIA_PDF = "application/pdf"
SUPPORTED_MEDIA_TYPES = (MEDIA_HTML, MEDIA_JSON, MEDIA_XML, MEDIA_PDF)


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def _digest(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


# ---- descriptor ---------------------------------------------------


@dataclass(frozen=True)
class SourceDescriptor:
    """Everything the generic layer needs to know about a source.

    Deliberately a DATA object. Gate 166 removed code-level source authority
    and this is the other half of that bargain: if the generic layer can act
    on a source purely from a descriptor plus an authorization decision, then
    activating a source is a data change, and the thousandth source costs the
    same as the second.
    """

    source_id: str
    adapter_key: str
    display_name: str
    publisher: str
    base_url: str
    transport_method: str = "GET"
    auth_mode: str = "unknown"
    pagination_model: str = "unknown"
    expected_media_types: tuple[str, ...] = (MEDIA_HTML,)
    max_pages: int = 1
    max_records: int = 100
    max_crawl_depth: int = 0
    attribution_required: bool = False
    attribution_text: str | None = None
    request_shape: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> dict[str, Any]:
        return _json_safe(
            {
                "source_id": self.source_id,
                "adapter_key": self.adapter_key,
                "display_name": self.display_name,
                "publisher": self.publisher,
                "transport_method": self.transport_method,
                "auth_mode": self.auth_mode,
                "pagination_model": self.pagination_model,
                "expected_media_types": list(self.expected_media_types),
                "max_pages": self.max_pages,
                "max_records": self.max_records,
                "max_crawl_depth": self.max_crawl_depth,
                "attribution_required": self.attribution_required,
            }
        )


def descriptor_failures(descriptor: SourceDescriptor) -> list[str]:
    """Refuse a descriptor that cannot produce a bounded collection."""
    failures: list[str] = []
    if not str(descriptor.source_id).strip():
        failures.append("descriptor_without_a_source_id")
    if not str(descriptor.adapter_key).strip():
        failures.append("descriptor_without_an_adapter_key")
    if not str(descriptor.base_url).startswith("http"):
        failures.append("descriptor_without_an_http_base_url")
    if descriptor.transport_method not in TRANSPORT_METHODS:
        failures.append(f"unsupported_transport_method:{descriptor.transport_method}")
    if descriptor.auth_mode not in AUTH_MODES:
        failures.append(f"unknown_auth_mode:{descriptor.auth_mode}")
    if descriptor.pagination_model not in PAGINATION_MODELS:
        failures.append(f"unknown_pagination_model:{descriptor.pagination_model}")
    for media in descriptor.expected_media_types:
        if media not in SUPPORTED_MEDIA_TYPES:
            failures.append(f"unsupported_media_type:{media}")
    # An unbounded collection is the failure mode that turns one adapter into
    # a crawler, so the bounds are refused at the descriptor rather than
    # trusted to the loop.
    if int(descriptor.max_pages) < 1:
        failures.append("max_pages_below_one")
    if int(descriptor.max_records) < 1:
        failures.append("max_records_below_one")
    if int(descriptor.max_crawl_depth) < 0:
        failures.append("negative_crawl_depth")
    if (
        descriptor.pagination_model == "single_document"
        and int(descriptor.max_pages) != 1
    ):
        failures.append("single_document_source_declaring_more_than_one_page")
    if descriptor.attribution_required and not (descriptor.attribution_text or ""):
        failures.append("attribution_required_without_attribution_text")
    return sorted(set(failures))


# ---- evidence -----------------------------------------------------


@dataclass(frozen=True)
class RawEvidenceEnvelope:
    """The bytes as they arrived, and what is known about how they arrived.

    `http_status` is nullable on purpose. See the module docstring: an absent
    status is recorded as absent.
    """

    source_id: str
    adapter_key: str
    request_method: str
    request_url_fingerprint: str
    retrieved_at: str
    media_type: str | None
    byte_count: int
    content_sha256: str
    http_status: int | None = None
    page_index: int = 0
    body_ref: str | None = None

    @staticmethod
    def for_body(
        *,
        source_id: str,
        adapter_key: str,
        request_method: str,
        request_url_fingerprint: str,
        retrieved_at: str,
        body_bytes: bytes,
        media_type: str | None = None,
        http_status: int | None = None,
        page_index: int = 0,
        body_ref: str | None = None,
    ) -> RawEvidenceEnvelope:
        payload = bytes(body_bytes or b"")
        return RawEvidenceEnvelope(
            source_id=source_id,
            adapter_key=adapter_key,
            request_method=request_method,
            request_url_fingerprint=request_url_fingerprint,
            retrieved_at=retrieved_at,
            media_type=media_type,
            byte_count=len(payload),
            content_sha256=_digest(payload),
            http_status=http_status,
            page_index=page_index,
            body_ref=body_ref,
        )


def evidence_failures(envelope: RawEvidenceEnvelope) -> list[str]:
    failures: list[str] = []
    if len(str(envelope.content_sha256)) != 64:
        failures.append("evidence_without_a_sha256")
    if int(envelope.byte_count) < 0:
        failures.append("negative_byte_count")
    if not str(envelope.retrieved_at).strip():
        failures.append("evidence_without_a_retrieval_time")
    if not str(envelope.request_url_fingerprint).strip():
        failures.append("evidence_without_a_request_fingerprint")
    # A URL in the fingerprint field defeats the point of fingerprinting it.
    if str(envelope.request_url_fingerprint).startswith("http"):
        failures.append("request_url_stored_instead_of_its_fingerprint")
    if envelope.http_status is not None and not (
        100 <= int(envelope.http_status) <= 599
    ):
        failures.append(f"impossible_http_status:{envelope.http_status}")
    return sorted(set(failures))


# ---- pagination ---------------------------------------------------


@dataclass
class PageCursor:
    """Where a paginated collection has got to, and why it may not continue.

    The cursor owns termination. An adapter cannot decide to keep going: it
    asks `should_continue` and is told. That is the difference between a
    bounded collector and a crawler, and it is enforced here rather than in
    each adapter, because the adapter is the thing most likely to be written
    in a hurry.
    """

    max_pages: int
    max_records: int
    page_index: int = 0
    records_seen: int = 0
    continuation_token: str | None = None
    seen_page_fingerprints: set[str] = field(default_factory=set)
    terminated_because: str | None = None

    def observe_page(self, *, content_sha256: str, record_count: int) -> None:
        self.page_index += 1
        self.records_seen += int(record_count)
        if content_sha256 in self.seen_page_fingerprints:
            # The same bytes twice means the source is looping us, whatever
            # its continuation token claims. Believing the token here is how
            # a collector spins until a rate limit stops it.
            self.terminated_because = "repeated_page_detected"
            return
        self.seen_page_fingerprints.add(content_sha256)
        if record_count == 0:
            self.terminated_because = "empty_page"

    def should_continue(self, *, source_says_more: bool) -> bool:
        if self.terminated_because is not None:
            return False
        if not source_says_more:
            self.terminated_because = "source_reported_last_page"
            return False
        if self.page_index >= int(self.max_pages):
            self.terminated_because = "max_pages_reached"
            return False
        if self.records_seen >= int(self.max_records):
            self.terminated_because = "max_records_reached"
            return False
        return True

    def describe(self) -> dict[str, Any]:
        return _json_safe(
            {
                "page_index": self.page_index,
                "records_seen": self.records_seen,
                "distinct_pages": len(self.seen_page_fingerprints),
                "terminated_because": self.terminated_because,
                "has_continuation_token": self.continuation_token is not None,
            }
        )


def cursor_failures(cursor: PageCursor) -> list[str]:
    failures: list[str] = []
    if cursor.page_index > int(cursor.max_pages):
        failures.append("cursor_ran_past_its_page_bound")
    if cursor.records_seen > int(cursor.max_records) + int(cursor.max_records):
        failures.append("cursor_ran_far_past_its_record_bound")
    if cursor.terminated_because is not None and (
        cursor.terminated_because not in TERMINATION_REASONS
    ):
        failures.append(f"unknown_termination_reason:{cursor.terminated_because}")
    if cursor.page_index > 0 and cursor.terminated_because is None:
        # Not a failure in itself; it is a failure to have FINISHED without
        # one, which the outcome check below catches.
        pass
    return sorted(set(failures))


# ---- documents ----------------------------------------------------

_TRACKING_PARAMS = ("utm_source", "utm_medium", "utm_campaign", "utm_term", "fbclid")


def canonical_url(raw: str) -> str:
    """One URL spelling per document, so duplicates can be detected at all.

    Deliberately conservative: it lowercases the host, drops a default port,
    a fragment and known tracking parameters, and strips a trailing slash on
    a non-root path. It does NOT reorder or drop unknown query parameters,
    because on a lot of government sites a query parameter IS the document.
    """
    text = str(raw or "").strip()
    if not text:
        return ""
    match = re.match(r"^(https?)://([^/?#]+)([^?#]*)(\?[^#]*)?(#.*)?$", text, re.I)
    if not match:
        return text
    scheme = match.group(1).lower()
    host = match.group(2).lower()
    path = match.group(3) or "/"
    query = match.group(4) or ""
    if scheme == "http" and host.endswith(":80"):
        host = host[:-3]
    if scheme == "https" and host.endswith(":443"):
        host = host[:-4]
    if len(path) > 1 and path.endswith("/"):
        path = path[:-1]
    if query:
        kept = [
            part
            for part in query[1:].split("&")
            if part and part.split("=")[0].lower() not in _TRACKING_PARAMS
        ]
        query = ("?" + "&".join(kept)) if kept else ""
    return f"{scheme}://{host}{path}{query}"


@dataclass(frozen=True)
class DocumentReference:
    """A document an adapter SAW. Seeing is not fetching.

    Depth is carried so a crawl boundary is checkable after the fact rather
    than only promised beforehand.
    """

    url: str
    relationship: str = "unknown"
    media_type: str | None = None
    title: str | None = None
    content_sha256: str | None = None
    depth: int = 0
    fetched: bool = False

    @property
    def canonical(self) -> str:
        return canonical_url(self.url)


def document_failures(
    documents: list[DocumentReference], *, max_depth: int
) -> list[str]:
    failures: list[str] = []
    for document in documents:
        if document.relationship not in DOCUMENT_RELATIONSHIPS:
            failures.append(f"unknown_document_relationship:{document.relationship}")
        if int(document.depth) > int(max_depth):
            failures.append(
                f"document_beyond_the_crawl_depth_bound:{document.depth}"
            )
        if document.fetched and int(document.depth) > 0:
            # Extracting a link is not permission to follow it.
            failures.append("adapter_followed_a_link_beyond_depth_zero")
        if document.media_type and document.media_type not in SUPPORTED_MEDIA_TYPES:
            failures.append(f"unsupported_document_media_type:{document.media_type}")
    return sorted(set(failures))


def deduplicate_documents(
    documents: list[DocumentReference],
) -> tuple[list[DocumentReference], int]:
    """Collapse by canonical URL first, then by content hash where known."""
    kept: list[DocumentReference] = []
    seen_urls: set[str] = set()
    seen_hashes: set[str] = set()
    suppressed = 0
    for document in documents:
        key = document.canonical
        digest = document.content_sha256
        if key in seen_urls or (digest and digest in seen_hashes):
            suppressed += 1
            continue
        seen_urls.add(key)
        if digest:
            seen_hashes.add(digest)
        kept.append(document)
    return kept, suppressed


# ---- records and outcome ------------------------------------------


@dataclass(frozen=True)
class SourceRecord:
    """One opportunity-shaped thing an adapter read out of the bytes.

    `fields` is deliberately loose and `supported_fields` is deliberately
    explicit: the graph needs to know which fields this source actually
    speaks for, because a field a source does not publish must not be
    mistaken for a field it published as empty. That distinction is what
    keeps a missing value from being recorded as a conflict.
    """

    source_record_id: str
    fields: dict[str, Any]
    supported_fields: tuple[str, ...]
    evidence_sha256: str
    documents: tuple[DocumentReference, ...] = ()
    page_index: int = 0
    #: Things the adapter measured that are NOT canonical opportunity fields -
    #: how many links it saw, how many duplicates it suppressed, what the text
    #: extractor warned about. They belong in the record because they describe
    #: this read, and they are kept OUT of `fields` because the canonical
    #: vocabulary is closed and a normalizer that accepted them would be
    #: accepting anything.
    metrics: dict[str, Any] = field(default_factory=dict)


def record_failures(record: SourceRecord) -> list[str]:
    failures: list[str] = []
    if not str(record.source_record_id).strip():
        failures.append("record_without_a_source_record_id")
    if len(str(record.evidence_sha256)) != 64:
        failures.append("record_not_bound_to_evidence")
    if not record.supported_fields:
        failures.append("record_claiming_no_supported_fields")
    for name in record.fields:
        if name not in record.supported_fields:
            failures.append(f"field_outside_the_supported_set:{name}")
    return sorted(set(failures))


@dataclass(frozen=True)
class CollectionOutcome:
    """What one bounded collection did. Includes what it refused to do."""

    source_id: str
    adapter_key: str
    records: tuple[SourceRecord, ...]
    evidence: tuple[RawEvidenceEnvelope, ...]
    requests_issued: int
    pages_fetched: int
    terminated_because: str
    refusals: tuple[str, ...] = ()
    cursor_state: dict[str, Any] = field(default_factory=dict)

    def describe(self) -> dict[str, Any]:
        return _json_safe(
            {
                "source_id": self.source_id,
                "adapter_key": self.adapter_key,
                "records": len(self.records),
                "evidence_envelopes": len(self.evidence),
                "requests_issued": self.requests_issued,
                "pages_fetched": self.pages_fetched,
                "terminated_because": self.terminated_because,
                "refusals": list(self.refusals),
                "cursor": self.cursor_state,
            }
        )


def outcome_failures(
    outcome: CollectionOutcome, descriptor: SourceDescriptor
) -> list[str]:
    """The checks that make a collection auditable after the fact."""
    failures: list[str] = []
    if outcome.terminated_because not in TERMINATION_REASONS:
        failures.append(f"unknown_termination_reason:{outcome.terminated_because}")
    if outcome.requests_issued > int(descriptor.max_pages):
        failures.append(
            f"more_requests_than_pages_allowed:{outcome.requests_issued}"
        )
    if outcome.pages_fetched > int(descriptor.max_pages):
        failures.append(f"more_pages_than_allowed:{outcome.pages_fetched}")
    if len(outcome.records) > int(descriptor.max_records):
        failures.append(f"more_records_than_allowed:{len(outcome.records)}")
    if outcome.source_id != descriptor.source_id:
        failures.append("outcome_attributed_to_a_different_source")
    if outcome.adapter_key != descriptor.adapter_key:
        failures.append("outcome_attributed_to_a_different_adapter")
    # Evidence has to exist for anything that was read. A record with no
    # envelope behind it is a record nobody can check.
    known = {envelope.content_sha256 for envelope in outcome.evidence}
    for record in outcome.records:
        if record.evidence_sha256 not in known:
            failures.append("record_cites_evidence_this_collection_does_not_hold")
    if outcome.requests_issued == 0 and outcome.records:
        failures.append("records_produced_without_a_request")
    return sorted(set(failures))


# ---- the adapter contract -----------------------------------------

#: What every adapter must expose. Checked structurally, so a new adapter
#: cannot be half-written and still register.
REQUIRED_ADAPTER_ATTRIBUTES = (
    "ADAPTER_KEY",
    "build_descriptor",
    "build_request",
    "read_records",
)

#: Module paths an adapter must not import. An adapter that can write to the
#: graph is an adapter that can bypass identity, provenance and change
#: intelligence, which are the things the graph exists to guarantee.
FORBIDDEN_ADAPTER_IMPORTS = (
    "nativeforge.repositories",
    "nativeforge.db",
)


def normalized_envelope_for(
    record: SourceRecord, *, adapter_key: str
) -> dict[str, Any]:
    """A SourceRecord as the canonical write path's normalized envelope.

    The canonical store takes an envelope shaped by
    `canonical_opportunity_normalizer_service.normalize_record`, which parses
    a RAW source payload through an adapter-keyed parser table. An adapter has
    already done that parsing - it read the bytes and produced typed records -
    so running a second parser over the same payload would be two parsers for
    one source, disagreeing eventually.

    This converts instead. It invents nothing: a field the adapter did not
    supply is `fields_absent`, a canonical field the adapter does not speak
    for is `fields_not_supported`, and the difference between those two is the
    difference between "this source published nothing here" and "this source
    does not publish this at all" - which is what stops a missing value
    becoming a conflict.
    """
    from nativeforge.services.canonical_opportunity_normalizer_service import (
        CANONICAL_FIELDS,
        PARSER_VERSION,
        PROVENANCE_REQUIRED_FIELDS,
        content_fingerprint,
        lifecycle_for_status,
    )

    fields = {
        name: value
        for name, value in record.fields.items()
        if name in CANONICAL_FIELDS and value is not None
    }
    supported = tuple(n for n in record.supported_fields if n in CANONICAL_FIELDS)
    absent = sorted(n for n in supported if n not in fields)
    not_supported = sorted(n for n in CANONICAL_FIELDS if n not in supported)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "parser_version": PARSER_VERSION,
            "parser_name": f"{adapter_key}_adapter_records",
            "adapter_key": str(adapter_key),
            "parseable": bool(fields),
            "fields": fields,
            "fields_absent": absent,
            "fields_not_supported": not_supported,
            "content_fingerprint": content_fingerprint(fields),
            "source_record_id": fields.get("source_record_id"),
            "lifecycle_state": lifecycle_for_status(fields.get("status")),
            "provenance_fields_present": sorted(
                name for name in PROVENANCE_REQUIRED_FIELDS if name in fields
            ),
            "provenance_fields_missing": sorted(
                name for name in PROVENANCE_REQUIRED_FIELDS if name not in fields
            ),
            # Carried alongside, never inside `fields`.
            "adapter_metrics": dict(record.metrics or {}),
            "documents_seen": len(record.documents),
        }
    )


def identity_for_normalized(
    normalized: dict[str, Any], *, source_id: str
) -> dict[str, Any]:
    """Pick the identity LAYER from what the record actually carries.

    `build_opportunity_identity` is the L1 builder, not a layer chooser - it
    returns L1 unconditionally. Handed a record with no published opportunity
    number it produces an L1 identity whose composite key is the empty string,
    and the canonical write path refuses it by name:
    `l1_identity_without_a_normalized_number`. That refusal is correct, and it
    is how this gate learned that a program PAGE is not a numbered notice.

    So the rule is explicit here:

    ```text
    a published opportunity number    L1, settleable
    no published number               L4, provisional, must never settle silently
    ```

    Generic. It reads the canonical fields, not the source. A document source
    that starts publishing numbers gets promoted the day it does, without an
    edit here.
    """
    from nativeforge.services.opportunity_identity_versioning_service import (
        build_fuzzy_fallback_key,
        build_opportunity_identity,
    )

    fields = dict(normalized.get("fields") or {})
    number = str(fields.get("opportunity_number") or "").strip()

    if number:
        return build_opportunity_identity(
            opportunity_number=number,
            doc_type=fields.get("doc_type"),
            opportunity_id=fields.get("source_record_id"),
            aln_list=fields.get("assistance_listings"),
            agency_code=fields.get("funder_agency_code"),
        )

    return build_fuzzy_fallback_key(
        agency=fields.get("funder_agency_name"),
        title=fields.get("title"),
        earliest_deadline_date=fields.get("close_date"),
        source_id=source_id,
    )


def adapter_contract_failures(module: Any) -> list[str]:
    """Structural conformance for one adapter module."""
    failures: list[str] = []
    for attribute in REQUIRED_ADAPTER_ATTRIBUTES:
        if not hasattr(module, attribute):
            failures.append(f"adapter_missing:{attribute}")
    key = getattr(module, "ADAPTER_KEY", "")
    if not str(key).strip():
        failures.append("adapter_without_a_key")
    source_file = getattr(module, "__file__", None)
    if source_file:
        try:
            text = open(source_file, encoding="utf-8").read()
        except OSError:
            text = ""
        for forbidden in FORBIDDEN_ADAPTER_IMPORTS:
            if f"import {forbidden}" in text or f"from {forbidden}" in text:
                failures.append(f"adapter_imports_a_writer:{forbidden}")
    return sorted(set(failures))
