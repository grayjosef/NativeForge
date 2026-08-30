# 669 — Gate 124: the awarded grants repository contract

What `nf_awarded_grants` is, what may enter it, and what it refuses.

## The table

```text
migration           0032_nf_awarded_grants        head 0031 -> 0032
columns             27
CHECK constraints    8
indexes              3 (one unique, partial)
RLS policy           nf_awarded_grants_org_demo_scope   PostgreSQL only
rows                 0
```

The RLS predicate is the one nineteen other tables carry, unchanged:

```sql
organization_id = current_setting('app.current_org_id', true)::uuid
AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
```

## The five identity names, and which one is authority

```text
organization_id          UUID, FK organizations, the RLS predicate's left side
tenant_beta_profile_id   UUID, FK nf_tenant_beta_profiles, ON DELETE SET NULL
tenant_id_label          text, no FK
customer_org_id_label    text, no FK
organization_profile_id  refused outright, by name
```

`tenant_beta_profile_id` is the interesting one: a real foreign key that is
still not an anchor. An award belongs to an **organization**; a beta profile is
how that organization wants to be served. If the profile is archived the award
remains, which is why the foreign key is `SET NULL` rather than `CASCADE`.

## Lineage, and why it carries no foreign key

```text
source_pursuit_id       text, no FK
source_opportunity_id   text, no FK
```

A foreign key would make a pursuit's existence a precondition for an award, and
awards arrive for things nobody pursued in this system.

Neither is ever a reason to create a row. A pursuit reaching "submitted"
produces nothing here; a human recording an award does.
`award_created_from_lineage` is a constant `False` with an invariant behind it,
and `prepare_award_write` has **no parameter** that could carry a projection —
the separation expressed as a signature rather than a runtime check.

## The eight CHECK constraints

```text
ck_nf_awarded_grants_award_status                    7-value vocabulary
ck_nf_awarded_grants_obligation_status               5-value vocabulary
ck_nf_awarded_grants_fact_status                     5-value vocabulary
ck_nf_awarded_grants_title_not_blank                 length(trim(...)) > 0
ck_nf_awarded_grants_period_order                    end >= start
ck_nf_awarded_grants_amount_needs_currency           both, or neither
ck_nf_awarded_grants_unknown_amount_is_unestablished
ck_nf_awarded_grants_obligations_need_established_facts
```

The Core `sa.Table` in `awarded_grants_repository_service` restates all eight.
Gate 119C shipped a Core table with the columns and none of the constraints,
which meant a test built a weaker schema than production and a never-expiring
row did not raise. Two tests now compare the two definitions by name.

`award_amount` is `Numeric(18, 2)`, not a float. A float is a rounding error
waiting for an audit.

## The six operations

```text
prepare_award_write       decides; touches no database
create_awarded_grant      one INSERT, if prepare permits it
get_awarded_grant         one row, anchored on organization_id
list_awarded_grants       every row, archived ones included by default
archive_awarded_grant     an UPDATE. Never a DELETE
validate_award_persistence  is what is stored fit to drive obligations?
```

There is no upsert. An award is a discrete event: a correction is a new row and
the mistaken one is archived as `mistaken_award`, so the audit trail shows what
was believed and when.

`list_awarded_grants` returns archived rows by default. A listing that hid a
`mistaken_award` would make it indistinguishable from an award that never
happened, which is exactly what a funder's audit asks about.

## Archive, never delete

```text
rows_deleted                 constant 0
sa.delete / .drop calls      0, asserted by parsing the module
mistaken_award               a status, not a deletion
```

The delete test parses the module with `ast` and looks for a `Call` whose
attribute is `delete` or `drop`. Gate 123 found the substring version matching
the docstring that explains there is no delete path — the sixth
substring-versus-meaning false positive in this campaign. The test also asserts
the prose is still present, so it would catch a real delete rather than the
explanation of one.

## What a production write requires

```text
customer_auth_live              false
verified_operational_binding    false
```

Both injectable, so the permitted branch is reachable in a test; both false in
reality. Named separately, because auth arriving without a verified binding
would still not be enough.

The guard now lists `write_awarded_grant` in `LABEL_BOUND_OPERATIONS` for the
same reason: the row carries `tenant_id_label` and `customer_org_id_label`, and
nothing relates either to the organization it is anchored on except a binding.

```text
rows in the application database    0
production awarded grants created   0
production award requirements       0
```
