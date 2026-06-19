"""Sprint 228: operator workbench advisory service."""

from __future__ import annotations

from nativeforge.services.operator_workbench_advisory_service import (
    SCHEMA_VERSION,
    build_matching_readiness_advisory_preview,
    build_native_relevance_advisory_preview,
    build_operator_workbench_advisory_bundle,
    build_org_applicant_profile_advisory_preview,
)


def test_advisory_bundle_shape() -> None:
    bundle = build_operator_workbench_advisory_bundle()
    assert bundle["schema_version"] == SCHEMA_VERSION
    assert bundle["synthetic_fixtures_only"] is True
    assert bundle["no_scoring_logic_changes"] is True
    assert "intake_preview" in bundle
    assert "matching_readiness_preview" in bundle


def test_native_relevance_preview() -> None:
    preview = build_native_relevance_advisory_preview(limit=2)
    assert preview["preview_count"] == 2


def test_org_profile_preview() -> None:
    preview = build_org_applicant_profile_advisory_preview(limit=2)
    assert preview["preview_count"] == 2


def test_matching_readiness_preview_uses_canonical_fit_layer() -> None:
    preview = build_matching_readiness_advisory_preview(limit=1)
    assert preview["canonical_fit_layer"] == "eligibility_fit_assessment_*"
    assert preview["preview_count"] == 1
