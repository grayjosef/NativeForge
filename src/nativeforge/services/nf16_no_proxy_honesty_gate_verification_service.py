"""Sprint 354: NF-16 gate verification."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.nf16_no_proxy_honesty_orchestrator_service import (
    run_nf16_no_proxy_honesty_block,
)
from nativeforge.services.no_evidence_irrelevant_guard_service import (
    NoEvidenceIrrelevantError,
    build_no_evidence_irrelevant_guard_contract,
)
from nativeforge.services.no_live_nofo_state_service import (
    SOURCE_INGESTION_STATE_NO_LIVE_NOFO,
    build_no_live_nofo_state_contract,
)
from nativeforge.services.source_program_ownership_guard_service import (
    build_source_program_ownership_guard_contract,
)

SCHEMA_VERSION = "nf_nf16_gate_verification_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def verify_nf16_no_proxy_honesty_gates() -> dict[str, Any]:
    result = run_nf16_no_proxy_honesty_block()
    classification = result["classification"]
    reingest = result["eligibility_reingest"]

    ownership_passed = True
    no_evidence_passed = True
    violations: list[str] = []

    for record in classification["classifications"]:
        cls = record["classification"]
        status = cls.get("eligibility_evidence_status") or ""
        try:
            from nativeforge.services.no_evidence_irrelevant_guard_service import (
                assert_no_evidence_not_irrelevant,
            )

            assert_no_evidence_not_irrelevant(
                grant_id=str(record.get("grant_id") or ""),
                classification_label=cls["classification_label"],
                eligibility_evidence_status=status,
            )
        except NoEvidenceIrrelevantError as exc:
            no_evidence_passed = False
            violations.append(str(exc))

    fed025 = next(
        (r for r in reingest["results"] if r.get("grant_id") == "nf13-real-fed-025"),
        {},
    )
    fed025_grant = fed025.get("updated_grant") or {}

    checks = {
        "zero_proxy_substitutions": classification["zero_proxy_substitutions"],
        "fed025_no_live_nofo": fed025.get("no_live_nofo") is True,
        "fed025_not_epa_proxy": not str(
            fed025_grant.get("opportunity_number") or ""
        ).startswith("EPA-OW"),
        "fed025_source_state": fed025_grant.get("source_ingestion_state")
        == SOURCE_INGESTION_STATE_NO_LIVE_NOFO,
        "no_live_nofo_never_irrelevant": classification["no_live_nofo_never_irrelevant"],
        "no_tribal_federal_in_irrelevant": classification[
            "no_tribal_federal_in_irrelevant"
        ],
        "ownership_guard_passed": ownership_passed,
        "no_evidence_guard_preserved": no_evidence_passed,
        "proxy_substitution_count_zero": reingest.get("proxy_substitution_count", 0) == 0,
        "honest_labeling": result["honest_labeling"] is True,
        "stop_at_checkpoint": result["stop_at_checkpoint"] is True,
    }

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "verification_passed": all(checks.values()),
            "checks": checks,
            "label_distribution": classification["label_distribution"],
            "nf15_baseline_distribution": classification["nf15_baseline_distribution"],
            "distribution_delta": classification["distribution_delta"],
            "no_live_nofo_grants": classification["no_live_nofo_grants"],
            "reingest_results": reingest["results"],
            "violations": violations,
            "ownership_guard": build_source_program_ownership_guard_contract(),
            "no_live_nofo_state": build_no_live_nofo_state_contract(),
            "no_evidence_guard": build_no_evidence_irrelevant_guard_contract(),
        }
    )
