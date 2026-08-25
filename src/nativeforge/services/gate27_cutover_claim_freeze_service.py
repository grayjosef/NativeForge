"""Production cutover checklist + final claim freeze (Block 60 / Gate 27)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.audit_event_collector_service import (
    AuditEventCollector,
    new_collector,
)
from nativeforge.services.gate26_controlled_pilot_master_service import (
    build_mode_a_pilot_master_packet,
)
from nativeforge.services.gate27_owner_unlock_packet_service import (
    build_owner_unlock_packet,
)

SCHEMA_VERSION = "nf_gate27_cutover_claim_freeze_v1"

CHECKLIST_STATUSES = (
    "blocked",
    "ready_for_owner_input",
    "ready_for_validation",
    "validated",
    "ready_for_owner_review",
    "ready_for_limited_external_validation",
    "controlled_customer_go",
    "production_rollout_no_go",
    "production_rollout_ready_for_review",
)

def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _emit_audit(
    collector: AuditEventCollector, event: str, detail: dict[str, Any]
) -> None:
    collector.record(event, detail)


def _item(name: str, status: str, evidence: str, unlocks: str) -> dict[str, Any]:
    st = status if status in CHECKLIST_STATUSES else "blocked"
    return {
        "name": name,
        "status": st,
        "evidence_ref": evidence,
        "unlocks_with": unlocks,
    }


def build_production_cutover_checklist(
    *,
    unlock: dict[str, Any] | None = None,
    master: dict[str, Any] | None = None,
) -> dict[str, Any]:
    u = unlock or build_owner_unlock_packet()
    packet = master or build_mode_a_pilot_master_packet()
    m = packet.get("master") if isinstance(packet, dict) and "master" in packet else (
        packet or {}
    )

    auth = [
        _item(
            "Auth0 configured",
            "ready_for_owner_input",
            "Gate 24 Mode A",
            "OIDC OOB",
        ),
        _item(
            "Live validation passed",
            "blocked",
            "auth validation run",
            "Mode B live",
        ),
        _item("Login live", "blocked", "login_live claim", "full Auth0 gates"),
        _item("Production auth", "blocked", "production_auth claim", "live + RBAC"),
        _item(
            "Invite/org/role mapping",
            "ready_for_owner_input",
            "invite design",
            "owner config",
        ),
        _item("RBAC/tenant/session audits", "validated", "Gate 24 suite", "maintain"),
    ]
    storage = [
        _item(
            "Approval token valid",
            "ready_for_owner_input",
            "Gate 25 ingest",
            "repo-safe token",
        ),
        _item("Metadata config validated", "blocked", "metadata adapter", "OOB URL"),
        _item(
            "Object storage validated",
            "blocked",
            "object adapter",
            "bucket/endpoint",
        ),
        _item(
            "Signed URLs validated",
            "blocked",
            "signed URL unlock",
            "approval+config",
        ),
        _item(
            "SSE/malware validated",
            "blocked",
            "Gate 25 gates",
            "SSE+malware config",
        ),
        _item(
            "Retention/delete/export linked",
            "validated",
            "Gate 23",
            "policy approval",
        ),
        _item("Customer persistence", "blocked", "persistence resolver", "all gates"),
    ]
    security = [
        _item(
            "SCA status",
            "validated",
            "Gate 16 evidence",
            "preserve / re-run on dep change",
        ),
        _item(
            "Pen-test evidence",
            "ready_for_owner_input",
            "Gate 26 attestation",
            "report ref",
        ),
        _item(
            "Critical/high findings",
            "blocked",
            "no report",
            "pen-test + remediate",
        ),
        _item("Remediation/retest", "blocked", "Gate 26", "close findings"),
        _item("Security exceptions", "blocked", "none", "owner approval only"),
    ]
    product = [
        _item("Authority verification", "blocked", "not_live", "live authority path"),
        _item("Source coverage", "blocked", "not_live", "live coverage"),
        _item("Evidence lifecycle", "validated", "local/dev model", "prod storage"),
        _item("Package readiness", "validated", "demo packs", "customer persistence"),
        _item(
            "Final export boundaries",
            "validated",
            "Gate 23 blocked",
            "keep blocked",
        ),
        _item(
            "Proposal drafting boundaries",
            "validated",
            "honesty panel",
            "keep NOT_SUPPORTED",
        ),
    ]
    pilot_ops = [
        _item(
            "Invite readiness",
            "ready_for_owner_input",
            "invite design",
            "allowlist",
        ),
        _item("Support readiness", "validated", "operator support", "maintain"),
        _item("Operator review", "validated", "SC demo panels", "maintain"),
        _item("Feedback path", "validated", "modeled", "customer pilot"),
        _item(
            "Customer issue triage",
            "ready_for_owner_input",
            "ops design",
            "pilot ops",
        ),
    ]
    ux = [
        _item("Buyer-grade readiness", "validated", "Monday demo GO", "maintain"),
        _item(
            "Trust/evidence/blocker clarity",
            "validated",
            "claim panels",
            "maintain",
        ),
        _item("No fake production language", "validated", "claim freeze", "enforce"),
    ]

    pilot_status = (
        m.get("controlled_customer_pilot_status") or "CONDITIONAL_INTERNAL_ONLY"
    )
    rollout = m.get("production_rollout_status") or "PRODUCTION_ROLLOUT_NO_GO"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "production_cutover_checklist": True,
            "controlled_pilot_checklist": True,
            "production_rollout_checklist": True,
            "sections": {
                "auth": auth,
                "storage": storage,
                "security": security,
                "product": product,
                "pilot_ops": pilot_ops,
                "ux": ux,
            },
            "checklist_statuses": list(CHECKLIST_STATUSES),
            "mode": u.get("mode"),
            "controlled_customer_pilot_status": pilot_status,
            "production_rollout_status": rollout,
            "unlock_missing": u.get("missing_owner_inputs") or [],
        }
    )


def build_claim_freeze_matrix(
    *,
    unlock: dict[str, Any] | None = None,
    checklist: dict[str, Any] | None = None,
    collector: AuditEventCollector | None = None,
) -> dict[str, Any]:
    collector = new_collector(collector)
    u = unlock or build_owner_unlock_packet()
    c = checklist or build_production_cutover_checklist(unlock=u)

    allowed = [
        {
            "claim": "monday_demo_internal_go",
            "evidence": "SC demo smoke + staging verify",
            "validation": "Playwright sc_customer_demo.smoke",
        },
        {
            "claim": "conditional_internal_only",
            "evidence": "Gate 26 pilot master",
            "validation": "resolve_controlled_pilot_master Mode A",
        },
        {
            "claim": "owner_unlock_packet_exists",
            "evidence": "Gate 27 Block 59",
            "validation": "build_owner_unlock_packet",
        },
        {
            "claim": "cutover_checklist_exists",
            "evidence": "Gate 27 Block 60",
            "validation": "build_production_cutover_checklist",
        },
        {
            "claim": "sca_gate16_pass_preserved",
            "evidence": "Gate 16 SCA artifacts",
            "validation": "no dependency churn this gate",
        },
        {
            "claim": "ai_training_consent_default_false",
            "evidence": "Gate 23 policy",
            "validation": "customer_data_policy_service",
        },
    ]
    conditional = [
        {
            "claim": "mode_b_ready",
            "evidence": "complete owner packet + OOB flags",
            "validation": "owner unlock packet mode_b_ready",
            "note": "ready ≠ GO",
        },
        {
            "claim": "ready_for_owner_review",
            "evidence": "all live gates + invite pending",
            "validation": "pilot master READY_FOR_OWNER_REVIEW",
        },
    ]
    forbidden = [
        {
            "claim": "login_live",
            "missing_evidence": "Auth0 live validation",
            "blocked_by": "auth0 incomplete",
        },
        {
            "claim": "production_auth",
            "missing_evidence": "production auth validation",
            "blocked_by": "login_live=false",
        },
        {
            "claim": "production_storage",
            "missing_evidence": "approval+config+SSE+malware validation",
            "blocked_by": "storage Mode A",
        },
        {
            "claim": "customer_persistence",
            "missing_evidence": "policy+auth+storage+tenant+audit",
            "blocked_by": "persistence resolver",
        },
        {
            "claim": "pen_test_passed",
            "missing_evidence": "report+scope+closed critical/high",
            "blocked_by": "no_report",
        },
        {
            "claim": "controlled_customer_pilot_GO",
            "missing_evidence": "all hard gates",
            "blocked_by": c.get("controlled_customer_pilot_status"),
        },
        {
            "claim": "production_rollout_GO",
            "missing_evidence": "all production gates",
            "blocked_by": c.get("production_rollout_status"),
        },
        {
            "claim": "production_ready",
            "missing_evidence": "full cutover",
            "blocked_by": "PRODUCTION_ROLLOUT_NO_GO",
        },
        {
            "claim": "mode_b_executed",
            "missing_evidence": "owner inputs",
            "blocked_by": u.get("mode"),
        },
    ]

    # Freeze booleans
    freeze = {
        "login_live": False,
        "production_auth": False,
        "production_storage": False,
        "customer_persistence": False,
        "pen_test_passed": False,
        "controlled_customer_pilot_GO": False,
        "production_rollout_GO": False,
    }

    owner_actions = [
        {
            "action": "Provide Auth0/OIDC OOB config + secrets",
            "unlocks": "login_live path",
            "proves_with": "Gate 24 Mode B validation",
        },
        {
            "action": "Place repo-safe storage approval + OOB storage config",
            "unlocks": "production_storage path",
            "proves_with": "Gate 25 Mode B validators",
        },
        {
            "action": "Attach pen-test report reference + remediate/retest",
            "unlocks": "pen_test_passed path",
            "proves_with": "Gate 26 attestation",
        },
        {
            "action": "Re-run Gate 26 pilot master after Mode B inputs",
            "unlocks": "controlled pilot status change",
            "proves_with": "resolve_controlled_pilot_master",
        },
    ]

    _emit_audit(collector, "claim_freeze_resolve",
        {
            "allowed": len(allowed),
            "forbidden": len(forbidden),
            "pilot": c.get("controlled_customer_pilot_status"),
        },
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "claim_freeze_contract": True,
            "allowed_claims": allowed,
            "conditional_claims": conditional,
            "forbidden_claims": forbidden,
            "required_evidence_map": {
                a["claim"]: a["evidence"] for a in allowed
            },
            "required_validation_map": {
                a["claim"]: a["validation"] for a in allowed
            },
            "owner_next_action_matrix": owner_actions,
            "frozen_claim_booleans": freeze,
            "controlled_customer_pilot_status": c.get(
                "controlled_customer_pilot_status"
            ),
            "production_rollout_status": c.get("production_rollout_status"),
            "login_live_claimed": False,
            "production_storage_claimed": False,
            "customer_persistence_claimed": False,
            "pen_test_passed_claimed": False,
            "fake_production_ready": False,
            "fake_pilot_ready": False,
            "fake_secure_badge": False,
            "human_review_required": True,
        }
    )


def cutover_claim_freeze_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "login_live_claimed",
        "production_storage_claimed",
        "customer_persistence_claimed",
        "pen_test_passed_claimed",
        "fake_production_ready",
        "fake_pilot_ready",
        "fake_secure_badge",
    ):
        if result.get(key) is True:
            fails.append(key)
    freeze = result.get("frozen_claim_booleans") or {}
    for k, v in freeze.items():
        if v is True:
            fails.append(f"freeze_{k}")
    if result.get("controlled_customer_pilot_status") == "CONTROLLED_CUSTOMER_GO":
        fails.append("pilot_go")
    if result.get("production_rollout_status") == "GO":
        fails.append("rollout_go")
    # Every allowed claim must have evidence
    for a in result.get("allowed_claims") or []:
        if not a.get("evidence") or not a.get("validation"):
            fails.append(f"allowed_missing_evidence:{a.get('claim')}")
    for f in result.get("forbidden_claims") or []:
        if not f.get("missing_evidence"):
            fails.append(f"forbidden_missing_evidence:{f.get('claim')}")
    return fails
