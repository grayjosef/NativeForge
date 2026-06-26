"""M5/M8: publish + auto-publish queue gate (kill-switch halts all)."""

from __future__ import annotations

from dataclasses import dataclass

from nativeforge.db.models import NfActivationState


class ActivationPublishHaltedError(PermissionError):
    """Raised when kill-switch or flags block publish/queue operations."""


@dataclass(frozen=True, slots=True)
class PublishGateStatus:
    publish_permitted: bool
    auto_publish_queue_permitted: bool
    live_attribution_permitted: bool
    kill_switch_engaged: bool
    halt_reason: str | None


def evaluate_publish_gate(state: NfActivationState) -> PublishGateStatus:
    if state.kill_switch_engaged:
        return PublishGateStatus(
            publish_permitted=False,
            auto_publish_queue_permitted=False,
            live_attribution_permitted=False,
            kill_switch_engaged=True,
            halt_reason="kill_switch_engaged",
        )
    return PublishGateStatus(
        publish_permitted=state.live_publish_enabled,
        auto_publish_queue_permitted=state.auto_publish_enabled,
        live_attribution_permitted=state.live_attribution_enabled,
        kill_switch_engaged=False,
        halt_reason=None,
    )


def assert_live_publish_permitted(state: NfActivationState) -> None:
    gate = evaluate_publish_gate(state)
    if not gate.publish_permitted:
        reason = gate.halt_reason or "live_publish_disabled"
        raise ActivationPublishHaltedError(reason)


def assert_auto_publish_queue_permitted(state: NfActivationState) -> None:
    gate = evaluate_publish_gate(state)
    if not gate.auto_publish_queue_permitted:
        reason = gate.halt_reason or "auto_publish_disabled"
        raise ActivationPublishHaltedError(reason)
