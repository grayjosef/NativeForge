"""Gate 173 material-input fingerprint: evidence changes must reassess."""

from __future__ import annotations

import hashlib

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
from nativeforge.services.native_relevance_ontology_service import APPLICANT_RELEVANT
from nativeforge.services.source_adapter_contract_service import identity_for_normalized


@pytest.fixture
def conn(db):
    return db.connection()


@pytest.fixture
def db():
    from nativeforge.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _ingest(
    connection: sa.engine.Connection,
    *,
    key: str,
    fields: dict,
) -> str:
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
        "content_fingerprint": "fp-" + key,
        "source_record_id": fields.get("source_record_id"),
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
    assert row
    return str(row[0])


def test_applicant_codes_after_suggestive_only_reassesses(conn) -> None:
    cid = _ingest(
        conn,
        key="suggestive-then-codes",
        fields={
            "title": "Agency context only",
            "source_record_id": "stale-173-001",
            "opportunity_number": "STALE-173-001",
            "funder_agency_name": "Bureau of Indian Affairs",
        },
    )
    first = project_canonical_opportunity(conn, canonical_id=cid)
    assert first["skipped_unchanged"] is False
    assert first["relevance_class"] == "INDIRECTLY_RELEVANT"

    _ingest(
        conn,
        key="suggestive-then-codes-v2",
        fields={
            "title": "Agency context only",
            "source_record_id": "stale-173-001",
            "opportunity_number": "STALE-173-001",
            "funder_agency_name": "Bureau of Indian Affairs",
            "eligible_applicant_codes": '["07"]',
        },
    )
    second = project_canonical_opportunity(conn, canonical_id=cid)
    assert second["skipped_unchanged"] is False
    assert second["relevance_class"] in APPLICANT_RELEVANT

    third = project_canonical_opportunity(conn, canonical_id=cid)
    assert third["skipped_unchanged"] is True


def test_legacy_output_fingerprint_does_not_block_reassessment(conn) -> None:
    cid = _ingest(
        conn,
        key="legacy-fp",
        fields={
            "title": "Tribal code",
            "source_record_id": "legacy-fp-001",
            "opportunity_number": "LEG-FP-001",
            "funder_agency_name": "Demo",
            "eligible_applicant_codes": "07",
        },
    )
    project_canonical_opportunity(conn, canonical_id=cid)
    conn.execute(
        sa.text(
            "UPDATE nf_opportunity_relevance_assessments "
            "SET reasons_json = :reasons WHERE canonical_id = :cid AND is_current = 1"
        ),
        {
            "cid": cid,
            "reasons": '{"projection_fingerprint": "deadbeef", "items": []}',
        },
    )
    again = project_canonical_opportunity(conn, canonical_id=cid)
    assert again["skipped_unchanged"] is False
    assert again["relevance_class"] in APPLICANT_RELEVANT
