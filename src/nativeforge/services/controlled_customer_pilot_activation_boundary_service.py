"""Gate 149C: may a controlled customer pilot be activated? Dry run only.

## There is no mutation path, and that is the design

`build_pilot_activation_decision` takes no connection, imports no repository,
and returns `mutation_performed: False` and `rows_written: 0` on every branch
including the permitted one. `mutation_enabled` is derived and reported so a
caller can see that even a clear decision does not activate anything.

Deciding a pilot may start and starting it are different actions with different
owners. Gate 149's survey found that no mechanism exists to record a pilot
activation — no table, no flag, no code path — and this module does not build
one. A switch that exists before its prerequisites do is a switch somebody flips
early.

## The refusal that matters most: bundling

A pilot request that also asks for email delivery, live source monitoring,
object storage or production is refused **as a bundle**, with each bundled
capability named. This is the failure this gate exists to prevent: a pilot that
quietly turned on email because "a pilot obviously needs notifications" would
undo four gates in one sentence.

The bundled request is refused even when every pilot prerequisite is satisfied.
Being allowed to start a pilot is not being allowed to start anything else.

## Deny by default

Every prerequisite must be satisfied. A missing one refuses, an unknown key
offered as an approval refuses, and `production` requested at all refuses
regardless of everything else.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.controlled_customer_pilot_activation_checklist_service import (  # noqa: E501
    LIMITED_GO,
    NO_GO,
    PREREQUISITES,
    build_pilot_activation_checklist,
    checklist_invariant_failures,
)

SCHEMA_VERSION = "nf_controlled_customer_pilot_activation_boundary_v1"

#: The fields a pilot activation approval would need. Declared so its absence
#: is a missing record rather than an undefined concept - the treatment Gates
#: 147 and 148 gave the binding approval and the consent record.
ACTIVATION_APPROVAL_FIELDS: tuple[str, ...] = (
    "organization_id",
    "approved_by",
    "approved_at",
    "pilot_scope",
    "support_contact",
    "rollback_owner",
    "expires_at",
)

#: Capabilities a pilot activation may never carry with it. Requesting one
#: alongside a pilot is refused as a bundle, by name.
UNSAFE_BUNDLE_KEYS: tuple[str, ...] = (
    "source_monitoring_live",
    "activate_source_monitoring",
    "email_delivery",
    "activate_email",
    "send_email",
    "object_store_configured",
    "activate_object_storage",
    "production_rollout",
    "activate_production",
    "go_live",
)

#: Which capability each bundled key would have turned on.
BUNDLE_TARGETS: dict[str, str] = {
    "source_monitoring_live": "source_monitoring_live",
    "activate_source_monitoring": "source_monitoring_live",
    "email_delivery": "email_delivery",
    "activate_email": "email_delivery",
    "send_email": "email_delivery",
    "object_store_configured": "object_store_configured",
    "activate_object_storage": "object_store_configured",
    "production_rollout": "production_rollout",
    "activate_production": "production_rollout",
    "go_live": "production_rollout",
}

BLOCKER_NO_APPROVAL = "no_pilot_activation_approval_supplied"
BLOCKER_BUNDLED = "activation_request_bundled_other_capabilities"
BLOCKER_PRODUCTION = "production_requested_alongside_a_pilot"
BLOCKER_NO_MECHANISM = "no_activation_mechanism_exists_to_record_this"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _approval_shape_failures(approval: Any) -> list[str]:
    if approval is None:
        return ["activation_approval_absent"]
    if not isinstance(approval, dict):
        return ["activation_approval_is_not_a_record"]
    return sorted(
        f"activation_approval_missing_field:{field}"
        for field in ACTIVATION_APPROVAL_FIELDS
        if not str(approval.get(field) or "").strip()
    )


def build_pilot_activation_decision(
    *,
    activation_approval: dict[str, Any] | None = None,
    real_customer_organization_exists: bool | None = None,
    second_person_event_complete: bool | None = None,
    customer_auth_live: bool | None = None,
    verified_operational_binding: bool | None = None,
    consent_boundary_documented: bool | None = None,
    customer_beta_scope_approved: bool | None = None,
    customer_data_write_guard_ready: bool | None = None,
    support_and_rollback_owner: dict[str, Any] | None = None,
    pilot_scope_limitations_documented: bool | None = None,
    internal_demo_beta: str | None = None,
    controlled_customer_beta: str | None = None,
    **requested: Any,
) -> dict[str, Any]:
    """May a pilot be activated? Decides without activating anything.

    `may_activate` is derived from the checklist plus this module's own approval
    and bundling checks. It is not a parameter, and there is no argument that
    turns a refusal into a permission.
    """
    checklist = build_pilot_activation_checklist(
        real_customer_organization_exists=real_customer_organization_exists,
        second_person_event_complete=second_person_event_complete,
        customer_auth_live=customer_auth_live,
        verified_operational_binding=verified_operational_binding,
        consent_boundary_documented=consent_boundary_documented,
        customer_beta_scope_approved=customer_beta_scope_approved,
        customer_data_write_guard_ready=customer_data_write_guard_ready,
        support_and_rollback_owner=support_and_rollback_owner,
        pilot_scope_limitations_documented=pilot_scope_limitations_documented,
        internal_demo_beta=internal_demo_beta,
        controlled_customer_beta=controlled_customer_beta,
    )

    approval_failures = _approval_shape_failures(activation_approval)
    approval_present = not approval_failures

    # Anything asking for another capability alongside the pilot. Refused as a
    # bundle even when every prerequisite is satisfied.
    bundled = sorted(
        key
        for key in requested
        if key in UNSAFE_BUNDLE_KEYS and requested.get(key)
    )
    bundled_targets = sorted({BUNDLE_TARGETS[key] for key in bundled})

    blockers: list[str] = [
        f"prerequisite_missing:{name}"
        for name in checklist["prerequisites_missing"]
    ]

    if not approval_present:
        blockers.append(BLOCKER_NO_APPROVAL)
    if bundled:
        blockers.append(BLOCKER_BUNDLED)
    if "production_rollout" in bundled_targets:
        blockers.append(BLOCKER_PRODUCTION)

    # Even a clear decision cannot be recorded, because nothing records it.
    # Reported as a blocker rather than hidden, so "may_activate" can never be
    # read as "has been activated".
    blockers.append(BLOCKER_NO_MECHANISM)

    blockers = sorted(set(blockers))

    # Derived. The mechanism blocker is excluded from this one judgement,
    # because the question "would the prerequisites permit it" is worth being
    # able to answer - and it is reported beside `may_activate`, not instead.
    decision_blockers = [b for b in blockers if b != BLOCKER_NO_MECHANISM]
    prerequisites_would_permit = not decision_blockers

    may_activate = False  # No branch returns true: there is nothing to activate.
    mutation_enabled = False
    approvals_required = sorted(
        {
            *(
                name
                for name in PREREQUISITES
                if name in checklist["prerequisites_missing"]
            ),
            *(["pilot_activation_approval"] if not approval_present else []),
        }
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "dry_run": True,
            # The answer, and the two halves it is made of.
            "may_activate": may_activate,
            "prerequisites_would_permit": prerequisites_would_permit,
            "why_may_activate_is_always_false": (
                "no mechanism exists to record a pilot activation - no table, "
                "no flag, no code path. prerequisites_would_permit answers the "
                "question worth asking; may_activate answers whether anything "
                "could act on it, and nothing can."
            ),
            "mutation_enabled": mutation_enabled,
            "mutation_performed": False,
            "rows_written": 0,
            "connection_supplied": False,
            "blockers": blockers,
            "approvals_required": approvals_required,
            "unsafe_bundled_requests": bundled,
            "unsafe_bundled_targets": bundled_targets,
            "bundling_refused_even_when_prerequisites_are_met": True,
            "activation_approval_supplied": activation_approval is not None,
            "activation_approval_shape_failures": approval_failures,
            "activation_approval_fields_required": list(ACTIVATION_APPROVAL_FIELDS),
            # Carried through from the checklist.
            "controlled_customer_pilot": checklist["controlled_customer_pilot"],
            "internal_demo_beta": checklist["internal_demo_beta"],
            "controlled_customer_beta": checklist["controlled_customer_beta"],
            "production_rollout": NO_GO,
            "prerequisites_missing": checklist["prerequisites_missing"],
            "separately_gated": checklist["separately_gated"],
            "would_unlock": checklist["would_unlock"],
            "would_not_unlock": checklist["would_not_unlock"],
            "next_human_action": checklist["next_human_action"],
            "checklist_invariant_failures": checklist_invariant_failures(checklist),
            "activation_mechanism_exists": False,
            "real_organization_touched": False,
            "leaked_shapes": checklist["leaked_shapes"],
        }
    )


def activation_decision_invariant_failures(decision: dict[str, Any]) -> list[str]:
    """Refuse a decision that activated something, or permitted a bundle."""
    fails: list[str] = []

    if not decision.get("dry_run"):
        fails.append("activation_decision_that_is_not_a_dry_run")
    if decision.get("mutation_performed"):
        fails.append("dry_run_performed_a_mutation")
    if decision.get("rows_written"):
        fails.append("dry_run_wrote_rows")
    if decision.get("connection_supplied"):
        fails.append("dry_run_was_handed_a_connection")
    if decision.get("real_organization_touched"):
        fails.append("dry_run_touched_the_real_organization")
    if decision.get("activation_mechanism_exists"):
        fails.append("an_activation_mechanism_appeared")

    if decision.get("may_activate"):
        fails.append("may_activate_became_true_with_no_mechanism_to_act_on_it")
    if decision.get("mutation_enabled"):
        fails.append("mutation_enabled_on_a_dry_run_only_boundary")

    if decision.get("prerequisites_would_permit") and decision.get(
        "prerequisites_missing"
    ):
        fails.append("would_permit_alongside_missing_prerequisites")
    if decision.get("prerequisites_would_permit") and decision.get(
        "unsafe_bundled_requests"
    ):
        fails.append("would_permit_a_bundled_request")

    if decision.get("controlled_customer_pilot") and decision.get(
        "prerequisites_missing"
    ):
        fails.append("pilot_true_with_missing_prerequisites")

    if decision.get("production_rollout") != NO_GO:
        fails.append("production_rollout_is_not_no_go")

    # A bundled request must always be reported alongside its target, or a
    # reader cannot tell what would have been switched on.
    if decision.get("unsafe_bundled_requests") and not decision.get(
        "unsafe_bundled_targets"
    ):
        fails.append("bundled_request_without_a_named_target")

    for name in decision.get("checklist_invariant_failures") or []:
        fails.append(f"checklist:{name}")
    for name in decision.get("leaked_shapes") or []:
        fails.append(f"leaked:{name}")

    return sorted(set(fails))


#: Re-exported so the verifier and tests name one set of decisions.
DECISION_VALUES: tuple[str, ...] = (LIMITED_GO, NO_GO)
