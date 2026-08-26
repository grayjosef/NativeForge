"""Customer operating-state source filter (Gate 90D).

Decides which registry sources a given customer may see, so that a state source
reaches only customers who actually operate in that state.

## The failure this exists to prevent

Every state row in the current seed is South Carolina. If the filter defaults
open, a customer in Oklahoma is shown SC broadband and SC emergency-management
programs they cannot apply to - and the campaign's whole SC pilot vocabulary
starts leaking into states it was never validated for.

So the filter is **deny by default for state-scoped rows**. A source becomes
visible by matching, never by failing to be excluded. A customer with no
declared operating state sees zero state sources, not all of them.

## Operating state, not mailing address

The dossier is explicit (§8.1): resolve operating state(s), service area and
lands - do not use a mailing address. This module takes an explicit
``operating_states`` list and has no address field at all, so there is nothing
to accidentally fall back to.

## Visibility is not eligibility

A visible source means "this is somewhere you might look". It does not mean the
customer qualifies. ``eligibility_status`` rides through untouched at
``NOT_DETERMINED_BY_REGISTRY``.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_customer_state_source_filter_v1"

# Scopes whose visibility depends on the customer's operating states.
STATE_DEPENDENT_SCOPES = frozenset({"state_scoped"})

# Scopes visible to every customer, subject to their own activation blockers.
UNIVERSAL_SCOPES = frozenset({"federal_all_customers", "private_unscoped"})

BLOCK_REASONS = frozenset(
    {
        "customer_has_no_declared_operating_state",
        "state_not_in_customer_operating_states",
        "source_state_unknown",
        "unrecognised_state_scope",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _normalise_states(states: Any) -> list[str]:
    if not states:
        return []
    if isinstance(states, str):
        states = [states]
    return sorted({str(s).strip().upper() for s in states if str(s).strip()})


def filter_sources_for_customer(
    *,
    seeds: list[dict[str, Any]],
    operating_states: Any = None,
    customer_id: str | None = None,
) -> dict[str, Any]:
    """Split registry seeds into what this customer may see and what they may not.

    ``operating_states`` is the customer's actual operating state(s). An empty
    or missing value is treated as *unknown*, which blocks every state-scoped
    source - the safe direction.
    """
    customer_states = _normalise_states(operating_states)
    has_declared_state = bool(customer_states)

    visible: list[dict[str, Any]] = []
    blocked: list[dict[str, Any]] = []
    unknown_state: list[dict[str, Any]] = []
    blocked_reasons: dict[str, str] = {}

    for seed in seeds:
        sid = str(seed.get("source_id") or "")
        scope = seed.get("state_scope_status")
        source_state = str(seed.get("state_if_applicable") or "").strip().upper()

        if scope in UNIVERSAL_SCOPES:
            visible.append(seed)
            continue

        if scope not in STATE_DEPENDENT_SCOPES:
            # Unrecognised scope: block rather than guess. A scope nobody has
            # classified is not a scope anybody has cleared.
            blocked.append(seed)
            blocked_reasons[sid] = "unrecognised_state_scope"
            unknown_state.append(seed)
            continue

        if not source_state:
            blocked.append(seed)
            blocked_reasons[sid] = "source_state_unknown"
            unknown_state.append(seed)
            continue

        if not has_declared_state:
            blocked.append(seed)
            blocked_reasons[sid] = "customer_has_no_declared_operating_state"
            continue

        if source_state in customer_states:
            visible.append(seed)
        else:
            blocked.append(seed)
            blocked_reasons[sid] = "state_not_in_customer_operating_states"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "customer_id": customer_id,
            "customer_operating_states": customer_states,
            "customer_has_declared_operating_state": has_declared_state,
            "visible_sources": visible,
            "blocked_sources": blocked,
            "blocked_reasons": blocked_reasons,
            "unknown_state_sources": unknown_state,
            "visible_count": len(visible),
            "blocked_count": len(blocked),
            # Said out loud so a caller cannot read visibility as qualification.
            "visibility_is_not_eligibility": True,
            "mailing_address_used": False,
            "default_all_state_expansion": False,
            "fabricated": False,
        }
    )


def filter_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("mailing_address_used") is not False:
        fails.append("mailing_address_used")
    if result.get("default_all_state_expansion") is not False:
        fails.append("default_all_state_expansion")
    if result.get("visibility_is_not_eligibility") is not True:
        fails.append("visibility_conflated_with_eligibility")

    customer_states = set(result.get("customer_operating_states") or [])

    for seed in result.get("visible_sources") or []:
        scope = seed.get("state_scope_status")
        state = str(seed.get("state_if_applicable") or "").strip().upper()
        if scope in STATE_DEPENDENT_SCOPES:
            if not state:
                fails.append(f"visible_state_source_without_state:{seed.get('source_id')}")
            elif state not in customer_states:
                # The leak this module exists to prevent.
                fails.append(
                    f"state_source_leaked_to_wrong_customer:{seed.get('source_id')}"
                )

    for seed in result.get("blocked_sources") or []:
        sid = str(seed.get("source_id") or "")
        reason = (result.get("blocked_reasons") or {}).get(sid)
        if not reason:
            fails.append(f"blocked_without_reason:{sid}")
        elif reason not in BLOCK_REASONS:
            fails.append(f"block_reason_out_of_vocabulary:{reason}")

    # Nothing may be silently dropped: every seed lands in exactly one bucket.
    visible_ids = {s.get("source_id") for s in result.get("visible_sources") or []}
    blocked_ids = {s.get("source_id") for s in result.get("blocked_sources") or []}
    if visible_ids & blocked_ids:
        fails.append("source_both_visible_and_blocked")

    return fails
