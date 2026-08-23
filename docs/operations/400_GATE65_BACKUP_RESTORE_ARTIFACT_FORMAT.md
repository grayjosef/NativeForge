# 400 — Gate 65D: Restore proof artifact format

The Gate 61 storage approval requires "at least one restore test recorded as an
artifact". This defines what that artifact is, so the requirement can be
satisfied by a file rather than by an assertion in a chat log.

**No artifact of this kind exists yet.** No restore has been executed. Every
value in the sample below is fabricated for illustration.

## Recovery objectives

These are the documented targets. They are objectives, not measurements — no
recovery has been timed, and the first real restore drill may well show they
are wrong, which is a good reason to run one.

| Objective | Target | Meaning |
| --- | --- | --- |
| **RTO** | **240 minutes** | Maximum acceptable time from decision-to-restore until the application serves traffic again. |
| **RPO** | **60 minutes** | Maximum acceptable data loss, measured backwards from the incident. |

RPO of 60 minutes implies backups at least hourly, or PITR. Daily-only backups
would give an RPO closer to 1440 minutes, so **daily backups alone do not meet
this RPO** — that gap must be closed by PITR or by more frequent backups before
production storage can be called live.

`rpo_minutes` should be less than or equal to `rto_minutes` in almost every
sane configuration. The readiness service warns when it is not, because the two
being swapped is a common transcription error.

## Field definitions

| Field | Type | Required | Notes |
| --- | --- | --- | --- |
| `artifact_id` | string | yes | Stable unique id, `nf_restore_<UTC stamp>` |
| `timestamp` | ISO-8601 UTC | yes | When the artifact was written |
| `environment` | string | yes | `staging`, `dr-drill`, `dev`. Never `production` for a drill into a throwaway target |
| `provider` | string | yes | Managed Postgres provider name |
| `database_identifier_redacted` | string | yes | Redacted connection identifier. **Must never contain a password** |
| `backup_source` | object | yes | `{type, created_at, size_bytes, checksum}` |
| `restore_target` | object | yes | `{identifier_redacted, was_empty, is_throwaway}` |
| `restore_type` | enum | yes | `full` \| `pitr` \| `partial` |
| `pitr_used` | bool | yes | Whether the restore replayed WAL to a point in time |
| `pitr_target_time` | ISO-8601 UTC \| null | if `pitr_used` | The point recovered to |
| `rto_minutes` | int | yes | Target in force at drill time |
| `rpo_minutes` | int | yes | Target in force at drill time |
| `started_at` | ISO-8601 UTC | yes | Restore start |
| `completed_at` | ISO-8601 UTC | yes | Restore finish |
| `duration_seconds` | int | yes | Measured, not estimated |
| `rto_met` | bool | yes | `duration_seconds / 60 <= rto_minutes` |
| `row_count_checks` | array | yes | Per-table `{table, expected, actual, match}` |
| `migration_head_before` | string | yes | Alembic head on the source |
| `migration_head_after` | string | yes | Alembic head on the restored target |
| `migration_head_match` | bool | yes | A restore landing at a different head is a failed restore |
| `rls_proof_after_restore` | object | yes | `{executed, result, harness, checks_passed}` |
| `operator` | string | yes | Who ran it |
| `result` | enum | yes | `passed` \| `failed` \| `blocked` |
| `blocked_reasons` | array | yes | Empty when `passed` |
| `redactions_confirmed` | bool | yes | Someone confirmed no credential is present |

### Two fields that are easy to omit and shouldn't be

**`rls_proof_after_restore`.** A restored database that came back without its
row-level security policies is not a recovered system, it is a tenant-isolation
incident wearing a recovery costume. `pg_dump --no-owner --no-privileges` does
carry policy definitions, but ownership and role grants change on restore, and
`FORCE ROW LEVEL SECURITY` combined with a target-side owner mismatch can
silently produce a database where the app role sees everything. Re-running
`verify_nativeforge_postgres_rls.sh --verify-rls` against the restored target
is the only way to know. The readiness service blocks on
`rls_not_reproven_after_restore` for exactly this reason.

**`migration_head_match`.** Restoring a dump taken at head `0027` into a target
already at `0030` gives a database that matches neither. Recording both heads
makes that visible instead of surprising.

## Sample — fabricated values, no real system

```json
{
  "artifact_id": "nf_restore_20260901T031500Z",
  "timestamp": "2026-09-01T03:22:41Z",
  "environment": "dr-drill",
  "provider": "example-managed-postgres",
  "database_identifier_redacted": "postgresql://nf_app:***@db-drill.example.internal:5432/nativeforge_drill",
  "backup_source": {
    "type": "automated_daily",
    "created_at": "2026-09-01T02:00:00Z",
    "size_bytes": 184320512,
    "checksum": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
  },
  "restore_target": {
    "identifier_redacted": "postgresql://nf_app:***@db-drill.example.internal:5432/nativeforge_drill",
    "was_empty": true,
    "is_throwaway": true
  },
  "restore_type": "full",
  "pitr_used": false,
  "pitr_target_time": null,
  "rto_minutes": 240,
  "rpo_minutes": 60,
  "started_at": "2026-09-01T03:15:00Z",
  "completed_at": "2026-09-01T03:22:18Z",
  "duration_seconds": 438,
  "rto_met": true,
  "row_count_checks": [
    { "table": "organizations", "expected": 12, "actual": 12, "match": true },
    { "table": "nf_org_memberships", "expected": 34, "actual": 34, "match": true },
    { "table": "nf_audit_events", "expected": 91204, "actual": 91204, "match": true }
  ],
  "migration_head_before": "0027",
  "migration_head_after": "0027",
  "migration_head_match": true,
  "rls_proof_after_restore": {
    "executed": true,
    "harness": "scripts/verify_nativeforge_postgres_rls.sh --verify-rls",
    "result": "PASS",
    "checks_passed": 11
  },
  "operator": "example-operator",
  "result": "passed",
  "blocked_reasons": [],
  "redactions_confirmed": true
}
```

## Rules

1. **Never commit an artifact containing a live identifier.** Artifacts live
   under `artifacts/gate65_backup_restore/`, which is untracked.
2. `database_identifier_redacted` and `restore_target.identifier_redacted` pass
   through the same redaction the harness uses. A password reaching this file
   is a credential leak into a document people paste into tickets.
3. `result: "passed"` requires `migration_head_match`, every
   `row_count_checks[].match`, `rls_proof_after_restore.result == "PASS"`, and
   `rto_met`. Any false makes it `failed`.
4. An artifact is not evidence on its own. `backup_restore_readiness_service`
   requires **both** a recorded artifact and an executed restore, and blocks on
   `restore_artifact_without_execution` when a file appears without one.
