"""Phase 1A: Denali Commission is dispatchable, unauthorized, and not Native.

Wave 1 verified this publisher live and corrected the research baseline twice:
it said HTML (denali.gov runs WordPress and exposes `/wp-json/wp/v2/`), and it
named the wrong pages (the funding notices are posts).

The invariant this file exists to protect is the one that is easiest to lose
by accident. Alaska is not Native. Record 4048 is a genuine Denali funding
opportunity that returns `native=[]`, `geo=['alaska','rural']`,
`has_geography_only_signal=true`; the tribal victim services notice returns
`native=['tribal']` because the publisher said so. A binding that stamped
Native relevance on everything from an Alaskan agency would be inventing it.
"""

from __future__ import annotations

import pytest

from nativeforge.services.canonical_opportunity_normalizer_service import (
    PROVENANCE_REQUIRED_FIELDS,
    extract_records,
    normalize_record,
    parser_for_adapter,
)
from nativeforge.services.denali_wp_binding_service import (
    ADAPTER_KEY,
    DENALI_POSTS_URL,
    SEED_ID,
    build_denali_listing_request,
    fetch_denali_listing,
    flatten_posts,
)
from nativeforge.services.source_collector_capability_service import (
    measure_collector_capability,
)
from nativeforge.services.source_monitoring_approved_source_service import (
    load_registry_rows,
)

ADAPTER_CHECKS = (
    "adapter_is_known",
    "adapter_module_resolves",
    "request_builds_for_source",
    "endpoint_matches_registry",
    "transport_is_injectable",
)

#: One real-shaped WordPress response, nested exactly as the publisher sends
#: it. Flattening is the binding's job and this is the input that proves it.
WP_PAGE = [
    {
        "id": 4048,
        "date": "2026-03-04T09:15:00",
        "modified": "2026-03-05T11:02:00",
        "slug": "fy2026-funding-opportunity",
        "link": "https://www.denali.gov/fy2026-funding-opportunity/",
        "title": {"rendered": "FY2026 Funding Opportunity"},
        "excerpt": {"rendered": "<p>Applications open.</p>"},
    },
    {
        "id": 3911,
        "date": "2026-01-20T08:00:00",
        "modified": "2026-01-20T08:00:00",
        "slug": "tribal-victim-services",
        "link": "https://www.denali.gov/tribal-victim-services/",
        "title": {"rendered": "FUNDING ASSISTANCE FOR TRIBAL VICTIM SERVICES"},
        "excerpt": {"rendered": "<p>For Tribal governments.</p>"},
    },
]


def _row() -> dict:
    return load_registry_rows()[SEED_ID]


# ------------------------------------------------------- capability


def test_denali_is_dispatchable():
    result = measure_collector_capability(
        connection=None, registry_row=_row(), source_id=SEED_ID
    )
    measured = result.get("measured") or {}
    failing = [name for name in ADAPTER_CHECKS if not measured.get(name)]
    assert failing == [], f"{failing}: {result.get('notes')}"


def test_denali_is_not_authorized():
    evidence = str(_row().get("health_evidence") or "")
    assert "operator_approved" not in evidence
    assert "awaiting_human_authorization" in evidence


def test_the_row_and_the_binding_name_the_same_endpoint():
    """`endpoint_matches_registry` is an equality, so a drift here silently
    makes the source uncollectable rather than loudly wrong."""
    assert _row()["source_url"] == DENALI_POSTS_URL


# ------------------------------------------------------- the wire shape


def test_wordpress_nesting_is_flattened_for_the_canonical_parser():
    """`field_map` reads flat keys. The {"rendered": ...} wrapper is this
    publisher's wire shape, not a canonical concept."""
    flat = flatten_posts(WP_PAGE)
    assert flat[0]["title"] == "FY2026 Funding Opportunity"
    assert flat[0]["id"] == 4048
    assert flat[0]["link"].endswith("/fy2026-funding-opportunity/")


def test_a_fetch_wraps_its_records_so_the_normalizer_can_walk_them():
    """`extract_records` walks a record path through a mapping, and a
    WordPress response is a bare array."""
    result = fetch_denali_listing(
        {"seed_id": SEED_ID, "source_url": DENALI_POSTS_URL},
        http_get=lambda url, params: WP_PAGE,
    )
    assert result["outcome"] == "hits"
    assert result["record_count"] == 2
    records = extract_records(payload=result, adapter_key=ADAPTER_KEY)
    assert len(records) == 2


def test_an_empty_listing_is_empty_and_not_an_error():
    result = fetch_denali_listing(
        {"seed_id": SEED_ID, "source_url": DENALI_POSTS_URL},
        http_get=lambda url, params: [],
    )
    assert result["outcome"] == "empty"
    assert result["record_count"] == 0


def test_a_transport_failure_is_not_an_empty_publisher():
    def broken(url, params):
        raise RuntimeError("tls handshake failed")

    result = fetch_denali_listing(
        {"seed_id": SEED_ID, "source_url": DENALI_POSTS_URL}, http_get=broken
    )
    assert result["outcome"] == "fetch_error"
    assert result["fetch_live"] is False
    assert "tls handshake failed" in result["api_error"]


def test_no_transport_is_refused_rather_than_defaulted():
    """A binding that quietly reached for a default transport would fetch
    outside the guard that is supposed to decide whether it may."""
    result = fetch_denali_listing({"seed_id": SEED_ID}, http_get=None)
    assert result["outcome"] == "fetch_error"
    assert result["api_error"] == "no_transport_supplied"


# ------------------------------------------------- honest field coverage


def test_the_parser_refuses_to_claim_fields_a_post_does_not_carry():
    """A WordPress post has no opportunity number, no close date, no
    eligibility prose and no amounts. Declaring support for a field the
    payload never carries makes it permanently absent instead of visibly
    unsupported."""
    parser = parser_for_adapter(ADAPTER_KEY)
    assert parser is not None
    for field in (
        "opportunity_number",
        "close_date",
        "eligibility_text",
        "funding_amount_min",
        "funding_amount_max",
    ):
        assert field in parser["not_supported"], field


def test_the_provenance_gap_is_visible_rather_than_silent():
    """Four of six provenance-required fields are missing for every record
    this source will ever produce. That is the publisher, not a bug - and it
    must show up in the normalized result."""
    flat = flatten_posts(WP_PAGE)
    normalized = normalize_record(record=flat[0], adapter_key=ADAPTER_KEY)
    assert normalized["parseable"] is True
    missing = set(normalized["provenance_fields_missing"])
    assert {"opportunity_number", "close_date", "status"} <= missing
    assert len(missing) < len(PROVENANCE_REQUIRED_FIELDS)


def test_a_publication_date_is_not_an_application_deadline():
    """`open_date` maps to the post date. WordPress has no deadline concept,
    and `close_date` must stay unsupported rather than borrow one."""
    flat = flatten_posts(WP_PAGE)
    normalized = normalize_record(record=flat[0], adapter_key=ADAPTER_KEY)
    assert normalized["fields"]["open_date"].startswith("2026-03-04")
    assert "close_date" in normalized["fields_not_supported"]


# ------------------------------------------------- Alaska is not Native


@pytest.mark.parametrize("index", [0, 1])
def test_the_binding_never_asserts_native_relevance(index: int):
    """Neither record gets a relevance verdict from this layer - including
    the one whose title does say Tribal. Relevance is decided downstream from
    evidence, and a geography-only signal is not evidence.
    """
    flat = flatten_posts(WP_PAGE)
    normalized = normalize_record(record=flat[index], adapter_key=ADAPTER_KEY)
    emitted = set(normalized["fields"])
    for invented in ("native", "native_relevance", "is_native", "tribal"):
        assert invented not in emitted
    assert "eligibility_text" in normalized["fields_not_supported"]


def test_the_binding_module_states_no_native_verdict_anywhere():
    """Guards the rule at the source, not just at one record.

    Record 4048 is a genuine Denali opportunity with `native=[]` and
    `geo=['alaska','rural']`. If this module ever starts emitting a verdict,
    the per-record test above would only catch the shapes it happens to
    check.
    """
    from pathlib import Path

    source = Path(
        "src/nativeforge/services/denali_wp_binding_service.py"
    ).read_text(encoding="utf-8")
    body = source.split('"""', 2)[-1]
    for verdict in ("native=True", 'native": True', "is_native = True"):
        assert verdict not in body, verdict
