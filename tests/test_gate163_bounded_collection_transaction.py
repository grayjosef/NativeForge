"""Transaction ownership for Gate 163 bounded corpus collection."""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest
from sqlalchemy.exc import InvalidRequestError

from nativeforge.db.operator_session import commit_bounded_operator_session
from nativeforge.db.session import SessionLocal
from nativeforge.services.grants_gov_live_corpus_collection_service import (
    run_grants_gov_bounded_live_collection,
)

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "fixtures" / "source_ingestion" / "grants_gov_search2_bia_tedc_hit.json"
DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
SOURCE = "nf-seed-2026-api-grants-gov-search2"


def test_duplicate_session_commit_raises_after_connection_commit() -> None:
    session = SessionLocal()
    try:
        session.connection().commit()
        with pytest.raises(InvalidRequestError, match="inactive"):
            session.commit()
    finally:
        session.rollback()
        session.close()


def test_commit_bounded_operator_session_after_connection_commit() -> None:
    session = SessionLocal()
    try:
        session.connection().commit()
        session.execute(__import__("sqlalchemy").text("SELECT 1"))
        commit_bounded_operator_session(session)
    finally:
        session.rollback()
        session.close()


def test_ingest_tail_commit_after_persist_connection_commit() -> None:
    """Spark/stamp tail uses connection.commit when Session txn is deassociated."""
    raw = FIXTURE.read_bytes()
    session = SessionLocal()
    try:
        from nativeforge.db.models import Organization
        from nativeforge.services.grants_gov_corpus_ingest_service import (
            ingest_grants_gov_search2_payload,
        )

        org = session.get(Organization, DEMO)
        if org is None:
            org = Organization(id=DEMO, org_type="demo")
            session.add(org)
            session.flush()
        ingest_grants_gov_search2_payload(
            session.connection(),
            session,
            organization_id=DEMO,
            org=org,
            org_type="demo",
            source_id=SOURCE,
            body_bytes=raw,
            payload_sha256="tx-tail-sha",
            attempt_id="tx-tail",
        )
        commit_bounded_operator_session(session)
    finally:
        session.rollback()
        session.close()


def test_operator_script_does_not_call_session_commit_on_apply_path() -> None:
    script = (
        REPO / "scripts" / "run_gate163_grants_gov_bounded_corpus_collection.py"
    ).read_text(encoding="utf-8")
    apply_block = script.split("if not args.apply:", 1)[1]
    assert "session.commit()" not in apply_block
    assert "persistence_committed" in script


def test_refusal_path_does_not_mark_persistence_committed() -> None:
    session = SessionLocal()
    try:
        result = run_grants_gov_bounded_live_collection(
            session,
            session,
            organization_id=DEMO,
            org_type="demo",
            source_id=SOURCE,
            job_id="tx-refusal",
            attempt_number=1,
            dry_run=True,
        )
        assert result.persistence_committed is False
    finally:
        session.close()
