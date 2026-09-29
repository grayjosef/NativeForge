"""Block 5B: Grants.gov bounded corpus path (no live network in default tests)."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

from nativeforge.db.session import SessionLocal
from nativeforge.services.grants_gov_corpus_ingest_service import (
    ingest_grants_gov_search2_payload,
    rollup_collection_metrics,
)
from nativeforge.services.grants_gov_live_corpus_collection_service import (
    assert_collection_permitted,
    run_grants_gov_bounded_live_collection,
)
from nativeforge.services.grants_gov_search_api_adapter_service import (
    build_grants_gov_broad_search_body,
)

REPO = Path(__file__).resolve().parents[1]
FIXTURE = (
    REPO / "fixtures" / "source_ingestion" / "grants_gov_search2_bia_tedc_hit.json"
)
DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
SOURCE = "nf-seed-2026-api-grants-gov-search2"


def test_broad_search_body_has_no_applicant_class_filter() -> None:
    body = build_grants_gov_broad_search_body(rows=200)
    assert body["oppStatuses"] == "posted|forecasted"
    assert body["rows"] == 200
    assert "keyword" not in body
    assert "eligibility" not in body


def test_ingest_fixture_payload_idempotent_sparks_and_canonical() -> None:
    raw = FIXTURE.read_bytes()
    sha = "test_sha_fixture_gate163_block5b"

    session = SessionLocal()
    try:
        from nativeforge.db.models import Organization

        org = session.get(Organization, DEMO)
        if org is None:
            org = Organization(id=DEMO, org_type="demo")
            session.add(org)
            session.flush()

        first = ingest_grants_gov_search2_payload(
            session,
            session,
            organization_id=DEMO,
            org=org,
            org_type="demo",
            source_id=SOURCE,
            body_bytes=raw,
            payload_sha256=sha,
            attempt_id="fixture-attempt-1",
        )
        session.commit()
        m1 = rollup_collection_metrics(first)
        assert m1["fetched"] == 1
        assert m1["normalized"] == 1
        assert m1["inserted"] >= 1

        second = ingest_grants_gov_search2_payload(
            session,
            session,
            organization_id=DEMO,
            org=org,
            org_type="demo",
            source_id=SOURCE,
            body_bytes=raw,
            payload_sha256=sha,
            attempt_id="fixture-attempt-2",
        )
        session.commit()
        m2 = rollup_collection_metrics(second)
        assert m2["fetched"] == 1
        assert m2["inserted"] == 0
        assert m2["unchanged"] + m2["updated"] >= 1
    finally:
        session.close()


def test_dry_run_never_opens_socket() -> None:
    session = SessionLocal()
    try:
        with patch(
            "nativeforge.services.grants_gov_live_corpus_collection_service.execute_request"
        ) as execute:
            result = run_grants_gov_bounded_live_collection(
                session,
                session,
                organization_id=DEMO,
                org_type="demo",
                source_id=SOURCE,
                job_id="test-job",
                attempt_number=1,
                dry_run=True,
            )
            execute.assert_not_called()
        assert result.permitted in (True, False)
        assert result.dispatched is False
    finally:
        session.close()


def test_warrant_refusal_blocks_before_transport() -> None:
    session = SessionLocal()
    try:
        with patch(
            "nativeforge.services.grants_gov_live_corpus_collection_service"
            ".assert_bounded_collection_permitted",
            return_value=__import__(
                "nativeforge.services.source_live_collection_policy_service",
                fromlist=["CollectionRefusal"],
            ).CollectionRefusal(reasons=["authorization:refused"]),
        ):
            refusal = assert_collection_permitted(
                session, organization_id=DEMO, source_id=SOURCE
            )
        assert refusal is not None
    finally:
        session.close()
