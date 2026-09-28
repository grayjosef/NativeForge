"""Customer-facing live federal opportunity search.

Collectors stay off. This is a customer-initiated query of the public
Grants.gov search2 API, labeled honestly, never synthesized, never treated as
a Native-relevance verdict.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.grants_gov_search_api_adapter_service import (
    ELIGIBILITY_INDIAN_HOUSING_AUTHORITY,
    ELIGIBILITY_TRIBAL_GOVERNMENT,
    ELIGIBILITY_TRIBAL_ORGANIZATION,
    EXPECTED_ELIGIBILITY_FACET_LABELS,
    FETCH_MODE_FIXTURE,
    FETCH_MODE_LIVE,
    HttpPostJson,
    search_grants_gov_by_eligibility,
)

SCHEMA_VERSION = "nf_customer_live_federal_search_v1"

SEARCH_CLASSES: tuple[str, ...] = (
    ELIGIBILITY_TRIBAL_GOVERNMENT,
    ELIGIBILITY_TRIBAL_ORGANIZATION,
    ELIGIBILITY_INDIAN_HOUSING_AUTHORITY,
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _row_from_hit(hit: dict[str, Any], eligibility_code: str) -> dict[str, Any]:
    evidence = hit.get("nf_eligibility_evidence") or {}
    number = str(hit.get("number") or hit.get("opportunityNumber") or "")
    title = str(hit.get("title") or hit.get("opportunityTitle") or "")
    agency = str(hit.get("agency") or hit.get("agencyName") or hit.get("agencyCode") or "")
    oid = hit.get("id")
    return {
        "opportunity_number": number,
        "title": title,
        "funder": agency,
        "program": str(hit.get("cfdaList") or hit.get("alnist") or [""])[:1][0]
        if isinstance(hit.get("cfdaList") or hit.get("alnist"), list)
        else "",
        "funding": str(hit.get("awardCeiling") or hit.get("estimatedFunding") or ""),
        "deadline": str(hit.get("closeDate") or hit.get("closeDateExplained") or ""),
        "eligibility_code": eligibility_code,
        "eligibility_label": EXPECTED_ELIGIBILITY_FACET_LABELS.get(eligibility_code, ""),
        "native_relevance": "publisher_eligibility_class",
        "native_relevance_decided": False,
        "why_it_matches": (
            "Grants.gov lists this opportunity under "
            f"{EXPECTED_ELIGIBILITY_FACET_LABELS.get(eligibility_code, eligibility_code)}. "
            "That is the publisher's applicant class, not a NativeForge verdict."
        ),
        "source": "grants.gov",
        "source_url": (
            f"https://www.grants.gov/search-results-detail/{oid}" if oid else ""
        ),
        "search_live": True,
        "never_synthesized": True,
        "tenant_eligibility_decided": False,
        "opportunity_id": oid,
        "evidence": evidence,
    }


def search_live_federal_opportunities(
    *,
    http_post: HttpPostJson | None = None,
    rows_per_class: int = 15,
    fetch_mode: str = FETCH_MODE_LIVE,
) -> dict[str, Any]:
    """Search the three Tribal applicant classes and merge unique rows."""
    mode = FETCH_MODE_FIXTURE if fetch_mode == FETCH_MODE_FIXTURE else FETCH_MODE_LIVE
    seen: set[str] = set()
    results: list[dict[str, Any]] = []
    class_outcomes: list[dict[str, Any]] = []
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
        for hit in raw.get("opp_hits") or []:
            if not isinstance(hit, dict):
                continue
            key = str(hit.get("number") or hit.get("id") or "")
            if not key or key in seen:
                continue
            seen.add(key)
            results.append(_row_from_hit(hit, code))

    status = "hits" if results else "empty"
    if blocked and not results:
        status = "live_search_not_authorized"
    elif error and not results and not live:
        status = "fetch_error"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source": "grants.gov",
            "collectors_live": False,
            "search_live": live,
            "never_synthesized": True,
            "fabricated": False,
            "status": status,
            "error": error,
            "class_outcomes": class_outcomes,
            "result_count": len(results),
            "results": results,
        }
    )
