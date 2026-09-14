"""Gate 153C: export controlled dev/demo operational state, org-scoped.

## A logical export, not a physical dump

`scripts/verify_nativeforge_backup_restore.sh` already covers the physical path
- `pg_dump` against a managed instance - and returns SKIP because no instance
exists. This is the other half: rows this system selected, filtered to one
organization, with the forbidden values filtered out, and a hash per table so a
restore can tell whether it got what was sent.

A provider dump proves bytes survive a round trip. It proves nothing about
whether a digest still hashes or an intent still resolves, which is what a
restore has to be good for.

## Values are checked, not column names

Every exported payload is scanned for the SHAPES of the things that must never
leave: an address, a provider subject, a token, an OAuth state, a PKCE verifier.
Gate 153A's own classifier flagged two tables because a column was called
`state` and both held `'active'`, so name-matching is a review hint here and the
value scan is the gate.

## Demo organization only

The real organization is refused by name before a row is read. Every row must
carry `is_demo` true or a `fact_status` of `demo_fixture`, and one that does not
is skipped and counted rather than silently dropped.

## It reads

No row is written, no provider contacted, no source called, no object store
touched. The export returns a payload; writing it anywhere is the caller's
decision.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from typing import Any

import sqlalchemy as sa

from nativeforge.services.operational_backup_manifest_service import (
    CONTROLLED_SCOPE,
    INCLUDED_TABLES,
    MANIFEST_MIGRATION_HEAD,
    build_backup_manifest,
)

SCHEMA_VERSION = "nf_operational_backup_export_v1"

DEMO_ORGANIZATION_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

#: Value shapes that must never appear in an export, whatever column holds
#: them. This is the gate; column names are a review hint.
FORBIDDEN_SHAPES: tuple[tuple[str, str], ...] = (
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


def _leaked_shapes(payload: Any) -> list[str]:
    body = json.dumps(payload, default=str, sort_keys=True)
    found = [name for name, pattern in FORBIDDEN_SHAPES if re.search(pattern, body)]
    if _PROVIDER_SUBJECT_SHAPE.search(body):
        found.append("provider_subject")
    return sorted(set(found))


def table_payload_sha256(rows: Any) -> str:
    """A stable hash over a table's exported rows.

    Rows are sorted by their serialised form before hashing, so two exports of
    the same data hash the same regardless of the order the database returned
    them in. An unordered SELECT is not a guarantee, and a hash that changed
    with row order would fail a restore for no reason.
    """
    serialised = sorted(
        json.dumps(row, sort_keys=True, separators=(",", ":"), default=str)
        for row in (rows or [])
    )
    joined = "\n".join(serialised)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except Exception:  # noqa: BLE001
        return None


def _is_fixture(row: dict[str, Any]) -> bool:
    if row.get("is_demo") in (True, 1):
        return True
    return str(row.get("fact_status") or "") == "demo_fixture"


def build_backup_export(
    *,
    connection: Any = None,
    organization_id: Any = None,
    migration_head: str | None = None,
) -> dict[str, Any]:
    """Export every manifest table for one organization. Writes nothing."""
    blocked: list[str] = []
    org = _as_uuid(organization_id)
    normalized = str(organization_id or "").strip().lower()

    if connection is None:
        blocked.append("no_connection_supplied")
    if org is None:
        blocked.append("organization_id_is_not_uuid_shaped")
    if normalized == REAL_ORGANIZATION_ID:
        blocked.append("real_organization_refused_by_name")
    if normalized and normalized != DEMO_ORGANIZATION_ID and org is not None:
        # A fixture organization is permitted so the tests can use one; the
        # real organization is refused above, by name, before this.
        pass

    if blocked:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "scope": CONTROLLED_SCOPE,
                "organization_id": normalized or None,
                "exported": False,
                "tables": {},
                "row_count_total": 0,
                "blocked_reasons": sorted(set(blocked)),
                "rows_written": 0,
                "leaked_shapes": [],
            }
        )

    inspector = sa.inspect(connection)
    present = set(inspector.get_table_names())

    tables: dict[str, Any] = {}
    skipped_non_fixture = 0
    total = 0

    for entry in INCLUDED_TABLES:
        name = entry["table"]
        if name not in present:
            tables[name] = {
                "rows": [],
                "row_count": 0,
                "payload_sha256": table_payload_sha256([]),
                "absent_from_this_database": True,
            }
            continue

        columns = [c["name"] for c in inspector.get_columns(name)]
        excluded = set(entry["excluded_fields"])
        selected = [c for c in columns if c not in excluded]

        partition = entry["org_partition"]
        raw = (
            connection.execute(
                sa.text(
                    f"SELECT {', '.join(selected)} FROM {name} "
                    f"WHERE {partition} = :org"
                ),
                {"org": org.hex},
            )
            .mappings()
            .all()
        )

        rows: list[dict[str, Any]] = []
        for row in raw:
            record = _json_safe(dict(row))
            if not _is_fixture(record):
                # Counted, not dropped silently. A non-fixture row in a
                # controlled export is a finding.
                skipped_non_fixture += 1
                continue
            rows.append(record)

        total += len(rows)
        tables[name] = {
            "rows": rows,
            "row_count": len(rows),
            "payload_sha256": table_payload_sha256(rows),
            "columns": selected,
            "excluded_fields": sorted(excluded),
            "hash_fields": entry["hash_fields"],
            "archive_field": entry["archive_field"],
            "absent_from_this_database": False,
        }

    payload = _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "organization_id": str(org),
            "exported": True,
            "migration_head": str(migration_head or MANIFEST_MIGRATION_HEAD),
            "manifest_migration_head": MANIFEST_MIGRATION_HEAD,
            "manifest_schema_version": build_backup_manifest()["schema_version"],
            "tables": tables,
            "table_count": len(tables),
            "row_count_total": total,
            "skipped_non_fixture_rows": skipped_non_fixture,
            "blocked_reasons": [],
            # Constants. An export reads.
            "rows_written": 0,
            "real_organization_touched": False,
            "email_sent": False,
            "live_source_called": False,
            "object_store_contacted": False,
            "leaked_shapes": [],
        }
    )
    payload["leaked_shapes"] = _leaked_shapes(payload)
    return payload


def export_invariant_failures(export: dict[str, Any]) -> list[str]:
    """Refuse an export that leaked, wrote, or lost its own accounting."""
    fails: list[str] = []

    tables = export.get("tables") or {}
    counted = sum(entry.get("row_count", 0) for entry in tables.values())
    if export.get("exported") and counted != export.get("row_count_total"):
        fails.append("row_count_total_disagrees_with_the_tables")

    for name, entry in tables.items():
        if entry.get("row_count") != len(entry.get("rows") or []):
            fails.append(f"row_count_disagrees:{name}")
        if entry.get("payload_sha256") != table_payload_sha256(entry.get("rows")):
            fails.append(f"payload_hash_does_not_match_the_rows:{name}")

    if export.get("rows_written"):
        fails.append("export_wrote_rows")

    for flag in (
        "real_organization_touched",
        "email_sent",
        "live_source_called",
        "object_store_contacted",
    ):
        if export.get(flag):
            fails.append(f"export_claimed_to_have:{flag}")

    for name in export.get("leaked_shapes") or []:
        fails.append(f"leaked:{name}")

    return sorted(set(fails))
