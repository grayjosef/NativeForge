# 471 — Gate 84: Production readiness delta

Gate 83B made the demo payload deterministic and exposed the reason it had not
been: thirty services kept module-level audit lists that accumulated for the
life of the process. Gate 84 fixes the design instead of working around it.

## Audit state: now

| | Before | After |
| --- | --- | --- |
| Services with a module-level `_AUDIT` list | 30 | **0** |
| Growth per demo payload build | doubled | none |
| `audit_refs` contents | this call **plus earlier callers'** | this call only |
| Repeated calls grow the trail | yes | no |
| One call can see another's events | yes | only if the caller shares a collector |
| Test-only `clear_*_audit_for_tests()` helpers | 24 | **0** |
| Determinism `_AUDIT` reset | required | removed |

Ownership is now explicit: a collector instance owns its events, and a caller
that wants one trail across several calls passes one collector to all of them.

Two of the "before" rows were correctness problems rather than tidiness:

- a service could report an audit trail containing **another call's events**,
  which is the wrong answer to "what did this operation do";
- the lists grew without bound in any long-running process — invisible only
  because these services are normally called once per process.

## Demo determinism: now

**Unchanged and still enforced.** The payload is byte-identical across
processes, and the verifier's eleven checks pass.

What changed is *why*: determinism no longer depends on clearing thirty lists
before each generation. The clock, uuid and artifact-path parts of the context
are untouched.

Regenerating the payload moved exactly two fields, both in
`session_tenant_enforcement`, and both stayed `true`. They briefly flipped to
`false` when the first threading pass created the suite's collector without
passing it to any sub-call — the suite could not see its own denial events. The
payload diff caught it, which is the argument for Gate 83B's determinism work in
one sentence: **a reviewable diff caught an audit regression that would
otherwise have shipped silently.**

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

No product claim was added or changed. No audit event was removed. The Gate 83
negative-intelligence surface is untouched and still renders.

## Native customer value

None directly — this gate adds no customer-visible behaviour. Indirectly it
matters for the same reason Gate 83B did: several of these services model
exactly the paths that will be live for a customer (session and tenant
enforcement, object storage access, retention and deletion). An audit trail that
mixes one customer's operation with another's is not a defect you want to
discover after those paths carry real requests.

## Owner-blocked

- Robots/terms review for the Gate 78R sources.
- Primary-source verification; the demo notice remains synthetic.
- Wording review before any customer sees "likely excluded" language.
- A PDF parser decision (carried from Gate 82).
- Real `OIDC_*` credentials, managed Postgres, migration 0028, backup/restore,
  pen test.

## Engineering-blocked

- **`_LOCAL_DEV_STORE`** in `production_metadata_adapter_service`: a
  module-level dict acting as a local dev store, with its own
  `clear_*_for_tests()` helper. Same class of process-lifetime state, out of
  scope here because it is a store rather than an audit accumulator.
- **`nm_wa_operator_demo.json`** has never been audited for determinism or
  accumulation.
- **Two order-dependent tests.** `test_recognition_requirement_coverage_expansion`
  and `test_sprint348_nf15_closeout` pass in the full suite but fail when run in
  a smaller subset, at this commit and at the previous one. Pre-existing, not
  caused by this gate, and worth its own look.
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

What genuinely changed: thirty services stopped leaking audit state across
calls, a workaround was replaced by a fix, and the audit trail a service reports
is now its own. What has not changed: nothing a customer can see, and no claim
about coverage.
