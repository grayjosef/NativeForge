# Gate 161 — what an execution proof is

Gate 158 left `completed` unreachable and said exactly why:

> `transition_job` has no `execution_proof_ref` parameter, no code in Gate 158
> sets it, and the gate that defines what an execution proof *is* has not been
> written.

This is that definition.

## The seven requirements

```text
1  attempt_persisted                a row in the attempts table
2  transport_invoked                the boundary reported dispatched=true
3  response_received                a response, not a timeout
4  raw_payload_persisted            Gate 160 stored the exact bytes
5  payload_hash_verified            and re-hashed them on readback
6  provenance_resolves              attempt -> job -> source, by LOOKING
7  policy_permitted_the_transport   the kind that ran was allowed
```

Each is read from a record somebody else produced. `build_execution_proof` has
no parameter meaning "this succeeded" — the inputs are an attempt row, a
payload row, a replay result, a policy verdict and a transport result, and the
function's whole job is to ask whether they agree.

Requirement 5 is the one that matters most. A store that records a hash and
never checks it again has recorded an intention. Requirement 6 is the one most
easily faked: it must resolve by querying, not by reading a column back to
itself, which Gate 160 measured going wrong before it was fixed.

## The eighth thing, deliberately outside the seven

```text
response_was_usable      a 2xx status
```

A 404 satisfies all seven. That is correct: the envelope really worked, and
"the source says there is nothing there" is a fact worth keeping. What a 404
must not do is let a job be called finished.

So usability is a separate field and only completion consults it. Folding it
into the seven would make a 404 look unevidenced and lose the record; leaving
it out entirely made "the fixture answered" and "the work is done" the same
fact, which is what the first draft of this module did.

## Scope, in the field names

```text
proof_scope                          hermetic_execution
proves_the_envelope_works            true
proves_a_source_responded            FALSE
permits_hermetic_job_completion      true, if the response was usable
permits_real_source_job_completion   FALSE, unconditionally
```

Two fields rather than one, because a single boolean meaning both is exactly
how "the pipeline ran" becomes "the source answered". A caller who wants the
second must read the second.

`LIVE_COMPLETION_SCOPE` is named so that refusing it is expressible, and is
unreachable: nothing in this gate can produce a proof in it, and
`execution_proof_invariant_failures` reports
`a_live_scoped_proof_was_produced` if one ever appears.

## What this does NOT unlock

**`completed` on a real-source job stays unreachable.** Gate 158's repository
still has no execution-proof parameter and this gate does not add one. The
proof this module issues is about an attempt; Gate 162 decides whether any real
source may be attempted at all.

**A hermetic job MAY complete**, under `HERMETIC_COMPLETION_SCOPE`, because a
synthetic fixture job that transported, persisted and verified usable bytes has
genuinely finished the only work it ever had. In practice the Gate 157 worker
still completes nothing: it records the hermetic execution and refuses the job
with `hermetic_execution_succeeded_and_a_fixture_is_not_a_collection`, which
keeps `jobs_completed = 0` true across four verifiers, the worker health
invariant and every Gate 157–160 artifact — and is simply accurate. The job
asked for a source to be collected. A fixture answered.

## Why define it now

Gate 158 deferred it because no payload spine existed. Gate 160 built one.

Defining the requirements while nothing can go live means Gate 162 decides
*which sources may be attempted* against a standard that already exists, rather
than inventing one under the pressure of a first live source. A proof standard
written next to the thing it is about to authorise is a proof standard shaped
by what that thing happens to produce.

## The reading to guard against at Gate 162

A hermetic execution produces a real proof, and the proof is correct. The
tempting inference is that a working, proven envelope means a source can now be
called. It does not. It means the envelope works.

Zero sources are approved. 177 are known, 171 are terms-blocked, 6 are
human-review-blocked. No live transport exists. The proof says nothing about
any of that, and its field names are written so that it cannot be read as if it
did.
