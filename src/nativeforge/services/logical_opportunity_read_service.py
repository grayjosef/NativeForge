"""What the product shows when two source rows are one real opportunity.

The resolver in `opportunity_identity_repository` answers "which logical
opportunity does this L1 id belong to?". This module is what the read and
write paths actually call, so that none of them has to learn the answer twice.

    resolutions = resolve_logical_canonical_ids(connection=..., canonical_ids=ids)
    feed        = build_feed(..., logical_resolutions=resolutions)
    decision    = build_decision(..., logical_canonical_id=logical_key(id, resolutions))

Resolution is passed IN, already batched. Nothing here touches a database,
which is what keeps a customer feed of N opportunities from issuing N
relationship queries - the caller resolves once and every consumer reuses it.

## Customer state binds to the logical opportunity, evidence does not

A pursuit, a watch, a dismissal belong to the grant the customer is chasing.
Provenance, versions and raw payloads stay attached to the representation they
actually came from: the forecast said what it said, and rewriting that to
point at the posting would destroy the record of what was known beforehand.

## Conflicts are named, never won

If someone dismissed the forecast and pursued the posting, this reports a
CONFLICT and keeps both. Picking the later timestamp would be inventing an
intention the customer never expressed.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_logical_opportunity_read_v1"

#: A decision that means the customer did something deliberate. NEW is the
#: absence of a decision, so it never conflicts with anything.
_DELIBERATE_STATES: frozenset[str] = frozenset({"WATCHED", "DISMISSED", "PURSUING"})

CONFLICT = "CONFLICT"
AGREED = "AGREED"
SINGLE = "SINGLE"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def logical_key(canonical_id: Any, resolutions: Any = None) -> str:
    """The id customer state should bind to. Falls back to the id itself.

    A missing resolution is not an error: an opportunity with no relationship
    IS its own logical opportunity, and that is the overwhelmingly common
    case.
    """
    key = str(canonical_id or "")
    table = (resolutions or {}).get("resolutions") or {}
    entry = table.get(key) or {}
    return str(entry.get("logical_canonical_id") or key)


def collapse_rows(
    rows: list[dict[str, Any]],
    *,
    resolutions: Any = None,
    id_field: str = "canonical_id",
) -> dict[str, Any]:
    """Collapse representation rows to one row per logical opportunity.

    The surviving row is the one whose own id IS the logical id - the primary.
    If the primary is not in the batch (a feed page that contains the forecast
    but not the posting), the first representation survives and is marked, so
    the caller can tell "this is the opportunity" from "this is all of it we
    were given".
    """
    by_logical: dict[str, dict[str, Any]] = {}
    superseded: dict[str, str] = {}
    order: list[str] = []

    for row in rows:
        raw = str(row.get(id_field) or "")
        logical = logical_key(raw, resolutions)
        if logical != raw:
            superseded[raw] = logical
        existing = by_logical.get(logical)
        if existing is None:
            by_logical[logical] = dict(row)
            order.append(logical)
            continue
        # Two rows for one opportunity. Keep the primary.
        if raw == logical:
            merged = dict(row)
            merged["_replaced"] = existing
            by_logical[logical] = merged

    collapsed: list[dict[str, Any]] = []
    for logical in order:
        row = dict(by_logical[logical])
        row.pop("_replaced", None)
        history = sorted(r for r, lg in superseded.items() if lg == logical)
        row["logical_opportunity_id"] = logical
        row["historical_representations"] = history
        row["has_pre_publication_history"] = bool(history)
        row["is_primary_representation"] = str(row.get(id_field) or "") == logical
        collapsed.append(row)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "representation_count": len(rows),
            "logical_opportunity_count": len(collapsed),
            "collapsed_count": len(rows) - len(collapsed),
            "rows": collapsed,
            "superseded_by": dict(sorted(superseded.items())),
        }
    )


def logical_opportunity_count(
    canonical_ids: list[Any], *, resolutions: Any = None
) -> int:
    """How many real opportunities these representations amount to.

    Distinct from a representation count, which is a legitimate number with a
    different meaning - `representation_count` in `collapse_rows` reports it.
    """
    return len({logical_key(c, resolutions) for c in canonical_ids if str(c or "")})


def reconcile_customer_state(
    decisions: list[dict[str, Any]], *, resolutions: Any = None
) -> dict[str, Any]:
    """One customer's decisions across representations of one opportunity.

    Returns a state per logical opportunity, and refuses to pick a winner when
    two representations disagree.
    """
    grouped: dict[str, list[dict[str, Any]]] = {}
    for decision in decisions:
        logical = logical_key(decision.get("canonical_id"), resolutions)
        grouped.setdefault(logical, []).append(decision)

    results: dict[str, dict[str, Any]] = {}
    conflicts: list[str] = []
    for logical, rows in sorted(grouped.items()):
        states = {
            str(r.get("decision_state") or "")
            for r in rows
            if str(r.get("decision_state") or "") in _DELIBERATE_STATES
        }
        if len(states) > 1:
            conflicts.append(logical)
            results[logical] = {
                "logical_canonical_id": logical,
                "status": CONFLICT,
                "decision_state": None,
                "competing_states": sorted(states),
                # Both histories survive. Neither is discarded because it was
                # older, which would be inventing an intention.
                "decisions": sorted(rows, key=lambda r: str(r.get("canonical_id"))),
                "requires_human": True,
            }
            continue
        state = next(iter(states)) if states else "NEW"
        results[logical] = {
            "logical_canonical_id": logical,
            "status": AGREED if len(rows) > 1 else SINGLE,
            "decision_state": state,
            "competing_states": [],
            "decisions": sorted(rows, key=lambda r: str(r.get("canonical_id"))),
            "requires_human": False,
        }

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "by_logical_opportunity": results,
            "logical_opportunity_count": len(results),
            "conflicts": sorted(conflicts),
            "conflict_count": len(conflicts),
        }
    )


def duplicate_pursuit_failures(
    pursuits: list[dict[str, Any]], *, resolutions: Any = None
) -> list[str]:
    """Two pursuits for one real grant is split-brain, not two projects."""
    seen: dict[str, list[str]] = {}
    for pursuit in pursuits:
        logical = logical_key(pursuit.get("canonical_id"), resolutions)
        seen.setdefault(logical, []).append(str(pursuit.get("pursuit_id") or ""))
    return sorted(
        f"duplicate_pursuits_for_one_opportunity:{logical}:{sorted(ids)}"
        for logical, ids in seen.items()
        if len(ids) > 1
    )


def customer_visible_invariant_failures(
    *,
    rows: list[dict[str, Any]],
    resolutions: Any = None,
    id_field: str = "canonical_id",
) -> list[str]:
    """The close condition, as something that can actually fail."""
    failures: list[str] = []
    collapsed = collapse_rows(rows, resolutions=resolutions, id_field=id_field)
    visible = {str(r.get(id_field) or "") for r in collapsed["rows"]}
    superseded = collapsed["superseded_by"]

    for representation, logical in superseded.items():
        if representation in visible:
            failures.append(f"superseded_representation_is_visible:{representation}")
        if logical not in visible and any(
            str(r.get(id_field) or "") == logical for r in rows
        ):
            failures.append(f"primary_is_not_visible:{logical}")
    return sorted(set(failures))
