"""Sprint 337: NF-14 mixed-corpus classifier discrimination orchestrator."""

from __future__ import annotations

import json
import uuid
from typing import Any

from nativeforge.services.mixed_corpus_builder_service import (
    build_mixed_corpus_builder_contract,
)
from nativeforge.services.mixed_corpus_classification_service import (
    classify_mixed_real_corpus,
)
from nativeforge.services.nf13_irrelevant_reexamination_service import (
    reexamine_nf13_irrelevant_grants,
)
from nativeforge.services.real_resolver_validation_gate_service import (
    build_real_resolver_validation_gate_contract,
    require_real_resolver_validation_gate,
)

SCHEMA_VERSION = "nf_mixed_corpus_discrimination_orchestrator_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_mixed_corpus_discrimination_block(
    *,
    org_id: uuid.UUID | None = None,
    nf_live_source_ingestion: bool = True,
    nf_real_resolver_validation: bool = True,
) -> dict[str, Any]:
    require_real_resolver_validation_gate(
        nf_live_source_ingestion=nf_live_source_ingestion,
        nf_real_resolver_validation=nf_real_resolver_validation,
    )
    classification = classify_mixed_real_corpus()
    nf13_reexam = reexamine_nf13_irrelevant_grants()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "org_id": str(org_id) if org_id else None,
            "gate": build_real_resolver_validation_gate_contract(
                nf_live_source_ingestion=nf_live_source_ingestion,
                nf_real_resolver_validation=nf_real_resolver_validation,
            ),
            "corpus": build_mixed_corpus_builder_contract(),
            "classification": classification,
            "nf13_irrelevant_reexamination": nf13_reexam,
            "label_distribution": classification["label_distribution"],
            "distinct_label_count": classification["distinct_label_count"],
            "tribe_eligible_broad_discoverable_count": classification[
                "tribe_eligible_broad_discoverable_count"
            ],
            "worked_examples_per_label": classification["worked_examples_per_label"],
            "stop_at_checkpoint": True,
            "honest_labeling": True,
        }
    )
