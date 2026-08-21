"""Customer data policy contract and classifications (Block 51)."""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_customer_data_policy_v1"

DATA_CLASSIFICATIONS = (
    "public_grant_source",
    "public_opportunity_metadata",
    "organization_profile",
    "tribal_recognition_evidence",
    "authority_evidence",
    "grant_application_evidence",
    "uploaded_attachment",
    "draft_content",
    "review_note",
    "audit_event",
    "system_metadata",
    "sensitive_customer_data",
    "legal_or_governance_document",
    "unknown",
)

STORAGE_MODES = (
    "not_stored",
    "local_dev_only",
    "fixture_only",
    "production_metadata_only",
    "production_object_storage",
    "external_source_reference",
    "blocked",
    "unknown",
)

POLICY_STATUSES = (
    "not_started",
    "policy_required",
    "partial",
    "approved_for_internal_demo",
    "approved_for_controlled_pilot",
    "approved_for_production",
    "blocked",
    "unknown",
)

# Stricter classifications always require elevated handling
STRICT_CLASSIFICATIONS = frozenset(
    {
        "sensitive_customer_data",
        "legal_or_governance_document",
        "authority_evidence",
        "tribal_recognition_evidence",
        "grant_application_evidence",
        "uploaded_attachment",
        "unknown",
    }
)

_AUDIT: list[dict[str, Any]] = []


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _emit_audit(event: str, detail: dict[str, Any]) -> None:
    _AUDIT.append({"event": event, **detail})


def build_customer_data_policy_contract(
    *,
    organization_profile_id: str = "org_demo",
    policy_status: str = "policy_required",
    ai_training_consent: bool | None = None,
) -> dict[str, Any]:
    # Default AI training consent is always false unless explicitly True
    consent = False if ai_training_consent is None else bool(ai_training_consent)
    permitted = [
        "not_stored",
        "local_dev_only",
        "fixture_only",
        "external_source_reference",
    ]
    prohibited = [
        "production_object_storage",
        "production_metadata_only",
        "blocked",
        "unknown",
    ]
    if policy_status not in {
        "approved_for_controlled_pilot",
        "approved_for_production",
    }:
        # production modes stay prohibited until approved policy
        pass
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "organization_profile_id": organization_profile_id,
            "policy_status": policy_status
            if policy_status in POLICY_STATUSES
            else "unknown",
            "data_classifications": list(DATA_CLASSIFICATIONS),
            "storage_modes": list(STORAGE_MODES),
            "permitted_storage_modes": permitted,
            "prohibited_storage_modes": prohibited,
            "ai_training_consent": consent,
            "ai_training_consent_default": False,
            "export_rights": "pending_policy",
            "deletion_rights": "pending_policy",
            "retention_requirement": "policy_not_set",
            "legal_hold_support_status": "unsupported",
            "human_operator_approval_required": True,
            "customer_data_policy_production_claimed": False,
            "legal_compliance_claimed": False,
            "customer_data_persistence_claimed": False,
            "human_review_required": True,
        }
    )


def classify_data_item(
    *,
    classification: str,
    proposed_storage_mode: str = "local_dev_only",
) -> dict[str, Any]:
    cls = classification if classification in DATA_CLASSIFICATIONS else "unknown"
    mode = (
        proposed_storage_mode if proposed_storage_mode in STORAGE_MODES else "unknown"
    )
    strict = cls in STRICT_CLASSIFICATIONS
    blocked = False
    reasons: list[str] = []
    if cls == "unknown":
        blocked = True
        reasons.append("unknown_classification")
    if mode in {"production_object_storage", "production_metadata_only"}:
        blocked = True
        reasons.append("production_storage_mode_without_approved_policy")
    if mode == "unknown":
        blocked = True
        reasons.append("unknown_storage_mode")
    if strict and mode not in {
        "local_dev_only",
        "fixture_only",
        "not_stored",
        "blocked",
    }:
        blocked = True
        reasons.append("strict_classification_requires_elevated_handling")
    if blocked:
        _emit_audit(
            "customer_data_policy_violation",
            {
                "classification": cls,
                "proposed_storage_mode": mode,
                "reasons": reasons,
            },
        )
    return _json_safe(
        {
            "classification": cls,
            "proposed_storage_mode": mode,
            "strict_handling_required": strict,
            "allowed": not blocked,
            "blocked": blocked,
            "reasons": reasons,
        }
    )


def resolve_customer_persistence(
    *,
    policy: dict[str, Any] | None = None,
    login_live: bool = False,
    production_storage_ready: bool = False,
    tenant_boundary_ready: bool = True,
    audit_ready: bool = True,
    customer_data_policy_approved: bool = False,
) -> dict[str, Any]:
    p = policy or build_customer_data_policy_contract()
    missing: list[str] = []
    if p.get("policy_status") not in {
        "approved_for_controlled_pilot",
        "approved_for_production",
    }:
        missing.append("policy_not_approved")
    if not customer_data_policy_approved:
        missing.append("customer_data_policy_not_approved")
    if not login_live:
        missing.append("login_not_live")
    if not production_storage_ready:
        missing.append("production_storage_not_ready")
    if not tenant_boundary_ready:
        missing.append("tenant_boundary")
    if not audit_ready:
        missing.append("audit")
    if (
        p.get("ai_training_consent") is True
        and p.get("ai_training_consent_default") is False
    ):
        # Consent can be true only if explicitly set — still does not unlock persistence alone
        pass
    if p.get("legal_hold_support_status") == "unsupported":
        # Does not alone block persistence but blocks legal compliance claim
        pass

    return _json_safe(
        {
            "schema_version": "nf_customer_persistence_resolver_v1",
            "customer_data_persistence_claimed": False,
            "customer_data_policy_production_claimed": False,
            "legal_compliance_claimed": False,
            "missing_gates": missing,
            "ai_training_consent": bool(p.get("ai_training_consent")),
            "ai_training_consent_default": False,
            "next_safe_action": (
                "Approve org customer data policy; keep AI training consent false; "
                "complete auth + production storage + tenant + audit before persistence"
            ),
            "human_review_required": True,
        }
    )


def customer_data_policy_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    for key in (
        "customer_data_persistence_claimed",
        "customer_data_policy_production_claimed",
        "legal_compliance_claimed",
    ):
        if result.get(key) is True:
            fails.append(key)
    if result.get("ai_training_consent_default") is not False:
        fails.append("ai_training_default_not_false")
    return fails


def get_customer_data_policy_audit_events() -> list[dict[str, Any]]:
    return list(_AUDIT)


def clear_customer_data_policy_audit_for_tests() -> None:
    _AUDIT.clear()
