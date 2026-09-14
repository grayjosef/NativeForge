# 800 — Gate 153: proving a restore actually restored something

A restore that loads rows and reports a row count has proved that rows moved.
It has not proved the thing anyone cares about, which is whether the restored
database still answers the questions the live one answers.

## The nine checks

```text
restored_row_counts_match_the_export            PASS
restored_table_hashes_match_the_export          PASS   11 tables rehashed
restored_digest_payloads_still_hash             PASS   1 hash-proven
restored_intents_still_resolve_to_a_digest      PASS
gate_152_replay_agrees_on_both_sides            PASS
evidence_ledger_statuses_are_identical          PASS
archived_rows_are_still_archived_and_readable   PASS
a_cross_organization_read_is_still_refused      PASS
legacy_gaps_survived_as_legacy_gaps             PASS   n → n, unchanged
```

The counts below are **live** and move with dev activity: running the other
verifiers writes fixture rows, so the row total and the legacy gap count are
different an hour later. What does not move is that the two sides agree. The
verifier measures the numbers; this document does not pin them.

## It runs the Gate 152 code, unmodified

`verify_restored_state` does not write a second replay. It calls
`audit_replay_service` and `evidence_ledger_service` against the restored
connection and against the source, and compares the answers.

If restored state needed its own special replay to pass, the restore would not
have restored anything worth having.

## UNKNOWN is not a pass

A check that could not run reports `UNKNOWN`, and `verified` is false while any
check is `UNKNOWN`. A verification that could not run everything has not
verified everything, and reporting nine checks where two never executed would
be the same defect as a blocker that gates nothing.

## Equal is not the same as good

The comparison is `source == restored`, not `restored is healthy`. A source
holding a `missing_record` must restore to a `missing_record`: that is a **pass
here** and a **finding in the ledger**.

Conflating the two would let a restore of broken state read as a pass because
nothing changed — which is true, and is also the wrong claim. The verification
reports fidelity. The ledger reports health. The payload says so in
`comparison_is_fidelity_not_health`.

## Three defects this gate found in its own work

### 1. The classifier that matched a word instead of a meaning

Covered in doc 798. A name-matching scan flagged two tables whose `state`
column holds `'active'`. Fixed by classifying by meaning with a declared reason
per table.

### 2. Asking the replay about the wrong key

`nf_tenant_digest_records` carries both an `id` primary key and a separate
tenant-facing `digest_id`, and `replay_digest` resolves the latter. The
verification read `id` and asked about that, and got `missing_record` back for
a digest sitting in the table.

A lookup-key mistake wearing the costume of a data-integrity failure. Had it
gone unexamined it would have read as "the restore lost a digest".

### 3. Measuring the whole chain when the check was about one link

With the key fixed, the check still reported **0 of 1 digests hash-proven** —
and passed anyway, because the source said the same thing. It was reading
`evidence_status`, which is the **weakest link**, and on the one persisted
fixture digest that link is `not_replayable`:

```text
digest_record     linked_record_found   is_proof: true
payload_hash      hash_verified         is_proof: true   ← what this check is about
delivery_intent   not_replayable        no intent names this digest
```

The weakest link is an honest Gate 152 finding about queueing. It says nothing
whatever about whether the payload still hashes, which it does. The check now
reads the `payload_hash` link.

This is the "green check with two possible causes" pattern again: the check was
passing on fidelity while reporting that nothing had been proven, and only the
count in the detail line showed it.

## A hash check with nothing to check is not a pass

Which is why the verifier has a tenth assertion beyond the nine checks:

```text
check=a_digest_hash_was_actually_proven status=PASS n=1
```

Nothing to preserve is not the same as preserved. If the dev database ever
loses its persisted digest, this fails rather than going quietly green.

## One measured run

A snapshot from a single execution. The first three move; the rest are
invariants.

```text
exported_rows                6842      live, moves with dev activity
restored_rows                6842      always equal to exported_rows
legacy_gaps                  97        live; must be UNCHANGED across a restore
restore_verification_checks  9/9       invariant
digest_hashes_proven         1         invariant: must be at least 1
real_organization_rows       0         invariant
identities_restored          0         invariant
temporary_database           removed   invariant
emails_sent                  0         invariant
live_source_calls            0         invariant
object_store_calls           0         invariant
```

An earlier run of the same verifier read 6580 rows and 93 gaps. Both moved
because the other readiness verifiers write fixtures into the dev database
between runs. That is not drift in this lane — the equality of the two sides
held in both runs, which is the only thing this verifier claims.
