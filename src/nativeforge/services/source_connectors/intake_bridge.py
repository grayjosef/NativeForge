"""Bridge static fixture connector output into `discovery_intake_service` (offline)."""

from __future__ import annotations

import uuid
from dataclasses import replace
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.db.models import Organization
from nativeforge.domain.enums import DiscoveryIntakeMode
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.services.discovery_intake_service import (
    process_structured_candidates,
    start_intake_run,
)
from nativeforge.services.source_connectors.base import (
    ConnectorRunContext,
    ConnectorSourceConfig,
)
from nativeforge.services.source_connectors.connector_run_manifest import (
    build_connector_run_manifest_v1,
)
from nativeforge.services.source_connectors.normalization import (
    to_discovery_intake_candidate_payload,
)
from nativeforge.services.source_connectors.static_fixture_connector import (
    dry_run_fixture_rows,
)


class IntakeBridgeFixtureError(ValueError):
    """Raised when fixture rows fail connector-side normalization before intake."""

    def __init__(self, errors: tuple[dict[str, Any], ...]) -> None:
        super().__init__("fixture normalization failed")
        self.errors = errors


def static_fixture_connector_intake_dry_run(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    source_registry_id: uuid.UUID,
    fixture_rows: list[dict[str, Any]],
    connector_config: ConnectorSourceConfig,
    run_context: ConnectorRunContext | None = None,
    intake_mode: DiscoveryIntakeMode = DiscoveryIntakeMode.structured_batch,
    operator_note: str | None = None,
) -> dict[str, Any]:
    """
    Run the Sprint 22 static fixture connector, then the existing intake pipeline.

    Calls `start_intake_run` and `process_structured_candidates` only — no parallel
    intake system. Persists through the same code path as API-originated batches.
    """
    ctx = run_context or ConnectorRunContext()
    cfg = replace(connector_config, source_registry_id=source_registry_id)
    dry = dry_run_fixture_rows(fixture_rows, config=cfg, ctx=ctx)
    if dry.errors:
        raise IntakeBridgeFixtureError(dry.errors)
    candidates = [to_discovery_intake_candidate_payload(c) for c in dry.candidates]
    run = start_intake_run(
        session,
        org=org,
        source_registry_id=source_registry_id,
        intake_mode=intake_mode,
        operator_note=operator_note,
    )
    out = process_structured_candidates(
        session,
        org=org,
        org_type=org_type,
        run_id=run.id,
        candidates=candidates,
    )
    manifest = build_connector_run_manifest_v1(
        source_registry_id=source_registry_id,
        intake_run_id=run.id,
        dry_run=ctx.dry_run,
        connector_run_id=ctx.run_id,
        fixture_row_count=len(fixture_rows),
        normalized_candidate_count=len(candidates),
    )
    return {**out, "connector_manifest": manifest}
