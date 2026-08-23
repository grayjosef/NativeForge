# 396 — Gate 63H: Test signal readiness delta

## Signal before

```text
scoped selection: 38 failed, 5278 passed, 11 skipped
```

38 permanently-red tests, stable across Gates 60–62 and verified byte-identical
between commits. The practical cost was not the red count — it was that the noise
**hid real signal three times during this campaign**:

1. A "7 pre-existing failures" figure was carried forward from a narrower `-k`
   expression and reported as if comparable to a 38-failure selection.
2. A `tail`-truncated capture reported 11 of 38 failure lines, producing a
   miscount.
3. Gate 62's own `now()` bug briefly took the count to 98, and distinguishing
   "my 60 new failures" from "the standing 38" required a worktree diff against
   a parent commit to establish.

None of those would have happened against a green baseline.

## Signal after

```text
patched files: 314 passed, 37 skipped, 0 failed
```

Broad scoped result reported in the final report. The 37 skips are the 37
retired assertions, each named and reasoned.

## What changed

| Treatment | Count | Detail |
| --- | --- | --- |
| **Fixed properly** | 1 | sprint20 head re-pinned 0019 → 0027; its unique-revision-id and file-existence checks untouched |
| **Retired: freeze guard** | 13 | `no_new_alembic_revision_beyond_0019` and variants |
| **Retired: unreachable path** | 21 | sprint62/64 behavioural, blocked by `blocked_runtime_revision_mismatch` |
| **Retired: superseded proof** | 3 | sprint47 SQLite up/down proof |
| **Left alone, out of scope** | 2 | recognition-coverage and fit-dimension failures, unrelated to migrations, not in the `-k` selection |
| **Deleted** | 0 | — |
| **Product behaviour changed** | 0 | — |

## The finding that shaped the gate

24 of the 38 were **not stale assertions**. The active-source services pin
`TARGET_REVISION_ID = "0019"` across twelve modules and return
`blocked_runtime_revision_mismatch` when the runtime DB is past it. That is a
safety gate working correctly — a service declining to operate against a schema
it was never authorised for.

The tempting fix was to repoint the constant at `0027`. That would have been
wrong twice over: it changes product behaviour to satisfy a test, and it silently
re-authorises a closed campaign against a schema nobody reviewed it against.
The pin is intact and the tests are skipped with the cause recorded instead.

Had this gate assumed "38 stale tests, update them all", it would have quietly
removed a real safety property.

## The doctrine that replaces the freeze guards

`tests/test_gate63_migration_doctrine.py` — 14 tests:

- migration graph has exactly one head
- head equals the documented `CURRENT_HEAD` (`0027`), with an error message
  telling the next person to update it *and* add a docs entry
- alembic CLI agrees with the parsed graph
- approved migrations 0023–0027 exist
- revision ids are unique
- identities are unique on `(issuer, subject)`, not email
- untrusted membership sources are absent from the `TRUSTED_SOURCES` tuple
- the RLS migration is Postgres-guarded so SQLite no-ops
- the RLS proof harness exists and covers cross-org denial, non-superuser and
  non-owner checks
- the Postgres-only seat-cap asymmetry is explained in the migration itself
- **no migration uses the Postgres-only `sa.text("now()")` literal** — a
  regression guard for the Gate 62 bug that broke 98 tests

The difference in kind: the old guards asserted a *file did not exist*, so any
approved migration broke a closed campaign. The new ones assert *properties that
remain true* as the schema evolves, and require exactly one deliberate constant
change when a migration is approved.

## Why backend signal is now stronger

- A failing scoped run means something is actually wrong.
- The head is asserted in one place with a message that tells you what to do.
- The `now()` dialect bug cannot recur silently.
- Retirements are reversible: doc 395 records how to un-retire the campaign if
  the owner re-authorises it.

## What remains blocked for controlled pilot

Unchanged by this gate — it improved test signal, not product readiness:

```text
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage live:   NO
Customer persistence:      NO
Pen-test passed:           NO
Slack live alert:          NOT PROVEN
```

Still owner-blocked: real `OIDC_*` credentials, a provisioned Postgres instance,
independent pen test, live Slack webhook + redaction decision.

Still engineering-blocked: the Gate 62 items interrupted before completion — a
Postgres proof harness with `--check-config`/`--verify-rls`/`--dry-run` modes, a
`PostgresMembershipDirectory`, an audit-persistence wiring plan, and
`tests/test_gate62_storage_membership_rls_path.py`. Then the invite/approval
path, capability enforcement on live routes, and the discovery baseline.
