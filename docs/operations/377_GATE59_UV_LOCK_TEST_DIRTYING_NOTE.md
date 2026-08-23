# 377 — Gate 59G: uv.lock test-run dirtying

Status: **root cause found and fixed.** The fix is a one-package re-lock.

## Symptom

Across Gates 51-58, `uv.lock` was reported modified after backend test runs
**four separate times** and reverted each time. Every occurrence was the same
4-line diff, and each one was a chance to accidentally commit an unrelated
dependency bump.

## Root cause

The lock was **internally inconsistent with `pyproject.toml`**:

```text
pyproject.toml:17   pydantic-settings>=2.14.2
uv.lock:474         { name = "pydantic-settings", specifier = ">=2.6" }   <- STALE
uv.lock:688         version = "2.14.1"                                    <- VIOLATES >=2.14.2
```

Someone raised the pyproject floor to `>=2.14.2` without re-locking. The lock
still recorded the old `>=2.6` requirement and pinned `2.14.1`, a version the
current constraint forbids.

So **any** `uv` invocation detected the drift, re-resolved, and rewrote the lock
to `>=2.14.2` / `2.15.0`. Several repo scripts call `uv run` (for example
`la_scale_federal_staging_verify.sh`, `grants_gov_*_staging_verify.sh`, and a
test fixture referencing `uv run alembic upgrade 0019`), so ordinary test and
verify activity kept triggering it.

The installed venv was **already running 2.15.0**, and every suite in this
campaign passed against it. The lock was the thing out of step with reality, not
the environment.

## Fix applied

```bash
uv lock
```

Scope — 42 packages resolved, exactly **one** changed:

```text
Updated pydantic-settings v2.14.1 -> v2.15.0
uv.lock | 8 ++++----
1 file changed, 4 insertions(+), 4 deletions(-)
```

The four lines are: the stale specifier `>=2.6` → `>=2.14.2`, the version pin,
and the sdist/wheel hash pair. No other package moved.

Verified after the re-lock:

```text
uv lock          -> "Resolved 42 packages in 3ms", no "Updated" line (no-op)
uv lock --check  -> exit 0
pytest run       -> uv.lock no longer re-resolves
```

## Why this counts as safe and tiny

- It records the version the venv already runs, so it changes no behaviour.
- All Gate 59 (38), Gate 58 (51) and Gate 51-57 (39) tests pass against it,
  as does the 108-test API suite.
- It aligns the lock with the declared constraint instead of leaving it in a
  state that violates it.
- Leaving it unfixed guarantees a fifth, sixth and seventh recurrence, each one
  a chance to commit a dependency change by accident.

## Reported deliberately

The standing hard rule is *"do not stage `uv.lock` unless intentionally
necessary and reported."* This is that case, so it is called out here and in the
Gate 59 report rather than slipped into the diff. `uv.lock` is staged
**intentionally**, as a single-package correction, with the scope above.

## If this recurs

Check for the same class of drift first:

```bash
uv lock --check          # non-zero means the lock disagrees with pyproject
grep -n "specifier" uv.lock | grep <package>
```

A pyproject constraint edited without a re-lock is the likely cause, and the fix
is to re-lock in the same commit as the constraint change.
