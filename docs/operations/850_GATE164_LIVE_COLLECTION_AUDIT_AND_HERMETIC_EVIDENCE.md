# 850 — Gate 164: replaying the live collection, and making evidence hermetic

Two questions. Can the one real collection be reconstructed from what was
written down? And can the evidence about it be generated without a developer's
laptop leaking into it?

## 1. The collection replays

From a fresh connection, with the original session closed and the connection
pool disposed, and with `socket.socket` replaced by one that raises:

```text
bytes recovered        11131, exactly
sha256 recomputed      eb4cc7cb…0cfd16, matching
source linkage         nf-seed-2026-api-grants-gov-search2
authorization linkage  the same id, on the attempt row
attribution            present_and_verbatim
normalized             O-BJA-2026-172662, re-derived from the bytes
network calls          0
HTTP status            still UNKNOWN
```

The pool is disposed as well as the session closed. A pooled connection
outlives `close()`, and reusing one would be the process-memory shortcut the
restart proof exists to exclude.

`http_status_is_still_unknown` is asserted as a POSITIVE property. A replay
that produced a status would be inventing one.

## 2. The audit composes; it does not duplicate

Six sections — source, authorization, request, response, execution,
normalization — read from the registry row, the decision records, the
activation row, the payload, the attempt and the stored bytes.

No second ledger. An audit written alongside the collection would be a second
account of one event, and two accounts can disagree; the one that disagreed
would not announce itself. Composing means a contradiction between the payload
row and the attempt row IS the audit's output rather than something it has
already smoothed over.

## 3. Tampering is refused, and the strongest refusal is the schema's

Every case runs against a COPY of the database file. The real evidence is
read-only throughout.

```text
changed raw bytes              hash fails
changed payload hash           hash fails
changed source id              audit chain breaks
stripped authorized_source_id  REFUSED BY THE DATABASE
changed request authority      fingerprint no longer matches the endpoint
missing execution proof        chain incomplete, section named
proof naming other bytes       invariant fires
backfilled HTTP status         invariant fires
```

Migration 0050's `CHECK (transport_kind <> 'live' OR authorized_source_id IS
NOT NULL)` means the fourth case has no representation at rest. That is
stronger than detection: the corrupt state cannot be written.

The control comes first — an untouched copy must still verify — or every
refusal below it could be "it is a copy".

## 4. The ambient-state boundary

Gate 163 nearly committed a developer's Auth0 configuration as repository
evidence. Gate 164 measured how wide that is, and the measurement took three
attempts to get right.

### What the measurement finally said

Varying ONE input at a time, with `DATABASE_URL` pinned to the same absolute
file in every variant, and a baseline run twice as a control:

```text
total writers                     71
ambient independent               41   identical across A-F
environment scoped                28
requires explicit input            2
non deterministic                  0
not measured                       0
unclassified                       0
```

`requires explicit input` exists because of a trap: two writers came back
"stable across every variant" in an early run when what they actually did was
raise the same TypeError six times. Failing identically is not hermeticity.

### The boundary itself

Not a list of variables to unset — that is a ritual that works until someone
forgets, which is what happened. `auth_environment_overlay` is the function
that turns credential PRESENCE into a fact, so the refusal lives there:

```text
default                    unchanged; nothing existing is affected
canonical_build()          raises AmbientStateRefused, naming the reader
environment_scoped_build() permits it, and says so in its own output
explicit environ passed    honoured - that is an input, not an ambient read
```

Canonical and environment-scoped are both honest. An artifact that reports
whether THIS deployment has its provider configured is doing something
legitimate; it is just not repository evidence, and it says which it is.

### Concurrency

The first draft used `threading.local()`. Wrong here, for a specific reason:
57 API route modules, zero `async def`. Every endpoint is sync, so Starlette
runs them in anyio's worker threadpool, and those workers are REUSED across
requests — state left behind would be inherited by whatever ran next on that
thread.

`ContextVar` with token-based reset. Proven under both models: a reused pooled
worker does not inherit the flag, concurrent asyncio tasks sharing one thread
do not see each other's context, nesting restores to the enclosing state in
both directions, and eight parallel canonical/environment-scoped builds do not
cross.

## 5. Health, and a gap that is not corruption

```text
health_status        healthy_with_known_evidence_gap
known_evidence_gaps  ["http_status_not_captured"]
unmet conditions     none
```

Six statuses, because three answers were not enough. The bytes verify, the
linkage holds, the collection replays — and one field was never captured.
Calling that `unhealthy` would say the evidence is untrustworthy; calling it
`healthy` would hide that something is missing.

A gap must be NAMED. A status claiming a known gap with an empty gap list is
an invariant failure, or "known gap" becomes a way to pass while hiding
anything.

## 6. What a customer may be told

Built from an ALLOWLIST, not a denylist. A denylist fails the moment a new
internal field appears upstream — it ships until someone notices. An allowlist
fails the other way: a new internal field is simply absent.

```text
shown     source name, authority, link, retrieved_at, opportunity id and
          number, title, agency, dates, the required attribution notice,
          and a plain statement that the listing was normalized from the
          source's own response
withheld  reviewers, warrants, guard statuses, decision kinds, hashes,
          attempt ids, fingerprints, organization ids, filesystem paths,
          anything environment- or credential-shaped
```

The blocked-marker scan is a NEGATIVE PROOF over the serialized DTO, not the
mechanism — two different jobs, and a nested internal field would not show up
in a key check.

## 7. Zero network, proven

Every phase replaces `socket.socket` with one that raises and counts attempts.

```text
network_requests_during_gate164   0
```

Not inferred from reading the code. The Gate 163 search2 request remains the
only collection request this repository has ever made.

## What went wrong in the measuring

Three times the instrument was the defect, not the code.

```text
1  the first survey varied cwd AND the database together, so 68 of 70
   builders "differed" for what may have been one cause
2  the second matrix ran while the tree was edited underneath it; the writer
   count moved 70 -> 71 mid-run and a writer that did not yet exist during
   variant A was reported as ambient-sensitive
3  `discover_writers()` globbed a cwd-relative path, so the no-`.env` variant
   silently found ZERO writers - and comparing a full run against an empty one
   is where "68 cwd/.env-sensitive builders" actually came from
```

Each produced a confident number. The third was only caught because the
baseline-twice control — removed in a rewrite, then restored — showed the
shape of the problem.

Two buckets exist now so those failures are nameable rather than absorbed:
`non_deterministic` and `not_measured`. A writer that was never measured is
not a classified writer.

The finding that survived all three corrections is the one that mattered:
**21 builders change because a developer holds credentials.** That is the Gate
163 defect class, and it is what the boundary is for.
