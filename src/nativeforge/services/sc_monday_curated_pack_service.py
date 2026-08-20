"""Load and validate SC Monday curated-current opportunity pack (offline)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nativeforge.services.sc_monday_demo_labels_service import (
    assert_honest_opportunity_labels,
)
from nativeforge.services.sc_monday_go_contract_service import (
    go_contract_invariant_failures,
    normalize_opportunity_to_go_contract,
)
from nativeforge.services.sc_pilot_fixture_loader_service import (
    build_sc_pilot_rule_reference_grants,
)
from nativeforge.services.tier3_foundation_corpus_persist_service import (
    load_mixed_tier13_corpus,
)

SCHEMA_VERSION = "nf_sc_curated_current_opp_pack_v2"
PACK_ID = "sc_monday_demo_curated_20260820"
CAPTURE_DATE = "2026-08-20"

_FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures" / "sc_monday_demo"
PACK_PATH = _FIXTURES_DIR / "sc_curated_current_opportunity_pack.json"
SC_PACK_PATH = _FIXTURES_DIR / "sc_state_curated_current_opportunity_pack.json"
FED_PACK_PATH = _FIXTURES_DIR / "federal_curated_current_opportunity_pack.json"

# Federal corpus ids curated for SC Native/tribal relevance (offline corpus only).
FEDERAL_CURATED_GRANT_IDS: tuple[str, ...] = (
    "la-real-013",
    "la-real-014",
    "la-real-015",
    "la-real-016",
    "nf13-real-fed-012",
    "la-real-006",
    "la-real-007",
    "la-real-009",
)

# SC state + key federal rule-reference categories for eligibility story.
RULE_REF_CATEGORY_IDS: tuple[str, ...] = (
    "SC_SHPO_STATE",
    "SC_CMA_DIRECT",
    "SC_FOOD_SOVEREIGNTY",
    "ANA_SEDS",
    "ANA_LANGUAGE_587",
    "ANA_SEEDS",
    "BIA_638",
    "IHS_COMPACTS",
    "NEA_GAP",
    "NEH_NONPROFIT",
)


class ScMondayDemoPackError(FileNotFoundError):
    """Curated pack missing or invalid."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def pack_path() -> Path:
    return PACK_PATH


def load_sc_curated_opportunity_pack(*, require_file: bool = True) -> dict[str, Any]:
    if not PACK_PATH.is_file():
        if require_file:
            raise ScMondayDemoPackError(
                f"SC Monday curated pack missing: {PACK_PATH}. "
                "Generate via build_default_sc_curated_opportunity_pack + write."
            )
        return build_default_sc_curated_opportunity_pack()
    raw = json.loads(PACK_PATH.read_text(encoding="utf-8"))
    ver = str(raw.get("schema_version") or "")
    if ver not in {SCHEMA_VERSION, "nf_sc_curated_current_opp_pack_v1"}:
        raise ScMondayDemoPackError(
            f"unexpected schema_version on pack: {raw.get('schema_version')!r}"
        )
    # Ensure GO contract fields present even for older on-disk packs.
    opps = [
        normalize_opportunity_to_go_contract(r)
        for r in (raw.get("opportunities") or [])
    ]
    raw = {**raw, "schema_version": SCHEMA_VERSION, "opportunities": opps}
    return raw


def pack_invariant_failures(pack: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    ver = str(pack.get("schema_version") or "")
    if ver not in {SCHEMA_VERSION, "nf_sc_curated_current_opp_pack_v1"}:
        failures.append("bad_schema_version")
    if pack.get("live_ingestion_claimed") is True:
        failures.append("pack_live_ingestion_claimed")
    if pack.get("source_activation_claimed") is True:
        failures.append("pack_source_activation_claimed")
    if pack.get("automated_refresh_claimed") is True:
        failures.append("pack_automated_refresh_claimed")
    opps = pack.get("opportunities") or []
    if not isinstance(opps, list) or len(opps) < 5:
        failures.append("too_few_opportunities")
    seen: set[str] = set()
    sc_count = 0
    fed_count = 0
    for row in opps:
        if not isinstance(row, dict):
            failures.append("non_dict_opportunity")
            continue
        norm = normalize_opportunity_to_go_contract(row)
        gid = str(norm.get("grant_id") or norm.get("opportunity_id") or "")
        if not gid:
            failures.append("missing_grant_id")
        elif gid in seen:
            failures.append(f"duplicate_grant_id:{gid}")
        else:
            seen.add(gid)
        failures.extend(assert_honest_opportunity_labels(norm))
        failures.extend(go_contract_invariant_failures(norm))
        geo = str(norm.get("funding_geography") or "")
        if geo == "south_carolina":
            sc_count += 1
        elif geo == "federal":
            fed_count += 1
        else:
            failures.append(f"bad_funding_geography:{gid}:{geo}")
    if sc_count < 1:
        failures.append("missing_sc_opportunities")
    if fed_count < 1:
        failures.append("missing_federal_opportunities")
    return failures


def build_default_sc_curated_opportunity_pack() -> dict[str, Any]:
    """Assemble curated pack from offline corpus + SC rule references."""
    corpus_by_id = {str(g.get("grant_id")): g for g in load_mixed_tier13_corpus()}
    rule_refs = {
        str(g.get("sc_rule_category_id")): g
        for g in build_sc_pilot_rule_reference_grants()
    }
    opportunities: list[dict[str, Any]] = []

    for gid in FEDERAL_CURATED_GRANT_IDS:
        base = corpus_by_id.get(gid)
        if not base:
            continue
        opportunities.append(
            {
                **dict(base),
                "grant_id": gid,
                "funding_geography": "federal",
                "data_label": "fixture_demo",
                "live_ingest_not_claimed": True,
                "live_ingestion_claimed": False,
                "retrieval_date": CAPTURE_DATE,
                "capture_date": CAPTURE_DATE,
                "source_url": str(
                    base.get("source_url")
                    or base.get("opportunity_url")
                    or "https://www.grants.gov/ (offline corpus evidence only)"
                ),
                "evidence_notes": (
                    "Offline mixed Tier1/3 corpus row curated for SC Native/tribal "
                    "relevance demo. Not a live Grants.gov pull in this block."
                ),
                "confirm_active_round": True,
                "sc_monday_demo_pack": True,
            }
        )

    for cat_id in RULE_REF_CATEGORY_IDS:
        ref = rule_refs.get(cat_id)
        if not ref:
            continue
        is_sc_state = cat_id.startswith("SC_")
        opportunities.append(
            {
                **dict(ref),
                "funding_geography": "south_carolina" if is_sc_state else "federal",
                "data_label": "rule_reference",
                "live_ingest_not_claimed": True,
                "live_ingestion_claimed": False,
                "retrieval_date": CAPTURE_DATE,
                "capture_date": CAPTURE_DATE,
                "source_url": str(
                    ref.get("eligibility_text") or "sc_eligibility_rules.json"
                ),
                "evidence_notes": (
                    "SC pilot eligibility rule-reference program — not a live portal listing. "
                    "Confirm active funding round before customer pursuit."
                ),
                "confirm_active_round": True,
                "sc_monday_demo_pack": True,
            }
        )

    opportunities = [normalize_opportunity_to_go_contract(o) for o in opportunities]
    pack = {
        "schema_version": SCHEMA_VERSION,
        "pack_id": PACK_ID,
        "title": "SC Monday Demo — Curated-Current Opportunity Pack",
        "capture_date": CAPTURE_DATE,
        "live_ingestion_claimed": False,
        "source_activation_claimed": False,
        "automated_refresh_claimed": False,
        "final_eligibility_claim_allowed": False,
        "opportunities": opportunities,
        "counts": {
            "total": len(opportunities),
            "south_carolina": sum(
                1
                for o in opportunities
                if o.get("funding_geography") == "south_carolina"
            ),
            "federal": sum(
                1 for o in opportunities if o.get("funding_geography") == "federal"
            ),
        },
    }
    return _json_safe(pack)


def split_layer_packs(
    pack: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Split combined pack into SC-state and federal curated packs."""
    doc = pack if pack is not None else build_default_sc_curated_opportunity_pack()
    sc_opps = [o for o in doc["opportunities"] if o.get("source_layer") == "sc_state"]
    fed_opps = [o for o in doc["opportunities"] if o.get("source_layer") == "federal"]
    sc_pack = {
        **doc,
        "pack_id": f"{PACK_ID}_sc_state",
        "title": "SC Monday Demo — South Carolina Curated-Current Pack",
        "opportunities": sc_opps,
        "counts": {"total": len(sc_opps), "south_carolina": len(sc_opps), "federal": 0},
    }
    fed_pack = {
        **doc,
        "pack_id": f"{PACK_ID}_federal",
        "title": "SC Monday Demo — Federal Curated-Current Pack",
        "opportunities": fed_opps,
        "counts": {
            "total": len(fed_opps),
            "south_carolina": 0,
            "federal": len(fed_opps),
        },
    }
    return _json_safe(sc_pack), _json_safe(fed_pack)


def write_sc_curated_opportunity_pack(
    pack: dict[str, Any] | None = None,
    *,
    path: Path | None = None,
) -> Path:
    doc = pack if pack is not None else build_default_sc_curated_opportunity_pack()
    failures = pack_invariant_failures(doc)
    if failures:
        raise ScMondayDemoPackError(f"pack invariants failed: {failures}")
    out = path or PACK_PATH
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(doc, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    sc_pack, fed_pack = split_layer_packs(doc)
    SC_PACK_PATH.write_text(
        json.dumps(sc_pack, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    FED_PACK_PATH.write_text(
        json.dumps(fed_pack, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return out


def grants_from_pack(pack: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    doc = (
        pack
        if pack is not None
        else load_sc_curated_opportunity_pack(require_file=False)
    )
    return [
        normalize_opportunity_to_go_contract(g)
        for g in (doc.get("opportunities") or [])
    ]
