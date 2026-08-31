# 686 — Gate 129: the demo operating shell

## The URL

```text
https://nf-dev.mayhem-nc.dev/?view=sc_customer_demo
```

Behind Cloudflare Access. An unauthenticated visitor gets a login screen, which
is the intended state for a dev domain and what the deployment verifier asserts.
Mayhem can show it today by signing in.

## What was missing

The page already had 291 test ids and covered eligibility, pursuit, readiness
and audit in real depth. What it did not have was a single surface saying, in
order, what NativeForge does for a Tribal government — and which parts of that
are live.

A buyer reading 95 pinned gate sections learns a great deal about the gates and
very little about the product.

## What was added

One panel, first thing under the header, with ten sections in reading order:

```text
 1  Tribal tenant profile & eligibility
 2  Source watchlist
 3  Weekly matched NOFO digest
 4  Pursuit pipeline
 5  Awarded grants workspace
 6  Award requirements & reporting deadlines
 7  Proof & audit trail
 8  Document metadata
 9  Readiness & blockers
10  Next actions
```

Each carries a status chip, the table behind it, its blocking reasons, and rows
written.

```text
Operational              live, with real rows
Built — not operational  schema, repository and write path all exist
Not built                no table declares it
```

Today: **0 operational, 6 built, 3 not built, 1 view with no lane of its own.**
Every one of the six gives the same reason — `no_customer_auth_so_nobody_owns_the_row`.

## The truth labels, and why they are computed

Six labels sit above the sections:

```text
CONTROLLED DEMO DATA
AUTH NOT LIVE
LIVE SOURCE MONITORING NOT ACTIVE
EMAIL DELIVERY NOT ACTIVE
OBJECT STORE NOT CONFIGURED
PROVIDER CONFIG REQUIRED FOR LOGIN
```

None of them is a string typed into the page. Each carries `active`, computed
from the service that owns that question, and `derived_from` naming it:

```text
CONTROLLED DEMO DATA                 spine.persisted + every lane's rows_written
AUTH NOT LIVE                        activation_gate.customer_auth_live
LIVE SOURCE MONITORING NOT ACTIVE    spine.requires_live_source_collection
EMAIL DELIVERY NOT ACTIVE            spine.requires_email_delivery
OBJECT STORE NOT CONFIGURED          spine.requires_document_storage
PROVIDER CONFIG REQUIRED FOR LOGIN   provider_readiness.provider_ready
```

This campaign has found the same defect in seven gates: a constant wearing the
shape of a measurement. A demo is where that defect would be least visible and
most expensive — a label that says AUTH NOT LIVE because somebody typed it stays
wrong forever after auth ships, and the person it misleads is a Tribal
government.

Two tests hold the line. One flips `customer_auth_live` true and asserts the
label deactivates on its own. One tampers with the claim while leaving the label
active and asserts the shell refuses itself.

## What the shell refuses

```text
a section marked operational while auth is down   nobody owns those rows
a label disagreeing with the claim beside it      two answers to one question
any non-zero row count                            nothing has been written
fabricated / live_fetch_performed / production    all constant false
```

## Where it lives

```text
service    src/nativeforge/services/customer_demo_operating_shell_service.py
payload    frontend/src/demo/sc_customer_demo.json -> demo_operating_shell
component  frontend/src/components/DemoOperatingShell.tsx
styles     frontend/src/index.css (.nf-operating-shell*)
tests      tests/test_gate129_demo_live_auth_unfuck.py
           frontend/src/components/DemoOperatingShell.test.tsx
```

The component decides nothing. Every status arrives already computed, so the
page cannot claim a lane is live while the system says it is not.

## The sentence to refuse

> This is NativeForge running.

It is NativeForge's compliance spine, built and provably empty, rendered
honestly. The workflow is real and the refusals are real. No Tribe's data is in
it, nothing is collected live, and nobody can log in yet.
