"""Sprint 25: offline connector fixture corpus (deterministic, no network)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any, cast

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import OpportunitySourceType
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
from nativeforge.services.source_connectors.fixture_corpus import (
    REQUIRED_FIXTURE_CATEGORIES,
    assert_complete_required_corpus,
    corpus_row_count,
    fixture_category_from_bundle,
    list_corpus_bundle_paths,
    load_all_corpus_rows_flat,
    load_bundle,
    load_category_rows,
    materialize_bundle_rows,
)
from nativeforge.services.source_connectors.source_check_bridge import (
    run_source_check_backed_connector_dry_run,
)
from nativeforge.services.source_connectors.static_fixture_connector import (
    dry_run_fixture_rows,
)

CONNECTOR_ROOT = (
    Path(__file__).resolve().parents[1]
    / "src"
    / "nativeforge"
    / "services"
    / "source_connectors"
)
_FORBIDDEN_IMPORT_SUBSTRINGS = (
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
                source_name="Sprint 25 fixture corpus source",
                source_type=OpportunitySourceType.federal,
                scope_global=True,
            ),
        )
        s.commit()
        return oid, src.id


def _cfg() -> ConnectorSourceConfig:
    return ConnectorSourceConfig(
        connector_id="sprint25_fixture_corpus",
        source_name="corpus",
        publisher_name="Illustrative Publisher",
    )


def _dry_one_category(category: str) -> tuple[dict[str, Any], dict[str, Any], str]:
    rows = load_category_rows(category)
    assert len(rows) >= 1
    ctx = ConnectorRunContext(run_id="s25-dry")
    res = dry_run_fixture_rows(rows, config=_cfg(), ctx=ctx)
    assert not res.errors
    nr = res.candidates[0].native_relevance
    prov = res.candidates[0].provenance
    dup = res.candidates[0].duplicate_key
    return nr, prov, dup


def test_corpus_loads_without_network() -> None:
    rows = load_all_corpus_rows_flat()
    assert len(rows) == corpus_row_count()
    assert_complete_required_corpus()


def test_all_required_categories_present() -> None:
    seen: set[str] = set()
    for path in list_corpus_bundle_paths():
        doc = load_bundle(path)
        seen.add(fixture_category_from_bundle(doc))
    assert seen == REQUIRED_FIXTURE_CATEGORIES


def test_each_fixture_has_minimum_required_fields() -> None:
    for path in list_corpus_bundle_paths():
        doc = load_bundle(path)
        rows = materialize_bundle_rows(doc)
        assert rows
        for row in rows:
            assert row.get("opportunity_title")
            agency_or_pub = row.get("agency") or row.get("publisher_name")
            assert agency_or_pub
            assert row.get("source_url") or row.get("url")
            assert row.get("opportunity_number") or row.get("fixture_key")
            assert row.get("opportunity_source_type")
            assert row.get("award_type")
            assert row.get("fixture_category")


def test_tribal_specific_categories_score_high_or_native_specific() -> None:
    tribal_specific = {
        "bia_tribal_specific",
        "ihs_tribal_health",
        "ana_language_culture",
        "doe_indian_energy",
        "hud_onap_housing",
        "epa_tribal_environment",
        "foundation_native_serving",
    }
    for cat in tribal_specific:
        nr, _, _ = _dry_one_category(cat)
        assert nr["native_relevance_band"] in ("high", "native_specific"), (
            f"{cat}: got {nr['native_relevance_band']}"
        )


def test_broad_tribe_eligible_without_native_keyword_in_title() -> None:
    """Structured tribal eligibility; title/synopsis avoid Native keyword tokens."""
    nr_gg, _, _ = _dry_one_category("grants_gov_broad_tribal_eligible")
    rows_gg = load_category_rows("grants_gov_broad_tribal_eligible")
    blob = (
        rows_gg[0].get("opportunity_title", "")
        + "\n"
        + str(rows_gg[0].get("raw_nofo_text") or "")
    ).lower()
    assert "native" not in blob
    assert "tribal" not in blob
    assert "indigenous" not in blob
    assert nr_gg["native_relevance_band"] in ("medium", "high", "native_specific")

    nr_bb, _, _ = _dry_one_category("broad_rural_broadband_tribes_eligible")
    rows_bb = load_category_rows("broad_rural_broadband_tribes_eligible")
    blob_b = (
        rows_bb[0].get("opportunity_title", "")
        + "\n"
        + str(rows_bb[0].get("raw_nofo_text") or "")
    ).lower()
    assert "tribal" not in blob_b
    assert "native" not in blob_b
    assert nr_bb["native_relevance_band"] in ("medium", "high", "native_specific")


def test_keyword_only_false_positive_review_not_confirmed() -> None:
    nr, _, _ = _dry_one_category("keyword_only_false_positive")
    assert nr["review_required"] is True
    assert "keyword_hypothesis_only" in nr["review_reason_codes"]
    assert nr["eligibility_confidence"] != "confirmed"


def test_irrelevant_broad_opportunity_scores_low() -> None:
    nr, _, _ = _dry_one_category("irrelevant_broad_opportunity")
    assert nr["native_relevance_band"] == "low"


def test_ambiguous_eligibility_requires_review() -> None:
    nr, _, _ = _dry_one_category("ambiguous_eligibility_case")
    assert nr["review_required"] is True
    assert "ambiguous_eligibility" in nr["review_reason_codes"]


def test_duplicate_keys_are_unique_hex_digests() -> None:
    rows = load_all_corpus_rows_flat()
    res = dry_run_fixture_rows(
        rows,
        config=_cfg(),
        ctx=ConnectorRunContext(run_id="s25-dup"),
    )
    assert not res.errors
    keys = [c.duplicate_key for c in res.candidates]
    assert len(keys) == len(set(keys))
    for k in keys:
        assert len(k) == 64


def test_full_corpus_source_check_dry_run_manifest_alignment() -> None:
    oid, sid = _seed_org_and_source()
    rows = load_all_corpus_rows_flat()
    cfg = _cfg()
    ctx = ConnectorRunContext(run_id="s25-full-corpus", dry_run=True)
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
            run_context=ctx,
        )
        s.commit()

    manifest = out["connector_manifest"]
    assert manifest["counts"]["fixture_rows"] == len(rows)
    assert manifest["counts"]["normalized_candidates"] == len(rows)
    assert out["candidate_counts"]["candidate_count"] == len(rows)

    intake = out["intake_run"]
    assert intake is not None
    run_id = uuid.UUID(intake["id"])
    with SessionLocal() as s:
        cands = intake_repo.list_discovery_intake_candidates_for_run(
            session=s,
            org_id=oid,
            org_type="demo",
            intake_run_id=run_id,
        )
    assert len(cands) == len(rows)


def test_provenance_includes_fixture_metadata() -> None:
    _, prov, _ = _dry_one_category("bia_tribal_specific")
    assert prov.get("fixture_category") == "bia_tribal_specific"
    assert prov.get("fixture_key")


def test_fixture_corpus_module_has_no_forbidden_imports() -> None:
    text = (CONNECTOR_ROOT / "fixture_corpus.py").read_text(encoding="utf-8")
    for bad in _FORBIDDEN_IMPORT_SUBSTRINGS:
        assert bad not in text, f"unexpected substring {bad!r}"


def test_materialized_rows_include_corpus_schema_version() -> None:
    rows = load_category_rows("epa_tribal_environment")
    assert rows[0].get("corpus_schema_version")
