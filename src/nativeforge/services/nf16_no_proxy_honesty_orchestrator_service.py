"""Sprint 353: NF-16 no-proxy honesty orchestrator."""

from __future__ import annotations

import json
import uuid
from typing import Any

from nativeforge.services.nf16_no_proxy_corpus_classification_service import (
    classify_nf16_no_proxy_corpus,
)
from nativeforge.services.real_resolver_validation_gate_service import (
    build_real_resolver_validation_gate_contract,
    require_real_resolver_validation_gate,
)
from nativeforge.services.tribal_grant_eligibility_reingest_service import (
    reingest_nf13_placeholder_grants,
)

SCHEMA_VERSION = "nf_nf16_no_proxy_honesty_orchestrator_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_nf16_no_proxy_honesty_block(
    *,
    org_id: uuid.UUID | None = None,
    nf_live_source_ingestion: bool = True,
    nf_real_resolver_validation: bool = True,
) -> dict[str, Any]:
    require_real_resolver_validation_gate(
        nf_live_source_ingestion=nf_live_source_ingestion,
        nf_real_resolver_validation=nf_real_resolver_validation,
    )
    reingest = reingest_nf13_placeholder_grants()
    classification = classify_nf16_no_proxy_corpus()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "org_id": str(org_id) if org_id else None,
            "gate": build_real_resolver_validation_gate_contract(
                nf_live_source_ingestion=nf_live_source_ingestion,
                nf_real_resolver_validation=nf_real_resolver_validation,
            ),
            "eligibility_reingest": reingest,
            "classification": classification,
            "label_distribution": classification["label_distribution"],
            "zero_proxy_substitutions": classification["zero_proxy_substitutions"],
            "no_live_nofo_grants": classification["no_live_nofo_grants"],
            "stop_at_checkpoint": True,
            "honest_labeling": True,
        }
    )
