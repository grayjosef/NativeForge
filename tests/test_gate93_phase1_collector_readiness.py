"""Gate 93 - Phase 1 collector readiness preflight.

The gate's purpose is to make accidental activation impossible, so most of these
tests are about what must *not* be reachable: an activation without a payload
store, a Grants.gov surface without the notice, a queue item that starts
approved, a preflight that says it is safe to fetch.
"""

from __future__ import annotations

import ast
import hashlib
import io
import json
from pathlib import Path

import pytest

from nativeforge.services.external_source_registry_import_service import (
    import_external_source_registry,
)
from nativeforge.services.external_source_registry_seed_service import (
    build_registry_seed_set,
)
from nativeforge.services.grants_gov_attribution_service import (
    ATTRIBUTION_TEXT,
    CUSTOMER_VISIBLE_SURFACES,
    GRANTS_GOV_SOURCE_IDS,
    attribution_invariant_failures,
    build_attribution_contract,
    grants_gov_output_may_be_customer_visible,
    verify_attribution_text,
)
from nativeforge.services.phase1_collector_activation_policy_service import (
    ATTRIBUTION_GATED_SOURCES,
    PHASE1_SOURCE_IDS,
    REQUIRED_PRECONDITIONS,
    SCRAPING_PROHIBITED_SOURCES,
    build_phase1_activation_matrix,
    default_phase1_preflights,
    evaluate_phase1_source,
    phase1_preflight_invariant_failures,
    policy_invariant_failures,
)
from nativeforge.services.phase1_readiness_artifact_service import (
    ARTIFACT_DIR,
    ATTRIBUTION_TXT_NAME,
    MATRIX_CSV_NAME,
    MATRIX_JSON_NAME,
    QUEUE_CSV_NAME,
    REQUIRED_DECLARATIONS,
    STORE_JSON_NAME,
    SUMMARY_NAME,
    Phase1ReadinessArtifactError,
    artifact_claim_failures,
    build_readiness_bundle,
    render_readiness_summary,
    write_phase1_readiness_artifacts,
)
from nativeforge.services.raw_payload_store_contract_service import (
    EVIDENCE_CRITICAL_FIELDS,
    REQUIRED_FIELDS,
    build_store_contract,
    store_contract_invariant_failures,
    validate_payload_record,
)
from nativeforge.services.source_activation_preflight_service import (
    ACTIVATION_STATUSES,
    CRAWLER_COLLECTOR_TYPES,
    CREDENTIALED_COLLECTOR_TYPES,
    REQUIREMENT_KEYS,
    build_activation_preflight,
    preflight_invariant_failures,
    summarise_preflight,
)
from nativeforge.services.source_terms_review_queue_service import (
    SAM_CREDENTIAL_ITEM,
    SPA_TERMS_PAGES,
    build_terms_review_queue,
    queue_invariant_failures,
)
from nativeforge.services.trust_surface_service import build_trust_manifest

REPO_ROOT = Path(__file__).resolve().parents[1]
V2_CSV = (
    REPO_ROOT / "fixtures/external_source_registry/nativeforge-source-registry-v2.csv"
)

GATE93_SERVICES = (
    "source_activation_preflight_service",
    "grants_gov_attribution_service",
    "phase1_collector_activation_policy_service",
    "raw_payload_store_contract_service",
    "source_terms_review_queue_service",
    "phase1_readiness_artifact_service",
)

# Everything satisfied, for a plain unauthenticated API collector.
ALL_SATISFIED = dict(
    terms_status="NO_REVIEW_REQUIRED",
    legal_review_status="not_required",
    credential_status="not_required",
    attribution_status="not_required",
    user_agent_status="not_required",
    rate_limit_status="policy_declared",
    storage_status="contract_satisfied",
    scheduler_status="policy_declared",
    monitoring_status="not_started",
)


@pytest.fixture(scope="module")
def v2_seeds() -> list[dict]:
    imported = import_external_source_registry(
        csv_text=V2_CSV.read_text(encoding="utf-8-sig"), source_label="registry_v2"
    )
    return build_registry_seed_set(imported=imported)["seeds"]


# --------------------------------------------------------------------------
# 93B - activation preflight
# --------------------------------------------------------------------------


def test_preflight_defaults_to_blocked() -> None:
    """Nothing supplied is not a pass."""
    result = build_activation_preflight(source_id="X")
    assert result["activation_allowed"] is False
    assert result["activation_status"] in {"activation_blocked", "activation_unknown"}
    assert preflight_invariant_failures(result) == []


def test_preflight_with_everything_satisfied_allows() -> None:
    result = build_activation_preflight(
        source_id="X", collector_type="public_api", **ALL_SATISFIED
    )
    assert result["activation_status"] == "activation_allowed"
    assert result["activation_allowed"] is True
    assert result["requirements_missing"] == []
    assert preflight_invariant_failures(result) == []


def test_terms_review_required_blocks_activation() -> None:
    result = build_activation_preflight(
        source_id="X",
        collector_type="public_api",
        **{**ALL_SATISFIED, "terms_status": "TERMS_REVIEW_REQUIRED"},
    )
    assert result["activation_allowed"] is False
    assert result["activation_status"] == "activation_blocked"
    assert any("terms_status_blocks" in r for r in result["blocked_reasons"])


def test_human_review_only_blocks_automation() -> None:
    """A checklist cannot lift a requirement that a person must decide."""
    result = build_activation_preflight(
        source_id="X",
        collector_type="public_api",
        **{**ALL_SATISFIED, "terms_status": "HUMAN_REVIEW_ONLY"},
    )
    assert result["activation_status"] == "activation_requires_human_review"
    assert result["human_review_required"] is True
    assert result["activation_allowed"] is False
    assert result["safe_to_schedule"] is False
    assert preflight_invariant_failures(result) == []


def test_unrecognised_status_value_blocks_rather_than_passes() -> None:
    """Deny by default: a typo is not a pass."""
    result = build_activation_preflight(
        source_id="X",
        collector_type="public_api",
        **{**ALL_SATISFIED, "terms_status": "NO_REVIEW_REQUIRD"},
    )
    assert result["activation_allowed"] is False
    assert result["resolved_inputs"]["terms_status"] == "UNKNOWN"


def test_missing_raw_payload_storage_blocks_activation() -> None:
    result = build_activation_preflight(
        source_id="X",
        collector_type="public_api",
        **{**ALL_SATISFIED, "storage_status": "missing"},
    )
    assert result["activation_allowed"] is False
    assert "raw_payload_storage" in result["requirements_missing"]


def test_missing_rate_limit_policy_blocks_activation() -> None:
    result = build_activation_preflight(
        source_id="X",
        collector_type="public_api",
        **{**ALL_SATISFIED, "rate_limit_status": "missing"},
    )
    assert result["activation_allowed"] is False
    assert "rate_limit_policy" in result["requirements_missing"]


@pytest.mark.parametrize("collector_type", sorted(CREDENTIALED_COLLECTOR_TYPES))
def test_credentialed_collector_cannot_exempt_itself(collector_type: str) -> None:
    """`not_required` must not satisfy a collector type that needs a key."""
    result = build_activation_preflight(
        source_id="X", collector_type=collector_type, **ALL_SATISFIED
    )
    assert result["activation_allowed"] is False
    assert "credential" in result["requirements_missing"]

    with_key = build_activation_preflight(
        source_id="X",
        collector_type=collector_type,
        **{**ALL_SATISFIED, "credential_status": "present_and_valid"},
    )
    assert with_key["activation_allowed"] is True


@pytest.mark.parametrize("collector_type", sorted(CRAWLER_COLLECTOR_TYPES))
def test_crawler_cannot_exempt_itself_from_a_user_agent_policy(
    collector_type: str,
) -> None:
    result = build_activation_preflight(
        source_id="X", collector_type=collector_type, **ALL_SATISFIED
    )
    assert result["activation_allowed"] is False
    assert "user_agent_policy" in result["requirements_missing"]


def test_forbidden_ai_crawler_user_agent_never_satisfies() -> None:
    result = build_activation_preflight(
        source_id="X",
        collector_type="html_crawler",
        **{**ALL_SATISFIED, "user_agent_status": "forbidden_ai_crawler"},
    )
    assert result["activation_allowed"] is False
    assert preflight_invariant_failures(result) == []


def test_monitoring_cannot_start_from_unknown() -> None:
    for state in ("unknown", "running", "scheduled"):
        result = build_activation_preflight(
            source_id="X",
            collector_type="public_api",
            **{**ALL_SATISFIED, "monitoring_status": state},
        )
        assert result["safe_to_schedule"] is False, state
        assert result["activation_allowed"] is False, state


def test_every_requirement_is_accounted_for() -> None:
    result = build_activation_preflight(source_id="X", collector_type="public_api")
    accounted = set(result["requirements_satisfied"]) | set(
        result["requirements_missing"]
    )
    assert accounted == set(REQUIREMENT_KEYS)


def test_preflight_never_says_safe_to_fetch_now() -> None:
    result = build_activation_preflight(
        source_id="X", collector_type="public_api", **ALL_SATISFIED
    )
    assert result["safe_to_fetch_now"] is False
    lying = dict(result, safe_to_fetch_now=True)
    assert "preflight_claimed_safe_to_fetch_now" in preflight_invariant_failures(lying)


def test_preflight_activates_nothing_and_fetches_nothing() -> None:
    result = build_activation_preflight(
        source_id="X", collector_type="public_api", **ALL_SATISFIED
    )
    assert result["activation_performed"] is False
    assert result["fetch_performed"] is False


def test_preflight_summary_counts_no_fetches() -> None:
    results = [
        build_activation_preflight(source_id="A", collector_type="public_api"),
        build_activation_preflight(
            source_id="B", collector_type="public_api", **ALL_SATISFIED
        ),
    ]
    summary = summarise_preflight(results)
    assert summary["safe_to_fetch_now_count"] == 0
    assert summary["sources_activated"] == 0
    assert set(summary["by_activation_status"]) == ACTIVATION_STATUSES


# --------------------------------------------------------------------------
# 93C - Grants.gov attribution
# --------------------------------------------------------------------------


def test_attribution_text_is_exactly_the_required_notice() -> None:
    assert ATTRIBUTION_TEXT == (
        "This product uses the Grants.gov API but is not endorsed or certified "
        "by the U.S. Department of Health and Human Services."
    )


def test_missing_attribution_fails() -> None:
    assert verify_attribution_text(None)["result"] == "missing"
    assert verify_attribution_text("")["result"] == "missing"


@pytest.mark.parametrize(
    "candidate",
    [
        "This product uses the Grants.gov API but is not endorsed or certified "
        "by the U.S. Department of Health and Human Services",  # period dropped
        ATTRIBUTION_TEXT.lower(),
        ATTRIBUTION_TEXT.upper(),
        ATTRIBUTION_TEXT.replace("  ", " ").replace(" ", "  "),
        ATTRIBUTION_TEXT.replace("U.S.", "US"),
    ],
)
def test_altered_attribution_fails(candidate: str) -> None:
    result = verify_attribution_text(candidate)
    assert result["matches_verbatim"] is False
    assert result["result"] != "present_and_verbatim"


@pytest.mark.parametrize(
    "candidate",
    [
        "Data sourced from the Grants.gov API. NativeForge is not affiliated "
        "with HHS.",
        "Powered by Grants.gov.",
    ],
)
def test_paraphrased_attribution_fails(candidate: str) -> None:
    result = verify_attribution_text(candidate)
    assert result["matches_verbatim"] is False
    assert result["result"] == "paraphrased"


def test_attribution_in_docs_only_does_not_satisfy() -> None:
    """A Python constant and a markdown file are not customer-visible."""
    contract = build_attribution_contract(
        surfaces_present=["documentation", "service_constant"]
    )
    assert contract["attribution_is_customer_visible"] is False
    assert contract["attribution_satisfied"] is False
    assert "attribution_not_customer_visible" in contract["blocked_reasons"]
    assert attribution_invariant_failures(contract) == []


def test_customer_visible_surfaces_are_only_runtime_and_ui() -> None:
    assert CUSTOMER_VISIBLE_SURFACES == frozenset({"runtime_payload", "rendered_ui"})


def test_attribution_is_present_in_the_live_trust_manifest() -> None:
    """The manifest is what a customer's browser actually receives."""
    manifest = build_trust_manifest(org_type="demo")
    assert manifest["source_attribution"]["grants_gov_notice"] == ATTRIBUTION_TEXT

    contract = build_attribution_contract(trust_manifest=manifest)
    assert contract["attribution_status"] == "present_and_verbatim"
    assert "runtime_payload" in contract["customer_visible_surfaces"]
    assert contract["attribution_satisfied"] is True
    assert attribution_invariant_failures(contract) == []


def test_trust_manifest_does_not_claim_a_grants_gov_collector() -> None:
    manifest = build_trust_manifest(org_type="demo")
    assert manifest["source_attribution"]["grants_gov_collector_active"] is False


def test_attribution_is_rendered_by_the_trust_card() -> None:
    """Runtime payload plus a component that draws it. Neither alone is enough."""
    card = (
        REPO_ROOT / "frontend/src/components/TrustCenterCard.tsx"
    ).read_text(encoding="utf-8")
    assert "source_attribution" in card
    assert "grants_gov_notice" in card
    assert "nf-grants-gov-attribution" in card
    # The string itself must not be hardcoded in the component - one source.
    assert "not endorsed or certified" not in card


def test_grants_gov_output_blocked_without_attribution() -> None:
    empty = build_attribution_contract()
    for source_id in sorted(GRANTS_GOV_SOURCE_IDS):
        decision = grants_gov_output_may_be_customer_visible(
            source_id=source_id, attribution_contract=empty
        )
        assert decision["attribution_required"] is True
        assert decision["may_surface_customer_data"] is False
        assert "grants_gov_attribution_absent" in decision["blocked_reasons"]


def test_non_grants_gov_source_does_not_require_the_notice() -> None:
    decision = grants_gov_output_may_be_customer_visible(
        source_id="federal_register_api",
        attribution_contract=build_attribution_contract(),
    )
    assert decision["attribution_required"] is False
    assert decision["may_surface_customer_data"] is True


def test_attribution_cannot_be_satisfied_by_a_non_customer_surface() -> None:
    contract = build_attribution_contract(
        surfaces_present=["documentation", "service_constant"]
    )
    lying = dict(contract, attribution_satisfied=True)
    fails = attribution_invariant_failures(lying)
    assert "attribution_satisfied_without_verbatim_text" in fails


# --------------------------------------------------------------------------
# 93D - Phase 1 activation policy
# --------------------------------------------------------------------------


def test_phase1_has_exactly_five_sources() -> None:
    assert PHASE1_SOURCE_IDS == (
        "grants_gov_daily_extract",
        "grants_gov_search2_fetch",
        "federal_register_api",
        "sam_assistance_listings_api",
        "usaspending_api_v2",
    )


def test_all_phase1_sources_default_to_not_active() -> None:
    matrix = build_phase1_activation_matrix()
    assert matrix["source_count"] == 5
    for source in matrix["sources"]:
        assert source["collector_status"] == "not_active"
    assert policy_invariant_failures(matrix) == []


def test_matrix_reports_no_active_collectors_or_monitors() -> None:
    matrix = build_phase1_activation_matrix(
        preflight_by_source=default_phase1_preflights()
    )
    assert matrix["collectors_active"] == 0
    assert matrix["monitors_active"] == 0
    assert matrix["live_fetch_performed"] is False
    assert matrix["live_source_coverage"] is False
    assert policy_invariant_failures(matrix) == []


@pytest.mark.parametrize("source_id", list(PHASE1_SOURCE_IDS))
def test_no_phase1_source_may_fetch_or_schedule(source_id: str) -> None:
    result = evaluate_phase1_source(source_id=source_id)
    assert result["may_fetch_live_now"] is False
    assert result["may_schedule_monitor"] is False
    assert result["may_surface_customer_data"] is False


@pytest.mark.parametrize("source_id", list(PHASE1_SOURCE_IDS))
def test_every_phase1_source_requires_a_raw_payload_store(source_id: str) -> None:
    assert "raw_payload_store" in REQUIRED_PRECONDITIONS[source_id]


@pytest.mark.parametrize("source_id", list(PHASE1_SOURCE_IDS))
def test_missing_preflight_is_a_missing_precondition(source_id: str) -> None:
    """Absence of a check is not a check that passed."""
    result = evaluate_phase1_source(source_id=source_id)
    assert result["preflight_present"] is False
    assert result["preflight_passed"] is False
    assert "activation_preflight_pass" in result["missing_preconditions"]


@pytest.mark.parametrize("source_id", sorted(ATTRIBUTION_GATED_SOURCES))
def test_grants_gov_sources_require_attribution(source_id: str) -> None:
    result = evaluate_phase1_source(source_id=source_id)
    assert result["attribution_required"] is True
    assert "grants_gov_attribution" in result["required_preconditions"]


def test_grants_gov_extract_requires_a_retention_alert_policy() -> None:
    """7-day retention: a missed day is unrecoverable."""
    required = REQUIRED_PRECONDITIONS["grants_gov_daily_extract"]
    assert "retention_alert_policy" in required


def test_grants_gov_search2_requires_amendment_materiality() -> None:
    required = REQUIRED_PRECONDITIONS["grants_gov_search2_fetch"]
    assert "amendment_materiality_policy" in required


def test_federal_register_requires_cadence_and_public_inspection() -> None:
    required = REQUIRED_PRECONDITIONS["federal_register_api"]
    assert "polling_cadence_policy" in required
    assert "public_inspection_handling" in required


def test_sam_gov_scraping_is_prohibited_and_key_is_required() -> None:
    result = evaluate_phase1_source(source_id="sam_assistance_listings_api")
    assert result["scraping_prohibited"] is True
    required = set(result["required_preconditions"])
    assert "api_key" in required
    assert "role_and_rate_limit_policy" in required
    assert "no_scraping_ack" in required
    assert SCRAPING_PROHIBITED_SOURCES == frozenset({"sam_assistance_listings_api"})


def test_sam_gov_preflight_blocks_on_the_missing_credential() -> None:
    preflights = default_phase1_preflights()
    sam = preflights["sam_assistance_listings_api"]
    assert sam["activation_allowed"] is False
    assert "credential" in sam["requirements_missing"]


def test_usaspending_is_prior_award_only() -> None:
    result = evaluate_phase1_source(source_id="usaspending_api_v2")
    assert result["prior_award_only"] is True
    assert "prior_award_only_classification" in result["required_preconditions"]


def test_default_phase1_preflights_are_all_blocked_today() -> None:
    """The store does not exist, so nothing can pass yet."""
    preflights = default_phase1_preflights()
    assert set(preflights) == set(PHASE1_SOURCE_IDS)
    for source_id, result in preflights.items():
        assert result["activation_allowed"] is False, source_id
        assert "raw_payload_storage" in result["requirements_missing"], source_id
    assert phase1_preflight_invariant_failures(preflights) == []


def test_unknown_phase1_source_is_rejected() -> None:
    with pytest.raises(ValueError):
        evaluate_phase1_source(source_id="grants_gov_rss")


def test_unrecognised_precondition_is_reported_not_credited() -> None:
    result = evaluate_phase1_source(
        source_id="usaspending_api_v2",
        satisfied_preconditions=["raw_payload_store", "definitely_fine"],
    )
    assert result["unrecognised_preconditions"] == ["definitely_fine"]
    assert "raw_payload_store" in result["satisfied_preconditions"]


# --------------------------------------------------------------------------
# 93E - raw payload store
# --------------------------------------------------------------------------


def _good_payload() -> dict:
    digest = hashlib.sha256(b"payload").hexdigest()
    return {
        "payload_id": "p1",
        "source_id": "grants_gov_daily_extract",
        "retrieved_at": "2026-08-26T05:30:00Z",
        "retrieval_method": "bulk_extract",
        "request_fingerprint": "GET GrantsDBExtract20260826v2.zip",
        "response_status": 200,
        "response_headers_hash": digest,
        "raw_payload_hash": digest,
        "raw_payload_size_bytes": 81_000_000,
        "canonical_url": "https://example.invalid/extract.zip",
        "attribution_required": True,
        "terms_status": "ATTRIBUTION_REQUIRED",
        "parser_status": "not_parsed",
        "retention_policy": "retain_indefinite",
        "redaction_status": "not_required",
        "secret_scan_status": "clean",
    }


def test_store_contract_lists_all_sixteen_required_fields() -> None:
    contract = build_store_contract()
    assert len(REQUIRED_FIELDS) == 16
    assert contract["required_fields"] == list(REQUIRED_FIELDS)
    assert store_contract_invariant_failures(contract) == []


def test_store_contract_does_not_claim_to_be_implemented() -> None:
    contract = build_store_contract()
    assert contract["store_implemented"] is False
    assert contract["payloads_stored"] == 0


def test_store_contract_performs_no_fetch() -> None:
    contract = build_store_contract()
    assert contract["fetch_performed"] is False
    assert contract["network_access_performed"] is False
    result = validate_payload_record(_good_payload())
    assert result["fetch_performed"] is False
    assert result["record_stored"] is False


def test_complete_payload_record_is_accepted() -> None:
    result = validate_payload_record(_good_payload())
    assert result["accepted"] is True
    assert result["promotion_allowed"] is True
    assert result["payload_is_trustworthy_as_collected"] is True
    assert store_contract_invariant_failures(result) == []


def test_payload_without_a_hash_is_rejected() -> None:
    result = validate_payload_record({**_good_payload(), "raw_payload_hash": None})
    assert result["accepted"] is False
    assert result["payload_is_trustworthy_as_collected"] is False


def test_payload_with_a_non_sha256_hash_is_rejected() -> None:
    result = validate_payload_record(
        {**_good_payload(), "raw_payload_hash": "deadbeef"}
    )
    assert result["accepted"] is False
    assert "raw_payload_hash_is_not_sha256_hex" in result["problems"]


def test_payload_without_retrieved_at_is_rejected() -> None:
    result = validate_payload_record({**_good_payload(), "retrieved_at": None})
    assert result["accepted"] is False
    assert "retrieved_at" in result["evidence_critical_missing"]


def test_payload_without_source_id_is_rejected() -> None:
    result = validate_payload_record({**_good_payload(), "source_id": None})
    assert result["accepted"] is False
    assert "source_id" in result["evidence_critical_missing"]


@pytest.mark.parametrize("status", ["pending", "unknown", "findings"])
def test_promotion_requires_an_affirmatively_clean_secret_scan(status: str) -> None:
    result = validate_payload_record(
        {**_good_payload(), "secret_scan_status": status}
    )
    assert result["secret_scan_clean"] is False
    assert result["promotion_allowed"] is False
    assert result["accepted"] is False


def test_response_headers_may_not_be_stored_verbatim() -> None:
    """Authorization and Set-Cookie live in headers."""
    result = validate_payload_record(
        {**_good_payload(), "response_headers": {"Authorization": "Bearer x"}}
    )
    assert result["accepted"] is False
    assert "response_headers_stored_verbatim" in result["problems"]


def test_zero_byte_body_is_not_recorded_as_content() -> None:
    """The HUD dead-shell shape: HTTP 200 with nothing in it."""
    result = validate_payload_record(
        {**_good_payload(), "raw_payload_size_bytes": 0}
    )
    assert result["accepted"] is False
    assert "zero_byte_payload_recorded_as_content" in result["problems"]


def test_parsed_record_cannot_outrank_a_missing_payload() -> None:
    result = validate_payload_record(
        {**_good_payload(), "raw_payload_hash": None, "parser_status": "parsed_ok"}
    )
    assert result["accepted"] is False
    assert result["payload_is_trustworthy_as_collected"] is False


def test_evidence_critical_fields_are_in_the_required_set() -> None:
    for field in EVIDENCE_CRITICAL_FIELDS:
        assert field in REQUIRED_FIELDS


# --------------------------------------------------------------------------
# 93F - terms review queue
# --------------------------------------------------------------------------


def test_queue_includes_terms_review_required_rows(v2_seeds: list[dict]) -> None:
    queue = build_terms_review_queue(seeds=v2_seeds)
    assert queue["by_risk_type"]["terms_review_required"] > 0
    assert queue_invariant_failures(queue) == []


def test_queue_includes_human_review_only_rows(v2_seeds: list[dict]) -> None:
    queue = build_terms_review_queue(seeds=v2_seeds)
    assert queue["by_risk_type"]["human_review_only"] > 0


def test_queue_covers_every_blocked_source(v2_seeds: list[dict]) -> None:
    """The queue is the work list for exactly the sources that are blocked."""
    blocked = {
        s["source_id"] for s in v2_seeds if s.get("legal_terms_review_required")
    }
    queued = {i["source_id"] for i in build_terms_review_queue(seeds=v2_seeds)["items"]}
    assert blocked <= queued, sorted(blocked - queued)[:5]


def test_queue_includes_the_four_spa_terms_pages(v2_seeds: list[dict]) -> None:
    """'No terms found' is not 'no terms exist'."""
    queue = build_terms_review_queue(seeds=v2_seeds)
    queued = {i["source_id"] for i in queue["items"]}
    for source_id, _, _ in SPA_TERMS_PAGES:
        assert source_id in queued
    assert queue["by_risk_type"]["terms_text_unretrievable"] == 4


def test_spa_terms_pages_are_queued_even_with_no_registry(v2_seeds: list[dict]) -> None:
    queue = build_terms_review_queue(seeds=[])
    queued = {i["source_id"] for i in queue["items"]}
    for source_id, _, _ in SPA_TERMS_PAGES:
        assert source_id in queued


def test_queue_includes_the_sam_gov_credential_blocker(v2_seeds: list[dict]) -> None:
    queue = build_terms_review_queue(seeds=v2_seeds)
    item = next(
        i for i in queue["items"] if i["source_id"] == SAM_CREDENTIAL_ITEM[0]
    )
    assert item["risk_type"] == "credential_and_role_required"
    assert item["credential_required"] is True
    assert item["automation_blocked"] is True
    assert "1,000" in item["review_required_reason"]


def test_every_queue_item_starts_pending_and_blocks_automation(
    v2_seeds: list[dict],
) -> None:
    queue = build_terms_review_queue(seeds=v2_seeds)
    assert queue["approved_count"] == 0
    for item in queue["items"]:
        assert item["review_status"] == "pending"
        assert item["automation_blocked"] is True


def test_queue_activates_nothing(v2_seeds: list[dict]) -> None:
    queue = build_terms_review_queue(seeds=v2_seeds)
    assert queue["sources_activated"] == 0
    assert queue["reviews_performed"] == 0
    assert queue["fetch_performed"] is False


def test_queue_generation_is_deterministic(v2_seeds: list[dict]) -> None:
    first = build_terms_review_queue(seeds=v2_seeds)
    second = build_terms_review_queue(seeds=v2_seeds)
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)


def test_queue_is_ordered_by_priority_then_source_id(v2_seeds: list[dict]) -> None:
    items = build_terms_review_queue(seeds=v2_seeds)["items"]
    keys = [(i["priority"], i["source_id"]) for i in items]
    assert keys == sorted(keys)


# --------------------------------------------------------------------------
# 93G - artifacts
# --------------------------------------------------------------------------


def test_artifacts_regenerate_deterministically(
    tmp_path: Path, v2_seeds: list[dict]
) -> None:
    first = tmp_path / "a"
    second = tmp_path / "b"
    write_phase1_readiness_artifacts(seeds=v2_seeds, repo_root=first)
    write_phase1_readiness_artifacts(seeds=v2_seeds, repo_root=second)
    for name in (
        MATRIX_JSON_NAME,
        MATRIX_CSV_NAME,
        SUMMARY_NAME,
        QUEUE_CSV_NAME,
        ATTRIBUTION_TXT_NAME,
        STORE_JSON_NAME,
    ):
        a = (first / ARTIFACT_DIR / name).read_bytes()
        b = (second / ARTIFACT_DIR / name).read_bytes()
        assert hashlib.sha256(a).hexdigest() == hashlib.sha256(b).hexdigest(), name


def test_committed_artifacts_match_a_fresh_generation(
    tmp_path: Path, v2_seeds: list[dict]
) -> None:
    committed_dir = REPO_ROOT / ARTIFACT_DIR
    if not (committed_dir / MATRIX_JSON_NAME).exists():
        pytest.skip("Phase 1 readiness artifacts not generated in this tree")
    write_phase1_readiness_artifacts(seeds=v2_seeds, repo_root=tmp_path)
    for name in (
        MATRIX_JSON_NAME,
        MATRIX_CSV_NAME,
        SUMMARY_NAME,
        QUEUE_CSV_NAME,
        ATTRIBUTION_TXT_NAME,
        STORE_JSON_NAME,
    ):
        fresh = (tmp_path / ARTIFACT_DIR / name).read_bytes()
        committed = (committed_dir / name).read_bytes()
        assert hashlib.sha256(committed).hexdigest() == hashlib.sha256(
            fresh
        ).hexdigest(), name


@pytest.mark.parametrize(
    "name",
    [
        MATRIX_JSON_NAME,
        MATRIX_CSV_NAME,
        SUMMARY_NAME,
        QUEUE_CSV_NAME,
        ATTRIBUTION_TXT_NAME,
        STORE_JSON_NAME,
    ],
)
def test_every_artifact_declares_nothing_is_running(name: str) -> None:
    """Each artifact must state all four declarations, and state them false.

    Read back out of the written file, per format - the point is what the file
    says, not what the object that produced it said. A JSON key and a CSV
    column both need their *value* checked, not their presence.
    """
    path = REPO_ROOT / ARTIFACT_DIR / name
    if not path.exists():
        pytest.skip("Phase 1 readiness artifacts not generated in this tree")

    keys = (
        "collectors_active",
        "monitors_active",
        "live_fetch_performed",
        "live_source_coverage",
    )
    raw = path.read_text(encoding="utf-8")

    for key in keys:
        assert key in raw, f"{name} does not state {key}"

    if name.endswith(".json"):
        payload = json.loads(raw)
        for key in keys:
            assert payload[key] is False, f"{name}: {key} is not false"
    elif name.endswith(".csv"):
        import csv as _csv

        rows = list(_csv.DictReader(io.StringIO(raw)))
        assert rows, f"{name} has no rows"
        for row in rows:
            for key in keys:
                assert row[key] == "False", f"{name}: {key} is {row[key]!r}"
    else:
        lowered = raw.lower()
        for key in keys:
            assert f"{key}: false" in lowered, f"{name}: {key} is not stated false"


def test_summary_states_all_four_declarations(v2_seeds: list[dict]) -> None:
    summary = render_readiness_summary(build_readiness_bundle(seeds=v2_seeds))
    for declaration in REQUIRED_DECLARATIONS:
        assert declaration in summary.lower()


def test_artifact_writer_refuses_a_banned_phrase(
    tmp_path: Path, v2_seeds: list[dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    import nativeforge.services.phase1_readiness_artifact_service as mod

    monkeypatch.setattr(
        mod,
        "render_readiness_summary",
        lambda bundle: "monitoring is active\n" + "\n".join(REQUIRED_DECLARATIONS),
    )
    with pytest.raises(Phase1ReadinessArtifactError):
        mod.write_phase1_readiness_artifacts(seeds=v2_seeds, repo_root=tmp_path)


def test_artifact_writer_refuses_a_summary_missing_a_declaration(
    v2_seeds: list[dict],
) -> None:
    bundle = build_readiness_bundle(seeds=v2_seeds)
    failures = artifact_claim_failures(bundle, "a summary that declares nothing")
    assert any(f.startswith("required_declaration_missing") for f in failures)


def test_bundle_invariants_all_hold(v2_seeds: list[dict]) -> None:
    bundle = build_readiness_bundle(seeds=v2_seeds)
    summary = render_readiness_summary(bundle)
    assert artifact_claim_failures(bundle, summary) == []


# --------------------------------------------------------------------------
# Cross-cutting: nothing here reaches the network
# --------------------------------------------------------------------------


@pytest.mark.parametrize("module_name", GATE93_SERVICES)
def test_gate93_services_import_no_network_library(module_name: str) -> None:
    """Parsed, not grepped - a docstring naming httpx is not a call."""
    path = REPO_ROOT / f"src/nativeforge/services/{module_name}.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    forbidden = {
        "requests",
        "httpx",
        "aiohttp",
        "socket",
        "urllib3",
        "http",
        "ftplib",
        "smtplib",
        "selenium",
        "playwright",
    }
    assert not (imported & forbidden), sorted(imported & forbidden)


@pytest.mark.parametrize("module_name", GATE93_SERVICES)
def test_gate93_services_do_not_import_a_live_fetch_module(module_name: str) -> None:
    """The three unguarded fetch paths found in the Gate 93A survey."""
    path = REPO_ROOT / f"src/nativeforge/services/{module_name}.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module)
        elif isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
    hazards = (
        "polite_http_fetch_service",
        "real_url_resolver_service",
        "grants_gov_search_api_adapter_service",
        "real_tier1_live_fetch_service",
        "tier1_batch_live_fetch_service",
    )
    for module in imported:
        for hazard in hazards:
            assert hazard not in module, f"{module_name} imports {hazard}"


@pytest.mark.parametrize("module_name", GATE93_SERVICES)
def test_no_gate93_service_claims_live_coverage(module_name: str) -> None:
    """A service must not assert live coverage in its own prose or output.

    Parsed rather than grepped, and a module's declared blocklist is excluded
    from the scan: `phase1_readiness_artifact_service.BANNED_PHRASES` contains
    these phrases precisely because it forbids them, and a guard that cannot
    tell a prohibition from a claim would fire on the code enforcing it.
    """
    banned = (
        "monitoring is active",
        "live source coverage",
        "65% improvement",
        "collection is live",
        "collectors are active",
    )
    tree = ast.parse(
        (REPO_ROOT / f"src/nativeforge/services/{module_name}.py").read_text(
            encoding="utf-8"
        )
    )

    # String constants belonging to a declared blocklist are prohibitions.
    blocklist_strings: set[str] = set()
    for node in ast.walk(tree):
        # Both forms: `BANNED_PHRASES = (...)` and the annotated
        # `BANNED_PHRASES: tuple[str, ...] = (...)`, which is an AnnAssign and
        # was missed on the first pass.
        if isinstance(node, ast.Assign):
            names = {t.id for t in node.targets if isinstance(t, ast.Name)}
            value = node.value
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names = {node.target.id}
            value = node.value
        else:
            continue
        if value is None:
            continue
        if not any(
            n.endswith(("BANNED_PHRASES", "FORBIDDEN_PHRASES")) for n in names
        ):
            continue
        for sub in ast.walk(value):
            if isinstance(sub, ast.Constant) and isinstance(sub.value, str):
                blocklist_strings.add(sub.value)

    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        if node.value in blocklist_strings:
            continue
        lowered = node.value.lower()
        for phrase in banned:
            assert phrase not in lowered, f"{module_name}: {phrase}"


def test_gate93_outputs_are_json_serialisable(v2_seeds: list[dict]) -> None:
    json.dumps(build_activation_preflight(source_id="X"))
    json.dumps(build_attribution_contract())
    json.dumps(build_phase1_activation_matrix())
    json.dumps(build_store_contract())
    json.dumps(build_terms_review_queue(seeds=v2_seeds))
