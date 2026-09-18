"""Sprint 304 / NF-11: Grants.gov search2 + fetchOpportunity with honest labeling."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any, Literal

from nativeforge.services.grants_gov_eligibility_parser_service import (
    parse_grants_gov_opportunity_eligibility,
)
from nativeforge.services.real_fetch_honest_labeling_guard_service import (
    assert_real_fetch_honest_labeling,
)

SCHEMA_VERSION = "nf_grants_gov_search_api_adapter_v2"
SEARCH2_URL = "https://api.grants.gov/v1/api/search2"
FETCH_OPPORTUNITY_URL = "https://api.grants.gov/v1/api/fetchOpportunity"
DEFAULT_ROWS = 5
DEFAULT_STATUSES = "posted|forecasted"
FETCH_MODE_LIVE: Literal["live"] = "live"
FETCH_MODE_FIXTURE: Literal["fixture"] = "fixture"
FetchMode = Literal["live", "fixture"]

HttpPostJson = Callable[[str, dict[str, Any]], dict[str, Any]]

#: How a search ended. A FIELD, not something inferred from which keys happen
#: to be populated - inferring it is how "the guard refused" and "there were no
#: results" came to look identical.
OUTCOME_HITS = "hits"
OUTCOME_EMPTY = "empty"
OUTCOME_FETCH_ERROR = "fetch_error"


#: Authorization refusals are re-raised rather than returned. Resolved lazily
#: because the warrant and transport services read the registry, which reads
#: this module.
def _authorization_refusals() -> tuple[type[BaseException], ...]:
    """The exception types that mean "not permitted", never "no results"."""
    found: list[type[BaseException]] = []
    for module_name, attribute in (
        ("nativeforge.services.live_source_transport_service", "LiveTransportRefused"),
        ("nativeforge.services.source_live_warrant_service", "LiveRequestRefused"),
        ("nativeforge.services.hermetic_test_guard_service", "LiveNetworkRefused"),
    ):
        try:
            module = __import__(module_name, fromlist=[attribute])
            candidate = getattr(module, attribute, None)
            if isinstance(candidate, type) and issubclass(candidate, BaseException):
                found.append(candidate)
        except Exception:  # noqa: BLE001 - an absent type cannot be raised
            continue
    # Never empty: an empty tuple in `except` catches nothing, which would
    # silently restore the behaviour this removes.
    return tuple(found) or (_NeverRaised,)


class _NeverRaised(BaseException):
    """Placeholder so the except clause is never an empty tuple."""


_ALN_RE = re.compile(r"(\d{2}\.\d{3})")
_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "source_ingestion"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def default_grants_gov_http_post(url: str, body: dict[str, Any]) -> dict[str, Any]:
    # Single choke point for every live Grants.gov call in the codebase.
    # Gate 77B: live HTTP is opt-in. Tests must inject a recorded transport
    # instead — a suite whose result depends on a third party's search ranking
    # is not testing this product. See doc 429.
    from nativeforge.services.hermetic_test_guard_service import (
        assert_live_network_allowed,
    )

    assert_live_network_allowed(url=url, caller="default_grants_gov_http_post")

    import httpx

    with httpx.Client(timeout=20.0) as client:
        resp = client.post(url, json=body)
        resp.raise_for_status()
        return resp.json()


def extract_assistance_listing_number(source_name: str) -> str | None:
    match = _ALN_RE.search(source_name)
    return match.group(1) if match else None


def build_grants_gov_search_body(source: dict[str, Any]) -> dict[str, Any]:
    name = str(source.get("source_name") or "")
    url = str(source.get("source_url") or "")
    seed_id = str(source.get("seed_id") or "")
    from nativeforge.services.fed_program_activation_binding_service import (
        SEED_ALN_BINDINGS,
    )

    aln = SEED_ALN_BINDINGS.get(seed_id) or extract_assistance_listing_number(name)
    keyword = name
    if "—" in name:
        keyword = name.split("—", 1)[-1].strip()
    body: dict[str, Any] = {
        "rows": DEFAULT_ROWS,
        "oppStatuses": DEFAULT_STATUSES,
        "keyword": keyword[:120],
    }
    if aln:
        body["cfda"] = aln
    if "bia" in url.lower() or "BIA" in name:
        body["agencies"] = "DOI-BIA"
    return body


def _hit_matches_aln(hit: dict[str, Any], aln: str | None) -> bool:
    if not aln:
        return True
    cfda_list = hit.get("cfdaList") or hit.get("alnist") or []
    return any(str(c).startswith(aln) for c in cfda_list)


def _parse_detail_to_payload(
    hit: dict[str, Any],
    detail: dict[str, Any] | None,
    *,
    source: dict[str, Any],
    fetch_mode: FetchMode,
    search_live: bool,
    detail_live: bool,
) -> dict[str, Any]:
    data = detail or {}
    synopsis = data.get("synopsis") or {}
    elig = parse_grants_gov_opportunity_eligibility(data)
    live_success = (
        fetch_mode == FETCH_MODE_LIVE and search_live and detail_live and bool(data)
    )
    payload = {
        "adapter_key": "grants_gov_federal",
        "opportunity_number": str(
            data.get("opportunityNumber") or hit.get("number") or ""
        ),
        "opportunity_title": str(
            data.get("opportunityTitle") or hit.get("title") or ""
        ),
        "agency": str(
            elig.get("agency")
            or synopsis.get("agencyName")
            or hit.get("agency")
            or hit.get("agencyCode")
            or ""
        ),
        "source_url": (
            f"https://www.grants.gov/search-results-detail/{hit.get('id')}"
            if hit.get("id")
            else str(source.get("source_url") or "")
        ),
        "posted_date": str(hit.get("openDate") or synopsis.get("postingDate") or ""),
        "application_deadline": str(
            hit.get("closeDate") or synopsis.get("closeDate") or ""
        ),
        "synopsis": str(elig.get("synopsis") or synopsis.get("synopsisDesc") or ""),
        "eligibility_text": elig["eligibility_text"],
        "eligibility_text_source": elig.get("eligibility_text_source"),
        "eligibility_provenance": elig.get("eligibility_provenance"),
        "grants_gov_doc_type": elig.get("grants_gov_doc_type"),
        "grants_gov_attachment_inventory": elig.get("grants_gov_attachment_inventory"),
        "tribal_eligible": elig["tribal_eligible"],
        "applicant_type_ids": elig.get("applicant_type_ids") or [],
        "applicant_types_json": elig.get("applicant_types_json") or [],
        "grants_gov_opportunity_id": hit.get("id"),
        "fetch_mode": fetch_mode,
        "fixture": fetch_mode == FETCH_MODE_FIXTURE,
        "real_fetch": live_success,
        "search_live": search_live,
        "detail_live": detail_live,
        "source_seed_id": source.get("seed_id"),
        "never_synthesized": True,
    }
    assert_real_fetch_honest_labeling(payload)
    return payload


def search_grants_gov_opportunities(
    source: dict[str, Any],
    *,
    http_post: HttpPostJson | None = None,
    fetch_mode: FetchMode = FETCH_MODE_LIVE,
) -> dict[str, Any]:
    do_post = http_post or default_grants_gov_http_post
    body = build_grants_gov_search_body(source)
    search_live = False
    try:
        raw = do_post(SEARCH2_URL, body)
        search_live = raw.get("errorcode") == 0
    except _authorization_refusals() as refusal:
        # An authorization refusal is NOT a search result. Re-raised unchanged
        # so the guard's own reasons reach the caller: the old bare
        # `except Exception` turned "the guard refused to let us ask" into
        # `hit_count: 0`, which is indistinguishable from "Grants.gov has no
        # tribal grants".
        raise refusal
    except Exception as exc:  # noqa: BLE001 - a transport failure is not a refusal
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "search_body": body,
                "hit_count": 0,
                "opp_hits": [],
                "search_live": False,
                "fetch_mode": fetch_mode,
                "outcome": OUTCOME_FETCH_ERROR,
                "api_error": str(exc),
            }
        )
    if not search_live:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "search_body": body,
                "hit_count": 0,
                "opp_hits": [],
                "search_live": False,
                "fetch_mode": fetch_mode,
                "outcome": OUTCOME_FETCH_ERROR,
                "api_error": raw.get("msg"),
            }
        )
    data = raw.get("data") or {}
    hits = list(data.get("oppHits") or [])
    from nativeforge.services.fed_program_activation_binding_service import (
        SEED_ALN_BINDINGS,
    )

    bind_seed_id = str(source.get("seed_id") or "")
    aln = SEED_ALN_BINDINGS.get(bind_seed_id) or extract_assistance_listing_number(
        str(source.get("source_name") or "")
    )
    if aln:
        hits = [h for h in hits if _hit_matches_aln(h, aln)]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "search_body": body,
            "hit_count": len(hits),
            "opp_hits": hits,
            "search_live": search_live,
            "fetch_mode": fetch_mode,
            # A real answer. Zero hits here means Grants.gov returned zero,
            # which is a different fact from "we could not ask".
            "outcome": OUTCOME_HITS if hits else OUTCOME_EMPTY,
            "api_error": None,
            "never_synthesized": True,
        }
    )


def probe_grants_gov_live_hits(
    source: dict[str, Any],
    *,
    http_post: HttpPostJson | None = None,
) -> dict[str, Any]:
    search = search_grants_gov_opportunities(
        source,
        http_post=http_post,
        fetch_mode=FETCH_MODE_LIVE,
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "hit_count": search.get("hit_count", 0),
            "search_live": search.get("search_live", False),
            "assistance_listing_number": extract_assistance_listing_number(
                str(source.get("source_name") or "")
            ),
            "seed_id": source.get("seed_id"),
        }
    )


def fetch_grants_gov_opportunity_detail(
    opportunity_id: int | str,
    *,
    http_post: HttpPostJson | None = None,
) -> tuple[dict[str, Any], bool]:
    do_post = http_post or default_grants_gov_http_post
    try:
        raw = do_post(FETCH_OPPORTUNITY_URL, {"opportunityId": int(opportunity_id)})
    except Exception:
        return {}, False
    if raw.get("errorcode") != 0:
        return {}, False
    return raw.get("data") or {}, True


def fetch_grants_gov_opportunities_for_source(
    source: dict[str, Any],
    *,
    http_post: HttpPostJson | None = None,
    fetch_mode: FetchMode = FETCH_MODE_LIVE,
) -> dict[str, Any]:
    """Execute search2 + fetchOpportunity; honest fetch_mode / real_fetch labels."""
    search = search_grants_gov_opportunities(
        source,
        http_post=http_post,
        fetch_mode=fetch_mode,
    )
    hits = search.get("opp_hits") or []
    search_live = bool(search.get("search_live"))
    if not hits:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "payloads": [],
                "fetch_mode": fetch_mode,
                "search_live": search_live,
                "detail_live": False,
                "real_fetch": False,
                "never_synthesized": True,
            }
        )
    hit = hits[0]
    opp_id = hit.get("id")
    detail, detail_live = (
        fetch_grants_gov_opportunity_detail(opp_id, http_post=http_post)
        if opp_id
        else ({}, False)
    )
    payload = _parse_detail_to_payload(
        hit,
        detail,
        source=source,
        fetch_mode=fetch_mode,
        search_live=search_live,
        detail_live=detail_live,
    )
    if not payload.get("opportunity_number"):
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "payloads": [],
                "fetch_mode": fetch_mode,
                "search_live": search_live,
                "detail_live": detail_live,
                "real_fetch": False,
                "never_synthesized": True,
            }
        )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "payloads": [payload],
            "fetch_mode": fetch_mode,
            "search_live": search_live,
            "detail_live": detail_live,
            "real_fetch": payload.get("real_fetch") is True,
            "never_synthesized": True,
        }
    )


def fetch_fed001_grants_gov_opportunities(
    source: dict[str, Any] | None = None,
    *,
    http_post: HttpPostJson | None = None,
    fetch_mode: FetchMode = FETCH_MODE_LIVE,
) -> list[dict[str, Any]]:
    """Query Grants.gov for source ALN (fed-001 → 15.020 only); empty if no match."""
    from nativeforge.services.real_tier1_live_fetch_service import load_fed001_candidate

    chosen = source or load_fed001_candidate()
    result = fetch_grants_gov_opportunities_for_source(
        chosen,
        http_post=http_post,
        fetch_mode=fetch_mode,
    )
    return list(result.get("payloads") or [])


def load_recorded_grants_gov_search_fixture() -> list[dict[str, Any]]:
    """Recorded TEDC (15.148) search + fetchOpportunity — fixture, never real_fetch."""
    search_path = _FIXTURES_DIR / "grants_gov_search2_bia_tedc_hit.json"
    detail_path = _FIXTURES_DIR / "grants_gov_fetch_opportunity_362648.json"
    if not search_path.is_file():
        return []
    raw = json.loads(search_path.read_text(encoding="utf-8"))
    hit = (raw.get("data") or {}).get("oppHits") or []
    if not hit:
        return []
    detail: dict[str, Any] = {}
    if detail_path.is_file():
        detail_raw = json.loads(detail_path.read_text(encoding="utf-8"))
        detail = detail_raw.get("data") or {}
    from nativeforge.services.source_ingestion_seed_loader_service import (
        load_source_seed_rows,
        seed_row_to_discovery_candidate,
    )

    fallback_seed_id = "nf-seed-2026-fed-006"
    source: dict[str, Any] = {}
    for row in load_source_seed_rows():
        if row["seed_id"] == fallback_seed_id:
            source = seed_row_to_discovery_candidate(row)
            break
    if not source:
        source = {"seed_id": fallback_seed_id, "source_name": "", "source_url": ""}
    payload = _parse_detail_to_payload(
        hit[0],
        detail,
        source=source,
        fetch_mode=FETCH_MODE_FIXTURE,
        search_live=False,
        detail_live=False,
    )
    return [payload]
