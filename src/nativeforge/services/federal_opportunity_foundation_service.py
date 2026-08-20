"""Federal opportunity foundation for SC Native/tribal customer workflows.

Funding-source geography (federal) must coexist with SC org geography.
Does not claim live Grants.gov ingest.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.opportunity_engine_contract_service import (
    durable_opportunity_invariant_failures,
    normalize_to_durable_opportunity,
)
from nativeforge.services.sc_monday_curated_pack_service import (
    grants_from_pack,
    load_sc_curated_opportunity_pack,
)

SCHEMA_VERSION = "nf_federal_opportunity_foundation_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def enrich_federal_opportunity_for_sc_customer(row: dict[str, Any]) -> dict[str, Any]:
    """Harden federal fields while preserving SC customer relevance handoff."""
    durable = normalize_to_durable_opportunity(row)
    if durable.get("source_layer") != "federal":
        raise ValueError(
            "enrich_federal_opportunity_for_sc_customer requires federal layer"
        )

    durable.update(
        {
            "foundation_schema_version": SCHEMA_VERSION,
            "federal_agency": durable.get("agency")
            or durable.get("source_name")
            or "unknown_agency",
            "assistance_listing_or_opportunity_number": (
                durable.get("assistance_listing")
                or durable.get("cfda")
                or durable.get("opportunity_number")
                or durable.get("funding_opportunity_number")
                or None
            ),
            "tribal_eligibility_language": (
                durable.get("native_tribal_eligibility_evidence")
                or durable.get("eligibility_summary")
                or "needs_confirmation"
            ),
            "sc_relevance_explanation": durable.get("sc_relevance_explanation")
            or "Federal opportunity curated for SC Native/tribal customer relevance",
            "organization_fit_handoff": {
                "org_geography": "south_carolina",
                "funding_source_geography": "federal",
                "org_geo_must_not_filter_funding_geo": True,
                "eligibility_handoff_state": durable.get("eligibility_handoff_state"),
                "needs_human_review": True,
            },
            "assistance_listing_status": (
                "known"
                if (
                    durable.get("assistance_listing")
                    or durable.get("cfda")
                    or durable.get("opportunity_number")
                )
                else "missing"
            ),
        }
    )
    if durable["assistance_listing_status"] == "missing":
        missing = list(durable.get("missing_fields") or [])
        if "assistance_listing_or_opportunity_number" not in missing:
            missing.append("assistance_listing_or_opportunity_number")
        durable["missing_fields"] = missing
    return _json_safe(durable)


def build_federal_foundation_pack_for_sc() -> dict[str, Any]:
    pack = load_sc_curated_opportunity_pack()
    grants = [
        g
        for g in grants_from_pack(pack)
        if g.get("funding_geography") == "federal" or g.get("source_layer") == "federal"
    ]
    records = [enrich_federal_opportunity_for_sc_customer(g) for g in grants]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "title": "Federal opportunity foundation for SC customers",
            "live_ingest_claimed": False,
            "count": len(records),
            "opportunities": records,
            "org_geography_note": (
                "Organization geography is South Carolina; funding geography is federal. "
                "Do not filter federal opportunities by org state."
            ),
        }
    )


def federal_foundation_invariant_failures(pack: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if pack.get("live_ingest_claimed") is True:
        fails.append("live_ingest_claimed")
    opps = pack.get("opportunities") or []
    if len(opps) < 1:
        fails.append("no_federal_opportunities")
    for o in opps:
        fails.extend(durable_opportunity_invariant_failures(o))
        if o.get("source_layer") != "federal":
            fails.append(f"non_federal:{o.get('opportunity_id')}")
        fit = o.get("organization_fit_handoff") or {}
        if fit.get("org_geo_must_not_filter_funding_geo") is not True:
            fails.append("org_geo_filter_risk")
        if fit.get("funding_source_geography") != "federal":
            fails.append("funding_geo")
    return fails
