"""Sprint 205: synthetic demo fixtures."""

from __future__ import annotations

from nativeforge.services.org_applicant_profile_demo_fixture_service import (
    SCHEMA_VERSION,
    build_demo_fixture_catalog,
    load_org_applicant_profile_fixtures,
)


def test_load_fixtures() -> None:
    fixtures = load_org_applicant_profile_fixtures()
    assert len(fixtures) >= 5
    keys = {f["fixture_key"] for f in fixtures}
    assert "oap_demo_tribal_government" in keys


def test_build_catalog() -> None:
    catalog = build_demo_fixture_catalog()
    assert catalog["schema_version"] == SCHEMA_VERSION
    assert catalog["synthetic_only"] is True
