"""Offline-safe connector contracts — no HTTP clients."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Literal


@dataclass(frozen=True)
class ConnectorSourceConfig:
    """Binding between a connector run and registry-oriented metadata."""

    connector_id: str
    source_name: str
    publisher_name: str | None = None
    source_registry_id: uuid.UUID | None = None
    source_lane: Literal[
        "native_specific", "native_relevant_broad", "general_monitoring"
    ] = "native_relevant_broad"
    opportunity_source_type_hint: str | None = "federal"


@dataclass(frozen=True)
class ConnectorRunContext:
    """Execution context for a connector invocation (always dry-run in Sprint 22)."""

    dry_run: bool = True
    run_id: str | None = None
    now: datetime | None = None
    normalization_schema_version: str = "nf_connector_normalized_v1"


@dataclass(frozen=True)
class RawOpportunityPayload:
    """Fixture or future capture row plus provenance."""

    local_key: str
    captured_at: datetime
    body: dict[str, Any]
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class NormalizedOpportunityCandidate:
    """Canonical candidate fields + scoring + provenance (no DB writes)."""

    local_key: str
    duplicate_key: str
    normalized_fields: dict[str, Any]
    native_relevance: dict[str, Any]
    provenance: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ConnectorDryRunResult:
    """Result bundle for operator review / tests."""

    candidates: tuple[NormalizedOpportunityCandidate, ...]
    errors: tuple[dict[str, Any], ...] = ()
