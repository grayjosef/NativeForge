# 670 — Gate 124: awarded grants validation

What makes a stored award fit to drive obligation tracking, and the defect found
while building it.

## The distinction the service exists for

```text
projected burden   what a NOFO suggests will be required if you win
active obligation  what this award requires, now
```

Gate 91 built `pursuit_reporting_burden_projection_service`: every field
prefixed `projected_`, every result stamped `is_active_obligation: False` and
`requires_award_before_obligations_begin: True`.

That refusal is one-directional, and this service is the other end of it.
Nothing here promotes a projection; `projected_burden_considered` is a constant
`False` with an invariant behind it. A test takes a **fully evidenced**
projection — extraction complete, no unevidenced requirements, the strongest the
pursuit side can produce — and shows the award side still reports
`obligations_established: False`.

## The defect: a claim reported as a derivation

The first version of this service had one field:

```python
"obligations_established": obligation in OBLIGATING_STATUSES
```

That is what the row **said**. Three invariants then treated it as what the
service had **concluded**:

```text
obligations_established without established facts
obligations_established without a capable extraction
obligations_established on a non-live award
```

So any caller writing `obligations_established` on an unverified award tripped
an invariant. An invariant that ordinary bad input can fire is not an invariant
— it is a validation rule with the wrong name, and it makes the real thing the
invariant was for unfalsifiable.

The fix separates the two:

```text
obligations_claimed      the row says `obligations_established`
obligations_established  and every condition for that actually holds
```

`obligations_established` is now a conjunction — the claim, established facts, a
capable extraction, a live award, and both vocabularies valid — so those three
invariants can no longer fire on input. They fire only if the derivation itself
breaks. A fourth invariant covers the new gap: a claim refused without a named
reason.

This is the same family the campaign has found in five consecutive gates —
Gate 120's filename probe, Gate 121's callback URL, Gate 122's provider
miscount, Gate 123's conflated profiles, Gate 124A's five mis-mapped lanes.
This one was mine.

## The rules

```text
title        the one field that cannot be unknown. A row nobody can name is a
             row nobody can act on
status       never inferred. `unknown` stays unknown and says so
amount       never inferred, never defaulted to zero. A zero in a funding
             column reads as a real number to everything downstream
currency     required alongside an amount, refused without one. ISO 4217 is
             three letters; anything else is a symbol somebody typed
period       a reversed period is refused, not swapped and not clamped - both
             plausible corrections are guesses about which end was mistyped
lineage      validated for shape and nothing else
```

An unknown amount cannot sit on an established `fact_status`. The same rule Gate
123 applied to recognition status, and the database enforces it too.

## The three conjuncts behind an obligation

```text
fact_status in {verified, tenant_supplied}   somebody established the award
extraction in {human_entered,                somebody established the
               evidence_extracted}           requirements
award_status in {active_award,               the award is actually live
                 closeout_pending}
```

`demo_fixture` is deliberately outside `ACTIONABLE_FACT_STATUSES`, which is why
a fixture award can be stored and can never establish an obligation: storable
and inert. All eleven fixture cases establish zero obligations.

An obligation on an award that is not live is a contradiction — a closed or
cancelled award obliges nobody — and archiving sets `obligations_closed`
whatever the row held before.

## The validation matrix

Ten cases, written to `awarded_grants_validation_matrix.csv`. Each row reports
`obligations_claimed` and `obligations_established` side by side, because a
matrix reporting only the derived value could not show a claim being refused,
and that is most of what these cases demonstrate.

## The artifact scan this gate added

```text
1  by field name    anything named like real award data - award_amount included
2  by inference     any result claiming an inference this campaign prohibits
3  by promotion     any payload asserting that somebody owes something
```

The third fired on its own intended output first, exactly as Gate 121's leak
scanner did. A matrix row *showing a refused claim* legitimately carries
`active_obligation_status: obligations_established`.

The fix narrows rather than drops it:

```text
active_obligation_status  obligations_established  verdict
obligations_established   present and False        a refused claim, allowed
obligations_established   absent, or True          an assertion, refused
```

`award_amount` is in the forbidden-field scan because a real award amount is the
number an auditor reconciles against, and an artifact is the wrong place for it.
