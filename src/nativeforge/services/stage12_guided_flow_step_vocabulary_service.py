"""Sprint 247: Stage 12 guided first-use flow step vocabulary."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_stage12_guided_flow_steps_v1"

GUIDED_FLOW_STEPS: tuple[str, ...] = (
    "source-discovery",
    "source-quality-review",
    "activation-readiness-preview",
    "opportunity-intake",
    "native-relevance-review",
    "profile-match-readiness",
    "operator-decision",
    "evidence-audit-trail",
)

STEP_LABELS: dict[str, str] = {
    "source-discovery": "Source discovery",
    "source-quality-review": "Source quality review",
    "activation-readiness-preview": "Activation readiness (preview only)",
    "opportunity-intake": "Opportunity intake",
    "native-relevance-review": "Native relevance review",
    "profile-match-readiness": "Profile match + readiness",
    "operator-decision": "Operator decision",
    "evidence-audit-trail": "Evidence / audit trail",
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def build_guided_flow_step_contract() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "steps": [
                {"id": s, "label": STEP_LABELS[s], "order": i + 1}
                for i, s in enumerate(GUIDED_FLOW_STEPS)
            ],
            "preview_only": True,
            "no_source_activation_execution": True,
        }
    )


def step_index(step_id: str) -> int:
    if step_id not in GUIDED_FLOW_STEPS:
        raise ValueError(f"unknown guided flow step: {step_id!r}")
    return GUIDED_FLOW_STEPS.index(step_id)
