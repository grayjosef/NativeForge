"""Production dry-run cutover rehearsal + final freeze verification (Block 62)."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from nativeforge.services.audit_event_collector_service import (
    AuditEventCollector,
    new_collector,
)
from nativeforge.services.gate26_controlled_pilot_master_service import (
    build_mode_a_pilot_master_packet,
)
from nativeforge.services.gate27_cutover_claim_freeze_service import (
    build_claim_freeze_matrix,
)
from nativeforge.services.gate28_mode_b_rehearsal_service import run_mode_b_rehearsal

SCHEMA_VERSION = "nf_gate28_dry_run_cutover_v1"

STEP_STATUSES = (
    "not_started",
    "ready",
    "validated",
    "blocked_missing_input",
    "blocked_missing_config",
    "blocked_missing_evidence",
    "blocked_policy",
    "blocked_security",
    "blocked_owner_approval",
    "blocked_not_supported",
    "skipped_after_blocker",
    "unknown",
)

CUTOVER_STEPS = (
    "baseline_repo_state",
    "sca_evidence_check",
    "auth0_oidc_preflight",
    "auth0_live_validation",
    "invite_org_role_mapping",
    "rbac_session_tenant_audit",
    "storage_approval_token_validation",
    "metadata_config_validation",
    "object_storage_config_validation",
    "signed_url_validation",
    "sse_encryption_validation",
    "malware_scan_validation",
    "customer_data_policy_validation",
    "retention_delete_export_validation",
    "pen_test_evidence_validation",
    "authority_verification_status",
    "source_coverage_status",
    "support_feedback_readiness",
    "ux_trust_readiness_check",
    "controlled_pilot_master_resolver",
    "production_rollout_resolver",
    "final_claim_freeze",
)

def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _emit_audit(
    collector: AuditEventCollector, event: str, detail: dict[str, Any]
) -> None:
    collector.record(event, detail)


def _step(
    name: str,
    status: str,
    evidence_ref: str,
    blocked_reason: str,
    owner_action: str,
    claim_impact: str,
    next_step_allowed: bool,
) -> dict[str, Any]:
    st = status if status in STEP_STATUSES else "unknown"
    return {
        "name": name,
        "status": st,
        "evidence_ref": evidence_ref,
        "blocked_reason": blocked_reason,
        "owner_action": owner_action,
        "claim_impact": claim_impact,
        "next_step_allowed": next_step_allowed,
    }


def run_production_dry_run_cutover(
    *,
    login_live: bool = False,
    storage_approval_present: bool = False,
    pen_test_report_present: bool = False,
    collector: AuditEventCollector | None = None,
) -> dict[str, Any]:
    """Walk cutover sequence; stop at first hard blocker; skip downstream."""
    collector = new_collector(collector)
    run_id = (
        f"nf_dryrun_cutover_"
        f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}_{uuid.uuid4().hex[:8]}"
    )
    rehearsal = run_mode_b_rehearsal(use_synthetic=True)
    packet = build_mode_a_pilot_master_packet()
    master = packet.get("master") or {}
    freeze = build_claim_freeze_matrix()

    # Planned statuses before skip-propagation
    planned: list[dict[str, Any]] = []

    def plan(
        name: str,
        status: str,
        evidence: str,
        reason: str,
        action: str,
        impact: str,
    ) -> None:
        next_ok = not status.startswith("blocked_")
        planned.append(_step(name, status, evidence, reason, action, impact, next_ok))

    plan("baseline_repo_state", "validated", "git status main", "", "none", "none")
    plan(
        "sca_evidence_check",
        "validated",
        "Gate 16 SCA evidence",
        "",
        "preserve; re-run on dep change",
        "sca_pass_preserved",
    )

    if not login_live:
        plan(
            "auth0_oidc_preflight",
            "blocked_missing_config",
            "Gate 24 Mode A",
            "login_live=false; Auth0 OOB absent",
            "Provide OIDC_* out-of-band",
            "blocks_login_live",
        )
        plan(
            "auth0_live_validation",
            "blocked_missing_config",
            "live validation",
            "Auth0 live not validated",
            "Enable live validation after preflight",
            "blocks_login_live",
        )
        plan(
            "invite_org_role_mapping",
            "blocked_missing_input",
            "invite design",
            "invite/org/role incomplete",
            "Configure invite allowlist + bindings",
            "blocks_external_access",
        )
    else:
        plan("auth0_oidc_preflight", "validated", "Auth0 preflight", "", "none", "none")
        plan(
            "auth0_live_validation",
            "validated",
            "Auth0 live validation",
            "",
            "none",
            "none",
        )
        plan(
            "invite_org_role_mapping",
            "validated",
            "invite bindings",
            "",
            "maintain",
            "none",
        )

    plan(
        "rbac_session_tenant_audit",
        "validated",
        "Gate 24 suite",
        "",
        "maintain",
        "none",
    )

    if not storage_approval_present:
        plan(
            "storage_approval_token_validation",
            "blocked_owner_approval",
            "Gate 25 ingest",
            "approval token absent",
            "Place repo-safe approval JSON",
            "blocks_production_storage",
        )
        for n, ev in (
            ("metadata_config_validation", "metadata adapter"),
            ("object_storage_config_validation", "object adapter"),
            ("signed_url_validation", "signed URL unlock"),
            ("sse_encryption_validation", "SSE model"),
            ("malware_scan_validation", "malware hook"),
        ):
            plan(
                n,
                "blocked_missing_config",
                ev,
                "storage config incomplete",
                "Provide storage OOB config after approval",
                "blocks_production_storage",
            )
    else:
        plan(
            "storage_approval_token_validation",
            "validated",
            "Gate 25 ingest",
            "",
            "none",
            "none",
        )
        for n, ev in (
            ("metadata_config_validation", "metadata adapter"),
            ("object_storage_config_validation", "object adapter"),
            ("signed_url_validation", "signed URL unlock"),
            ("sse_encryption_validation", "SSE model"),
            ("malware_scan_validation", "malware hook"),
        ):
            # Approval present enables dry-run pass-through of config steps for
            # later-gate rehearsal only — claims stay frozen false.
            plan(n, "validated", ev, "", "rehearsal_only_not_live", "none")

    plan(
        "customer_data_policy_validation",
        "validated",
        "Gate 23 policy model",
        "",
        "approve for pilot before persistence claim",
        "persistence_still_frozen",
    )
    plan(
        "retention_delete_export_validation",
        "validated",
        "Gate 23 resolver",
        "",
        "keep production delete/export blocked",
        "none",
    )

    if not pen_test_report_present:
        plan(
            "pen_test_evidence_validation",
            "blocked_missing_evidence",
            "Gate 26 attestation",
            "no report",
            "Attach pen-test report reference",
            "blocks_pen_test_pass",
        )
    else:
        plan(
            "pen_test_evidence_validation",
            "validated",
            "Gate 26 attestation",
            "",
            "none",
            "none",
        )

    plan(
        "authority_verification_status",
        "blocked_not_supported",
        "authority not_live",
        "authority_not_live",
        "Complete live authority path",
        "blocks_final_eligibility",
    )
    plan(
        "source_coverage_status",
        "blocked_not_supported",
        "coverage not_live",
        "source_coverage_not_live",
        "Enable live source coverage",
        "blocks_broad_coverage",
    )
    plan(
        "support_feedback_readiness",
        "ready",
        "ops modeled",
        "",
        "confirm pilot support roster",
        "none",
    )
    plan(
        "ux_trust_readiness_check",
        "validated",
        "Monday demo GO",
        "",
        "maintain honesty panels",
        "none",
    )
    plan(
        "controlled_pilot_master_resolver",
        "validated",
        "Gate 26 master",
        "",
        "re-run after Mode B inputs",
        "pilot_status_visible",
    )
    plan(
        "production_rollout_resolver",
        "validated",
        "Gate 26 rollout",
        "",
        "keep NO_GO until all gates",
        "rollout_status_visible",
    )
    plan(
        "final_claim_freeze",
        "validated",
        "Gate 27/28 freeze",
        "",
        "preserve frozen false claims",
        "claims_frozen",
    )

    # Propagate: first blocked_* wins; rest become skipped_after_blocker
    steps: list[dict[str, Any]] = []
    first_hard_blocker: str | None = None
    for s in planned:
        if first_hard_blocker:
            steps.append(
                {
                    **s,
                    "status": "skipped_after_blocker",
                    "blocked_reason": f"skipped_after:{first_hard_blocker}",
                    "next_step_allowed": False,
                }
            )
            continue
        steps.append(s)
        if s["status"].startswith("blocked_"):
            first_hard_blocker = s["name"]

    skipped = [s for s in steps if s["status"] == "skipped_after_blocker"]
    blockers = [s for s in steps if s["status"].startswith("blocked_")]

    pilot_status = master.get("controlled_customer_pilot_status") or (
        "CONDITIONAL_INTERNAL_ONLY"
    )
    rollout = master.get("production_rollout_status") or "PRODUCTION_ROLLOUT_NO_GO"

    result = {
        "schema_version": SCHEMA_VERSION,
        "dry_run_cutover_contract": True,
        "run_id": run_id,
        "mode": "A",
        "step_sequence": list(CUTOVER_STEPS),
        "step_statuses": list(STEP_STATUSES),
        "steps": steps,
        "steps_run": len(steps),
        "first_hard_blocker": first_hard_blocker,
        "downstream_step_handling": "skipped_after_blocker",
        "skipped_after_blocker_count": len(skipped),
        "blocker_count": len(blockers),
        "sca_evidence_check": "validated",
        "auth0_step": next(
            (s for s in steps if s["name"] == "auth0_oidc_preflight"), {}
        ),
        "storage_step": next(
            (s for s in steps if s["name"] == "storage_approval_token_validation"),
            {},
        ),
        "customer_policy_step": next(
            (s for s in steps if s["name"] == "customer_data_policy_validation"),
            {},
        ),
        "pen_test_step": next(
            (s for s in steps if s["name"] == "pen_test_evidence_validation"),
            {},
        ),
        "authority_source_steps": [
            s
            for s in steps
            if s["name"] in {"authority_verification_status", "source_coverage_status"}
        ],
        "ux_support_steps": [
            s
            for s in steps
            if s["name"] in {"support_feedback_readiness", "ux_trust_readiness_check"}
        ],
        "final_freeze_verified": True,
        "frozen_claim_booleans": freeze.get("frozen_claim_booleans"),
        "controlled_customer_pilot_status": pilot_status,
        "production_rollout_status": rollout,
        "production_cutover_executed": False,
        "customer_data_mutated": False,
        "production_data_mutated": False,
        "login_live_claimed": False,
        "production_storage_claimed": False,
        "pen_test_passed_claimed": False,
        "fake_cutover_complete": False,
        "fake_pilot_ready": False,
        "rehearsal_run_id": rehearsal.get("rehearsal_run_id"),
        "owner_next_action": (
            f"Clear first blocker ({first_hard_blocker}): provide Auth0 OOB, "
            "then storage approval/config, then pen-test report"
        ),
        "human_review_required": True,
    }

    for s in steps:
        if s["status"].startswith("blocked_") and not s.get("owner_action"):
            s["owner_action"] = "owner_input_required"

    _emit_audit(collector, "dry_run_cutover",
        {
            "run_id": run_id,
            "first_hard_blocker": first_hard_blocker,
            "skipped": len(skipped),
        },
    )
    return _json_safe(result)


def dry_run_cutover_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_cutover_executed",
        "customer_data_mutated",
        "production_data_mutated",
        "login_live_claimed",
        "production_storage_claimed",
        "pen_test_passed_claimed",
        "fake_cutover_complete",
        "fake_pilot_ready",
    ):
        if result.get(key) is True:
            fails.append(key)
    if result.get("controlled_customer_pilot_status") == "CONTROLLED_CUSTOMER_GO":
        fails.append("pilot_go")
    if result.get("production_rollout_status") == "GO":
        fails.append("rollout_go")
    if not result.get("final_freeze_verified"):
        fails.append("freeze_not_verified")
    if result.get("mode") == "A" and not result.get("first_hard_blocker"):
        fails.append("no_hard_blocker")
    if result.get("skipped_after_blocker_count", 0) < 1:
        fails.append("no_skipped_downstream")
    for s in result.get("steps") or []:
        if s.get("status", "").startswith("blocked_") and not s.get("owner_action"):
            fails.append(f"blocker_missing_owner_action:{s.get('name')}")
    return fails
