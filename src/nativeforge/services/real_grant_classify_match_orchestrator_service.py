"""Sprint 329: NF-13 classify + match real grants orchestrator."""

from __future__ import annotations

import json
import uuid
from typing import Any

from nativeforge.services.real_grant_classify_match_service import (
    classify_and_match_real_grants,
)
from nativeforge.services.real_grant_workbench_queue_service import (
    build_real_grant_workbench_queues,
)
from nativeforge.services.real_resolver_validation_gate_service import (
    build_real_resolver_validation_gate_contract,
    require_real_resolver_validation_gate,
)

SCHEMA_VERSION = "nf_real_grant_classify_match_orchestrator_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_real_grant_classify_match_block(
    *,
    org_id: uuid.UUID | None = None,
    nf_live_source_ingestion: bool = True,
    nf_real_resolver_validation: bool = True,
) -> dict[str, Any]:
    require_real_resolver_validation_gate(
        nf_live_source_ingestion=nf_live_source_ingestion,
        nf_real_resolver_validation=nf_real_resolver_validation,
    )
    classify_match = classify_and_match_real_grants()
    queues = build_real_grant_workbench_queues(classify_match_result=classify_match)
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
            "label_distribution": classify_match["label_distribution"],
            "matched_grant_count": classify_match["matched_grant_count"],
            "worked_examples": classify_match["worked_examples"],
            "stop_at_checkpoint": True,
            "honest_labeling": True,
        }
    )
