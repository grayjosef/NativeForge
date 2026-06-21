"""Sprint 291: human-gated activation for exactly one authorized seed source."""

from __future__ import annotations

import json
import uuid
from typing import Any

from nativeforge.domain.enums import OpportunityVerificationStatus
from nativeforge.services import opportunity_discovery_service as ods
from nativeforge.services.fed_program_activation_binding_service import (
    NF11_ALLOWED_ACTIVATION_SEEDS,
    assert_seed_aln_binding,
)
from nativeforge.services.source_ingestion_orchestrator_service import (
    _candidate_to_source_payload,
    persist_seed_candidates_to_registry,
)
from nativeforge.services.source_ingestion_seed_loader_service import (
    load_source_seed_rows,
    seed_row_to_discovery_candidate,
)

SCHEMA_VERSION = "nf_seed_source_human_activation_v2"
NF9_AUTHORIZED_SEED_ID = "nf-seed-2026-fed-001"

REQUIRED_CONFIRMATION_KEYS: frozenset[str] = frozenset(
    {
        "operator_handle",
        "human_activation_acknowledged",
        "public_only_acknowledged",
        "single_source_only_acknowledged",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _load_seed_candidate(seed_id: str) -> dict[str, Any]:
    for row in load_source_seed_rows():
        if row["seed_id"] == seed_id:
            return seed_row_to_discovery_candidate(row)
    raise ValueError(f"unknown seed_id: {seed_id!r}")


def _validate_confirmation(confirmation: dict[str, Any]) -> None:
    missing = REQUIRED_CONFIRMATION_KEYS - set(confirmation.keys())
    if missing:
        raise ValueError(f"missing confirmation keys: {sorted(missing)}")
    if not confirmation.get("human_activation_acknowledged"):
        raise PermissionError("human_activation_acknowledged required")
    if not confirmation.get("public_only_acknowledged"):
        raise PermissionError("public_only_acknowledged required")
    if not confirmation.get("single_source_only_acknowledged"):
        raise PermissionError("single_source_only_acknowledged required")


def activate_single_seed_source_human_gate(
    session: Any,
    *,
    org: Any,
    seed_id: str,
    operator_confirmation: dict[str, Any],
    authorized_seeds: frozenset[str] | None = None,
) -> dict[str, Any]:
    """Activate exactly one authorized seed — is_active=True for that source only."""
    allowed = authorized_seeds or frozenset({NF9_AUTHORIZED_SEED_ID})
    if seed_id not in allowed:
        raise PermissionError(
            f"activation not authorized for seed {seed_id!r}; allowed={sorted(allowed)}"
        )
    _validate_confirmation(operator_confirmation)
    candidate = _load_seed_candidate(seed_id)
    if seed_id in NF11_ALLOWED_ACTIVATION_SEEDS:
        assert_seed_aln_binding(seed_id, str(candidate["source_name"]))
    if candidate.get("access_posture_hint") != "public":
        raise PermissionError("only public posture sources may be activated")
    persist_seed_candidates_to_registry(
        session,
        org=org,
        candidates=[candidate],
    )
    from nativeforge.repositories import opportunity_sources as os_repo

    rows = os_repo.list_opportunity_sources_for_org(
        session=session,
        org_id=org.id,
        org_type=org.org_type,
    )
    target_url = str(candidate["source_url"])
    activated_id: uuid.UUID | None = None
    other_active: list[str] = []
    for row in rows:
        if row.source_url == target_url:
            row.is_active = True
            row.verification_status = OpportunityVerificationStatus.operator_reviewed.value
            activated_id = row.id
        elif row.is_active:
            other_active.append(str(row.id))
            row.is_active = False
    if activated_id is None:
        payload = _candidate_to_source_payload(candidate)
        payload.is_active = True
        payload.verification_status = OpportunityVerificationStatus.operator_reviewed
        created = ods.create_opportunity_source(session, org=org, body=payload)
        activated_id = created.id
    session.flush()
    active_count = sum(
        1 for r in os_repo.list_opportunity_sources_for_org(
            session=session,
            org_id=org.id,
            org_type=org.org_type,
        )
        if r.is_active
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "seed_id": seed_id,
            "canonical_source_id": candidate["canonical_source_id"],
            "activated_source_id": str(activated_id),
            "operator_handle": str(operator_confirmation["operator_handle"]),
            "exactly_one_active": active_count == 1,
            "active_source_count": active_count,
            "deactivated_other_sources": len(other_active),
            "human_activation_path": True,
            "no_other_seeds_activated": True,
        }
    )
