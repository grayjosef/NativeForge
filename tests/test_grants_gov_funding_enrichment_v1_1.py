"""OVI V1.1 — Grants.gov synopsis funding enrichment."""

from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from pathlib import Path

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
from nativeforge.services.grants_gov_active_funding_enrichment_service import (
    enrich_one_active_opportunity,
    run_bounded_active_funding_enrichment,
)
from nativeforge.services.grants_gov_synopsis_funding_service import (
    map_synopsis_funding_to_canonical,
)
from nativeforge.services.opportunity_value_intelligence_service import (
    compute_active_opportunity_value_aggregate,
    invalidate_public_cache,
)
from nativeforge.services.source_adapter_contract_service import identity_for_normalized

FIXTURE_DETAIL = Path(
    "fixtures/source_ingestion/grants_gov_fetch_opportunity_362648.json"
)


@pytest.fixture
def db():
    from nativeforge.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _seed_search2_only(conn: sa.engine.Connection, *, key: str, grants_id: str) -> str:
    fields = {
        "doc_type": "synopsis",
        "status": "posted",
        "title": f"Opp {key}",
        "funder_agency_name": "BIA",
        "close_date": "2026-12-01",
        "opportunity_number": f"TST-{key}",
        "source_record_id": grants_id,
    }
    normalized = {
        "schema_version": "test",
        "parser_version": "test",
        "parser_name": "test",
        "adapter_key": "grants_gov_search2",
        "parseable": True,
        "fields": fields,
        "fields_absent": [],
        "fields_not_supported": ["funding_amount_min", "funding_amount_max"],
        "content_fingerprint": "fp-" + key,
        "source_record_id": grants_id,
        "lifecycle_state": "posted",
        "provenance_fields_present": sorted(fields),
        "provenance_fields_missing": [],
    }
    identity = identity_for_normalized(normalized, source_id=GRANTS_GOV_SOURCE)
    payload_sha = hashlib.sha256(f"payload-{key}".encode()).hexdigest()
    persist_observations(
        connection=conn,
        observations=[
            NormalizedSourceObservation(
                source_id=GRANTS_GOV_SOURCE,
                normalized=normalized,
                raw_payload_sha256=payload_sha,
                identity=identity,
                raw_payload_attempt_id=hashlib.sha256(f"att-{key}".encode()).hexdigest(),
                source_authority_host="api.grants.gov",
            )
        ],
    )
    row = conn.execute(
        sa.text(
            "SELECT canonical_id FROM nf_opportunity_source_observations "
            "WHERE raw_payload_sha256 = :sha LIMIT 1"
        ),
        {"sha": payload_sha},
    ).fetchone()
    cid = str(row[0])
    project_canonical_opportunity(conn, canonical_id=cid)
    return cid


def test_program_total_from_estimated_funding():
    m = map_synopsis_funding_to_canonical(
        {"estimatedFunding": "6800000", "awardCeiling": "450000", "awardFloor": "10000"}
    )
    assert m["funding_semantic"] == "PROGRAM_TOTAL_POINT"
    assert m["funding_amount_min"] == m["funding_amount_max"] == "6800000"


def test_ceiling_alone_does_not_populate_canonical():
    m = map_synopsis_funding_to_canonical({"awardCeiling": "5000000"})
    assert m["funding_semantic"] == "NONE"
    assert m["funding_amount_min"] is None


def test_floor_ceiling_range():
    m = map_synopsis_funding_to_canonical(
        {"awardFloor": "10000", "awardCeiling": "450000"}
    )
    assert m["funding_semantic"] == "AWARD_FLOOR_CEILING_RANGE"
    assert m["funding_amount_min"] == "10000"
    assert m["funding_amount_max"] == "450000"


def test_detail_enrichment_idempotent(db):
    invalidate_public_cache()
    conn = db.connection()
    detail = json.loads(FIXTURE_DETAIL.read_text())["data"]
    grants_id = str(detail["id"])

    def mock_post(url: str, body: dict) -> dict:
        if "fetchOpportunity" in url:
            return json.loads(FIXTURE_DETAIL.read_text())
        raise AssertionError(url)

    cid = _seed_search2_only(conn, key="tedc", grants_id=grants_id)
    row = {
        "canonical_id": cid,
        "source_record_id": grants_id,
        "opportunity_number": detail["opportunityNumber"],
        "doc_type": "synopsis",
        "lifecycle_state": "posted",
    }
    before = compute_active_opportunity_value_aggregate(conn, use_cache=False)
    r1 = enrich_one_active_opportunity(conn, row=row, http_post=mock_post)
    assert r1["observation_persisted"]
    mid = compute_active_opportunity_value_aggregate(conn, use_cache=False)
    r2 = enrich_one_active_opportunity(conn, row=row, http_post=mock_post)
    after = compute_active_opportunity_value_aggregate(conn, use_cache=False)
    assert mid["known_value_count"] >= before["known_value_count"] + 1
    assert after["known_value_count"] == mid["known_value_count"]
    delta = Decimal(after["active_known_value_total_usd"] or "0") - Decimal(
        before["active_known_value_total_usd"] or "0"
    )
    assert delta >= Decimal("6800000")
    assert r2["observation_persisted"]


def test_enrichment_run_bounded(db):
    invalidate_public_cache()
    conn = db.connection()
    stats = run_bounded_active_funding_enrichment(conn, limit=5, dry_run=True)
    assert stats["dry_run"] is True
    assert "before" in stats
