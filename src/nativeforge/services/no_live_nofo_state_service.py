"""Sprint 350: honest no_live_nofo source state — empty but true identity preserved."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_no_live_nofo_state_v1"
SOURCE_INGESTION_STATE_NO_LIVE_NOFO = "no_live_nofo"


class NoLiveNofoStateError(ValueError):
    """Raised when no_live_nofo grant is mislabeled or holds foreign program data."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _seed_agency_label(source: dict[str, Any]) -> str:
    name = str(source.get("source_name") or "")
    if "—" in name:
        return name.split("—", 1)[0].strip()
    if " - " in name:
        return name.split(" - ", 1)[0].strip()
    return name.strip()


def _seed_program_label(source: dict[str, Any]) -> str:
    name = str(source.get("source_name") or "")
    if "—" in name:
        return name.split("—", 1)[-1].strip()
    if " - " in name:
        return name.split(" - ", 1)[-1].strip()
    return name.strip()


def build_no_live_nofo_grant(
    grant: dict[str, Any],
    source: dict[str, Any],
    *,
    diagnosis: str,
) -> dict[str, Any]:
    """Preserve catalog identity; empty eligibility; never substitute another NOFO."""
    agency = _seed_agency_label(source)
    program = _seed_program_label(source)
    catalog_number = str(grant.get("opportunity_number") or "")
    if catalog_number.startswith("EPA-") or catalog_number.startswith("SM-"):
        catalog_number = str(grant.get("grant_id") or "").replace("nf13-real-", "").upper()
        if not catalog_number.startswith("FED-"):
            catalog_number = f"FED-{catalog_number.split('-')[-1]}"

    updated = dict(grant)
    updated.update(
        {
            "opportunity_number": catalog_number,
            "opportunity_title": program or grant.get("opportunity_title"),
            "agency": agency or grant.get("agency"),
            "eligibility_text": "",
            "synopsis": (
                f"Federal grant program: {agency} — {program}. "
                "No posted NOFO on Grants.gov at ingest (no_live_nofo)."
            ),
            "tribal_eligible": False,
            "applicant_types_include_tribal": None,
            "tribal_set_aside": False,
            "tribal_priority_points": False,
            "eligibility_tags": [],
            "source_ingestion_state": SOURCE_INGESTION_STATE_NO_LIVE_NOFO,
            "no_live_nofo": True,
            "empty_honestly": True,
            "real_fetch": False,
            "fetch_mode": "no_live_nofo",
            "fixture": False,
            "search_live": True,
            "detail_live": False,
            "grants_gov_opportunity_id": None,
            "eligibility_reingest": True,
            "eligibility_reingest_diagnosis": diagnosis,
            "prior_eligibility_was_placeholder": str(
                grant.get("eligibility_text") or ""
            ).startswith("Open to eligible applicants"),
            "reingest_program_proxy": False,
            "source_url": source.get("source_url"),
            "never_synthesized": True,
            "honest_labeling": True,
        }
    )
    updated.pop("intended_program", None)
    return _json_safe(updated)


def assert_no_live_nofo_honest(grant: dict[str, Any]) -> None:
    if not grant.get("no_live_nofo"):
        return
    if grant.get("reingest_program_proxy"):
        raise NoLiveNofoStateError(
            f"grant {grant.get('grant_id')!r} is no_live_nofo but marked reingest_program_proxy"
        )
    if str(grant.get("eligibility_text") or "").strip():
        raise NoLiveNofoStateError(
            f"grant {grant.get('grant_id')!r} is no_live_nofo but has eligibility text"
        )
    opp = str(grant.get("opportunity_number") or "")
    if opp.startswith("EPA-OW") or opp.startswith("EPA-OLEM"):
        raise NoLiveNofoStateError(
            f"grant {grant.get('grant_id')!r} holds foreign EPA NOFO id under no_live_nofo"
        )


def build_no_live_nofo_state_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_ingestion_state": SOURCE_INGESTION_STATE_NO_LIVE_NOFO,
            "empty_honestly": True,
            "never_proxy_substitute": True,
            "preview_only": True,
        }
    )
