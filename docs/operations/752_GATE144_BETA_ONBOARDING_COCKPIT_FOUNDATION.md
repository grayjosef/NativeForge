# 752 — Gate 144: the beta onboarding cockpit foundation

## What it is

One place where an operator can see what this deployment can do — and, more
importantly, what it cannot and why.

```text
GET /v1/nf/demo/orgs/{org}/beta-cockpit/readiness      every lane, measured
GET /v1/nf/demo/orgs/{org}/beta-cockpit/next-actions   the one safe next step
GET /v1/nf/demo/orgs/{org}/beta-cockpit/blockers       why each lane is blocked
GET /v1/nf/demo/orgs/{org}/beta-cockpit/capabilities   what the demo org can do
```

plus a sixth frontend surface at `?view=beta_onboarding_cockpit`.

## It reports the deployment, not a tenant

No route and no card names a Tribe, a grant, an eligibility or a deadline. The
cockpit answers "what can this deployment do", which is a different question
from "what is in this customer's pipeline" — and a far safer one to put on a
screen. A test asserts it against the response's string **values**.

## Fifteen lanes, seven statuses

```text
login                          operational
customer_persistence           operational
awarded_grants                 operational
tenant_digest                  operational
document_metadata              operational
document_body_storage          not_configured
email_delivery_readiness       operational
email_delivery                 not_configured
source_monitoring_preflight    operational
source_monitoring              blocked
object_storage                 not_configured
customer_auth                  requires_human_approval
verified_operational_binding   requires_human_approval
controlled_customer_pilot      production_false
production_rollout             production_false
```

`requires_human_approval` is deliberately not `blocked`. An operator reading
"blocked" looks for a bug, and for customer auth and the verified binding there
is none — a person has to decide, and no code change moves either.

## Every false lane is shown, with its reason

That is the property that matters. A dashboard showing only the green lanes
would be the most dangerous artifact this campaign could produce, so:

```text
every lane appears                       15 of 15, asserted
every false lane carries a blocker       asserted on the route and in the summary
every blocker names an owner             asserted
production_rollout is shown as false     on the page, in words
```

## The route reports fewer operational lanes than the verifier, on purpose

```text
the route      measures what a request can measure — a persistence round trip,
               the source monitoring preflight
the verifier   runs each lane's own verifier first, then reports what they proved
```

`LANE_EVIDENCE` records, per lane, what the summary may conclude unaided. A lane
needing outside evidence — a route smoke against a live server — is
`readiness_only`, never `operational`, until something actually measures it.

This is the defect the gate was most likely to introduce, named in doc 751
before any code was written: a summary that supplied a lane its own proof would
be **grading its own homework**. The design is shaped around not doing that, and
three tests target it.

## One next safe action, not a backlog

```text
finish_the_controlled_beta_readiness_matrix

why:           every controlled_dev_demo lane that can be proved is proved; the
               remaining lanes need a human decision or an external activation,
               and neither is a code change
safe because:  it activates nothing, contacts nothing and changes no lane's value

not this yet:  activating a controlled customer pilot
               binding the real organization
               configuring an email provider
               configuring an object store
               starting a collector
```

An operator reading a cockpit needs to know what to do next, not everything that
could eventually be done.

## Nothing is activated

```text
live source calls      0
emails sent            0
object store calls     0
collectors activated   0
real org touched       no
customer data written  no
```

The cockpit reads services that contact nothing. It activates nothing because
there is nothing in it that could.
