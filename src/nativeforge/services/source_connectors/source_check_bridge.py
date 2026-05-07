"""Wire offline connector dry runs to source check runs + intake (no network)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.db.models import Organization, is_demo_for_org_type
from nativeforge.domain.enums import (
    DiscoveryIntakeMode,
    SourceCheckMode,
    SourceCheckRunStatus,
)
from nativeforge.lib.demo_isolation import OrgType
from nativeforge.repositories import opportunity_sources as os_repo
from nativeforge.repositories import source_check_runs as scr_repo
from nativeforge.services import source_freshness_service as sfs
from nativeforge.services.source_connectors.base import (
    ConnectorRunContext,
    ConnectorSourceConfig,
)
from nativeforge.services.source_connectors.connector_diagnostics import (
    connector_shape_label,
    source_labels_from_fixture_rows,
    warning_codes_from_connector_normalization_errors,
)
from nativeforge.services.source_connectors.connector_health import (
    ConnectorHealthLabel,
    intake_bridge_outcome_health,
)
from nativeforge.services.source_connectors.connector_run_manifest import (
    build_connector_run_manifest_v1,
)
from nativeforge.services.source_connectors.intake_bridge import (
    IntakeBridgeFixtureError,
    static_fixture_connector_intake_dry_run,
)


def run_source_check_backed_connector_dry_run(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    source_registry_id: uuid.UUID,
    fixture_rows: list[dict[str, Any]],
    connector_config: ConnectorSourceConfig,
    run_context: ConnectorRunContext | None = None,
    check_mode: str = SourceCheckMode.manual.value,
    intake_mode: DiscoveryIntakeMode = DiscoveryIntakeMode.structured_batch,
    operator_note: str | None = None,
) -> dict[str, Any]:
    """
    Create a running source-check row, run static fixture intake, finalize the check.

    Deterministic; caller commits. On fixture normalization failure before intake,
    the source check is finalized as failed and no intake run is created.
    """
    registry = os_repo.get_opportunity_source_scoped(
        session=session,
        source_id=source_registry_id,
        org_id=org.id,
        org_type=org_type,
    )
    if registry is None:
        raise ValueError("opportunity source not found for source_registry_id")

    ctx = run_context or ConnectorRunContext()
    check_run = scr_repo.create_source_check_run(
        session,
        organization_id=org.id,
        is_demo=is_demo_for_org_type(org.org_type),
        source_registry_id=source_registry_id,
        check_mode=check_mode,
        check_status=SourceCheckRunStatus.running.value,
    )

    provenance_extras: dict[str, Any] = {
        "source_check_run_id": str(check_run.id),
    }

    try:
        intake_out = static_fixture_connector_intake_dry_run(
            session,
            org=org,
            org_type=org_type,
            source_registry_id=source_registry_id,
            fixture_rows=fixture_rows,
            connector_config=connector_config,
            run_context=ctx,
            intake_mode=intake_mode,
            operator_note=operator_note,
            source_check_run_id=check_run.id,
            connector_provenance_extras=provenance_extras,
        )
    except IntakeBridgeFixtureError as ex:
        src_hint = {
            "connector_shape": connector_shape_label(
                grants_gov_shaped_dry_run=False,
                provenance={},
            ),
        }
        src_hint.update(source_labels_from_fixture_rows(fixture_rows))
        manifest = build_connector_run_manifest_v1(
            source_registry_id=source_registry_id,
            intake_run_id=None,
            dry_run=ctx.dry_run,
            connector_run_id=ctx.run_id,
            fixture_row_count=len(fixture_rows),
            normalized_candidate_count=0,
            intake_candidate_count=0,
            accepted=0,
            duplicate=0,
            rejected=0,
            error=0,
            review_required=0,
            normalization_errors=len(ex.errors),
            source_check_run_id=check_run.id,
            connector_id=connector_config.connector_id,
            connector_schema_version=ctx.normalization_schema_version,
            health_status="failed",
            warning_codes=warning_codes_from_connector_normalization_errors(ex.errors),
            source_identifiers=src_hint,
        )
        err_msgs = [str(e.get("message", "")) for e in ex.errors]
        summary_blob = {
            "connector_dry_run": True,
            "fixture_normalization_failed": True,
            "fixture_errors": list(ex.errors),
            "connector_manifest": manifest,
        }
        sfs.finalize_completed_source_check(
            session,
            org=org,
            org_type=org_type,
            run=check_run,
            source=registry,
            patch={
                "check_status": SourceCheckRunStatus.failed.value,
                "opportunities_seen_count": 0,
                "new_candidates_count": 0,
                "accepted_count": 0,
                "duplicate_count": 0,
                "rejected_count": 0,
                "review_items_created_count": 0,
                "error_code": "fixture_normalization_failed",
                "error_message": (
                    "; ".join(err_msgs) if err_msgs else "fixture_normalization_failed"
                ),
                "result_summary": summary_blob,
            },
        )
        health: ConnectorHealthLabel = intake_bridge_outcome_health(
            normalization_errors=len(ex.errors),
            accepted_count=0,
            rejected_count=0,
            duplicate_count=0,
            error_count=0,
        )
        return {
            "source_check_run": sfs.check_run_to_dict(check_run),
            "intake_run": None,
            "connector_manifest": manifest,
            "connector_health": health,
            "candidate_counts": {
                "normalization_errors": len(ex.errors),
                "accepted_count": 0,
                "rejected_count": 0,
                "duplicate_count": 0,
                "error_count": 0,
                "candidate_count": 0,
            },
        }

    counts_map = intake_out["summary"]["counts"]
    accepted = int(counts_map["accepted_count"])
    rejected = int(counts_map["rejected_count"])
    duplicate = int(counts_map["duplicate_count"])
    err_cnt = int(counts_map["error_count"])
    cand_total = int(counts_map["candidate_count"])

    check_complete_status = (
        SourceCheckRunStatus.succeeded.value
        if err_cnt == 0
        else SourceCheckRunStatus.succeeded_with_warnings.value
    )

    manifest = intake_out["connector_manifest"]
    intake_run_dict = intake_out["intake_run"]
    summary_blob = {
        "connector_dry_run": True,
        "intake_run_id": intake_run_dict["id"],
        "connector_manifest": manifest,
    }

    sfs.finalize_completed_source_check(
        session,
        org=org,
        org_type=org_type,
        run=check_run,
        source=registry,
        patch={
            "check_status": check_complete_status,
            "opportunities_seen_count": cand_total,
            "new_candidates_count": accepted,
            "accepted_count": accepted,
            "duplicate_count": duplicate,
            "rejected_count": rejected,
            "review_items_created_count": 0,
            "result_summary": summary_blob,
        },
    )

    health = intake_out.get("connector_health")
    if health is None:
        health = intake_bridge_outcome_health(
            normalization_errors=0,
            accepted_count=accepted,
            rejected_count=rejected,
            duplicate_count=duplicate,
            error_count=err_cnt,
        )

    return {
        "source_check_run": sfs.check_run_to_dict(check_run),
        "intake_run": intake_run_dict,
        "connector_manifest": manifest,
        "connector_health": health,
        "candidate_counts": {
            "normalization_errors": 0,
            "accepted_count": accepted,
            "rejected_count": rejected,
            "duplicate_count": duplicate,
            "error_count": err_cnt,
            "candidate_count": cand_total,
        },
    }
