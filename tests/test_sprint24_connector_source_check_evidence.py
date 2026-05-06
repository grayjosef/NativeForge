"""Sprint 24: source-check-backed connector dry run + evidence traceability."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    DiscoveryCandidateStatus,
    EvidencePackSubjectType,
    GrantAwardType,
    OpportunitySourceType,
    SourceCheckMode,
    SourceCheckRunStatus,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import discovery_intake_runs as intake_repo
from nativeforge.services.discovery_evidence_pack_service import (
    build_discovery_evidence_pack,
)
from nativeforge.services.opportunity_discovery_service import (
    OpportunitySourcePayload,
    create_opportunity_source,
)
from nativeforge.services.source_connectors.base import (
    ConnectorRunContext,
    ConnectorSourceConfig,
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
                source_name="Sprint 24 connector source",
                source_type=OpportunitySourceType.federal,
                scope_global=True,
            ),
        )
        s.commit()
        return oid, src.id


def _fixture_row(*, suffix: str = "001") -> dict[str, Any]:
    dl = datetime.now(UTC) + timedelta(days=60)
    return {
        "opportunity_title": f"S24 provenance opportunity {suffix}",
        "agency": "Illustrative Agency",
        "award_type": GrantAwardType.grant.value,
        "opportunity_source_type": OpportunitySourceType.federal.value,
        "opportunity_number": f"S24-{suffix}",
        "source_url": f"https://example.test/s24/{suffix}",
        "tribal_eligible": True,
        "application_deadline": dl.isoformat(),
    }


def test_source_check_backed_run_completes_and_links_intake() -> None:
    oid, sid = _seed_org_and_source()
    cfg = ConnectorSourceConfig(
        connector_id="s24_bridge",
        source_name="s24",
        publisher_name="Illustrative Agency",
    )
    ctx = ConnectorRunContext(run_id="s24-run-1", dry_run=True)
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=[_fixture_row()],
            connector_config=cfg,
            run_context=ctx,
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    scr = out["source_check_run"]
    assert scr["check_status"] == SourceCheckRunStatus.succeeded.value
    assert scr["completed_at"] is not None
    assert uuid.UUID(scr["source_registry_id"]) == sid

    intake = out["intake_run"]
    assert intake is not None
    assert uuid.UUID(intake["source_registry_id"]) == sid

    m = out["connector_manifest"]
    assert m["schema_version"] == "nf_connector_run_manifest_v1"
    assert m["dry_run"] is True
    assert m["ids"]["source_registry_id"] == str(sid)
    assert m["ids"]["intake_run_id"] == intake["id"]
    assert m["ids"]["source_check_run_id"] == scr["id"]
    assert "generated_at" in m
    assert "timestamps" in m and "manifest_generated_at" in m["timestamps"]
    assert m["counts"]["fixture_rows"] >= 1

    assert out["connector_health"] == "healthy"
    cc = out["candidate_counts"]
    assert cc["accepted_count"] >= 1


def test_zero_row_fixture_empty_health() -> None:
    oid, sid = _seed_org_and_source()
    cfg = ConnectorSourceConfig(
        connector_id="s24_empty", source_name="x", publisher_name="X"
    )
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=[],
            connector_config=cfg,
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    assert (
        out["source_check_run"]["check_status"] == SourceCheckRunStatus.succeeded.value
    )
    assert out["connector_health"] == "empty"
    assert out["candidate_counts"]["candidate_count"] == 0


def test_fixture_normalization_failure_failed_health_no_intake() -> None:
    oid, sid = _seed_org_and_source()
    cfg = ConnectorSourceConfig(
        connector_id="s24_bad", source_name="x", publisher_name="X"
    )
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
            connector_config=cfg,
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    assert out["intake_run"] is None
    assert out["source_check_run"]["check_status"] == SourceCheckRunStatus.failed.value
    assert out["connector_health"] == "failed"
    m = out["connector_manifest"]
    assert m["ids"]["intake_run_id"] is None
    assert m["ids"]["source_check_run_id"] == out["source_check_run"]["id"]


def test_duplicate_only_run_is_degraded() -> None:
    oid, sid = _seed_org_and_source()
    row = _fixture_row(suffix="dup")
    cfg = ConnectorSourceConfig(
        connector_id="s24_dup", source_name="x", publisher_name="Illustrative Agency"
    )
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
    assert out2["candidate_counts"]["accepted_count"] == 0
    assert out2["candidate_counts"]["duplicate_count"] >= 1


def test_provenance_survives_payloads_and_evidence_pack_traceability() -> None:
    oid, sid = _seed_org_and_source()
    cfg = ConnectorSourceConfig(
        connector_id="s24_ev",
        source_name="s24",
        publisher_name="Illustrative Agency",
    )
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=[_fixture_row()],
            connector_config=cfg,
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    intake_id = uuid.UUID(cast(dict, out["intake_run"])["id"])
    scr_id = uuid.UUID(cast(dict, out["source_check_run"])["id"])

    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        cands = intake_repo.list_discovery_intake_candidates_for_run(
            session=s,
            org_id=oid,
            org_type="demo",
            intake_run_id=intake_id,
        )
        accepted = [
            c
            for c in cands
            if c.candidate_status == DiscoveryCandidateStatus.accepted.value
        ]
        assert len(accepted) == 1
        raw = accepted[0].raw_candidate_json
        assert isinstance(raw, dict)
        prov = raw.get("connector_provenance_v1")
        assert isinstance(prov, dict)
        assert prov.get("source_check_run_id") == str(scr_id)

        norm = accepted[0].normalized_candidate_json
        assert isinstance(norm, dict)
        extras = norm.get("extras")
        assert isinstance(extras, dict)
        assert "connector_provenance_v1" in extras

        pack_src = build_discovery_evidence_pack(
            s,
            org=org,
            org_type="demo",
            subject_type=EvidencePackSubjectType.opportunity_source,
            subject_id=sid,
            include_audit_trail=False,
            include_sections=False,
        )
        linked = pack_src["linked_records"]
        scr_sample = linked.get("source_check_runs_sample", [])
        scr_ids = {str(r["id"]) for r in scr_sample if isinstance(r, dict)}
        intake_sample = linked.get("intake_runs_sample", [])
        intake_ids = {str(r["id"]) for r in intake_sample if isinstance(r, dict)}
        assert str(scr_id) in scr_ids
        assert str(intake_id) in intake_ids

        pack_ir = build_discovery_evidence_pack(
            s,
            org=org,
            org_type="demo",
            subject_type=EvidencePackSubjectType.intake_run,
            subject_id=intake_id,
            include_audit_trail=False,
            include_sections=False,
        )
        sample = pack_ir["linked_records"]["candidates_sample"]

        def _prov_scr(c: object) -> str | None:
            if not isinstance(c, dict):
                return None
            raw = c.get("raw_candidate_json")
            if not isinstance(raw, dict):
                return None
            prov = raw.get("connector_provenance_v1")
            if not isinstance(prov, dict):
                return None
            sid = prov.get("source_check_run_id")
            return str(sid) if sid is not None else None

        assert any(_prov_scr(c) == str(scr_id) for c in sample)

        pack_chk = build_discovery_evidence_pack(
            s,
            org=org,
            org_type="demo",
            subject_type=EvidencePackSubjectType.source_check_run,
            subject_id=scr_id,
            include_audit_trail=False,
            include_sections=False,
        )
        assert pack_chk["subject"]["intake_run_id"] == str(intake_id)
        rs = pack_chk["linked_records"]["source_check_run"].get("result_summary_json")
        assert isinstance(rs, dict)
        assert rs.get("intake_run_id") == str(intake_id)


def test_source_check_bridge_has_no_forbidden_imports() -> None:
    text = (CONNECTOR_ROOT / "source_check_bridge.py").read_text(encoding="utf-8")
    for bad in _FORBIDDEN:
        assert f"import {bad}" not in text
        assert f"from {bad}" not in text
