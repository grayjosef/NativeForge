# 550 — Gate 98B: source schedule decision

`src/nativeforge/services/source_schedule_decision_service.py`

Decides whether a source is due for a check. It does not perform one, does not
enqueue one, and cannot.

## Three answers, not one

```text
due_for_check          the clock says it is time
safe_to_enqueue        it may be put on a queue
safe_to_execute_now    a request may go out immediately
```

A source can be overdue by a week and still be unsafe to touch: its terms may
need review, its circuit may be open, or the production payload store may not
exist to hold what comes back. Collapsing the three is how a scheduler ends up
hammering a host it was never allowed to contact.

`safe_to_execute_now` is `False` on every decision in this gate, held by an
invariant. Nothing executes, so a decision that could return True would be
describing a capability that does not exist.

## Five statuses

```text
not_due                  the clock has not come round
due_but_blocked          it is time, and something says no
due_and_safe_to_enqueue  it is time and every precondition holds
disabled                 monitoring is off or paused for this source
unknown                  the inputs do not describe a state
```

`due_and_safe_to_enqueue` is the only status that permits anything, and
`safe_to_enqueue` is derived from that membership rather than set beside it —
an invariant fails any result where the two disagree.

## Seven requirements

Each is reported as satisfied or missing, and every one must hold:

```text
collector_active            collector_status == active
activation_allowed          activation_status == activation_allowed
monitoring_enabled          monitoring_status in {enabled, active}
terms_cleared               NO_REVIEW_REQUIRED or ATTRIBUTION_REQUIRED
human_review_cleared        not HUMAN_REVIEW_ONLY, review not pending
circuit_permits             circuit_status in {closed, half_open}
production_payload_store    Gate 96/97 storage exists
```

The last one matters as much as the rest. A check whose bytes have nowhere
durable to land produces a record nobody can later verify — the 185/18 corpus
split Gates 87–89 measured, repeated live.

An invariant asserts that satisfied ∪ missing equals the full requirement set,
so a future edit that adds a requirement and forgets to evaluate it fails a test
rather than shipping a permissive result.

## A missing due date is a question, not a licence

`next_check_due_at` absent produces `unknown` and sets `human_review_required`.

The tempting reading — "never checked, so check it now" — is exactly backwards.
A source with no schedule is a source nobody has decided the cadence for, and
picking one automatically is picking it arbitrarily, against a host whose rate
limits nobody has read.

The same applies to a due date that cannot be compared to `now`: a naive
timestamp against an aware one is not derivable, and inventing a timezone to get
an answer would be manufacturing the answer. Both report `unknown`.

## Everything defaults to blocked

Every status input resolves to its blocking member when absent or unrecognised:

```text
collector_status      -> not_active
activation_status     -> activation_unknown
monitoring_status     -> unknown
terms_status          -> UNKNOWN
human_review_status   -> unknown
circuit_status        -> unknown
```

A typo blocks. A vocabulary this code has not been taught blocks. Gate 98C found
the cost of the other reading: an unrecognised manual override was normalising
to `unknown` and then falling through to a permitting branch. A smoke test caught
it; a live scheduler would not have.

## It bridges rather than re-derives

`circuit_status` is consumed from Gate 98C's `evaluate_circuit`, and
`SCHEDULING_PERMITTED_STATUSES` is imported from it rather than restated. Gate
98A found four independent failure counters and two disagreeing thresholds
precisely because each site declared its own; this service does not add a fifth.
