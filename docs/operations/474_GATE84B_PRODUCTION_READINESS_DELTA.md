# 474 — Gate 84B: Production readiness delta

## Correction

Gate 84 reported two tests as order-dependent. They were **not order-dependent**.
Both failed deterministically, alone and in every arrangement tested. That
characterisation was an inference from a green `-k`-selected run, not a
measurement, and the tests it described were not in that selection.

The actual defects were older and simpler:

| Test | Cause |
| --- | --- |
| `test_nf15_gate_and_closeout` | Gate 77B made live Grants.gov opt-in; this path had no way to inject a recorded transport, so the re-ingest was permanently refused |
| `test_unknown_count_drops_ac1` | an absolute unknown threshold measured against a corpus that grew from 76 to 168 grants across three later commits |

## Test state: now

| | Before | After |
| --- | --- | --- |
| `test_nf15_gate_and_closeout` | failed everywhere | passes, transport injected |
| `test_unknown_count_drops_ac1` | failed everywhere | passes on its calibrated corpus |
| Either passes in isolation | no | **yes, in its own interpreter** |
| Live Grants.gov fallback | refused | still refused, asserted |
| Tier-1 derivation regression could hide | — | blocked by a structural assertion |
| Suite number reported | a `-k` selection | **the whole suite, no `-k`** |

The NF-15 fix threads an optional, keyword-only `http_post` through the
orchestrator and the gate verification. A guard test asserts that omitting it
still refuses the live path, so Gate 77B's boundary is intact.

The AC1 fix changes the corpus read, not the assertion: 13 unknowns against an
unchanged threshold of 45. A structural assertion requires every unknown outside
tier-1 to be attributable to a later corpus layer.

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

No product behaviour changed. The NF-15 orchestrator gained an optional
parameter whose default preserves existing behaviour exactly, and the
recognition derivation was not touched.

## Native customer value

None directly. Indirectly: two acceptance criteria that had silently stopped
being checked are being checked again — one of them the NF-15 no-evidence
honesty gate, which exists to stop a grant with no eligibility evidence being
labelled irrelevant. That is a guard on exactly the kind of claim this product
must not get wrong.

## Owner-blocked

- Robots/terms review for the Gate 78R sources.
- Primary-source verification; the demo notice remains synthetic.
- Wording review before any customer sees "likely excluded" language.
- A PDF parser decision (carried from Gate 82).
- Real `OIDC_*` credentials, managed Postgres, migration 0028, backup/restore,
  pen test.

## The full suite, measured for the first time

Running the whole suite with no `-k`:

```text
4 failed, 7114 passed, 51 skipped   in 35:31
```

The two tests this gate fixed **pass**. The four failures are *different* tests
that the `-k` selection has also been hiding. All four fail alone as well, so
none is order-dependent — they are the same disease as the two fixed here.

| Test | Diagnosis |
| --- | --- |
| `test_sprint197_...::test_five_fit_dimensions` | `assert len(FIT_DIMENSIONS) == 5`, but a sixth dimension (`capacity_fit`) was added later. Stale count. |
| `test_sprint222_...::test_incomplete_profile_blocked_readiness` | expects `readiness_label` in `{blocked, not_ready_eligibility_uncertain}`; the vocabulary later gained `not_ready_missing_documents`, which is what it returns. Stale enum. |
| `test_sprint4202_...::test_5175_collision_blocks_serve` | `OSError: Address already in use` — needs port 5175 free, but the demo preview service owns it by design |
| `test_sprint4202_...::test_verifier_fail_when_server_down` | `DistNotReady: port 5175 already in use` — same cause |

The first two are stale assertions outgrown by product evolution, the same
pattern as `test_unknown_count_drops_ac1`. The last two are structurally
incompatible with a machine where the dev preview is running; they would pass in
CI with the port free, and stopping that service is forbidden by this gate's
hard rules.

**They are not fixed here.** This gate's scope was the two named tests, and
correcting a stale assertion requires deciding what it should now assert — a
judgement call that is exactly where a hasty fix weakens a test. They are
recorded rather than rushed.

## Engineering-blocked

- **The `-k` selection is not suite health.** This is the real finding, and the
  full-suite run above quantifies it: **six** tests were failing behind a
  regression number that read `0 failed` for several gates. Two are fixed here;
  four are listed above. Options: run the whole suite per gate (35 minutes, done
  here), or add a check that flags tests no gate selection reaches.
- **The four remaining full-suite failures**, with diagnoses above. Two are
  stale assertions needing a product decision about what they should assert now;
  two need port 5175 free and cannot pass while the dev preview runs.
- `_LOCAL_DEV_STORE` in `production_metadata_adapter_service` (carried from
  Gate 84).
- `nm_wa_operator_demo.json` never audited for determinism or accumulation.
- Real notices on the demo surface — blocked behind the fetch layer.
- Threading `applicant_class` from a customer org profile (carried from 79B).
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

What genuinely changed: two silently failing acceptance criteria pass again,
without weakening either assertion or reopening the live-network path, and this
gate's regression number is the whole suite rather than a selection of it.
