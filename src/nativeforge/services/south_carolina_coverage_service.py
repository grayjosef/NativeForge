"""South Carolina coverage candidates.

A responding homepage is not a grant listing and is not an enabled source.
Federal coverage for a South Carolina applicant is the broad Grants.gov
index, which is not limited to one state and is not a collector.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_south_carolina_coverage_v1"

SEED_ROW_ID = "nf-seed-2026-st-041"

# Hosts that answered HTTP 200 on 2026-09-28. None of these responses was a
# confirmed grant-listing document, so none is enabled.
CANDIDATE_HOSTS: tuple[dict[str, str], ...] = (
    {
        "source_id": "sc-candidate-ria",
        "name": "South Carolina Rural Infrastructure Authority",
        "url": "https://ria.sc.gov/",
        "source_class": "state",
        "program_area": "infrastructure",
    },
    {
        "source_id": "sc-candidate-commerce",
        "name": "South Carolina Department of Commerce",
        "url": "https://www.sccommerce.com/",
        "source_class": "state",
        "program_area": "economic_development",
    },
    {
        "source_id": "sc-candidate-housing",
        "name": "South Carolina State Housing Finance and Development Authority",
        "url": "https://www.schousing.com/",
        "source_class": "state",
        "program_area": "housing",
    },
    {
        "source_id": "sc-candidate-des",
        "name": "South Carolina Department of Environmental Services",
        "url": "https://des.sc.gov/",
        "source_class": "state",
        "program_area": "environment",
    },
    {
        "source_id": "sc-candidate-em",
        "name": "South Carolina Emergency Management Division",
        "url": "https://www.scemd.org/",
        "source_class": "state",
        "program_area": "emergency_management",
    },
    {
        "source_id": "sc-candidate-ccf",
        "name": "Coastal Community Foundation of South Carolina",
        "url": "https://www.ccfsc.org/",
        "source_class": "foundation",
        "program_area": "community_development",
    },
    {
        "source_id": "sc-candidate-duke",
        "name": "The Duke Endowment",
        "url": "https://www.dukeendowment.org/",
        "source_class": "foundation",
        "program_area": "health",
    },
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def south_carolina_coverage() -> dict[str, Any]:
    candidates = [
        {
            **host,
            "adapter_family": "html_listing",
            "backlog_class": "NEEDS_RESEARCH",
            "host_responded": True,
            "grant_listing_confirmed": False,
            "enabled": False,
            "authorized": False,
            "warrant_valid": False,
        }
        for host in CANDIDATE_HOSTS
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "seed_row_id": SEED_ROW_ID,
            "seed_url": "https://www.sc.gov",
            "seed_backlog_class": "NEEDS_RESEARCH",
            "seed_note": (
                "The seed points at the state homepage, not a grant listing."
            ),
            "federal_artery": "grants_gov_search2",
            "federal_artery_is_state_limited": False,
            "candidates": candidates,
            "configured": len(candidates),
            "enabled": 0,
            "active": 0,
            "ingested_opportunities": 0,
            "fabricated": False,
        }
    )
