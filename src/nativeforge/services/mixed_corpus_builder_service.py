"""Sprint 332-333: build NF-14 mixed real corpus (tribal federal + broad + edge)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nativeforge.services.mixed_corpus_grant_field_derivation_service import (
    derive_mixed_corpus_grant_fields,
)
from nativeforge.services.real_grants_corpus_loader_service import (
    load_nf13_real_ingested_grants,
)

SCHEMA_VERSION = "nf_mixed_corpus_builder_v1"
PULLS_PATH = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "real_grants_corpus"
    / "nf14_grants_gov_broad_edge_pulls.json"
)
MIXED_CORPUS_PATH = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "real_grants_corpus"
    / "nf14_mixed_corpus.json"
)
EXPECTED_TRIBAL_FEDERAL_COUNT = 40


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _pull_to_grant(pull: dict[str, Any], idx: int) -> dict[str, Any]:
    payload = dict(pull.get("parsed_payload") or {})
    segment = str(pull.get("segment") or "broad")
    detail = pull.get("fetch_detail") or {}
    synopsis = detail.get("synopsis") or {}
    grant = {
        "grant_id": f"nf14-mixed-{segment}-{idx:02d}",
        "source_seed_id": payload.get("source_seed_id"),
        "opportunity_number": payload.get("opportunity_number"),
        "opportunity_title": payload.get("opportunity_title"),
        "agency": payload.get("agency"),
        "eligibility_text": payload.get("eligibility_text"),
        "synopsis": payload.get("synopsis"),
        "tribal_eligible": payload.get("tribal_eligible", False),
        "applicant_types_include_tribal": payload.get("tribal_eligible"),
        "tribal_set_aside": False,
        "tribal_priority_points": False,
        "application_deadline": payload.get("application_deadline"),
        "real_fetch": False,
        "fetch_mode": "fixture",
        "fixture": True,
        "search_live": False,
        "detail_live": False,
        "never_synthesized": True,
        "corpus_segment": segment,
        "grants_gov_opportunity_id": pull.get("grants_gov_opportunity_id"),
        "recorded_from_live_pull": True,
        "recorded_pull_date": pull.get("recorded_pull_date", "2026-05-19"),
    }
    return derive_mixed_corpus_grant_fields(grant, synopsis=synopsis)


def load_nf14_grants_gov_pulls() -> list[dict[str, Any]]:
    if not PULLS_PATH.is_file():
        raise FileNotFoundError(f"missing NF-14 pulls fixture: {PULLS_PATH}")
    raw = json.loads(PULLS_PATH.read_text(encoding="utf-8"))
    return list(raw.get("pulls") or [])


def build_mixed_real_corpus(*, use_cached_manifest: bool = True) -> list[dict[str, Any]]:
    """40 tribal federal (NF-13) + recorded Grants.gov broad/edge/label-spread pulls."""
    if use_cached_manifest and MIXED_CORPUS_PATH.is_file():
        raw = json.loads(MIXED_CORPUS_PATH.read_text(encoding="utf-8"))
        grants = list(raw.get("grants") or [])
        if grants:
            return grants

    tribal = []
    for grant in load_nf13_real_ingested_grants():
        row = derive_mixed_corpus_grant_fields(
            {**grant, "corpus_segment": "tribal_federal"}
        )
        tribal.append(row)

    supplemental = [
        _pull_to_grant(pull, idx + 1) for idx, pull in enumerate(load_nf14_grants_gov_pulls())
    ]
    return _json_safe(tribal + supplemental)


def build_mixed_corpus_manifest() -> dict[str, Any]:
    grants = build_mixed_real_corpus(use_cached_manifest=False)
    tribal_count = sum(1 for g in grants if g.get("corpus_segment") == "tribal_federal")
    broad_count = sum(1 for g in grants if g.get("corpus_segment") == "broad")
    edge_count = sum(1 for g in grants if g.get("corpus_segment") == "edge")
    spread_count = sum(1 for g in grants if g.get("corpus_segment") == "label_spread")
    return _json_safe(
        {
            "schema_version": "nf14_mixed_corpus_v1",
            "grant_count": len(grants),
            "tribal_federal_count": tribal_count,
            "broad_count": broad_count,
            "edge_count": edge_count,
            "label_spread_count": spread_count,
            "recorded_pull_fixture": PULLS_PATH.name,
            "grants": grants,
            "honest_labeling": True,
            "never_synthesized": True,
        }
    )


def build_mixed_corpus_builder_contract() -> dict[str, Any]:
    grants = build_mixed_real_corpus()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "grant_count": len(grants),
            "tribal_federal_count": EXPECTED_TRIBAL_FEDERAL_COUNT,
            "supplemental_count": len(grants) - EXPECTED_TRIBAL_FEDERAL_COUNT,
            "recorded_pull_fixture": PULLS_PATH.name,
            "mixed_corpus_manifest": MIXED_CORPUS_PATH.name,
            "honest_labeling": True,
            "never_synthesized": True,
        }
    )
