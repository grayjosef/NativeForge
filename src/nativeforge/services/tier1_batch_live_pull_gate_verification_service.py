"""Sprint 319: NF-12 gate verification — honest labeling lock + batch tier-1 pull."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from nativeforge.db.models import Organization
from nativeforge.repositories import activation_state as activation_repo
from nativeforge.services.grants_gov_eligibility_parser_service import (
    parse_grants_gov_synopsis_eligibility,
)
from nativeforge.services.grants_gov_search_api_adapter_service import (
    load_recorded_grants_gov_search_fixture,
)
from nativeforge.services.real_fetch_honest_labeling_guard_service import (
    assert_real_fetch_honest_labeling,
    build_real_fetch_honest_labeling_guard_contract,
)
from nativeforge.services.real_tier1_live_fetch_service import (
    reset_real_tier1_fetch_rate_limit,
)
from nativeforge.services.real_url_resolver_service import (
    reset_real_url_resolver_rate_limit,
)
from nativeforge.services.source_seed_url_correction_service import (
    SEED_URL_CORRECTIONS,
)
from nativeforge.services.tier1_batch_live_fetch_service import (
    reset_tier1_batch_fetch_rate_limits,
)
from nativeforge.services.tier1_batch_live_pull_orchestrator_service import (
    run_tier1_batch_live_pull_block,
)

SCHEMA_VERSION = "nf_tier1_batch_live_pull_gate_verification_v1"

_CONFIRMATION = {
    "operator_handle": "staging-operator",
    "human_activation_acknowledged": True,
    "public_only_acknowledged": True,
    "batch_tier1_public_activation_acknowledged": True,
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _ci_url_fetcher(url: str, method: str) -> dict[str, Any]:
    if "invalid" in url or "does-not-exist" in url:
        return {"http_status": 404, "body_snippet": "", "final_url": url}
    return {
        "http_status": 200,
        "body_snippet": "public grants listing",
        "final_url": url,
    }


def _ci_grants_gov_post(url: str, body: dict[str, Any]) -> dict[str, Any]:
    fixtures = (
        Path(__file__).resolve().parents[3] / "fixtures" / "source_ingestion"
    )
    if "search2" in url:
        if body.get("cfda") == "15.148":
            tedc = fixtures / "grants_gov_search2_bia_tedc_hit.json"
            return json.loads(tedc.read_text(encoding="utf-8"))
        return {
            "errorcode": 0,
            "msg": "Webservice Succeeds",
            "data": {"oppHits": [], "hitCount": 0},
        }
    if "fetchOpportunity" in url:
        detail = fixtures / "grants_gov_fetch_opportunity_362648.json"
        return json.loads(detail.read_text(encoding="utf-8"))
    return {"errorcode": 1, "msg": "unknown", "data": {}}


def verify_tier1_batch_live_pull_gates(
    session: Any,
    *,
    org: Organization,
) -> dict[str, Any]:
    reset_real_url_resolver_rate_limit()
    reset_real_tier1_fetch_rate_limit()
    reset_tier1_batch_fetch_rate_limits()
    fixture_rows = load_recorded_grants_gov_search_fixture()
    for row in fixture_rows:
        assert_real_fetch_honest_labeling(row)
    detail_fixture = (
        Path(__file__).resolve().parents[3]
        / "fixtures"
        / "source_ingestion"
        / "grants_gov_fetch_opportunity_362648.json"
    )
    raw = json.loads(detail_fixture.read_text(encoding="utf-8"))
    syn = (raw.get("data") or {}).get("synopsis") or {}
    elig = parse_grants_gov_synopsis_eligibility(syn)
    activation_row = activation_repo.get_or_create_activation_state(
        session,
        organization_id=org.id,
        is_demo=True,
    )
    activation_row.live_publish_enabled = True
    activation_row.kill_switch_engaged = False
    session.flush()
    result = run_tier1_batch_live_pull_block(
        session,
        org=org,
        operator_confirmation=_CONFIRMATION,
        url_fetcher=_ci_url_fetcher,
        http_post=_ci_grants_gov_post,
        max_batch_size=8,
    )
    posture = result["corrected_posture_report"]
    activation = result["batch_activation"]
    batch_fetch = result["batch_live_fetch"]
    checks = {
        "honest_labeling_guard": True,
        "fixture_never_real_fetch": all(
            not row.get("real_fetch") for row in fixture_rows
        ),
        "tribal_eligible_tedc": elig["tribal_eligible"] is True,
        "eligibility_text_populated": bool(elig["eligibility_text"]),
        "url_corrections_applied": len(SEED_URL_CORRECTIONS) >= 40,
        "dead_urls_reduced": posture["quality_summary"]["dead_url_count"] <= 8,
        "batch_activated": activation["activated_count"] >= 1,
        "real_grants_when_tedc_in_batch": batch_fetch["real_grant_count"] >= 1,
        "stop_at_checkpoint": result["stop_at_checkpoint"] is True,
        "never_synthesized": batch_fetch["never_synthesized"] is True,
    }
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "verification_passed": all(checks.values()),
            "checks": checks,
            "guard_contract": build_real_fetch_honest_labeling_guard_contract(),
            "batch_result_summary": {
                "sources_activated": result["sources_activated"],
                "real_grants_ingested": result["real_grants_ingested"],
                "empty_nofo_count": batch_fetch["empty_count"],
                "dead_url_count": posture["quality_summary"]["dead_url_count"],
            },
        }
    )
