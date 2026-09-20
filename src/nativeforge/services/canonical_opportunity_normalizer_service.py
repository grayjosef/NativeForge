"""Bytes to a normalized opportunity, per adapter (Gate 167C).

The canonical field vocabulary is fixed. What each SOURCE can supply is not,
and the difference is the whole point of this module: a source that publishes
no funding range must leave the funding fields absent, not zero, not empty
string, and not a guess derived from something adjacent.

```text
SUPPORTED + present in the payload   -> a value, with the evidence behind it
SUPPORTED + absent from the payload  -> absent, and named in fields_absent
NOT SUPPORTED by this source         -> named in fields_not_supported
```

Three outcomes, never two. Collapsing "this source cannot tell you" into "this
source says no" is how a Tribe ends up reading a funding ceiling that nobody
published.

## Keyed by adapter, like every other source-specific thing

`OPPORTUNITY_PARSERS` is keyed by `adapter_key` from the source's own catalog
row - the pattern Gate 166 established for capabilities and attribution. The
generic write path never names a publisher; it looks up the parser belonging to
the source in front of it.

## Parser version is part of the evidence

A normalized value is a claim made by a specific parser about specific bytes.
When the parser changes, the claim can change without the bytes changing, so
`PARSER_VERSION` is recorded on every observation and every version. Without it
"the data changed" and "we started reading it differently" are the same event.

Nothing here writes, and nothing here fetches.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_canonical_opportunity_normalizer_v1"

#: Bumped when a parser's OUTPUT for unchanged bytes would change. Recorded on
#: every observation, so a field that moved can be attributed to the parser
#: rather than to the source.
PARSER_VERSION = "1"

#: The canonical field vocabulary. A field outside this set cannot be written
#: to the graph, which is what stops a source inventing its own columns.
CANONICAL_FIELDS: tuple[str, ...] = (
    "title",
    "funder_agency_name",
    "funder_agency_code",
    "opportunity_number",
    "source_record_id",
    "open_date",
    "close_date",
    "status",
    "doc_type",
    "assistance_listings",
    "eligibility_text",
    "funding_amount_min",
    "funding_amount_max",
    "source_url",
)

#: Fields Gate 167C names as the minimum a canonical opportunity should be able
#: to carry. Listed so "this source supplies none of them" is visible.
PROVENANCE_REQUIRED_FIELDS: tuple[str, ...] = (
    "title",
    "funder_agency_name",
    "opportunity_number",
    "open_date",
    "close_date",
    "status",
)

#: adapter_key -> what that source's records can supply.
#:
#: `supported` is a claim about the SOURCE, verified against the payload at
#: parse time. Declaring support for a field the payload never carries makes
#: that field permanently absent, which is visible in `fields_absent` rather
#: than silently fine.
OPPORTUNITY_PARSERS: dict[str, dict[str, Any]] = {
    "grants_gov_search2": {
        "parser_name": "grants_gov_search2_opp_hit",
        "record_path": ("data", "oppHits"),
        "record_id_field": "id",
        "supported": (
            "title",
            "funder_agency_name",
            "funder_agency_code",
            "opportunity_number",
            "source_record_id",
            "open_date",
            "close_date",
            "status",
            "doc_type",
            "assistance_listings",
        ),
        # Measured, not assumed: the Gate 163 payload's oppHit carries ten
        # fields and none of these is among them. A search RESULT is not a
        # detail record; these arrive from fetchOpportunity, which Gate 163
        # was explicitly forbidden to call.
        "not_supported": (
            "eligibility_text",
            "funding_amount_min",
            "funding_amount_max",
            "source_url",
        ),
        "field_map": {
            "title": "title",
            "funder_agency_name": "agency",
            "funder_agency_code": "agencyCode",
            "opportunity_number": "number",
            "source_record_id": "id",
            "open_date": "openDate",
            "close_date": "closeDate",
            "status": "oppStatus",
            "doc_type": "docType",
            "assistance_listings": "cfdaList",
        },
    },
}

#: Source status strings mapped onto the canonical lifecycle. Anything not
#: named here is `unknown` - a source that says something we have not modelled
#: has not said `posted`.
STATUS_TO_LIFECYCLE: dict[str, str] = {
    "posted": "posted",
    "forecasted": "forecasted",
    "forecast": "forecasted",
    "closed": "closed",
    "archived": "archived",
    "awarded": "awarded",
}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def parser_for_adapter(adapter_key: Any) -> dict[str, Any] | None:
    key = str(adapter_key or "").strip()
    return dict(OPPORTUNITY_PARSERS[key]) if key in OPPORTUNITY_PARSERS else None


def lifecycle_for_status(status: Any) -> str:
    return STATUS_TO_LIFECYCLE.get(str(status or "").strip().lower(), "unknown")


def content_fingerprint(fields: dict[str, Any]) -> str:
    """A stable digest of the normalized field set.

    Same bytes parsed by the same parser produce the same fingerprint, which is
    what makes an exact replay idempotent at the schema level rather than by
    comparing fields in application code.
    """
    canonical = json.dumps(
        {k: fields[k] for k in sorted(fields)}, sort_keys=True, default=str
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def extract_records(
    *, payload: Any = None, adapter_key: Any = None
) -> list[dict[str, Any]]:
    """The opportunity records inside one payload. Returns [] if unparseable."""
    parser = parser_for_adapter(adapter_key)
    if parser is None or not isinstance(payload, dict):
        return []

    node: Any = payload
    for step in parser["record_path"]:
        if not isinstance(node, dict):
            return []
        node = node.get(step)
    return [record for record in (node or []) if isinstance(record, dict)]


def normalize_record(
    *, record: dict[str, Any] | None = None, adapter_key: Any = None
) -> dict[str, Any]:
    """One source record -> canonical fields, plus what is missing and why.

    Never raises. An unparseable record produces a result that says so, because
    a normalizer that throws turns one bad row into a failed collection.
    """
    parser = parser_for_adapter(adapter_key)
    if parser is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "parser_version": PARSER_VERSION,
                "adapter_key": str(adapter_key or "") or None,
                "parseable": False,
                "reason": "no_parser_declared_for_this_adapter",
                "fields": {},
                "fields_absent": list(CANONICAL_FIELDS),
                "fields_not_supported": [],
            }
        )

    raw = record or {}
    supported = tuple(parser["supported"])
    field_map = dict(parser["field_map"])

    fields: dict[str, Any] = {}
    absent: list[str] = []
    for name in supported:
        source_key = field_map.get(name)
        value = raw.get(source_key) if source_key else None
        # Empty string is absence, not a value. An agency that publishes ""
        # for a close date has not published a close date.
        if value is None or (isinstance(value, str) and not value.strip()):
            absent.append(name)
            continue
        if isinstance(value, list):
            cleaned = [str(item).strip() for item in value if str(item).strip()]
            if not cleaned:
                absent.append(name)
                continue
            fields[name] = cleaned
        else:
            fields[name] = str(value).strip()

    not_supported = [
        name for name in CANONICAL_FIELDS if name not in supported
    ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "parser_version": PARSER_VERSION,
            "parser_name": parser["parser_name"],
            "adapter_key": str(adapter_key or "") or None,
            "parseable": bool(fields),
            "fields": fields,
            "fields_absent": sorted(absent),
            "fields_not_supported": sorted(not_supported),
            "content_fingerprint": content_fingerprint(fields),
            "source_record_id": fields.get("source_record_id"),
            "lifecycle_state": lifecycle_for_status(fields.get("status")),
            # Reported so a caller can see the gap without recomputing it.
            "provenance_fields_present": sorted(
                name for name in PROVENANCE_REQUIRED_FIELDS if name in fields
            ),
            "provenance_fields_missing": sorted(
                name for name in PROVENANCE_REQUIRED_FIELDS if name not in fields
            ),
        }
    )


def normalizer_invariant_failures(normalized: dict[str, Any]) -> list[str]:
    """Refuse a normalization that invented something."""
    fails: list[str] = []

    fields = normalized.get("fields") or {}
    unknown = sorted(set(fields) - set(CANONICAL_FIELDS))
    if unknown:
        fails.append(f"field_outside_the_canonical_vocabulary:{unknown}")

    # A field cannot be both present and absent, or both present and
    # unsupported. Either would let a reader draw opposite conclusions.
    absent = set(normalized.get("fields_absent") or [])
    unsupported = set(normalized.get("fields_not_supported") or [])
    both = sorted((absent | unsupported) & set(fields))
    if both:
        fails.append(f"field_reported_present_and_missing:{both}")

    overlap = sorted(absent & unsupported)
    if overlap:
        fails.append(f"field_both_absent_and_unsupported:{overlap}")

    if normalized.get("parseable") and not fields:
        fails.append("parseable_without_any_field")

    if fields and normalized.get("content_fingerprint") != content_fingerprint(
        fields
    ):
        fails.append("content_fingerprint_does_not_match_the_fields")

    if not normalized.get("parser_version"):
        fails.append("no_parser_version_recorded")

    return sorted(set(fails))
