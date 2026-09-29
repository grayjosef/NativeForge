"""Source fleet expansion inventory: seeds + authority + activation facts."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_authority_service import resolve_source_authority
from nativeforge.services.source_definition_service import build_source_definition
from nativeforge.services.source_ingestion_seed_loader_service import (
    load_source_seed_rows,
)
from nativeforge.services.source_monitoring_approved_source_service import (
    load_registry_rows,
)
from nativeforge.services.source_seed_backlog_service import classify_seed_row

SCHEMA_VERSION = "nf_source_fleet_expansion_inventory_v1"

# Mission classification vocabulary (evidence-backed, not aspirational).
LIVE = "LIVE"
READY_TO_ACTIVATE = "READY_TO_ACTIVATE"
ADAPTER_SUPPORTED = "ADAPTER_SUPPORTED"
ADAPTER_REQUIRED = "ADAPTER_REQUIRED"
AUTHORIZATION_REQUIRED = "AUTHORIZATION_REQUIRED"
RESEARCH_REQUIRED = "RESEARCH_REQUIRED"
INVALID = "INVALID"
DUPLICATE = "DUPLICATE"
STALE = "STALE"
BLOCKED = "BLOCKED"

_AUTHORITY_TO_CLASS: dict[str, str] = {
    "authorized_for_live": READY_TO_ACTIVATE,
    "live_opted_in": READY_TO_ACTIVATE,
    "activated": AUTHORIZATION_REQUIRED,
    "reviewed": AUTHORIZATION_REQUIRED,
    "registered": AUTHORIZATION_REQUIRED,
    "review_required": AUTHORIZATION_REQUIRED,
    "blocked": BLOCKED,
    "retired": BLOCKED,
    "unregistered": RESEARCH_REQUIRED,
    "unknown": RESEARCH_REQUIRED,
}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _classify_row(
    *,
    seed_row: dict[str, str],
    backlog: dict[str, Any],
    authority_state: str,
    activation_present: bool,
    live_on_fleet: bool,
) -> str:
    if live_on_fleet:
        return LIVE
    if backlog.get("backlog_class") == "INVALID":
        return INVALID
    if backlog.get("backlog_class") == "DUPLICATE":
        return DUPLICATE
    if authority_state in ("blocked", "retired"):
        return BLOCKED
    if authority_state == "authorized_for_live" and activation_present:
        return READY_TO_ACTIVATE
    mapped = _AUTHORITY_TO_CLASS.get(authority_state, RESEARCH_REQUIRED)
    if backlog.get("backlog_class") == "NEW_ADAPTER_REQUIRED":
        return ADAPTER_REQUIRED
    if backlog.get("backlog_class") == "ADAPTER_SUPPORTED":
        return ADAPTER_SUPPORTED if mapped == AUTHORIZATION_REQUIRED else mapped
    if backlog.get("backlog_class") == "NEEDS_RESEARCH":
        return RESEARCH_REQUIRED
    return mapped


def build_source_fleet_inventory(
    connection: Any,
    *,
    organization_id: Any,
    live_source_ids: list[str] | None = None,
) -> dict[str, Any]:
    """Classify every seed row using CSV + DB authority (no network)."""
    registry = load_registry_rows()
    seen_ids: set[str] = set()
    seen_urls: set[str] = set()
    live_ids = set(live_source_ids or [])

    activation_rows: set[str] = set()
    if connection is not None:
        try:
            import sqlalchemy as sa

            for row in connection.execute(
                sa.text(
                    """
                    SELECT source_id FROM nf_active_opportunity_sources
                    WHERE organization_id = :org AND disabled_at IS NULL
                    """
                ),
                {"org": organization_id},
            ):
                activation_rows.add(str(row[0]))
        except Exception:  # noqa: BLE001
            pass

    entries: list[dict[str, Any]] = []
    counts: dict[str, int] = {}

    for row in load_source_seed_rows():
        seed_id = str(row.get("seed_id") or "").strip()
        backlog = classify_seed_row(row, seen_ids=seen_ids, seen_urls=seen_urls)
        registered = seed_id in registry
        authority = resolve_source_authority(
            connection=connection,
            organization_id=organization_id,
            source_id=seed_id,
            registered=registered,
        )
        state = str(authority.get("state") or "unknown")
        definition = (
            build_source_definition(
                source_id=seed_id,
                registry_row=registry.get(seed_id),
                connection=connection,
                organization_id=organization_id,
            )
            if seed_id
            else {}
        )
        classification = _classify_row(
            seed_row=row,
            backlog=backlog,
            authority_state=state,
            activation_present=seed_id in activation_rows,
            live_on_fleet=seed_id in live_ids,
        )
        counts[classification] = counts.get(classification, 0) + 1
        entries.append(
            {
                "source_id": seed_id,
                "source_name": row.get("source_name"),
                "source_family": backlog.get("adapter_family"),
                "endpoint": definition.get("endpoint") or row.get("source_url"),
                "adapter_key": row.get("adapter_key"),
                "access_posture": row.get("access_posture_hint") or "UNKNOWN",
                "authorization_state": state,
                "activation_present": seed_id in activation_rows,
                "classification": classification,
                "blocker": (
                    None
                    if classification
                    in (LIVE, READY_TO_ACTIVATE, ADAPTER_SUPPORTED)
                    else authority.get("reasons")
                ),
                "recommended_next_action": _recommend(classification, state),
            }
        )

    shortlist = _priority_shortlist(entries)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_id": str(organization_id),
            "seed_count": len(entries),
            "classification_counts": counts,
            "entries": entries,
            "priority_shortlist": shortlist,
        }
    )


def _recommend(classification: str, authority_state: str) -> str:
    if classification == LIVE:
        return "maintain_scheduled_collection"
    if classification == READY_TO_ACTIVATE:
        return "run_bounded_collection_pass_1"
    if classification == AUTHORIZATION_REQUIRED:
        return f"record_signed_decisions:{authority_state}"
    if classification == ADAPTER_REQUIRED:
        return "finish_adapter_and_tests"
    if classification == RESEARCH_REQUIRED:
        return "identify_listing_endpoint"
    if classification == BLOCKED:
        return "resolve_blockers_or_retire"
    return "review"


def _priority_shortlist(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rank by yield/relevance heuristics from seed metadata (no network)."""
    scored: list[tuple[int, dict[str, Any]]] = []
    for entry in entries:
        score = 0
        cls = entry.get("classification")
        if cls == LIVE:
            score += 1000
        if cls == READY_TO_ACTIVATE:
            score += 500
        if cls == ADAPTER_SUPPORTED:
            score += 200
        adapter = str(entry.get("adapter_key") or "")
        if "grants_gov" in adapter or "federal_register" in adapter:
            score += 80
        tier = str(entry.get("source_family") or "")
        if "federal" in tier:
            score += 40
        name = str(entry.get("source_name") or "").lower()
        if "south carolina" in name or "sc " in name:
            score += 60
        scored.append((score, entry))
    scored.sort(key=lambda t: (-t[0], str(t[1].get("source_id") or "")))
    return [e for _, e in scored[:15]]
