"""HABEAS DATA — opportunity value intelligence V1."""

from __future__ import annotations

import hashlib
import uuid
from decimal import Decimal

import pytest
import sqlalchemy as sa

from nativeforge.repositories.canonical_opportunity_batch_repository import (
    NormalizedSourceObservation,
    persist_observations,
)
from nativeforge.services.canonical_intelligence_projection_service import (
    GRANTS_GOV_SOURCE,
    project_canonical_opportunity,
)
from nativeforge.services.opportunity_value_intelligence_service import (
    METHODOLOGY_VERSION,
    VALUE_KNOWN,
    VALUE_UNKNOWN,
    _select_monetary_value,
    compute_active_opportunity_value_aggregate,
    invalidate_public_cache,
    public_aggregate_view,
)
from nativeforge.services.source_adapter_contract_service import identity_for_normalized

ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")


@pytest.fixture
def db():
    from nativeforge.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _seed_posted(
    connection: sa.engine.Connection,
    *,
    key: str,
    funding_min: str | None = None,
    funding_max: str | None = None,
    lifecycle: str = "posted",
) -> str:
    fields = {
        "doc_type": "synopsis",
        "status": "posted",
        "title": f"Opp {key}",
        "funder_agency_name": "EPA",
        "close_date": "2026-12-01",
        "opportunity_number": f"TST-{key}",
        "source_record_id": f"TST-{key}",
    }
    if funding_min is not None:
        fields["funding_amount_min"] = funding_min
    if funding_max is not None:
        fields["funding_amount_max"] = funding_max
    normalized = {
        "schema_version": "test",
        "parser_version": "test",
        "parser_name": "test",
        "adapter_key": "grants_gov_detail_v1",
        "parseable": True,
        "fields": fields,
        "fields_absent": [],
        "fields_not_supported": [],
        "content_fingerprint": "fp-" + key,
        "source_record_id": fields["source_record_id"],
        "lifecycle_state": lifecycle,
        "provenance_fields_present": sorted(fields),
        "provenance_fields_missing": [],
    }
    identity = identity_for_normalized(normalized, source_id=GRANTS_GOV_SOURCE)
    payload_sha = hashlib.sha256(f"payload-{key}".encode()).hexdigest()
    persist_observations(
        connection=connection,
        observations=[
            NormalizedSourceObservation(
                source_id=GRANTS_GOV_SOURCE,
                normalized=normalized,
                raw_payload_sha256=payload_sha,
                identity=identity,
                raw_payload_attempt_id=hashlib.sha256(
                    f"attempt-{key}".encode()
                ).hexdigest(),
                source_authority_host="api.grants.gov",
            )
        ],
    )
    row = connection.execute(
        sa.text(
            "SELECT canonical_id FROM nf_opportunity_source_observations "
            "WHERE raw_payload_sha256 = :sha LIMIT 1"
        ),
        {"sha": payload_sha},
    ).fetchone()
    cid = str(row[0])
    project_canonical_opportunity(connection, canonical_id=cid)
    connection.execute(
        sa.text(
            "UPDATE nf_canonical_opportunities SET lifecycle_state = :lc WHERE canonical_id = :cid"
        ),
        {"lc": lifecycle, "cid": cid},
    )
    return cid


def test_unknown_not_treated_as_zero():
    sel = _select_monetary_value(
        min_raw=None,
        max_raw=None,
        has_field_conflicts=False,
        min_conflict=None,
        max_conflict=None,
    )
    assert sel["value_status"] == VALUE_UNKNOWN
    assert sel["selected_amount"] is None


def test_ceiling_only_is_known_but_stays_out_of_the_total():
    """The contract changed on 2026-10-03, in both directions.

    A ceiling alone used to be UNKNOWN. It is monetary intelligence - "up to
    $5,000,000" is decision-useful - and reporting it as UNKNOWN hid amounts
    the publisher had actually announced.

    What did NOT change is the part worth keeping: it carries the ceiling
    semantic rather than being promoted to a point estimate, and the
    aggregate keeps it out of the summed program dollars. A per-award maximum
    is a different kind of number from program funding and adding them would
    overstate money nobody announced.
    """
    sel = _select_monetary_value(
        min_raw=None,
        max_raw="5000000",
        has_field_conflicts=False,
        min_conflict=None,
        max_conflict=None,
    )
    assert sel["value_status"] == VALUE_KNOWN
    assert sel["semantic"] == "award_ceiling_excluded_from_aggregate"
    assert sel["selected_amount"] is not None


def test_equal_min_max_point_estimate():
    sel = _select_monetary_value(
        min_raw="1000000",
        max_raw="1000000",
        has_field_conflicts=False,
        min_conflict=None,
        max_conflict=None,
    )
    assert sel["value_status"] == VALUE_KNOWN
    assert sel["selected_amount"] == Decimal("1000000")


def test_aggregate_exact_with_fixtures(db):
    invalidate_public_cache()
    conn = db.connection()
    before = compute_active_opportunity_value_aggregate(conn, use_cache=False)
    _seed_posted(conn, key="a", funding_min="1000000", funding_max="1000000")
    _seed_posted(conn, key="b", funding_min="500000", funding_max="500000")
    _seed_posted(conn, key="c", funding_max="9000000")  # ceiling only
    _seed_posted(conn, key="d", lifecycle="closed", funding_min="999", funding_max="999")
    agg = compute_active_opportunity_value_aggregate(conn, use_cache=False)
    assert agg["methodology_version"] == METHODOLOGY_VERSION
    assert agg["active_opportunity_count"] == before["active_opportunity_count"] + 3
    # All three active fixtures now count as monetary intelligence: two point
    # values and the ceiling-only record "c". Before 2026-10-03 the ceiling
    # was UNKNOWN, which hid an amount the publisher had announced.
    assert agg["known_value_count"] == before["known_value_count"] + 3
    assert agg["unknown_value_count"] == before["unknown_value_count"] + 0

    # The assertion this test really exists for, and the one that did NOT
    # change: the $9,000,000 ceiling must not reach the program total. Only
    # the two point values do. If a ceiling ever starts summing, the total
    # becomes a number nobody published.
    delta = Decimal(agg["active_known_value_total_usd"] or "0") - Decimal(
        before["active_known_value_total_usd"] or "0"
    )
    assert delta == Decimal("1500000.00")


def test_expired_closed_excluded(db):
    invalidate_public_cache()
    conn = db.connection()
    before = compute_active_opportunity_value_aggregate(conn, use_cache=False)
    _seed_posted(conn, key="closed1", funding_min="100", funding_max="100", lifecycle="closed")
    _seed_posted(conn, key="open1", funding_min="250000", funding_max="250000")
    agg = compute_active_opportunity_value_aggregate(conn, use_cache=False)
    assert agg["active_opportunity_count"] == before["active_opportunity_count"] + 1
    assert agg["known_value_count"] == before["known_value_count"] + 1
    assert Decimal(agg["active_known_value_total_usd"] or "0") == Decimal(
        before["active_known_value_total_usd"] or "0"
    ) + Decimal("250000")


def test_public_view_omits_tenant_fields(db):
    invalidate_public_cache()
    conn = db.connection()
    agg = compute_active_opportunity_value_aggregate(conn, use_cache=False)
    pub = public_aggregate_view(agg)
    assert "opportunities" not in pub
    assert pub.get("habeas_data")


def test_duplicate_observation_idempotent(db):
    invalidate_public_cache()
    conn = db.connection()
    before = compute_active_opportunity_value_aggregate(conn, use_cache=False)
    _seed_posted(conn, key="dup-once", funding_min="10000", funding_max="10000")
    mid = compute_active_opportunity_value_aggregate(conn, use_cache=False)
    _seed_posted(conn, key="dup-once", funding_min="10000", funding_max="10000")
    after = compute_active_opportunity_value_aggregate(conn, use_cache=False)
    assert mid["active_opportunity_count"] == before["active_opportunity_count"] + 1
    assert after["active_opportunity_count"] == mid["active_opportunity_count"]


def test_conflicting_values_excluded(db):
    invalidate_public_cache()
    conn = db.connection()
    cid = _seed_posted(conn, key="conf", funding_min="100", funding_max="100")
    conn.execute(
        sa.text(
            "UPDATE nf_canonical_opportunities SET has_field_conflicts = 1 WHERE canonical_id = :cid"
        ),
        {"cid": cid},
    )
    agg = compute_active_opportunity_value_aggregate(conn, use_cache=False)
    assert agg["conflicting_value_count"] >= 1


def test_public_api_route():
    from fastapi.testclient import TestClient

    from nativeforge.main import create_app

    c = TestClient(create_app(), raise_server_exceptions=False)
    r = c.get("/api/public/opportunity-value/active")
    assert r.status_code == 200
    body = r.json()
    assert body["methodology_version"] == METHODOLOGY_VERSION
