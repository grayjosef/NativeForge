"""Tenant source priority (Gate 103D).

Connects a tenant profile to SC and federal source priority. It activates
nothing, monitors nothing, and fetches nothing.

## Priority is an ordering, not an activation

Ranking a source first says which one a collector would reach for *if one were
running*. Gate 93 found all five Phase 1 collectors `not_active` and Gates
98–102 kept them that way, so every source in every ranking this service
produces is inert.

```text
sources_active     0
sources_monitored  0
live_coverage      false
```

All three are held by invariants. A ranked list of 360 sources with zero active
collectors is exactly the state of this repository, and the numbers say so
rather than the ordering implying otherwise.

## Priority is tenant-specific

South Carolina is the beta's immediate priority because *these four tenants*
operate there — it is not a property of NativeForge. A tenant whose profile does
not carry SC in its operating states gets federal sources ranked first and no SC
tier at all, and an invariant fails any result claiming an SC tier without SC in
the tenant's operating states.

That mirrors Gate 103B, where `sc_priority` is derived from the tenant's own
states rather than assumed.

## Source status is carried through, never upgraded

Each row keeps the activation status the registry and Gate 93's policy give it:

```text
not_active               nothing runs
human_review_only        a person must look before anything runs
terms_review_required    terms have not been read
activation_allowed       cleared - and still not running
```

Ranking never changes a status. A source can be first in the list and
`terms_review_required`, and the row says both.

## Read from the registry fixture, never from the network

The 381-row v2 registry fixture is the input. This service imports no HTTP
client and an AST test proves it.
"""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_tenant_source_priority_v1"

REPO_ROOT = Path(__file__).resolve().parents[3]
REGISTRY_RELATIVE_PATH = (
    "fixtures/external_source_registry/nativeforge-source-registry-v2.csv"
)

# Gate 93's activation vocabulary, carried rather than restated.
SOURCE_ACTIVATION_STATUSES = frozenset(
    {
        "not_active",
        "human_review_only",
        "terms_review_required",
        "activation_allowed",
        "unknown",
    }
)

# The only status that would permit anything, and nothing holds it today.
ACTIVATION_PERMITTING = frozenset({"activation_allowed"})

SOURCE_SCOPES = frozenset({"federal", "state", "private", "unknown"})

# Beta priority tiers, strongest first. SC before federal is the product
# requirement; both before private, which is out of beta scope.
PRIORITY_TIERS: tuple[str, ...] = (
    "tenant_state_priority",
    "federal_priority",
    "other_state",
    "private",
    "out_of_scope",
)

TIER_RANK: dict[str, int] = {tier: index for index, tier in enumerate(PRIORITY_TIERS)}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def load_registry_rows(*, repo_root: Path | None = None) -> list[dict[str, Any]]:
    """The v2 registry fixture. A file read, never a fetch."""
    root = repo_root or REPO_ROOT
    path = root / REGISTRY_RELATIVE_PATH
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _scope(row: dict[str, Any]) -> str:
    value = str(row.get("federal_or_state_or_private") or "").strip().lower()
    return value if value in SOURCE_SCOPES else "unknown"


def _state(row: dict[str, Any]) -> str:
    return str(row.get("state_if_applicable") or "").strip().upper()


def _activation_status(row: dict[str, Any]) -> str:
    """The status this source actually holds. Never upgraded by ranking.

    `requires_login` is tri-state in the registry - Gate 92 found a seed reading
    the raw string and getting it wrong, so an unrecognised value means human
    review rather than a permissive default.
    """
    login = str(row.get("requires_login") or "").strip().lower()
    if login in {"yes", "true"}:
        return "human_review_only"
    if login in {"unknown", "", "tbd"}:
        return "terms_review_required"
    if login in {"no", "false"}:
        # Cleared of a login wall, and still not activated by anyone.
        return "not_active"
    return "terms_review_required"


def build_tenant_source_priority(
    *,
    tenant_id: Any,
    profile: dict[str, Any] | None = None,
    repo_root: Path | None = None,
    include_private: bool = False,
) -> dict[str, Any]:
    """Rank sources for one tenant. Nothing is activated or monitored."""
    rows = load_registry_rows(repo_root=repo_root)

    operating_fact = (profile or {}).get("operating_states") or {}
    operating = operating_fact.get("value") or []
    tenant_states = {str(s).strip().upper() for s in operating if str(s).strip()}
    watchlist = {
        str(s).strip() for s in ((profile or {}).get("source_watchlist") or [])
    }

    priority_rows: list[dict[str, Any]] = []
    for row in rows:
        scope = _scope(row)
        state = _state(row)
        source_id = str(row.get("source_id") or "").strip()

        if scope == "state" and state and state in tenant_states:
            tier = "tenant_state_priority"
        elif scope == "federal":
            tier = "federal_priority"
        elif scope == "state":
            tier = "other_state"
        elif scope == "private":
            tier = "private" if include_private else "out_of_scope"
        else:
            tier = "out_of_scope"

        priority_rows.append(
            {
                "source_id": source_id,
                "source_name": str(row.get("source_name") or "").strip(),
                "scope": scope,
                "state": state or None,
                "priority_tier": tier,
                "tier_rank": TIER_RANK[tier],
                "activation_status": _activation_status(row),
                "on_tenant_watchlist": source_id in watchlist,
                # Per-row constants. A rank is not a run.
                "active": False,
                "monitored": False,
                "fetch_performed": False,
            }
        )

    # Stable ordering: tier, then id. No clock, no input-order dependence.
    priority_rows.sort(key=lambda r: (r["tier_rank"], r["source_id"]))

    in_priority = [
        r for r in priority_rows if r["priority_tier"] != "out_of_scope"
    ]
    sc_rows = [
        r for r in priority_rows if r["priority_tier"] == "tenant_state_priority"
    ]
    federal_rows = [
        r for r in priority_rows if r["priority_tier"] == "federal_priority"
    ]

    blocked_reasons: list[str] = []
    if not rows:
        blocked_reasons.append("registry_fixture_not_found")
    if not tenant_states:
        blocked_reasons.append("tenant_operating_states_unknown")
    if not sc_rows and "SC" in tenant_states:
        blocked_reasons.append("no_sc_sources_matched_the_registry")
    # The load-bearing one: a ranking with nothing behind it.
    blocked_reasons.append("no_active_collectors")
    blocked_reasons.append("source_monitoring_not_available")

    by_status = {status: 0 for status in sorted(SOURCE_ACTIVATION_STATUSES)}
    for row in priority_rows:
        by_status[row["activation_status"]] += 1

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_id": tenant_id,
            "tenant_operating_states": sorted(tenant_states),
            "registry_row_count": len(rows),
            "priority_source_count": len(in_priority),
            "sc_source_count": len(sc_rows),
            "federal_source_count": len(federal_rows),
            "by_activation_status": by_status,
            "watchlist_matched_count": sum(
                1 for r in priority_rows if r["on_tenant_watchlist"]
            ),
            # The three the gate requires, derived from the rows.
            "sources_active": sum(1 for r in priority_rows if r["active"]),
            "sources_monitored": sum(1 for r in priority_rows if r["monitored"]),
            "live_coverage": False,
            "sc_priority_applied": bool(sc_rows),
            "priority_tiers": list(PRIORITY_TIERS),
            "blocked_reasons": sorted(set(blocked_reasons)),
            "source_priority_rows": priority_rows,
            # Constants: ranking is not running.
            "fetch_performed": False,
            "collectors_activated": 0,
            "fabricated": False,
        }
    )


def summarise_source_priority(result: dict[str, Any]) -> dict[str, Any]:
    """A flat summary. Carries counts, never the row bodies."""
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "tenant_id": result.get("tenant_id"),
            "priority_source_count": result.get("priority_source_count"),
            "sc_source_count": result.get("sc_source_count"),
            "federal_source_count": result.get("federal_source_count"),
            "by_activation_status": result.get("by_activation_status"),
            "sources_active": 0,
            "sources_monitored": 0,
            "live_coverage": False,
            "fetch_performed": False,
            "fabricated": False,
        }
    )


def source_priority_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    for constant in ("live_coverage", "fetch_performed"):
        if result.get(constant) is not False:
            fails.append(f"priority_claimed:{constant}")
    if result.get("collectors_activated") != 0:
        fails.append("priority_activated_collectors")

    rows = result.get("source_priority_rows")
    if not isinstance(rows, list):
        fails.append("source_priority_rows_not_a_list")
        return fails

    for row in rows:
        if row.get("priority_tier") not in PRIORITY_TIERS:
            fails.append(f"priority_tier_out_of_vocabulary:{row.get('priority_tier')}")
        if row.get("activation_status") not in SOURCE_ACTIVATION_STATUSES:
            fails.append(
                f"activation_status_out_of_vocabulary:{row.get('activation_status')}"
            )
        for constant in ("active", "monitored", "fetch_performed"):
            if row.get(constant) is not False:
                fails.append(f"row_claimed:{constant}:{row.get('source_id')}")
        # Ranking never upgrades a status, and a permitted source is still not
        # a running one - only a collector could make it active, and there is
        # none.
        if row.get("activation_status") in ACTIVATION_PERMITTING and row.get("active"):
            fails.append(f"permitted_source_marked_active:{row.get('source_id')}")

    # Counts derived from the rows, never asserted beside them.
    if result.get("sources_active") != sum(1 for r in rows if r.get("active")):
        fails.append("active_count_disagrees_with_the_rows")
    if result.get("sources_monitored") != sum(1 for r in rows if r.get("monitored")):
        fails.append("monitored_count_disagrees_with_the_rows")
    if result.get("sc_source_count") != sum(
        1 for r in rows if r.get("priority_tier") == "tenant_state_priority"
    ):
        fails.append("sc_count_disagrees_with_the_rows")
    if result.get("federal_source_count") != sum(
        1 for r in rows if r.get("priority_tier") == "federal_priority"
    ):
        fails.append("federal_count_disagrees_with_the_rows")

    # SC priority is tenant-specific.
    states = set(result.get("tenant_operating_states") or [])
    if result.get("sc_priority_applied") and "SC" not in states:
        fails.append("sc_tier_without_sc_in_tenant_operating_states")
    if result.get("sc_source_count") and "SC" not in states:
        fails.append("sc_sources_counted_for_a_non_sc_tenant")

    # A ranking with no collectors must say so.
    if not result.get("sources_active"):
        if "no_active_collectors" not in (result.get("blocked_reasons") or []):
            fails.append("inactive_ranking_without_a_reason")

    return fails
