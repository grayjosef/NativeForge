# 511 — Gate 91B/91C/91D: awarded vs pursuit lane contract

## The separation

```text
PURSUIT_LANES    pursuit | application_in_progress | submitted | award_pending
AWARDED_LANES    awarded_active | awarded_closeout | awarded_closed
INACTIVE_LANES   not_pursued | archived
                 unknown
```

**A pursuit is a possibility. An award is an obligation.** Moving between them
is not a status update — it changes what the customer owes, with federal
deadlines attached. The lane label says so: **Awarded Grants**, never
"opportunities".

`AWARDED_LANES` and `PURSUIT_LANES` are disjoint, and a test asserts it.

## `unknown` defaults to neither

Both `is_pursuit` and `is_awarded` are `False` for `unknown`, and
`human_review_required` is `True`.

Defaulting either way is wrong in a specific, asymmetric way: defaulting to
**pursuit** hides a real award and its deadlines; defaulting to **awarded**
invents obligations nobody agreed to. The honest answer is that the lane is
unresolved and a person should look.

An unrecognised lane string — including the bare `"awarded"` — resolves to
`unknown`, not to a guess.

## A pipeline stage is not a lane

`GrantPipelineStage.awarded` exists at `domain/enums.py:208` and is the only
place the word appears in the codebase. It is a plain `StrEnum` member,
assignable by anything, recording nobody.

Gate 91 does **not** remove it — other code may depend on it — but
`"awarded"` is deliberately **not** a member of `GRANT_LANES`. Passing the raw
stage value to `classify_grant_lane` yields `unknown`, and every result carries
`pipeline_stage_is_not_a_lane: True`.

### A naming note

The lane vocabulary is `GRANT_LANES`, not `LANES`. The first draft used the bare
name and the Gate 79B drift guard failed —
`test_the_bare_lanes_name_is_used_by_exactly_two_unrelated_concepts` pins that
`LANES` means exactly two things (opportunity funding lanes, seed catalog
groupings) and fails when a third appears.

The guard was right and the constant was renamed rather than the guard widened.
Three unrelated things sharing a bare name is precisely the confusion that
guard exists to prevent.

## Awarded grants are customer-specific

`build_awarded_grant_record` **raises** without a `customer_org_id`. Not
defaults, not infers from context — raises.

An awarded grant is:

```text
NOT a source registry row      (Gate 90: 55 shared candidate sources)
NOT a generic opportunity      (Baseline X: 185 shared records)
```

Those are the same for everybody. This is one customer's obligation. Three
constants say so on every record — `is_customer_specific`,
`is_source_registry_row`, `is_generic_opportunity` — with invariants behind each.

## Evidence rules on the portfolio

- **No requirement without evidence.** One lacking a quote is *not dropped* — it
  is kept, marked `human_review_required`, and given a blocked reason. A
  requirement somebody believed in is worth a human look even when its source is
  missing.
- **No due date without a source.** The reporting calendar splits into
  `dated_obligations` and `undated_obligations`, and `dates_inferred` is a
  constant `0`.
- **A frequency is not a deadline.** "Quarterly" with no stated date produces
  *zero* dated obligations, not four. A test pins that directly.
- **Missing award details** produce `HUMAN_REVIEW_REQUIRED` and
  `administrable_from_this_record: False` — never a computed default.

## Projected burden is not active obligation

| | Projected | Active |
| --- | --- | --- |
| service | `pursuit_reporting_burden_projection_service` | `awarded_grant_portfolio_service` |
| field names | `projected_*_requirements` | `*_requirements` |
| flag | `is_active_obligation: False` | `is_active_obligation: True` |
| calendar | none | `reporting_calendar` |
| when | before award | after award |
| if wrong | a bad pursuit decision | a missed federal deadline |

The two are **structurally** distinct, not merely labelled: a test asserts
`reporting_requirements` is absent from a projection and
`projected_reporting_requirements` is absent from an awarded record, and that
only the awarded record carries a calendar.

Every projection field is prefixed `projected_`, enforced by an invariant that
walks the result keys.

## Burden is not eligibility

```text
manageable | manageable_with_support | high_burden |
requires_dedicated_staff | requires_new_systems | unclear | human_review_required
```

- **High burden does not mean ineligible.** `affects_eligibility` is a constant
  `False` and must never be wired into the exclusion model.
- **Unclear burden does not mean no-go.** It means human review before the
  pursuit decision.
- **Absence of evidence is not evidence of low burden.** An incomplete
  extraction yields `unclear`, never `manageable` — and a *complete* extraction
  that found nothing also yields `unclear`, because a document may simply not
  state its reporting terms.

A determinate burden requires both a complete read and evidenced requirements;
an invariant fails otherwise.

## On the commercial incentive

`system_need` feeds NativeForge sales and support recommendations. A projection
that overstates burden sells more software.

The evidence rules are what keep that honest. Every projected requirement needs
a quote, and a burden derived from no requirements at all is `unclear` — never
`requires_new_systems`.
