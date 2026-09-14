"""Gate 153F: the backup manifest, export accounting and lane, read-only.

```text
GET /v1/nf/demo/orgs/{org}/backup-restore/manifest
GET /v1/nf/demo/orgs/{org}/backup-restore/export-summary
GET /v1/nf/demo/orgs/{org}/backup-restore/table/{table}
GET /v1/nf/demo/orgs/{org}/backup-restore/readiness
```

GET only. Nothing here exports to a file, restores anything, or writes a row.

## No route returns the rows

`build_backup_export` returns row bodies, and these routes return counts,
column names, exclusions and hashes - never the rows themselves. A backup
endpoint that streamed the payload would be a data-egress surface reachable
with a session cookie, and the export exists to be handed to a restore, not to
a browser. The hash is enough to tell a reader whether two exports agree.

## Which conditions a request can actually measure

Three of the eight conditions need a second database to exist, and a request
does not have one. Rather than declaring them true with a comment, the response
splits them:

```text
measured_in_this_request   the manifest, the org scoping, the per-table hashes
measured_by_the_verifier   the restore, both refusals, the replay, the gaps
```

Every condition names which, so nothing in the response claims to have been
proved by a read that could not have proved it. `scripts/verify_nativeforge_
backup_restore_readiness.sh` is where the other five are measured, and it does
run the refused restores rather than asserting they would refuse.
"""

from __future__ import annotations

import uuid
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from nativeforge.api.customer_org_context_dependency import require_demo_org_session
from nativeforge.api.deps_db import get_db_session
from nativeforge.api.org_context import OrgContext
from nativeforge.api.post_award_common import envelope, same_org
from nativeforge.services.audit_replay_service import find_legacy_gaps
from nativeforge.services.operational_backup_export_service import (
    build_backup_export,
    export_invariant_failures,
)
from nativeforge.services.operational_backup_manifest_service import (
    build_backup_manifest,
    manifest_invariant_failures,
)
from nativeforge.services.operational_backup_restore_readiness_service import (
    CONDITIONS,
    build_operational_restore_readiness,
    operational_restore_readiness_invariant_failures,
)
from nativeforge.services.operational_restore_service import RESTORE_LIMITATIONS

router = APIRouter(prefix="/v1/nf/demo/orgs", tags=["backup-restore-demo"])

#: Conditions a single read can prove, and the ones it cannot.
MEASURED_IN_REQUEST: frozenset[str] = frozenset(
    {
        "manifest_classified_by_meaning",
        "export_scoped_to_one_organization",
        "export_carries_a_hash_per_table",
    }
)
MEASURED_BY_VERIFIER: frozenset[str] = frozenset(CONDITIONS) - MEASURED_IN_REQUEST


def _table_summary(name: str, entry: dict[str, Any]) -> dict[str, Any]:
    """Accounting for one table. Never the rows."""
    return {
        "table": name,
        "row_count": entry.get("row_count", 0),
        "payload_sha256": entry.get("payload_sha256"),
        "columns": entry.get("columns", []),
        "excluded_fields": entry.get("excluded_fields", []),
        "hash_fields": entry.get("hash_fields", []),
        "archive_field": entry.get("archive_field"),
        "absent_from_this_database": entry.get("absent_from_this_database", False),
    }


def _export_or_refuse(db: Session, org_id: uuid.UUID) -> dict[str, Any]:
    export = build_backup_export(
        connection=db.connection(),
        organization_id=str(org_id),
        migration_head=None,
    )
    if export.get("leaked_shapes"):
        raise HTTPException(status_code=500, detail="export_payload_refused")
    if export_invariant_failures(export):
        raise HTTPException(status_code=500, detail="export_refused")
    return export


@router.get("/{org_id}/backup-restore/manifest")
def get_backup_manifest(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
) -> dict[str, Any]:
    """Which tables may be exported, and the reason for each one."""
    same_org(org_id, ctx)
    manifest = build_backup_manifest()
    failures = manifest_invariant_failures(manifest)
    if failures:
        raise HTTPException(status_code=500, detail="manifest_refused")
    return envelope({**manifest, "invariant_failures": failures})


@router.get("/{org_id}/backup-restore/export-summary")
def get_export_summary(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """What an export of this organization would contain. Counts, not rows."""
    same_org(org_id, ctx)
    export = _export_or_refuse(db, org_id)

    return envelope(
        {
            "organization_id": export["organization_id"],
            "scope": export["scope"],
            "migration_head": export["migration_head"],
            "table_count": export["table_count"],
            "row_count_total": export["row_count_total"],
            "skipped_non_fixture_rows": export["skipped_non_fixture_rows"],
            "tables": [
                _table_summary(name, entry)
                for name, entry in sorted((export.get("tables") or {}).items())
            ],
            "rows_are_never_returned_by_this_route": (
                "an export exists to be handed to a restore, not to a browser"
            ),
            "restore_limitations": list(RESTORE_LIMITATIONS),
            "rows_written": 0,
            "production_backup_ready": False,
        }
    )


@router.get("/{org_id}/backup-restore/table/{table_name}")
def get_table_export_summary(
    org_id: uuid.UUID,
    table_name: str,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """One table's export accounting. Counts and a hash, not rows."""
    same_org(org_id, ctx)
    export = _export_or_refuse(db, org_id)
    entry = (export.get("tables") or {}).get(table_name)

    if entry is None:
        # The same answer for "not in the manifest" as for "does not exist".
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "error": "table_not_in_the_backup_manifest",
                "manifest_tables": build_backup_manifest()["table_names"],
            },
        )

    return envelope(_table_summary(table_name, entry))


@router.get("/{org_id}/backup-restore/readiness")
def get_backup_restore_readiness(
    org_id: uuid.UUID,
    ctx: Annotated[OrgContext, Depends(require_demo_org_session)],
    db: Annotated[Session, Depends(get_db_session)],
) -> dict[str, Any]:
    """The lane, with each condition labelled by what actually measured it."""
    same_org(org_id, ctx)
    connection = db.connection()

    manifest = build_backup_manifest()
    export = _export_or_refuse(db, org_id)
    gaps = find_legacy_gaps(connection=connection, organization_id=str(org_id))

    # Measured here, by this request.
    manifest_ok = not manifest_invariant_failures(manifest)
    scoped = bool(
        export["exported"]
        and export["organization_id"] == str(org_id)
        and not export["skipped_non_fixture_rows"]
        and not export["leaked_shapes"]
    )
    hashed = bool(export["tables"]) and all(
        entry.get("payload_sha256") for entry in (export.get("tables") or {}).values()
    )

    # NOT measured here. A request has no second database, so these stay false
    # in this response rather than being declared true with a comment. The
    # verifier measures them, and its result is the lane's verdict.
    readiness = build_operational_restore_readiness(
        manifest_classified_by_meaning=manifest_ok,
        export_scoped_to_one_organization=scoped,
        export_carries_a_hash_per_table=hashed,
        restore_into_isolated_target_works=False,
        restore_into_source_refused=False,
        restore_into_live_refused=False,
        restored_state_passes_the_gate_152_replay=False,
        legacy_gaps_preserved=False,
        source_legacy_gap_count=gaps["legacy_gap_count"],
        restored_legacy_gap_count=gaps["legacy_gap_count"],
        exported_row_count=export["row_count_total"],
        restored_row_count=0,
        email_delivery=False,
        source_monitoring_live=False,
        object_store_configured=False,
        customer_data_backed_up=False,
    )
    failures = operational_restore_readiness_invariant_failures(readiness)
    if failures:
        raise HTTPException(status_code=500, detail="readiness_refused")

    return envelope(
        {
            **readiness,
            "measured_in_this_request": sorted(MEASURED_IN_REQUEST),
            "measured_by_the_verifier": sorted(MEASURED_BY_VERIFIER),
            "why_the_split": (
                "five conditions need a second database to exist and a request "
                "does not have one. They are reported false here rather than "
                "declared true, and "
                "scripts/verify_nativeforge_backup_restore_readiness.sh is "
                "where they are measured - by running the restore and the two "
                "refused restores, not by asserting they would refuse."
            ),
            "lane_verdict_comes_from_the_verifier": True,
            "invariant_failures": failures,
        }
    )
