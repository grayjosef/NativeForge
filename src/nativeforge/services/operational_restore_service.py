"""Gate 153D: load an export into an isolated database, and refuse anything else.

## The target must not be the source

The Gate 65 harness says it plainly: "a restore proof that overwrites the live
database is an outage, not a proof." This enforces the same rule one layer down.
A restore requires an explicitly isolated target, and refuses when the target
URL matches the source.

## Hashes are checked before rows are written, not after

An export carries a sha256 per table. If the payload does not hash to what it
claims, the restore refuses that table rather than loading it and reporting the
mismatch afterwards - a restore that writes first and checks second has already
done the damage by the time it tells you.

## Nothing is invented

A table absent from the payload stays absent. A row referring to something the
payload does not contain is loaded as it is, with the dangling reference intact,
because a restore that filled in the missing end would be manufacturing evidence
- and the Gate 152 verification that runs afterwards is what reports the gap.

Legacy gaps survive a restore as legacy gaps. That is the correct outcome and a
test asserts it.

## Rows are written back the way they were read

The export reads through `sa.text` and serialises to JSON, so a timestamp leaves
as an ISO string. Writing that back through a typed `sa.Table` fails on SQLite
("only accepts Python datetime") and, worse, succeeding would have re-rendered
the value: SQLite stores a coerced datetime as `2026-01-02 03:04:05.000000`
where the export held `2026-01-02T03:04:05`. The verification rehashes the
restored rows, so a restore that changed the representation would report a hash
mismatch against a database holding exactly the right data.

So the insert goes back through `sa.text` with bound parameters, and what was
read is what is written. This is the controlled dev/demo SQLite path, and it is
a stated limitation: a PostgreSQL target would need per-type coercion, which is
one of the things the provider-level Gate 65 harness does for itself.

## No production, no customer data, no real organization

The real organization is refused by name. A payload whose rows are not fixtures
is refused as a whole rather than filtered, because a mixed payload means the
export that produced it was wrong and loading half of it would hide that.
"""

from __future__ import annotations

import json
import uuid
from typing import Any

import sqlalchemy as sa

from nativeforge.services.operational_backup_export_service import (
    REAL_ORGANIZATION_ID,
    table_payload_sha256,
)
from nativeforge.services.operational_backup_manifest_service import (
    INCLUDED_TABLES,
    MANIFEST_MIGRATION_HEAD,
)

SCHEMA_VERSION = "nf_operational_restore_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: The only target kind a restore will write to.
ISOLATED_TARGET = "isolated_temporary_database"

BLOCK_NOT_ISOLATED = "restore_target_is_not_isolated"
BLOCK_SAME_AS_SOURCE = "restore_target_is_the_source_database"
BLOCK_HEAD_MISMATCH = "migration_head_mismatch"
BLOCK_HASH_MISMATCH = "payload_hash_mismatch"
BLOCK_NOT_FIXTURE = "payload_contains_a_non_fixture_row"
BLOCK_REAL_ORG = "real_organization_refused_by_name"
BLOCK_FORBIDDEN_FIELD = "payload_contains_a_forbidden_field"

#: What this restore does not do, stated rather than left to be discovered.
RESTORE_LIMITATIONS: tuple[str, ...] = (
    "rows are written through sa.text so the stored representation survives; "
    "a PostgreSQL target would need per-type coercion this does not do",
    "the organizations row is a precondition the target must already have; it "
    "is never restored, so the real organization cannot arrive this way",
    "a row whose link points outside the payload is restored with the dangling "
    "link intact - the verification reports it, the restore does not fix it",
    "this is not production backup, and proves nothing about a managed instance",
)

#: Field names that must never arrive in a payload. Unlike the manifest's
#: review hints, these are exact names on tables the manifest includes - a
#: payload carrying one means the export was built by something else.
FORBIDDEN_FIELDS: frozenset[str] = frozenset(
    {
        "email",
        "recipient",
        "recipient_email",
        "address",
        "subject",
        "access_token",
        "id_token",
        "refresh_token",
        "cookie",
        "state_hash",
        "pkce_verifier",
        "pkce_verifier_hash",
        "pkce_verifier_encrypted",
        "code_challenge",
        "client_secret",
        "rendered_body",
        "document_body",
        "body_bytes",
        "object_bytes",
    }
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _as_uuid(value: Any) -> uuid.UUID | None:
    try:
        return uuid.UUID(str(value))
    except Exception:  # noqa: BLE001
        return None


def _is_fixture(row: dict[str, Any]) -> bool:
    if row.get("is_demo") in (True, 1):
        return True
    return str(row.get("fact_status") or "") == "demo_fixture"


def restore_backup(
    *,
    target_connection: Any = None,
    export: dict[str, Any] | None = None,
    target_kind: str | None = None,
    source_url: str | None = None,
    target_url: str | None = None,
    target_migration_head: str | None = None,
) -> dict[str, Any]:
    """Load an export into an isolated target. Refuses every other target."""
    blocked: list[str] = []
    payload = export or {}

    if target_connection is None:
        blocked.append("no_target_connection_supplied")
    if target_kind != ISOLATED_TARGET:
        blocked.append(BLOCK_NOT_ISOLATED)
    if source_url and target_url and str(source_url) == str(target_url):
        blocked.append(BLOCK_SAME_AS_SOURCE)

    if not payload.get("exported"):
        blocked.append("export_payload_was_not_exported")

    org = _as_uuid(payload.get("organization_id"))
    if str(payload.get("organization_id") or "").strip().lower() == (
        REAL_ORGANIZATION_ID
    ):
        blocked.append(BLOCK_REAL_ORG)
    if org is None:
        blocked.append("export_payload_has_no_organization")

    head = str(target_migration_head or MANIFEST_MIGRATION_HEAD)
    payload_head = str(payload.get("migration_head") or "")
    if payload_head and payload_head != head:
        blocked.append(BLOCK_HEAD_MISMATCH)

    tables = payload.get("tables") or {}

    # Hashes and shapes are checked BEFORE anything is written.
    hash_mismatches: list[str] = []
    forbidden_hits: list[str] = []
    non_fixture: list[str] = []

    for name, entry in sorted(tables.items()):
        rows = entry.get("rows") or []
        if entry.get("payload_sha256") != table_payload_sha256(rows):
            hash_mismatches.append(name)
        for row in rows:
            present = FORBIDDEN_FIELDS & set(row)
            if present:
                forbidden_hits.append(f"{name}:{sorted(present)[0]}")
                break
            if not _is_fixture(row):
                non_fixture.append(name)
                break

    if hash_mismatches:
        blocked.append(BLOCK_HASH_MISMATCH)
    if forbidden_hits:
        blocked.append(BLOCK_FORBIDDEN_FIELD)
    if non_fixture:
        blocked.append(BLOCK_NOT_FIXTURE)

    if blocked:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "scope": CONTROLLED_SCOPE,
                "restored": False,
                "target_kind": target_kind,
                "restored_tables": {},
                "rows_restored_total": 0,
                "hash_mismatched_tables": sorted(hash_mismatches),
                "forbidden_field_hits": sorted(forbidden_hits),
                "non_fixture_tables": sorted(non_fixture),
                "blocked_reasons": sorted(set(blocked)),
                "restore_limitations": list(RESTORE_LIMITATIONS),
                "evidence_fabricated": False,
                "real_organization_touched": False,
            }
        )

    inspector = sa.inspect(target_connection)
    present_tables = set(inspector.get_table_names())
    by_name = {entry["table"]: entry for entry in INCLUDED_TABLES}

    restored: dict[str, Any] = {}
    total = 0

    for name, entry in sorted(tables.items()):
        rows = entry.get("rows") or []
        if name not in present_tables:
            restored[name] = {
                "rows_restored": 0,
                "skipped": len(rows),
                "skipped_reason": "table_absent_from_the_target",
            }
            continue
        if not rows:
            restored[name] = {"rows_restored": 0, "skipped": 0}
            continue

        target_columns = {c["name"] for c in inspector.get_columns(name)}

        written = 0
        skipped = 0
        # A field the target has no column for is dropped, and COUNTED. A row
        # narrowed on the way in would hash differently on the way out, and
        # the verification would report that as a mismatch without saying why.
        dropped_fields: set[str] = set()
        for row in rows:
            usable = {k: v for k, v in row.items() if k in target_columns}
            dropped_fields |= set(row) - target_columns
            if not usable:
                skipped += 1
                continue
            fields = sorted(usable)
            target_connection.execute(
                sa.text(
                    f"INSERT INTO {name} ({', '.join(fields)}) "
                    f"VALUES ({', '.join(':' + f for f in fields)})"
                ),
                usable,
            )
            written += 1

        total += written
        restored[name] = {
            "rows_restored": written,
            "skipped": skipped,
            "dropped_fields": sorted(dropped_fields),
            "hash_fields": (by_name.get(name) or {}).get("hash_fields", []),
        }

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "restored": True,
            "target_kind": target_kind,
            "organization_id": str(org),
            "migration_head": head,
            "restored_tables": restored,
            "rows_restored_total": total,
            "hash_mismatched_tables": [],
            "forbidden_field_hits": [],
            "non_fixture_tables": [],
            "blocked_reasons": [],
            "restore_limitations": list(RESTORE_LIMITATIONS),
            # Nothing was invented to fill a dangling reference.
            "evidence_fabricated": False,
            "legacy_gaps_backfilled": False,
            "real_organization_touched": False,
            "email_sent": False,
            "live_source_called": False,
            "object_store_contacted": False,
        }
    )


def restore_invariant_failures(restore: dict[str, Any]) -> list[str]:
    """Refuse a restore that wrote somewhere it should not have."""
    fails: list[str] = []

    if restore.get("restored"):
        if restore.get("blocked_reasons"):
            fails.append("restored_alongside_blockers")
        if restore.get("target_kind") != ISOLATED_TARGET:
            fails.append("restored_into_a_target_that_is_not_isolated")
        if restore.get("hash_mismatched_tables"):
            fails.append("restored_despite_a_hash_mismatch")
        if restore.get("forbidden_field_hits"):
            fails.append("restored_despite_a_forbidden_field")
        if restore.get("non_fixture_tables"):
            fails.append("restored_despite_a_non_fixture_row")

        counted = sum(
            entry.get("rows_restored", 0)
            for entry in (restore.get("restored_tables") or {}).values()
        )
        if counted != restore.get("rows_restored_total"):
            fails.append("rows_restored_total_disagrees")

        # A narrowed row is not a restored row, whatever the count says.
        for name, entry in (restore.get("restored_tables") or {}).items():
            if entry.get("dropped_fields"):
                fails.append(f"restored_a_narrowed_row:{name}")

    if restore.get("evidence_fabricated"):
        fails.append("restore_fabricated_evidence")
    if restore.get("legacy_gaps_backfilled"):
        fails.append("restore_backfilled_legacy_gaps")

    for flag in (
        "real_organization_touched",
        "email_sent",
        "live_source_called",
        "object_store_contacted",
    ):
        if restore.get(flag):
            fails.append(f"restore_claimed_to_have:{flag}")

    return sorted(set(fails))
