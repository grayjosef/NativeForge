# 597 — Gate 108D/E: requirement model and calendar contract

`src/nativeforge/services/award_requirement_model_service.py`
`src/nativeforge/services/award_requirements_calendar_service.py`

## Three questions, three vocabularies

The design mistake this avoids is one `status` field carrying all of it.

```text
requirement_status   where the work stands         not_started ... accepted
due_date_status      how the date was arrived at   verified ... unsupported
extraction_status    where the requirement came from human_entered ... unknown
```

A requirement can be `in_progress` against an `estimated` date that was
`projected_from_nofo`. Collapsing those forces a caller to guess which meaning is
intended, and guessing is how an estimate becomes a deadline.

Fifteen requirement types are supported, and Gate 91's five portfolio categories
are imported and mapped onto them — `portfolio_categories_are_fully_mapped()`
fails if Gate 91 grows one this misses.

## Projected burden is not an active obligation

The rule the whole gate turns on.

```text
projected_from_nofo   a burden guessed from a notice before the award existed
                      -> is_active_obligation: False
                      -> a person must confirm before it becomes a duty
```

Gate 91's `pursuit_reporting_burden_projection_service` already stamps
`is_active_obligation: False` on every projection. This carries that boundary
across the award transition rather than letting it dissolve there.

Two invariants hold it: a projection marked active fails, and an active
obligation whose provenance cannot support one fails. Both mutations are caught.

## Unsupported document types do not create verified requirements

An `unsupported_document_type` means a package arrived that nobody could read.
That is a different state from a requirement nobody looked for, and both differ
from one with a confirmed date.

```text
extraction_status = unsupported_document_type
    -> due_date_status forced to unsupported
    -> date_is_calculable false
    -> blocked reason recorded
```

An invariant fails an unreadable document that produced a supported date.

## Unknown due dates remain unknown, and remain visible

No date is computed from a default. `due_date_inferred` is a constant `False`,
and the calendar reports `dates_inferred: 0` — the rule Gate 91's calendar
established.

The calendar's job is to not hide them. A compliance calendar that silently omits
what it cannot date shows a tenant a short clean list and lets a real obligation
pass unnoticed. **Absence of a date is not absence of a duty.**

```text
every requirement appears in calendar_items
undated ones carry calendar_placement: undated and a reason
items_unknown_due_date counts them where a person can see the number
```

Mutations that hide undated items or zero the count are both caught.

## A countdown needs a date somebody can vouch for

```text
verified / calculated   overdue and due_soon may be computed
estimated               shown, never counted down
unknown / unsupported   shown as undated, never "no deadline"
needs_human_review      shown, routed to a person
```

An estimate presented as a countdown is how a tenant misses the real date while
believing they had a week left. An invariant fails any countdown on a date status
that cannot support one, and another fails an estimate that was counted down.

## No implicit clock

`reference_date` must be supplied. Without it nothing is counted down and
`no_reference_date_supplied` is recorded.

A calendar that reads the wall clock gives a different answer every run and
cannot be attested — the same reason the demo fixture pins `REFERENCE_NOW`.

## Confidence is measured

```text
documented       every active obligation carries a date somebody can vouch for
mixed            some do
estimated_only   none do, but estimates exist
no_obligations   nothing is owed here yet
```

Derived from the items, and an invariant fails a confidence that disagrees with
them. A calendar built entirely from estimates reports low confidence rather than
looking identical to one built from award documents.

## Tenant and award scoped first

`build_requirements_calendar` filters by tenant id and award id before it looks
at anything else, so another tenant's requirement can never appear. A mutation
removing that filter is caught.
