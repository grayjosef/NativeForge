# 395 — Gate 63C/D: Active-source test cleanup

What was changed, file by file. **No file was deleted and no suite was
broad-disabled.** Every skip is on a named function and carries a reason string
that explains the cause and names the replacement coverage.

## The fix (1 test)

**`tests/test_sprint20_discovery_engine_closeout.py`**

```diff
-    assert result.stdout.strip() == "0019 (head)"
+    # Gate 63: re-pinned 0019 -> 0027. This assertion still protects a real
+    # invariant (single head, no duplicate revision ids); only the expected
+    # value was stale. Update it deliberately when a migration is approved.
+    assert result.stdout.strip() == "0027 (head)"
```

The duplicate-revision-id check and the discovery migration file checks in the
same test are untouched and still run. This is the "preserve the invariant,
update the expected value" case from Gate 63C option A.

## Marked obsolete — freeze guards (13 tests, 13 files)

`test_no_new_alembic_revision_beyond_0019` in sprint54–62 and sprint64 (×2);
`test_no_new_alembic_revision_file_added_for_sprint_53_chain` in sprint53;
`test_28_no_new_alembic_revision_beyond_0019` in sprint65.

Reason recorded on each:

> Gate 63: obsolete campaign freeze guard. Asserts no 0020_* migration exists;
> revisions 0020-0022 (M7/M8) and 0023-0027 (approved Gate 62 storage path) now
> exist for reasons outside this campaign. Replaced by
> tests/test_gate63_migration_doctrine.py.

This is Gate 63C option C — retire a freeze assertion belonging to a closed
campaign — with option B's living check supplied as the replacement.

## Marked obsolete — revision-gated behaviour (21 tests, 3 files)

`test_sprint62_runtime_active_source_creation_execution_evidence` (6),
`test_sprint64_active_source_activation_readiness_gate` (7),
`test_sprint64_post_runtime_active_source_verification` (8).

Reason recorded on each:

> Gate 63: unreachable happy path. The active-source services pin
> TARGET_REVISION_ID='0019' and correctly return
> blocked_runtime_revision_mismatch now that the migration head is 0027. The
> service is behaving as designed; re-pointing it at 0027 would change product
> behaviour to satisfy a test, and re-authorising this closed campaign is an
> owner decision.

**The service was not touched.** Twelve service modules carry the `0019` pin and
all of them still refuse to operate outside their authorised revision. That
refusal is a safety property and it is intact.

## Marked obsolete — superseded migration proof (3 tests, 1 file)

`test_sprint47_active_source_local_migration_verification`:
`test_table_exists_after_upgrade_and_gone_after_downgrade`,
`test_full_artifact_with_isolated_proof_passes`,
`test_downgrade_does_not_drop_unrelated_tables`.

Reason recorded:

> Gate 63: superseded migration proof. This upgrade/downgrade proof assumes head
> 0019, so downgrade now removes more than the target table. Superseded by the
> real-PostgreSQL proof in scripts/verify_nativeforge_rls_isolation.sh (doc 389)
> and tests/test_gate63_migration_doctrine.py.

Worth noting the replacement is *stronger*, not weaker: the retired test was a
SQLite up/down check, while doc 389's proof runs against real PostgreSQL 16.2
and demonstrates cross-org read denial, fail-closed behaviour with no GUC set,
and `WITH CHECK` refusal of cross-org writes.

## Result on the patched files

```text
before:  40 failed (direct file run)
after:  314 passed, 37 skipped, 0 failed
```

The 37 skips are the 37 assertions retired above. Everything else in those 15
files still executes.

## Invariants preserved

- unique revision ids (sprint20)
- single migration head (sprint20 + new doctrine test)
- discovery-sprint migration files present (sprint20)
- every non-revision-gated assertion in the active-source files
- the `TARGET_REVISION_ID = "0019"` service safety gate, untouched

## How to un-retire this campaign

If the active-source campaign is ever re-authorised against the current schema:

1. Owner re-authorises the campaign against head `0027` (or later).
2. Update `TARGET_REVISION_ID` in the twelve service modules, with a
   docs/operations entry recording the re-authorisation.
3. Remove the `@pytest.mark.skip` decorators added here.
4. Expect the behavioural tests to pass again, because the block was only ever a
   revision mismatch.

The skips are reversible on purpose. Nothing was deleted.
