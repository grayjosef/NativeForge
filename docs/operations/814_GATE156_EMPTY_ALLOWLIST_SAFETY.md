# 814 — Gate 156: why an empty allowlist is safe, and why that is not a flag

```text
registry rows                 177
terms_blocked                 171
human_review_blocked            6
activation_approved             0
collectors registered           0
executable jobs                 0
```

## There is nothing to call

With zero sources approved, a scheduler has **no URL to fetch** even if
something wanted one. The safety here is not a flag being respected; it is an
absence of anything to contact.

That is what makes this gate safe to build before the terms review rather than
after it. A scheduler proved against an empty allowlist is a scheduler proved in
the state where a mistake costs nothing.

## Zero comes from counting, not from a guard

There is no `if allowlist_empty: return` branch. Every job refuses on its own
terms, and `jobs_executable` is the length of the list that survived:

```text
no_check_interval_recorded                  177
no_collector_is_registered_for_this_source  177
source_activation_not_approved              177
source_requires_human_review                177
source_terms_not_approved                   177
```

A guard that special-cases the safe state is a guard that stops working the
moment the state changes — it would keep returning zero after the first source
was approved, and nobody would notice until a collection window was missed.

**Proved behaviourally, not by reading the source.** A test runs the same cycle
twice: once with every prerequisite absent (0 executable) and once with every
prerequisite supplied (3 executable). If a guard existed, the second would still
be zero.

That test's first version scanned the module text for `allowlist_empty` and
failed — the docstring explaining that no such branch exists contains the word.
Substring versus meaning, in the scan written to rule the branch out.

## The permitting branch is reachable, and must be

A refusal nobody can escape proves nothing. The verifier evaluates a source with
every prerequisite affirmatively true and asserts it comes back `executable`,
then evaluates the six refusal paths and asserts each one refuses and names
itself:

```text
terms_blocked              source_terms_not_approved
human_review_blocked       source_requires_human_review
activation_not_approved    source_activation_not_approved
no_collector               no_collector_is_registered_for_this_source
disabled                   source_is_disabled
unknown_source             source_is_not_in_the_registry
```

Gate 134F's lesson: an unreachable permitted branch makes a refusal
unfalsifiable.

## Absence is never permission

```text
terms_state = "terms_approved"          permits
terms_state = "terms_unknown"           blocks
terms_state = None                      blocks
terms_state = ""                        blocks
terms_state = "probably fine"           blocks
```

Each prerequisite must equal its permitting value. The registry carries **no
terms column at all**, which is exactly why Gate 143 reports all 177 rows as
`UNKNOWN` — and `UNKNOWN` blocks.

## What would have to change for one source to become executable

```text
1  a human reads that source's terms of use            terms_approved
2  a human clears it for review                        human_review_cleared
3  an approver approves activation                     activation_approved
4  a collector is registered for it                    Gate 161
5  a cadence is recorded for it                        check_interval_days
6  the clock comes round                               due
```

Steps 1–3 are people. Steps 4–5 are gates in this block. No gate in Gates
156–165 clears steps 1–3, and building the whole block leaves all 171
terms-blocked sources exactly where they are.

## What this gate must not be read as

> NativeForge monitors grant sources.

It does not. It can now evaluate 177 sources against a clock and refuse all 177
— a scheduler that works, attached to a system that polls nothing.
