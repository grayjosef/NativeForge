"""South Carolina source seed catalog (Gate 78D).

Category-level SC source references. **Not coverage, not monitoring, not
ingestion.** Every seed is `discovered`, `unreviewed`, `last_checked_at=None`,
and comes back `monitoring_allowed=False`.

**No seed carries a URL.** Unlike the federal lane — where grants.gov,
federalregister.gov and sam.gov are canonical public entry points and a matter of
public record — there is no equivalent SC address this repo can assert without
research. Writing a plausible-looking state portal URL would fabricate a source,
and `source_seed_real_url_guard_service` exists because that has been a problem
here before.

That leaves this catalog deliberately thin, and thin is the honest state. South
Carolina's Native-relevant state funding landscape has not been enumerated. A
catalog of invented URLs would look like progress and would send a tribal grant
office to pages that do not exist.

`native_relevance_expected` is likewise `False` throughout. Whether an SC source
tends to carry Native-relevant opportunities is a finding, not an assumption, and
nothing here has been examined.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.sc_state_source_lane_service import build_sc_source

SCHEMA_VERSION = "nf_sc_source_seed_catalog_v1"

SC_SEED_LANES = (
    "sc_state_portal",
    "sc_agency_grant_pages",
    "sc_agency_program_pages",
    "sc_procurement",
    "sc_foundations",
    "sc_regional_local",
    "native_intermediary",
)


def _seed(
    key: str,
    lane: str,
    family: str,
    *,
    scope: str = "unknown",
    rationale: str | None = None,
) -> dict[str, Any]:
    return {
        "catalog_key": key,
        "lane": lane,
        "family": family,
        "scope": scope,
        "rationale": rationale,
    }


SC_SEEDS: tuple[dict[str, Any], ...] = (
    _seed(
        "sc.state_portal.to_research",
        "sc_state_portal",
        "sc_state_grant_portal",
        scope="statewide",
        rationale=(
            "Central SC state funding listings, if one exists. State-administered "
            "opportunities including pass-through federal funds. Distinct lane "
            "from federal: state eligibility rules may recognise state-recognized "
            "tribes that federal programs do not."
        ),
    ),
    _seed(
        "sc.agency_grant_pages.to_enumerate",
        "sc_agency_grant_pages",
        "sc_agency_grant_page",
        scope="agency_wide",
        rationale=(
            "Department-level SC opportunities not aggregated centrally. Each "
            "needs its owning state agency named, not just the state."
        ),
    ),
    _seed(
        "sc.agency_program_pages.to_enumerate",
        "sc_agency_program_pages",
        "sc_agency_program_page",
        scope="single_program",
        rationale=(
            "Recurring SC programs and their applicant rules. Context for "
            "eligibility, not opportunity-level eligibility on its own."
        ),
    ),
    _seed(
        "sc.procurement.to_research",
        "sc_procurement",
        "sc_procurement_or_contracting_page",
        scope="statewide",
        rationale=(
            "Contracting and procurement, relevant to Native business and "
            "economic-development pursuit. A contract is not a grant and its "
            "eligibility rules differ; kept as a separate family."
        ),
    ),
    _seed(
        "sc.foundations.to_enumerate",
        "sc_foundations",
        "sc_community_foundation",
        scope="regional",
        rationale=(
            "Regional philanthropic funders. Often the only lane open to a Native "
            "nonprofit that is not a federally recognized tribal government."
        ),
    ),
    _seed(
        "sc.regional_local.to_enumerate",
        "sc_regional_local",
        "sc_regional_council",
        scope="regional",
        rationale=(
            "Councils of government, county and municipal sources. Highest effort "
            "per opportunity; lowest aggregation."
        ),
    ),
    _seed(
        "sc.native_intermediary.to_research",
        "native_intermediary",
        "native_intermediary",
        scope="unknown",
        rationale=(
            "Native-serving intermediaries and funds relevant to SC tribal and "
            "Native nonprofit organizations. Frequently carry explicit Native "
            "eligibility language, so relevance would be evidenceable once "
            "identified."
        ),
    ),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_sc_seed_catalog(lane: str | None = None) -> dict[str, Any]:
    """Build SC seeds as SC-lane source records.

    Each seed goes through ``build_sc_source`` so it inherits the monitoring
    gate rather than bypassing it.
    """
    wanted = [lane] if lane in SC_SEED_LANES else list(SC_SEED_LANES)
    records: list[dict[str, Any]] = []

    for seed in SC_SEEDS:
        if seed["lane"] not in wanted:
            continue
        record = build_sc_source(
            source_id=seed["catalog_key"],
            source_family=seed["family"],
            state="SC",
            state_agency=None,
            source_url=None,
            access_method="unknown",
            robots_terms_status="unreviewed",
            refresh_cadence="unknown",
            state_program_scope=seed["scope"],
            native_relevance_expected=False,
            native_relevance_rationale=seed["rationale"],
            recognition_relevance=None,
            provenance_url=None,
            promotion_status="discovered",
            last_checked_at=None,
        )
        record["seed_lane"] = seed["lane"]
        records.append(record)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "state": "SC",
            "lanes": wanted,
            "records": records,
            "record_count": len(records),
            "monitoring_allowed_count": sum(
                1 for r in records if r["monitoring_allowed"]
            ),
            "with_url_count": sum(1 for r in records if r["source_url"]),
            "coverage_claimed": False,
            "live_ingestion_claimed": False,
            "sc_coverage_complete_claimed": False,
            "notes": (
                "Categories only. No SC source has been identified, fetched, "
                "reviewed or monitored. No seed carries a URL: unlike the federal "
                "lane there is no canonical SC entry point this repo can assert "
                "without research, and a plausible-looking state portal URL would "
                "be a fabricated source."
            ),
        }
    )


def sc_seed_catalog_invariant_failures(catalog: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if catalog.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if not catalog.get("records"):
        fails.append("catalog_empty")
    if catalog.get("state") != "SC":
        fails.append("catalog_is_not_south_carolina")

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
        if record.get("source_url"):
            fails.append(f"seed_claims_a_url_without_research:{key}")
        if record.get("lane") != "sc_state":
            fails.append(f"seed_left_the_sc_state_lane:{key}")
        if record.get("federal_agency"):
            fails.append(f"sc_seed_carries_a_federal_agency:{key}")

    if catalog.get("monitoring_allowed_count") != 0:
        fails.append("catalog_reports_monitorable_sources")
    if catalog.get("with_url_count") != 0:
        fails.append("catalog_reports_seed_urls_without_research")
    for forbidden in (
        "coverage_claimed",
        "live_ingestion_claimed",
        "sc_coverage_complete_claimed",
    ):
        if catalog.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")
    return fails
