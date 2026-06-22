"""Sprint 347: NF-15 gate verification."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.eligibility_evidence_quality_service import (
    is_placeholder_eligibility,
)
from nativeforge.services.nf15_no_evidence_honesty_orchestrator_service import (
    run_nf15_no_evidence_honesty_block,
)
from nativeforge.services.no_evidence_irrelevant_guard_service import (
    NoEvidenceIrrelevantError,
    build_no_evidence_irrelevant_guard_contract,
)
from nativeforge.services.tribal_serving_agency_safety_net_service import (
    build_tribal_serving_agency_safety_net_contract,
    is_tribal_serving_agency,
)

SCHEMA_VERSION = "nf_nf15_gate_verification_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def verify_nf15_no_evidence_honesty_gates() -> dict[str, Any]:
    result = run_nf15_no_evidence_honesty_block()
    classification = result["classification"]
    reingest = result["eligibility_reingest"]

    no_evidence_guard_passed = True
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
            no_evidence_guard_passed = False
            violations.append(str(exc))

    fed021 = next(
        (r for r in reingest["results"] if r.get("grant_id") == "nf13-real-fed-021"),
        {},
    )
    fed025 = next(
        (r for r in reingest["results"] if r.get("grant_id") == "nf13-real-fed-025"),
        {},
    )

    checks = {
        "reingest_both_targets": reingest["reingested_success_count"] >= 2,
        "fed021_reingested": fed021.get("reingested") is True,
        "fed025_reingested": fed025.get("reingested") is True,
        "fed021_not_placeholder": not is_placeholder_eligibility(
            str((fed021.get("updated_grant") or {}).get("eligibility_text") or "")
        ),
        "no_tribal_federal_in_irrelevant": classification[
            "no_tribal_federal_in_irrelevant"
        ],
        "no_evidence_guard_passed": no_evidence_guard_passed,
        "tribal_agency_safety_net_exercisable": is_tribal_serving_agency(
            agency="SAMHSA / HHS"
        ),
        "honest_labeling": result["honest_labeling"] is True,
        "stop_at_checkpoint": result["stop_at_checkpoint"] is True,
    }

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "verification_passed": all(checks.values()),
            "checks": checks,
            "label_distribution": classification["label_distribution"],
            "nf14_baseline_distribution": classification["nf14_baseline_distribution"],
            "distribution_delta": classification["distribution_delta"],
            "reingest_results": reingest["results"],
            "tribal_federal_in_irrelevant": classification["tribal_federal_in_irrelevant"],
            "no_evidence_violations": violations,
            "no_evidence_guard": build_no_evidence_irrelevant_guard_contract(),
            "tribal_agency_safety_net": build_tribal_serving_agency_safety_net_contract(),
        }
    )
