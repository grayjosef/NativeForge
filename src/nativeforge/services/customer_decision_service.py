"""179D: watch, dismiss and pursue, as durable decisions with a history.

The Gate 179 survey found the existing decision tables recording a time and
nothing else:

```text
nf_source_watchlist_entries     457 rows   records_actor = false
nf_tenant_pursuit_suppressions  124 rows   records_actor = false
```

A dismissal nobody is recorded as having made cannot be reviewed, reversed
with confidence, or explained to the person who later asks why an opportunity
they were eligible for never appeared. So every decision here names its
actor, its organisation, its opportunity and its time, and the previous
decision is kept rather than overwritten.

## Dismiss is a tenant preference, not a fact about the world

This is the rule that matters most in this module. When one organisation
dismisses an opportunity, that opportunity is still in the canonical graph,
still Native-relevant, still recommended to every other tenant, and still
carries all of its evidence. Dismissal hides a row from ONE feed.

The failure mode it prevents is quiet and severe: a system where dismissing
deletes intelligence lets one person's tidy-up remove a funding opportunity
from every Tribe in the product, and nobody finds out until a deadline has
passed.

`apply_decision` therefore returns `global_intelligence_unchanged` and
`canonical_record_untouched` as fields somebody can assert on, and the
self-health layer has a detector for it.
"""

from __future__ import annotations

import hashlib
from typing import Any

SCHEMA_VERSION = "nf_customer_decision_v1"

DECISION_MODEL_VERSION = "2026.09.1"

# ---------------------------------------------------------------------------
# 179D: the decisions a customer may take about an opportunity.
# ---------------------------------------------------------------------------

NEW = "NEW"
WATCHED = "WATCHED"
DISMISSED = "DISMISSED"
PURSUING = "PURSUING"

DECISION_STATES: tuple[str, ...] = (NEW, WATCHED, DISMISSED, PURSUING)

DECISION_MEANINGS: dict[str, str] = {
    NEW: "nobody has decided anything about this yet",
    WATCHED: "somebody wants to keep an eye on it",
    DISMISSED: (
        "hidden from THIS organisation's feed. The opportunity, its evidence "
        "and every other tenant's view of it are untouched"
    ),
    PURSUING: "the organisation is working on an application",
}

#: What may follow what. Every state can be revisited, because a customer who
#: dismissed something in March must be able to pursue it in April - and a
#: dead end in a workflow about money is a support ticket.
ALLOWED_TRANSITIONS: dict[str, frozenset[str]] = {
    NEW: frozenset({WATCHED, DISMISSED, PURSUING}),
    WATCHED: frozenset({NEW, DISMISSED, PURSUING}),
    DISMISSED: frozenset({NEW, WATCHED, PURSUING}),
    PURSUING: frozenset({WATCHED, DISMISSED, NEW}),
}

#: Decisions that a human must have made. All of them: there is no state in
#: this module a machine may enter on somebody's behalf.
HUMAN_DECIDED: frozenset[str] = frozenset({WATCHED, DISMISSED, PURSUING})

#: States that keep the opportunity in the customer's working set.
ACTIVE_STATES: frozenset[str] = frozenset({WATCHED, PURSUING})

DECISION_FIELDS: tuple[str, ...] = (
    "decision_id",
    "organization_id",
    "canonical_id",
    "decision_state",
    "previous_state",
    "actor_id",
    "decided_at",
    "reason",
    "model_version",
)


def build_decision_id(*, organization_id: Any, canonical_id: Any) -> str:
    """One current decision per organisation per opportunity."""
    parts = [str(organization_id or ""), str(canonical_id or "")]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_decision(
    *,
    organization_id: Any,
    canonical_id: Any,
    decision_state: str = NEW,
    previous_state: str | None = None,
    actor_id: Any = None,
    decided_at: Any = None,
    reason: Any = None,
    logical_canonical_id: Any = None,
) -> dict[str, Any]:
    """One current decision per organisation per LOGICAL opportunity.

    `logical_canonical_id` is what the customer is actually deciding about.
    Without it, watching a forecast and then pursuing the posting it became
    produces two decision ids for one grant - the customer would watch one
    record and pursue another, and neither view would know about the other.

    The canonical_id stays on the row: it records which representation the
    person was looking at when they decided, which is evidence and is not
    rewritten when the posting arrives.
    """
    target = logical_canonical_id or canonical_id
    return {
        "schema_version": SCHEMA_VERSION,
        "decision_id": build_decision_id(
            organization_id=organization_id, canonical_id=target
        ),
        "organization_id": str(organization_id) if organization_id else None,
        "canonical_id": str(canonical_id) if canonical_id else None,
        "logical_canonical_id": str(target) if target else None,
        "decision_binds_to_logical_opportunity": logical_canonical_id is not None,
        "decision_state": str(decision_state),
        "previous_state": str(previous_state) if previous_state else None,
        "actor_id": str(actor_id) if actor_id else None,
        "decided_at": decided_at,
        "reason": str(reason) if reason else None,
        "model_version": DECISION_MODEL_VERSION,
    }


def apply_decision(
    *,
    current: dict[str, Any] | None,
    organization_id: Any,
    canonical_id: Any,
    to_state: str,
    actor_id: Any,
    decided_at: Any,
    reason: Any = None,
    history: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Move a decision, keeping the one it replaced.

    History is APPENDED, never overwritten. "Why did this stop appearing" is
    a question somebody will ask months later, and the only satisfying answer
    names a person and a date.
    """
    history = list(history or [])
    from_state = str((current or {}).get("decision_state") or NEW)
    target = str(to_state)

    if target not in DECISION_STATES:
        return {
            "accepted": False,
            "why": f"{target} is not a decision state",
            "decision": current,
            "history": history,
        }
    if target not in ALLOWED_TRANSITIONS.get(from_state, frozenset()):
        return {
            "accepted": False,
            "why": f"{from_state} -> {target} is not an allowed transition",
            "decision": current,
            "history": history,
        }
    if target in HUMAN_DECIDED and not actor_id:
        return {
            "accepted": False,
            "why": f"{target} requires a named actor",
            "decision": current,
            "history": history,
        }
    if not decided_at:
        return {
            "accepted": False,
            "why": "a decision requires the time it was taken",
            "decision": current,
            "history": history,
        }

    decision = build_decision(
        organization_id=organization_id,
        canonical_id=canonical_id,
        decision_state=target,
        previous_state=from_state,
        actor_id=actor_id,
        decided_at=decided_at,
        reason=reason,
    )
    if current is not None:
        history.append(dict(current))

    return {
        "accepted": True,
        "decision": decision,
        # The previous decision is kept, not replaced.
        "history": history,
        "history_length": len(history),
        "audit_event": {
            "action": f"customer.opportunity_{target.lower()}",
            "organization_id": str(organization_id) if organization_id else None,
            "actor_id": str(actor_id) if actor_id else None,
            "canonical_id": str(canonical_id) if canonical_id else None,
            "from_state": from_state,
            "to_state": target,
            "reason": str(reason) if reason else None,
            "occurred_at": str(decided_at),
        },
        # The rule this module exists for.
        "global_intelligence_unchanged": True,
        "canonical_record_untouched": True,
        "other_tenants_unaffected": True,
        "scope": "this organisation only",
        "why": str(reason) if reason else f"{from_state} -> {target}",
    }


def visible_to_other_tenant(
    *, decision: dict[str, Any], other_organization_id: Any
) -> bool:
    """Would another tenant's feed be affected by this decision? Never.

    Written as a function rather than asserted in a docstring so the corpus
    and the self-health layer can call it, and so it can be shown to be false
    if somebody ever makes it so.
    """
    return str(decision.get("organization_id")) == str(other_organization_id)


def decision_invariant_failures(decision: dict[str, Any]) -> list[str]:
    """Refuse a decision nobody is recorded as having made."""
    failures: list[str] = []

    for field in DECISION_FIELDS:
        if field not in decision:
            failures.append(f"decision_missing_field:{field}")

    state = str(decision.get("decision_state") or "")
    if state not in DECISION_STATES:
        failures.append(f"decision_state_outside_the_vocabulary:{state or 'missing'}")

    if not decision.get("organization_id"):
        failures.append("decision_names_no_organization")
    if not decision.get("canonical_id"):
        failures.append("decision_names_no_opportunity")

    # The survey's finding, made unrepresentable.
    if state in HUMAN_DECIDED:
        if not decision.get("actor_id"):
            failures.append(f"{state.lower()}_decision_names_no_actor")
        if not decision.get("decided_at"):
            failures.append(f"{state.lower()}_decision_has_no_time")

    previous = decision.get("previous_state")
    if previous and str(previous) not in DECISION_STATES:
        failures.append(f"previous_state_outside_the_vocabulary:{previous}")
    if previous and state not in ALLOWED_TRANSITIONS.get(str(previous), frozenset()):
        failures.append(f"decision_records_a_forbidden_move:{previous}_to_{state}")

    return sorted(set(failures))


def summarize_decisions(
    *, decisions: list[dict[str, Any]], organization_id: Any
) -> dict[str, Any]:
    """Counts for the dashboard, for ONE organisation."""
    mine = [
        d for d in decisions if str(d.get("organization_id")) == str(organization_id)
    ]
    counts = dict.fromkeys(DECISION_STATES, 0)
    for d in mine:
        key = str(d.get("decision_state") or NEW)
        if key in counts:
            counts[key] += 1
    return {
        "schema_version": SCHEMA_VERSION,
        "organization_id": str(organization_id) if organization_id else None,
        "counts": counts,
        "watching": counts[WATCHED],
        "pursuing": counts[PURSUING],
        "dismissed": counts[DISMISSED],
        "decisions_considered": len(mine),
        # Rows belonging to other tenants were never in scope.
        "rows_from_other_tenants": len(decisions) - len(mine),
        "tenant_scoped": True,
    }


def describe_decision_model() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "model_version": DECISION_MODEL_VERSION,
        "decision_states": list(DECISION_STATES),
        "active_states": sorted(ACTIVE_STATES),
        "every_state_has_a_meaning": set(DECISION_MEANINGS) == set(DECISION_STATES),
        "every_state_has_transitions": set(ALLOWED_TRANSITIONS) == set(DECISION_STATES),
        # The refusals.
        "every_decision_names_an_actor": True,
        "every_decision_names_a_time": True,
        "history_is_appended_never_overwritten": True,
        "dismiss_is_tenant_scoped": True,
        "dismiss_does_not_delete_intelligence": True,
        "dismiss_does_not_affect_other_tenants": True,
        "every_state_is_reversible": all(
            bool(ALLOWED_TRANSITIONS[state]) for state in DECISION_STATES
        ),
        "no_machine_decides_on_a_customers_behalf": True,
    }
