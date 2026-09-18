"""Per-source live-fetch opt-in (Gate 163H).

Gate 162 kept `authorized` and `live_fetch_opted_in` apart deliberately:
authorization complete is not a permitted request. This is the second half,
and it is recorded PER SOURCE.

## Not a global switch

There is no `live_transport_enabled` flag here and this module will not grow
one. An opt-in is a row naming one source, signed by the operator who took
responsibility for it. Opting in a second source means a second row, a second
signature, and a second deliberate act.

The reason is the failure it prevents: a global switch turns "we authorized
Grants.gov" into "every authorized source may now be called", and the 177
other registry rows are one terms decision away from being authorized.

## It composes the decision table

No new table. The opt-in is a third `decision_kind` in
`nf_source_authorization_decisions`, so it inherits every constraint migration
0048 put there — an `approved` opt-in cannot be written without a signer, a
time and an evidence reference.

That also means the count of opted-in sources is a query anyone can run
against the same table as the terms and review decisions, rather than a flag
in a different shape somewhere else.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_source_live_fetch_opt_in_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: The third decision kind. Migration 0052 adds it to the vocabulary.
LIVE_FETCH = "live_fetch"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def is_live_fetch_opted_in(
    *,
    connection: Any = None,
    organization_id: Any = None,
    source_id: Any = None,
) -> bool:
    """Is there a signed, approved live-fetch opt-in for THIS source?

    Returns False for anything else, including a missing row, an unsigned row
    and a row for a different source. Absence is not permission.
    """
    if connection is None or not str(source_id or "").strip():
        return False
    try:
        from nativeforge.repositories.source_authorization_decision_repository import (
            get_decision,
        )

        found = get_decision(
            connection=connection,
            organization_id=organization_id,
            source_id=source_id,
            decision_kind=LIVE_FETCH,
        )
    except Exception:  # noqa: BLE001 - an unreadable opt-in is not one
        return False

    row = found.get("decision") or {}
    return bool(
        row.get("decision") == "approved"
        and row.get("reviewed_by")
        and row.get("reviewed_at")
    )


def describe_opt_in_state(
    *, connection: Any = None, organization_id: Any = None
) -> dict[str, Any]:
    """Which sources are opted in, and the count that matters."""
    opted: list[dict[str, Any]] = []
    try:
        from nativeforge.repositories.source_authorization_decision_repository import (
            list_decisions,
        )

        listed = list_decisions(
            connection=connection,
            organization_id=organization_id,
            decision_kind=LIVE_FETCH,
        )
        for row in listed.get("decisions") or []:
            if row.get("decision") == "approved":
                opted.append(
                    {
                        "source_id": row.get("source_id"),
                        "reviewed_by": row.get("reviewed_by"),
                        "reviewed_at": row.get("reviewed_at"),
                        "signed": bool(
                            row.get("reviewed_by") and row.get("reviewed_at")
                        ),
                    }
                )
    except Exception:  # noqa: BLE001
        opted = []

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "opted_in_sources": opted,
            "opted_in_count": len(opted),
            "unsigned_opt_ins": len([o for o in opted if not o["signed"]]),
            "is_a_global_switch": False,
            "why_not_global": (
                "a global switch turns one authorized source into every "
                "authorized source. 177 registry rows are one terms decision "
                "away from being authorized, so the opt-in is per source and "
                "carries its own signature."
            ),
            "stored_in": "nf_source_authorization_decisions[decision_kind=live_fetch]",
            "inherits_constraints_from": (
                "migration 0048 - an approved opt-in needs a signer, a time "
                "and an evidence reference"
            ),
        }
    )


def opt_in_invariant_failures(state: dict[str, Any]) -> list[str]:
    """Refuse an opt-in state that is global, unsigned, or over-broad."""
    fails: list[str] = []

    if state.get("is_a_global_switch"):
        fails.append("the_opt_in_became_a_global_switch")
    if int(state.get("unsigned_opt_ins") or 0):
        fails.append(f"unsigned_opt_ins:{state.get('unsigned_opt_ins')}")

    # Gate 163 authorized exactly one source. More than one opted in means
    # something widened without a gate.
    if int(state.get("opted_in_count") or 0) > 1:
        fails.append(f"more_than_one_source_opted_in:{state.get('opted_in_count')}")

    for entry in state.get("opted_in_sources") or []:
        if not entry.get("signed"):
            fails.append(f"an_unsigned_opt_in:{entry.get('source_id')}")

    return sorted(set(fails))
