"""Sprint 344 / NF-16: re-ingest tribal grant eligibility — no proxy substitution."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nativeforge.services.fed_program_activation_binding_service import (
    load_seed_candidate,
)
from nativeforge.services.grants_gov_seed_search_refinement_service import (
    fetch_refined_grants_gov_for_seed,
)
from nativeforge.services.no_live_nofo_state_service import build_no_live_nofo_grant
from nativeforge.services.source_program_ownership_guard_service import (
    assert_source_program_ownership,
    resolve_ingested_agency,
)

SCHEMA_VERSION = "nf_tribal_grant_eligibility_reingest_v2"
REINGEST_SEED_IDS = ("nf-seed-2026-fed-021", "nf-seed-2026-fed-025")
REINGEST_GRANT_IDS = ("nf13-real-fed-021", "nf13-real-fed-025")
FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "fixtures"
    / "real_grants_corpus"
    / "nf15_eligibility_reingest_pulls.json"
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _payload_to_grant_update(
    grant: dict[str, Any],
    payload: dict[str, Any],
    *,
    source: dict[str, Any],
    reingest_meta: dict[str, Any],
) -> dict[str, Any]:
    from nativeforge.services.mixed_corpus_grant_field_derivation_service import (
        derive_mixed_corpus_grant_fields,
    )

    updated = dict(grant)
    updated["opportunity_title"] = payload.get("opportunity_title") or grant.get(
        "opportunity_title"
    )
    updated["eligibility_text"] = payload.get("eligibility_text")
    updated["synopsis"] = payload.get("synopsis")
    updated["tribal_eligible"] = payload.get("tribal_eligible", False)
    elig = str(payload.get("eligibility_text") or "")
    from nativeforge.services.real_grant_classification_input_adapter_service import (
        _TRIBAL_TYPE_RE,
    )

    if payload.get("tribal_eligible"):
        updated["applicant_types_include_tribal"] = True
    elif _TRIBAL_TYPE_RE.search(elig):
        updated["applicant_types_include_tribal"] = True
    else:
        updated["applicant_types_include_tribal"] = payload.get("tribal_eligible")
    updated["opportunity_number"] = payload.get("opportunity_number") or grant.get(
        "opportunity_number"
    )
    updated["agency"] = resolve_ingested_agency(
        source=source,
        payload_agency=str(payload.get("agency") or grant.get("agency") or ""),
    )
    updated["grants_gov_opportunity_id"] = payload.get("grants_gov_opportunity_id")
    updated["real_fetch"] = payload.get("real_fetch")
    updated["fetch_mode"] = payload.get("fetch_mode", "live")
    updated["fixture"] = False
    updated["search_live"] = reingest_meta.get("search_live")
    updated["detail_live"] = reingest_meta.get("detail_live")
    updated["eligibility_reingest"] = True
    updated["eligibility_reingest_diagnosis"] = reingest_meta.get("diagnosis")
    updated["prior_eligibility_was_placeholder"] = str(
        grant.get("eligibility_text") or ""
    ).startswith("Open to eligible applicants")
    updated["reingest_program_proxy"] = False
    updated.pop("intended_program", None)
    updated.pop("no_live_nofo", None)
    updated.pop("source_ingestion_state", None)
    derived = derive_mixed_corpus_grant_fields(updated)
    assert_source_program_ownership(source=source, grant=derived)
    return derived


def reingest_tribal_grant_eligibility(
    grant: dict[str, Any],
) -> dict[str, Any]:
    """Re-fetch Grants.gov eligibility; no_live_nofo when no matching posted NOFO."""
    seed_id = str(grant.get("source_seed_id") or "")
    if seed_id not in REINGEST_SEED_IDS:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "grant_id": grant.get("grant_id"),
                "reingested": False,
                "reason": "not_a_reingest_target",
            }
        )
    source = load_seed_candidate(seed_id)
    fetch_result = fetch_refined_grants_gov_for_seed(source)
    payloads = list(fetch_result.get("payloads") or [])

    if not payloads:
        diagnosis = str(fetch_result.get("diagnosis") or "no_intent_matching_hit")
        nofo_grant = build_no_live_nofo_grant(
            grant,
            source,
            diagnosis=f"no_live_nofo:{diagnosis}",
        )
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "grant_id": grant.get("grant_id"),
                "source_seed_id": seed_id,
                "reingested": False,
                "no_live_nofo": True,
                "diagnosis": diagnosis,
                "updated_grant": nofo_grant,
                "prior_placeholder": nofo_grant.get("prior_eligibility_was_placeholder"),
            }
        )

    updated_grant = _payload_to_grant_update(
        grant,
        payloads[0],
        source=source,
        reingest_meta=fetch_result,
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "grant_id": grant.get("grant_id"),
            "source_seed_id": seed_id,
            "reingested": True,
            "no_live_nofo": False,
            "diagnosis": fetch_result.get("diagnosis"),
            "chosen_opportunity_id": fetch_result.get("chosen_opportunity_id"),
            "updated_grant": updated_grant,
            "prior_placeholder": updated_grant.get("prior_eligibility_was_placeholder"),
        }
    )


def reingest_nf13_placeholder_grants(
    grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    from nativeforge.services.real_grants_corpus_loader_service import (
        load_nf13_real_ingested_grants,
    )

    corpus = grants if grants is not None else load_nf13_real_ingested_grants()
    by_id = {g["grant_id"]: dict(g) for g in corpus}
    results: list[dict[str, Any]] = []
    for grant_id in REINGEST_GRANT_IDS:
        grant = by_id.get(grant_id)
        if not grant:
            continue
        results.append(reingest_tribal_grant_eligibility(grant))

    pulls = {
        "schema_version": "nf16_eligibility_reingest_pulls_v1",
        "pull_count": len(results),
        "results": results,
        "no_proxy_substitution": True,
    }
    FIXTURE_PATH.write_text(json.dumps(pulls, indent=2), encoding="utf-8")

    updated_grants = []
    for g in corpus:
        gid = g["grant_id"]
        match = next((r for r in results if r.get("grant_id") == gid), None)
        if match and match.get("updated_grant"):
            updated_grants.append(match["updated_grant"])
        else:
            updated_grants.append(g)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "reingest_count": len(REINGEST_GRANT_IDS),
            "reingested_success_count": sum(1 for r in results if r.get("reingested")),
            "no_live_nofo_count": sum(1 for r in results if r.get("no_live_nofo")),
            "proxy_substitution_count": 0,
            "results": results,
            "updated_grants": updated_grants,
            "fixture_path": str(FIXTURE_PATH),
            "honest_labeling": True,
            "never_synthesized": True,
        }
    )


def build_tribal_grant_eligibility_reingest_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "target_grant_ids": list(REINGEST_GRANT_IDS),
            "target_seed_ids": list(REINGEST_SEED_IDS),
            "no_proxy_substitution": True,
            "preview_only": True,
        }
    )
