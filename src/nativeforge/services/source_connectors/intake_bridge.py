"""Bridge static fixture connector output into `discovery_intake_service` (offline)."""

from __future__ import annotations

import dataclasses
import uuid
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.db.models import Organization
from nativeforge.domain.enums import DiscoveryIntakeMode
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import discovery_intake_runs as intake_repo
from nativeforge.services.discovery_intake_service import (
    process_structured_candidates,
    start_intake_run,
)
from nativeforge.services.source_connectors.base import (
    ConnectorRunContext,
    ConnectorSourceConfig,
    NormalizedOpportunityCandidate,
)
from nativeforge.services.source_connectors.connector_diagnostics import (
    connector_shape_label,
    count_review_required_from_intake_candidates,
    source_labels_from_fixture_rows,
)
from nativeforge.services.source_connectors.connector_health import (
    intake_bridge_outcome_health,
)
from nativeforge.services.source_connectors.connector_run_manifest import (
    build_connector_run_manifest_v1,
)
from nativeforge.services.source_connectors.grants_gov_shaped import (
    dry_run_grants_gov_shaped_rows,
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
    source_check_run_id: uuid.UUID | None = None,
    connector_provenance_extras: dict[str, Any] | None = None,
    evidence_pack_subject_hints: dict[str, Any] | None = None,
    grants_gov_shaped_dry_run: bool = False,
) -> dict[str, Any]:
    """
    Run the Sprint 22 static fixture connector, then the existing intake pipeline.

    Calls `start_intake_run` and `process_structured_candidates` only — no parallel
    intake system. Persists through the same code path as API-originated batches.

    When ``grants_gov_shaped_dry_run`` is True, rows are normalized via
    :func:`dry_run_grants_gov_shaped_rows` (Grants.gov-like keys) instead of the
    static fixture connector.
    """
    ctx = run_context or ConnectorRunContext()
    cfg = dataclasses.replace(connector_config, source_registry_id=source_registry_id)
    if grants_gov_shaped_dry_run:
        dry = dry_run_grants_gov_shaped_rows(fixture_rows, config=cfg, ctx=ctx)
    else:
        dry = dry_run_fixture_rows(fixture_rows, config=cfg, ctx=ctx)
    if dry.errors:
        raise IntakeBridgeFixtureError(dry.errors)
    merged_norm: list[NormalizedOpportunityCandidate] = []
    for c in dry.candidates:
        prov = dict(c.provenance)
        if connector_provenance_extras:
            prov.update(connector_provenance_extras)
        merged_norm.append(dataclasses.replace(c, provenance=prov))
    first_prov = dict(merged_norm[0].provenance) if merged_norm else {}
    shape_lbl = connector_shape_label(
        grants_gov_shaped_dry_run=grants_gov_shaped_dry_run,
        provenance=first_prov,
    )
    src_ids: dict[str, Any] = {
        "connector_shape": shape_lbl,
    }
    src_ids.update(source_labels_from_fixture_rows(fixture_rows))

    candidates = [to_discovery_intake_candidate_payload(c) for c in merged_norm]
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
    counts_map = out["summary"]["counts"]
    accepted = int(counts_map["accepted_count"])
    rejected = int(counts_map["rejected_count"])
    duplicate = int(counts_map["duplicate_count"])
    err_cnt = int(counts_map["error_count"])
    cand_total = int(counts_map["candidate_count"])

    db_candidates = intake_repo.list_discovery_intake_candidates_for_run(
        session=session,
        org_id=org.id,
        org_type=org_type,
        intake_run_id=run.id,
    )
    review_req = count_review_required_from_intake_candidates(db_candidates)

    health = intake_bridge_outcome_health(
        normalization_errors=0,
        accepted_count=accepted,
        rejected_count=rejected,
        duplicate_count=duplicate,
        error_count=err_cnt,
    )

    row_n = len(fixture_rows)
    rows_kwargs: dict[str, Any] = {}
    if grants_gov_shaped_dry_run:
        rows_kwargs["source_row_count"] = row_n
    else:
        rows_kwargs["fixture_row_count"] = row_n

    manifest = build_connector_run_manifest_v1(
        source_registry_id=source_registry_id,
        intake_run_id=run.id,
        dry_run=ctx.dry_run,
        connector_run_id=ctx.run_id,
        normalized_candidate_count=len(candidates),
        intake_candidate_count=cand_total,
        accepted=accepted,
        duplicate=duplicate,
        rejected=rejected,
        error=err_cnt,
        review_required=review_req,
        normalization_errors=0,
        source_check_run_id=source_check_run_id,
        evidence_pack_subject_hints=evidence_pack_subject_hints,
        connector_id=connector_config.connector_id,
        connector_schema_version=ctx.normalization_schema_version,
        health_status=health,
        source_identifiers=src_ids,
        **rows_kwargs,
    )
    return {**out, "connector_manifest": manifest, "connector_health": health}
