# 467 — Gate 83B: Production readiness delta

Gate 83 put customer-facing eligibility content into the committed demo payload
and flagged that the payload was not reproducible. Gate 83B fixes that and
proves the new surface renders in a real browser.

## Demo payload determinism: now

| | Before | After |
| --- | --- | --- |
| Two builds, same process | differed (94 leaves) | **byte-identical** |
| Two builds, separate processes | differed | **byte-identical** |
| Committed artifact reproducible from HEAD | no | **yes**, verifier-enforced |
| Reviewable diff of demo payload | no | yes |
| Generation writes into `artifacts/` | every run | **never** |
| `_AUDIT` lists per build | doubled | reset per generation |
| Ids stable across interpreter restarts | no | yes |

Five causes, each visible only after the previous was fixed — differing leaves
went `94 → 44 → 387 → 3 → 0`:

1. **Wall clock** in 41 loaded modules.
2. **`uuid.uuid4()`** in 37.
3. **Thirty module-level `_AUDIT` lists**, each doubling per build. Output
   depended on how many payloads the process had already built, and the lists
   grow unboundedly in any long-running process.
4. **On-disk side effects.** Generation wrote four files into `artifacts/` per
   run; one directory held **4,379** of them, and output depended on what
   earlier runs had left behind.
5. **`hash()`-derived id.** Python randomises string hashing per process, so
   `hash(gate) & 0xFFFF` produced a different id on every interpreter start.

Two of these were bugs in their own right, not merely demo noise:

- an id built from `hash()` cannot serve as a cross-process key — a latent
  correctness problem wherever such an id is compared or stored;
- thirty unbounded module-global lists are a slow memory leak, invisible only
  because these services are normally called once per process.

Both are fixed at the source. A test fails if another `hash()`-derived id
appears.

## Browser smoke coverage: now

| | Before | After |
| --- | --- | --- |
| Playwright tests | 2 | **4** |
| Negative-intelligence section in a real browser | untested | asserted |
| Evidence quote in a real browser | untested | asserted |
| Both recognition tiers rendered | untested | asserted |
| Excluded row still visible | untested | asserted |
| Synthetic / no-live-coverage labels | untested | asserted |
| Banned legal-ineligibility phrasing | vitest only | vitest **and** real browser |

vitest renders the component to static markup; Playwright loads the built,
stamped bundle. Only the second proves the section survives bundling and
actually reaches a viewer.

## Live source coverage: now

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

No product claim was added in this gate. The payload's content is unchanged
apart from now-stable ids, timestamps and one list ordering.

## Native customer value

Indirect but real: the demo payload carries an applicant-class exclusion, the
sentence it rests on, and the hash of the artifact that sentence came from.
Until now a reviewer could not tell a **wording change to a customer-facing
exclusion** from timestamp noise — regenerating for Gate 83 produced 567
insertions and 476 deletions almost entirely unrelated to the change.

Now the diff is the change. For content that tells a tribal grant office it may
be excluded from a programme, being able to review exactly what changed is a
prerequisite for showing it to anyone.

## Owner-blocked

- **Robots/terms review** for the Gate 78R sources — still the gate on any real
  notice reaching this surface.
- **Primary-source verification**; the demo notice is synthetic throughout.
- **Wording review** before any customer sees "likely excluded" language. Both
  a vitest and a Playwright guard now assert the page never claims legal
  ineligibility, but automated phrasing checks are not sign-off.
- **A PDF parser decision** (carried from Gate 82).
- Real `OIDC_*` credentials, managed Postgres, migration 0028, backup/restore,
  pen test.

## Engineering-blocked

- **`_AUDIT` as module state.** The deterministic context resets these lists per
  generation, which fixes the payload. It does not fix the underlying design:
  thirty services still accumulate audit events in module globals that grow for
  the life of a process. Making them request-scoped is a 30-service refactor of
  live audit code and was deliberately not attempted inside a determinism gate.
- **Determinism is enforced for one artifact.** `nm_wa_operator_demo.json` was
  not audited and may have the same problem.
- Real notices on the surface — blocked behind the fetch layer.
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

What genuinely changed: the committed demo artifact is now reproducible and
reviewable, generation no longer mutates the repository, two real bugs were
fixed at the source, and the negative-intelligence section is proven to render
in a browser rather than only in a test renderer. What has not changed: every
word on that surface still describes a synthetic fixture.
