"""Operator readiness contract + go/no-go matrix (Campaign Block 22)."""

from __future__ import annotations

import hashlib
import json
import subprocess
from typing import Any

SCHEMA_VERSION = "nf_operator_readiness_contract_v1"

READINESS_STATUSES = frozenset(
    {
        "demo_ready",
        "operator_ready",
        "needs_review",
        "blocked",
        "not_production_ready",
        "not_supported",
    }
)

GO_NO_GO_TARGETS = (
    "monday_demo",
    "internal_pilot",
    "controlled_customer_pilot",
    "production_rollout",
    "collaboration_rollout",
    "upload_persistence_rollout",
    "live_source_rollout",
    "controlled_drafting_rollout",
    "export_rollout",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def make_operator_readiness_id(route: str, head: str) -> str:
    raw = f"or::{route}::{head}".encode()
    return f"or_{hashlib.sha256(raw).hexdigest()[:16]}"


def _git_short_head() -> str:
    try:
        return (
            subprocess.check_output(
                ["git", "rev-parse", "--short", "HEAD"],
                stderr=subprocess.DEVNULL,
                text=True,
            ).strip()
            or "unknown"
        )
    except (OSError, subprocess.CalledProcessError):
        return "unknown"


def build_go_no_go_matrix() -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    def row(
        target: str,
        status: str,
        *,
        blockers: list[str],
        validation: list[str],
        allowed: list[str],
        forbidden: list[str],
        next_action: str,
        role: str,
        evidence: str,
    ) -> dict[str, Any]:
        return {
            "target": target,
            "status": status,
            "blockers": blockers,
            "required_validation": validation,
            "allowed_claims": allowed,
            "forbidden_claims": forbidden,
            "next_action": next_action,
            "owner_action_role": role,
            "evidence_reference": evidence,
        }

    rows.append(
        row(
            "monday_demo",
            "GO",
            blockers=[],
            validation=["sc_monday staging", "Playwright sc_customer_demo"],
            allowed=[
                "Fixture-backed multi-org pilot packaging",
                "Package export preview (not final)",
                "Forms/attachments mapping v0",
            ],
            forbidden=["submission-ready", "final export", "pen-test passed"],
            next_action="Run demo route and keep claim boundaries visible",
            role="operator",
            evidence="/?view=sc_customer_demo",
        )
    )
    rows.append(
        row(
            "internal_pilot",
            "CONDITIONAL_GO",
            blockers=[
                "full suite not green-claimed",
                "upload persistence planned only",
            ],
            validation=["Block 17–22 smokes", "operator checklist review"],
            allowed=["Internal operator review of SC cohort fixtures"],
            forbidden=["production multi-tenant", "customer login live"],
            next_action="Use fixture cohort; no production customer data",
            role="operator",
            evidence="docs/operations/13_HANDOFF_LATEST.md",
        )
    )
    rows.append(
        row(
            "controlled_customer_pilot",
            "NO_GO",
            blockers=[
                "customer login not implemented",
                "durable upload storage not validated",
                "production multi-tenant not claimed",
            ],
            validation=[
                "auth path",
                "validated_persistent storage",
                "tenant isolation",
            ],
            allowed=["Planning language only"],
            forbidden=["customers can log in", "uploads durable"],
            next_action="Approve storage proposal + auth plan before pilot",
            role="owner",
            evidence="docs/operations/161_EVIDENCE_UPLOAD_STORAGE_PROPOSAL.md",
        )
    )
    rows.append(
        row(
            "production_rollout",
            "NO_GO",
            blockers=[
                "production_ready_claimed must remain false",
                "pen-test not passed",
                "SCA/dependency scan missing",
            ],
            validation=["external pen-test", "SCA", "prod authz/CORS review"],
            allowed=["Production readiness blockers visible"],
            forbidden=["production-ready", "pen-test passed"],
            next_action="Engage external pen-test after upload/auth foundations",
            role="owner",
            evidence="docs/operations/152_PEN_TEST_READINESS_REPORT.md",
        )
    )
    rows.append(
        row(
            "collaboration_rollout",
            "NO_GO",
            blockers=["feature dark/OFF", "opt-in not collected", "no data sharing"],
            validation=["consent workflow", "sovereignty review"],
            allowed=["Collaboration dark-launch foundation"],
            forbidden=["partner matching live", "data sharing"],
            next_action="Keep collaboration OFF until explicit enablement",
            role="operator",
            evidence="collaboration_dark_launch surface",
        )
    )
    rows.append(
        row(
            "upload_persistence_rollout",
            "NO_GO",
            blockers=["storage mode fixture/planned", "migrations not approved"],
            validation=["approved migration", "malware scan plan", "retention policy"],
            allowed=["Evidence intake contract + storage proposal"],
            forbidden=["uploaded files stored", "customer uploads durable"],
            next_action="Review and approve storage proposal before implementation",
            role="owner",
            evidence="docs/operations/161_EVIDENCE_UPLOAD_STORAGE_PROPOSAL.md",
        )
    )
    rows.append(
        row(
            "live_source_rollout",
            "NO_GO",
            blockers=["source freshness pilot is fixture-backed"],
            validation=["external live check design", "activation approval"],
            allowed=["Read-only freshness pilot"],
            forbidden=["live ingest"],
            next_action="Keep curated/fixture labels visible",
            role="operator",
            evidence="source_freshness_pilot",
        )
    )
    rows.append(
        row(
            "controlled_drafting_rollout",
            "CONDITIONAL_GO",
            blockers=["QA/human review required", "export blocked"],
            validation=["AI governance smoke", "citation checks"],
            allowed=["Evidence-cited controlled drafting v0"],
            forbidden=["complete proposal", "submission-ready"],
            next_action="Keep QA gates hard; no export unlock",
            role="operator",
            evidence="ai_governance surface",
        )
    )
    rows.append(
        row(
            "export_rollout",
            "NO_GO",
            blockers=["export_allowed=false", "final_export_claimed=false"],
            validation=["QA pass + human review + validated evidence"],
            allowed=["Package export preview only"],
            forbidden=["final export", "submission-ready package"],
            next_action="Do not unlock download/final export",
            role="operator",
            evidence="package_export_preview",
        )
    )
    return rows


def build_operator_readiness_contract(
    *,
    route: str = "/?view=sc_customer_demo",
    current_head: str | None = None,
) -> dict[str, Any]:
    head = current_head or _git_short_head()
    matrix = build_go_no_go_matrix()
    blockers = [
        "Durable upload persistence not validated (fixture/planned only)",
        "Production multi-tenant / customer login not claimed",
        "Pen-test not passed",
        "Collaboration dark/OFF",
        "Final export / submission-ready remain false",
    ]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "operator_readiness_id": make_operator_readiness_id(route, head),
            "route": route,
            "current_head": head,
            "required_commands": [
                "source .venv/bin/activate",
                "cd frontend && npm run dev",
                "uvicorn nativeforge.main:app --reload",
            ],
            "smoke_commands": [
                "bash scripts/sc_monday_demo_staging_verify.sh",
                "bash scripts/campaign_block21_smoke_verify.sh",
                "bash scripts/campaign_block22_smoke_verify.sh",
                "bash scripts/sc_monday_playwright_e2e_smoke_verify.sh",
            ],
            "playwright_status": "run_on_gate_closeout",
            "backend_status": "demo_ready",
            "frontend_status": "demo_ready",
            "source_health_status": "fixture_pilot_only",
            "test_posture_reference": (
                "docs/operations/149_CODE_HEALTH_TEST_POSTURE_REPORT.md"
            ),
            "security_posture_reference": (
                "docs/operations/151_SECURITY_POSTURE_INVENTORY.md"
            ),
            "pen_test_readiness_reference": (
                "docs/operations/152_PEN_TEST_READINESS_REPORT.md"
            ),
            "package_readiness_reference": "package_readiness_queue",
            "upload_persistence_status": "fixture_planned_not_persistent",
            "feedback_slack_status": "dry_run_default_not_sent",
            "collaboration_status": "dark_off",
            "multi_org_status": "fixture_cohort_ready",
            "production_readiness_status": "not_production_ready",
            "go_no_go_status": "demo_ready",
            "go_no_go_matrix": matrix,
            "blockers": blockers,
            "operator_next_actions": [
                "Run Monday demo route with claim strip visible",
                "Review evidence intake storage proposal before any migration",
                "Keep collaboration and final export OFF",
            ],
            "customer_next_actions": [
                "Provide missing org evidence when durable upload path is approved",
                "Complete human review of blockers before any submission language",
            ],
            "production_ready_claimed": False,
            "pen_test_passed_claimed": False,
            "upload_persistence_claimed": False,
            "customer_data_persistence_claimed": False,
            "submission_ready_claimed": False,
            "final_export_claimed": False,
            "collaboration_matching_claimed": False,
            "live_customer_login_claimed": False,
            "live_ingest_claimed": False,
        }
    )


def operator_readiness_invariant_failures(contract: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "production_ready_claimed",
        "pen_test_passed_claimed",
        "upload_persistence_claimed",
        "customer_data_persistence_claimed",
        "submission_ready_claimed",
        "final_export_claimed",
        "collaboration_matching_claimed",
        "live_customer_login_claimed",
        "live_ingest_claimed",
    ):
        if contract.get(key) is True:
            fails.append(key)
    if contract.get("production_readiness_status") == "production_ready":
        fails.append("production_status_ready")
    # Production rollout row must not be GO
    for row in contract.get("go_no_go_matrix") or []:
        if row.get("target") == "production_rollout" and row.get("status") == "GO":
            fails.append("production_rollout_go")
        if (
            row.get("target") == "upload_persistence_rollout"
            and row.get("status") == "GO"
        ):
            fails.append("upload_rollout_go")
        if row.get("target") == "collaboration_rollout" and row.get("status") == "GO":
            fails.append("collab_rollout_go")
    return fails
