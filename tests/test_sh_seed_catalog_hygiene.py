"""SH: seed catalog hygiene — identity key + reconciliation tests."""

from __future__ import annotations

import uuid

import pytest

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.services.seed_catalog_health_service import (
    BUCKET_ACTIVATABLE,
    build_catalog_reconciliation_report,
)
from nativeforge.services.source_ingestion_orchestrator_service import (
    persist_seed_candidates_to_registry,
)
from nativeforge.services.source_ingestion_seed_loader_service import (
    build_source_seed_candidate_bundle,
    seed_row_to_discovery_candidate,
)
from nativeforge.services.tier1_batch_federal_activation_service import (
    activate_tier1_public_batch_human_gate,
)

_DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
_BIA_SEEDS = (
    "nf-seed-2026-fed-001",
    "nf-seed-2026-fed-003",
    "nf-seed-2026-fed-004",
)
_CONFIRMATION = {
    "operator_handle": "hygiene-test",
    "human_activation_acknowledged": True,
    "public_only_acknowledged": True,
    "batch_tier1_public_activation_acknowledged": True,
}


@pytest.fixture
def demo_org() -> Organization:
    with SessionLocal() as s:
        org = s.get(Organization, _DEMO_ORG)
        if org is None:
            org = Organization(id=_DEMO_ORG, org_type="demo")
            s.add(org)
            s.commit()
        return org


def test_ac1_reconciliation_accounts_all_177_rows() -> None:
    bundle = build_source_seed_candidate_bundle()
    report = build_catalog_reconciliation_report(bundle["candidates"])
    assert report["catalog_row_count"] == 177
    assert report["nothing_silently_dropped"] is True
    assert sum(report["bucket_counts"].values()) == 177
    headline = report["headline"]
    assert headline["catalog_programs"] == 177
    assert headline["activatable_now"] >= 100


def test_ac2_bia_shared_url_three_distinct_registry_rows(
    demo_org: Organization,
) -> None:
    bundle = build_source_seed_candidate_bundle()
    by_id = {c["seed_id"]: c for c in bundle["candidates"]}
    candidates = [by_id[sid] for sid in _BIA_SEEDS]
    assert len({c["source_url"] for c in candidates}) == 1

    with SessionLocal() as s:
        org = s.get(Organization, _DEMO_ORG)
        assert org is not None
        persist_seed_candidates_to_registry(s, org=org, candidates=candidates)
        result = activate_tier1_public_batch_human_gate(
            s,
            org=org,
            seed_ids=list(_BIA_SEEDS),
            operator_confirmation=_CONFIRMATION,
        )
        s.commit()

    assert result["activated_count"] == 3
    from nativeforge.repositories import opportunity_sources as os_repo

    with SessionLocal() as s:
        org = s.get(Organization, _DEMO_ORG)
        assert org is not None
        rows = os_repo.list_opportunity_sources_for_org(
            session=s, org_id=org.id, org_type=org.org_type
        )
        active_bia = [
            r
            for r in rows
            if r.is_active and r.seed_id in _BIA_SEEDS
        ]
    assert len(active_bia) == 3
    assert len({r.id for r in active_bia}) == 3


def test_ac3_fed023_login_gated_not_activatable() -> None:
    bundle = build_source_seed_candidate_bundle()
    fed023 = next(
        c for c in bundle["candidates"] if c["seed_id"] == "nf-seed-2026-fed-023"
    )
    assert fed023.get("access_posture_hint") == "login"
    assert fed023.get("catalog_accounting_bucket") != BUCKET_ACTIVATABLE


def test_persist_skips_duplicate_seed_id_not_url(demo_org: Organization) -> None:
    row = next(
        r
        for r in __import__(
            "nativeforge.services.source_ingestion_seed_loader_service",
            fromlist=["load_source_seed_rows"],
        ).load_source_seed_rows()
        if r["seed_id"] == "nf-seed-2026-fed-001"
    )
    cand = seed_row_to_discovery_candidate(row)
    with SessionLocal() as s:
        org = s.get(Organization, _DEMO_ORG)
        assert org is not None
        first = persist_seed_candidates_to_registry(s, org=org, candidates=[cand])
        second = persist_seed_candidates_to_registry(s, org=org, candidates=[cand])
        s.commit()
    assert first["inserted"] == 1
    assert second["skipped"] == 1
    assert second["identity_key"] == "seed_id"
