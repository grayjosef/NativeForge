"""SC Monday demo lane — honest data-plane labels (no live-ingest claims)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_sc_monday_demo_labels_v1"

LABEL_CURATED_CURRENT = "curated_current"
LABEL_FIXTURE_DEMO = "fixture_demo"
LABEL_RULE_REFERENCE = "rule_reference"

ALLOWED_DATA_LABELS: frozenset[str] = frozenset(
    {
        LABEL_CURATED_CURRENT,
        LABEL_FIXTURE_DEMO,
        LABEL_RULE_REFERENCE,
    }
)

REQUIRED_UI_FLAGS: dict[str, Any] = {
    "show_activation_controls": False,
    "show_submit_controls": False,
    "advisory_banner": (
        "South Carolina customer demo — curated/fixture opportunities only. "
        "Not automated live ingestion. No final eligibility claim. "
        "Human review required before pursuit decisions."
    ),
}


def assert_honest_opportunity_labels(row: dict[str, Any]) -> list[str]:
    """Return invariant failures for one opportunity row (empty = ok)."""
    failures: list[str] = []
    label = str(row.get("data_label") or "")
    if label not in ALLOWED_DATA_LABELS:
        failures.append(f"invalid_data_label:{label!r}")
    if row.get("live_ingest_not_claimed") is not True:
        failures.append("live_ingest_not_claimed_must_be_true")
    if row.get("live_ingestion_claimed") is True:
        failures.append("live_ingestion_claimed_must_not_be_true")
    if not row.get("retrieval_date") and not row.get("capture_date"):
        failures.append("missing_retrieval_or_capture_date")
    if label == LABEL_RULE_REFERENCE and not row.get("sc_pilot_rule_reference"):
        failures.append("rule_reference_requires_sc_pilot_rule_reference")
    return failures


def build_demo_lane_claim_matrix() -> dict[str, Any]:
    """Explicit claim matrix for handoff / buyer honesty."""
    return {
        "schema_version": SCHEMA_VERSION,
        "live_ingestion": "NOT_CLAIMED",
        "source_activation": "NOT_CLAIMED",
        "final_eligibility_claim": "NOT_ALLOWED",
        "sc_opportunity_mode": "curated_current_and_rule_reference",
        "federal_opportunity_mode": "curated_from_offline_corpus_and_rule_refs",
        "organization_profiles": "sc_pilot_fixtures",
        "nofo_pdf_extraction": "NOT_IN_THIS_BLOCK",
        "proposal_drafting": "NOT_IN_THIS_BLOCK",
        "human_review_required": True,
        "allowed_data_labels": sorted(ALLOWED_DATA_LABELS),
    }


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_labels_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "allowed_data_labels": sorted(ALLOWED_DATA_LABELS),
            "required_ui_flags": dict(REQUIRED_UI_FLAGS),
            "claim_matrix": build_demo_lane_claim_matrix(),
        }
    )
