"""Gate 163 robots preflight: URL derivation and activated-state warrant."""

from __future__ import annotations

import uuid
from urllib.parse import urlsplit

import pytest

from nativeforge.db.session import SessionLocal
from nativeforge.services.robots_verdict_service import derive_robots_verdict
from nativeforge.services.source_live_warrant_service import (
    PREFLIGHT_AUTHORITY_STATES,
    WARRANT_ROBOTS_PREFLIGHT,
    evaluate_live_request,
    warrant_invariant_failures,
)
from nativeforge.services.source_monitoring_approved_source_service import (
    load_registry_rows,
)
from tests import session_org_helper as soh

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
AUTHORIZED = "nf-seed-2026-api-grants-gov-search2"
ROBOTS_PATH = "/robots.txt"


def test_grants_gov_robots_url_is_derived_from_the_collection_authority() -> None:
    row = load_registry_rows()[AUTHORIZED]
    url = str(row["source_url"])
    host = (urlsplit(url).hostname or "").lower()
    assert host == "api.grants.gov"
    assert f"https://{host}{ROBOTS_PATH}" == "https://api.grants.gov/robots.txt"


def test_rfc9309_403_is_unavailable_not_a_publisher_disallow() -> None:
    verdict = derive_robots_verdict(
        status=403, body=b"", path="/v1/api/search2"
    )
    assert verdict["decision"] == "unavailable"
    assert not verdict.get("restricts_collection")


@pytest.fixture
def connection():
    soh.ensure_org(DEMO, "demo")
    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def test_robots_preflight_warrant_does_not_require_live_fetch_opt_in(
    connection,
) -> None:
    """Activated + signed decisions must suffice; opt-in resolves robots first."""
    row = load_registry_rows()[AUTHORIZED]
    robots_url = f"https://{(urlsplit(str(row['source_url'])).hostname or '').lower()}{ROBOTS_PATH}"
    decision = evaluate_live_request(
        warrant_kind=WARRANT_ROBOTS_PREFLIGHT,
        authorized_source_id=AUTHORIZED,
        request_url=robots_url,
        method="GET",
        connection=connection,
        organization_id=DEMO,
    )
    state = decision.get("source_authority_state")
    if state in PREFLIGHT_AUTHORITY_STATES:
        assert "live_fetch_is_not_opted_in" not in (
            decision.get("refusal_reasons") or []
        )
    assert decision.get("live_fetch_opt_in_required") is False
    if decision.get("permitted"):
        assert warrant_invariant_failures(decision) == []
