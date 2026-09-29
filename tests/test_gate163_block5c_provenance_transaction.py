"""Block 5C: provenance must survive canonical batch failure (regression)."""

from __future__ import annotations

import datetime as dt
import uuid
from unittest.mock import patch

import sqlalchemy as sa

from nativeforge.db.session import SessionLocal
from nativeforge.repositories.canonical_opportunity_batch_repository import (
    NormalizedSourceObservation,
    persist_observations,
)
from nativeforge.repositories.source_collection_raw_payload_repository import (
    persist_payload,
)
from nativeforge.services.canonical_opportunity_normalizer_service import (
    normalize_record,
)
from nativeforge.services.opportunity_identity_versioning_service import (
    build_opportunity_identity,
)
from tests import session_org_helper as soh

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
SOURCE = "nf-seed-2026-api-grants-gov-search2"
HIT = {
    "id": "999001",
    "number": "NF5C-TEST-001",
    "title": "Block 5C transaction regression",
    "agency": "Test Agency",
    "agencyCode": "TST",
    "openDate": "01/01/2026",
    "closeDate": "12/31/2026",
    "oppStatus": "posted",
    "docType": "synopsis",
}


def _obs(sha: str) -> NormalizedSourceObservation:
    normalized = normalize_record(record=HIT, adapter_key="grants_gov_search2")
    identity = build_opportunity_identity(
        opportunity_number=normalized["fields"].get("opportunity_number"),
        doc_type=normalized["fields"].get("doc_type"),
        opportunity_id=normalized["fields"].get("source_record_id"),
    )
    return NormalizedSourceObservation(
        source_id=SOURCE,
        normalized=normalized,
        raw_payload_sha256=sha,
        identity=identity,
        source_authority_host="api.grants.gov",
    )


def test_raw_payload_survives_canonical_batch_failure() -> None:
    sha = "a" * 64
    soh.ensure_org(DEMO, "demo")
    session = SessionLocal()
    try:
        body = b'{"data":{"oppHits":[]}}'
        written = persist_payload(
            connection=session,
            organization_id=DEMO,
            attempt_id="block5c-payload-test",
            attempt_number=1,
            job_id="block5c",
            source_id=SOURCE,
            body=body,
            declared_sha256=__import__("hashlib").sha256(body).hexdigest(),
            is_demo=True,
            live_fetch_performed=True,
            collector_invoked=True,
            authorized_source_id=SOURCE,
            received_at=dt.datetime(2026, 9, 28, 12, 0, tzinfo=dt.UTC),
        )
        assert written.get("stored") or written.get("deduplicated")

        with patch(
            "nativeforge.repositories.canonical_opportunity_batch_repository._persist_chunk",
            side_effect=RuntimeError("simulated batch failure"),
        ):
            metrics = persist_observations(
                connection=session, observations=[_obs(sha)]
            )
        batch_metrics = metrics.get("metrics") or metrics
        assert int(batch_metrics.get("batch_failures") or 0) == 1

        session.commit()
        session.close()

        verify = SessionLocal()
        count = verify.execute(
            sa.text(
                """
                SELECT count(*) FROM nf_source_collection_raw_payloads
                WHERE attempt_id = 'block5c-payload-test'
                """
            )
        ).scalar()
        verify.close()
        assert int(count or 0) == 1
    finally:
        try:
            session.rollback()
            session.close()
        except Exception:  # noqa: BLE001
            pass


def test_canonical_batch_succeeds_for_parseable_hit() -> None:
    sha = "b" * 64
    soh.ensure_org(DEMO, "demo")
    session = SessionLocal()
    try:
        metrics = persist_observations(connection=session, observations=[_obs(sha)])
        session.commit()
        batch_metrics = metrics.get("metrics") or metrics
        assert int(batch_metrics.get("observations_inserted") or 0) >= 1
        canonical = session.execute(
            sa.text("SELECT count(*) FROM nf_canonical_opportunities")
        ).scalar()
        assert int(canonical or 0) >= 1
    finally:
        session.close()
