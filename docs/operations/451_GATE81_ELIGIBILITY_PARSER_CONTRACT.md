# 451 — Gate 81C: Eligibility parser contract

`src/nativeforge/services/nofo_eligibility_parser_service.py`
Schema `nf_nofo_eligibility_parser_v1`.

Decides, per applicant class, what a notice's eligibility sections actually
support — with a character span for every claim.

## Applicant classes

Twelve. A **superset** of the canonical eight, never a fork:

```text
canonical (eligibility_exclusion_evidence_service.APPLICANT_CLASSES)
  federally_recognized_tribe   state_recognized_tribe   tribal_organization
  native_nonprofit             native_business          bie_funded_school
  native_individual            unknown

added here (NON_NATIVE_CLASSES)
  local_government   state_government   nonprofit   education_institution
```

A test asserts `APPLICANT_CLASSES < PARSER_APPLICANT_CLASSES` and that the
difference is exactly `NON_NATIVE_CLASSES`.

### Why the four extra classes exist

They are not there to broaden the product. They are there so **exclusive lists
become readable**.

`analyse_eligibility_text` computes `is_exclusive_list` as
`bool(markers and named)`. A notice reading *"Eligible applicants are units of
local government"* names nothing the canonical vocabulary knows, so `named` was
empty, the list never registered as exclusive, and every Native class came back
`not_supported_by_evidence` — when the text plainly excludes them.

They are dropped before anything reaches the exclusion contract. An invariant
fails any non-canonical class appearing in `excluded_classes`, and
`all_classes_invariant_failures` still sees exactly the canonical seven.

## How eligibility is evidenced

Only text inside a detected eligibility section is ever considered. The parser
takes the Gate 81B extraction and re-slices the original `raw_text` by each
eligibility section's span, so citations stay absolute against the real notice.
Without `raw_text` it falls back to the clipped section quotes and reports
`spans_absolute: false`.

Class detection reuses the canonical `CLASS_PHRASES` by import — never a copy —
so phrasing stays owned by one module. `ALL_CLASS_PHRASES` layers the four
non-Native maps on top.

### The specific rules

| Text | Result |
| --- | --- |
| "federally recognized Indian tribes" | supports `federally_recognized_tribe` only |
| "state-recognized tribes" | supports `state_recognized_tribe` only |
| "tribal organizations" | supports `tribal_organization`, **not** tribal governments |
| "BIE-funded schools" | supports `bie_funded_school` only |
| "federal trust land" | a **restriction**, never eligibility |

The two recognition tiers are never collapsed: a notice limited to federally
recognized tribes excludes state-recognized ones, and a notice naming both
admits both. Both directions are tested.

## How exclusions are evidenced

Two paths, both citation-required.

**Exclusive list.** Markers (`only`, `limited to`, `eligible applicants are`,
...) plus a named class make the list exclusive; classes it omits are excluded.
Absence of a class in a *non*-exclusive list proves nothing and yields
`not_supported_by_evidence`.

**Explicit negation.** *"Federally recognized tribes are not eligible under this
program"* names the class. Naive matching read that as **eligible** — a false
positive in the worst possible direction, telling a tribe to spend weeks on a
programme that had already ruled them out in writing. The parser detects
negation cues in the same sentence as the class phrase and passes
`negated_classes` to the exclusion service, which returns
`excluded_by_evidence`.

Sentence scope is deliberate. Widening past the sentence starts attaching
negations to classes several clauses away.

Both new parameters on `evaluate_applicant_class` are keyword-only and optional;
omitting them reproduces Gate 79 behaviour exactly, which a test asserts.
`additional_named_classes` can only ever make a list *exclusive* — it is never
treated as naming the class under evaluation, so it cannot manufacture
eligibility.

### Citation

The citation is the notice locator plus the span. Without `notice_url`,
`source_url`, or an explicit `evidence_reference` there is nothing to cite, so
no exclusion is produced and the result goes to human review. An invariant fails
any result carrying exclusions without a citation.

## Restrictions

Restrictions are kept as restrictions. `is_eligibility_rule` is hardcoded
`False` and invariant-checked. "Federal trust land" narrows where money may be
spent; promoting it to eligibility would silently rewrite a land-use condition
into an applicant rule, and a tribe eligible on paper would look ineligible.

## Ambiguity

`human_review_required` is set when:

- a class is both named and negated (`conflicting_classes`) — a contradiction
  we are not entitled to resolve;
- an exclusive list names nothing any vocabulary recognises
  (`exclusive_list_names_no_recognised_class`);
- there is no citable reference;
- the extraction was blocked, or no eligibility section exists.

An invariant fails any result with conflicting classes that does **not** demand
review.

## What is never asserted

```text
not_eligible_asserted             False
keyword_counted_as_eligibility    False
restriction_counted_as_eligibility False
coverage_claimed                  False
live_fetch_performed              False
```

Gate 77's boundary stands: this module never asserts universal ineligibility,
only that a cited text excludes a class.

## Why no live coverage is claimed

Nothing here fetches. Every fixture is synthetic.

## What still needs primary-source verification

The parser is only as good as the notice handed to it. No real notice has been
parsed. Phrase lists are conservative and will miss real-world phrasing —
`not_supported_by_evidence` and `human_review_required` are the honest outcomes
for anything they do not recognise, and both keep a human in the loop rather
than guessing.
