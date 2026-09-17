# Gate 161 — collector execution delta

What changed, and what is still exactly as false as it was.

## The one-line version

The repository now contains code that composes a source request, sends it
through a transport, stores the bytes that come back and issues a proof that it
happened. It contacted nothing, and four independent things would each have to
change before it could.

## The lane

```text
                             before 161   after 161
execution envelope exists       no          YES
hermetic execution proven       no          YES
execution proof DEFINED         no          YES
live transport implemented      no          no
live transport dispatchable     no          no
approved source count            0           0
source_monitoring_live         false       false
jobs_completed                   0           0
```

Three rows moved. Five did not, and the five are the ones that would mean a
source had been contacted.

## What was added

```text
source_collection_transport_service          the boundary. Imports nothing
                                             network-capable; takes a transport
hermetic_source_transport_service            a registry of fixtures
source_collection_execution_policy_service   composes Gate 94B's live guard
source_collection_request_builder_service    a request from a source definition
source_collection_execution_proof_service    the seven requirements
source_collection_execution_retry_service    outcome -> Gate 157's retry policy
source_collector_execution_service           the envelope, one pass
source_collector_execution_health_service    the lane
source_collection_execution_chokepoint_service   proves the above by parsing
source_collection_execution_attempt_repository   a row per attempt
source_collector_execution_routes            two reads and one smoke
alembic 0047                                 nf_source_collection_execution_attempts
```

Plus an OPT-IN hermetic handler on the Gate 157 worker, behind seven
conditions. The default handler is byte-for-byte the behaviour it had.

## What was NOT added

- **No second payload store.** Bytes go to Gate 160's. The attempt row points
  at them by sha256 and by a shared `attempt_id`, and duplicates none of them.
- **No second job store.** Gate 99B remains the job identity source of truth.
- **No second retry schedule.** `evaluate_execution_retry` classifies the
  outcome and hands it to Gate 157's `evaluate_retry`. One schedule or two is
  the difference between a policy and a coincidence.
- **No refactor of the three legacy httpx importers.** They are guarded,
  injectable, on the approved list with reasons, and absent from the envelope's
  import graph. Doc 837 records the decision; the chokepoint measures the
  absence.
- **No execution-proof parameter on `transition_job`.** Gate 158 left
  `completed` unreachable for real-source jobs and it stays unreachable.

## The four stops in front of a live call

```text
1  the execution policy     refuses transport_kind=live
2  the transport boundary   refuses it again, independently
3  DISPATCHABLE_KINDS       {hermetic}
4  migration 0047           CHECK (transport_kind = 'hermetic')
                            CHECK (live_source_call = 0)
```

Stop 1 is the only one a caller can influence — Gate 94B's guard CAN be
satisfied by a caller who supplies every status, which is by design because
Gate 162 will do exactly that. The other three take no caller input at all.

Each was measured alone, with the ones before it satisfied. A chain tested only
end to end could have three broken links and still refuse.

## The distinctions this gate had to keep

**A hermetic proof is a real proof of a small thing.** The bytes really were
transported, hashed, stored and verified. What it does not prove is that a
source answered, so the proof carries two fields:

```text
proves_the_envelope_works   true
proves_a_source_responded   FALSE
```

A single boolean meaning both is exactly how "the pipeline ran" becomes "the
source answered".

**A 404 is evidence and is not a finished job.** It satisfies all seven
requirements — the envelope worked, and the record that the source said there
is nothing there is worth keeping. Completion asks an eighth thing, kept
outside the seven: was the response usable?

**A malformed body is not a failure.** A 200 whose bytes no parser accepts
still transported and still persisted. Retrying it would re-fetch what we hold,
on a schedule meant for sources that did not answer.

**Knowing a source is not approving it.** The registry holds 177 sources: 171
terms-blocked, 6 human-review-blocked, 0 approved. The health lane reports both
counts, because a zero from an empty registry and a zero from nothing being
approved are the same number for opposite reasons.

## What Gate 162 inherits

A proof standard that already exists, written while nothing could go live. The
temptation at Gate 162 will be to read a hermetic proof as evidence that a
source can be called. It is evidence the envelope works. The two fields exist
so that reading cannot happen by accident.

See doc 841 for what still blocks a live call, and
`artifacts/source_collector_execution_gate161/next_execution_blockers.md` for
the machine-readable version.
