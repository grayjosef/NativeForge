"""Seed source catalog — categories and placeholders (Gate 76E).

**This is not live coverage.** Every entry is a category placeholder with
`promotion_status="discovered"`, `robots_terms_status="unreviewed"` and
`last_checked_at=None`. Nothing here has been fetched, nothing is monitored, and
no entry can be monitored until a human reviews its terms — enforced by
`source_registry_service.build_source_record`, not by convention.

Two things this file deliberately does **not** contain:

  * **Fabricated URLs.** Where a canonical public entry point is a matter of
    public record (grants.gov, the Federal Register), it is named. Where it is
    not, `source_url` is `None` and the entry is a category to be researched.
    Inventing a plausible-looking state portal URL would be fabricating a
    source, and `source_seed_real_url_guard_service` exists because that has
    been a problem before.
  * **Fabricated timestamps.** No `last_checked_at`, ever. A seed with a check
    timestamp would claim we had looked at something we have not.

Lanes follow the campaign's ordering: federal first because it is the most
uniform, South Carolina second as the first production-quality proving ground,
then the expansion framework.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_registry_service import (
    build_source_record,
)

SCHEMA_VERSION = "nf_source_seed_catalog_v1"

LANES = ("federal", "south_carolina", "expansion")


def _seed(
    key: str,
    name: str,
    source_type: str,
    jurisdiction: str,
    *,
    url: str | None = None,
    state: str | None = None,
    federal_agency: str | None = None,
    access_method: str = "unknown",
    rationale: str | None = None,
) -> dict[str, Any]:
    """One catalog entry. Always `discovered` + `unreviewed` + no timestamps."""
    return {
        "catalog_key": key,
        "source_name": name,
        "source_url": url,
        "source_type": source_type,
        "jurisdiction": jurisdiction,
        "state": state,
        "federal_agency": federal_agency,
        "access_method": access_method,
        "native_relevance_rationale": rationale,
    }


# ── federal lane ────────────────────────────────────────────────────────────
# The most uniform lane: a small number of canonical, publicly documented entry
# points plus per-agency NOFO pages that still need enumerating.
FEDERAL_SEEDS: tuple[dict[str, Any], ...] = (
    _seed(
        "federal.grants_gov",
        "Grants.gov",
        "grants_gov",
        "federal",
        url="https://www.grants.gov/",
        access_method="public_api",
        rationale=(
            "Government-wide federal opportunity index. Carries explicit eligible "
            "applicant codes including federally recognized tribal governments and "
            "tribal organizations, so eligibility can be evidenced rather "
            "than inferred."
        ),
    ),
    _seed(
        "federal.federal_register",
        "Federal Register",
        "federal_register",
        "federal",
        url="https://www.federalregister.gov/",
        access_method="public_api",
        rationale=(
            "Authoritative source for funding notices, deadline extensions and "
            "amendments. Primary evidence source for amendment and extension claims."
        ),
    ),
    _seed(
        "federal.agency_nofo_pages",
        "Federal agency NOFO pages (to enumerate)",
        "federal_agency_nofo_page",
        "federal",
        access_method="html_page_scheduled_check",
        rationale=(
            "Agencies publish NOFOs on their own pages, sometimes before or "
            "instead of Grants.gov. Per-agency enumeration is outstanding work."
        ),
    ),
    _seed(
        "federal.native_specific_program_pages",
        "Native-specific federal program pages (to enumerate)",
        "federal_agency_nofo_page",
        "federal",
        access_method="html_page_scheduled_check",
        rationale=(
            "Programs with statutory tribal set-asides or Native-specific authority. "
            "Highest-value lane for evidenced Native relevance; requires enumeration "
            "per agency rather than a single index."
        ),
    ),
)

# ── South Carolina lane ─────────────────────────────────────────────────────
# SC is the first production-quality proving ground. Entries are categories:
# specific portals and agency pages need research before a URL is recorded.
#
# One SC-specific fact that shapes this lane and is a matter of public record:
# South Carolina has state-recognized tribes, and state recognition is a
# different status from federal recognition with different eligibility
# consequences. The registry must route those separately — which is why
# recognition routing carries an applicant axis at all.
SOUTH_CAROLINA_SEEDS: tuple[dict[str, Any], ...] = (
    _seed(
        "sc.state_grant_portal",
        "South Carolina state grant portal(s) (to research)",
        "state_grant_portal",
        "state",
        state="SC",
        access_method="unknown",
        rationale=(
            "State-administered opportunities, including pass-through federal funds. "
            "Distinct lane from federal: state eligibility rules may recognise "
            "state-recognized tribes that federal programs do not."
        ),
    ),
    _seed(
        "sc.agency_grant_pages",
        "SC agency grant pages (to enumerate)",
        "state_agency_page",
        "state",
        state="SC",
        access_method="html_page_scheduled_check",
        rationale=(
            "Department-level SC opportunities not aggregated in a central portal."
        ),
    ),
    _seed(
        "sc.community_foundations",
        "SC community foundations (to enumerate)",
        "community_foundation",
        "private",
        state="SC",
        access_method="unknown",
        rationale=(
            "Regional philanthropic funders. Often the only lane open to a Native "
            "nonprofit that is not a federally recognized tribal government."
        ),
    ),
    _seed(
        "sc.native_relevant_regional",
        "SC Native-relevant regional sources (to research)",
        "native_intermediary",
        "private",
        state="SC",
        access_method="unknown",
        rationale=(
            "Native-serving intermediaries and regional funders relevant to SC "
            "tribal and Native nonprofit organizations."
        ),
    ),
)

# ── expansion lane ──────────────────────────────────────────────────────────
EXPANSION_SEEDS: tuple[dict[str, Any], ...] = (
    _seed(
        "expansion.top15_state_framework",
        "Top-15 state framework (not yet scoped)",
        "state_grant_portal",
        "state",
        access_method="unknown",
        rationale=(
            "Generalises the SC pattern to further states. Each state needs its own "
            "recognition routing: state-recognition status varies and must not be "
            "generalised from SC."
        ),
    ),
    _seed(
        "expansion.native_intermediaries",
        "Native intermediary funders (to enumerate)",
        "native_intermediary",
        "private",
        access_method="unknown",
        rationale=(
            "Native-led and Native-serving funds and CDFIs. Frequently carry "
            "explicit Native eligibility language, so relevance is evidenceable."
        ),
    ),
    _seed(
        "expansion.foundations",
        "National foundations (to enumerate)",
        "foundation",
        "private",
        access_method="unknown",
        rationale="National philanthropic funders with Native-relevant programs.",
    ),
    _seed(
        "expansion.corporate_grants",
        "Corporate giving programs (to enumerate)",
        "corporate_grants",
        "private",
        access_method="unknown",
        rationale=(
            "Corporate community giving with tribal or Native-serving eligibility."
        ),
    ),
    _seed(
        "expansion.university_research",
        "University research partnerships (to enumerate)",
        "university_research",
        "private",
        access_method="unknown",
        rationale=(
            "Subaward and partnership opportunities requiring an academic partner."
        ),
    ),
    _seed(
        "expansion.local_regional",
        "Local and regional sources (to enumerate)",
        "local_regional",
        "local",
        access_method="unknown",
        rationale="County and municipal opportunities; highest effort per opportunity.",
    ),
)

SEEDS_BY_LANE: dict[str, tuple[dict[str, Any], ...]] = {
    "federal": FEDERAL_SEEDS,
    "south_carolina": SOUTH_CAROLINA_SEEDS,
    "expansion": EXPANSION_SEEDS,
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_seed_catalog(lane: str | None = None) -> dict[str, Any]:
    """Build the seed catalog as registry records.

    Every record goes through `build_source_record`, so every entry inherits the
    monitoring gate rather than bypassing it. The invariant that matters: no
    entry comes back with `can_monitor=True`.
    """
    lanes = [lane] if lane in SEEDS_BY_LANE else list(LANES)
    records: list[dict[str, Any]] = []

    for lane_name in lanes:
        for seed in SEEDS_BY_LANE[lane_name]:
            record = build_source_record(
                source_id=seed["catalog_key"],
                source_name=seed["source_name"],
                source_url=seed["source_url"],
                source_type=seed["source_type"],
                jurisdiction=seed["jurisdiction"],
                state=seed["state"],
                federal_agency=seed["federal_agency"],
                access_method=seed["access_method"],
                # Nothing has been reviewed and nothing has been checked.
                robots_terms_status="unreviewed",
                promotion_status="discovered",
                retirement_status="active",
                last_checked_at=None,
                staleness_status="unknown",
                native_relevance_rationale=seed["native_relevance_rationale"],
                provenance_url=seed["source_url"],
            )
            record["lane"] = lane_name
            records.append(record)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "lanes": lanes,
            "records": records,
            "record_count": len(records),
            "monitorable_count": sum(1 for r in records if r["can_monitor"]),
            "with_url_count": sum(1 for r in records if r["source_url"]),
            # The claims this catalog must never make.
            "live_coverage_claimed": False,
            "coverage_complete_claimed": False,
            "any_source_monitored": False,
            "notes": (
                "Categories and placeholders only. No source has been fetched, "
                "reviewed or monitored. Entries without a source_url are "
                "categories awaiting research; a plausible-looking URL would be "
                "a fabricated source."
            ),
        }
    )


def seed_catalog_invariant_failures(catalog: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if catalog.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if not catalog.get("records"):
        fails.append("catalog_empty")

    for record in catalog.get("records") or []:
        key = record.get("source_id")
        # The central guarantee: a seed can never be monitorable.
        if record.get("can_monitor"):
            fails.append(f"seed_is_monitorable:{key}")
        if record.get("promotion_status") != "discovered":
            fails.append(f"seed_not_in_discovered_state:{key}")
        if record.get("robots_terms_status") != "unreviewed":
            fails.append(f"seed_claims_terms_review:{key}")
        if record.get("last_checked_at"):
            fails.append(f"seed_claims_a_check_timestamp:{key}")
        if record.get("staleness_status") != "unknown":
            fails.append(f"seed_claims_staleness:{key}")

    if catalog.get("monitorable_count") != 0:
        fails.append("catalog_reports_monitorable_sources")
    for forbidden in (
        "live_coverage_claimed",
        "coverage_complete_claimed",
        "any_source_monitored",
    ):
        if catalog.get(forbidden) is not False:
            fails.append(f"forbidden_claim:{forbidden}")
    return fails
