"""Funding Landscape Intelligence V4 — Gate 173 calibration + decision advantage."""

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
from nativeforge.services.eligibility_intelligence_repository_service import (
    write_matches,
)
from nativeforge.services.funding_landscape_decision_advantage_service import (
    compute_org_decision_advantage,
)
from nativeforge.services.gate173_calibration_service import (
    build_gate173_calibration_report,
)
from nativeforge.services.native_relevance_ontology_service import APPLICANT_RELEVANT
from nativeforge.services.opportunity_value_funnel_service import (
    compute_org_funnel_aggregate,
    invalidate_funnel_cache,
)
from nativeforge.services.source_adapter_contract_service import identity_for_normalized

ORG = uuid.UUID("cccccccc-dddd-eeee-ffff-000000000001")


@pytest.fixture
def db():
    from nativeforge.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _seed_with_tribal_code(conn: sa.engine.Connection, key: str) -> str:
    fields = {
        "doc_type": "synopsis",
        "status": "posted",
        "title": f"Tribal {key}",
        "funder_agency_name": "BIA",
        "close_date": "2026-12-01",
        "opportunity_number": f"TR-{key}",
        "source_record_id": f"tr-{key}",
        "eligible_applicant_codes": "07",
        "funding_amount_min": "250000",
        "funding_amount_max": "250000",
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
        "content_fingerprint": "fp-tr-" + key,
        "source_record_id": fields["source_record_id"],
        "lifecycle_state": "posted",
        "provenance_fields_present": sorted(fields),
        "provenance_fields_missing": [],
    }
    identity = identity_for_normalized(normalized, source_id=GRANTS_GOV_SOURCE)
    sha = hashlib.sha256(f"tr-{key}".encode()).hexdigest()
    persist_observations(
        connection=conn,
        observations=[
            NormalizedSourceObservation(
                source_id=GRANTS_GOV_SOURCE,
                normalized=normalized,
                raw_payload_sha256=sha,
                identity=identity,
                raw_payload_attempt_id=hashlib.sha256(
                    f"a-tr-{key}".encode()
                ).hexdigest(),
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
    return str(cid)


def test_calibration_gold_corpus_green():
    report = build_gate173_calibration_report()
    assert report["calibration_corpus"]["size"] >= 20
    assert report["metrics"]["false_negatives"] == []
    assert report["relevance_methodology_version"] == "2026.09.1"


def test_projection_reads_applicant_codes(db):
    conn = db.connection()
    cid = _seed_with_tribal_code(conn, "codes")
    out = project_canonical_opportunity(conn, canonical_id=cid, dry_run=False)
    assert out["relevance_class"] in APPLICANT_RELEVANT
    row = conn.execute(
        sa.text(
            "SELECT relevance_class FROM nf_opportunity_relevance_assessments "
            "WHERE canonical_id = :cid ORDER BY created_at DESC LIMIT 1"
        ),
        {"cid": cid},
    ).fetchone()
    assert row[0] in APPLICANT_RELEVANT


def test_decision_advantage_gap_closure_non_additive(db):
    invalidate_funnel_cache()
    conn = db.connection()
    cid = _seed_with_tribal_code(conn, "gap")
    write_matches(
        conn,
        matches=[
            {
                "match_id": "m-gap-v4",
                "canonical_id": cid,
                "tenant_id": str(ORG),
                "organization_id": str(ORG),
                "profile_version": "pv1",
                "eligibility_result": "CONDITIONALLY_ELIGIBLE",
                "reason": "needs registration",
                "conditions_to_obtain": ["REGISTRATION", "MATCHING_FUNDS"],
            }
        ],
    )
    da = compute_org_decision_advantage(
        conn, organization_id=str(ORG), tenant_id=str(ORG)
    )
    assert da["gap_closure"]["condition_slices_non_additive"] is True
    assert "REGISTRATION" in da["gap_closure"]["by_condition"]
    assert da["no_opaque_priority_score"] is True


def test_org_funnel_includes_decision_advantage(db):
    conn = db.connection()
    org = compute_org_funnel_aggregate(
        conn,
        organization_id=str(ORG),
        tenant_id=str(ORG),
        use_cache=False,
    )
    assert "decision_advantage" in org
    assert org["decision_advantage"]["not_currently_pursued"]["supported"] is True
