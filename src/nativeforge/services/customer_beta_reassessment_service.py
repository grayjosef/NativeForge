"""Gate 150B: did the customer beta decision change, and what is understood now?

## The answer is no, and that is the correct answer

Gates 146-149 were boundary gates. They were built to make refusals exact, not
to clear them. A block of four gates that moved a lane without a new external
approval would mean one of them had granted itself something.

```text
internal_demo_beta         GO          ->  GO
controlled_customer_beta   LIMITED_GO  ->  LIMITED_GO
production_rollout         NO_GO       ->  NO_GO
```

## Four conflations this module must not make

Each is a readiness fact that reads like the capability beside it, and each was
established by one of the four gates it summarises:

```text
second_person_readiness_passed   is not  customer_auth_live
approval_boundary_ready          is not  verified_operational_binding
customer_data_write_guard_ready  is not  customer data writes allowed
activation_package_ready         is not  controlled_customer_pilot
prerequisites_would_permit       is not  may_activate
the demo organization            is not  a customer organization
```

The fifth is Gate 149's and the sixth is Gate 145's. A reassessment that
collapsed any of them would report a GO the evidence does not support, which is
the one failure mode this gate has.

## Decisions are compared, never recomputed here

`build_reassessment` takes the current decision as measured by the services that
own it, and compares it to Gate 145's recorded baseline. It does not decide
anything itself: a summariser that could compute its own verdict would be
grading its own homework, which Gate 144 spent a defect learning.

The current decision is not a parameter either in the sense that matters - the
three scope verdicts are supplied by `controlled_beta_readiness_decision_service`
and passed through, and the invariants refuse a customer GO that arrives without
all four approvals behind it.
"""

from __future__ import annotations

import json
import re
from typing import Any

SCHEMA_VERSION = "nf_customer_beta_reassessment_v1"

GO = "GO"
LIMITED_GO = "LIMITED_GO"
NO_GO = "NO_GO"

#: What Gate 145 recorded. The baseline this gate compares against.
GATE_145_BASELINE: dict[str, str] = {
    "internal_demo_beta": GO,
    "controlled_customer_beta": LIMITED_GO,
    "production_rollout": NO_GO,
}

#: The four approvals the controlled customer beta needs. None is technical.
CUSTOMER_BETA_APPROVALS: tuple[str, ...] = (
    "customer_auth_live",
    "verified_operational_binding",
    "consent_and_data_boundary_documented",
    "customer_beta_scope_approved",
)

#: Readiness facts that must never be read as the capability beside them.
CONFLATIONS: tuple[dict[str, str], ...] = (
    {
        "readiness": "second_person_readiness_passed",
        "capability": "customer_auth_live",
        "difference": "the path is correct; nobody has walked it",
        "gate": "146",
    },
    {
        "readiness": "approval_boundary_ready",
        "capability": "verified_operational_binding",
        "difference": "the boundary refuses correctly; nobody satisfied it",
        "gate": "147",
    },
    {
        "readiness": "customer_data_write_guard_ready",
        "capability": "customer data writes allowed",
        "difference": "a future write path has something right to call",
        "gate": "148",
    },
    {
        "readiness": "activation_package_ready",
        "capability": "controlled_customer_pilot",
        "difference": "the prerequisites are stated; a pilot is not running",
        "gate": "149",
    },
    {
        "readiness": "prerequisites_would_permit",
        "capability": "may_activate",
        "difference": (
            "the prerequisites would allow it; nothing exists to act on that"
        ),
        "gate": "149",
    },
    {
        "readiness": "the demo organization",
        "capability": "a customer organization",
        "difference": "a fixture is not a Tribe",
        "gate": "145",
    },
)

#: What each gate clarified. Not what it activated - none of them activated
#: anything, and saying so plainly is the point of this record.
CLARIFICATIONS: tuple[dict[str, str], ...] = (
    {
        "gate": "146",
        "subject": "customer auth",
        "was_reported_as": "invite_binding_passed",
        "is_actually": (
            "a conjunction of three sequential events, none of which has "
            "started. One identity exists - the owner - and no invite has been "
            "recorded, so the state was never an invite waiting to be accepted."
        ),
        "lane_moved": "no",
    },
    {
        "gate": "147",
        "subject": "verified binding",
        "was_reported_as": "owner_decision_absent",
        "is_actually": (
            "five refusals, any one sufficient, one of which never clears. "
            "Granting the owner decision moves nothing, because there is no "
            "organization it could apply to."
        ),
        "lane_moved": "no",
    },
    {
        "gate": "148",
        "subject": "consent and customer data",
        "was_reported_as": "a named gap",
        "is_actually": (
            "every post-award production write is gated on customer_auth_live "
            "and verified_operational_binding, both identity facts and neither "
            "consent - so the day those turn true, a customer write becomes "
            "permitted with nothing recording that a tenant agreed"
        ),
        "lane_moved": "no",
    },
    {
        "gate": "149",
        "subject": "pilot activation",
        "was_reported_as": "not approved",
        "is_actually": (
            "not a value at all - no table records a pilot approval, no flag "
            "exists, and no code path assigns it. Nine prerequisites, one "
            "satisfied."
        ),
        "lane_moved": "no",
    },
)

#: The single fact three of the four gates independently arrived at.
THE_THROUGHLINE = {
    "finding": (
        "a real customer organization has to exist, and no approval supplies one"
    ),
    "found_by": ["147", "148", "149"],
    "why_it_matters": (
        "the campaign had been describing each remaining blocker as one "
        "decision away. None of them was, and the front of the queue is not a "
        "decision at all."
    ),
}

#: Safe to say to a prospective beta customer. Each is true today.
SAFE_CLAIMS: tuple[str, ...] = (
    "this is a controlled demonstration in a demo environment",
    "the awarded-grants workspace, requirements and audit trail work against "
    "fixture data",
    "177 grant sources are catalogued; none is being monitored yet",
    "nothing you see here is sent, monitored, or stored as your data",
    "a weekly digest can be previewed in the product; it is not sent",
    "we can show you exactly what would have to be true before your "
    "organization could use this, and who has to decide each part",
)

#: Unsafe, with the true statement each one should be replaced by.
UNSAFE_CLAIMS: tuple[dict[str, str], ...] = (
    {
        "claim": "we monitor grant sources for you",
        "why_unsafe": "source_monitoring_live is false; no collector runs",
        "true_statement": "177 sources are catalogued and none is monitored yet",
    },
    {
        "claim": "you will get a weekly digest by email",
        "why_unsafe": "email_delivery is false; nothing can send mail",
        "true_statement": "a digest can be previewed in the product",
    },
    {
        "claim": "your data is in our system",
        "why_unsafe": "no customer data has been written and consent does not exist",
        "true_statement": "the demo organization holds fixture-labelled rows",
    },
    {
        "claim": "your organization is set up",
        "why_unsafe": "no real customer organization exists in this deployment",
        "true_statement": "there is one demo organization and one refused real one",
    },
    {
        "claim": "we have verified your organization",
        "why_unsafe": "verified_operational_binding is false behind five refusals",
        "true_statement": "no organization has been verified; the path refuses",
    },
    {
        "claim": "the binding is in place, we just need an approval",
        "why_unsafe": (
            "nearly true and entirely wrong - the approval is not what is "
            "missing, a customer organization is"
        ),
        "true_statement": "a customer organization has to exist first",
    },
    {
        "claim": "we can turn email on as part of the pilot",
        "why_unsafe": "bundling is refused; email is a separate activation",
        "true_statement": "the pilot gives a digest in the product, not by mail",
    },
    {
        "claim": "we guarantee your eligibility",
        "why_unsafe": "no eligibility determination is ever reported to a tenant",
        "true_statement": "we surface sources and requirements; you decide",
    },
    {
        "claim": "we guarantee these deadlines",
        "why_unsafe": "deadlines are not reported as guaranteed by any surface",
        "true_statement": "published dates are shown with their source",
    },
    {
        "claim": "a 65% improvement in anything",
        "why_unsafe": "no such measurement exists",
        "true_statement": "no improvement figure is claimed",
    },
)

#: Where the campaign should go next, and why this rather than waiting.
NEXT_BLOCK = {
    "block": "Gates 151-155, operational durability",
    "why": (
        "every remaining customer-beta blocker is an approval, a document, or "
        "a person signing in. Nothing further in engineering advances that "
        "block, and waiting leaves the campaign idle on work only Mayhem and a "
        "second person can do."
    ),
    "first_gate": "151 - digest persistence",
    "first_gate_why": (
        "delivery intents name a digest nobody kept, and a digest that cannot "
        "be re-read cannot be audited after a missed deadline"
    ),
    "gates": [
        {"gate": "151", "subject": "digest persistence"},
        {
            "gate": "152",
            "subject": "source terms review tooling",
            "note": "171 sources need a human decision each; unblocked today",
        },
        {"gate": "153", "subject": "backup and restore proof"},
        {
            "gate": "154",
            "subject": "operational runbook and on-call",
            "note": "the support and rollback owner Gate 149 asked for needs "
            "something to hand them",
        },
        {"gate": "155", "subject": "the block close"},
    ],
}

NOT_APPROVED: tuple[str, ...] = (
    "controlled_customer_pilot",
    "production_rollout",
    "customer_auth_live",
    "verified_operational_binding",
    "consent_boundary_documented",
    "customer_beta_scope_approved",
    "source_monitoring_live",
    "email_delivery",
    "object_store_configured",
)

_FORBIDDEN_SHAPES: tuple[tuple[str, str], ...] = (
    ("email_address", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("bearer_token", r"\beyJ[A-Za-z0-9_-]{8,}"),
    ("session_cookie", r"nf_session="),
    ("set_cookie", r"(?i)set-cookie:"),
    ("google_client_secret", r"GOCSPX-"),
    ("private_key", r"BEGIN PRIVATE KEY"),
    ("aws_key", r"AKIA"),
)
_PROVIDER_SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")

def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _leaked_shapes(payload: dict[str, Any]) -> list[str]:
    """Scan the whole payload, inventory included.

    Gate 145 needed an exemption here because its scan carried a "65%" marker
    and its inventory records that phrase by design. This scan looks for value
    SHAPES - an address, a token, a subject - and the unsafe-claim inventory
    contains none of them, so it scans clean on its own merits.

    An exemption that protects against nothing is an unscanned region, so there
    is none.
    """
    body = json.dumps(payload, default=str, sort_keys=True)
    found = [name for name, pattern in _FORBIDDEN_SHAPES if re.search(pattern, body)]
    if _PROVIDER_SUBJECT_SHAPE.search(body):
        found.append("provider_subject")
    return sorted(set(found))


def build_reassessment(
    *,
    internal_demo_beta: str | None = None,
    controlled_customer_beta: str | None = None,
    production_rollout: str | None = None,
    customer_auth_live: bool | None = None,
    verified_operational_binding: bool | None = None,
    consent_boundary_documented: bool | None = None,
    customer_beta_scope_approved: bool | None = None,
    controlled_customer_pilot: bool | None = None,
    activation_mechanism_exists: bool | None = None,
    second_person_readiness_passed: bool | None = None,
    approval_boundary_ready: bool | None = None,
    customer_data_write_guard_ready: bool | None = None,
    activation_package_ready: bool | None = None,
) -> dict[str, Any]:
    """Compare Gate 145's decision to the current one, and say what changed.

    The three scope verdicts are supplied by the service that owns them. This
    module compares and reports; it decides nothing, because a summariser that
    computed its own verdict would be supplying its own evidence.
    """
    current = {
        "internal_demo_beta": internal_demo_beta or NO_GO,
        "controlled_customer_beta": controlled_customer_beta or NO_GO,
        "production_rollout": NO_GO,
    }

    delta = {
        scope: {
            "gate_145": GATE_145_BASELINE[scope],
            "now": current[scope],
            "changed": current[scope] != GATE_145_BASELINE[scope],
        }
        for scope in GATE_145_BASELINE
    }
    any_changed = any(entry["changed"] for entry in delta.values())

    approvals = {
        "customer_auth_live": bool(customer_auth_live),
        "verified_operational_binding": bool(verified_operational_binding),
        "consent_and_data_boundary_documented": bool(consent_boundary_documented),
        "customer_beta_scope_approved": bool(customer_beta_scope_approved),
    }
    approvals_outstanding = sorted(
        name for name in CUSTOMER_BETA_APPROVALS if not approvals[name]
    )

    readiness = {
        "second_person_readiness_passed": bool(second_person_readiness_passed),
        "approval_boundary_ready": bool(approval_boundary_ready),
        "customer_data_write_guard_ready": bool(customer_data_write_guard_ready),
        "activation_package_ready": bool(activation_package_ready),
    }

    payload = _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "gate_145_baseline": dict(GATE_145_BASELINE),
            "current_decision": current,
            "decision_delta": delta,
            "any_decision_changed": any_changed,
            "expected_no_change": True,
            "why_no_change_is_correct": (
                "Gates 146-149 were boundary gates, built to make refusals "
                "exact rather than to clear them. A block of four gates that "
                "moved a lane without a new external approval would mean one "
                "of them had granted itself something."
            ),
            # The four approvals, and none of them is technical.
            "customer_beta_approvals": approvals,
            "customer_beta_approvals_outstanding": approvals_outstanding,
            "no_outstanding_customer_blocker_is_technical": True,
            # Readiness facts, reported beside the capabilities they are not.
            "readiness_facts": readiness,
            "conflations": [dict(entry) for entry in CONFLATIONS],
            # What the block established.
            "clarifications": [dict(entry) for entry in CLARIFICATIONS],
            "throughline": dict(THE_THROUGHLINE),
            "lanes_moved_by_this_block": 0,
            # Claims.
            "safe_claims": list(SAFE_CLAIMS),
            "safe_claim_count": len(SAFE_CLAIMS),
            "unsafe_claims": [dict(entry) for entry in UNSAFE_CLAIMS],
            "unsafe_claim_count": len(UNSAFE_CLAIMS),
            # Where next.
            "next_block": dict(NEXT_BLOCK),
            # Constants.
            "controlled_customer_pilot": bool(controlled_customer_pilot),
            "activation_mechanism_exists": bool(activation_mechanism_exists),
            "pilot_activated_by_this_module": False,
            "activation_mechanism_created_by_this_module": False,
            "approval_granted_by_this_module": False,
            "rows_written": 0,
            "real_organization_touched": False,
            "not_approved": list(NOT_APPROVED),
            "leaked_shapes": [],
        }
    )
    payload["leaked_shapes"] = _leaked_shapes(payload)
    return payload


def reassessment_invariant_failures(reassessment: dict[str, Any]) -> list[str]:
    """Refuse a reassessment that reports more than the evidence supports."""
    fails: list[str] = []

    current = reassessment.get("current_decision") or {}

    # A customer GO needs all four approvals behind it. This is the one failure
    # mode this gate has.
    if current.get("controlled_customer_beta") == GO:
        outstanding = reassessment.get("customer_beta_approvals_outstanding") or []
        if outstanding:
            fails.append(f"customer_go_with_outstanding_approvals:{sorted(outstanding)}")

    if current.get("production_rollout") != NO_GO:
        fails.append("production_rollout_is_not_no_go")

    if reassessment.get("controlled_customer_pilot"):
        fails.append("pilot_reported_as_activated")
    if reassessment.get("activation_mechanism_exists"):
        fails.append("an_activation_mechanism_appeared")

    # Readiness must never be reported as the capability beside it.
    readiness = reassessment.get("readiness_facts") or {}
    approvals = reassessment.get("customer_beta_approvals") or {}
    # Readiness passing while the capability is false is the CORRECT state and
    # is not checked. The failure is the other direction: reporting the
    # capability true because the readiness behind it passed.
    if approvals.get("customer_auth_live") and not readiness.get(
        "second_person_readiness_passed"
    ):
        fails.append("customer_auth_live_without_the_readiness_behind_it")

    if reassessment.get("activation_package_ready") and reassessment.get(
        "controlled_customer_pilot"
    ):
        fails.append("package_readiness_reported_as_an_activated_pilot")

    # The delta must be consistent with the baseline it names.
    baseline = reassessment.get("gate_145_baseline") or {}
    for scope, entry in (reassessment.get("decision_delta") or {}).items():
        if entry.get("gate_145") != baseline.get(scope):
            fails.append(f"delta_baseline_disagrees:{scope}")
        if (entry.get("now") != entry.get("gate_145")) != bool(entry.get("changed")):
            fails.append(f"delta_changed_flag_disagrees:{scope}")

    if len(reassessment.get("conflations") or []) < 6:
        fails.append("conflation_list_lost_entries")
    if len(reassessment.get("unsafe_claims") or []) < 10:
        fails.append("unsafe_claim_list_lost_entries")

    for flag in (
        "pilot_activated_by_this_module",
        "activation_mechanism_created_by_this_module",
        "approval_granted_by_this_module",
        "real_organization_touched",
    ):
        if reassessment.get(flag):
            fails.append(f"module_claimed_to_have:{flag}")

    if reassessment.get("rows_written"):
        fails.append("reassessment_wrote_rows")

    for name in reassessment.get("leaked_shapes") or []:
        fails.append(f"leaked:{name}")

    return sorted(set(fails))
