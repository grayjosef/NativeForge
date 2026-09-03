"""Gate 140B: the source watchlist lane, which had nothing at all.

Gate 138's capability matrix reported `source_watchlist_persistence` absent on
all three counts — no table, no repository, no contract — and it stayed false
honestly for two gates. This is all three.

## organization_id is the anchor; tenant_id is a label

`tenant_pursuit_suppression_service` keys its in-memory records on `tenant_id`,
and Gates 109 through 113 settled that a tenant label is never authority. So
every read here is anchored on `organization_id` and `tenant_id_label` narrows;
it never selects.

## A source is a registry id or a controlled fixture id

Nothing in this module contacts a registry, a source, or the network. A caller
supplies a `source_id` and says where it came from:

```text
registry_entry       an id from the source registry
controlled_fixture   a labelled fixture id - the only one this gate produces
tenant_requested     a tenant asked for a source nobody has vetted yet
needs_human_review   somebody tried to resolve it and could not
unknown
```

A `registry_entry` claim is checked against the registry **as it already exists
in this repository** — no HTTP — and an id that is not there is refused by name
rather than accepted on the caller's word. `tenant_requested` and
`needs_human_review` are stored with `human_review_required` true, because a
source nobody has vetted is exactly the thing a human has to look at.

## Archive, never delete

One live entry per organization and source, enforced by a partial unique index.
Removing a source archives the row: a watchlist that forgets it used to watch
something cannot answer "why did we stop seeing these".

## What this module never does

No live HTTP. No source activation. No monitoring claim — `source_monitoring_live`
is reported False as a constant and an invariant fails if it is ever true.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_tenant_source_watchlist_v1"

TABLE_NAME = "nf_source_watchlist_entries"

WATCHLIST_STATES = frozenset(
    {"watching", "paused", "archived", "needs_human_review", "unknown"}
)

#: States where the source is actually being watched.
ACTIVE_STATES = frozenset({"watching"})

WATCHLIST_SOURCES = frozenset(
    {
        "registry_entry",
        "controlled_fixture",
        "tenant_requested",
        "needs_human_review",
        "unknown",
    }
)

#: Sources whose id must exist in the registry. The others say, in their own
#: name, that nobody has vetted them.
REGISTRY_BACKED_SOURCES = frozenset({"registry_entry"})

#: Sources that always require a human to look. A watchlist entry nobody has
#: vetted is not a monitoring commitment.
HUMAN_REVIEW_SOURCES = frozenset({"tenant_requested", "needs_human_review", "unknown"})

FACT_STATUSES = frozenset(
    {"demo_fixture", "tenant_supplied", "verified", "needs_human_review", "unknown"}
)

#: Values that may never anchor a watchlist read or write.
FORBIDDEN_ANCHOR_NAMES: tuple[str, ...] = (
    "tenant_id",
    "customer_org_id",
    "organization_profile_id",
)

#: The prefix a controlled fixture source id must carry, so a fixture can never
#: be mistaken for a registry entry by a reader or by a later query.
FIXTURE_SOURCE_PREFIX = "nf-fixture-"

UNKNOWN_REGISTRY_SOURCE = "source_id_is_not_in_the_source_registry"
FIXTURE_PREFIX_MISSING = "controlled_fixture_source_id_must_carry_the_fixture_prefix"

_METADATA = sa.MetaData()

WATCHLIST = sa.Table(
    TABLE_NAME,
    _METADATA,
    sa.Column("id", sa.Uuid(as_uuid=True), primary_key=True),
    sa.Column("organization_id", sa.Uuid(as_uuid=True), nullable=False),
    sa.Column("is_demo", sa.Boolean(), nullable=False),
    sa.Column("tenant_id_label", sa.Text(), nullable=True),
    sa.Column("source_id", sa.Text(), nullable=False),
    sa.Column("source_name", sa.Text(), nullable=True),
    sa.Column("jurisdiction", sa.String(length=64), nullable=True),
    sa.Column("program_area", sa.String(length=128), nullable=True),
    sa.Column("watchlist_state", sa.String(length=32), nullable=False),
    sa.Column("watchlist_source", sa.String(length=32), nullable=False),
    sa.Column("fact_status", sa.String(length=32), nullable=False),
    sa.Column("human_review_required", sa.Boolean(), nullable=False),
    sa.Column("blocked_reasons", sa.JSON(), nullable=False),
    sa.Column("created_by_identity_id", sa.Uuid(as_uuid=True), nullable=True),
    sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
    sa.Column("archived_at", sa.DateTime(timezone=True), nullable=True),
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value or "").strip())
    except (ValueError, AttributeError, TypeError):
        return None


def _norm(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    text = str(value or "").strip().lower()
    return text if text in vocabulary else fallback


def known_registry_source_ids() -> frozenset[str]:
    """Source ids this repository already knows about. No network.

    Read from the seed catalogue that ships with the repository rather than
    fetched. A `registry_entry` claim is checked against this; anything else is
    refused by name, so a caller cannot promote a made-up id by labelling it.
    """
    import csv

    try:
        from nativeforge.services.source_ingestion_seed_schema_service import (
            seed_csv_path,
        )

        path = seed_csv_path()
        if not path.is_file():
            return frozenset()
        with path.open(encoding="utf-8-sig", newline="") as handle:
            rows = list(csv.DictReader(handle))
    except Exception:
        return frozenset()

    ids: set[str] = set()
    for row in rows:
        for key in ("seed_id", "source_id", "id"):
            value = str((row or {}).get(key) or "").strip()
            if value:
                ids.add(value)
                break
    return frozenset(ids)


def prepare_watchlist_entry(
    *,
    organization_id: Any = None,
    source_id: Any = None,
    watchlist_source: Any = None,
    watchlist_state: Any = "watching",
    source_name: Any = None,
    jurisdiction: Any = None,
    program_area: Any = None,
    tenant_id_label: Any = None,
    fact_status: Any = "demo_fixture",
    is_demo: bool = True,
    registry_source_ids: frozenset[str] | None = None,
    **offered: Any,
) -> dict[str, Any]:
    """Decide whether this watchlist entry may be stored. Touches no network."""
    anchor = _as_uuid(organization_id)
    source = str(source_id or "").strip()
    origin = _norm(watchlist_source, WATCHLIST_SOURCES, fallback="unknown")
    state = _norm(watchlist_state, WATCHLIST_STATES, fallback="unknown")
    facts = _norm(fact_status, FACT_STATUSES, fallback="unknown")

    blocked: list[str] = []

    for key in FORBIDDEN_ANCHOR_NAMES:
        if str(offered.get(key) or "").strip():
            blocked.append(f"not_an_anchor_for_a_watchlist_entry:{key}")

    if anchor is None:
        blocked.append("watchlist_entry_without_an_organization_id_anchor")
    if not source:
        blocked.append("watchlist_entry_without_a_source_id")

    if origin == "unknown":
        blocked.append("watchlist_source_not_recognised")
    if state == "unknown":
        blocked.append("watchlist_state_not_recognised")

    # A registry claim is checked against the registry this repository has.
    known = (
        known_registry_source_ids()
        if registry_source_ids is None
        else frozenset(registry_source_ids)
    )
    if origin in REGISTRY_BACKED_SOURCES and source and source not in known:
        blocked.append(UNKNOWN_REGISTRY_SOURCE)

    # And a fixture says so in its id, so nothing later mistakes it for one.
    if (
        origin == "controlled_fixture"
        and source
        and not source.startswith(FIXTURE_SOURCE_PREFIX)
    ):
        blocked.append(FIXTURE_PREFIX_MISSING)

    # Anything nobody vetted needs a human, and the row says so.
    human_review = origin in HUMAN_REVIEW_SOURCES or state == "needs_human_review"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "table_name": TABLE_NAME,
            "organization_id": str(anchor) if anchor else None,
            "source_id": source or None,
            "source_name": str(source_name or "").strip() or None,
            "jurisdiction": str(jurisdiction or "").strip() or None,
            "program_area": str(program_area or "").strip() or None,
            "tenant_id_label": str(tenant_id_label or "").strip() or None,
            "watchlist_state": state,
            "watchlist_source": origin,
            "fact_status": facts,
            "is_demo": bool(is_demo),
            "human_review_required": bool(human_review),
            "registry_source_count": len(known),
            "storage_allowed": not blocked,
            "write_performed": False,
            "rows_written": 0,
            # Constants. This module watches nothing and calls nobody.
            "source_monitoring_live": False,
            "live_source_called": False,
            "collector_activated": False,
            "network_calls": 0,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def add_watchlist_entry(
    *,
    connection: Any = None,
    entry_id: uuid.UUID | None = None,
    now: datetime | None = None,
    created_by_identity_id: Any = None,
    **fields: Any,
) -> dict[str, Any]:
    """Store one entry, if ``prepare_watchlist_entry`` permits it."""
    decision = prepare_watchlist_entry(**fields)
    blocked = list(decision["blocked_reasons"])
    moment = now or datetime.now(UTC)

    if connection is None:
        blocked.append("no_connection_supplied_so_nothing_was_written")

    # One live entry per organization and source. The partial unique index
    # enforces it; this reports the reason rather than an IntegrityError.
    if connection is not None and decision["storage_allowed"]:
        existing = int(
            connection.execute(
                sa.select(sa.func.count())
                .select_from(WATCHLIST)
                .where(
                    WATCHLIST.c.organization_id
                    == _as_uuid(decision["organization_id"]),
                    WATCHLIST.c.source_id == str(decision["source_id"]),
                    WATCHLIST.c.archived_at.is_(None),
                )
            ).scalar_one()
        )
        if existing:
            blocked.append("this_organization_already_watches_this_source")

    written = 0
    if decision["storage_allowed"] and connection is not None and not blocked:
        connection.execute(
            sa.insert(WATCHLIST).values(
                id=entry_id or uuid.uuid4(),
                organization_id=_as_uuid(decision["organization_id"]),
                is_demo=bool(decision["is_demo"]),
                tenant_id_label=decision["tenant_id_label"],
                source_id=str(decision["source_id"]),
                source_name=decision["source_name"],
                jurisdiction=decision["jurisdiction"],
                program_area=decision["program_area"],
                watchlist_state=decision["watchlist_state"],
                watchlist_source=decision["watchlist_source"],
                fact_status=decision["fact_status"],
                human_review_required=bool(decision["human_review_required"]),
                blocked_reasons=[],
                created_by_identity_id=_as_uuid(created_by_identity_id),
                created_at=moment,
                updated_at=moment,
                archived_at=None,
            )
        )
        written = 1

    return _json_safe(
        {
            **decision,
            "operation": "add_watchlist_entry",
            "entry_id": str(entry_id) if entry_id else None,
            "write_performed": bool(written),
            "rows_written": written,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def _row_to_entry(row: Any) -> dict[str, Any]:
    return {
        "entry_id": str(row["id"]),
        "organization_id": str(row["organization_id"]),
        "source_id": row["source_id"],
        "source_name": row["source_name"],
        "jurisdiction": row["jurisdiction"],
        "program_area": row["program_area"],
        "watchlist_state": row["watchlist_state"],
        "watchlist_source": row["watchlist_source"],
        "fact_status": row["fact_status"],
        "human_review_required": bool(row["human_review_required"]),
        "is_demo": bool(row["is_demo"]),
        "archived_at": row["archived_at"].isoformat() if row["archived_at"] else None,
        # Never monitored. Stated per row, so a reader of one entry does not
        # have to find the header to learn it.
        "source_monitoring_live": False,
        "last_checked_at": None,
    }


def list_watchlist(
    *,
    connection: Any = None,
    organization_id: Any = None,
    include_archived: bool = False,
    jurisdiction: Any = None,
) -> dict[str, Any]:
    """Every entry for one organization. Anchored; labels only narrow."""
    anchor = _as_uuid(organization_id)
    blocked: list[str] = []
    if anchor is None:
        blocked.append("read_without_a_uuid_shaped_organization_id_anchor")
    if connection is None:
        blocked.append("no_connection_supplied_so_nothing_was_read")

    rows: list[dict[str, Any]] = []
    if not blocked:
        query = sa.select(WATCHLIST).where(WATCHLIST.c.organization_id == anchor)
        if not include_archived:
            query = query.where(WATCHLIST.c.archived_at.is_(None))
        if str(jurisdiction or "").strip():
            query = query.where(WATCHLIST.c.jurisdiction == str(jurisdiction).strip())
        query = query.order_by(WATCHLIST.c.source_id)
        rows = [
            _row_to_entry(row) for row in connection.execute(query).mappings().all()
        ]

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "operation": "list_watchlist",
            "organization_id": str(anchor) if anchor else None,
            "rows_read": len(rows),
            "entries": rows,
            "active_count": sum(
                1 for row in rows if row["watchlist_state"] in ACTIVE_STATES
            ),
            "human_review_count": sum(
                1 for row in rows if row["human_review_required"]
            ),
            "source_monitoring_live": False,
            "live_source_called": False,
            "network_calls": 0,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def get_watchlist_entry(
    *, connection: Any = None, organization_id: Any = None, entry_id: Any = None
) -> dict[str, Any]:
    anchor = _as_uuid(organization_id)
    identifier = _as_uuid(entry_id)
    blocked: list[str] = []
    if anchor is None:
        blocked.append("read_without_a_uuid_shaped_organization_id_anchor")
    if identifier is None:
        blocked.append("read_without_a_uuid_shaped_entry_id")
    if connection is None:
        blocked.append("no_connection_supplied_so_nothing_was_read")

    row = None
    if not blocked:
        row = (
            connection.execute(
                sa.select(WATCHLIST).where(
                    WATCHLIST.c.organization_id == anchor,
                    WATCHLIST.c.id == identifier,
                )
            )
            .mappings()
            .first()
        )
        if row is None:
            blocked.append("no_watchlist_entry_for_this_organization")

    entry = _row_to_entry(row) if row is not None else {}
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "operation": "get_watchlist_entry",
            "organization_id": str(anchor) if anchor else None,
            "rows_read": 1 if row is not None else 0,
            **entry,
            "source_monitoring_live": False,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def archive_watchlist_entry(
    *,
    connection: Any = None,
    organization_id: Any = None,
    entry_id: Any = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Stop watching. The row stays, so the history stays."""
    anchor = _as_uuid(organization_id)
    identifier = _as_uuid(entry_id)
    blocked: list[str] = []
    if anchor is None:
        blocked.append("archive_without_a_uuid_shaped_organization_id_anchor")
    if identifier is None:
        blocked.append("archive_without_a_uuid_shaped_entry_id")
    if connection is None:
        blocked.append("no_connection_supplied_so_nothing_was_written")

    written = 0
    if not blocked:
        moment = now or datetime.now(UTC)
        result = connection.execute(
            sa.update(WATCHLIST)
            .where(
                WATCHLIST.c.organization_id == anchor,
                WATCHLIST.c.id == identifier,
                WATCHLIST.c.archived_at.is_(None),
            )
            .values(watchlist_state="archived", archived_at=moment, updated_at=moment)
        )
        written = int(result.rowcount or 0)
        if not written:
            blocked.append("no_live_watchlist_entry_for_this_organization")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "operation": "archive_watchlist_entry",
            "organization_id": str(anchor) if anchor else None,
            "entry_id": str(identifier) if identifier else None,
            "write_performed": bool(written),
            "rows_written": written,
            "rows_deleted": 0,
            "history_preserved": True,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def watchlist_invariant_failures(result: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if result.get("source_monitoring_live"):
        fails.append("claimed:source_monitoring_live")
    if result.get("live_source_called"):
        fails.append("claimed:live_source_called")
    if result.get("collector_activated"):
        fails.append("claimed:collector_activated")
    if result.get("network_calls"):
        fails.append(f"network_calls:{result.get('network_calls')}")
    if result.get("rows_deleted"):
        fails.append("a_watchlist_entry_was_deleted_rather_than_archived")

    if result.get("rows_written"):
        if result.get("blocked_reasons"):
            fails.append("wrote_a_watchlist_entry_alongside_blockers")
        if (
            result.get("watchlist_source") in REGISTRY_BACKED_SOURCES
            and result.get("registry_source_count") == 0
        ):
            fails.append("claimed_a_registry_entry_with_no_registry_to_check")

    for entry in result.get("entries") or []:
        if entry.get("source_monitoring_live"):
            fails.append(f"entry_claimed_monitoring:{entry.get('source_id')}")
        if entry.get("last_checked_at"):
            fails.append(f"entry_claimed_a_check:{entry.get('source_id')}")

    return fails
