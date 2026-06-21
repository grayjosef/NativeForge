"""Sprint 304: real Grants.gov search2 + fetchOpportunity adapter for tier-1 federal."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from nativeforge.services.seed_source_human_activation_service import (
    NF9_AUTHORIZED_SEED_ID,
)

SCHEMA_VERSION = "nf_grants_gov_search_api_adapter_v1"
SEARCH2_URL = "https://api.grants.gov/v1/api/search2"
FETCH_OPPORTUNITY_URL = "https://api.grants.gov/v1/api/fetchOpportunity"
DEFAULT_ROWS = 5
DEFAULT_STATUSES = "posted|forecasted"

HttpPostJson = Callable[[str, dict[str, Any]], dict[str, Any]]

_ALN_RE = re.compile(r"(\d{2}\.\d{3})")


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def default_grants_gov_http_post(url: str, body: dict[str, Any]) -> dict[str, Any]:
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
    aln = extract_assistance_listing_number(name)
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
) -> dict[str, Any]:
    data = detail or {}
    synopsis = data.get("synopsis") or {}
    alns = data.get("alns") or []
    eligibility = ""
    if synopsis.get("applicantTypes"):
        eligibility = "; ".join(
            str(x.get("description") or "")
            for x in synopsis["applicantTypes"]
            if isinstance(x, dict)
        )
    elif alns:
        eligibility = "; ".join(
            str(a.get("programTitle") or "") for a in alns if isinstance(a, dict)
        )
    return {
        "adapter_key": "grants_gov_federal",
        "opportunity_number": str(
            data.get("opportunityNumber") or hit.get("number") or ""
        ),
        "opportunity_title": str(
            data.get("opportunityTitle") or hit.get("title") or ""
        ),
        "agency": str(
            synopsis.get("agencyName")
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
        "synopsis": str(synopsis.get("synopsisDesc") or ""),
        "eligibility_text": eligibility,
        "grants_gov_opportunity_id": hit.get("id"),
        "real_fetch": True,
        "source_seed_id": source.get("seed_id"),
        "never_synthesized": True,
    }


def search_grants_gov_opportunities(
    source: dict[str, Any],
    *,
    http_post: HttpPostJson | None = None,
) -> dict[str, Any]:
    do_post = http_post or default_grants_gov_http_post
    body = build_grants_gov_search_body(source)
    raw = do_post(SEARCH2_URL, body)
    if raw.get("errorcode") != 0:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "search_body": body,
                "hit_count": 0,
                "opp_hits": [],
                "api_error": raw.get("msg"),
            }
        )
    data = raw.get("data") or {}
    hits = list(data.get("oppHits") or [])
    aln = extract_assistance_listing_number(str(source.get("source_name") or ""))
    if aln:
        hits = [h for h in hits if _hit_matches_aln(h, aln)]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "search_body": body,
            "hit_count": len(hits),
            "opp_hits": hits,
            "never_synthesized": True,
        }
    )


def fetch_grants_gov_opportunity_detail(
    opportunity_id: int | str,
    *,
    http_post: HttpPostJson | None = None,
) -> dict[str, Any]:
    do_post = http_post or default_grants_gov_http_post
    raw = do_post(FETCH_OPPORTUNITY_URL, {"opportunityId": int(opportunity_id)})
    if raw.get("errorcode") != 0:
        return {}
    return raw.get("data") or {}


def fetch_fed001_grants_gov_opportunities(
    source: dict[str, Any] | None = None,
    *,
    http_post: HttpPostJson | None = None,
) -> list[dict[str, Any]]:
    """Query search2 for fed-001 program; return parsed NOFO rows or empty list."""
    from nativeforge.services.real_tier1_live_fetch_service import load_fed001_candidate

    chosen = source or load_fed001_candidate()
    search = search_grants_gov_opportunities(chosen, http_post=http_post)
    hits = search.get("opp_hits") or []
    if not hits:
        return []
    hit = hits[0]
    opp_id = hit.get("id")
    detail = (
        fetch_grants_gov_opportunity_detail(opp_id, http_post=http_post)
        if opp_id
        else None
    )
    payload = _parse_detail_to_payload(hit, detail, source=chosen)
    if not payload.get("opportunity_number"):
        return []
    return [payload]


def load_recorded_grants_gov_search_fixture() -> list[dict[str, Any]]:
    """Offline recorded search hit — real API shape, not illustrative fiction."""
    from pathlib import Path

    path = (
        Path(__file__).resolve().parents[3]
        / "fixtures"
        / "source_ingestion"
        / "grants_gov_search2_bia_tedc_hit.json"
    )
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    hit = (raw.get("data") or {}).get("oppHits") or []
    if not hit:
        return []
    source = {
        "seed_id": NF9_AUTHORIZED_SEED_ID,
        "source_name": "BIA TEDC",
        "source_url": "",
    }
    return [_parse_detail_to_payload(hit[0], None, source=source)]
