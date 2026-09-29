"""Gate 173-WIRE: canonical graph → persisted relevance + customer read model."""

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
    match_tenant_for_canonical,
    project_all_canonical_opportunities,
    project_canonical_opportunity,
    reevaluate_tenant_matches_for_organization,
    resolve_canonical_id_for_spark,
)
from nativeforge.services.customer_intelligence_read_model_service import (
    AUTHORITATIVE_LAYER,
)
from nativeforge.services.eligibility_requirement_model_service import EXCLUSION
from nativeforge.services.native_relevance_repository_service import (
    ASSESSMENTS,
    EVIDENCE,
)
from nativeforge.services.opportunity_discovery_service import (
    opportunity_intelligence_summary,
)
from nativeforge.services.source_adapter_contract_service import identity_for_normalized

DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")


@pytest.fixture
def db():
    from nativeforge.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


@pytest.fixture
def conn(db):
    return db.connection()


def _ingest_one(connection: sa.engine.Connection, *, canonical_key: str, fields: dict) -> str:
    fields = {
        "doc_type": "synopsis",
        "status": "posted",
        **fields,
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
        "content_fingerprint": "fp-" + canonical_key,
        "source_record_id": fields.get("source_record_id"),
        "lifecycle_state": "posted",
        "provenance_fields_present": sorted(fields),
        "provenance_fields_missing": [],
    }
    identity = identity_for_normalized(normalized, source_id=GRANTS_GOV_SOURCE)
    payload_sha = hashlib.sha256(f"payload-{canonical_key}".encode()).hexdigest()
    persist_observations(
        connection=connection,
        observations=[
            NormalizedSourceObservation(
                source_id=GRANTS_GOV_SOURCE,
                normalized=normalized,
                raw_payload_sha256=payload_sha,
                identity=identity,
                raw_payload_attempt_id=hashlib.sha256(
                    f"attempt-{canonical_key}".encode()
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
    assert row, "observation not persisted"
    return str(row[0])


def test_projection_idempotent_and_exclusion_requirement(conn) -> None:
    fields = {
        "title": "Tribal exclusion demo",
        "source_record_id": "wire-excl-001",
        "opportunity_number": "WIRE-EXCL-001",
        "funder_agency_name": "Demo Agency",
        "eligibility_text": "State governments only; tribal governments are not eligible.",
    }
    cid = _ingest_one(conn, canonical_key="excl", fields=fields)
    first = project_canonical_opportunity(conn, canonical_id=cid)
    second = project_canonical_opportunity(conn, canonical_id=cid)
    assert first["skipped_unchanged"] is False
    assert second["skipped_unchanged"] is True
    ev = conn.execute(
        sa.text(f"SELECT count(*) FROM {EVIDENCE} WHERE canonical_id = :c"),
        {"c": cid},
    ).scalar()
    assert ev and ev >= 1
    reqs = conn.execute(
        sa.text(
            "SELECT polarity FROM nf_opportunity_eligibility_requirements "
            "WHERE canonical_id = :c AND is_current = 1"
        ),
        {"c": cid},
    ).fetchall()
    assert any(r[0] == EXCLUSION for r in reqs)


def test_tenant_match_unknown_without_requirements(conn) -> None:
    fields = {
        "title": "Agency only",
        "source_record_id": "wire-unknown-002",
        "opportunity_number": "WIRE-UNK-002",
        "funder_agency_name": "HUD",
    }
    cid = _ingest_one(conn, canonical_key="unk", fields=fields)
    project_canonical_opportunity(conn, canonical_id=cid)
    match = match_tenant_for_canonical(
        conn,
        canonical_id=cid,
        organization_id=str(DEMO_ORG),
        tenant_id=str(DEMO_ORG),
        profile_facts={"entity_class": "tribal_government"},
    )
    assert match["eligibility_result"] == "UNKNOWN"


def test_profile_change_reevaluation(conn) -> None:
    fields = {
        "title": "Match funds req",
        "source_record_id": "wire-cond-003",
        "opportunity_number": "WIRE-COND-003",
        "funder_agency_name": "Demo",
        "eligible_applicant_codes": "07",
    }
    cid = _ingest_one(conn, canonical_key="cond", fields=fields)
    project_canonical_opportunity(conn, canonical_id=cid)
    m1 = match_tenant_for_canonical(
        conn,
        canonical_id=cid,
        organization_id=str(DEMO_ORG),
        tenant_id=str(DEMO_ORG),
        profile_facts={
            "entity_class": "tribal_government",
            "matching_funds_capability": False,
        },
    )
    m2 = match_tenant_for_canonical(
        conn,
        canonical_id=cid,
        organization_id=str(DEMO_ORG),
        tenant_id=str(DEMO_ORG),
        profile_facts={
            "entity_class": "tribal_government",
            "matching_funds_capability": True,
        },
    )
    assert m1["eligibility_result"] in ("ELIGIBLE", "LIKELY_ELIGIBLE", "UNKNOWN")
    assert m2["eligibility_result"] in ("ELIGIBLE", "LIKELY_ELIGIBLE", "UNKNOWN")
    summary = reevaluate_tenant_matches_for_organization(
        conn,
        organization_id=str(DEMO_ORG),
        tenant_id=str(DEMO_ORG),
        profile_facts={"entity_class": "tribal_government"},
    )
    assert summary["reevaluated"] >= 1


def test_customer_read_model_authoritative_not_keyword(db, conn) -> None:
    from nativeforge.db.models import NfGrantSpark, Organization
    from nativeforge.domain.enums import GrantAwardType, GrantSparkSource

    fields = {
        "title": "Read model",
        "source_record_id": "wire-read-004",
        "opportunity_number": "WIRE-READ-004",
        "funder_agency_name": "BIA",
    }
    cid = _ingest_one(conn, canonical_key="read", fields=fields)
    project_canonical_opportunity(conn, canonical_id=cid)
    org = db.get(Organization, DEMO_ORG)
    if org is None:
        db.add(Organization(id=DEMO_ORG, org_type="demo"))
        db.flush()
    spark = NfGrantSpark(
        organization_id=DEMO_ORG,
        source=GrantSparkSource.grants_gov,
        source_id="wire-read-004",
        opportunity_number="WIRE-READ-004",
        opportunity_title="Read model",
        agency="BIA",
        award_type=GrantAwardType.grant,
        native_relevance_score=99,
        native_relevance_reasons_json=["legacy_keyword"],
    )
    db.add(spark)
    db.flush()
    resolved = resolve_canonical_id_for_spark(
        conn, source_record_id="wire-read-004", opportunity_number="WIRE-READ-004"
    )
    assert resolved == cid
    body = opportunity_intelligence_summary(
        spark, session=db, organization_id=DEMO_ORG
    )
    assert body["native_relevance"]["authoritative"] is True
    assert body["native_relevance"].get("score") is None
    assert body["unified_intelligence"]["authoritative_layer"] == AUTHORITATIVE_LAYER


def test_bulk_projection(conn) -> None:
    _ingest_one(
        conn,
        canonical_key="bulk",
        fields={
            "title": "Bulk",
            "source_record_id": "wire-bulk-001",
            "opportunity_number": "WIRE-BULK-001",
            "funder_agency_name": "HUD",
        },
    )
    out = project_all_canonical_opportunities(conn, limit=5, dry_run=False)
    assert out["projected_count"] >= 1
    count = conn.execute(sa.text(f"SELECT count(*) FROM {ASSESSMENTS}")).scalar()
    assert count and count >= 1
