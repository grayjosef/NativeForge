# 700 — Gate 132: three sources, one answer about which orgs are demo

Mayhem made this a precondition of writing any row, and it was the right call:
the inconsistency sat directly under the membership about to be created.

## The defect, measured

```text
settings allowlist              []       NF_DEMO_ORG_IDS unset
organizations.org_type          demo     for bbbbbbbb-cccc-dddd-eeee-ffffffffffff
demo_isolation.org_type_for()   real     for that same organization
nf_org_memberships.is_demo      whatever the caller passed
```

`org_type_for()` classifies by the settings allowlist alone. An empty allowlist
therefore made **every organization real**, including the one whose own column
says `demo`.

That is not cosmetic. Every tenant table carries

```sql
organization_id = current_setting('app.current_org_id', true)::uuid
AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
```

so an organization classified `real` while its rows are written `is_demo = true`
splits one organization across both partitions — and a demo organization
classified `real` puts demo rows where a real session reads them.

## The authority: the `organizations` row

It is the only one of the three that is a fact about the organization rather
than a statement about a deployment. The allowlist is configuration a deployment
may not have set — this one had not. `nf_org_memberships.is_demo` is whatever a
caller wrote, which makes it a record of a decision, not the decision.

So `demo_org_classification_service.classify_organization()` reads the row, and
`is_demo` is derived from it and from nothing else. There is no `is_demo`
parameter on that function or on `prepare_membership_insert`, which is the
point: a value that cannot be supplied cannot be supplied wrongly.

## The allowlist is compared, not ignored, and not overridden

```text
allowlist empty        silence, not disagreement. The database answers alone.
allowlist agrees       classification available
allowlist disagrees    classification REFUSED, by name
```

A deployment that has listed its demo organizations and a database that
disagrees is a misconfiguration somebody needs to see. Picking a winner would
hide it. `reconcile_demo_org_allowlist()` reports
`allowlist_that_would_agree` — reported, never applied, because an allowlist
that heals itself from the database is not a second source and comparing a value
against its own origin is vacuous.

## What changed on this machine

`NF_DEMO_ORG_IDS` was set in `.env` to the demo organization's id. That is a
deployment configuration change, not a code change, and it is what makes the
three sources agree:

```text
before   allowlist_matches_database  false
         allowlist_that_would_agree  [bbbbbbbb-cccc-dddd-eeee-ffffffffffff]

after    allowlist_matches_database  true
         disagreements               []
         org_type_for(demo org)      demo     (was real)
```

`.env` is gitignored, so this is recorded here rather than committed. A
deployment that does not set it gets the database's answer, which is now the
same answer.

## It also un-broke the demo plane

`require_demo_org` refuses any context whose `org_type` is not `demo`, and the
demo frontend runs on `plane = "demo"` with `DEFAULT_ORG` set to the demo
organization. With the allowlist empty that combination refused itself:

```text
allowlist EMPTY   org_type_for(demo org) = real   require_demo_org -> 403
allowlist SET     org_type_for(demo org) = demo   require_demo_org -> 200
```

Measured against the running backend afterwards:

```text
/v1/nf/demo/orgs/<demo org>/grant-sparks   200
/v1/nf/real/orgs/<demo org>/grant-sparks   403
```

Demo-plane routes now answer the demo organization and real-plane routes refuse
it. Before, both were the wrong way round. That was not the reason for the
reconciliation and it is not a claim about the demo working end to end — the
frontend renders from a committed payload — but it is a live 403 that this
change removed, and it had been sitting there since `NF_DEMO_ORG_IDS` was
introduced.

## What was deliberately not changed

`lib/demo_isolation.py` still classifies from the allowlist alone. It is
documented as model-agnostic and takes no connection, and rewriting it to read
the database would give it a dependency its whole design excludes. The new
service is what anything writing rows must use; the old one is now correct on
this deployment because the allowlist agrees with the database.

That leaves a residual: a deployment that forgets `NF_DEMO_ORG_IDS` gets a
correct answer from `classify_organization` and a wrong one from
`org_type_for`. Naming it rather than fixing it here, because the fix is either
a connection in a module built to avoid one, or removing `org_type_for`'s
callers — and `api/isolation_deps.py` is Gate 122's territory, where the dev
header it serves is already scheduled for removal.
