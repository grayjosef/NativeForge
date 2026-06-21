"""Sprint 316: human-gated batch activation for public tier-1 federal sources."""

from __future__ import annotations

import json
import uuid
from typing import Any

from nativeforge.domain.enums import OpportunityVerificationStatus
from nativeforge.services import opportunity_discovery_service as ods
from nativeforge.services.fed_program_activation_binding_service import (
    assert_seed_aln_binding,
)
from nativeforge.services.seed_source_human_activation_service import (
    _load_seed_candidate,
)
from nativeforge.services.source_ingestion_orchestrator_service import (
    _candidate_to_source_payload,
    persist_seed_candidates_to_registry,
)
from nativeforge.services.source_ingestion_tier1_federal_adapter_service import (
    TIER1_ADAPTER_KEYS,
)

SCHEMA_VERSION = "nf_tier1_batch_federal_activation_v1"

BATCH_CONFIRMATION_KEYS: frozenset[str] = frozenset(
    {
        "operator_handle",
        "human_activation_acknowledged",
        "public_only_acknowledged",
        "batch_tier1_public_activation_acknowledged",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _validate_batch_confirmation(confirmation: dict[str, Any]) -> None:
    missing = BATCH_CONFIRMATION_KEYS - set(confirmation.keys())
    if missing:
        raise ValueError(f"missing batch confirmation keys: {sorted(missing)}")
    if not confirmation.get("human_activation_acknowledged"):
        raise PermissionError("human_activation_acknowledged required")
    if not confirmation.get("public_only_acknowledged"):
        raise PermissionError("public_only_acknowledged required")
    if not confirmation.get("batch_tier1_public_activation_acknowledged"):
        raise PermissionError("batch_tier1_public_activation_acknowledged required")


def select_tier1_public_batch_seed_ids(
    posture_candidates: list[dict[str, Any]],
    *,
    max_batch_size: int | None = None,
) -> list[str]:
    """Green public tier-1 federal seeds eligible for controlled batch activation."""
    eligible: list[str] = []
    for row in posture_candidates:
        if int(row.get("tier") or 0) != 1:
            continue
        if str(row.get("adapter_key") or "") not in TIER1_ADAPTER_KEYS:
            continue
        if str(row.get("access_posture_hint") or "") != "public":
            continue
        if row.get("url_status") == "dead":
            continue
        if row.get("access_posture_blocked"):
            continue
        eligible.append(str(row["seed_id"]))
    eligible.sort()
    if max_batch_size is not None:
        eligible = eligible[:max_batch_size]
    return eligible


def activate_tier1_public_batch_human_gate(
    session: Any,
    *,
    org: Any,
    seed_ids: list[str],
    operator_confirmation: dict[str, Any],
) -> dict[str, Any]:
    """Activate each public tier-1 seed — preserves prior batch activations."""
    _validate_batch_confirmation(operator_confirmation)
    if not seed_ids:
        raise ValueError("batch activation requires at least one seed_id")
    candidates = [_load_seed_candidate(sid) for sid in seed_ids]
    for cand in candidates:
        if cand.get("access_posture_hint") != "public":
            raise PermissionError("only public posture sources may be batch-activated")
        if int(cand.get("tier") or 0) != 1:
            raise PermissionError("batch activation limited to tier-1 federal seeds")
        if str(cand.get("adapter_key") or "") not in TIER1_ADAPTER_KEYS:
            raise PermissionError("batch activation limited to tier-1 federal adapters")
        sid = str(cand["seed_id"])
        if sid.startswith("nf-seed-2026-fed-"):
            assert_seed_aln_binding(sid, str(cand["source_name"]))
    persist_seed_candidates_to_registry(session, org=org, candidates=candidates)
    from nativeforge.repositories import opportunity_sources as os_repo

    rows = os_repo.list_opportunity_sources_for_org(
        session=session,
        org_id=org.id,
        org_type=org.org_type,
    )
    activated: list[dict[str, str]] = []
    for candidate in candidates:
        target_url = str(candidate["source_url"])
        activated_id: uuid.UUID | None = None
        for row in rows:
            if row.source_url == target_url:
                row.is_active = True
                row.verification_status = (
                    OpportunityVerificationStatus.operator_reviewed.value
                )
                activated_id = row.id
                break
        if activated_id is None:
            payload = _candidate_to_source_payload(candidate)
            payload.is_active = True
            payload.verification_status = (
                OpportunityVerificationStatus.operator_reviewed
            )
            created = ods.create_opportunity_source(session, org=org, body=payload)
            activated_id = created.id
        activated.append(
            {
                "seed_id": str(candidate["seed_id"]),
                "activated_source_id": str(activated_id),
            }
        )
    session.flush()
    active_count = sum(
        1
        for r in os_repo.list_opportunity_sources_for_org(
            session=session,
            org_id=org.id,
            org_type=org.org_type,
        )
        if r.is_active
    )
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "activated_count": len(activated),
            "activated_seeds": activated,
            "active_source_count": active_count,
            "human_activation_path": True,
            "batch_mode": True,
            "public_only": True,
        }
    )
