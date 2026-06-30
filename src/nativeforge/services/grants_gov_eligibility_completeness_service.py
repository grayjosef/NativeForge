"""Grants.gov eligibility completeness: forecast merge + empty-on-success backfill."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.grants_gov_eligibility_parser_service import (
    parse_grants_gov_opportunity_eligibility,
)
from nativeforge.services.grants_gov_search_api_adapter_service import (
    fetch_grants_gov_opportunity_detail,
)

SCHEMA_VERSION = "nf_grants_gov_eligibility_completeness_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def apply_opportunity_eligibility_to_grant(
    grant: dict[str, Any],
    parsed: dict[str, Any],
) -> dict[str, Any]:
    """Merge parsed fetchOpportunity eligibility onto a grant row."""
    out = dict(grant)
    elig_text = str(parsed.get("eligibility_text") or "").strip()
    if elig_text:
        out["eligibility_text"] = elig_text
    if parsed.get("eligibility_text_source"):
        out["eligibility_text_source"] = parsed["eligibility_text_source"]
    if parsed.get("eligibility_provenance"):
        out["eligibility_provenance"] = parsed["eligibility_provenance"]
    if parsed.get("grants_gov_attachment_inventory") is not None:
        out["grants_gov_attachment_inventory"] = parsed["grants_gov_attachment_inventory"]
    if parsed.get("grants_gov_doc_type"):
        out["grants_gov_doc_type"] = parsed["grants_gov_doc_type"]
    if parsed.get("applicant_type_ids"):
        out["applicant_type_ids"] = parsed["applicant_type_ids"]
    if parsed.get("applicant_types_json"):
        out["applicant_types_json"] = parsed["applicant_types_json"]
    if parsed.get("tribal_eligible") is not None:
        out["tribal_eligible"] = parsed["tribal_eligible"]
        if out.get("applicant_types_include_tribal") is None:
            out["applicant_types_include_tribal"] = parsed["tribal_eligible"]
    if parsed.get("synopsis") and not str(out.get("synopsis") or "").strip():
        out["synopsis"] = parsed["synopsis"]
    if parsed.get("agency") and not str(out.get("agency") or "").strip():
        out["agency"] = parsed["agency"]
    out["eligibility_completeness_applied"] = True
    return _json_safe(out)


def complete_grant_from_fetch_opportunity_detail(
    grant: dict[str, Any],
    detail: dict[str, Any],
) -> dict[str, Any]:
    parsed = parse_grants_gov_opportunity_eligibility(detail)
    return apply_opportunity_eligibility_to_grant(grant, parsed)


def grant_needs_eligibility_completeness(grant: dict[str, Any]) -> bool:
    """True when corpus row is empty but has a Grants.gov opportunity id."""
    if str(grant.get("eligibility_text") or "").strip():
        return False
    return bool(grant.get("grants_gov_opportunity_id"))


def maybe_complete_grant_eligibility(
    grant: dict[str, Any],
    *,
    detail: dict[str, Any] | None = None,
    allow_live_fetch: bool = False,
) -> dict[str, Any]:
    """
    Backfill empty eligibility_text from stored detail or live fetchOpportunity.

    Honest: only fills when API returns substantive eligibility fields.
    """
    if not grant_needs_eligibility_completeness(grant):
        return grant
    if detail is not None:
        return complete_grant_from_fetch_opportunity_detail(grant, detail)
    if not allow_live_fetch:
        return grant
    opp_id = grant.get("grants_gov_opportunity_id")
    if not opp_id:
        return grant
    fetched, live = fetch_grants_gov_opportunity_detail(opp_id)
    if not live or not fetched:
        return grant
    completed = complete_grant_from_fetch_opportunity_detail(grant, fetched)
    if str(completed.get("eligibility_text") or "").strip():
        completed["eligibility_completeness_live_fetch"] = True
    return completed


def enrich_grant_with_grants_gov_completeness(
    grant: dict[str, Any],
    *,
    allow_live_fetch: bool = False,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return maybe_complete_grant_eligibility(
        grant,
        detail=detail,
        allow_live_fetch=allow_live_fetch,
    )
