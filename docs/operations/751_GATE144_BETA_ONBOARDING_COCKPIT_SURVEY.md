# 751 — Gate 144A: what a cockpit would show, and what already exists

Survey before implementation. Nothing was built while writing this.

## What cockpit surfaces already exist

Five, dispatched from one union in `frontend/src/viewSurface.ts`:

```text
workspace              the default M0 flow
workbench              ?view=workbench
activation             ?view=activation
nm_wa_operator_demo    ?view=nm_wa_operator_demo
sc_customer_demo       ?view=sc_customer_demo
```

`App.tsx` reads the surface once, keeps it in state, pushes it into the URL, and
renders one page per branch. Adding a sixth is a union member, a `readSurface`
branch, a dispatch branch and a page — the pattern is already there and is not
being invented for this gate.

`ScCustomerDemoPage` reads a **committed JSON payload**
(`frontend/src/demo/sc_customer_demo.json`) rather than calling the API. That is
the shape Gate 141's payload-determinism verifier already checks, and it means a
new surface can be either payload-driven or API-driven without disturbing it.

## What readiness data is available through routes

A great deal, added by Gates 138–143 and all behind
`require_demo_org_session`:

```text
GET  .../awarded-grants                            Gate 139
GET  .../documents/{id}/body-storage               Gate 141
GET  .../digest/readiness                          Gate 140
GET  .../digest/delivery/readiness                 Gate 142
GET  .../source-monitoring/readiness               Gate 143
GET  .../source-monitoring/blockers                Gate 143
```

Each answers for **its own lane**. Nothing answers "what is the state of this
deployment", which is the cockpit's question and the gap this gate fills.

## What is backend-only

Everything from Gates 138–143. Six readiness services, six verifier scripts and
roughly forty routes have no frontend surface at all:

```text
customer_persistence_activation_service          no UI
awarded_operational_tracking_readiness_service   no UI
tenant_digest_operational_readiness_service      no UI
document_storage_readiness_service               no UI
email_delivery_readiness_service                 no UI
source_monitoring_readiness_service              no UI
```

An operator's only view of any of it today is a shell prompt and a verifier's
`RESULT=` line.

## What is missing from the frontend

```text
a lane-by-lane status view
a distinction between operational, readiness-only and blocked
the blockers, named
the next safe action
a plain statement that production is not live
```

`OrgReadinessCard` and `TrustCenterCard` exist in the workspace, and both are
about **one organization's** grant readiness — a different question from "what
can this deployment do". Reusing either would conflate them.

## Which statuses can safely display

All of them, because every one is already derived rather than declared, and
because the cockpit reports the deployment's own state rather than a customer's:

```text
login_live                       true
customer_persistence_live        true
awarded_operational_tracking     true
tenant_digest_operational        true
document_metadata_operational    true
email_delivery_readiness         true
source_monitoring_preflight_ready true
```

None of those names a Tribe, a person, a grant or a deadline. A cockpit that
displayed a customer's pipeline would be a different and riskier surface.

## Which statuses must remain blocked

```text
customer_auth_live               false, blocked by invite_binding_passed
verified_operational_binding     false, Gate 137's two-part owner decision
source_monitoring_live           false, five scheduler components absent
email_delivery                   false, no provider and no send activation
object_store_configured          false, five settings absent
document_body_storage_ready      false, no adapter in runtime
controlled_customer_pilot        false
production_rollout               false
```

The cockpit's job is to show these **as false, with the reason**, which is the
opposite of hiding them. A dashboard that showed only the green lanes would be
the most dangerous artifact this campaign could produce.

## Can the cockpit be route-live without production activation?

Yes. Every fact it needs is already computed by a service that contacts nothing:

```text
no live source is called          Gate 143's guard scans 1088 files
no email is sent                  Gate 142's preflight has no provider
no object store is contacted      Gate 141: no SDK is installed
no collector runs                 Gate 143: runtime_mode is dry_run_in_process
```

So a cockpit route reads services and returns booleans. It activates nothing
because there is nothing in it that could.

## Can the demo org be used safely?

Yes, and it is the only one that may be. `bbbbbbbb-cccc-dddd-eeee-ffffffffffff`
is the standing authorization from Gate 135; `aaaaaaaa-…` is not, and no route
this gate adds will reach it.

The cockpit reports **deployment** facts, not tenant data, so even the demo
org's rows are not read except through the readiness services that already read
them.

## One thing worth being careful about

Several readiness services take injectable proofs so their permitted branches
stay reachable — `tenant_digest_operational` needs a route smoke,
`document_body_storage_ready` needs a body-route proof, and so on. A cockpit
that supplied those proofs itself would be **grading its own homework**: it
would report `true` for a lane whose evidence it invented.

So the summary service must call each lane's own *measurement*, and where a lane
needs evidence the cockpit cannot honestly produce, it must report
`readiness_only` or `blocked` rather than assuming. That is the defect most
likely to be introduced by this gate, and the tests target it directly.

## Exact blockers remaining

```text
invite_binding_passed        a second real person accepting a real invite
verified_operational_binding Gate 137's owner decision
source_monitoring_live       171 terms reviews + 5 scheduler components
email_delivery               a provider, a service, an explicit activation
object_store_configured      five settings and an owner decision
controlled_customer_pilot    not approved
production_rollout           not approved
```

## What this gate will and will not do

Will:

```text
build one summary service that aggregates the six lanes by MEASURING them
build four cockpit routes behind the demo org session
add a sixth frontend surface, following the existing pattern exactly
show every false lane, with its blocker named
show the next safe action
build a verifier, seven artifacts, tests and four docs
```

Will not:

```text
activate a controlled customer pilot
claim production readiness
change any lane's value
supply a lane its own evidence
name a Tribe, a person, a grant, an eligibility or a deadline
break ?view=sc_customer_demo
add a public bypass
```
