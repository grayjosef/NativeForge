"""Sprint 26: Grants.gov-shaped fixture connector (offline, no network)."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any, cast

from nativeforge.db.models import Organization
from nativeforge.db.session import SessionLocal
from nativeforge.domain.enums import OpportunitySourceType
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.services.opportunity_discovery_service import (
    OpportunitySourcePayload,
    create_opportunity_source,
)
from nativeforge.services.source_connectors.base import (
    ConnectorRunContext,
    ConnectorSourceConfig,
)
from nativeforge.services.source_connectors.grants_gov_shaped import (
    GRANTS_GOV_SHAPED_CONNECTOR_KEY,
    dry_run_grants_gov_shaped_rows,
    grants_gov_like_to_fixture_row,
    normalize_grants_gov_payload,
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
GRANTS_GOV_FIXTURE_DIR = CONNECTOR_ROOT / "fixtures" / "grants_gov"

_FORBIDDEN_SUBSTRINGS = (
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


def _load_grants_fixture(name: str) -> dict[str, Any]:
    path = GRANTS_GOV_FIXTURE_DIR / name
    doc = json.loads(path.read_text(encoding="utf-8"))
    return cast(dict[str, Any], doc["payload"])


def _cfg() -> ConnectorSourceConfig:
    return ConnectorSourceConfig(
        connector_id="sprint26_grants_gov",
        source_name="grants.gov (fixture)",
        publisher_name="Illustrative",
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
                source_name="Sprint 26 grants.gov fixture",
                source_type=OpportunitySourceType.federal,
                scope_global=True,
            ),
        )
        s.commit()
        return oid, src.id


def test_grants_gov_shaped_payload_maps_internal_fields() -> None:
    raw = _load_grants_fixture("tribal_eligibility_synopsis.json")
    row = grants_gov_like_to_fixture_row(raw)
    assert row["opportunity_title"] == raw["Title"]
    assert row["agency"] == raw["agencyName"]
    assert row["opportunity_number"] == raw["OpportunityNumber"]
    assert row["source_url"] == raw["OpportunityURL"]
    assert row["award_type"] == "grant"
    assert row["cfda_assistance_listing"] == "93.123"
    assert row["posted_date"] == raw["PostedDate"]
    assert row["application_deadline"] == raw["CloseDate"]
    assert row["tribal_eligible"] is True
    assert "federally_recognized_tribe" in (row.get("eligibility_tags") or [])


def test_normalize_grants_gov_payload_alias() -> None:
    assert normalize_grants_gov_payload is grants_gov_like_to_fixture_row


def test_tribal_eligibility_synopsis_structured_signals() -> None:
    raw = _load_grants_fixture("tribal_eligibility_synopsis.json")
    res = dry_run_grants_gov_shaped_rows([raw], config=_cfg())
    assert not res.errors
    nr = res.candidates[0].native_relevance
    assert nr["eligibility_confidence"] == "confirmed"


def test_broad_eligible_scores_relevant_without_native_keyword_in_title() -> None:
    raw = _load_grants_fixture("broad_eligible_structured.json")
    row = grants_gov_like_to_fixture_row(raw)
    title = row["opportunity_title"]
    synopsis = str(row.get("raw_nofo_text") or "")
    blob = (title + "\n" + synopsis).lower()
    assert "native" not in blob
    assert "tribal" not in blob
    res = dry_run_grants_gov_shaped_rows([raw], config=_cfg())
    band = res.candidates[0].native_relevance["native_relevance_band"]
    assert band in ("medium", "high", "native_specific")


def test_keyword_only_false_positive_review_not_confirmed() -> None:
    raw = _load_grants_fixture("keyword_only_title.json")
    res = dry_run_grants_gov_shaped_rows([raw], config=_cfg())
    nr = res.candidates[0].native_relevance
    assert nr["review_required"] is True
    assert "keyword_hypothesis_only" in nr["review_reason_codes"]
    assert nr["eligibility_confidence"] != "confirmed"


def test_ambiguous_eligibility_requires_review() -> None:
    raw = _load_grants_fixture("ambiguous_eligibility.json")
    res = dry_run_grants_gov_shaped_rows([raw], config=_cfg())
    nr = res.candidates[0].native_relevance
    assert nr["review_required"] is True
    assert "ambiguous_eligibility" in nr["review_reason_codes"]


def test_duplicate_keys_stable_across_equivalent_alias_payloads() -> None:
    alias_a = {
        "Title": "Duplicate Stability Demo",
        "agencyName": "Illustrative Agency X",
        "OpportunityNumber": "S26-DUP-777",
        "OpportunityURL": "https://example.test/s26/dup-stability",
        "FundingInstrumentType": "Grant",
        "Synopsis": "Fixture text.",
        "CloseDate": "2099-08-01T23:59:59Z",
    }
    alias_b = {
        "opportunity_title": "Duplicate Stability Demo",
        "agency": "Illustrative Agency X",
        "opportunity_number": "S26-DUP-777",
        "source_url": "https://example.test/s26/dup-stability",
        "award_type": "grant",
        "opportunity_source_type": "federal",
        "raw_nofo_text": "Fixture text.",
        "application_deadline": "2099-08-01T23:59:59Z",
    }
    ra = grants_gov_like_to_fixture_row(alias_a)
    rb = grants_gov_like_to_fixture_row(alias_b)
    da = dry_run_grants_gov_shaped_rows([alias_a], config=_cfg())
    db = dry_run_grants_gov_shaped_rows([alias_b], config=_cfg())
    assert not da.errors and not db.errors
    assert da.candidates[0].duplicate_key == db.candidates[0].duplicate_key
    assert ra["opportunity_title"] == rb["opportunity_title"]


def test_grants_gov_shaped_provenance_identifier() -> None:
    raw = _load_grants_fixture("tribal_eligibility_synopsis.json")
    res = dry_run_grants_gov_shaped_rows([raw], config=_cfg())
    prov = res.candidates[0].provenance
    assert prov.get("fixture_connector") == GRANTS_GOV_SHAPED_CONNECTOR_KEY
    assert prov.get("connector_shape") == GRANTS_GOV_SHAPED_CONNECTOR_KEY


def test_grants_gov_rows_source_check_dry_run_manifest() -> None:
    oid, sid = _seed_org_and_source()
    rows = [
        grants_gov_like_to_fixture_row(_load_grants_fixture(name))
        for name in (
            "tribal_eligibility_synopsis.json",
            "broad_eligible_structured.json",
            "keyword_only_title.json",
            "ambiguous_eligibility.json",
        )
    ]
    cfg = _cfg()
    ctx = ConnectorRunContext(run_id="s26-gg-source-check", dry_run=True)
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
    m = out["connector_manifest"]
    assert m["counts"]["fixture_rows"] == 4
    assert m["counts"]["normalized_candidates"] == 4
    assert out["candidate_counts"]["candidate_count"] == 4


def test_award_ceiling_floor_parsed_to_normalized_fields() -> None:
    raw = _load_grants_fixture("broad_eligible_structured.json")
    res = dry_run_grants_gov_shaped_rows([raw], config=_cfg())
    nf = res.candidates[0].normalized_fields
    assert nf.get("award_ceiling") == 2500000.0
    assert nf.get("award_floor") == 100000.0


def test_module_has_no_forbidden_network_imports() -> None:
    text = (CONNECTOR_ROOT / "grants_gov_shaped.py").read_text(encoding="utf-8")
    for bad in _FORBIDDEN_SUBSTRINGS:
        assert bad not in text
