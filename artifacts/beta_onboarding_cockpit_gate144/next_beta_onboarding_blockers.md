# Gate 144 — what the beta onboarding cockpit does not yet reach

## Where this stands

```text
cockpit foundation route-live   TRUE
frontend surface exists         TRUE
lanes reported                  17
scope                           controlled_dev_demo
```

An operator can now see, in one place, what this deployment can do — and, more
importantly, what it cannot and why.

## What works today

```text
  awarded_grants
  customer_persistence
  document_metadata
  email_delivery_readiness
  login
  source_monitoring_preflight
  tenant_digest
```

Every one is `controlled_dev_demo`. None is a production claim.

## What needs a person

```text
  consent_and_data_boundary        ['consent_boundary_not_documented', 'customer_auth_live_false', 'real_customer_organization_missing', 'verified_operational_binding_false']
  customer_auth                    ['invite_binding_passed']
  customer_beta_scope              ['customer_beta_scope_not_approved', 'real_customer_organization_missing']
  verified_operational_binding     ['demo_organization_is_never_a_verified_operational_binding', 'no_authorized_real_organization', 'owner_decision_absent', 'production_verified_binding_requires_live_customer_auth', 'real_organization_refused_by_name']
```

No code change moves either of these. That is why they are
`requires_human_approval` rather than `blocked`: an operator reading "blocked"
looks for a bug, and there is none.

## What is not configured

```text
  document_body_storage            ['no_body_route_proof_was_supplied', 'no_metadata_route_smoke_was_supplied']
  email_delivery                   ['email_settings_absent:nf_email_api_endpoint,nf_email_api_key,nf_email_provider,nf_email_sender_address,nf_email_sender_domain', 'no_email_provider_configured', 'send_activation_absent']
  object_storage                   ['no_owner_decision', 'object_storage_settings_absent']
```

## What is deliberately false

```text
controlled_customer_pilot   not approved
production_rollout          not approved, and no lane above is a production claim
source_monitoring           171 terms reviews and five scheduler components
```

## The route reports fewer operational lanes than the verifier, on purpose

```text
the route      measures what a request can measure
the verifier   runs each lane's own verifier first, then reports
```

A cockpit route that assumed the wider set would be reporting a proof it did not
have. `LANE_EVIDENCE` records, per lane, what the summary is allowed to conclude
unaided — and a lane needing outside evidence is `readiness_only`, never
`operational`, until something measures it.

That is the defect this gate was most likely to introduce, and it is the one the
design is shaped around.

## The frontend surface

```text
surface name             beta_onboarding_cockpit
in the union             true
dispatched in App        true
existing surfaces intact true
sc_customer_demo intact  true
names a Tribe            false
claims production        false
shows false lanes        true
shows blockers           true
```

It is a foundation, not finished UX: status cards, blockers and one next action.
What it does have is the property that matters — every false lane is shown as
false, with its reason. A dashboard that showed only the green lanes would be
the most dangerous artifact this campaign could produce.

## Nothing was activated

```text
live source calls      0
emails sent            0
object store calls     0
collectors activated   0
real org touched       false
customer data written  false
```

## Still false, and not touched

```text
customer_auth_live             false
verified_operational_binding   false
source_monitoring_live         false
email_delivery                 false
object_store_configured        false
document_body_storage_ready    false
controlled_customer_pilot      false
production_rollout             false
```
