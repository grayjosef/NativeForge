"""Deterministic normalization of Grants.gov-shaped local payloads (fixtures only)."""

from __future__ import annotations

from typing import Any

from nativeforge.domain.enums import GrantAwardType, OpportunitySourceType


def grants_gov_like_to_fixture_row(raw: dict[str, Any]) -> dict[str, Any]:
    """
    Map common Grants.gov export keys onto static connector fixture expectations.

    No network calls — intended for Sprint 26 corpus + offline tests.
    """
    out = dict(raw)
    title = out.get("opportunity_title") or out.get("title") or out.get("Title")
    if title is not None:
        out["opportunity_title"] = str(title).strip()

    agency = out.get("agency") or out.get("agencyName") or out.get("Agency")
    if agency is not None:
        out["agency"] = str(agency).strip()

    ost = out.get("opportunity_source_type")
    if ost is None:
        cat = str(out.get("FundingInstrumentType") or "").lower()
        if "grant" in cat:
            out.setdefault("award_type", GrantAwardType.grant.value)
        out.setdefault("opportunity_source_type", OpportunitySourceType.federal.value)

    num = out.get("opportunity_number") or out.get("OpportunityNumber")
    if num is not None:
        out.setdefault("opportunity_number", str(num).strip())

    url = out.get("source_url") or out.get("OpportunityURL") or out.get("url")
    if url is not None:
        out.setdefault("source_url", str(url).strip())

    return out
