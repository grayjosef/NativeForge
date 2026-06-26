"""M8: governed activation dispatcher (activation:toggle, policy:change)."""

from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy.orm import Session

from nativeforge.domain.enums import ActivationToggleKey, GovernedActionKind
from nativeforge.services.activation_principal_service import (
    ActivationPrincipal,
    assert_governed_action_permitted,
)
from nativeforge.services.activation_state_service import (
    apply_auto_publish_policy_enable,
    apply_flag_toggle,
    apply_kill_switch,
)

SCHEMA_VERSION = "nf_governed_activation_dispatcher_v1"

HIGH_RISK_ENABLES = frozenset(
    {
        ActivationToggleKey.live_publish,
        ActivationToggleKey.auto_publish,
    }
)


class GovernedActivationValidationError(ValueError):
    """Invalid governed activation request."""


def dispatch_governed_activation_action(
    session: Session,
    *,
    organization_id: uuid.UUID,
    is_demo: bool,
    org_type: str,
    principal: ActivationPrincipal,
    governed_action: GovernedActionKind,
    toggle: ActivationToggleKey,
    value: bool,
    reason: str | None = None,
    config_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    assert_governed_action_permitted(
        principal=principal,
        governed_action=governed_action.value,
    )

    if toggle == ActivationToggleKey.kill_switch:
        if governed_action != GovernedActionKind.activation_toggle:
            raise GovernedActivationValidationError(
                "kill_switch must use activation:toggle"
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "governed_action": governed_action.value,
            "toggle": toggle.value,
            "activation_state": apply_kill_switch(
                session,
                organization_id=organization_id,
                is_demo=is_demo,
                org_type=org_type,
                principal=principal,
                engaged=value,
            ),
        }

    if governed_action == GovernedActionKind.policy_change:
        if toggle != ActivationToggleKey.auto_publish or not value:
            raise GovernedActivationValidationError(
                "policy:change only supports auto_publish enable"
            )
        if not reason or not reason.strip():
            raise GovernedActivationValidationError(
                "reason required to enable auto_publish via policy:change"
            )
        return {
            "schema_version": SCHEMA_VERSION,
            "governed_action": governed_action.value,
            "toggle": toggle.value,
            "activation_state": apply_auto_publish_policy_enable(
                session,
                organization_id=organization_id,
                is_demo=is_demo,
                org_type=org_type,
                principal=principal,
                reason=reason.strip(),
                config_payload=config_payload,
            ),
        }

    if governed_action != GovernedActionKind.activation_toggle:
        raise GovernedActivationValidationError(
            f"unsupported governed_action {governed_action.value!r}"
        )

    if toggle in HIGH_RISK_ENABLES and value:
        if not reason or not reason.strip():
            raise GovernedActivationValidationError(
                f"reason required to enable {toggle.value}"
            )

    if toggle == ActivationToggleKey.auto_publish and value:
        raise GovernedActivationValidationError(
            "auto_publish enable must use policy:change"
        )

    return {
        "schema_version": SCHEMA_VERSION,
        "governed_action": governed_action.value,
        "toggle": toggle.value,
        "activation_state": apply_flag_toggle(
            session,
            organization_id=organization_id,
            is_demo=is_demo,
            org_type=org_type,
            principal=principal,
            flag=toggle.value,
            enabled=value,
            reason=reason.strip() if reason else None,
        ),
    }


def build_governed_activation_dispatcher_contract() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "actions": [
            GovernedActionKind.activation_toggle.value,
            GovernedActionKind.policy_change.value,
        ],
        "agent_denied": True,
        "high_risk_requires_reason": sorted(k.value for k in HIGH_RISK_ENABLES),
        "kill_switch_no_confirm": True,
        "preview_only": False,
    }
