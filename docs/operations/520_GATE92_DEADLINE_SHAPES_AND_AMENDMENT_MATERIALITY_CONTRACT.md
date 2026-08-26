# 520 — Gate 92: deadline shapes and amendment materiality contract

## One date field is wrong, and the research pass says how

Five shapes were verified, each of which breaks a single-date model:

| pattern | evidence |
| --- | --- |
| `dual` | Every DOJ opportunity has a Grants.gov deadline **and** a JustGrants deadline — 11:59 p.m. ET and 8:59 p.m. ET. Both binding. |
| `per_region` | EPA GAP publishes ten regional deadlines inside one national NOFA. A national date is not a simplification of that; it is wrong for nine regions. |
| `revised` | HUD labelled an ICDBG date "New Deadline." Deadlines are mutable and versioned. |
| `phased` | USDA NIFA TCRGP phase deadlines appear only in an "Upcoming Program Events" block on the program page. |
| `multi_year` | FHWA TTPSF's operating NOFO spans 2022–2026 at Amendment No. 2. The amendments change, not the NOFO. |

Plus `single`, and `unknown` — which is the default. `dual`, `per_region` and
`phased` are marked multi-valued, and an invariant fails any of them carrying
fewer than two deadlines: a collapsed multi-deadline record looks correct and
is not. A `revised` record without its superseded deadline also fails — the old
date is the evidence that a revision happened.

## No date is ever synthesized

A deadline pattern is `unknown` unless it was verified, and a historical pattern
is never turned into a current date. `dates_synthesized` and
`dates_inferred_from_pattern` are both 0, checked by an invariant. This
continues Gate 87's finding: a date with no evidence behind it is a placeholder,
and presenting one as current is worse than presenting none.

## forecast_lapsed

A forecast whose Estimated Synopsis Post Date has passed with no synopsis and no
archive is the common failure mode of naive trackers — it keeps looking like a
live opportunity forever. It gets its own explicit lifecycle state. Invariants
run in both directions, so the state and the flag cannot disagree, and a lapsed
forecast cannot be quietly filed as `open`.

## Amendments are classified from named fields

`synopsisModifiedFields[]` / `forecastModifiedFields[]` is a literal list of the
fields the agency changed. Nothing else in the federal ecosystem provides it, so
it is the primary signal: amendments are classified from the named fields rather
than from a whole-record diff, and users are told *what* changed — "the close
date changed", not "something changed".

Seven categories, four of which notify:

```text
NOTIFY      deadline_change  eligibility_change  funding_amount_change
            attachment_change
SUPPRESS    contact_change   descriptive_text_change   uncategorized_change
```

Un-triaged amendment noise is what makes grant alerting unusable, so
contact-name churn and description typos are classified, recorded, and
suppressed — not discarded. An invariant asserts that the material and
suppressed sets together account for every category found, so nothing is
silently dropped, and an unrecognised field name lands in
`uncategorized_change` (reviewable) rather than vanishing.

`attachment_change` notifies because a changed NOFO PDF with an unchanged
synopsis is a real and easily missed case — the eligibility answer for a `25` or
`99` opportunity lives in that PDF.

## The polymorphic field trap

The extract's "Last Updated Date or Created Date" field holds the **created**
date when an opportunity has never been updated. A value there does not prove an
update occurred.

So when that field is the only evidence, `amendment_confirmed` is False, and an
invariant fails any record that confirms an amendment from it alone. Without
this, every never-updated opportunity in the corpus would appear to have been
amended on the day it was created.

## Nothing is sent

`notifications_sent` is 0 and an invariant keeps it there. This service decides
what *would* be material. Delivery is not built.
