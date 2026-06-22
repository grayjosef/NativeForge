"""Sprint 339: NF-14 mixed-corpus discrimination closeout packet."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_mixed_corpus_discrimination_closeout_v1"
ARTIFACT_TYPE = "nf14_mixed_corpus_discrimination_closeout"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_mixed_corpus_discrimination_closeout_packet(
    *,
    gate_verification: dict[str, Any],
) -> dict[str, Any]:
    return _json_safe(
        {
            "artifact_type": ARTIFACT_TYPE,
            "schema_version": SCHEMA_VERSION,
            "block": "NF-14",
            "verification_passed": gate_verification.get("verification_passed"),
            "checks": gate_verification.get("checks"),
            "label_distribution": gate_verification.get("label_distribution"),
            "distinct_label_count": gate_verification.get("distinct_label_count"),
            "labels_missing_from_corpus": gate_verification.get(
                "labels_missing_from_corpus"
            ),
            "tribe_eligible_broad_count": gate_verification.get(
                "tribe_eligible_broad_count"
            ),
            "tribe_eligible_broad_discoverable_count": gate_verification.get(
                "tribe_eligible_broad_discoverable_count"
            ),
            "overclaim_catches": gate_verification.get("overclaim_catches"),
            "over_filter_catches": gate_verification.get("over_filter_catches"),
            "worked_examples_per_label": gate_verification.get(
                "worked_examples_per_label"
            ),
            "nf13_irrelevant_reexamination": gate_verification.get(
                "nf13_irrelevant_reexamination"
            ),
            "stop_at_checkpoint": True,
            "honest_labeling": True,
            "from_real_source_text": True,
        }
    )
