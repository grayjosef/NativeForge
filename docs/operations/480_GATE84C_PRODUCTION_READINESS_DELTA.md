# 480 — Gate 84C: Production readiness delta

Gate 84B measured the full suite for the first time and found four remaining
failures. This gate closes them and adds a guard so a gate `-k` selection cannot
hide a failing test indefinitely.

## Full suite: measured and green

```text
Gate 84B    4 failed, 7114 passed, 51 skipped
Gate 84C    0 failed, 7157 passed, 51 skipped
```

Five tests fixed — the four Gate 84B named, plus a fifth in the same file that
escaped that run only by skipping when `frontend/dist` was unstamped.

| Test | Kind | Fix |
| --- | --- | --- |
| `test_five_fit_dimensions` | stale count | pin the exact tuple by name |
| `test_incomplete_profile_blocked_readiness` | stale enum | pin the exact label, add a bypass guard |
| `test_5175_collision_blocks_serve` | needs 5175 free | ephemeral port |
| `test_verifier_fail_when_server_down` | needs 5175 free | ephemeral base URL |
| `test_verifier_pass_when_stamped_server_up` | needs 5175 free | verify against the running preview |

**No product code changed.** Every fix is in a test. `require_preview_port_free`
already accepted host and port, and the deployment verifier already accepted a
base URL, so neither needed touching. Nothing was skipped or xfailed, no
assertion was weakened, and the preview service was never stopped.

Two assertions came out **stronger** than they went in: an exact dimension tuple
catches renames and reorders the old count missed, and the readiness test now
also asserts that no newly added label can land in the proceed set.

## Test selection coverage: now

| | Before | After |
| --- | --- | --- |
| Full suite measured | once, at Gate 84B | every gate can, and this one did |
| Blind spot size | unknown | **674 of 7172 measured** |
| Critical tests reached by the gate `-k` | 2 of 6 | **6 of 6** |
| Guard against recurrence | none | `verify_nativeforge_test_selection_coverage.sh` |

The guard failed on its first run — four of six critical tests were outside the
expression, which is precisely how they failed unnoticed. Adding
`fit_dimension`, `readiness` and `gate37` moved selection from 6436 to 6498 and
brought all six inside.

The critical list holds **node ids, not keywords**, so a rename fails the guard
rather than quietly dropping coverage. Two of the six were renamed by this gate,
and the list names the new identifiers.

## Live coverage: now

**Unchanged. Zero.**

```text
Live SC source coverage:   NONE
Live federal coverage:     NONE
Sources monitored:         0
Notices fetched:           0
Real notices parsed:       0
SC coverage complete:      NOT CLAIMED
65% improvement:           NOT CLAIMED
```

## Native customer value

None directly. Indirectly: five acceptance criteria that had stopped being
checked are being checked again, and two of them guard things this product must
not get wrong — the recognition-tier fit dimension, and the rule that an
incomplete profile is never allowed to proceed to an application.

## Owner-blocked

- Robots/terms review for the Gate 78R sources.
- Primary-source verification; the demo notice remains synthetic.
- Wording review before any customer sees "likely excluded" language.
- A PDF parser decision (carried from Gate 82).
- Real `OIDC_*` credentials, managed Postgres, migration 0028, backup/restore,
  pen test.

## Engineering-blocked

- **674 unselected tests.** The blind spot is measured, not eliminated. A
  failure in one of them is still invisible to a scoped run. The durable fix is
  a full suite per gate — 35 minutes, done here.
- **The critical list is retrospective.** It guards tests that have already
  failed once. A seventh can still rot before anyone notices.
- **The `-k` expression lives in two places** — the guard script and the gate
  prompts. The script is the source of truth; a prompt that drifts from it will
  select differently from what the guard checks.
- `_LOCAL_DEV_STORE` in `production_metadata_adapter_service` (from Gate 84).
- `nm_wa_operator_demo.json` never audited for determinism or accumulation.
- Real notices on the demo surface — blocked behind the fetch layer.
- Threading `applicant_class` from a customer org profile (from Gate 79B).
- Scheduler (Gate 80) — still correctly blocked.

## Controlled customer pilot delta

**None.**

```text
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage live:   NO
Customer persistence:      NO
Pen-test passed:           NO
```

What genuinely changed: the full suite is green for the first time in the
campaign, and the gap between "the scoped run passed" and "the suite passes" is
now measured and guarded rather than assumed.
