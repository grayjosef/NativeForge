"""Grants.gov-specific aliases for fleet collector gate evidence."""

from __future__ import annotations

import uuid
from typing import Any

from nativeforge.repositories.grants_gov_collector_gate_evidence_repository import (
    AUTHORIZED_SOURCE,
)
from nativeforge.services.source_collector_gate_evidence_service import (
    fleet_live_source_rows as _fleet_rows,
)
from nativeforge.services.source_collector_gate_evidence_service import (
    measure_source_collector_gates,
)

SCHEMA_VERSION = "nf_grants_gov_collector_gate_evidence_v1"


def measure_grants_gov_collector_gates(
    connection: Any,
    *,
    organization_id: uuid.UUID,
    source_id: str = AUTHORIZED_SOURCE,
    now: Any = None,
) -> dict[str, Any]:
    return measure_source_collector_gates(
        connection,
        organization_id=organization_id,
        source_id=source_id,
        now=now,
    )


def fleet_live_source_rows(
    connection: Any,
    *,
    organization_id: uuid.UUID,
    source_id: str = AUTHORIZED_SOURCE,
) -> list[dict[str, Any]]:
    """All activated sources for the org (``source_id`` param kept for compat)."""
    del source_id
    return _fleet_rows(connection, organization_id=organization_id)
