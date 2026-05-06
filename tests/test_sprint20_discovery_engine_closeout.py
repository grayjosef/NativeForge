"""Sprint 20: discovery closeout tests — routes, migrations, export, offline guard."""

from __future__ import annotations

import re
import subprocess
import uuid
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import (
    DiscoveryIntakeMode,
    GrantAwardType,
    OpportunitySourceType,
    OpportunityVerificationStatus,
    SourceCheckMode,
    SourceCheckRunStatus,
)
from nativeforge.lib.settings import get_settings
from nativeforge.main import create_app
from nativeforge.services.discovery_coverage_gap_service import (
    SCHEMA_VERSION as COVERAGE_GAP_SCHEMA_VERSION,
)
from nativeforge.services.discovery_evidence_pack_service import (
    EVIDENCE_PACK_SCHEMA_VERSION,
)
from nativeforge.services.discovery_operator_workbench_service import (
    DECISION_PACK_SCHEMA_VERSION,
)
from nativeforge.services.discovery_quality_service import QUALITY_SCHEMA_VERSION
from nativeforge.services.operator_action_service import (
    NF_OPERATOR_ACTION_SCHEMA_VERSION,
)
from nativeforge.services.source_freshness_service import (
    FRESHNESS_DETAIL_SCHEMA_VERSION,
    SUMMARY_SCHEMA_VERSION,
)
from nativeforge.services.trust_surface_service import ORG_DATA_SNAPSHOT_VERSION

ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_VERSIONS = ROOT / "alembic" / "versions"

DISCOVERY_ROUTE_SUBSTRINGS = (
    "/discovery/sources",
    "/discovery/review-items",
    "/discovery/sources/due",
    "/discovery/sources/overdue",
    "/discovery/coverage-gap-intelligence",
    "/discovery/coverage-gaps",
    "/discovery/source-recommendations",
    "/discovery/operator-decision-pack",
    "/discovery/operator-workbench",
    "/discovery/operator-actions",
    "/discovery/operator-actions-ledger",
    "/discovery/evidence-pack",
)

OFFLINE_SERVICE_FILES = (
    ROOT / "src/nativeforge/services/discovery_review_service.py",
    ROOT / "src/nativeforge/services/discovery_intake_service.py",
    ROOT / "src/nativeforge/services/source_freshness_service.py",
    ROOT / "src/nativeforge/services/discovery_coverage_gap_service.py",
    ROOT / "src/nativeforge/services/discovery_operator_workbench_service.py",
    ROOT / "src/nativeforge/services/operator_action_service.py",
    ROOT / "src/nativeforge/services/discovery_evidence_pack_service.py",
)


def _hdr(oid: uuid.UUID) -> dict[str, str]:
    return {"X-NF-Org-Id": str(oid)}


@pytest.fixture
def client_nf(monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setenv("NF_DEV_ORG_HEADERS", "true")
    get_settings.cache_clear()
    yield TestClient(create_app())
    get_settings.cache_clear()


def _discovery_route_paths(app) -> list[str]:
    out: list[str] = []
    for r in app.routes:
        if isinstance(r, APIRoute):
            out.append(r.path)
    return out


def test_discovery_route_families_registered_demo_and_real() -> None:
    app = create_app()
    paths = _discovery_route_paths(app)
    for sub in DISCOVERY_ROUTE_SUBSTRINGS:
        matches = [p for p in paths if sub in p]
        msg = f"expected demo+real routes containing {sub!r}, got {matches!r}"
        assert len(matches) >= 2, msg


def test_demo_real_planes_distinct_prefixes() -> None:
    app = create_app()
    paths = _discovery_route_paths(app)
    demo = [
        p for p in paths if p.startswith("/v1/nf/demo/orgs/") and "/discovery/" in p
    ]
    real = [
        p for p in paths if p.startswith("/v1/nf/real/orgs/") and "/discovery/" in p
    ]
    assert len(demo) >= 10
    assert len(real) >= 10
    assert set(demo).isdisjoint(set(real))


def test_schema_version_constants_match_documented_sprint20_values() -> None:
    assert QUALITY_SCHEMA_VERSION == "nf_discovery_quality_v1"
    assert COVERAGE_GAP_SCHEMA_VERSION == "nf_discovery_coverage_gap_intelligence_v1"
    assert DECISION_PACK_SCHEMA_VERSION == "nf_discovery_operator_decision_pack_v1"
    assert EVIDENCE_PACK_SCHEMA_VERSION == "nf_discovery_evidence_pack_v1"
    assert NF_OPERATOR_ACTION_SCHEMA_VERSION == "nf_operator_action_v1"
    assert SUMMARY_SCHEMA_VERSION == "nf_source_freshness_summary_v1"
    assert FRESHNESS_DETAIL_SCHEMA_VERSION == "nf_source_freshness_detail_v1"
    assert ORG_DATA_SNAPSHOT_VERSION == "org_data_snapshot_v1"


def _parse_revision_ids() -> dict[str, str]:
    by_file: dict[str, str] = {}
    for path in sorted(ALEMBIC_VERSIONS.glob("*.py")):
        if path.name == "__init__.py":
            continue
        text = path.read_text(encoding="utf-8")
        m = re.search(r"^revision:\s*str\s*=\s*\"([^\"]+)\"", text, re.MULTILINE)
        if m:
            by_file[path.name] = m.group(1)
    return by_file


def test_alembic_migrations_unique_revisions_and_expected_head() -> None:
    by_file = _parse_revision_ids()
    revs = list(by_file.values())
    assert revs, "no revision strings parsed"
    counts = Counter(revs)
    dupes = {k: v for k, v in counts.items() if v > 1}
    assert not dupes, f"duplicate revision ids: {dupes}"

    result = subprocess.run(
        ["uv", "run", "alembic", "heads"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.strip() == "0018 (head)"

    sprint_discovery_files = [
        "0010_nf_opportunity_sources_discovery.py",
        "0011_nf_opportunity_sources_coverage.py",
        "0012_nf_discovery_intake.py",
        "0013_nf_discovery_review_items.py",
        "0014_discovery_review_assigned_to_text.py",
        "0015_nf_source_check_scheduling.py",
        "0018_nf_operator_action_ledger.py",
    ]
    for fn in sprint_discovery_files:
        assert (ALEMBIC_VERSIONS / fn).is_file(), f"missing {fn}"

    expected_ids = ("0010", "0011", "0012", "0013", "0014", "0015", "0018")
    for rid in expected_ids:
        assert rid in revs, f"missing revision id {rid} in migrations"


def test_org_export_snapshot_includes_discovery_sections(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    snap = client_nf.get(
        f"/v1/nf/demo/orgs/{oid}/export/org-data-snapshot",
        params={"audit_sample_limit": 5, "include_sf424_previews": False},
        headers=_hdr(oid),
    )
    assert snap.status_code == 200, snap.text
    body = snap.json()
    assert body["snapshot_schema_version"] == ORG_DATA_SNAPSHOT_VERSION

    for key in (
        "discovery_review_summary",
        "discovery_review_items_sample",
        "source_freshness_summary",
        "coverage_gap_intelligence",
        "coverage_gap_sample",
        "source_recommendations_sample",
        "operator_decision_pack_summary",
        "operator_workbench_summary",
        "operator_priority_actions_sample",
        "operator_action_ledger_summary",
        "operator_actions_sample",
        "evidence_pack_summary",
        "evidence_subjects_sample",
        "source_check_runs_sample",
        "counts",
    ):
        assert key in body, f"missing export key {key!r}"

    counts = body["counts"]
    for ck in (
        "discovery_review_items",
        "source_check_runs",
        "coverage_gap_rows",
        "source_recommendations",
        "operator_priority_actions",
        "operator_actions",
        "open_operator_actions",
        "evidence_subjects_available",
    ):
        assert ck in counts, f"missing counts.{ck}"


def _violating_lines_for_offline_guard(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    violations: list[str] = []
    for i, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if "urllib.parse" in stripped:
            continue
        if re.search(r"\b(import requests|from requests)\b", stripped):
            violations.append(f"{path.name}:{i}:{stripped}")
        if re.search(r"\b(import httpx|from httpx)\b", stripped):
            violations.append(f"{path.name}:{i}:{stripped}")
        if re.search(r"\b(import aiohttp|from aiohttp)\b", stripped):
            violations.append(f"{path.name}:{i}:{stripped}")
        if "urllib.request" in stripped:
            violations.append(f"{path.name}:{i}:{stripped}")
        if re.search(r"^import socket\b", stripped) or re.search(
            r"^from socket\b", stripped
        ):
            violations.append(f"{path.name}:{i}:{stripped}")
        if re.search(r"\b(import boto3|from boto3)\b", stripped):
            violations.append(f"{path.name}:{i}:{stripped}")
        if re.search(r"\b(import openai|from openai)\b", stripped):
            violations.append(f"{path.name}:{i}:{stripped}")
        if re.search(r"\b(import anthropic|from anthropic)\b", stripped):
            violations.append(f"{path.name}:{i}:{stripped}")
        if "google.generative" in stripped:
            violations.append(f"{path.name}:{i}:{stripped}")
    return violations


def test_discovery_engine_services_have_no_network_client_imports() -> None:
    all_v: list[str] = []
    for fp in OFFLINE_SERVICE_FILES:
        assert fp.is_file(), f"missing {fp}"
        all_v.extend(_violating_lines_for_offline_guard(fp))
    assert not all_v, "network-like imports found:\n" + "\n".join(all_v)


def test_schema_inventory_doc_lists_same_constants() -> None:
    doc = (ROOT / "docs/product/nativeforge-discovery-schema-inventory.md").read_text(
        encoding="utf-8"
    )
    for token in (
        QUALITY_SCHEMA_VERSION,
        COVERAGE_GAP_SCHEMA_VERSION,
        DECISION_PACK_SCHEMA_VERSION,
        EVIDENCE_PACK_SCHEMA_VERSION,
        NF_OPERATOR_ACTION_SCHEMA_VERSION,
        SUMMARY_SCHEMA_VERSION,
        FRESHNESS_DETAIL_SCHEMA_VERSION,
        ORG_DATA_SNAPSHOT_VERSION,
        "nf_operator_actions_ledger_list_v1",
    ):
        assert token in doc, f"schema doc should mention {token}"


def test_operator_discovery_workflow_smoke_demo_plane(client_nf: TestClient) -> None:
    oid = uuid.uuid4()
    with SessionLocal() as s:
        s.add(Organization(id=oid, org_type="demo"))
        s.commit()

    base = f"/v1/nf/demo/orgs/{oid}"
    src = client_nf.post(
        f"{base}/discovery/sources",
        json={
            "source_name": "Sprint20 Unverified Source",
            "source_type": OpportunitySourceType.federal.value,
            "scope_global": True,
            "verification_status": OpportunityVerificationStatus.unverified.value,
        },
        headers=_hdr(oid),
    )
    assert src.status_code == 201, src.text
    sid = src.json()["id"]

    run = client_nf.post(
        f"{base}/discovery/sources/{sid}/intake-runs",
        json={"intake_mode": DiscoveryIntakeMode.structured_batch.value},
        headers=_hdr(oid),
    )
    assert run.status_code == 201, run.text
    run_id = run.json()["id"]

    dl = datetime.now(UTC) + timedelta(days=120)
    proc = client_nf.post(
        f"{base}/discovery/intake-runs/{run_id}/candidates",
        json={
            "candidates": [
                {
                    "opportunity_title": "Tribal climate resilience pilot",
                    "publisher_name": "Federal Partner",
                    "agency": "Federal Partner",
                    "award_type": GrantAwardType.grant.value,
                    "opportunity_source_type": OpportunitySourceType.federal.value,
                    "opportunity_number": "S20-001",
                    "source_url": "https://example.gov/s20",
                    "tribal_eligible": True,
                    "eligibility_tags": ["tribal_eligible"],
                    "application_deadline": dl.isoformat(),
                },
            ]
        },
        headers=_hdr(oid),
    )
    assert proc.status_code == 200, proc.text

    cands = client_nf.get(
        f"{base}/discovery/intake-runs/{run_id}/candidates",
        headers=_hdr(oid),
    ).json()
    assert len(cands) >= 1
    cid = cands[0]["id"]

    qual = client_nf.get(
        f"{base}/discovery/intake-candidates/{cid}/quality",
        headers=_hdr(oid),
    )
    assert qual.status_code == 200, qual.text
    qbody = qual.json()
    assert qbody["quality_summary"]["quality_schema_version"] == QUALITY_SCHEMA_VERSION

    reviews = client_nf.get(f"{base}/discovery/review-items", headers=_hdr(oid)).json()
    assert len(reviews) >= 1

    chk = client_nf.post(
        f"{base}/discovery/sources/{sid}/check-runs",
        json={"check_mode": SourceCheckMode.manual.value},
        headers=_hdr(oid),
    )
    assert chk.status_code == 201, chk.text
    check_run_id = chk.json()["id"]

    patch = client_nf.patch(
        f"{base}/discovery/source-check-runs/{check_run_id}",
        json={
            "check_status": SourceCheckRunStatus.succeeded.value,
            "opportunities_seen_count": 1,
            "new_candidates_count": 1,
            "accepted_count": 1,
            "duplicate_count": 0,
            "rejected_count": 0,
            "review_items_created_count": 0,
        },
        headers=_hdr(oid),
    )
    assert patch.status_code == 200, patch.text

    gap = client_nf.get(
        f"{base}/discovery/coverage-gap-intelligence",
        headers=_hdr(oid),
    )
    assert gap.status_code == 200, gap.text
    assert gap.json()["schema_version"] == COVERAGE_GAP_SCHEMA_VERSION

    pack = client_nf.get(
        f"{base}/discovery/operator-decision-pack",
        params={"limit": 50, "intake_run_limit": 40},
        headers=_hdr(oid),
    )
    assert pack.status_code == 200, pack.text
    pbody = pack.json()
    assert pbody["schema_version"] == DECISION_PACK_SCHEMA_VERSION
    items = pbody.get("decision_items") or []
    assert items, "expected at least one decision item from review queue or signals"

    decision_item = items[0]
    created = client_nf.post(
        f"{base}/discovery/operator-actions-ledger/from-decision",
        json={"decision_item": decision_item},
        headers=_hdr(oid),
    )
    assert created.status_code == 201, created.text
    action = created.json()["operator_action"]
    assert action["schema_version"] == NF_OPERATOR_ACTION_SCHEMA_VERSION
    aid = action["id"]

    ev = client_nf.get(
        f"{base}/discovery/evidence-pack/operator-actions/{aid}",
        params={
            "include_audit_trail": True,
            "include_linked_records": True,
            "include_sections": True,
            "audit_limit": 10,
        },
        headers=_hdr(oid),
    )
    assert ev.status_code == 200, ev.text
    assert ev.json()["schema_version"] == EVIDENCE_PACK_SCHEMA_VERSION

    snap = client_nf.get(
        f"{base}/export/org-data-snapshot",
        params={"audit_sample_limit": 10, "include_sf424_previews": False},
        headers=_hdr(oid),
    )
    assert snap.status_code == 200, snap.text
    exp = snap.json()
    assert exp["snapshot_schema_version"] == ORG_DATA_SNAPSHOT_VERSION
    assert exp["discovery_review_summary"]["total"] >= 1
    assert exp["evidence_pack_summary"]


def test_closeout_doc_files_exist() -> None:
    api_doc = ROOT / "docs/product/nativeforge-discovery-engine-api-inventory.md"
    closeout = ROOT / "docs/product/nativeforge-discovery-engine-closeout-sprint20.md"
    assert api_doc.is_file()
    assert closeout.is_file()
    assert "NativeForge" in api_doc.read_text(encoding="utf-8")
