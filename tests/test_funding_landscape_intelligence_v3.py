"""Funding Landscape Intelligence V3 — Gate 173 projection, composition, blocked value."""

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
from nativeforge.services.eligibility_intelligence_repository_service import (
    write_matches,
)
from nativeforge.services.funding_landscape_blocked_value_service import (
    BLOCKED_VALUE_METHODOLOGY,
    compute_org_blocked_known_value,
)
from nativeforge.services.funding_landscape_composition_service import (
    compute_known_value_composition,
)
from nativeforge.services.funding_landscape_velocity_service import (
    compute_partial_velocity,
)
from nativeforge.services.gate173_active_corpus_projection_service import (
    list_active_canonical_ids_missing_current_assessment,
    project_intelligence_for_canonical_ids,
    run_bounded_active_relevance_projection,
)
from nativeforge.services.native_relevance_ontology_service import APPLICANT_RELEVANT
from nativeforge.services.opportunity_value_funnel_service import (
    compute_corpus_funnel_aggregate,
    invalidate_funnel_cache,
)
from nativeforge.services.source_adapter_contract_service import identity_for_normalized

ORG = uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


@pytest.fixture
def db():
    from nativeforge.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _seed_active(conn: sa.engine.Connection, key: str, *, amount: str = "50000") -> str:
    fields = {
        "doc_type": "synopsis",
        "status": "posted",
        "title": f"Opp {key}",
        "funder_agency_name": "EPA",
        "close_date": "2026-12-01",
        "opportunity_number": f"V3-{key}",
        "source_record_id": f"id-{key}",
        "funding_amount_min": amount,
        "funding_amount_max": amount,
        "eligibility_text": "Federally recognized tribal governments.",
        "eligible_applicant_codes": "07",
    }
    normalized = {
        "schema_version": "test",
        "parser_version": "test",
        "parser_name": "test",
        "adapter_key": "grants_gov_search2",
        "parseable": True,
        "fields": fields,
        "fields_absent": [],
        "fields_not_supported": [],
        "content_fingerprint": "fp-" + key,
        "source_record_id": fields["source_record_id"],
        "lifecycle_state": "posted",
        "provenance_fields_present": sorted(fields),
        "provenance_fields_missing": [],
    }
    identity = identity_for_normalized(normalized, source_id=GRANTS_GOV_SOURCE)
    sha = hashlib.sha256(f"v3-{key}".encode()).hexdigest()
    persist_observations(
        connection=conn,
        observations=[
            NormalizedSourceObservation(
                source_id=GRANTS_GOV_SOURCE,
                normalized=normalized,
                raw_payload_sha256=sha,
                identity=identity,
                raw_payload_attempt_id=hashlib.sha256(f"a-{key}".encode()).hexdigest(),
                source_authority_host="api.grants.gov",
            )
        ],
    )
    row = conn.execute(
        sa.text(
            "SELECT canonical_id FROM nf_opportunity_source_observations "
            "WHERE raw_payload_sha256 = :sha LIMIT 1"
        ),
        {"sha": sha},
    ).fetchone()
    return str(row[0])


def test_gate173_active_projection_idempotent(db):
    conn = db.connection()
    cid = _seed_active(conn, "g173a")
    missing_before = list_active_canonical_ids_missing_current_assessment(conn, limit=500)
    assert cid in missing_before
    first = project_intelligence_for_canonical_ids(
        conn, canonical_ids=[cid], dry_run=False
    )
    assert first["projected"] == 1
    missing_after = list_active_canonical_ids_missing_current_assessment(conn, limit=500)
    assert cid not in missing_after
    second = project_intelligence_for_canonical_ids(
        conn, canonical_ids=[cid], dry_run=False
    )
    assert second["skipped_unchanged"] >= 1
    row = conn.execute(
        sa.text(
            "SELECT relevance_class FROM nf_opportunity_relevance_assessments "
            "WHERE canonical_id = :cid AND is_current = 1"
        ),
        {"cid": cid},
    ).fetchone()
    assert row is not None


def test_native_relevant_funnel_after_gate173(db):
    invalidate_funnel_cache()
    conn = db.connection()
    cid = _seed_active(conn, "g173b", amount="75000")
    project_canonical_opportunity(conn, canonical_id=cid)
    full = compute_corpus_funnel_aggregate(conn, use_cache=False)
    nr = full["stages"]["native_relevant"]
    assert nr["supported"] is True
    cls = conn.execute(
        sa.text(
            "SELECT relevance_class FROM nf_opportunity_relevance_assessments "
            "WHERE canonical_id = :cid AND is_current = 1"
        ),
        {"cid": cid},
    ).fetchone()[0]
    if cls in APPLICANT_RELEVANT:
        assert nr["count"] >= 1
        assert nr["known_count"] >= 1


def test_concentration_shares_exact(db):
    conn = db.connection()
    _seed_active(conn, "big", amount="900000")
    _seed_active(conn, "small", amount="100000")
    comp = compute_known_value_composition(conn, top_n=5)
    shares = comp["concentration"]
    assert shares["top_1_share_pct"] is not None
    assert shares["top_5_share_pct"] is not None
    breakdown = comp["semantic_breakdown"]
    total = Decimal(comp["known_total_by_currency"].get("USD", "0"))
    sem_sum = sum(
        Decimal(v["known_value_by_currency"].get("USD", "0"))
        for v in breakdown.values()
    )
    assert sem_sum == total


def test_blocked_value_non_additive(db):
    conn = db.connection()
    cid = _seed_active(conn, "blk", amount="200000")
    write_matches(
        conn,
        matches=[
            {
                "match_id": "m-blk",
                "canonical_id": cid,
                "tenant_id": str(ORG),
                "organization_id": str(ORG),
                "profile_version": "pv1",
                "eligibility_result": "CONDITIONALLY_ELIGIBLE",
                "reason": "needs match",
                "conditions_to_obtain": ["MATCHING_FUNDS", "REGISTRATION"],
            }
        ],
    )
    blocked = compute_org_blocked_known_value(conn, tenant_id=str(ORG))
    assert blocked["supported"] is True
    assert blocked["methodology_version"] == BLOCKED_VALUE_METHODOLOGY
    assert blocked["blocked_value_dimensions_are_non_additive"] is True
    assert "MATCHING_FUNDS" in blocked["by_reason"]
    assert "REGISTRATION" in blocked["by_reason"]


def test_velocity_fail_closed_value_delta(db):
    conn = db.connection()
    vel = compute_partial_velocity(conn)
    assert vel["velocity_support"] is False
    assert "new_known_value_7d" not in vel.get("measurements", {})


def test_dry_run_gate173_projection(db):
    conn = db.connection()
    stats = run_bounded_active_relevance_projection(conn, limit=5, dry_run=True)
    assert stats["dry_run"] is True
    assert "cohort_sample" in stats


def test_public_composition_route():
    from fastapi.testclient import TestClient

    from nativeforge.main import create_app

    c = TestClient(create_app(), raise_server_exceptions=False)
    r = c.get("/api/public/opportunity-value/composition")
    assert r.status_code == 200
    body = r.json()
    assert "semantic_breakdown" in body
