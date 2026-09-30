"""Applicant eligibility provenance from Grants.gov fetchOpportunity detail."""

from __future__ import annotations

import copy
import hashlib
import json
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
from nativeforge.services.customer_canonical_feed_assembler_service import (
    assemble_customer_opportunity_feed,
)
from nativeforge.services.gate173_calibration_service import (
    build_gate173_calibration_report,
)
from nativeforge.services.grants_gov_detail_enrichment_service import (
    enrich_one_active_detail,
    run_bounded_active_applicant_enrichment,
)
from nativeforge.services.grants_gov_synopsis_applicant_service import (
    map_detail_applicant_to_canonical,
    normalize_applicant_type_ids,
)
from nativeforge.services.native_eligibility_code_classification_service import (
    classify_native_eligibility,
)
from nativeforge.services.native_relevance_ontology_service import APPLICANT_RELEVANT
from nativeforge.services.source_adapter_contract_service import identity_for_normalized

FIXTURE = Path("fixtures/source_ingestion/grants_gov_fetch_opportunity_362648.json")
ORG = "dddddddd-eeee-ffff-0000-111111111111"


@pytest.fixture
def db():
    from nativeforge.db.session import SessionLocal

    session = SessionLocal()
    try:
        yield session
    finally:
        session.rollback()
        session.close()


def _detail_with_codes(*code_ids: str, opp_id: int | str | None = None) -> dict:
    raw = json.loads(FIXTURE.read_text())
    data = copy.deepcopy(raw["data"])
    if opp_id is not None:
        data["id"] = int(opp_id)
    types = []
    for cid in code_ids:
        label = {
            "07": "Native American tribal governments (Federally recognized)",
            "99": "Unrestricted (i.e., open to any type of entity below)",
            "25": 'Others (see text field entitled "Additional Information on Eligibility")',
        }.get(cid, f"Type {cid}")
        types.append({"id": cid, "description": label})
    data["synopsis"]["applicantTypes"] = types
    return data


def test_normalize_applicant_codes():
    assert normalize_applicant_type_ids(["7", "07", "07"]) == "07"
    assert normalize_applicant_type_ids(["99", "25"]) == "25,99"
    assert normalize_applicant_type_ids(["abc"]) is None


def test_code_semantics_07_99_25():
    assert (
        classify_native_eligibility(eligible_applicant_codes=["07"])["confidence"]
        == "direct"
    )
    assert (
        classify_native_eligibility(eligible_applicant_codes=["99"])["confidence"]
        == "requires_reading"
    )
    assert (
        classify_native_eligibility(eligible_applicant_codes=["25"])["confidence"]
        == "requires_reading"
    )


def test_map_detail_applicant_from_fixture():
    data = json.loads(FIXTURE.read_text())["data"]
    mapped = map_detail_applicant_to_canonical(data)
    assert "07" in (mapped.get("eligible_applicant_codes") or "")
    assert mapped.get("eligibility_text")


def _seed(conn: sa.engine.Connection, key: str, grants_id: str) -> str:
    fields = {
        "doc_type": "synopsis",
        "status": "posted",
        "title": f"App {key}",
        "funder_agency_name": "Agency",
        "close_date": "2026-12-01",
        "opportunity_number": f"APP-{key}",
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
        "fields_not_supported": [],
        "content_fingerprint": "fp-" + key,
        "source_record_id": grants_id,
        "lifecycle_state": "posted",
        "provenance_fields_present": sorted(fields),
        "provenance_fields_missing": [],
    }
    identity = identity_for_normalized(normalized, source_id=GRANTS_GOV_SOURCE)
    sha = hashlib.sha256(f"app-{key}".encode()).hexdigest()
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
    return conn.execute(
        sa.text(
            "SELECT canonical_id FROM nf_opportunity_source_observations "
            "WHERE raw_payload_sha256 = :sha LIMIT 1"
        ),
        {"sha": sha},
    ).fetchone()[0]


def test_enrichment_path_gate173_applicant_relevant(db):
    conn = db.connection()
    detail = _detail_with_codes("07")
    grants_id = str(detail["id"])

    def mock_post(url: str, body: dict) -> dict:
        if "fetchOpportunity" in url:
            return {"errorcode": 0, "data": detail}
        raise AssertionError(url)

    cid = _seed(conn, "tribal07", grants_id)
    row = {
        "canonical_id": cid,
        "source_record_id": grants_id,
        "opportunity_number": detail["opportunityNumber"],
        "doc_type": "synopsis",
        "lifecycle_state": "posted",
    }
    result = enrich_one_active_detail(conn, row=row, http_post=mock_post)
    assert result["observation_persisted"]
    assert result["applicant_outcome"] == "applicant_evidence_found"
    proj = project_canonical_opportunity(conn, canonical_id=str(cid))
    assert proj["relevance_class"] in APPLICANT_RELEVANT
    codes = conn.execute(
        sa.text(
            "SELECT field_value FROM nf_opportunity_field_provenance "
            "WHERE canonical_id = :cid AND field_name = 'eligible_applicant_codes' "
            "AND is_current_canonical = 1"
        ),
        {"cid": cid},
    ).fetchone()
    assert codes is not None


def test_code_99_broad_eligibility(db):
    conn = db.connection()
    grants_id = "999001"
    detail = _detail_with_codes("99", opp_id=grants_id)

    def mock_post(url: str, body: dict) -> dict:
        return {"errorcode": 0, "data": detail}

    cid = _seed(conn, "broad99", grants_id)
    row = {
        "canonical_id": cid,
        "source_record_id": grants_id,
        "opportunity_number": "BROAD-99",
        "doc_type": "synopsis",
        "lifecycle_state": "posted",
    }
    enrich_one_active_detail(conn, row=row, http_post=mock_post)
    proj = project_canonical_opportunity(conn, canonical_id=str(cid))
    assert proj["relevance_class"] in APPLICANT_RELEVANT


def test_negative_federal_only_code(db):
    conn = db.connection()
    grants_id = "999012"
    detail = _detail_with_codes("12", opp_id=grants_id)

    def mock_post(url: str, body: dict) -> dict:
        return {"errorcode": 0, "data": detail}

    cid = _seed(conn, "fed12", grants_id)
    row = {
        "canonical_id": cid,
        "source_record_id": grants_id,
        "opportunity_number": "FED-12",
        "doc_type": "synopsis",
        "lifecycle_state": "posted",
    }
    enrich_one_active_detail(conn, row=row, http_post=mock_post)
    proj = project_canonical_opportunity(conn, canonical_id=str(cid))
    assert proj["relevance_class"] not in APPLICANT_RELEVANT


def test_gold_corpus_regression():
    report = build_gate173_calibration_report()
    assert report["metrics"]["false_negatives"] == []
    assert report["metrics"]["recall"] == 1.0


def test_ineligible_still_visible(db):
    conn = db.connection()
    detail = _detail_with_codes("07")
    grants_id = str(detail["id"])

    def mock_post(url: str, body: dict) -> dict:
        return {"errorcode": 0, "data": detail}

    cid = _seed(conn, "vis", grants_id)
    enrich_one_active_detail(
        conn,
        row={
            "canonical_id": cid,
            "source_record_id": grants_id,
            "opportunity_number": detail["opportunityNumber"],
            "doc_type": "synopsis",
            "lifecycle_state": "posted",
        },
        http_post=mock_post,
    )
    project_canonical_opportunity(conn, canonical_id=str(cid))
    feed = assemble_customer_opportunity_feed(
        conn, organization_id=ORG, tenant_id=ORG, limit=50
    )
    ids = {r["canonical_id"] for r in feed["feed"].get("recommendations") or []}
    assert str(cid) in ids


def test_bounded_applicant_dry_run(db):
    conn = db.connection()
    stats = run_bounded_active_applicant_enrichment(conn, limit=3, dry_run=True)
    assert stats["dry_run"] is True
