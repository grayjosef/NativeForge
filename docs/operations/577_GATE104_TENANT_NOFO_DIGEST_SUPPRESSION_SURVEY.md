# 577 — Gate 104A: digest and suppression survey

Verified again rather than inherited from Gate 103. Two of the three services
this gate most needs to reuse turn out to exist and be substantial.

## Greenfield confirmed

```text
digest services        0
email services         0
notification services  0
watchlist services     0
suppression services   0
```

Gate 103's finding holds. Nothing in the repository sends anything to anybody,
and nothing suppresses an opportunity from anybody's view.

`db/models.py` matches "digest" four times, all in unrelated prose — there is no
digest table.

## What exists and must be reused

### Amendment classification — `opportunity_deadline_and_amendment_model_service`

```text
AMENDMENT_CATEGORIES   deadline_change, eligibility_change,
                       funding_amount_change, attachment_change,
                       contact_change, descriptive_text_change,
                       uncategorized_change
MATERIAL_CATEGORIES    the first four
classify_amendment(modified_fields, revision, previous_revision,
                   last_updated_or_created_only, opportunity_key)
categorize_modified_field(field_name)
```

This is a real model, not a stub. It already distinguishes material changes from
cosmetic ones and already handles the `last_updated_date_or_created_date`
polymorphic field that makes "something changed" ambiguous. Gate 104C bridges
`AMENDMENT_CATEGORIES` and calls `classify_amendment` rather than inventing a
second amendment vocabulary.

### Deadline provenance — `deadline_provenance_service`

```text
PROVENANCE_STATUSES         verified_deadline, unverified_deadline,
                            suspected_placeholder, missing_deadline,
                            unknown_deadline
VERIFIED_STATUSES           verified_deadline only
FRESHNESS_BLOCKING_STATUSES suspected_placeholder, unknown_deadline,
                            missing_deadline
EVIDENCE_LEVELS             none, self_asserted, checked, corroborated
PLACEHOLDER_CLUSTER_MIN     10
```

Gate 87 built this because the corpus had deadline clusters with no fetch
evidence behind them. **Exactly one of five statuses counts as verified**, and
three of them block any freshness claim outright.

This answers doc 570's third flagged tension directly: the digest consumes these
statuses rather than comparing raw dates, so an unverified deadline surfaces as
unverified instead of as a countdown.

### Pursuit state — two vocabularies, neither matching the product requirement

```text
PursuitWorkflowStatus (enum)          active, paused, submitted, closed
pursuit_workspace_contract_service    draft, under_review, needs_information,
  PURSUIT_STATUSES                    deferred, blocked, closed
```

Doc 570 asks for `review · pursue · drafting · submitted · awarded ·
not_pursued · archived`. Neither existing vocabulary is that, and the two are not
each other.

**Gate 104 does not reconcile them.** Suppression needs to know only whether a
pursuit record exists, not which stage it is in, so `tenant_pursuit_suppression_
service` takes a `pursuit_record_id` and stays out of the stage question. Picking
the canonical pipeline vocabulary is Gate 105's or 107's problem and deserves its
own decision rather than being settled as a side effect here.

### Tenant contracts — Gate 103

`tenant_beta_profile_service` (fact statuses, SC priority),
`tenant_beta_feature_entitlement_service` (weekly default, daily opt-in),
`tenant_source_priority_service`, `software_capacity_allowability_review_service`
(with the NativeForge self-assessment cap). All bridged here.

## Answers to the gate's specific questions

**Where should digest records live eventually?** A table that does not exist. The
natural shape is `nf_tenant_digest` + `nf_tenant_digest_item` keyed by
`organization_id`, following `NfTribalProfile`'s pattern. That is a migration
decision and this gate does not make it.

**Is this gate contract-only or persistence-backed?** Contract-only. Nothing is
written to the database, and `customer_persistence_live` stays false — Gate 103
already reported no beta tenant field persists.

**How should multi-snapshot fixture comparison be represented?** Two labelled
snapshots compared explicitly, with `comparison_kind` recording what was
compared. Doc 570's first tension: without live collection there is no second
observation, so a *recorded* pair is the only honest substrate and the contract
has to be able to say that is what it did.

**Which service owns deadline confidence?** `deadline_provenance_service`.

**Which service owns amendment classification?**
`opportunity_deadline_and_amendment_model_service`.

**Which service owns tenant-specific suppression?**
`tenant_pursuit_suppression_service`, new in 104E.

**Can suppression ever delete source/opportunity history?** **No.** It is a view
filter on the "new/unpursued" digest and nothing else. `source_history_preserved`
and `provenance_preserved` are constants on every suppression record and
invariants fail any record where either is false. The opportunity stays visible
in the pursuit pipeline, stays in source history, and stays in provenance.

## What is greenfield

```text
snapshot contract          104B
change detection           104C
item explanation           104D
pursuit suppression        104E
digest builder             104F
digest readiness           104G
digest demo fixtures       104H
```

## Boundaries confirmed unchanged

```text
Phase 1 collectors     not_active (all five)
sources_active         0
sources_monitored      0
live_source_coverage   false
email delivery         no service
customer persistence   not live
```
