"""Sprint 017: NM missing evidence categories in rollup."""

from __future__ import annotations

from nativeforge.services.nm_operator_surfacing_report_service import (
    build_nm_operator_surfacing_report,
)

_G = [
    {
        "grant_id": "os-nm-t017",
        "opportunity_title": "Tribal Discretionary Grant",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def test_nm_missing_evidence_categories_are_dict() -> None:
    cats = build_nm_operator_surfacing_report(grants=_G)["rollup"][
        "missing_evidence_categories"
    ]
    assert isinstance(cats, dict)
