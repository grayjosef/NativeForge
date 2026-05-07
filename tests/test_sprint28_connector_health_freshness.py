"""Sprint 28: connector dry-run health, freshness overlay, source-check summaries."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from nativeforge.db.models import NfOpportunitySource, Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    GrantAwardType,
    OpportunitySourceType,
    SourceCheckMode,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.services.opportunity_discovery_service import (
    OpportunitySourcePayload,
    create_opportunity_source,
)
from nativeforge.services.source_connectors.base import (
    ConnectorSourceConfig,
)
from nativeforge.services.source_connectors.connector_diagnostics import (
    RESULT_SUMMARY_SCHEMA_VERSION,
)
from nativeforge.services.source_connectors.fixture_corpus import load_category_rows
from nativeforge.services.source_connectors.grants_gov_shaped import (
    GRANTS_GOV_SHAPED_CONNECTOR_KEY,
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
                source_name="Sprint 28 connector source",
                source_type=OpportunitySourceType.federal,
                scope_global=True,
            ),
        )
        s.commit()
        return oid, src.id


def _fixture_row(*, suffix: str = "001") -> dict[str, Any]:
    dl = datetime.now(UTC) + timedelta(days=60)
    return {
        "opportunity_title": f"S28 provenance opportunity {suffix}",
        "agency": "Illustrative Agency",
        "award_type": GrantAwardType.grant.value,
        "opportunity_source_type": OpportunitySourceType.federal.value,
        "opportunity_number": f"S28-{suffix}",
        "source_url": f"https://example.test/s28/{suffix}",
        "tribal_eligible": True,
        "application_deadline": dl.isoformat(),
    }


def _cfg(*, cid: str = "s28") -> ConnectorSourceConfig:
    return ConnectorSourceConfig(
        connector_id=cid,
        source_name="s28",
        publisher_name="Illustrative Agency",
    )


def test_accepted_rows_healthy_and_summary_aligned() -> None:
    oid, sid = _seed_org_and_source()
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=[_fixture_row()],
            connector_config=_cfg(),
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    m = out["connector_manifest"]
    rs = out["source_check_run"]["result_summary_json"]
    assert isinstance(rs, dict)
    assert (
        rs["connector_result_summary_schema_version"] == RESULT_SUMMARY_SCHEMA_VERSION
    )
    assert rs["health_status"] == "healthy"
    assert rs["health_status"] == m["health_status"]
    assert rs["counts"]["accepted_count"] == m["counts"]["accepted"]
    assert rs["counts"]["accepted_count"] >= 1
    assert rs["connector_id"] == "s28"
    assert rs["source_check_run_id"] == out["source_check_run"]["id"]
    assert rs["intake_run_id"] == out["intake_run"]["id"]
    assert rs["manifest_counts"] == m["counts"]
    assert out["connector_health"] == "healthy"


def test_zero_row_fixture_empty_explicit() -> None:
    oid, sid = _seed_org_and_source()
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=[],
            connector_config=_cfg(cid="s28_empty"),
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    assert out["connector_health"] == "empty"
    m = out["connector_manifest"]
    rs = cast(dict[str, Any], out["source_check_run"]["result_summary_json"])
    assert m["health_status"] == "empty"
    assert rs["health_status"] == "empty"
    assert "connector_run_empty" in (m.get("warning_codes") or [])
    assert rs["counts"]["accepted_count"] == 0
    assert rs["counts"]["fixture_rows"] == 0


def test_duplicate_only_run_degraded() -> None:
    oid, sid = _seed_org_and_source()
    row = _fixture_row(suffix="dup")
    cfg = _cfg(cid="s28_dup")
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=[row],
            connector_config=cfg,
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out2 = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=[row],
            connector_config=cfg,
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    assert out2["connector_health"] == "degraded"
    m = out2["connector_manifest"]
    rs = cast(dict[str, Any], out2["source_check_run"]["result_summary_json"])
    assert m["health_status"] == rs["health_status"] == "degraded"
    assert out2["candidate_counts"]["duplicate_count"] >= 1
    assert out2["candidate_counts"]["accepted_count"] == 0


def test_review_required_heavy_degraded() -> None:
    oid, sid = _seed_org_and_source()
    rows = load_category_rows("keyword_only_false_positive") + load_category_rows(
        "ambiguous_eligibility_case"
    )
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=rows,
            connector_config=_cfg(cid="s28_rr"),
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    rr = out["connector_manifest"]["counts"].get("review_required") or 0
    assert rr >= 1
    assert out["connector_health"] == "degraded"
    assert "review_required_heavy" in out["connector_manifest"].get("warning_codes", [])


def test_normalization_failure_failed_and_codes() -> None:
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
            connector_config=_cfg(cid="s28_bad"),
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    assert out["connector_health"] == "failed"
    assert out["intake_run"] is None
    m = out["connector_manifest"]
    rs = cast(dict[str, Any], out["source_check_run"]["result_summary_json"])
    assert m["health_status"] == "failed"
    assert rs["health_status"] == "failed"
    assert m["counts"]["accepted"] == 0
    assert rs["counts"]["accepted_count"] == 0
    assert "fixture_normalization_failed" in m["warning_codes"]


def test_result_summary_includes_operator_message_and_ids() -> None:
    oid, sid = _seed_org_and_source()
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=[_fixture_row(suffix="rs")],
            connector_config=_cfg(cid="s28_rs"),
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    rs = cast(dict[str, Any], out["source_check_run"]["result_summary_json"])
    assert rs.get("operator_diagnostic_message")
    assert isinstance(rs["operator_diagnostic_message"], str)
    assert rs["connector_shape"] == "static_fixture"


def test_stale_when_source_overdue_before_run() -> None:
    oid, sid = _seed_org_and_source()
    with SessionLocal() as s:
        reg = s.get(NfOpportunitySource, sid)
        assert reg is not None
        reg.last_checked_at = datetime.now(UTC) - timedelta(days=100)
        reg.check_interval_days = 1
        reg.next_check_due_at = None
        s.commit()

    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=[_fixture_row(suffix="stale")],
            connector_config=_cfg(cid="s28_stale"),
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    assert out["connector_health"] == "stale"
    m = out["connector_manifest"]
    rs = cast(dict[str, Any], out["source_check_run"]["result_summary_json"])
    assert m["health_status"] == "stale"
    assert rs["health_status"] == "stale"
    assert "source_check_overdue" in m["warning_codes"]


def test_grants_gov_shaped_source_check_health_and_shape() -> None:
    oid, sid = _seed_org_and_source()
    dl = datetime.now(UTC) + timedelta(days=50)
    raw = {
        "Title": "S28 Grants.gov-shaped dry run",
        "agencyName": "Illustrative DOE",
        "OpportunityNumber": "S28-GG-001",
        "OpportunityURL": "https://example.test/s28/gg",
        "AwardType": "Grant",
        "FundingInstrumentType": "Grant",
        "PostedDate": "2025-01-01",
        "CloseDate": dl.isoformat(),
    }
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=[raw],
            connector_config=_cfg(cid="s28_gg"),
            check_mode=SourceCheckMode.manual.value,
            grants_gov_shaped_dry_run=True,
        )
        s.commit()

    m = out["connector_manifest"]
    rs = cast(dict[str, Any], out["source_check_run"]["result_summary_json"])
    assert m["source_identifiers"]["connector_shape"] == GRANTS_GOV_SHAPED_CONNECTOR_KEY
    assert rs["connector_shape"] == GRANTS_GOV_SHAPED_CONNECTOR_KEY
    assert m["counts"].get("source_rows") == 1
    assert out["connector_health"] in ("healthy", "degraded", "stale")
    assert rs["health_status"] == m["health_status"]


@pytest.mark.parametrize(
    "path",
    [
        CONNECTOR_ROOT / "connector_health.py",
        CONNECTOR_ROOT / "source_check_bridge.py",
        CONNECTOR_ROOT / "connector_run_manifest.py",
    ],
)
def test_no_forbidden_network_imports(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for bad in _FORBIDDEN:
        assert f"import {bad}" not in text
        assert f"from {bad}" not in text
