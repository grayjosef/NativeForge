"""Sprint 22: Native-relevant source architecture docs + offline connector shell."""

from __future__ import annotations

from pathlib import Path

from nativeforge.domain.enums import GrantAwardType, OpportunitySourceType
from nativeforge.services.source_connectors.base import (
    ConnectorRunContext,
    ConnectorSourceConfig,
)
from nativeforge.services.source_connectors.native_relevance import (
    NativeRelevanceInput,
    assess_native_relevance,
)
from nativeforge.services.source_connectors.normalization import (
    build_native_relevance_input,
    normalize_raw_dict,
    to_discovery_intake_candidate_payload,
)
from nativeforge.services.source_connectors.static_fixture_connector import (
    dry_run_fixture_rows,
)

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs" / "product"
CONNECTOR_PKG = ROOT / "src" / "nativeforge" / "services" / "source_connectors"


def test_docs_exist() -> None:
    paths = (
        DOCS / "nativeforge-native-relevant-source-architecture.md",
        DOCS / "nativeforge-source-taxonomy-v1.md",
        DOCS / "nativeforge-native-relevance-scoring-v1.md",
        DOCS / "nativeforge-source-connector-architecture.md",
    )
    for p in paths:
        assert p.is_file(), f"missing {p}"


def test_taxonomy_includes_lanes() -> None:
    text = (DOCS / "nativeforge-source-taxonomy-v1.md").read_text(encoding="utf-8")
    assert "native_specific" in text
    assert "native_relevant_broad" in text


def test_scoring_tribal_set_aside_band() -> None:
    out = assess_native_relevance(
        NativeRelevanceInput(
            opportunity_title="Illustrative tribal set-aside competition",
            tribal_set_aside=True,
            tribal_eligible=True,
        )
    )
    assert out["native_relevance_band"] == "native_specific"
    assert out["native_relevance_score"] >= 70


def test_scoring_broad_tribal_government_eligible() -> None:
    out = assess_native_relevance(
        NativeRelevanceInput(
            opportunity_title="Regional infrastructure discretionary grant",
            raw_nofo_text="Eligible applicants include tribal governments.",
            tribal_eligible=True,
        )
    )
    assert out["native_relevance_band"] in {"medium", "high", "native_specific"}
    assert out["eligibility_confidence"] == "confirmed"


def test_scoring_keyword_only_not_confirmed() -> None:
    out = assess_native_relevance(
        NativeRelevanceInput(
            opportunity_title="Native innovation prize for municipalities",
            tribal_eligible=False,
        )
    )
    assert out["eligibility_confidence"] != "confirmed"
    assert out["review_required"] is True
    assert "keyword_hypothesis_only" in out["review_reason_codes"]


def test_scoring_ambiguous_eligibility_review() -> None:
    out = assess_native_relevance(
        NativeRelevanceInput(
            opportunity_title="General operating support grant",
            raw_nofo_text=None,
            tribal_eligible=False,
            applicant_types_include_tribal=None,
        )
    )
    assert out["review_required"] is True
    assert "ambiguous_eligibility" in out["review_reason_codes"]


def test_scoring_broad_irrelevant_low_band() -> None:
    out = assess_native_relevance(
        NativeRelevanceInput(
            opportunity_title="Municipal wastewater regulatory compliance study",
            tribal_eligible=False,
            applicant_types_include_tribal=False,
        )
    )
    assert out["native_relevance_band"] == "low"


def test_static_fixture_normalizes_and_provenance() -> None:
    cfg = ConnectorSourceConfig(
        connector_id="static_fixture",
        source_name="Fixture Source",
        publisher_name="Fixture Publisher",
    )
    ctx = ConnectorRunContext(run_id="run-fixture-1")
    rows = [
        {
            "fixture_key": "a",
            "opportunity_title": "Tribal roads improvement set-aside",
            "agency": "Illustrative DOT",
            "tribal_set_aside": True,
            "tribal_eligible": True,
        }
    ]
    res = dry_run_fixture_rows(rows, config=cfg, ctx=ctx)
    assert len(res.candidates) == 1
    c0 = res.candidates[0]
    assert c0.duplicate_key
    assert c0.provenance.get("fixture_connector") == "static_fixture"
    assert "native_relevance_score" in c0.native_relevance


def test_static_fixture_native_relevance_reasons() -> None:
    cfg = ConnectorSourceConfig(
        connector_id="static_fixture",
        source_name="Fixture Source",
        publisher_name="Fixture Publisher",
    )
    rows = [
        {
            "opportunity_title": "Eligible tribal governments — workforce",
            "agency": "Illustrative Agency",
            "tribal_eligible": True,
        }
    ]
    res = dry_run_fixture_rows(rows, config=cfg)
    reasons = res.candidates[0].native_relevance["native_relevance_reasons"]
    assert any(r.startswith("tribal_eligible_true") or "tribal" in r for r in reasons)


_FORBIDDEN_NET = ("requests", "httpx", "aiohttp", "urllib.request", "socket")


def _file_has_forbidden_imports(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    bad: list[str] = []
    for frag in _FORBIDDEN_NET:
        if f"import {frag}" in text or f"from {frag}" in text:
            bad.append(f"{path.name}: references {frag}")
    return bad


def test_static_fixture_module_has_no_network_imports() -> None:
    p = CONNECTOR_PKG / "static_fixture_connector.py"
    assert _file_has_forbidden_imports(p) == []


def test_connector_base_has_no_network_imports() -> None:
    p = CONNECTOR_PKG / "base.py"
    assert _file_has_forbidden_imports(p) == []


def test_normalized_payload_intake_compatible() -> None:
    cfg = ConnectorSourceConfig(
        connector_id="static_fixture",
        source_name="Fixture Source",
        publisher_name="Pub",
    )
    cand = normalize_raw_dict(
        {
            "opportunity_title": "Sample NOFO",
            "agency": "Agency X",
            "award_type": GrantAwardType.grant.value,
            "opportunity_source_type": OpportunitySourceType.federal.value,
        },
        local_key="k1",
        config=cfg,
        ctx=ConnectorRunContext(),
    )
    payload = to_discovery_intake_candidate_payload(cand)
    assert payload["opportunity_title"] == "Sample NOFO"
    assert payload["award_type"] == GrantAwardType.grant.value
    assert payload["opportunity_source_type"] == OpportunitySourceType.federal.value
    assert payload.get("agency") or payload.get("publisher_name")
    assert "connector_native_relevance_v1" in payload


def test_build_native_relevance_input_reads_flags() -> None:
    raw = {
        "opportunity_title": "Test",
        "tribal_set_aside": True,
        "applicant_types_include_tribal": None,
    }
    inp = build_native_relevance_input(raw)
    assert inp.tribal_set_aside is True
    assert inp.applicant_types_include_tribal is None
