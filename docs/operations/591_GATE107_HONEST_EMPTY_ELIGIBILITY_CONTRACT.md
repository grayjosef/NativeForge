# 591 — Gate 107B/C: honest empty eligibility contract

`src/nativeforge/services/mixed_corpus_grant_field_derivation_service.py`
`src/nativeforge/services/mixed_corpus_builder_service.py`

Two rules, and the reasoning that makes them rules rather than preferences.

## A synopsis is not eligibility language

`eligibility_text` means "what the source says about who may apply". A synopsis
is prose *about* the opportunity. On the one corpus row recording an unposted
NOFO, the synopsis is literally a note that no NOFO exists.

Derivation used to adopt it whenever `eligibility_text` was empty:

```python
if parsed.get("eligibility_text") and not out.get("eligibility_text"):
    out["eligibility_text"] = parsed["eligibility_text"]
```

That put manufactured text into the field `derive_explicit_source_evidence` and
the canonical Tribal classifier read, on a row that simultaneously asserted
`empty_honestly: True` and `never_synthesized: True` about itself.

### Detected, not declared

The parser reports what its output was built from, so the rule reads that rather
than trusting a flag:

```text
applicant_types_text or applicant_eligibility_desc non-empty  -> adopt
synopsisDesc was the only contribution                        -> refuse
```

`_parsed_eligibility_is_source_backed` asks that question. A future row with the
same shape is covered without anyone remembering to flag it.

### And a second, independent guard

`_declares_honest_emptiness` refuses regardless of what the parser reports, for
any row that declared its blank deliberate. Defence in depth: two conditions,
either sufficient.

Because they are redundant, neither is exercised by a row both would catch. Two
tests isolate them — one row that declares honest emptiness but whose parsed text
*is* source-backed, one that does not declare it but whose text is synopsis-only.
Without those, a mutation removing either guard survives, and both did on the
first mutation run.

### A correction to the brief: never_synthesized is not an emptiness flag

Gate 107 proposed gating on `empty_honestly=True or never_synthesized=True`.
Measured across NF-13:

```text
empty_honestly     1 row
no_live_nofo       1 row
never_synthesized  40 rows - every row in the fixture
```

`never_synthesized` is a corpus-wide provenance assertion, not a statement that
a row is empty. Using it would make the guard fire on everything, which is
harmless only by coincidence — the copy already requires an empty field. A guard
whose stated condition is true of everything is not a guard.

`HONEST_EMPTINESS_FLAGS` therefore holds `empty_honestly` and `no_live_nofo`, and
a test asserts `never_synthesized` is excluded.

## A negative has to be earned

`applicant_types_include_tribal: False` claims the applicant classes are known
and exclude Tribes. That is an assertion and it needs a source.

```text
structured applicantTypes present, none Tribal      -> False is earned
eligibility text present, no Tribal language        -> False is earned
neither present                                     -> None (unknown)
```

Derivation used to narrow `None` to `False` because nothing said otherwise —
the inverse of deny-by-default. `_negative_applicant_type_is_earned` now gates
it, and unknown survives where nobody has said who may apply.

### The same defect, a second time, in the builder

The honest-derivation report caught an instance the brief did not name.
`_pull_to_grant` seeded the field from a different question:

```python
"applicant_types_include_tribal": payload.get("tribal_eligible"),
```

`tribal_eligible` answers "may Tribes apply". `applicant_types_include_tribal`
answers "do the listed applicant types include a Tribal class". Seeding the
second from the absence of the first turned "no tribal signal recorded" into
"applicant types affirmatively exclude Tribes" on `nf14-mixed-label_spread-16` —
a row with no applicant types, no eligibility text and no eligibility
description at all.

It now seeds `True` only on a positive signal and `None` otherwise, leaving the
question to derivation's earned-negative rule.

This was in scope by the gate's own words — "False is allowed only when evidence
supports a negative classification" — and fixing it cost one extra fixture row.
The alternative was shipping an artifact whose own invariants failed, or
relaxing the invariant to ignore it. Neither is a real option.

## Unknown is a value, not an absence

Where derivation declines to assert anything, the field is still present and
explicitly `None`:

```python
out.setdefault("eligibility_text", "")
out.setdefault("applicant_types_include_tribal", None)
```

Previously the key simply vanished, so `row["applicant_types_include_tribal"]`
raised `KeyError` and "we do not know" was indistinguishable from "this field is
not part of the schema". Every real corpus row already carried both keys, so this
changed no corpus value — it closed a trap for callers.

## What did not change

```text
legitimate eligibility text   still derived from applicantTypes /
                              applicantEligibilityDesc, tested
earned negatives              still reached, tested both ways
positive tribal signals       still seeded True, tested
the Gate 106 attestation      unchanged; the gate was passed, not lowered
```
