"""South Carolina funding listing research (no network; official URLs only).

HTTP 200 on a homepage does not prove grant inventory. Each host is classified
from repository facts and named listing endpoints where the seed catalog records
them; otherwise RESEARCH_REQUIRED / NO_USABLE_LISTING.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_ingestion_seed_loader_service import (
    load_source_seed_rows,
)

SCHEMA_VERSION = "nf_sc_grant_listing_research_v1"

# Named in product brief; matched against seed catalog names/URLs when present.
SC_HOST_HINTS: tuple[tuple[str, str], ...] = (
    ("Rural Infrastructure Authority", "scira"),
    ("Commerce", "commerce.sc.gov"),
    ("State Housing", "schousing.com"),
    ("Environmental Services", "des.sc.gov"),
    ("Emergency Management", "scemd.org"),
    ("Coastal Community Foundation", "coastalcommunityfoundation.org"),
    ("Duke Endowment", "dukeendowment.org"),
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _match_seed(keyword: str, hint: str) -> dict[str, Any] | None:
    key = keyword.lower()
    hint_l = hint.lower()
    for row in load_source_seed_rows():
        name = str(row.get("source_name") or "").lower()
        url = str(row.get("source_url") or "").lower()
        if key in name or hint_l in url or hint_l in name:
            return row
    return None


def build_south_carolina_listing_research() -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    for label, hint in SC_HOST_HINTS:
        row = _match_seed(label, hint)
        if row is None:
            findings.append(
                {
                    "label": label,
                    "listing_endpoint": None,
                    "source_type": "UNKNOWN",
                    "structured": False,
                    "expected_yield": "UNKNOWN",
                    "access_posture": "UNKNOWN",
                    "terms_posture": "UNKNOWN",
                    "adapter_status": "none_in_catalog",
                    "authorization_requirement": "human_review_required_if_activated",
                    "classification": "NO_USABLE_LISTING",
                    "notes": "no_matching_seed_row_in_NF_SOURCE_SEED_2026",
                }
            )
            continue
        url = str(row.get("source_url") or "").strip()
        adapter = str(row.get("adapter_key") or "")
        posture = str(row.get("access_posture_hint") or "UNKNOWN")
        structured = adapter in (
            "grants_gov_search2",
            "grants_gov_federal",
            "federal_register_documents_json",
        )
        classification = "RESEARCH_REQUIRED"
        if not url.startswith("https://"):
            classification = "NO_USABLE_LISTING"
        elif adapter == "state_portal_generic" and url.rstrip("/").endswith("sc.gov"):
            classification = "RESEARCH_REQUIRED"
            url = url  # homepage only — not a listing endpoint
        findings.append(
            {
                "label": label,
                "seed_id": row.get("seed_id"),
                "listing_endpoint": url,
                "source_type": row.get("source_type"),
                "structured": structured,
                "expected_yield": "UNKNOWN",
                "access_posture": posture,
                "terms_posture": "UNKNOWN",
                "adapter_status": adapter or "UNKNOWN",
                "authorization_requirement": "signed_decisions_required",
                "classification": classification,
                "notes": (
                    "catalog_url_may_be_homepage_not_grant_list;"
                    "find_program_grants_or_opportunities_path_before_activation"
                ),
            }
        )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "findings": findings,
            "south_carolina_seed_hits": sum(
                1 for f in findings if f.get("seed_id")
            ),
        }
    )
