"""Wire offline connector dry runs to source check runs + intake (no network)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
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
    build_connector_source_check_result_summary_v1,
    connector_shape_label,
    source_labels_from_fixture_rows,
    warning_codes_from_connector_normalization_errors,
)
from nativeforge.services.source_connectors.connector_health import (
    ConnectorHealthLabel,
    connector_dry_run_operator_diagnostic_message,
    connector_outcome_warning_codes,
    intake_bridge_outcome_health,
)
from nativeforge.services.source_connectors.connector_operator_escalation import (
    build_connector_operator_escalation_recommendations,
    enrich_connector_result_summary_with_escalations,
    persist_connector_escalations_as_operator_actions,
)
from nativeforge.services.source_connectors.connector_run_manifest import (
    build_connector_run_manifest_v1,
)
from nativeforge.services.source_connectors.intake_bridge import (
    IntakeBridgeFixtureError,
    static_fixture_connector_intake_dry_run,
)


def _connector_shape_from_manifest(manifest: dict[str, Any]) -> str | None:
    src = manifest.get("source_identifiers")
    if isinstance(src, dict):
        raw = src.get("connector_shape")
        return str(raw) if raw is not None else None
    return None


def _embed_connector_escalations(
    summary_blob: dict[str, Any],
    *,
    source_registry_id: uuid.UUID,
    check_run_id: uuid.UUID,
    intake_run_id: str | None,
    connector_id: str | None,
    health: str,
    manifest: dict[str, Any],
    accepted: int,
    rejected: int,
    duplicate: int,
    err_cnt: int,
    review_req: int,
    normalization_errors: int,
    op_msg: str,
    source_check_run_status: str | None,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    esc = build_connector_operator_escalation_recommendations(
        source_registry_id=str(source_registry_id),
        source_check_run_id=str(check_run_id),
        intake_run_id=intake_run_id,
        connector_id=connector_id,
        health_status=str(health),
        warning_codes=list(manifest.get("warning_codes") or []),
        normalization_errors=normalization_errors,
        accepted_count=accepted,
        rejected_count=rejected,
        duplicate_count=duplicate,
        error_count=err_cnt,
        review_required_count=review_req,
        operator_diagnostic_message=op_msg,
        source_check_run_status=source_check_run_status,
        manifest=manifest,
    )
    enriched = enrich_connector_result_summary_with_escalations(summary_blob, esc)
    return enriched, esc


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
    grants_gov_shaped_dry_run: bool = False,
    create_operator_actions: bool = False,
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

    ref_now = datetime.now(UTC)
    was_overdue = sfs.is_active_source_overdue(registry, now=ref_now)

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
            grants_gov_shaped_dry_run=grants_gov_shaped_dry_run,
            source_overdue_for_check=was_overdue,
        )
    except IntakeBridgeFixtureError as ex:
        src_hint = {
            "connector_shape": connector_shape_label(
                grants_gov_shaped_dry_run=grants_gov_shaped_dry_run,
                provenance={},
            ),
        }
        src_hint.update(source_labels_from_fixture_rows(fixture_rows))
        rows_kwargs: dict[str, Any] = {}
        if grants_gov_shaped_dry_run:
            rows_kwargs["source_row_count"] = len(fixture_rows)
        else:
            rows_kwargs["fixture_row_count"] = len(fixture_rows)
        norm_codes = warning_codes_from_connector_normalization_errors(ex.errors)
        outcome_codes = connector_outcome_warning_codes(
            health="failed",
            accepted_count=0,
            rejected_count=0,
            duplicate_count=0,
            error_count=0,
            review_required_count=0,
            normalization_errors=len(ex.errors),
        )
        merged_codes = sorted(set(norm_codes) | set(outcome_codes))
        manifest = build_connector_run_manifest_v1(
            source_registry_id=source_registry_id,
            intake_run_id=None,
            dry_run=ctx.dry_run,
            connector_run_id=ctx.run_id,
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
            warning_codes=merged_codes,
            source_identifiers=src_hint,
            **rows_kwargs,
        )
        err_msgs = [str(e.get("message", "")) for e in ex.errors]
        fr_ct = len(fixture_rows)
        op_msg = connector_dry_run_operator_diagnostic_message(
            health="failed",
            accepted_count=0,
            rejected_count=0,
            duplicate_count=0,
            error_count=0,
            review_required_count=0,
            normalization_errors=len(ex.errors),
            fixture_row_count=fr_ct if not grants_gov_shaped_dry_run else None,
            source_row_count=fr_ct if grants_gov_shaped_dry_run else None,
        )
        summary_blob = build_connector_source_check_result_summary_v1(
            connector_id=connector_config.connector_id,
            connector_shape=_connector_shape_from_manifest(manifest),
            health_status="failed",
            warning_codes=merged_codes,
            manifest=manifest,
            intake_run_id=None,
            source_check_run_id=str(check_run.id),
            accepted_count=0,
            duplicate_count=0,
            rejected_count=0,
            error_count=0,
            review_required_count=0,
            fixture_rows=manifest["counts"].get("fixture_rows"),
            source_rows=manifest["counts"].get("source_rows"),
            operator_diagnostic_message=op_msg,
        )
        summary_blob["fixture_normalization_failed"] = True
        summary_blob["fixture_errors"] = list(ex.errors)
        summary_blob, esc_list = _embed_connector_escalations(
            summary_blob,
            source_registry_id=source_registry_id,
            check_run_id=check_run.id,
            intake_run_id=None,
            connector_id=connector_config.connector_id,
            health="failed",
            manifest=manifest,
            accepted=0,
            rejected=0,
            duplicate=0,
            err_cnt=0,
            review_req=0,
            normalization_errors=len(ex.errors),
            op_msg=op_msg,
            source_check_run_status=SourceCheckRunStatus.failed.value,
        )
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
            now=ref_now,
        )
        health: ConnectorHealthLabel = intake_bridge_outcome_health(
            normalization_errors=len(ex.errors),
            accepted_count=0,
            rejected_count=0,
            duplicate_count=0,
            error_count=0,
        )
        actions_created: list[dict[str, Any]] = []
        if create_operator_actions:
            actions_created = persist_connector_escalations_as_operator_actions(
                session,
                org=org,
                org_type=org_type,
                recommendations=esc_list,
                create_operator_actions=True,
            )
        out_norm: dict[str, Any] = {
            "source_check_run": sfs.check_run_to_dict(check_run),
            "intake_run": None,
            "connector_manifest": manifest,
            "connector_health": health,
            "connector_operator_escalations": esc_list,
            "candidate_counts": {
                "normalization_errors": len(ex.errors),
                "accepted_count": 0,
                "rejected_count": 0,
                "duplicate_count": 0,
                "error_count": 0,
                "candidate_count": 0,
            },
        }
        if create_operator_actions:
            out_norm["operator_actions_created"] = actions_created
        return out_norm

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
    counts_body = manifest.get("counts") if isinstance(manifest, dict) else {}
    review_req = int(counts_body.get("review_required", 0)) if counts_body else 0
    health = intake_out.get("connector_health")
    if health is None:
        health = intake_bridge_outcome_health(
            normalization_errors=0,
            accepted_count=accepted,
            rejected_count=rejected,
            duplicate_count=duplicate,
            error_count=err_cnt,
            review_required_count=review_req,
            source_overdue_for_check=was_overdue,
        )

    op_msg = connector_dry_run_operator_diagnostic_message(
        health=health,
        accepted_count=accepted,
        rejected_count=rejected,
        duplicate_count=duplicate,
        error_count=err_cnt,
        review_required_count=review_req,
        normalization_errors=0,
        fixture_row_count=counts_body.get("fixture_rows")
        if counts_body.get("fixture_rows") is not None
        else None,
        source_row_count=counts_body.get("source_rows")
        if counts_body.get("source_rows") is not None
        else None,
    )
    summary_blob = build_connector_source_check_result_summary_v1(
        connector_id=connector_config.connector_id,
        connector_shape=_connector_shape_from_manifest(manifest),
        health_status=str(health),
        warning_codes=list(manifest.get("warning_codes") or []),
        manifest=manifest,
        intake_run_id=str(intake_run_dict["id"]),
        source_check_run_id=str(check_run.id),
        accepted_count=accepted,
        duplicate_count=duplicate,
        rejected_count=rejected,
        error_count=err_cnt,
        review_required_count=review_req,
        fixture_rows=counts_body.get("fixture_rows"),
        source_rows=counts_body.get("source_rows"),
        operator_diagnostic_message=op_msg,
    )
    summary_blob, esc_list = _embed_connector_escalations(
        summary_blob,
        source_registry_id=source_registry_id,
        check_run_id=check_run.id,
        intake_run_id=str(intake_run_dict["id"]),
        connector_id=connector_config.connector_id,
        health=str(health),
        manifest=manifest,
        accepted=accepted,
        rejected=rejected,
        duplicate=duplicate,
        err_cnt=err_cnt,
        review_req=review_req,
        normalization_errors=0,
        op_msg=op_msg,
        source_check_run_status=check_complete_status,
    )

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
        now=ref_now,
    )

    actions_created_ok: list[dict[str, Any]] = []
    if create_operator_actions:
        actions_created_ok = persist_connector_escalations_as_operator_actions(
            session,
            org=org,
            org_type=org_type,
            recommendations=esc_list,
            create_operator_actions=True,
        )
    out_ok: dict[str, Any] = {
        "source_check_run": sfs.check_run_to_dict(check_run),
        "intake_run": intake_run_dict,
        "connector_manifest": manifest,
        "connector_health": health,
        "connector_operator_escalations": esc_list,
        "candidate_counts": {
            "normalization_errors": 0,
            "accepted_count": accepted,
            "rejected_count": rejected,
            "duplicate_count": duplicate,
            "error_count": err_cnt,
            "candidate_count": cand_total,
        },
    }
    if create_operator_actions:
        out_ok["operator_actions_created"] = actions_created_ok
    return out_ok
