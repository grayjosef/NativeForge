"""Federal source seed catalog (Gate 77D).

Category-level federal source references. **Not coverage, not monitoring, not
ingestion.** Every seed is `discovered` or `triaged`, carries
`robots_terms_status="unreviewed"`, has `last_checked_at=None`, and comes back
with `monitoring_allowed=False`.

Only entry points that are a matter of public record get a URL: grants.gov,
federalregister.gov, sam.gov. Agency NOFO pages are enumerated as *categories*
with the department named where the family requires it, because inventing a
specific agency NOFO URL would fabricate a federal source — and Gate 77's triage
showed exactly how much damage a wrong agency binding does.

Deliberately absent: any specific Native program page. Naming one would require
asserting that a particular program exists at a particular URL and serves a
particular applicant type, which is a factual claim about a real federal program
that cannot be verified from repo data.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.federal_source_lane_service import build_federal_source

SCHEMA_VERSION = "nf_federal_source_seed_catalog_v1"

FEDERAL_SEED_LANES = (
    "grants_gov",
    "federal_register",
    "agency_nofo_pages",
    "agency_program_pages",
    "native_specific_program_pages",
    "assistance_listing_evidence",
)


def _seed(
    key: str,
    lane: str,
    family: str,
    *,
    url: str | None = None,
    agency: str | None = None,
    subagency: str | None = None,
    program_name: str | None = None,
    access_method: str = "unknown",
    scope: str = "unknown",
    native_expected: bool = False,
    rationale: str | None = None,
) -> dict[str, Any]:
    return {
        "catalog_key": key,
        "lane": lane,
        "family": family,
        "url": url,
        "agency": agency,
        "subagency": subagency,
        "program_name": program_name,
        "access_method": access_method,
        "scope": scope,
        "native_expected": native_expected,
        "rationale": rationale,
    }


FEDERAL_SEEDS: tuple[dict[str, Any], ...] = (
    _seed(
        "fed.grants_gov.search",
        "grants_gov",
        "grants_gov",
        url="https://www.grants.gov/",
        access_method="public_api",
        scope="government_wide",
        native_expected=True,
        rationale=(
            "Government-wide index. Carries structured applicant eligibility "
            "codes including federally recognized tribal governments and tribal "
            "organizations, so eligibility can be evidenced rather than inferred."
        ),
    ),
    _seed(
        "fed.federal_register.notices",
        "federal_register",
        "federal_register",
        url="https://www.federalregister.gov/",
        access_method="public_api",
        scope="government_wide",
        rationale=(
            "Authoritative channel for funding notices, deadline extensions and "
            "amendments. Primary evidence source for the extension and "
            "supersession rules in the Gate 76 freshness service."
        ),
    ),
    _seed(
        "fed.sam_gov.assistance_listings",
        "assistance_listing_evidence",
        "sam_gov_assistance_listing",
        url="https://sam.gov/",
        access_method="public_api",
        scope="government_wide",
        rationale=(
            "Assistance listings carry applicant-type detail for a program. "
            "Evidence only when bound to a specific listing or opportunity."
        ),
    ),
    _seed(
        "fed.agency_nofo_pages.to_enumerate",
        "agency_nofo_pages",
        "agency_nofo_page",
        access_method="html_page_scheduled_check",
        scope="operating_division",
        rationale=(
            "Agencies publish NOFOs on their own pages, sometimes ahead of or "
            "instead of Grants.gov. Each entry needs its operating division "
            "named, not just its department: HHS is not a program owner."
        ),
    ),
    _seed(
        "fed.agency_program_pages.to_enumerate",
        "agency_program_pages",
        "agency_program_page",
        access_method="html_page_scheduled_check",
        scope="operating_division",
        rationale=(
            "Program pages describe recurring programs and their applicant "
            "types. Useful context; not opportunity-level eligibility on their own."
        ),
    ),
    _seed(
        "fed.native_specific_program_pages.to_enumerate",
        "native_specific_program_pages",
        "native_specific_federal_program_page",
        access_method="html_page_scheduled_check",
        scope="single_program",
        native_expected=True,
        rationale=(
            "Programs with statutory tribal set-asides or Native-specific "
            "authority. Highest-value lane for evidenced Native relevance. "
            "Deliberately not enumerated here: naming a specific program page "
            "would assert a factual claim about a real federal program that "
            "cannot be verified from repo data."
        ),
    ),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_federal_seed_catalog(lane: str | None = None) -> dict[str, Any]:
    """Build federal seeds as federal-lane source records.

    Each seed goes through ``build_federal_source`` so it inherits the
    monitoring gate rather than bypassing it.
    """
    wanted = [lane] if lane in FEDERAL_SEED_LANES else list(FEDERAL_SEED_LANES)
    records: list[dict[str, Any]] = []

    for seed in FEDERAL_SEEDS:
        if seed["lane"] not in wanted:
            continue
        record = build_federal_source(
            source_id=seed["catalog_key"],
            source_family=seed["family"],
            agency=seed["agency"],
            subagency=seed["subagency"],
            program_name=seed["program_name"],
            source_url=seed["url"],
            access_method=seed["access_method"],
            # Nothing has been reviewed and nothing has been checked.
            robots_terms_status="unreviewed",
            refresh_cadence="unknown",
            federal_program_scope=seed["scope"],
            native_relevance_expected=seed["native_expected"],
            native_relevance_rationale=seed["rationale"],
            provenance_url=seed["url"],
            promotion_status="discovered",
            last_checked_at=None,
        )
        record["seed_lane"] = seed["lane"]
        records.append(record)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "lanes": wanted,
            "records": records,
            "record_count": len(records),
            "monitoring_allowed_count": sum(
                1 for r in records if r["monitoring_allowed"]
            ),
            "with_url_count": sum(1 for r in records if r["source_url"]),
            "coverage_claimed": False,
            "live_ingestion_claimed": False,
            "federal_coverage_complete_claimed": False,
            "notes": (
                "Category-level references only. Nothing fetched, reviewed or "
                "monitored. Entries without a URL are categories awaiting "
                "enumeration; a plausible-looking agency NOFO URL would be a "
                "fabricated federal source."
            ),
        }
    )


def federal_seed_catalog_invariant_failures(catalog: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if catalog.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if not catalog.get("records"):
        fails.append("catalog_empty")

    for record in catalog.get("records") or []:
        key = record.get("source_id")
        if record.get("monitoring_allowed"):
            fails.append(f"seed_is_monitorable:{key}")
        if record.get("promotion_status") != "discovered":
            fails.append(f"seed_not_in_discovered_state:{key}")
        if record.get("robots_terms_status") != "unreviewed":
            fails.append(f"seed_claims_terms_review:{key}")
        if record.get("last_checked_at"):
            fails.append(f"seed_claims_a_check_timestamp:{key}")
        if record.get("freshness_claimable"):
            fails.append(f"seed_claims_freshness:{key}")
        if record.get("lane") != "federal":
            fails.append(f"seed_left_the_federal_lane:{key}")

    if catalog.get("monitoring_allowed_count") != 0:
        fails.append("catalog_reports_monitorable_sources")
    for forbidden in (
        "coverage_claimed",
        "live_ingestion_claimed",
        "federal_coverage_complete_claimed",
    ):
        if catalog.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")
    return fails
