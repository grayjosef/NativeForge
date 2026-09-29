"""Nine-gate live-collector evidence for any registered source."""

from __future__ import annotations

import datetime as dt
import uuid
from typing import Any

from nativeforge.repositories.source_collector_gate_evidence_repository import (
    count_distinct_canonical_from_observations,
    count_field_provenance,
    count_live_raw_payloads,
    count_source_observations,
    fetch_active_source_row,
    fetch_catalog_source,
    has_approved_terms_decision,
    list_active_source_ids,
)
from nativeforge.services.source_definition_service import build_source_definition
from nativeforge.services.source_fleet_live_readiness_service import LIVE_GATES
from nativeforge.services.source_live_fetch_opt_in_service import is_live_fetch_opted_in
from nativeforge.services.source_live_warrant_service import (
    WARRANT_SOURCE_COLLECTION,
    evaluate_live_request,
)

SCHEMA_VERSION = "nf_source_collector_gate_evidence_v1"


def _bool(value: Any) -> bool:
    return value is True


def _collection_url_for_source(
    connection: Any,
    *,
    organization_id: uuid.UUID,
    source_id: str,
) -> str:
    definition = build_source_definition(
        source_id=source_id,
        connection=connection,
        organization_id=organization_id,
    )
    endpoint = str(definition.get("endpoint") or "").strip()
    return endpoint


def measure_source_collector_gates(
    connection: Any,
    *,
    organization_id: uuid.UUID,
    source_id: str,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    """Measure gate evidence from stored facts; never invent true."""
    stamp = now or dt.datetime.now(dt.UTC)
    collection_url = _collection_url_for_source(
        connection, organization_id=organization_id, source_id=source_id
    )
    method = "POST" if source_id == "nf-seed-2026-api-grants-gov-search2" else "GET"

    catalog = fetch_catalog_source(connection, source_id=source_id)
    activation = fetch_active_source_row(
        connection, organization_id=organization_id, source_id=source_id
    )
    payload_count = count_live_raw_payloads(
        connection, organization_id=organization_id, source_id=source_id
    )
    observation_count = count_source_observations(connection, source_id=source_id)
    canonical_count = count_distinct_canonical_from_observations(
        connection, source_id=source_id
    )
    provenance_count = count_field_provenance(connection, source_id=source_id)

    opted_in = is_live_fetch_opted_in(
        connection=connection, organization_id=organization_id, source_id=source_id
    )
    warrant = evaluate_live_request(
        warrant_kind=WARRANT_SOURCE_COLLECTION,
        authorized_source_id=source_id,
        request_url=collection_url,
        method=method,
        connection=connection,
        organization_id=organization_id,
    )
    terms_row = has_approved_terms_decision(
        connection, organization_id=organization_id, source_id=source_id
    )

    disabled = activation and activation.get("disabled_at") is not None
    last_success = activation.get("last_success_at") if activation else None
    transport_ok = last_success is not None and int(
        (activation or {}).get("consecutive_failure_count") or 0
    ) == 0

    gates = {
        "registered": catalog,
        "enabled": activation is not None and not disabled,
        "authorized": opted_in,
        "warrant_valid": _bool(warrant.get("permitted")),
        "terms_satisfied": terms_row,
        "transport_healthy": transport_ok,
        "parser_healthy": observation_count > 0,
        "normalization_healthy": observation_count > 0 and canonical_count > 0,
        "persistence_healthy": (
            payload_count > 0 and observation_count > 0 and provenance_count > 0
        ),
    }
    missing = [name for name in LIVE_GATES if not gates.get(name)]

    return {
        "schema_version": SCHEMA_VERSION,
        "source_id": source_id,
        "organization_id": str(organization_id),
        "measured_at": stamp.isoformat(),
        "collection_url": collection_url or None,
        "gates": gates,
        "unsatisfied_gates": missing,
        "payload_count": payload_count,
        "observation_count": observation_count,
        "canonical_count": canonical_count,
        "provenance_count": provenance_count,
        "last_success_at": last_success,
    }


def fleet_live_source_rows(
    connection: Any,
    *,
    organization_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """One row per activated source for ``derive_collectors_live``."""
    rows: list[dict[str, Any]] = []
    for source_id in list_active_source_ids(
        connection, organization_id=organization_id
    ):
        measured = measure_source_collector_gates(
            connection, organization_id=organization_id, source_id=source_id
        )
        rows.append({"source_id": source_id, "gates": measured["gates"]})
    return rows


def fleet_health_summary(
    connection: Any,
    *,
    organization_id: uuid.UUID,
) -> dict[str, Any]:
    """Fleet totals from measured gate evidence (not hardcoded)."""
    from nativeforge.services.source_fleet_live_readiness_service import (
        derive_collectors_live,
        source_gates_are_live,
    )

    rows = fleet_live_source_rows(connection, organization_id=organization_id)
    live = derive_collectors_live(sources=rows)
    healthy = sum(1 for r in rows if source_gates_are_live(r.get("gates")))
    unhealthy = len(rows) - healthy
    blocked: list[str] = []
    for r in rows:
        sid = str(r.get("source_id") or "")
        gates = r.get("gates") or {}
        if not source_gates_are_live(gates):
            failed = [g for g in LIVE_GATES if not gates.get(g)]
            if sid and failed:
                blocked.append(f"{sid}:{','.join(failed)}")
    return {
        "schema_version": "nf_source_fleet_health_summary_v1",
        "registered_sources": len(
            {
                sid
                for sid in list_active_source_ids(
                    connection, organization_id=organization_id
                )
            }
        ),
        "active_sources": len(rows),
        "collectors_live": live["collectors_live"],
        "healthy_collectors": healthy,
        "unhealthy_collectors": unhealthy,
        "fleet_live_sources": live["fleet_live_sources"],
        "blocked_sources": blocked,
    }
