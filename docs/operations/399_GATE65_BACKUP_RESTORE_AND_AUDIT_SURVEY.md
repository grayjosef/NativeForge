# 399 — Gate 65A: Backup / restore and audit vocabulary survey

Surveyed before implementing, because the repo already contains services with
"backup_restore" and "restore_rehearsal" in their names and building a parallel
layer next to them would repeat the mistake Gate 61 warned about.

## Files inspected

| File | Lines | What it is |
| --- | --- | --- |
| `services/gate32_backup_restore_service.py` | 62 | Block 73 demo contract |
| `services/gate32_backup_restore_assembler_service.py` | 62 | Block 73 demo surface assembler |
| `services/gate33_restore_rehearsal_service.py` | 91 | Block 77 modeled rehearsal |
| `services/gate33_restore_rehearsal_assembler_service.py` | — | Block 77 surface assembler |
| `services/production_storage_readiness_validator_service.py` | 105 | Block 42 readiness validator |
| `services/postgres_membership_directory_service.py` | — | Gate 64 storage posture |
| `alembic/versions/0002_sprint0_demo_rls.py` | — | `nf_audit_events` definition |
| `domain/enums.py` | — | `AuditAction` |
| `repositories/audit_events.py` | — | append / list |
| `scripts/` (127 entries) | — | no backup or restore script |

## Backup / restore: current state

**There is no backup or restore capability, and there never has been.**

The decisive finding: `grep -rn "pg_dump\|pg_restore" src/ scripts/` returns
**nothing**. No code in this repository has ever invoked a dump or a restore.

What does exist is a demo contract layer from the old campaign blocks:

- `gate32_backup_restore_service.resolve_backup_restore(...)` takes
  `non_prod_rehearsed: bool` and `restore_evidence_ref: str | None`, and
  promotes restore status to `validated_non_prod` when the caller passes **any
  truthy string**. The string is never opened, parsed, or checked.
- `gate33_restore_rehearsal_service.run_restore_rehearsal(...)` defaults
  `restore_attempted=True` and defaults its evidence refs to the literals
  `nf://gate33/non-prod-restore-rehearsal` and
  `nf://gate33/non-prod-backup-manifest`. Called with no arguments it reports a
  rehearsal that did not happen.

Those are honest as *demo surfaces* — they model what the UI should show — and
they are labelled non-prod throughout. They are not evidence of anything, and
they must not be mistaken for the restore proof the Gate 61 storage approval
asked for. Gate 65 does not modify them; it builds alongside with a service
whose readiness depends on execution rather than on a string being non-empty.

Tooling available on this host: `pg_dump` 16.15 and `pg_restore` 16.15.

## Audit vocabulary: current state

`AuditAction` in `src/nativeforge/domain/enums.py` — a `StrEnum` with **37
members**, all workflow verbs (artifact lifecycle, profiles, pursuits, form
packages, discovery, source checks, operator actions).

**None of the 13 security-critical verbs from doc 391 exists.** Confirmed by
parsing the class rather than grepping the file.

## Audit table / repository status

`nf_audit_events` (migration 0002) is real, org-scoped, `is_demo`-scoped, and
RLS-covered — Gate 62 proved those policies execute.

`repositories/audit_events.py` provides `append_org_audit_event(...)` and
`list_audit_events_for_org(...)`, already used by `repositories/pursuits.py` and
`repositories/evidence_pack.py`.

So audit persistence is missing *wiring*, not missing infrastructure.

One check that mattered for this gate: **`action` is `sa.String(64)` with no
`CHECK` constraint.** Migration 0018 adds enumerated CHECKs to
`nf_operator_actions`, but nothing constrains `nf_audit_events.action`. Adding
enum members is therefore a pure Python vocabulary change requiring no
migration and carrying no insert risk. The longest new verb,
`authority_sensitive_action_blocked`, is 34 characters and fits comfortably.

No test asserts an exact `AuditAction` member set, so additions break nothing.
(Grep reported matches in `tests/__pycache__/*.pyc` only — stale bytecode, not
source.)

## Exact gaps

**Backup / restore**

1. No backup policy is declared anywhere in the repo.
2. No backup automation exists or is configured.
3. PITR is neither supported-by-a-provider nor enabled — there is no provider.
4. No restore has ever been executed.
5. No restore artifact format is defined.
6. No RTO or RPO figures are recorded.
7. The existing Block 73/77 services accept an unvalidated string as proof.

**Audit**

8. 13 security verbs absent from `AuditAction`.
9. `organization_id` is `NOT NULL`, so `cross_org_access_attempt` cannot record
   both the claimed and the targeted organization. Storing the claimed org in
   the scoped column would hide the event from the org actually attacked.
10. No outcome, severity, correlation id, or actor-subject columns.
11. No retention policy and no purge job.

## What Gate 65 addresses

Gaps 1, 5, 6, 7 (fully), 2/3/4 (as an executable proof path that stays honest
about not having run), and gap 8. Gaps 9–11 are planned in doc 401 for
migration `0028` and deliberately not wired here.
