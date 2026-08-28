# 590 — Gate 107A: honest mixed corpus derivation survey

Written before any code or fixture change. Every number below was reproduced by
running the tree.

## Gate 106 blocked regeneration correctly

Gate 106 refused to regenerate `nf14_mixed_corpus.json` because the same
regeneration that absorbs three correct Gate 105 corrections would also copy a
row's synopsis into its `eligibility_text` and narrow an unknown to a negative.
That refusal stands up: both defects are real, both are reproducible, and this
gate fixes them at the source rather than relaxing the attestation.

## Defect 1 — synopsis copied into eligibility_text

`mixed_corpus_grant_field_derivation_service.py:98`

```python
if parsed.get("eligibility_text") and not out.get("eligibility_text"):
    out["eligibility_text"] = parsed["eligibility_text"]
```

For an NF-13 row the builder passes only `{"synopsisDesc": synopsis}`. The parser
therefore produces an `eligibility_text` composed **entirely of synopsis prose**,
and this line adopts it into the field that means "what the source says about who
may apply".

Exposure, measured:

```text
NF-13 rows where the copy fires                 1   nf13-real-fed-025
of those, declaring empty_honestly              1   nf13-real-fed-025
NF-14 pulls declaring honest emptiness          0
```

The guard `not out.get("eligibility_text")` means only a row with nothing
recorded can be overwritten. Exactly one row qualifies, and it is the row whose
synopsis says *no NOFO exists*.

## Where honest emptiness is represented — and a correction

The Gate 107 brief proposes gating on `empty_honestly=True or
never_synthesized=True`. Measured across the NF-13 fixture:

```text
empty_honestly = True      1 row    nf13-real-fed-025
no_live_nofo = True        1 row    nf13-real-fed-025
never_synthesized = True  40 rows   every row in the fixture
```

`never_synthesized` is a **corpus-wide provenance assertion** — "nothing in this
row was fabricated" — not a statement that the row is empty. Using it as the
discriminator would make the guard fire on all 40 rows, which happens to be
harmless here only because the copy already requires an empty `eligibility_text`.
A guard whose stated condition is true of everything is not a guard; it is a
coincidence waiting to be edited into a bug.

`empty_honestly` and `no_live_nofo` are the row-specific declarations.

## A better rule is available: detected, not declared

The parser already reports what its output was built from:

```text
                          fed-025    fed-016
applicant_types_text      ''         ''
applicant_eligibility_desc ''        ''
synopsis_desc_included    True       True
```

So the honest condition does not need a row flag at all. Adopt
`parsed["eligibility_text"]` **only when it is backed by real eligibility
fields** — `applicant_types_text` or `applicant_eligibility_desc` non-empty. When
the only contribution was `synopsisDesc`, refuse.

This is better than either flag-based option:

```text
gating on never_synthesized   fires corpus-wide; discriminates nothing
gating on empty_honestly      fixes one row, leaves the class open
gating on parser provenance   fixes the class, and is observed rather than
                              trusted - a future row with the same shape is
                              covered without anyone remembering to flag it
```

The row flags are kept as a second, independent condition. Defence in depth: a
row that declares its emptiness honest is never overwritten regardless of what
the parser reports.

## Defect 2 — unknown narrowed to a negative

`mixed_corpus_grant_field_derivation_service.py:116`

```python
elif out.get("applicant_types_include_tribal") is None:
    out["applicant_types_include_tribal"] = False
```

Unknown becomes an affirmative negative because nothing said otherwise. That is
the inverse of deny-by-default and it asserts more than the source supports:
`False` claims the applicant types are known and exclude Tribes.

Exposure, measured:

```text
NF-13 rows reaching this narrowing   1   nf13-real-fed-025
  has structured applicantTypes      False
  has source eligibility_text        False
  tribal_eligible                    False
```

### When is a negative actually earned?

`False` is defensible when something describing who may apply was read and did
not include a Tribal class:

```text
structured applicantTypes present, none Tribal      -> False is evidence-backed
source eligibility_text present, no Tribal language -> False is evidence-backed
neither present                                     -> None (unknown)
```

`nf13-real-fed-025` has neither. There is no NOFO, so nobody has said who may
apply. `None` is the honest answer, and it is the answer the cached fixture
already holds.

## Rows affected

```text
nf13-real-fed-025    both fixes apply; returns to eligibility_text '' and
                     applicant_types_include_tribal None
all other NF-13 rows the copy never fires (they already have eligibility_text);
                     the narrowing never fires
all NF-14 pulls      supply real applicantTypes / applicantEligibilityDesc, so
                     the parser-provenance rule leaves them untouched
the three Gate 105 rows  unaffected by these fixes - their correction comes from
                     the canonical Tribal classifier, not from either path here
```

Predicted post-fix diff against the cached manifest: **3 rows, 3 fields, all
`applicant_types_include_tribal` False -> True**. Confirmed after implementation
in 592.

## Existing test coverage

```text
guards honest-empty eligibility_text     none
guards None/unknown preservation         none
```

Neither behaviour was tested, which is why both defects survived. Gate 106's
tests assert the *drift exists*; they do not assert the derivation is honest.
Gate 106's tests will need updating once the drift is gone — they currently pin
the blocked state, and pinning a resolved blocker would be a false assertion.

## Determinism

Fresh derivation is deterministic today (three runs, identical sha256), and
neither fix introduces ordering, time or randomness. Re-verified after
implementation before any regeneration.

## Plan

```text
107B  refuse synopsis-only eligibility_text, by parser provenance and row flags
107C  preserve None unless a negative is evidence-backed
107D  re-run the Gate 106 attestation unchanged
107E  regenerate only if it reports safe
```

The attestation is not modified to permit the regeneration. If it still refuses,
the fixture is not written.
