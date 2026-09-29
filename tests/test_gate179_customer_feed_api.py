"""Gate 179: customer opportunity feed API + canonical assembler."""

from __future__ import annotations

import hashlib
import uuid

import pytest
import sqlalchemy as sa

from nativeforge.main import create_app
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


def _seed_canonical(connection: sa.engine.Connection) -> str:
    key = "feed-api-001"
    fields = {
        "doc_type": "synopsis",
        "status": "posted",
        "title": "Tribal Water Infrastructure",
        "funder_agency_name": "EPA",
        "close_date": "2026-12-01",
        "opportunity_number": "TST-FEED-001",
        "source_record_id": "TST-FEED-001",
        "eligible_applicant_codes": "07",
        "eligibility_text": "Federally recognized tribal governments.",
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
            "WHERE source_id = :sid AND raw_payload_sha256 = :sha LIMIT 1"
        ),
        {"sid": GRANTS_GOV_SOURCE, "sha": payload_sha},
    ).fetchone()
    cid = str(row[0])
    project_canonical_opportunity(connection, canonical_id=cid)
    return cid


def test_assembler_returns_canonical_feed(db):
    conn = db.connection()
    cid = _seed_canonical(conn)
    payload = assemble_customer_opportunity_feed(
        conn,
        organization_id=str(ORG),
        tenant_id=str(ORG),
        limit=20,
    )
    assert payload["sourced_from_canonical_graph"] is True
    feed = payload["feed"]
    assert feed["sourced_from_canonical_graph"] is True
    recs = [r for r in feed.get("recommendations") or [] if r.get("canonical_id") == cid]
    assert recs, "expected recommendation for seeded canonical row"
    rec = recs[0]
    assert rec["sourced_from_canonical_graph"] is True
    assert rec.get("relevance_class")


def test_feed_route_module_registered():
    from nativeforge.api.customer_opportunity_feed_routes import demo_feed_router

    paths = {getattr(r, "path", "") for r in demo_feed_router.routes}
    assert any("customer-opportunity-feed" in p for p in paths)
