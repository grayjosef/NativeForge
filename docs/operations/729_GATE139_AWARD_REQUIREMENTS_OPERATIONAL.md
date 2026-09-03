# 729 — Gate 139: award requirements operational

## The routes

```text
POST   .../awarded-grants/{award_id}/requirements   create, attached
GET    .../awarded-grants/{award_id}/requirements   list for that award
GET    .../requirements/{requirement_id}            read one
POST   .../requirements/{requirement_id}/archive    archive
```

## Attachment is same-organization, and the id is never trusted

A requirement's `awarded_grant_id` must name an award **this organization
owns**. That is checked by reading the award through the anchored read before
the write:

```python
found = award_repo.get_awarded_grant(
    connection=db.connection(), organization_id=str(org_id), award_id=str(award_id)
)
if not found["rows_read"]:
    404 awarded_grant_not_found_in_this_organization
```

`awarded_grant_id` is in the repository's `FORBIDDEN_ANCHOR_NAMES`: it is a
relationship, never the authority. Anchoring on it would make this table's
policy depend on another table's.

Measured: a requirement pointed at another organization's award gets **404**.

## The two refusals this gate was forbidden from weakening

### No fabricated requirement

`requirement_source` has **no default**. The vocabulary already distinguishes
where a requirement came from:

```text
human_entered              a person typed it
evidence_extracted         something read it out of a document
projected_from_nofo        derived from the notice, and labelled as derived
needs_human_review         something tried and could not be sure
unsupported_document_type  the document could not be read at all
unknown
```

A route that defaulted this to `evidence_extracted` would be claiming an
extraction happened. Omitting it is a **422**, and a test proves that.

An unsupported requirement stays unresolved:

```text
requirement_status  needs_human_review
requirement_source  unsupported_document_type
requirement_due_date  absent
```

and the read reports `"unresolved": true` rather than leaving a caller to infer
it from the status vocabulary.

### No inferred deadline

`requirement_due_date` is accepted **only** alongside a `due_date_status` the
caller also supplies. A bare date is a **422** from the route's own validator:

```text
due_date_supplied_without_a_due_date_status
```

The status vocabulary exists so an unsure date can be stored as unsure:

```text
verified | calculated | estimated | needs_human_review | unsupported | unknown
```

Accepting a date without one would make every date read as `verified` to
whoever looked at it next. And a test parses the route module for `timedelta`,
`relativedelta`, `date.today` and `datetime.now` and asserts none of them
appear — nothing here reads a title and produces a deadline.

`award_requirements_repository_service.prohibited_inferences()` already named
what may not be derived. This route adds no exception to it.

## No update, again

```text
POST .../requirements/{id}/archive
```

and nothing else. The repository:

> "There is no upsert. A requirement that recurs is many rows, one per period,
> because a compliance calendar is a list of dated obligations and overwriting
> last quarter's row erases whether last quarter was met."

So "mark this satisfied" is a new row plus an archive of the old one. The
archive response carries the reason in the payload:

```json
"update_path_available": false,
"update_path_available_because":
  "a recurring obligation is many rows, one per period; overwriting last
   quarter's row erases whether last quarter was met"
```

## What a caller cannot set

`is_demo`, `fact_status`, `organization_id`, `tenant_id`, `customer_org_id`,
`organization_profile_id`, `customer_auth_live`,
`verified_operational_binding`, `object_store_configured` — all **400**, by
name. Every row is `demo_fixture` and `is_demo`, forced.
