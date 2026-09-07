# 755 — Gate 144: the beta onboarding readiness delta

## What changed

```text
                                before Gate 144   after Gate 144
cockpit foundation              did not exist     route-live, 4 routes
frontend cockpit surface        did not exist     ?view=beta_onboarding_cockpit
unified readiness summary       did not exist     15 lanes, 7 statuses
blocker matrix                  did not exist     named, with an owner each
next safe action                did not exist     one, with what is not yet
frontend surfaces               5                 6
```

**No lane's value changed.** Gate 144 built a view of what Gates 138–143
established; it established nothing new and activated nothing.

## Did the cockpit foundation become route-live?

Yes. Four routes behind `require_demo_org_session`, all returning 401
unauthenticated, all refusing a forged `X-NF-Org-Id`, all refusing a
cross-organization read.

## Does a frontend surface exist?

Yes — `?view=beta_onboarding_cockpit`, wired the same way as the five existing
surfaces, with seven tests of its own. It requires a session and tells a
signed-out visitor to sign in.

## Exact operational lanes

```text
login                          controlled_dev_demo
customer_persistence           controlled_dev_demo
awarded_grants                 controlled_dev_demo
tenant_digest                  controlled_dev_demo
document_metadata              controlled_dev_demo
email_delivery_readiness       controlled_dev_demo
source_monitoring_preflight    controlled_dev_demo
```

Seven, all `controlled_dev_demo`, none a production claim.

## Exact blocked and readiness-only lanes

```text
source_monitoring              blocked
                               171 terms reviews, 5 scheduler components

customer_auth                  requires_human_approval
                               invite_binding_passed

verified_operational_binding   requires_human_approval
                               owner_decision_absent

document_body_storage          not_configured
email_delivery                 not_configured
object_storage                 not_configured

controlled_customer_pilot      production_false
production_rollout             production_false
```

`readiness_only` is what a lane gets when its evidence was not supplied — the
route reports several that way, because a request measures what a request can
measure.

## Did any flag change?

No.

```text
customer_auth_live       false   (unchanged, asserted by a test)
source_monitoring_live   false   (unchanged, asserted by a test)
email_delivery           false   (unchanged, asserted by a test)
object_store_configured  false   (unchanged, asserted by a test)
```

Four tests exist for no other purpose than to assert this gate changed none of
them.

## Did production status change?

No. `production_rollout` and `controlled_customer_pilot` are false in the
summary, in every route, on the page and in every artifact. `NEVER_TRUE_LANES`
names the seven a cockpit may never report true, and an invariant fails if one
is forged.

## Defects found and fixed

Two, both mine, and both the same family this campaign keeps finding — the
fourteenth and fifteenth instances:

```text
The artifact's `page_names_a_tribe` read the page's own SOURCE, comments
included. The page's docstring says "No Tribe name, no grant, no eligibility,
no deadline appears here", so the check reported true for a file whose comment
explains that it does not. Comments are now stripped before the scan.

A test serialised the whole summary and searched for "eligib" and "deadline",
and found them in "eligibility_reported": false and "deadlines_reported":
false - the fields whose entire purpose is to state that the summary reports
neither. It now scans string VALUES, because a field name is the guarantee and
not the leak.
```

Plus one environmental finding: this repo's vitest setup registers no automatic
testing-library cleanup, so a test file that renders more than once leaves every
previous tree in the document. Fixed locally rather than by changing what happens
between every test in sixteen other files.

## What the gate deliberately did not do

```text
grade its own homework    the summary concludes only what LANE_EVIDENCE allows
                          it to; a lane needing outside evidence is
                          readiness_only until something measures it
name a customer           no Tribe, grant, eligibility or deadline anywhere
add a public bypass       the page fetches with credentials; strict-public passes
polish the UX             status cards, blockers and one next action; it is a
                          foundation and says so
```

## Next gate

Gate 145 closes the 136–145 block. What remains, in the order the blockers
unblock:

```text
customer_auth_live             a second real person accepting a real invite
verified_operational_binding   Gate 137's two-part owner decision
terms review                   171 sources unreviewed, 6 needing a human
source_monitoring_live         the terms reviews plus five scheduler components
digest persistence             no nf_tenant_digest_records; delivery intents are
                               persisted and name a digest nobody kept
recipient consent              named in Gate 142, not modelled anywhere
email_delivery                 a provider, a service, an explicit activation
object_store_configured        five settings and an owner decision
controlled_customer_pilot      an owner decision, after the above
```

Every one of those is now visible in one place, which is what this gate was
for.
