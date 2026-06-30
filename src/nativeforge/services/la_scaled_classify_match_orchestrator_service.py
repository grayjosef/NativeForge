"""LA block: classify + match scaled federal corpus (synthetic profile)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.real_grant_classify_match_service import (
    classify_and_match_real_grants,
)
from nativeforge.services.real_grant_workbench_queue_service import (
    build_real_grant_workbench_queues,
)
from nativeforge.services.matching_profile_selector_service import (
    PROFILE_SYNTHETIC_RED_CEDAR,
    build_matching_profile_selector_contract,
    resolve_matching_profile,
)
from nativeforge.services.real_resolver_validation_gate_service import (
    build_real_resolver_validation_gate_contract,
    require_real_resolver_validation_gate,
)
from nativeforge.services.scaled_federal_corpus_persist_service import (
    load_scaled_federal_corpus,
)

SCHEMA_VERSION = "nf_la_scaled_classify_match_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_la_scaled_classify_match_block(
    *,
    org_id: Any = None,
    nf_live_source_ingestion: bool = True,
    nf_real_resolver_validation: bool = True,
    profile_fixture_key: str | None = None,
) -> dict[str, Any]:
    require_real_resolver_validation_gate(
        nf_live_source_ingestion=nf_live_source_ingestion,
        nf_real_resolver_validation=nf_real_resolver_validation,
    )
    grants = load_scaled_federal_corpus()
    profile = resolve_matching_profile(
        profile_fixture_key=profile_fixture_key or PROFILE_SYNTHETIC_RED_CEDAR,
    )
    classify_match = classify_and_match_real_grants(
        grants=grants,
        profile=profile,
        profile_fixture_key=profile_fixture_key,
    )
    queues = build_real_grant_workbench_queues(classify_match_result=classify_match)
    all_need_review = all(
        m["match_label"] == "needs_operator_review" for m in classify_match["matches"]
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "org_id": str(org_id) if org_id else None,
            "gate": build_real_resolver_validation_gate_contract(
                nf_live_source_ingestion=nf_live_source_ingestion,
                nf_real_resolver_validation=nf_real_resolver_validation,
            ),
            "classify_match": classify_match,
            "workbench_queues": queues,
            "grant_count": classify_match["grant_count"],
            "profile_selector": build_matching_profile_selector_contract(),
            "selected_profile_fixture_key": profile.get("fixture_key"),
            "all_needs_operator_review": all_need_review,
            "honest_labeling": True,
        }
    )
