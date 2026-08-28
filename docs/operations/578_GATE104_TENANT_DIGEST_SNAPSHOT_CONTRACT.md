# 578 — Gate 104B/H: tenant digest snapshot contract

`src/nativeforge/services/tenant_nofo_digest_snapshot_service.py`
`src/nativeforge/services/tenant_nofo_digest_demo_fixture_service.py`

A recorded set of opportunity rows as they appeared to one tenant at one moment.
Building one fetches nothing.

## Four kinds, and only one asserts collection

```text
demo_fixture      invented for a demo, labelled as such
recorded_fixture  captured from a real observation and stored
live_observation  taken from a live collection just now
unknown           nobody said which
```

`live_observation` is **refused unless `source_collection_status` proves it.**
Passing the kind is not enough: a caller claiming a live observation while
collection status says `not_active` gets `unknown` and a stated reason.

That refusal is the reason the field exists. Every snapshot in this repository is
a fixture, and the contract makes a fixture that *claims* to be live impossible
rather than merely discouraged. A test proves both directions — the refusal
fires, and a snapshot with `source_collection_status: collected` is accepted, so
the check is not a blanket ban.

## A snapshot never claims coverage

```text
source_monitoring_live  false
live_source_coverage    false
collectors_active       0
fetch_performed         false
```

Held by invariants on every snapshot regardless of kind. A recorded fixture of a
real observation is still not monitoring.

## Unknowns stay visible

Twenty-two fields per opportunity row, and the ones that carry uncertainty never
default to something reassuring:

```text
deadline with no provenance    -> unverified_deadline, never verified
reporting burden unsupported   -> unsupported_document_type
eligibility not established    -> unknown / needs_human_review
```

A bare date is `unverified_deadline`, not `verified_deadline` — recording the
date *and* the fact that nobody can vouch for it is more useful than dropping
either. `deadline_verified` is derived from Gate 87's `VERIFIED_STATUSES` and an
invariant fails any row where the flag and the status disagree.

An excluded row with no exclusion reason, or a human-review row with no review
reason, fails an invariant. A refusal a tenant cannot interrogate is worse than
no refusal.

## The demo fixture pair

Ten opportunities across two labelled snapshots, covering every change type the
digest must demonstrate:

```text
opp-new-match          absent from week 1, matched in week 2
opp-deadline-verified  verified deadline moved
opp-deadline-unverif   unverified date moved
opp-amended            material amendment (eligibility_change)
opp-excluded           matched -> excluded
opp-downgraded         matched -> downgraded
opp-review             needs human review, suspected_placeholder deadline,
                       unsupported_document_type burden
opp-approaching        verified deadline inside 30 days
opp-suppressed         pursued, withheld from the new-opportunity view
opp-removed            present in week 1, absent from week 2
```

Each exercises a different **refusal** rather than a different happy path. A
fixed reference clock keeps `approaching_deadline` in range and the artifacts
byte-identical between runs.

No real Tribe is named — Gate 103's seventeen-token list is imported and scanned
rather than restated, and a test scans the committed artifact too. Both snapshots
are `demo_fixture` and an invariant fails the set if either drifts to
`live_observation`.
