# 571 — Gate 103A: tenant beta feature survey

Verified against the repository. Two findings change what this gate should build.

## Service counts by theme

```text
theme          count  notable
tenant             4  seat model, session enforcement - infrastructure, not profile
org_profile        0
eligibility       33  evidence contract, quality, exclusion evidence, fit
                      assessment (blockers, confidence, deadline risk, fixtures)
pursuit            7  pursuit_brief, pursuit_readiness_next_action, m0 kanban
awarded            1  awarded_grant_portfolio_service
deadline           5  deadline_normalization, deadline_provenance
provenance         6  corpus_provenance_attestation, corpus_provenance_evidence
document           4  grant_document_attachment_inventory, documentation readiness
recognition        6  recognition_requirement_derivation, recognition_routing_contract
allowability       1  nativeforge_software_allowability_source_service
digest             0
email              0
notification       0
watchlist          0
alert              1  feedback_slack_alert_service - internal feedback, not tenant
```

## Answers to the gate's specific questions

### Is digest genuinely greenfield? Yes

`digest`, `email`, `notification` and `watchlist` are all zero. The single
`alert` service is `feedback_slack_alert_service`, which posts internal product
feedback — not a tenant alerting path. Nothing in the repository sends anything
to anybody.

### Where should tenant profile live?

Persistence already exists: **`NfTribalProfile`** (`db/models.py:306`) with
`organization_id`, `is_demo`, `legal_name`, `entity_type`, `uei`, `ein`,
`sam_registration_status`, served by `tribal_profile_service.py`
(`create/update/get/export`).

So Gate 103B should **not** create a second tenant table. It builds the
*contract* — the pure-function layer the campaign has used since Gate 92 — over
the fields the beta requires, several of which (`recognition_status`,
`operating_states`, `service_area`, `applicant_classes`, watchlist, digest and
routing preferences) have no column today. The contract names them and marks
them `unknown` until something supplies them; whether they become columns is a
migration decision for a later gate.

`is_demo` on the existing model is a useful precedent: the schema already
distinguishes demo rows from real ones.

### Where should tenant-specific rules live?

`recognition_routing_contract_service` already models routing by recognition
class. Gate 103B carries `routing_rules` and `alert_rules` as tenant fields and
bridges that service's vocabulary rather than inventing a second one.

### Does pursuit suppression already exist? No

Five services match "suppress", and every one is about suppressing a *claim*
without evidence (`eligibility_fit_assessment_no_claim_without_evidence_guard`,
`matching_readiness_no_eligibility_without_review_guard`). None suppresses an
opportunity from a tenant's view. Gate 104 builds it.

### Does the Awarded Grants workspace exist? Service only

`awarded_grant_portfolio_service.py` is substantial and already models what the
requirement asks for:

```text
build_awarded_grant_record   _requirement_has_evidence
build_reporting_calendar     build_risk_summary
build_portfolio              awarded_grant_invariant_failures
```

It already refuses requirements without evidence. **There is no UI.** Gate 105
extends the service; Gate 109 surfaces it.

### Does reporting requirement tracking exist beyond parser contracts? Partly

Gate 91's parser plus `build_reporting_calendar` and `_requirement_has_evidence`
in the portfolio service. What does not exist is the *distinction the
requirement insists on* — projected burden **before** pursuit versus active
obligations **after** award. Gate 105 draws it.

### Can deadline provenance be reused for digest deadline warnings? Yes, and it must

`deadline_provenance_service` and `deadline_normalization_service` exist, and
`opportunity_deadline_and_amendment_model_service` already provides
`build_deadline_model`, `classify_amendment` and `categorize_modified_field`.

That last one matters more than expected: **amendment classification already
exists.** The digest's "changed deadlines" and "amendments" items have a model to
consume rather than invent. What is still missing is the *time series* — two
observations to compare — which doc 570 flagged and which no amount of existing
service supplies without collection.

## Finding that changes 103F: an allowability service already exists

`nativeforge_software_allowability_source_service.py` (Gate 92-era) classifies
**sources** with its own six-label vocabulary:

```text
existing (source-level)      Gate 103F requires (cost-level)
clearly_allowable            clearly_allowable
likely_allowable             likely_allowable
sometimes_allowable          possibly_allowable
unclear                      requires_human_review
unlikely_allowable           likely_not_allowable
unknown                      not_indicated
```

Two labels match, four are renames with a semantic shift. And the two services
answer different questions:

```text
existing   does this funding *source* ever allow software costs?
103F       may this *cost type* be allowable under this *opportunity*?
```

So Gate 103F creates the new service as the brief says, and **bridges** the
existing vocabulary through an explicit mapping rather than forking it or
rewriting the old one — 55 registry rows and Gate 92's tests depend on the
existing classes.

It also has **no NativeForge self-assessment cap.** That rule is new in Gate
103F, and it is the one place this gate adds a restriction rather than a
capability.

## What to reuse, and what is greenfield

```text
reuse                                          greenfield
--------------------------------------------------------------------
NfTribalProfile + tribal_profile_service       tenant beta profile contract
33 eligibility services                        feature entitlement contract
awarded_grant_portfolio_service                tenant source priority contract
deadline_provenance + normalization            demo tenant fixtures
opportunity_deadline_and_amendment_model       allowability *review* (cost-level)
recognition_routing_contract                   tenant beta readiness
nativeforge_software_allowability_source       digest (Gate 104)
Gate 91 awarded-vs-pursuit parser              pursuit suppression (Gate 104)
```

## Doc 091 not found

The brief lists `docs/operations/091_GATE91_AWARDED_VS_PURSUIT_REPORTING_PARSER.md`
"if present". It is not — Gate 91's documentation sits elsewhere in the 400–500
range under the campaign's numbering. The parser service itself was surveyed
directly instead.

## Gate 102 was not host-action only

`tests/test_gate102_backend_unit_lifespan.py` exists with 103 tests, so the
brief's fallback clause does not apply and the full regression chain runs as
listed.

## Boundaries unchanged

```text
Phase 1 collectors     not_active (all five)
live SC collection     0
live federal collection 0
source monitoring live  false
live source coverage    false
```

Nothing in this gate changes any of them.
