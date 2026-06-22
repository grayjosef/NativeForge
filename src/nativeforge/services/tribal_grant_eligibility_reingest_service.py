"""Sprint 344: re-ingest tribal grant eligibility for NF-15 upstream fix."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nativeforge.services.fed_program_activation_binding_service import load_seed_candidate
from nativeforge.services.grants_gov_seed_search_refinement_service import (
    fetch_refined_grants_gov_for_seed,
)

SCHEMA_VERSION = "nf_tribal_grant_eligibility_reingest_v1"
REINGEST_SEED_IDS = ("nf-seed-2026-fed-021", "nf-seed-2026-fed-025")
REINGEST_GRANT_IDS = ("nf13-real-fed-021", "nf13-real-fed-025")
# When IEGAP GAP has no posted NOFO, use EPA tribal environmental TA (synopsis-enriched).
SEED_FALLBACK_OPPORTUNITY_IDS: dict[str, int] = {
    "nf-seed-2026-fed-025": 362798,
}
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
    if reingest_meta.get("diagnosis", "").startswith("iegap_nofo_absent"):
        updated["reingest_program_proxy"] = True
        updated["intended_program"] = "EPA Indian Environmental General Assistance Program (GAP)"
    return derive_mixed_corpus_grant_fields(updated)


def reingest_tribal_grant_eligibility(
    grant: dict[str, Any],
) -> dict[str, Any]:
    """Re-fetch Grants.gov eligibility for a single tribal federal grant."""
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
    diagnosis = str(fetch_result.get("diagnosis") or "")
    if not payloads and seed_id in SEED_FALLBACK_OPPORTUNITY_IDS:
        from nativeforge.services.grants_gov_search_api_adapter_service import (
            FETCH_MODE_LIVE,
            _parse_detail_to_payload,
            fetch_grants_gov_opportunity_detail,
        )

        opp_id = SEED_FALLBACK_OPPORTUNITY_IDS[seed_id]
        detail, detail_live = fetch_grants_gov_opportunity_detail(opp_id)
        if detail_live and detail:
            hit = {
                "id": opp_id,
                "number": detail.get("opportunityNumber"),
                "title": detail.get("opportunityTitle"),
            }
            payloads = [
                _parse_detail_to_payload(
                    hit,
                    detail,
                    source=source,
                    fetch_mode=FETCH_MODE_LIVE,
                    search_live=True,
                    detail_live=True,
                )
            ]
            diagnosis = "iegap_nofo_absent_epa_tribal_environmental_fallback"
            fetch_result = {
                **fetch_result,
                "chosen_opportunity_id": opp_id,
                "diagnosis": diagnosis,
            }
    if not payloads:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "grant_id": grant.get("grant_id"),
                "source_seed_id": seed_id,
                "reingested": False,
                "diagnosis": fetch_result.get("diagnosis"),
                "upstream_issue": (
                    "default keyword search returned wrong NOFO; "
                    "refined search found no matching posted NOFO"
                ),
                "prior_placeholder": str(grant.get("eligibility_text") or "").startswith(
                    "Open to eligible applicants"
                ),
            }
        )
    updated_grant = _payload_to_grant_update(
        grant,
        payloads[0],
        reingest_meta=fetch_result,
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "grant_id": grant.get("grant_id"),
            "source_seed_id": seed_id,
            "reingested": True,
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
        "schema_version": "nf15_eligibility_reingest_pulls_v1",
        "pull_count": len(results),
        "results": results,
    }
    FIXTURE_PATH.write_text(json.dumps(pulls, indent=2), encoding="utf-8")

    updated_grants = []
    for g in corpus:
        gid = g["grant_id"]
        match = next((r for r in results if r.get("grant_id") == gid and r.get("reingested")), None)
        if match:
            updated_grants.append(match["updated_grant"])
        else:
            updated_grants.append(g)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "reingest_count": len(REINGEST_GRANT_IDS),
            "reingested_success_count": sum(1 for r in results if r.get("reingested")),
            "results": results,
            "updated_grants": updated_grants,
            "fixture_path": str(FIXTURE_PATH),
            "honest_labeling": True,
        }
    )


def build_tribal_grant_eligibility_reingest_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "target_grant_ids": list(REINGEST_GRANT_IDS),
            "target_seed_ids": list(REINGEST_SEED_IDS),
            "preview_only": True,
        }
    )
