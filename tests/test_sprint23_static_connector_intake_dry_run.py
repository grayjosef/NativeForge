"""Sprint 23: static fixture connector → discovery intake (service-level, offline)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any, cast

import pytest

from nativeforge.db.models import NfDiscoveryIntakeCandidate, Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    DiscoveryCandidateStatus,
    GrantAwardType,
    OpportunitySourceType,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import discovery_intake_runs as intake_repo
from nativeforge.services.opportunity_discovery_service import (
    OpportunitySourcePayload,
    create_opportunity_source,
)
from nativeforge.services.source_connectors.base import (
    ConnectorRunContext,
    ConnectorSourceConfig,
)
from nativeforge.services.source_connectors.intake_bridge import (
    IntakeBridgeFixtureError,
    static_fixture_connector_intake_dry_run,
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
                source_name="Sprint 23 bridge source",
                source_type=OpportunitySourceType.federal,
                scope_global=True,
            ),
        )
        s.commit()
        return oid, src.id


def _candidates_for_run(
    session: Any,
    org_id: uuid.UUID,
    run_id: uuid.UUID,
) -> list[NfDiscoveryIntakeCandidate]:
    return intake_repo.list_discovery_intake_candidates_for_run(
        session=session,
        org_id=org_id,
        org_type="demo",
        intake_run_id=run_id,
    )


def test_intake_bridge_completes_run_with_tribal_fixture() -> None:
    oid, sid = _seed_org_and_source()
    dl = datetime.now(UTC) + timedelta(days=90)
    rows = [
        {
            "opportunity_title": "Tribal transportation set-aside (fixture)",
            "agency": "Illustrative DOT",
            "award_type": GrantAwardType.grant.value,
            "opportunity_source_type": OpportunitySourceType.federal.value,
            "opportunity_number": "S23-TSA-001",
            "source_url": "https://example.test/s23/tribal-only",
            "tribal_set_aside": True,
            "tribal_eligible": True,
            "application_deadline": dl.isoformat(),
        }
    ]
    cfg = ConnectorSourceConfig(
        connector_id="sprint23_fixture",
        source_name="bridge",
        publisher_name="Illustrative DOT",
    )
    ctx = ConnectorRunContext(run_id="bridge-run-1", dry_run=True)
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = static_fixture_connector_intake_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=rows,
            connector_config=cfg,
            run_context=ctx,
            operator_note="sprint23",
        )
        s.commit()
        assert out["intake_run"]["run_status"] == "completed"
        assert int(out["intake_run"]["accepted_count"]) >= 1
        rid = uuid.UUID(out["intake_run"]["id"])
        rows_db = _candidates_for_run(s, oid, rid)
        assert len(rows_db) == 1
        assert rows_db[0].candidate_status == DiscoveryCandidateStatus.accepted.value


def test_intake_bridge_duplicate_matches_existing_intake_behavior() -> None:
    oid, sid = _seed_org_and_source()
    dl = datetime.now(UTC) + timedelta(days=60)
    dup_url = "https://example.test/s23/dup-target"
    rows = [
        {
            "opportunity_title": "Duplicate probe opportunity",
            "agency": "Illustrative Agency",
            "award_type": GrantAwardType.grant.value,
            "opportunity_source_type": OpportunitySourceType.federal.value,
            "opportunity_number": "S23-DUP-001",
            "source_url": dup_url,
            "tribal_eligible": True,
            "eligibility_tags": ["tribal_eligible"],
            "application_deadline": dl.isoformat(),
        },
        {
            "opportunity_title": "Duplicate probe opportunity",
            "agency": "Illustrative Agency",
            "award_type": GrantAwardType.grant.value,
            "opportunity_source_type": OpportunitySourceType.federal.value,
            "opportunity_number": "S23-DUP-001",
            "source_url": dup_url,
            "tribal_eligible": True,
            "application_deadline": dl.isoformat(),
        },
    ]
    cfg = ConnectorSourceConfig(
        connector_id="s23_dup", source_name="x", publisher_name="Illustrative Agency"
    )
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = static_fixture_connector_intake_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=rows,
            connector_config=cfg,
        )
        s.commit()
        assert out["intake_run"]["accepted_count"] == 1
        assert out["intake_run"]["duplicate_count"] == 1
        rid = uuid.UUID(out["intake_run"]["id"])
        cands = _candidates_for_run(s, oid, rid)
        st = {c.candidate_status for c in cands}
        assert DiscoveryCandidateStatus.accepted.value in st
        assert DiscoveryCandidateStatus.duplicate.value in st


def test_keyword_only_connector_relevance_not_confirmed_on_raw_json() -> None:
    oid, sid = _seed_org_and_source()
    rows = [
        {
            "opportunity_title": "Native innovation prize for municipalities",
            "agency": "Illustrative Agency",
            "award_type": GrantAwardType.grant.value,
            "opportunity_source_type": OpportunitySourceType.federal.value,
            "opportunity_number": "S23-KW-001",
            "source_url": "https://example.test/s23/kw-only",
            "tribal_eligible": False,
        }
    ]
    cfg = ConnectorSourceConfig(
        connector_id="s23_kw", source_name="x", publisher_name="Illustrative Agency"
    )
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = static_fixture_connector_intake_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=rows,
            connector_config=cfg,
        )
        s.commit()
        rid = uuid.UUID(out["intake_run"]["id"])
        cands = _candidates_for_run(s, oid, rid)
        assert len(cands) == 1
        raw = cands[0].raw_candidate_json
        assert isinstance(raw, dict)
        nr = raw.get("connector_native_relevance_v1")
        assert isinstance(nr, dict)
        assert nr.get("eligibility_confidence") != "confirmed"
        assert nr.get("review_required") is True


def test_connector_provenance_preserved_raw_and_normalized_extras() -> None:
    oid, sid = _seed_org_and_source()
    dl = datetime.now(UTC) + timedelta(days=30)
    rows = [
        {
            "opportunity_title": "Provenance check opportunity",
            "agency": "Illustrative Agency",
            "award_type": GrantAwardType.grant.value,
            "opportunity_source_type": OpportunitySourceType.federal.value,
            "opportunity_number": "S23-PROV-001",
            "source_url": "https://example.test/s23/prov",
            "tribal_eligible": True,
            "application_deadline": dl.isoformat(),
        }
    ]
    cfg = ConnectorSourceConfig(
        connector_id="s23_prov",
        source_name="bridge",
        publisher_name="Illustrative Agency",
    )
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        out = static_fixture_connector_intake_dry_run(
            s,
            org=org,
            org_type=cast(OrgType, org.org_type),
            source_registry_id=sid,
            fixture_rows=rows,
            connector_config=cfg,
        )
        s.commit()
        rid = uuid.UUID(out["intake_run"]["id"])
        c = _candidates_for_run(s, oid, rid)[0]
        raw = c.raw_candidate_json
        assert isinstance(raw, dict)
        prov = raw.get("connector_provenance_v1")
        assert isinstance(prov, dict)
        assert prov.get("connector_id") == "s23_prov"
        assert prov.get("fixture_connector") == "static_fixture"
        norm = c.normalized_candidate_json
        assert isinstance(norm, dict)
        extras = norm.get("extras")
        assert isinstance(extras, dict)
        assert "connector_provenance_v1" in extras
        assert "connector_native_relevance_v1" in extras


def test_bridge_raises_on_bad_fixture_row() -> None:
    oid, sid = _seed_org_and_source()
    rows: list[dict[str, Any]] = [
        {
            "opportunity_title": "",
            "agency": "X",
            "award_type": GrantAwardType.grant.value,
            "opportunity_source_type": OpportunitySourceType.federal.value,
        }
    ]
    cfg = ConnectorSourceConfig(connector_id="bad", source_name="x", publisher_name="X")
    with SessionLocal() as s:
        org = s.get(Organization, oid)
        assert org is not None
        with pytest.raises(IntakeBridgeFixtureError):
            static_fixture_connector_intake_dry_run(
                s,
                org=org,
                org_type=cast(OrgType, org.org_type),
                source_registry_id=sid,
                fixture_rows=rows,
                connector_config=cfg,
            )


def test_intake_bridge_module_has_no_forbidden_imports() -> None:
    text = (CONNECTOR_ROOT / "intake_bridge.py").read_text(encoding="utf-8")
    for bad in _FORBIDDEN:
        assert f"import {bad}" not in text
        assert f"from {bad}" not in text
