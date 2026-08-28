# 573 — Gate 103C: tenant feature entitlement contract

`src/nativeforge/services/tenant_beta_feature_entitlement_service.py`

Which of the eleven beta features are switched on for a tenant, and what that
does and does not mean.

## Four different facts, routinely collapsed into one

```text
entitled     this tenant is allowed to use the feature
configured   the tenant has supplied what the feature needs
implemented  the feature exists and works
live         the feature is doing something in the world
```

A flag in a settings table is only the first. Turning on `weekly_nofo_digest`
does not make a digest arrive; turning on `sc_federal_source_watchlist` does not
check a source; turning on `awarded_grants_workspace` does not verify a single
extracted requirement.

Every result carries the downstream facts beside the flags:

```text
digest_email_delivery_live        false
source_monitoring_live            false
extracted_requirements_verified   false
live_source_coverage              false
features_implemented_by_enabling  false
```

`MISREADABLE_FEATURES` maps each easily-confused feature to the fact it is
confused with, and an invariant fails any result where an enabled feature sits
beside a true downstream claim.

## The eleven features

```text
tenant_eligibility_profile             sc_federal_source_watchlist
weekly_nofo_digest                     optional_daily_alerts
pursuit_suppression                    tenant_pursuit_pipeline
reporting_burden_preview               awarded_grants_workspace
tenant_document_library                tenant_rules_routing_alerts
software_capacity_allowability_review
```

Ten are enabled by default. `optional_daily_alerts` is not: the product
requirement makes weekly the default and daily an opt-in for grants/admin users,
and the default set reflects that rather than leaving it to configuration.

## Implementation is detected, not declared

`FEATURE_IMPLEMENTATION` names the services behind each feature and
`detect_feature_implementation` imports them. Two features have no services at
all today:

```text
weekly_nofo_digest    not implemented - Gate 104
pursuit_suppression   not implemented - Gate 104
```

They are entitled and unimplemented, and the result says both. A flag claiming
otherwise would be more comfortable and less useful.

## Configuration gaps name what is missing

A feature needing tenant facts the profile does not carry is reported as
`configuration_required` with the missing fields listed, rather than
enabled-and-broken:

```text
sc_federal_source_watchlist   needs operating_states
tenant_eligibility_profile    needs recognition_status, applicant_classes
optional_daily_alerts         needs daily_alerts_audience
tenant_rules_routing_alerts   needs routing_rules
tenant_document_library       needs document_library_requirements
```

A demo-fixture value counts as supplied — it configures a demo. The profile's own
`profile_fact_status` carries the caveat, and `human_review_required` is set when
that status is `unknown`, `needs_human_review` or `demo_fixture`.

## An unrecognised feature name is reported

Not silently dropped, and not silently honoured. It appears in
`unrecognised_features` and in `blocked_reasons`.
