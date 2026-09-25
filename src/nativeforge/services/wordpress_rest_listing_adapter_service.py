"""Collect funding announcements from any publisher running WordPress.

A surprising number of federal commissions, state agencies and foundations
publish their funding notices as WordPress posts and expose `/wp-json/wp/v2/`
without knowing it. That endpoint is a far better source than the rendered
page: stable integer ids, a `modified` timestamp, and pagination in response
headers rather than inferred from markup.

Nothing in this module is specific to one publisher. It takes a base URL and
a search term and returns normalized listing records. The Denali Commission is
the first instance; the second costs a configuration row.

## A 200 is not a healthy source

The failure that matters here is quiet: the endpoint answers, the shape has
changed, the parser finds nothing, and a naive collector reports "no
opportunities today" forever. So parse outcome is a FIELD, and four states
that look identical from the outside are kept apart:

    LEGITIMATE_ZERO   the publisher genuinely has nothing right now
    PARSE_FAILURE     records came back and none could be read
    STRUCTURE_DRIFT   required fields are missing from every record
    BLOCKED           the request was refused, which is not an empty result

## Geography is not identity

This module extracts EVIDENCE, never a relevance verdict. An Alaskan funder is
not automatically a Native funder, and a record whose only Native signal is
that it comes from Alaska carries no Native evidence at all. Gate 173 decides
relevance; the most this does is report which signals it actually saw.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

SCHEMA_VERSION = "nf_wordpress_rest_listing_adapter_v1"

POSTS_PATH = "/wp-json/wp/v2/posts"
DEFAULT_PER_PAGE = 50
DEFAULT_FIELDS = "id,date,modified,slug,link,title,excerpt,categories"

# ---- parse outcomes --------------------------------------------------
LEGITIMATE_ZERO = "LEGITIMATE_ZERO"
PARSE_FAILURE = "PARSE_FAILURE"
STRUCTURE_DRIFT = "STRUCTURE_DRIFT"
BLOCKED = "BLOCKED"
PARSED = "PARSED"

PARSE_OUTCOMES: tuple[str, ...] = (
    PARSED,
    LEGITIMATE_ZERO,
    PARSE_FAILURE,
    STRUCTURE_DRIFT,
    BLOCKED,
)

#: Outcomes in which the source is behaving correctly. STRUCTURE_DRIFT and
#: PARSE_FAILURE are explicitly not here: a source that answers and cannot be
#: read is broken, however cheerful its status code.
HEALTHY_OUTCOMES: frozenset[str] = frozenset({PARSED, LEGITIMATE_ZERO})

#: Fields a record must carry to be usable. Absence across every record is
#: drift, not emptiness.
REQUIRED_RECORD_FIELDS: tuple[str, ...] = ("id", "title", "link")

HttpGetJson = Callable[[str, dict[str, Any]], dict[str, Any]]

_TAG_RE = re.compile(r"<[^>]+>")
_WS_RE = re.compile(r"\s+")

#: Signals that a record concerns Native beneficiaries or applicants. These
#: are EVIDENCE TERMS, not a verdict, and geography is deliberately absent -
#: see `extract_native_relevance_evidence`.
_NATIVE_EVIDENCE_TERMS: tuple[str, ...] = (
    "tribal",
    "tribe",
    "native village",
    "alaska native",
    "american indian",
    "indian tribe",
    "native american",
    "native hawaiian",
    "village council",
)

#: Terms that locate a record without saying anything about who benefits.
_GEOGRAPHY_ONLY_TERMS: tuple[str, ...] = (
    "alaska",
    "rural",
    "remote",
    "statewide",
    "region",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _text(value: Any) -> str:
    """WordPress returns {'rendered': '<p>...'} for title and excerpt."""
    if isinstance(value, dict):
        value = value.get("rendered", "")
    return _WS_RE.sub(" ", _TAG_RE.sub(" ", str(value or ""))).strip()


def build_listing_request(
    *,
    base_url: str,
    search: str | None = None,
    per_page: int = DEFAULT_PER_PAGE,
    page: int = 1,
) -> dict[str, Any]:
    """The request, as data, so a collector can be replayed from evidence."""
    params: dict[str, Any] = {
        "per_page": int(per_page),
        "page": int(page),
        "_fields": DEFAULT_FIELDS,
    }
    if search:
        params["search"] = str(search)
    return _json_safe(
        {
            "url": f"{str(base_url).rstrip('/')}{POSTS_PATH}",
            "params": params,
            "method": "GET",
        }
    )


def parse_listing_response(
    *,
    records: Any,
    headers: dict[str, Any] | None = None,
    source_id: Any = None,
    retrieved_at: Any = None,
    raw_payload_sha256: Any = None,
) -> dict[str, Any]:
    """Normalize records and say honestly how the parse went."""
    head = {str(k).lower(): v for k, v in (headers or {}).items()}
    total = head.get("x-wp-total")
    total_pages = head.get("x-wp-totalpages")

    if not isinstance(records, list):
        return _outcome(
            PARSE_FAILURE,
            [],
            reason="response_was_not_a_list_of_records",
            total=total,
            total_pages=total_pages,
        )

    if not records:
        return _outcome(
            LEGITIMATE_ZERO,
            [],
            reason="publisher_returned_no_records",
            total=total,
            total_pages=total_pages,
        )

    listings: list[dict[str, Any]] = []
    unusable = 0
    for record in records:
        if not isinstance(record, dict):
            unusable += 1
            continue
        missing = [f for f in REQUIRED_RECORD_FIELDS if not record.get(f)]
        if missing:
            unusable += 1
            continue
        listings.append(
            {
                "publisher_record_id": str(record.get("id")),
                "slug": str(record.get("slug") or ""),
                "title": _text(record.get("title")),
                "excerpt": _text(record.get("excerpt")),
                "source_url": str(record.get("link") or ""),
                # The publisher's own change marker. Better than diffing a
                # rendered page, and the reason this endpoint beats the HTML.
                "published_at": str(record.get("date") or "") or None,
                "modified_at": str(record.get("modified") or "") or None,
                # Everything the publisher does not say stays unsaid.
                "deadline": None,
                "funding_amount": None,
                "eligibility_text": None,
                "status": None,
                "fields_absent": [
                    "deadline",
                    "funding_amount",
                    "eligibility_text",
                    "status",
                ],
                "source_id": str(source_id) if source_id else None,
                "retrieved_at": retrieved_at,
                "raw_payload_sha256": raw_payload_sha256,
            }
        )

    if not listings:
        # Records arrived and none was readable. That is drift, not zero.
        return _outcome(
            STRUCTURE_DRIFT,
            [],
            reason="records_present_but_none_carried_required_fields",
            total=total,
            total_pages=total_pages,
            unusable=unusable,
        )

    return _outcome(
        PARSED,
        listings,
        reason="records_parsed",
        total=total,
        total_pages=total_pages,
        unusable=unusable,
    )


def _outcome(
    outcome: str,
    listings: list[dict[str, Any]],
    *,
    reason: str,
    total: Any = None,
    total_pages: Any = None,
    unusable: int = 0,
) -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "parse_outcome": outcome,
            "parse_reason": reason,
            "listings": listings,
            "listing_count": len(listings),
            "unusable_record_count": unusable,
            "publisher_total": total,
            "publisher_total_pages": total_pages,
            "source_is_behaving": outcome in HEALTHY_OUTCOMES,
            "never_synthesized": True,
        }
    )


def blocked_response(*, reason: Any) -> dict[str, Any]:
    """A refusal is not an empty source, and must never read as one."""
    return _outcome(BLOCKED, [], reason=str(reason))


def extract_native_relevance_evidence(listing: dict[str, Any]) -> dict[str, Any]:
    """Which Native signals this record actually carries. Not a verdict.

    Geography is tracked separately and on purpose. An Alaskan infrastructure
    notice is not a Native funding notice, even though most of the villages it
    serves are Native, and a system that conflated the two would label an
    entire agency's output Native-specific on the strength of a state name.

    Gate 173 decides relevance from this evidence. This only reports it.
    """
    haystack = " ".join(
        str(listing.get(f) or "") for f in ("title", "excerpt", "eligibility_text")
    ).lower()

    native_terms = sorted({t for t in _NATIVE_EVIDENCE_TERMS if t in haystack})
    geography_terms = sorted({t for t in _GEOGRAPHY_ONLY_TERMS if t in haystack})

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "native_evidence_terms": native_terms,
            "has_native_evidence": bool(native_terms),
            "geography_terms": geography_terms,
            "has_geography_only_signal": bool(geography_terms) and not native_terms,
            # The refusal, said out loud on every record.
            "geography_alone_is_not_native_relevance": True,
            "relevance_decided": False,
            "relevance_is_decided_by_gate_173": True,
        }
    )


def listing_health(parse_result: dict[str, Any]) -> dict[str, Any]:
    """Source health from parse outcome, not from a status code."""
    outcome = str(parse_result.get("parse_outcome") or "")
    listings = int(parse_result.get("listing_count") or 0)
    failures: list[str] = []

    if outcome == PARSE_FAILURE:
        failures.append("response_shape_unreadable")
    if outcome == STRUCTURE_DRIFT:
        failures.append("required_fields_absent_from_every_record")
    if outcome == BLOCKED:
        failures.append("access_refused_not_empty")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "parse_outcome": outcome,
            "listing_count": listings,
            "healthy": outcome in HEALTHY_OUTCOMES,
            # The distinction the whole module exists to keep.
            "zero_is_legitimate": outcome == LEGITIMATE_ZERO,
            "zero_is_a_failure": outcome in (PARSE_FAILURE, STRUCTURE_DRIFT),
            "invariant_failures": sorted(set(failures)),
        }
    )
