"""Grant-spark projection after canonical persist commits must re-stamp RLS GUCs."""

from __future__ import annotations

import uuid
from pathlib import Path
from unittest.mock import patch

import pytest
import sqlalchemy as sa

from nativeforge.db.rls import IS_DEMO_GUC, ORG_ID_GUC
from nativeforge.db.session import SessionLocal
from nativeforge.repositories.canonical_opportunity_batch_repository import (
    canonical_ids_from_persist_batch,
)
from nativeforge.services.grants_gov_corpus_ingest_service import (
    ingest_grants_gov_search2_payload,
)

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "fixtures" / "source_ingestion" / "grants_gov_search2_bia_tedc_hit.json"
DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
SOURCE = "nf-seed-2026-api-grants-gov-search2"


def test_persist_batch_contract_is_not_top_level_dict_keys() -> None:
    batch = {
        "results": [{"canonical_id": "L1:PAR25156|synopsis"}],
        "metrics": {},
    }
    assert canonical_ids_from_persist_batch(batch) == ["L1:PAR25156|synopsis"]
    with pytest.raises(AttributeError):
        for row in batch:
            row.get("canonical_id")


def test_ingest_reapplies_rls_before_grant_spark_projection() -> None:
    source = (
        REPO / "src/nativeforge/services/grants_gov_corpus_ingest_service.py"
    ).read_text(encoding="utf-8")
    spark_at = source.index("spark_metrics = project_grant_sparks_from_hits")
    reapply_at = source.rindex("reapply_org_rls_after_commit", 0, spark_at)
    enrich_at = source.index("enrich_canonical_ids_missing_applicant")
    assert enrich_at < reapply_at < spark_at


def test_ingest_fixture_reaches_grant_spark_projection() -> None:
    raw = FIXTURE.read_bytes()
    session = SessionLocal()
    try:
        from nativeforge.db.models import Organization

        org = session.get(Organization, DEMO)
        if org is None:
            org = Organization(id=DEMO, org_type="demo")
            session.add(org)
            session.flush()

        reapplies: list[str] = []
        original = __import__(
            "nativeforge.db.rls", fromlist=["reapply_org_rls_after_commit"]
        ).reapply_org_rls_after_commit

        def _track(session_arg, org_id, org_type):  # noqa: ANN001
            reapplies.append(str(org_type))
            return original(session_arg, org_id, org_type)

        with patch(
            "nativeforge.services.grants_gov_corpus_ingest_service.reapply_org_rls_after_commit",
            side_effect=_track,
        ):
            report = ingest_grants_gov_search2_payload(
                session.connection(),
                session,
                organization_id=DEMO,
                org=org,
                org_type="demo",
                source_id=SOURCE,
                body_bytes=raw,
                payload_sha256="gate163-post-commit-rls-sha",
                attempt_id="gate163-post-commit-rls",
            )
        assert report.sparks.inserted + report.sparks.updated + report.sparks.unchanged >= 1
        assert reapplies.count("demo") >= 2
    finally:
        session.rollback()
        session.close()


def _pg_available() -> bool:
    import shutil

    return shutil.which("psql") is not None or Path.home().joinpath(
        ".pgtmp/root/usr/lib/postgresql/16/bin/psql"
    ).exists()


@pytest.mark.skipif(not _pg_available(), reason="local PostgreSQL not available")
def test_empty_is_demo_guc_does_not_abort_grant_spark_select_under_hardened_rls() -> None:
    """RLS with NULLIF must deny quietly; legacy cast raises DataError."""
    from nativeforge.db import session as session_module  # noqa: F401
    from nativeforge.lib.settings import get_settings

    url = get_settings().database_url
    if not url.startswith("postgresql"):
        pytest.skip("requires PostgreSQL")

    engine = sa.create_engine(url)
    demo = DEMO
    with engine.connect() as conn:
        conn.execute(
            sa.text(f"SELECT set_config('{ORG_ID_GUC}', :o, true)"),
            {"o": str(demo)},
        )
        conn.execute(sa.text(f"SELECT set_config('{IS_DEMO_GUC}', '', true)"))
        # Must not raise after migration 0072 policy hardening.
        conn.execute(
            sa.text(
                "SELECT id FROM nf_grant_sparks "
                "WHERE organization_id = :oid AND is_demo IS TRUE LIMIT 1"
            ),
            {"oid": str(demo)},
        )
        conn.commit()
