"""Sprint 30: discovery connector closeout — end-to-end validation (no network)."""

from __future__ import annotations

import json
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
from nativeforge.repositories import operator_actions as oa_repo
from nativeforge.services.opportunity_discovery_service import (
    OpportunitySourcePayload,
    create_opportunity_source,
)
from nativeforge.services.source_connectors.base import ConnectorSourceConfig
from nativeforge.services.source_connectors.connector_diagnostics import (
    RESULT_SUMMARY_SCHEMA_VERSION,
    manifest_counts_intake_consistent,
)
from nativeforge.services.source_connectors.connector_operator_escalation import (
    CONNECTOR_OPERATOR_ESCALATION_SCHEMA_VERSION,
    escalation_recommendations_json_safe,
)
from nativeforge.services.source_connectors.fixture_corpus import (
    CORPUS_SCHEMA_VERSION,
    assert_complete_required_corpus,
    load_all_corpus_rows_flat,
    load_category_rows,
    validate_corpus_categories_present,
)
from nativeforge.services.source_connectors.grants_gov_shaped import (
    GRANTS_GOV_SHAPED_CONNECTOR_KEY,
    dry_run_grants_gov_shaped_rows,
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
CONNECTOR_MODULES = sorted(CONNECTOR_ROOT.glob("*.py"))

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
                source_name="Sprint 30 connector closeout source",
                source_type=OpportunitySourceType.federal,
                scope_global=True,
            ),
        )
        s.commit()
        return oid, src.id


def _fixture_row(*, suffix: str = "001") -> dict[str, Any]:
    dl = datetime.now(UTC) + timedelta(days=60)
    return {
        "opportunity_title": f"S30 provenance opportunity {suffix}",
        "agency": "Illustrative Agency",
        "award_type": GrantAwardType.grant.value,
        "opportunity_source_type": OpportunitySourceType.federal.value,
        "opportunity_number": f"S30-{suffix}",
        "source_url": f"https://example.test/s30/{suffix}",
        "tribal_eligible": True,
        "application_deadline": dl.isoformat(),
    }


def _cfg(*, cid: str = "s30") -> ConnectorSourceConfig:
    return ConnectorSourceConfig(
        connector_id=cid,
        source_name="s30",
        publisher_name="Illustrative Agency",
    )


def _assert_counts_aligned(out: dict[str, Any]) -> None:
    m = cast(dict[str, Any], out["connector_manifest"])
    rs = cast(dict[str, Any], out["source_check_run"]["result_summary_json"])
    cc = cast(dict[str, Any], out["candidate_counts"])
    mc = cast(dict[str, Any], m["counts"])
    sm = cast(dict[str, Any], rs["counts"])

    assert rs["health_status"] == out["connector_health"] == m["health_status"]
    assert rs["manifest_counts"] == mc
    assert int(sm["accepted_count"]) == int(mc["accepted"]) == int(cc["accepted_count"])
    dup_m = int(mc["duplicate"])
    dup_cc = int(cc["duplicate_count"])
    assert int(sm["duplicate_count"]) == dup_m == dup_cc
    assert int(sm["rejected_count"]) == int(mc["rejected"]) == int(cc["rejected_count"])
    assert int(sm["error_count"]) == int(mc["error"]) == int(cc["error_count"])

    summary_counts = {
        "candidate_count": int(cc["candidate_count"]),
        "accepted_count": int(cc["accepted_count"]),
        "duplicate_count": int(cc["duplicate_count"]),
        "rejected_count": int(cc["rejected_count"]),
        "error_count": int(cc["error_count"]),
    }
    assert manifest_counts_intake_consistent(
        summary_counts=summary_counts,
        accepted=int(mc["accepted"]),
        duplicate=int(mc["duplicate"]),
        rejected=int(mc["rejected"]),
        error=int(mc["error"]),
    )


def _json_must_dump(label: str, obj: Any) -> None:
    try:
        json.dumps(obj, sort_keys=True)
    except TypeError as ex:
        raise AssertionError(f"not JSON-serializable ({label}): {ex}") from ex


def test_closeout_corpus_categories_and_bundle_integrity() -> None:
    assert_complete_required_corpus()
    report = validate_corpus_categories_present()
    assert not report["missing"] and not report["extra"]


def test_closeout_fixture_keys_unique_across_corpus() -> None:
    rows = load_all_corpus_rows_flat()
    keys = [str(r.get("fixture_key", "")) for r in rows]
    assert len(keys) == len(set(keys)), "duplicate fixture_key values in corpus"


def test_closeout_full_rich_corpus_source_check_dry_run() -> None:
    oid, sid = _seed_org_and_source()
    rows = load_all_corpus_rows_flat()
    assert len(rows) >= 12
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=rows,
            connector_config=_cfg(cid="s30_corpus_full"),
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    _assert_counts_aligned(out)
    m = out["connector_manifest"]
    rs = cast(dict[str, Any], out["source_check_run"]["result_summary_json"])
    sid_meta = cast(dict[str, Any], m.get("source_identifiers") or {})
    assert sid_meta.get("corpus_schema_version") == CORPUS_SCHEMA_VERSION
    cats = sid_meta.get("fixture_categories") or []
    assert "keyword_only_false_positive" in cats
    assert "ambiguous_eligibility_case" in cats

    esc = cast(list[dict[str, Any]], rs["operator_escalation_recommendations"])
    escalation_recommendations_json_safe(esc)
    _json_must_dump("full_corpus_manifest", m)
    _json_must_dump("full_corpus_result_summary", rs)


def test_closeout_grants_gov_shaped_category_source_check_dry_run() -> None:
    oid, sid = _seed_org_and_source()
    rows = load_category_rows("grants_gov_broad_tribal_eligible")
    assert rows
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=rows,
            connector_config=_cfg(cid="s30_gg_shaped"),
            check_mode=SourceCheckMode.manual.value,
            grants_gov_shaped_dry_run=True,
        )
        s.commit()

    _assert_counts_aligned(out)
    m = cast(dict[str, Any], out["connector_manifest"])
    assert m["counts"].get("fixture_rows") is None
    assert m["counts"].get("source_rows") == len(rows)
    rs = cast(dict[str, Any], out["source_check_run"]["result_summary_json"])
    assert rs["counts"].get("source_rows") == len(rows)
    sid_meta = cast(dict[str, Any], m.get("source_identifiers") or {})
    assert sid_meta.get("connector_shape") == GRANTS_GOV_SHAPED_CONNECTOR_KEY

    hints = cast(dict[str, Any], m["evidence_pack_subject_hints"])
    assert "opportunity_source" in hints
    assert "source_check_run" in hints
    assert "intake_run" in hints

    esc = rs["operator_escalation_recommendations"]
    assert isinstance(esc, list)
    if esc:
        first = esc[0]
        assert (
            first.get("schema_version") == CONNECTOR_OPERATOR_ESCALATION_SCHEMA_VERSION
        )
        subj = cast(
            list[dict[str, Any]],
            first.get("evidence_pack_subject_hints") or [],
        )
        types = {h.get("subject_type") for h in subj}
        assert "source_check_run" in types
        assert "opportunity_source" in types
        assert "intake_run" in types

    _json_must_dump("gg_shaped_manifest", m)
    _json_must_dump("gg_shaped_result_summary", rs)


def test_closeout_healthy_run_no_action_creation_escalation() -> None:
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
            connector_config=_cfg(cid="s30_healthy"),
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    assert out["connector_health"] == "healthy"
    rs = cast(dict[str, Any], out["source_check_run"]["result_summary_json"])
    esc = cast(list[dict[str, Any]], rs["operator_escalation_recommendations"])
    assert all(not r.get("should_create_action") for r in esc)

    m = cast(dict[str, Any], out["connector_manifest"])
    hints = cast(dict[str, Any], m["evidence_pack_subject_hints"])
    assert hints["opportunity_source"]["subject_id"] == str(sid)
    assert hints["intake_run"]["subject_id"] == out["intake_run"]["id"]
    assert hints["source_check_run"]["subject_id"] == out["source_check_run"]["id"]
    _json_must_dump("healthy_manifest", m)
    _json_must_dump("healthy_summary", rs)


def test_closeout_normalization_failure_manifest_health_escalation() -> None:
    oid, sid = _seed_org_and_source()
    bad_rows = [
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
            fixture_rows=bad_rows,
            connector_config=_cfg(cid="s30_norm_fail"),
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    assert out["connector_health"] == "failed"
    assert out["intake_run"] is None
    m = cast(dict[str, Any], out["connector_manifest"])
    rs = cast(dict[str, Any], out["source_check_run"]["result_summary_json"])
    assert m["health_status"] == rs["health_status"] == "failed"
    assert int(m["counts"]["accepted"]) == 0
    assert int(rs["counts"]["accepted_count"]) == 0
    assert "fixture_normalization_failed" in m["warning_codes"]

    esc = cast(list[dict[str, Any]], rs["operator_escalation_recommendations"])
    assert any(e["escalation_type"] == "normalization_mapping_failure" for e in esc)
    assert any(e.get("should_create_action") for e in esc)

    ev = cast(dict[str, Any], esc[0].get("evidence_refs") or {})
    assert "source_identifiers" in ev
    cm = cast(dict[str, Any], ev.get("source_identifiers") or {})
    assert cm.get("connector_shape") == "static_fixture"
    if m.get("connector_run_id"):
        assert ev.get("connector_run_id") == m.get("connector_run_id")

    subj = cast(list[dict[str, Any]], esc[0].get("evidence_pack_subject_hints") or [])
    stypes = {h.get("subject_type") for h in subj}
    assert "source_check_run" in stypes
    assert "opportunity_source" in stypes
    assert "intake_run" not in stypes

    _json_must_dump("norm_fail_manifest", m)
    _json_must_dump("norm_fail_summary", rs)


def test_closeout_empty_run_health_and_coverage_escalation() -> None:
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
            connector_config=_cfg(cid="s30_empty"),
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    assert out["connector_health"] == "empty"
    m = cast(dict[str, Any], out["connector_manifest"])
    rs = cast(dict[str, Any], out["source_check_run"]["result_summary_json"])
    assert m["health_status"] == rs["health_status"] == "empty"
    assert "connector_run_empty" in m["warning_codes"]
    esc = cast(list[dict[str, Any]], rs["operator_escalation_recommendations"])
    assert any(e["escalation_type"] == "source_coverage_verification" for e in esc)
    _json_must_dump("empty_manifest", m)
    _json_must_dump("empty_summary", rs)


def test_closeout_stale_source_health_and_freshness_escalation() -> None:
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
            connector_config=_cfg(cid="s30_stale"),
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    assert out["connector_health"] == "stale"
    rs = cast(dict[str, Any], out["source_check_run"]["result_summary_json"])
    esc = cast(list[dict[str, Any]], rs["operator_escalation_recommendations"])
    assert any(e["escalation_type"] == "source_freshness_verification" for e in esc)
    assert rs["health_status"] == "stale"
    _json_must_dump("stale_summary", rs)


def test_closeout_create_operator_actions_default_skips_persistence() -> None:
    oid, sid = _seed_org_and_source()
    bad_rows = [
        {
            "opportunity_title": "",
            "agency": "X",
            "award_type": GrantAwardType.grant.value,
            "opportunity_source_type": OpportunitySourceType.federal.value,
        }
    ]
    with SessionLocal() as s:
        before = len(
            oa_repo.list_operator_actions_for_org(
                s, org_id=oid, org_type="demo", limit=500
            )
        )

    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = run_source_check_backed_connector_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=bad_rows,
            connector_config=_cfg(cid="s30_no_persist"),
            check_mode=SourceCheckMode.manual.value,
        )
        s.commit()

    assert "operator_actions_created" not in out
    with SessionLocal() as s:
        after = len(
            oa_repo.list_operator_actions_for_org(
                s, org_id=oid, org_type="demo", limit=500
            )
        )
    assert after == before


@pytest.mark.parametrize("path", CONNECTOR_MODULES)
def test_closeout_no_forbidden_network_imports_in_connector_modules(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    for bad in _FORBIDDEN:
        assert f"import {bad}" not in text
        assert f"from {bad}" not in text


def test_closeout_grants_gov_shaped_stable_duplicate_opportunity_keys() -> None:
    """Duplicate OpportunityNumber rows share the same normalization local_key."""
    dl = datetime.now(UTC) + timedelta(days=30)
    dup_num = "CORPUS-DUP-STABLE-030"
    raw_rows = [
        {
            "Title": "First title",
            "agencyName": "Agency A",
            "OpportunityNumber": dup_num,
            "OpportunityURL": "https://example.test/dup-a",
            "FundingInstrumentType": "Grant",
            "CloseDate": dl.isoformat(),
            "synopsis": "Tribal governments may apply.",
        },
        {
            "Title": "Second title",
            "agencyName": "Agency B",
            "OpportunityNumber": dup_num,
            "OpportunityURL": "https://example.test/dup-b",
            "FundingInstrumentType": "Grant",
            "CloseDate": dl.isoformat(),
            "synopsis": "Federally recognized tribes eligible.",
        },
    ]
    cfg = _cfg(cid="s30_dup_keys")
    dry = dry_run_grants_gov_shaped_rows(raw_rows, config=cfg)
    assert not dry.errors
    keys = [c.local_key for c in dry.candidates]
    assert keys == [dup_num, dup_num]


def test_closeout_result_summary_schema_constants() -> None:
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
    rs = cast(dict[str, Any], out["source_check_run"]["result_summary_json"])
    assert (
        rs["connector_result_summary_schema_version"] == RESULT_SUMMARY_SCHEMA_VERSION
    )
    assert (
        rs["connector_operator_escalation_schema_version"]
        == CONNECTOR_OPERATOR_ESCALATION_SCHEMA_VERSION
    )
