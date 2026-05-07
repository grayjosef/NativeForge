"""Sprint 27: connector run manifest v1 + offline diagnostics coverage."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import cast

import pytest

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    GrantAwardType,
    OpportunitySourceType,
    SourceCheckMode,
    SourceCheckRunStatus,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.services.opportunity_discovery_service import (
    OpportunitySourcePayload,
    create_opportunity_source,
)
from nativeforge.services.source_connectors.base import (
    ConnectorRunContext,
    ConnectorSourceConfig,
)
from nativeforge.services.source_connectors.connector_diagnostics import (
    manifest_counts_intake_consistent,
)
from nativeforge.services.source_connectors.fixture_corpus import (
    CORPUS_SCHEMA_VERSION,
    load_all_corpus_rows_flat,
    load_category_rows,
)
from nativeforge.services.source_connectors.grants_gov_shaped import (
    GRANTS_GOV_SHAPED_CONNECTOR_KEY,
)
from nativeforge.services.source_connectors.intake_bridge import (
    static_fixture_connector_intake_dry_run,
)
from nativeforge.services.source_connectors.source_check_bridge import (
    run_source_check_backed_connector_dry_run,
)

CONNECTOR_ROOT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "nativeforge"
    / "services"
    / "source_connectors"
)
_FORBIDDEN = (
    "requests",
    "httpx",
    "aiohttp",
    "urllib.request",
    "socket",
    "openai",
    "anthropic",
    "boto3",
    "google.generative",
)


def _seed_org_and_source() -> tuple[uuid.UUID, uuid.UUID]:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        src = create_opportunity_source(
            s,
            org=org,
            body=OpportunitySourcePayload(
                source_name="Sprint 27 manifest source",
                source_type=OpportunitySourceType.federal,
                scope_global=True,
            ),
        )
        s.commit()
        return oid, src.id


def _cfg(*, cid: str = "sprint27") -> ConnectorSourceConfig:
    return ConnectorSourceConfig(
        connector_id=cid,
        source_name="s27",
        publisher_name="Illustrative Agency",
    )


def test_manifest_static_fixture_success_includes_core_fields() -> None:
    oid, sid = _seed_org_and_source()
    dl = datetime.now(UTC) + timedelta(days=45)
    rows = [
        {
            "opportunity_title": "S27 success fixture",
            "agency": "Illustrative Agency",
            "award_type": GrantAwardType.grant.value,
            "opportunity_source_type": OpportunitySourceType.federal.value,
            "opportunity_number": "S27-OK-001",
            "source_url": "https://example.test/s27/ok",
            "tribal_eligible": True,
            "application_deadline": dl.isoformat(),
        }
    ]
    ctx = ConnectorRunContext(run_id="s27-run-a", dry_run=True)
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = static_fixture_connector_intake_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=rows,
            connector_config=_cfg(),
            run_context=ctx,
        )
        s.commit()
    m = out["connector_manifest"]
    assert m["schema_version"] == "nf_connector_run_manifest_v1"
    assert m["dry_run"] is True
    assert m["connector_id"] == "sprint27"
    assert m["connector_schema_version"] == "nf_connector_normalized_v1"
    assert m["connector_run_id"] == "s27-run-a"
    assert m["source_registry_id"] == str(sid)
    assert m["counts"]["fixture_rows"] == 1
    assert m["counts"]["normalized_candidates"] == 1
    assert m["counts"]["intake_candidates"] == 1
    assert m["counts"]["accepted"] >= 1
    assert m["health_status"] == "healthy"
    json.dumps(m)
    hints = m["evidence_pack_subject_hints"]
    assert hints["opportunity_source"]["subject_id"] == str(sid)
    assert hints["intake_run"]["subject_id"] == out["intake_run"]["id"]


def test_manifest_full_fixture_corpus_run() -> None:
    oid, sid = _seed_org_and_source()
    rows = load_all_corpus_rows_flat()
    assert len(rows) >= 12
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = static_fixture_connector_intake_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=rows,
            connector_config=_cfg(cid="s27_corpus"),
        )
        s.commit()
    m = out["connector_manifest"]
    assert m["counts"]["fixture_rows"] == len(rows)
    sm = out["summary"]["counts"]
    assert m["counts"]["accepted"] == int(sm["accepted_count"])
    assert m["counts"]["duplicate"] == int(sm["duplicate_count"])
    assert m["counts"]["rejected"] == int(sm["rejected_count"])
    assert m["counts"]["error"] == int(sm["error_count"])
    assert manifest_counts_intake_consistent(
        summary_counts=sm,
        accepted=m["counts"]["accepted"],
        duplicate=m["counts"]["duplicate"],
        rejected=m["counts"]["rejected"],
        error=m["counts"]["error"],
    )
    sid_meta = m.get("source_identifiers") or {}
    assert sid_meta.get("corpus_schema_version") == CORPUS_SCHEMA_VERSION
    cats = sid_meta.get("fixture_categories") or []
    assert "keyword_only_false_positive" in cats
    assert "ambiguous_eligibility_case" in cats
    json.dumps(m)


def test_manifest_grants_gov_shaped_intake_path() -> None:
    oid, sid = _seed_org_and_source()
    dl = datetime.now(UTC) + timedelta(days=50)
    raw = {
        "Title": "S27 Grants.gov-shaped dry run",
        "agencyName": "Illustrative DOE",
        "OpportunityNumber": "S27-GG-001",
        "OpportunityURL": "https://example.test/s27/gg",
        "AwardType": "Grant",
        "FundingInstrumentType": "Grant",
        "PostedDate": "2025-01-01",
        "CloseDate": dl.isoformat(),
    }
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = static_fixture_connector_intake_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=[raw],
            connector_config=_cfg(cid="s27_grants_shaped"),
            grants_gov_shaped_dry_run=True,
        )
        s.commit()
    m = out["connector_manifest"]
    assert m["counts"].get("fixture_rows") is None
    assert m["counts"]["source_rows"] == 1
    si = m.get("source_identifiers") or {}
    assert si.get("connector_shape") == GRANTS_GOV_SHAPED_CONNECTOR_KEY
    assert m["counts"]["normalized_candidates"] == 1
    json.dumps(m)


def test_source_check_manifest_ids_and_evidence_hints() -> None:
    oid, sid = _seed_org_and_source()
    dl = datetime.now(UTC) + timedelta(days=40)
    rows = [
        {
            "opportunity_title": "S27 source-check manifest",
            "agency": "Illustrative Agency",
            "award_type": GrantAwardType.grant.value,
            "opportunity_source_type": OpportunitySourceType.federal.value,
            "opportunity_number": "S27-SCR-001",
            "source_url": "https://example.test/s27/scr",
            "tribal_eligible": True,
            "application_deadline": dl.isoformat(),
        }
    ]
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=rows,
            connector_config=_cfg(),
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()
    m = out["connector_manifest"]
    scr = out["source_check_run"]
    intake = out["intake_run"]
    assert m["ids"]["source_registry_id"] == str(sid)
    assert m["ids"]["source_check_run_id"] == scr["id"]
    assert m["ids"]["intake_run_id"] == intake["id"]
    hints = m["evidence_pack_subject_hints"]
    assert hints["opportunity_source"]["subject_id"] == str(sid)
    assert hints["source_check_run"]["subject_id"] == scr["id"]
    assert hints["intake_run"]["subject_id"] == intake["id"]


def test_review_required_counts_keyword_and_ambiguous_rows() -> None:
    oid, sid = _seed_org_and_source()
    kw = load_category_rows("keyword_only_false_positive")
    amb = load_category_rows("ambiguous_eligibility_case")
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out_kw = static_fixture_connector_intake_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=kw,
            connector_config=_cfg(cid="s27_kw"),
        )
        out_am = static_fixture_connector_intake_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=amb,
            connector_config=_cfg(cid="s27_amb"),
        )
        s.commit()
    assert out_kw["connector_manifest"]["counts"]["review_required"] >= 1
    assert out_am["connector_manifest"]["counts"]["review_required"] >= 1


def test_duplicate_fixture_rows_manifest_duplicate_count() -> None:
    oid, sid = _seed_org_and_source()
    dl = datetime.now(UTC) + timedelta(days=55)
    url = "https://example.test/s27/dup-manifest"
    row = {
        "opportunity_title": "S27 dup manifest",
        "agency": "Illustrative Agency",
        "award_type": GrantAwardType.grant.value,
        "opportunity_source_type": OpportunitySourceType.federal.value,
        "opportunity_number": "S27-DUP-M1",
        "source_url": url,
        "tribal_eligible": True,
        "eligibility_tags": ["tribal_eligible"],
        "application_deadline": dl.isoformat(),
    }
    rows = [row, dict(row)]
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = static_fixture_connector_intake_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=rows,
            connector_config=_cfg(cid="s27_dup"),
        )
        s.commit()
    m = out["connector_manifest"]
    assert m["counts"]["duplicate"] == 1
    assert m["counts"]["accepted"] == 1
    assert m["counts"]["accepted"] + m["counts"]["duplicate"] == 2


def test_failure_manifest_no_accepted_and_has_warning_codes() -> None:
    oid, sid = _seed_org_and_source()
    rows = [
        {
            "opportunity_title": "",
            "agency": "X",
            "award_type": GrantAwardType.grant.value,
            "opportunity_source_type": OpportunitySourceType.federal.value,
        }
    ]
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=rows,
            connector_config=_cfg(cid="s27_bad"),
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()
    assert out["intake_run"] is None
    assert out["source_check_run"]["check_status"] == SourceCheckRunStatus.failed.value
    m = out["connector_manifest"]
    assert m["counts"]["accepted"] == 0
    assert m["counts"]["normalization_errors"] >= 1
    assert m["health_status"] == "failed"
    assert "fixture_normalization_failed" in m["warning_codes"]
    json.dumps(m)


@pytest.mark.parametrize(
    "path",
    [
        CONNECTOR_ROOT / "connector_run_manifest.py",
        CONNECTOR_ROOT / "connector_diagnostics.py",
    ],
)
def test_no_forbidden_network_imports(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for sub in _FORBIDDEN:
        assert sub not in text, f"{path.name} must not mention {sub!r}"
