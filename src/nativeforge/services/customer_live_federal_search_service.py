"""Customer-facing live federal opportunity search.

Collectors stay off. This is a customer-initiated query of the public
Grants.gov search2 API, labeled honestly, never synthesized, never treated as
a Native-relevance verdict.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.grants_gov_eligibility_parser_service import (
    parse_grants_gov_opportunity_eligibility,
)
from nativeforge.services.grants_gov_search_api_adapter_service import (
    ELIGIBILITY_INDIAN_HOUSING_AUTHORITY,
    ELIGIBILITY_TRIBAL_GOVERNMENT,
    ELIGIBILITY_TRIBAL_ORGANIZATION,
    EXPECTED_ELIGIBILITY_FACET_LABELS,
    FETCH_MODE_FIXTURE,
    FETCH_MODE_LIVE,
    HttpPostJson,
    fetch_grants_gov_opportunity_detail,
    search_grants_gov_broad,
    search_grants_gov_by_eligibility,
)
from nativeforge.services.source_fleet_live_readiness_service import (
    derive_collectors_live,
)

SCHEMA_VERSION = "nf_customer_live_federal_search_v1"

SEARCH_CLASSES: tuple[str, ...] = (
    ELIGIBILITY_TRIBAL_GOVERNMENT,
    ELIGIBILITY_TRIBAL_ORGANIZATION,
    ELIGIBILITY_INDIAN_HOUSING_AUTHORITY,
)

LANE_PUBLISHER_CLASS = "publisher_applicant_class"
LANE_BROAD = "broad_posted_or_forecasted"
DETAIL_ENRICH_CAP = 8


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _first_listing(hit: dict[str, Any]) -> str | None:
    for key in ("cfdaList", "alnist"):
        values = hit.get(key)
        if isinstance(values, list) and values:
            text = str(values[0]).strip()
            if text:
                return text
    return None


def _present(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _row_from_hit(
    hit: dict[str, Any],
    *,
    coverage_lane: str,
    eligibility_code: str | None,
) -> dict[str, Any]:
    evidence = hit.get("nf_eligibility_evidence") or {}
    number = str(hit.get("number") or hit.get("opportunityNumber") or "")
    title = str(hit.get("title") or hit.get("opportunityTitle") or "")
    agency = str(
        hit.get("agency") or hit.get("agencyName") or hit.get("agencyCode") or ""
    )
    oid = hit.get("id")
    label = (
        EXPECTED_ELIGIBILITY_FACET_LABELS.get(eligibility_code, "")
        if eligibility_code
        else ""
    )
    if coverage_lane == LANE_PUBLISHER_CLASS and label:
        why = (
            "Grants.gov lists this opportunity under "
            f"{label}. That is the publisher's applicant class, not a NativeForge verdict."
        )
        relevance = "publisher_eligibility_class"
    else:
        why = (
            "Grants.gov returned this posted or forecasted opportunity without an "
            "applicant-class filter. NativeForge has not decided relevance or eligibility."
        )
        relevance = "not_decided"
    ceiling = _present(hit.get("awardCeiling"))
    return {
        "opportunity_number": number,
        "title": title,
        "funder": agency,
        "agency_code": _present(hit.get("agencyCode")),
        "program": _first_listing(hit) or "",
        "assistance_listing": _first_listing(hit),
        "funding": ceiling or _present(hit.get("estimatedFunding")) or "",
        "award_ceiling": ceiling,
        "award_floor": _present(hit.get("awardFloor")),
        "estimated_funding": _present(hit.get("estimatedFunding")),
        "deadline": str(hit.get("closeDate") or hit.get("closeDateExplained") or ""),
        "open_date": _present(hit.get("openDate")),
        "opportunity_status": _present(hit.get("oppStatus")),
        "eligibility_code": eligibility_code,
        "eligibility_label": label,
        "eligibility_text": None,
        "contacts": None,
        "documents": None,
        "geography": None,
        "coverage_lane": coverage_lane,
        "native_relevance": relevance,
        "native_relevance_decided": False,
        "why_it_matches": why,
        "source": "grants.gov",
        "source_url": (
            f"https://www.grants.gov/search-results-detail/{oid}" if oid else ""
        ),
        "search_live": True,
        "detail_status": "not_requested",
        "never_synthesized": True,
        "tenant_eligibility_decided": False,
        "opportunity_id": oid,
        "evidence": evidence,
        "fabricated": False,
    }


def _apply_detail(row: dict[str, Any], detail: dict[str, Any]) -> None:
    """Copy fields the detail record actually carries. Absent stays absent."""
    if not detail or not (detail.get("synopsis") or detail.get("opportunityTitle")):
        row["detail_status"] = "unavailable"
        return
    synopsis = (
        detail.get("synopsis") if isinstance(detail.get("synopsis"), dict) else {}
    )
    parsed = parse_grants_gov_opportunity_eligibility(detail)
    eligibility = _present(parsed.get("eligibility_text"))
    if eligibility:
        row["eligibility_text"] = eligibility
    for source_key, target in (
        ("awardCeiling", "award_ceiling"),
        ("awardFloor", "award_floor"),
        ("estimatedFunding", "estimated_funding"),
        ("postingDate", "open_date"),
        ("responseDate", "deadline"),
        ("archiveDate", "archive_date"),
    ):
        found = _present(synopsis.get(source_key))
        if found:
            row[target] = found
    if row.get("award_ceiling"):
        row["funding"] = row["award_ceiling"]
    elif row.get("estimated_funding"):
        row["funding"] = row["estimated_funding"]
    contact_name = _present(synopsis.get("agencyContactName"))
    contact_email = _present(synopsis.get("agencyContactEmail"))
    if contact_name or contact_email:
        row["contacts"] = {"name": contact_name, "email": contact_email}
    documents = detail.get("synopsisDocumentURLs")
    if isinstance(documents, list) and documents:
        row["documents"] = documents
    row["detail_status"] = "enriched"


def _absorb_hits(
    raw: dict[str, Any],
    *,
    results: list[dict[str, Any]],
    seen: set[str],
    coverage_lane: str,
    eligibility_code: str | None,
) -> None:
    for hit in raw.get("opp_hits") or []:
        if not isinstance(hit, dict):
            continue
        key = str(hit.get("number") or hit.get("id") or "")
        if not key or key in seen:
            continue
        seen.add(key)
        results.append(
            _row_from_hit(
                hit,
                coverage_lane=coverage_lane,
                eligibility_code=eligibility_code,
            )
        )


def search_live_federal_opportunities(
    *,
    http_post: HttpPostJson | None = None,
    rows_per_class: int = 15,
    fetch_mode: str = FETCH_MODE_LIVE,
    enrich_details: bool = True,
) -> dict[str, Any]:
    """Search publisher applicant classes and the broad posted/forecasted index."""
    mode = FETCH_MODE_FIXTURE if fetch_mode == FETCH_MODE_FIXTURE else FETCH_MODE_LIVE
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    class_outcomes: list[dict[str, Any]] = []
    broad_outcome: dict[str, Any] | None = None
    live = False
    blocked = False
    error: str | None = None

    for code in SEARCH_CLASSES:
        try:
            raw = search_grants_gov_by_eligibility(
                eligibility_code=code,
                rows=rows_per_class,
                http_post=http_post,
                fetch_mode=mode,
            )
        except Exception as exc:  # noqa: BLE001 - transport/guard is a search state
            name = type(exc).__name__
            if "LiveNetworkBlocked" in name:
                blocked = True
                error = str(exc)
                class_outcomes.append(
                    {"eligibility_code": code, "outcome": "blocked", "hit_count": 0}
                )
                continue
            error = str(exc)
            class_outcomes.append(
                {"eligibility_code": code, "outcome": "fetch_error", "hit_count": 0}
            )
            continue

        if raw.get("search_live"):
            live = True
        class_outcomes.append(
            {
                "eligibility_code": code,
                "outcome": raw.get("outcome"),
                "hit_count": int(raw.get("hit_count") or 0),
                "facet_contract_holds": bool(
                    (raw.get("facet_contract") or {}).get("contract_holds")
                )
                if raw.get("facet_contract")
                else None,
            }
        )
        _absorb_hits(
            raw,
            results=results,
            seen=seen,
            coverage_lane=LANE_PUBLISHER_CLASS,
            eligibility_code=code,
        )

    try:
        broad = search_grants_gov_broad(
            rows=rows_per_class,
            http_post=http_post,
            fetch_mode=mode,
        )
    except Exception as exc:  # noqa: BLE001 - a broad refusal is not an empty index
        name = type(exc).__name__
        if "LiveNetworkBlocked" in name:
            blocked = True
            error = error or str(exc)
            broad_outcome = {"outcome": "blocked", "hit_count": 0}
        else:
            error = error or str(exc)
            broad_outcome = {"outcome": "fetch_error", "hit_count": 0}
    else:
        if broad.get("search_live"):
            live = True
        broad_outcome = {
            "outcome": broad.get("outcome"),
            "hit_count": int(broad.get("hit_count") or 0),
            "total_hit_count": broad.get("total_hit_count"),
        }
        _absorb_hits(
            broad,
            results=results,
            seen=seen,
            coverage_lane=LANE_BROAD,
            eligibility_code=None,
        )

    enriched = 0
    if enrich_details:
        for row in results:
            if enriched >= DETAIL_ENRICH_CAP:
                break
            if not row.get("opportunity_id"):
                continue
            detail, ok = fetch_grants_gov_opportunity_detail(
                row["opportunity_id"],
                http_post=http_post,
            )
            enriched += 1
            if ok:
                _apply_detail(row, detail)
            else:
                row["detail_status"] = "unavailable"

    status = "hits" if results else "empty"
    if blocked and not results:
        status = "live_search_not_authorized"
    elif error and not results and not live:
        status = "fetch_error"

    fleet = derive_collectors_live()
    lanes = {
        LANE_PUBLISHER_CLASS: sum(
            1 for row in results if row["coverage_lane"] == LANE_PUBLISHER_CLASS
        ),
        LANE_BROAD: sum(1 for row in results if row["coverage_lane"] == LANE_BROAD),
    }

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source": "grants.gov",
            "collectors_live": fleet["collectors_live"],
            "fleet_live_sources": fleet["fleet_live_sources"],
            "search_live": live,
            "never_synthesized": True,
            "fabricated": False,
            "status": status,
            "error": error,
            "class_outcomes": class_outcomes,
            "broad_outcome": broad_outcome,
            "lanes": lanes,
            "result_count": len(results),
            "results": results,
        }
    )
