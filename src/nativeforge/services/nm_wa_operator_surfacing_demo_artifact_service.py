"""Offline NM/WA operator surfacing demo artifact builder.

Synthetic fixtures only. Deterministic local artifacts. No network/live ingest.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from nativeforge.services.nm_operator_surfacing_report_service import (
    build_nm_operator_surfacing_report,
)
from nativeforge.services.nm_pilot_classify_match_orchestrator_service import (
    run_nm_pilot_classify_match_block,
)
from nativeforge.services.nm_pilot_fixture_loader_service import (
    EXPECTED_PROFILE_COUNT as NM_EXPECTED,
)
from nativeforge.services.nm_pilot_fixture_loader_service import (
    load_nm_tribal_profiles,
)
from nativeforge.services.nm_wa_combined_operator_surfacing_service import (
    build_combined_operator_review_queue,
)
from nativeforge.services.wa_operator_surfacing_report_service import (
    build_wa_operator_surfacing_report,
)
from nativeforge.services.wa_pilot_classify_match_orchestrator_service import (
    run_wa_pilot_classify_match_block,
)
from nativeforge.services.wa_pilot_fixture_loader_service import (
    EXPECTED_PROFILE_COUNT as WA_EXPECTED,
)
from nativeforge.services.wa_pilot_fixture_loader_service import (
    load_wa_tribal_profiles,
)

SCHEMA_VERSION = "nf_nm_wa_operator_surfacing_demo_artifact_v1"

DEFAULT_DEMO_GRANTS: list[dict[str, Any]] = [
    {
        "grant_id": "smoke-demo-001",
        "opportunity_title": "Federal Tribal Discretionary Support",
        "program_area": "health",
        "recognition_requirement": "federal_required",
    }
]


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _canonical_digest(payload: dict[str, Any]) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def build_demo_artifact(
    *,
    grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Sprint 011: full offline demo artifact for NM/WA operator surfacing."""
    corpus = grants if grants is not None else DEFAULT_DEMO_GRANTS
    nm_profiles = load_nm_tribal_profiles()
    wa_profiles = load_wa_tribal_profiles()
    nm_cm = run_nm_pilot_classify_match_block(
        grants=corpus, allow_live_completeness_fetch=False
    )
    wa_cm = run_wa_pilot_classify_match_block(
        grants=corpus, allow_live_completeness_fetch=False
    )
    nm_report = build_nm_operator_surfacing_report(grants=corpus)
    wa_report = build_wa_operator_surfacing_report(grants=corpus)
    combined = build_combined_operator_review_queue(grants=corpus)

    missing_summary = {
        "nm_missing_evidence_categories": nm_report["rollup"][
            "missing_evidence_categories"
        ],
        "wa_missing_evidence_categories": wa_report["rollup"][
            "missing_evidence_categories"
        ],
        "combined_missing_data_count": combined["combined_missing_data_count"],
        "hidden_missing_data": False,
    }
    provenance_summary = {
        "combined_evidence_provenance_summary": combined[
            "combined_evidence_provenance_summary"
        ],
        "notes_visible": True,
    }
    next_check_summary = {
        "combined_review_needed_count": combined["combined_review_needed_count"],
        "rows_with_next_checks": sum(
            1 for r in combined["rows"] if r.get("operator_next_check")
        ),
        "human_review_required_count": sum(
            1 for r in combined["rows"] if r.get("human_review_required")
        ),
    }

    artifact = {
        "schema_version": SCHEMA_VERSION,
        "offline_only": True,
        "live_ingestion": False,
        "source_activation": False,
        "external_urls_used": False,
        "does_not_alter_classify_match_logic": True,
        "final_eligibility_claim_allowed": False,
        "mode": "offline_synthetic",
        "fixtures": {
            "nm_profile_count": len(nm_profiles),
            "wa_profile_count": len(wa_profiles),
            "nm_expected": NM_EXPECTED,
            "wa_expected": WA_EXPECTED,
        },
        "classify_match": {
            "nm": {
                "profile_count": len(nm_cm.get("per_profile") or []),
                "grant_count": len(corpus),
            },
            "wa": {
                "profile_count": len(wa_cm.get("per_profile") or []),
                "grant_count": len(corpus),
            },
        },
        "nm_operator_report": nm_report,
        "wa_operator_report": wa_report,
        "combined_review_queue": combined,
        "missing_data_summary": missing_summary,
        "provenance_evidence_summary": provenance_summary,
        "operator_next_check_summary": next_check_summary,
    }
    artifact["content_digest"] = _canonical_digest(
        {k: v for k, v in artifact.items() if k != "content_digest"}
    )
    return _json_safe(artifact)


def write_demo_artifact(
    path: Path | str,
    *,
    grants: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Sprint 012: write demo artifact JSON to a local path."""
    artifact = build_demo_artifact(grants=grants)
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(artifact, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    return artifact


def demo_artifact_invariant_failures(artifact: dict[str, Any]) -> list[str]:
    """Sprint 013: hard invariant checks on demo artifact honesty."""
    failures: list[str] = []
    if artifact.get("final_eligibility_claim_allowed") is not False:
        failures.append("final_eligibility_claim_must_be_false")
    if artifact.get("live_ingestion") is True:
        failures.append("live_ingestion_forbidden")
    if artifact.get("source_activation") is True:
        failures.append("source_activation_forbidden")
    if artifact.get("external_urls_used") is True:
        failures.append("external_urls_forbidden")
    if artifact.get("missing_data_summary", {}).get("hidden_missing_data") is True:
        failures.append("missing_data_must_not_be_hidden")

    combined = artifact.get("combined_review_queue") or {}
    rows = combined.get("rows") or []
    for r in rows:
        if r.get("human_review_required") and not r.get("operator_next_check"):
            failures.append(
                f"missing_next_check:{r.get('state_cohort')}:{r.get('profile_id')}"
            )
        if r.get("final_eligibility_claim_allowed") is True:
            failures.append(
                f"final_claim_allowed:{r.get('state_cohort')}:{r.get('profile_id')}"
            )
        if r.get("discoverability") != "visible_in_operator_review":
            # Unknown/partial must remain discoverable
            if r.get("missing_data") or r.get("human_review_required"):
                failures.append(
                    f"not_discoverable:{r.get('state_cohort')}:{r.get('profile_id')}"
                )
    if not artifact.get("nm_operator_report"):
        failures.append("missing_nm_operator_report")
    if not artifact.get("wa_operator_report"):
        failures.append("missing_wa_operator_report")
    if not combined.get("rows"):
        failures.append("missing_combined_review_queue_rows")
    return failures
