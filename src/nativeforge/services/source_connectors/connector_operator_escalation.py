"""Deterministic connector → operator escalation recommendations (Sprint 29).

Pure builders map connector manifest / source-check summaries to structured
recommendations that align with existing operator action / decision primitives.
No network access.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.db.models import Organization
from nativeforge.domain.enums import (
    OperatorDecisionAction,
    OperatorDecisionItemType,
    OperatorDecisionSeverity,
    SourceCheckRunStatus,
)
from nativeforge.lib.demo_isolation import OrgType

CONNECTOR_OPERATOR_ESCALATION_SCHEMA_VERSION = "nf_connector_operator_escalation_v1"

_INFORMATIONAL_WARNING_CODES = frozenset(
    {
        "review_required_elevated",
    }
)


def _stable_decision_id(source_check_run_id: str | None, escalation_type: str) -> str:
    raw = f"nf_co_esc|{source_check_run_id or 'none'}|{escalation_type}"
    return raw[:256]


def _evidence_refs(
    *,
    manifest: dict[str, Any] | None,
    extra: dict[str, Any],
) -> dict[str, Any]:
    out: dict[str, Any] = dict(extra)
    if manifest and isinstance(manifest.get("connector_run_id"), str):
        out["connector_run_id"] = manifest["connector_run_id"]
    if manifest and isinstance(manifest.get("source_identifiers"), dict):
        out["source_identifiers"] = manifest["source_identifiers"]
    return out


def _subject_hints(
    *,
    source_registry_id: str | None,
    source_check_run_id: str | None,
    intake_run_id: str | None,
) -> list[dict[str, str]]:
    hints: list[dict[str, str]] = []
    if source_check_run_id:
        hints.append(
            {"subject_type": "source_check_run", "subject_id": source_check_run_id},
        )
    if source_registry_id:
        hints.append(
            {"subject_type": "opportunity_source", "subject_id": source_registry_id},
        )
    if intake_run_id:
        hints.append({"subject_type": "intake_run", "subject_id": intake_run_id})
    return hints


def build_connector_operator_escalation_recommendations(
    *,
    source_registry_id: str | None,
    source_check_run_id: str | None,
    intake_run_id: str | None,
    connector_id: str | None,
    health_status: str,
    warning_codes: list[str],
    normalization_errors: int,
    accepted_count: int,
    rejected_count: int,
    duplicate_count: int,
    error_count: int,
    review_required_count: int,
    operator_diagnostic_message: str = "",
    source_check_run_status: str | None = None,
    manifest: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """
    Produce zero or more escalation rows. Healthy runs default to no recommendations.

    Ordering is deterministic (escalation_type, priority rank).
    """
    codes = sorted(set(warning_codes))
    diag = (operator_diagnostic_message or "").strip()
    recs: list[dict[str, Any]] = []

    def _rank_pri(p: str) -> int:
        return {"critical": 4, "high": 3, "medium": 2, "low": 1, "none": 0}.get(p, 0)

    def _append(
        *,
        escalation_type: str,
        priority: str,
        reason_codes: list[str],
        operator_title: str,
        operator_message: str,
        recommended_action: str,
        item_type: str,
        severity: str,
        should_create_action: bool,
    ) -> None:
        recs.append(
            {
                "schema_version": CONNECTOR_OPERATOR_ESCALATION_SCHEMA_VERSION,
                "source_registry_id": source_registry_id,
                "source_check_run_id": source_check_run_id,
                "intake_run_id": intake_run_id,
                "connector_id": connector_id,
                "health_status": health_status,
                "priority": priority,
                "escalation_type": escalation_type,
                "reason_codes": reason_codes,
                "operator_title": operator_title,
                "operator_message": operator_message or diag,
                "recommended_action": recommended_action,
                "operator_decision_item_type": item_type,
                "operator_decision_severity": severity,
                "evidence_refs": _evidence_refs(
                    manifest=manifest,
                    extra={
                        "warning_codes": codes,
                        "counts": {
                            "accepted_count": accepted_count,
                            "rejected_count": rejected_count,
                            "duplicate_count": duplicate_count,
                            "error_count": error_count,
                            "review_required_count": review_required_count,
                            "normalization_errors": normalization_errors,
                        },
                    },
                ),
                "evidence_pack_subject_hints": _subject_hints(
                    source_registry_id=source_registry_id,
                    source_check_run_id=source_check_run_id,
                    intake_run_id=intake_run_id,
                ),
                "should_create_action": should_create_action,
            },
        )

    # Healthy + informational warnings only (no ledger spam by default).
    if health_status == "healthy":
        note_codes = sorted(c for c in codes if c in _INFORMATIONAL_WARNING_CODES)
        if note_codes:
            _append(
                escalation_type="operator_diagnostic_note",
                priority="low",
                reason_codes=note_codes,
                operator_title="Connector dry run — elevated review rate",
                operator_message=(
                    diag
                    or (
                        "Accepted candidates carry review-required signals above "
                        "baseline; monitor Native relevance thresholds."
                    )
                ),
                recommended_action=OperatorDecisionAction.monitor.value,
                item_type=OperatorDecisionItemType.quality_risk.value,
                severity=OperatorDecisionSeverity.low.value,
                should_create_action=False,
            )
        _warn_st = SourceCheckRunStatus.succeeded_with_warnings.value
        if source_check_run_status == _warn_st and error_count == 0:
            _append(
                escalation_type="operator_diagnostic_note",
                priority="low",
                reason_codes=sorted(set(codes) | {"source_check_warnings"}),
                operator_title="Source check completed with warnings",
                operator_message=(
                    diag
                    or (
                        "Review source-check diagnostics even though intake stayed "
                        "healthy."
                    )
                ),
                recommended_action=OperatorDecisionAction.monitor.value,
                item_type=OperatorDecisionItemType.quality_risk.value,
                severity=OperatorDecisionSeverity.low.value,
                should_create_action=False,
            )
        return sorted(
            recs,
            key=lambda r: (
                -_rank_pri(str(r.get("priority") or "none")),
                str(r.get("escalation_type") or ""),
            ),
        )

    if normalization_errors > 0:
        _append(
            escalation_type="normalization_mapping_failure",
            priority="high",
            reason_codes=sorted(set(codes) | {"fixture_normalization_failed"}),
            operator_title="Inspect connector normalization mapping",
            operator_message=(
                diag
                or "Fixture rows failed connector normalization before intake; "
                "correct field mapping or fixture shape."
            ),
            recommended_action=OperatorDecisionAction.resolve_failure.value,
            item_type=OperatorDecisionItemType.intake_run_attention.value,
            severity=OperatorDecisionSeverity.high.value,
            should_create_action=True,
        )
        return sorted(
            recs,
            key=lambda r: (
                -_rank_pri(str(r.get("priority") or "none")),
                str(r.get("escalation_type") or ""),
            ),
        )

    if health_status == "failed" and error_count > 0:
        _append(
            escalation_type="connector_run_failed",
            priority="high",
            reason_codes=sorted(set(codes) | {"intake_candidate_errors"}),
            operator_title="Investigate connector or source processing failure",
            operator_message=(
                diag
                or (
                    "Intake reported candidate processing errors; trace connector "
                    "output and intake handling for this source."
                )
            ),
            recommended_action=OperatorDecisionAction.resolve_failure.value,
            item_type=OperatorDecisionItemType.source_failing.value,
            severity=OperatorDecisionSeverity.high.value,
            should_create_action=True,
        )

    if health_status == "empty":
        _append(
            escalation_type="source_coverage_verification",
            priority="medium",
            reason_codes=sorted(set(codes) | {"connector_run_empty"}),
            operator_title="Verify source coverage or expected no-op",
            operator_message=(
                diag
                or "Dry run produced zero intake candidates; confirm upstream payload, "
                "filters, or an intentional empty batch."
            ),
            recommended_action=OperatorDecisionAction.check_source.value,
            item_type=OperatorDecisionItemType.source_yield_issue.value,
            severity=OperatorDecisionSeverity.medium.value,
            should_create_action=True,
        )

    if health_status == "stale":
        _append(
            escalation_type="source_freshness_verification",
            priority="medium",
            reason_codes=sorted(set(codes) | {"source_check_overdue"}),
            operator_title="Verify source freshness schedule",
            operator_message=(
                diag
                or "Accepted intake while this source was overdue for its scheduled "
                "check; validate cadence and registry freshness metadata."
            ),
            recommended_action=OperatorDecisionAction.verify.value,
            item_type=OperatorDecisionItemType.source_overdue.value,
            severity=OperatorDecisionSeverity.medium.value,
            should_create_action=True,
        )

    if health_status == "degraded":
        dup_dom = duplicate_count > accepted_count or (
            accepted_count == 0 and duplicate_count > 0
        )
        rev_heavy = (
            accepted_count > 0
            and review_required_count >= 2
            and review_required_count >= accepted_count
        )
        if dup_dom:
            _append(
                escalation_type="dedupe_source_overlap",
                priority="medium",
                reason_codes=sorted(
                    set(codes)
                    | {
                        "duplicate_load_dominant",
                        "duplicate_only_intake",
                    },
                ),
                operator_title="Inspect deduplication and source overlap",
                operator_message=(
                    diag
                    or "Duplicates dominate outcomes relative to accepts; review "
                    "identity keys, corpus overlap, and upstream duplication."
                ),
                recommended_action=OperatorDecisionAction.inspect_intake_run.value,
                item_type=OperatorDecisionItemType.intake_run_attention.value,
                severity=OperatorDecisionSeverity.medium.value,
                should_create_action=True,
            )
        if rev_heavy:
            _append(
                escalation_type="native_relevance_rule_precision",
                priority="medium",
                reason_codes=sorted(set(codes) | {"review_required_heavy"}),
                operator_title="Review Native relevance rule precision",
                operator_message=(
                    diag
                    or "Most accepted candidates require operator review; tune "
                    "connector_native_relevance_v1 thresholds or rules."
                ),
                recommended_action=OperatorDecisionAction.improve_source_quality.value,
                item_type=OperatorDecisionItemType.quality_risk.value,
                severity=OperatorDecisionSeverity.medium.value,
                should_create_action=True,
            )
        if not dup_dom and not rev_heavy:
            _append(
                escalation_type="connector_intake_degraded",
                priority="medium",
                reason_codes=codes,
                operator_title="Inspect degraded connector intake outcomes",
                operator_message=(
                    diag
                    or (
                        "Intake finished without accepts or with rejection-heavy "
                        "outcomes; inspect eligibility filters and connector logic."
                    )
                ),
                recommended_action=OperatorDecisionAction.inspect_intake_run.value,
                item_type=OperatorDecisionItemType.intake_run_attention.value,
                severity=OperatorDecisionSeverity.medium.value,
                should_create_action=True,
            )

    out = sorted(
        recs,
        key=lambda r: (
            -_rank_pri(str(r.get("priority") or "none")),
            str(r.get("escalation_type") or ""),
        ),
    )
    return out


def enrich_connector_result_summary_with_escalations(
    summary: dict[str, Any],
    recommendations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Merge escalations into a connector source-check ``result_summary`` blob."""
    merged = dict(summary)
    merged["connector_operator_escalation_schema_version"] = (
        CONNECTOR_OPERATOR_ESCALATION_SCHEMA_VERSION
    )
    merged["operator_escalation_recommendations"] = recommendations
    return merged


def escalation_recommendations_json_safe(
    recommendations: Sequence[dict[str, Any]],
) -> str:
    """Serialize recommendations (``json.dumps`` with sorted keys)."""
    return json.dumps(list(recommendations), sort_keys=True)


def persist_connector_escalations_as_operator_actions(
    session: Session,
    *,
    org: Organization,
    org_type: OrgType,
    recommendations: Sequence[dict[str, Any]],
    create_operator_actions: bool = False,
) -> list[dict[str, Any]]:
    """
    Optional ledger writes via existing manual operator-action creation.

    Defaults to no-op; callers must pass create_operator_actions=True explicitly.
    """
    if not create_operator_actions:
        return []
    from nativeforge.services import operator_action_service as oa_svc

    created: list[dict[str, Any]] = []
    for rec in recommendations:
        if not rec.get("should_create_action"):
            continue
        esc_type = str(rec.get("escalation_type") or "unknown")
        scr_id = rec.get("source_check_run_id")
        did = _stable_decision_id(
            str(scr_id) if scr_id else None,
            esc_type,
        )
        src_reg = rec.get("source_registry_id")
        intake = rec.get("intake_run_id")
        src_uuid = uuid.UUID(str(src_reg)) if src_reg else None
        intake_uuid = uuid.UUID(str(intake)) if intake else None
        scr_uuid = uuid.UUID(str(scr_id)) if scr_id else None

        title = str(rec.get("operator_title") or "Connector escalation").strip()[:512]
        body = str(rec.get("operator_message") or "").strip()
        item_type = str(rec.get("operator_decision_item_type") or "").strip()
        severity = str(rec.get("operator_decision_severity") or "").strip()
        action = str(rec.get("recommended_action") or "").strip()

        try:
            row = oa_svc.create_operator_action_manual(
                session,
                org=org,
                org_type=org_type,
                decision_id=did,
                action_title=title,
                operator_action=body,
                item_type=item_type,
                severity=severity,
                action=action,
                action_summary=body,
                source_registry_id=src_uuid,
                intake_run_id=intake_uuid,
                source_check_run_id=scr_uuid,
            )
            created.append(row)
        except ValueError:
            # Duplicate decision_id — skip without failing dry-run callers.
            continue
    return created


__all__ = [
    "CONNECTOR_OPERATOR_ESCALATION_SCHEMA_VERSION",
    "build_connector_operator_escalation_recommendations",
    "enrich_connector_result_summary_with_escalations",
    "escalation_recommendations_json_safe",
    "persist_connector_escalations_as_operator_actions",
]
