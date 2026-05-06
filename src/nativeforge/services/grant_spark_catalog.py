"""Deterministic demo Grant Spark catalog (12 seeded opportunities).

Aligned with research/domain/grant-lifecycle.md Stage 3 — hand-curated demo Sparks.
IDs are stable per organization via :func:`demo_spark_primary_key`.
"""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any

from nativeforge.domain.enums import GrantAwardType, GrantSparkSource

# Stable UUID namespace for demo Spark primary keys (per org + source + source_id).
_DEMO_NS = uuid.uuid5(
    uuid.NAMESPACE_URL, "https://nativeforge.dev/nf/demo-grant-sparks/v1"
)


def demo_spark_primary_key(
    org_id: uuid.UUID,
    *,
    source: str,
    source_id: str,
) -> uuid.UUID:
    return uuid.uuid5(_DEMO_NS, f"{org_id}:{source}:{source_id}")


def _dt(y: int, m: int, d: int, hh: int = 23, mm: int = 59) -> datetime:
    return datetime(y, m, d, hh, mm, tzinfo=UTC)


# Twelve deterministic catalog rows (metadata only — no live Grants.gov keys).
DEMO_GRANT_SPARK_CATALOG: list[dict[str, Any]] = [
    {
        "source": GrantSparkSource.bia.value,
        "source_id": "NF-DEMO-BIA-001",
        "agency": "Bureau of Indian Affairs",
        "sub_agency": "Office of Trust Services",
        "program_name": "Tribal Climate Resilience Annual Awards",
        "opportunity_title": (
            "Tribal Climate Adaptation — Wetland and Floodplain Restoration"
        ),
        "opportunity_number": "BIA-TCR-2027-01",
        "cfda_assistance_listing": "15.032",
        "url": "https://example.gov/nf-demo/bia-tcr-001",
        "funding_floor": Decimal("75000"),
        "funding_ceiling": Decimal("500000"),
        "award_type": GrantAwardType.grant.value,
        "match_required": True,
        "match_percent": Decimal("20"),
        "indirect_cost_allowable": True,
        "posted_date": date(2026, 3, 1),
        "application_deadline": _dt(2027, 4, 30),
        "tribal_eligible": True,
        "eligibility_tags": [
            "tribal_eligible",
            "federally_recognized_only",
            "climate_resilience",
        ],
    },
    {
        "source": GrantSparkSource.ihs.value,
        "source_id": "NF-DEMO-IHS-002",
        "agency": "Indian Health Service",
        "sub_agency": None,
        "program_name": "Sanitation Facilities Construction",
        "opportunity_title": "Sanitation Facilities — Planning and Design",
        "opportunity_number": "IHS-SFC-2027-05",
        "cfda_assistance_listing": "93.162",
        "award_type": GrantAwardType.grant.value,
        "funding_floor": Decimal("100000"),
        "funding_ceiling": Decimal("2000000"),
        "match_required": False,
        "posted_date": date(2026, 4, 10),
        "application_deadline": _dt(2027, 6, 15),
        "tribal_eligible": True,
        "eligibility_tags": ["tribal_eligible", "ihs_service_population", "health"],
    },
    {
        "source": GrantSparkSource.ana.value,
        "source_id": "NF-DEMO-ANA-003",
        "agency": "Administration for Native Americans",
        "program_name": "Native Language Preservation",
        "opportunity_title": "Native Language Preservation and Maintenance — Elder-led",
        "opportunity_number": "ANA-NLP-2027-02",
        "cfda_assistance_listing": "93.612",
        "award_type": GrantAwardType.competitive.value,
        "funding_ceiling": Decimal("450000"),
        "match_required": False,
        "posted_date": date(2026, 5, 1),
        "application_deadline": _dt(2027, 8, 1),
        "tribal_eligible": True,
        "eligibility_tags": ["tribal_eligible", "language_preservation", "culture"],
    },
    {
        "source": GrantSparkSource.usda.value,
        "source_id": "NF-DEMO-USDA-004",
        "agency": "USDA Rural Development",
        "program_name": "Community Facilities",
        "opportunity_title": (
            "Community Facilities Direct Loan & Grant — Tribal Priority"
        ),
        "opportunity_number": "RD-CF-TRIBAL-2027",
        "award_type": GrantAwardType.grant.value,
        "funding_floor": Decimal("10000"),
        "funding_ceiling": Decimal("40000000"),
        "match_required": True,
        "match_percent": Decimal("5"),
        "match_waiver_available": True,
        "posted_date": date(2026, 2, 15),
        "application_deadline": _dt(2027, 9, 30),
        "tribal_eligible": True,
        "eligibility_tags": ["tribal_eligible", "rural", "community_facilities"],
    },
    {
        "source": GrantSparkSource.hud.value,
        "source_id": "NF-DEMO-HUD-005",
        "agency": "HUD",
        "sub_agency": "Office of Native American Programs",
        "program_name": "Indian Housing Block Grant",
        "opportunity_title": "IHBG Competitive — Housing Rehabilitation",
        "opportunity_number": "HUD-IHBG-C-2027",
        "award_type": GrantAwardType.formula.value,
        "posted_date": date(2026, 6, 1),
        "application_deadline": _dt(2027, 11, 15),
        "tribal_eligible": True,
        "eligibility_tags": ["tribal_eligible", "housing", "ihbg"],
    },
    {
        "source": GrantSparkSource.epa.value,
        "source_id": "NF-DEMO-EPA-006",
        "agency": "EPA",
        "program_name": "General Assistance Program",
        "opportunity_title": "GAP — Tribal Environmental Program Capacity",
        "opportunity_number": "EPA-GAP-TRIBAL-2027",
        "award_type": GrantAwardType.grant.value,
        "funding_ceiling": Decimal("350000"),
        "posted_date": date(2026, 7, 20),
        "application_deadline": _dt(2027, 5, 20),
        "tribal_eligible": True,
        "eligibility_tags": ["tribal_eligible", "environment", "capacity_building"],
    },
    {
        "source": GrantSparkSource.doe.value,
        "source_id": "NF-DEMO-DOE-007",
        "agency": "Department of Energy",
        "program_name": "Tribal Energy Loan Guarantee",
        "opportunity_title": "Energy Efficiency — Tribal Facilities Retrofit",
        "opportunity_number": "DOE-TE-2027-EE",
        "award_type": GrantAwardType.grant.value,
        "funding_ceiling": Decimal("2500000"),
        "match_required": True,
        "match_percent": Decimal("50"),
        "posted_date": date(2026, 8, 5),
        "application_deadline": _dt(2027, 7, 31),
        "tribal_eligible": True,
        "eligibility_tags": ["tribal_eligible", "energy", "facilities"],
    },
    {
        "source": GrantSparkSource.ntia.value,
        "source_id": "NF-DEMO-NTIA-008",
        "agency": "NTIA",
        "program_name": "Tribal Broadband Connectivity",
        "opportunity_title": "Middle Mile Infrastructure — Tribal Lands",
        "opportunity_number": "NTIA-TBC-2027-MM",
        "award_type": GrantAwardType.grant.value,
        "funding_floor": Decimal("500000"),
        "match_required": False,
        "posted_date": date(2026, 9, 1),
        "application_deadline": _dt(2027, 12, 1),
        "tribal_eligible": True,
        "eligibility_tags": ["tribal_eligible", "broadband", "infrastructure"],
    },
    {
        "source": GrantSparkSource.grants_gov.value,
        "source_id": "NF-DEMO-GG-009",
        "agency": "DOI",
        "program_name": "Consolidated Demo Notice",
        "opportunity_title": (
            "Demo Competitive Notice — Multi-eligibility Review Template"
        ),
        "opportunity_number": "GG-DEMO-2027-OPEN",
        "url": "https://example.gov/nf-demo/grants-gov-placeholder",
        "award_type": GrantAwardType.competitive.value,
        "expected_awards": 25,
        "posted_date": date(2026, 1, 10),
        "application_deadline": _dt(2027, 3, 15),
        "tribal_eligible": True,
        "eligibility_tags": [
            "tribal_eligible",
            "multi_eligibility_review",
            "demo_seed",
        ],
    },
    {
        "source": GrantSparkSource.ctas.value,
        "source_id": "NF-DEMO-CTAS-010",
        "agency": "DOJ",
        "program_name": "Coordinated Tribal Assistance Solicitation",
        "opportunity_title": "CTAS — Public Safety and Community Wellness",
        "opportunity_number": "CTAS-2027-PS",
        "award_type": GrantAwardType.competitive.value,
        "funding_ceiling": Decimal("900000"),
        "posted_date": date(2026, 10, 1),
        "application_deadline": _dt(2027, 2, 28),
        "tribal_eligible": True,
        "eligibility_tags": ["tribal_eligible", "justice", "public_safety"],
    },
    {
        "source": GrantSparkSource.sam_assistance.value,
        "source_id": "NF-DEMO-SAM-011",
        "agency": "HHS",
        "program_name": "Formula Assistance Listing (demo)",
        "opportunity_title": "Formula Block — Planning Allocation (demo)",
        "opportunity_number": "SAM-FORM-DEMO-011",
        "award_type": GrantAwardType.formula.value,
        "match_required": False,
        "posted_date": date(2026, 4, 1),
        "application_deadline": None,
        "tribal_eligible": True,
        "eligibility_tags": ["tribal_eligible", "formula", "rolling_window"],
    },
    {
        "source": GrantSparkSource.manual.value,
        "source_id": "NF-DEMO-MAN-012",
        "agency": "Tribal College Board (demo publisher)",
        "program_name": "STEM Pathways",
        "opportunity_title": "Tribal College STEM Equipment — Demo Entry",
        "opportunity_number": "MANUAL-DEMO-012",
        "award_type": GrantAwardType.grant.value,
        "funding_ceiling": Decimal("150000"),
        "posted_date": date(2026, 11, 20),
        "application_deadline": _dt(2027, 10, 15),
        "tribal_eligible": True,
        "eligibility_tags": [
            "tribal_eligible",
            "tribal_college",
            "stem",
            "manual_seed",
        ],
    },
]
