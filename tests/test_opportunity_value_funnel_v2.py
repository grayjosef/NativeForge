"""Opportunity value funnel V2 — corpus + org slices."""

from __future__ import annotations

import hashlib
import uuid

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
from nativeforge.services.customer_canonical_feed_assembler_service import (
    assemble_customer_opportunity_feed,
)
from nativeforge.services.eligibility_intelligence_repository_service import (
    write_matches,
)
from nativeforge.services.opportunity_value_funnel_service import (
    FUNNEL_METHODOLOGY_VERSION,
    compute_corpus_funnel_aggregate,
    compute_org_funnel_aggregate,
    invalidate_funnel_cache,
    public_corpus_funnel_view,
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


def _seed_active_with_funding(
    conn: sa.engine.Connection, key: str, *, eligibility_text: str | None = None
) -> str:
    fields = {
        "doc_type": "synopsis",
        "status": "posted",
        "title": f"Opp {key}",
        "funder_agency_name": "EPA",
        "close_date": "2026-12-01",
        "opportunity_number": f"FUN-{key}",
        "source_record_id": f"id-{key}",
        "funding_amount_min": "100000",
        "funding_amount_max": "100000",
    }
    if eligibility_text:
        fields["eligibility_text"] = eligibility_text
        fields["eligible_applicant_codes"] = "07"
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
    sha = hashlib.sha256(f"p-{key}".encode()).hexdigest()
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
    cid = conn.execute(
        sa.text(
            "SELECT canonical_id FROM nf_opportunity_source_observations "
            "WHERE raw_payload_sha256 = :sha LIMIT 1"
        ),
        {"sha": sha},
    ).fetchone()[0]
    project_canonical_opportunity(conn, canonical_id=str(cid))
    return str(cid)


def test_corpus_funnel_active_and_native_relevant(db):
    invalidate_funnel_cache()
    conn = db.connection()
    cid = _seed_active_with_funding(conn, "nr1")
    # Re-ingest with tribal eligibility prose so Gate 173 projection can classify.
    fields = {
        "doc_type": "synopsis",
        "status": "posted",
        "title": "Tribal Community Development",
        "funder_agency_name": "Bureau of Indian Affairs",
        "close_date": "2026-12-01",
        "opportunity_number": "FUN-nr1",
        "source_record_id": "id-nr1",
        "funding_amount_min": "100000",
        "funding_amount_max": "100000",
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
        "content_fingerprint": "fp-nr1b",
        "source_record_id": fields["source_record_id"],
        "lifecycle_state": "posted",
        "provenance_fields_present": sorted(fields),
        "provenance_fields_missing": [],
    }
    identity = identity_for_normalized(normalized, source_id=GRANTS_GOV_SOURCE)
    sha2 = hashlib.sha256(b"p-nr1b").hexdigest()
    persist_observations(
        connection=conn,
        observations=[
            NormalizedSourceObservation(
                source_id=GRANTS_GOV_SOURCE,
                normalized=normalized,
                raw_payload_sha256=sha2,
                identity=identity,
                raw_payload_attempt_id=hashlib.sha256(b"a-nr1b").hexdigest(),
                source_authority_host="api.grants.gov",
            )
        ],
    )
    project_canonical_opportunity(conn, canonical_id=cid)
    full = compute_corpus_funnel_aggregate(conn, use_cache=False)
    assert full["funnel_methodology_version"] == FUNNEL_METHODOLOGY_VERSION
    assert full["stages"]["active"]["known_count"] >= 1
    nr = full["stages"]["native_relevant"]
    assert nr["supported"] is True
    if nr["count"] >= 1:
        assert nr["known_count"] >= 1
    pub = public_corpus_funnel_view(full)
    assert "native_relevant" in pub["stages"]


def test_ineligible_still_in_customer_feed(db):
    conn = db.connection()
    cid = _seed_active_with_funding(conn, "inelig")
    write_matches(
        conn,
        matches=[
            {
                "match_id": "m-inelig",
                "canonical_id": cid,
                "tenant_id": str(ORG),
                "organization_id": str(ORG),
                "profile_version": "pv1",
                "eligibility_result": "INELIGIBLE",
                "reason": "exclusion applies",
            }
        ],
    )
    payload = assemble_customer_opportunity_feed(
        conn,
        organization_id=str(ORG),
        tenant_id=str(ORG),
        limit=50,
    )
    ids = {r["canonical_id"] for r in payload["feed"].get("recommendations") or []}
    assert cid in ids


def test_org_funnel_eligibility_slice(db):
    invalidate_funnel_cache()
    conn = db.connection()
    cid = _seed_active_with_funding(conn, "elig")
    write_matches(
        conn,
        matches=[
            {
                "match_id": "m-elig",
                "canonical_id": cid,
                "tenant_id": str(ORG),
                "organization_id": str(ORG),
                "profile_version": "pv1",
                "eligibility_result": "ELIGIBLE",
                "reason": "all satisfied",
            }
        ],
    )
    org = compute_org_funnel_aggregate(
        conn,
        organization_id=str(ORG),
        tenant_id=str(ORG),
        use_cache=False,
    )
    elig = org["stages"]["eligibility"]["eligible"]
    assert elig["count"] >= 1
    assert elig["known_count"] >= 1


def test_public_funnel_route():
    from fastapi.testclient import TestClient

    from nativeforge.main import create_app

    c = TestClient(create_app(), raise_server_exceptions=False)
    r = c.get("/api/public/opportunity-value/funnel")
    assert r.status_code == 200
    body = r.json()
    assert body["funnel_methodology_version"] == FUNNEL_METHODOLOGY_VERSION
