"""TA-3: human-gated batch activation for Tier-3 foundation cohort."""

from __future__ import annotations

import json
import uuid
from typing import Any

from pydantic import BaseModel, Field, model_validator

from nativeforge.domain.enums import OpportunityVerificationStatus
from nativeforge.services import opportunity_discovery_service as ods
from nativeforge.services.seed_catalog_health_service import is_seed_activatable
from nativeforge.services.source_ingestion_orchestrator_service import (
    _candidate_to_source_payload,
    persist_seed_candidates_to_registry,
)
from nativeforge.services.tier3_org_cluster_config_service import TA3_COHORT_SEED_IDS

SCHEMA_VERSION = "nf_tier3_foundation_batch_activation_v1"


class Tier3BatchConfirmationBody(BaseModel):
    operator_handle: str = Field(min_length=1)
    human_activation_acknowledged: bool
    public_only_acknowledged: bool
    batch_tier3_foundation_activation_acknowledged: bool

    @model_validator(mode="after")
    def require_truthy(self) -> Tier3BatchConfirmationBody:
        for field in (
            "human_activation_acknowledged",
            "public_only_acknowledged",
            "batch_tier3_foundation_activation_acknowledged",
        ):
            if not getattr(self, field):
                raise ValueError(f"{field} must be true")
        return self


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def parse_tier3_batch_confirmation(
    confirmation: dict[str, Any] | Tier3BatchConfirmationBody,
) -> Tier3BatchConfirmationBody:
    if isinstance(confirmation, Tier3BatchConfirmationBody):
        return confirmation
    return Tier3BatchConfirmationBody.model_validate(confirmation)


def select_tier3_foundation_batch_seed_ids(
    posture_candidates: list[dict[str, Any]] | None = None,
    *,
    cohort_only: bool = True,
) -> list[str]:
    from nativeforge.services.corrected_catalog_posture_report_service import (
        build_corrected_catalog_posture_report,
    )

    rows = posture_candidates or build_corrected_catalog_posture_report()[
        "posture_candidates"
    ]
    allowed = set(TA3_COHORT_SEED_IDS) if cohort_only else None
    eligible: list[str] = []
    for row in rows:
        if int(row.get("tier") or 0) != 3:
            continue
        seed_id = str(row.get("seed_id") or "")
        if allowed is not None and seed_id not in allowed:
            continue
        if str(row.get("access_posture_hint") or "") != "public":
            continue
        if row.get("url_status") == "dead":
            continue
        if row.get("access_posture_blocked"):
            continue
        if not is_seed_activatable(row):
            continue
        eligible.append(seed_id)
    return sorted(eligible)


def activate_tier3_foundation_batch_human_gate(
    session: Any,
    *,
    org: Any,
    operator_confirmation: dict[str, Any] | Tier3BatchConfirmationBody,
    seed_ids: list[str] | None = None,
) -> dict[str, Any]:
    confirmation = parse_tier3_batch_confirmation(operator_confirmation)
    ids = seed_ids or list(TA3_COHORT_SEED_IDS)
    from nativeforge.services.fed_program_activation_binding_service import (
        load_seed_candidate,
    )
    from nativeforge.repositories import opportunity_sources as os_repo

    persist_seed_candidates_to_registry(session, org=org)
    rows = os_repo.list_opportunity_sources_for_org(
        session=session,
        org_id=org.id,
        org_type=org.org_type,
    )
    by_seed = {r.seed_id: r for r in rows if r.seed_id}
    activated: list[str] = []
    for seed_id in ids:
        cand = load_seed_candidate(seed_id)
        row = by_seed.get(seed_id)
        if row is None:
            payload = _candidate_to_source_payload(cand)
            row = ods.create_opportunity_source(session, org=org, body=payload)
            by_seed[seed_id] = row
        row.is_active = True
        row.verification_status = OpportunityVerificationStatus.operator_reviewed.value
        activated.append(seed_id)
    session.flush()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "operator_handle": confirmation.operator_handle,
            "activated_seed_ids": activated,
            "activated_count": len(activated),
            "identity_key": "seed_id",
        }
    )
