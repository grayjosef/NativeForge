# 508 — Reporting requirements and grant lifecycle obligation lane

**Status: queued requirement. Nothing in this document is built.**

Captured during Gate 90 and deliberately not implemented there. Gate 90 imported
a source registry; this lane is a different problem and deserves its own gates.

## The question this lane answers

> If we apply for this grant and win, what exactly are we signing up for?

Everything the campaign has built so far answers *can we apply* — eligibility,
exclusion evidence, recognition tier, funding lane. None of it answers *can we
comply after award*, which is the question that decides whether pursuing is
sensible.

A tribal grants office with two staff can be perfectly eligible for a programme
whose quarterly performance reporting, participant tracking and single-audit
threshold would consume more capacity than the award provides. Telling them they
are eligible and stopping there is not neutral — it is the useful half of an
answer presented as the whole.

## The rule this lane inherits

Same as every gate since 85: **no obligation without evidence.**

```text
- no obligation without a source quote
- no inferred due date without source text
- no generic federal requirement treated as opportunity-specific unless the
  source applies it to this opportunity
- preserve source quotes and spans
- preserve UNKNOWN
- ambiguous obligations are HUMAN_REVIEW_REQUIRED, not guesses
- application requirements are distinct from post-award requirements
- recipient duties are distinct from subrecipient duties
- required reports are distinct from optional guidance
```

The third is the one most likely to be got wrong. "Federal grants generally
require SF-425 quarterly" is true as background and is *not* a finding about a
specific NOFO. A burden profile assembled from federal-grant folklore would look
authoritative and be unfalsifiable — which is the failure mode Gates 87 and 88
kept finding in a different guise.

## Extraction categories

Five groups, each carrying `evidence_quote`, `evidence_location`, `confidence`
and `human_review_required`:

```text
reporting_requirements   report_name, report_type, report_frequency,
                         first_due_date, recurring_due_dates, final_report_due,
                         reporting_portal, submission_method, required_forms,
                         required_metrics, required_narrative_sections,
                         required_financial_sections,
                         required_backup_documentation

financial_requirements   budget_categories, match_required, match_percentage,
                         allowable_cost_notes, unallowable_cost_notes,
                         drawdown_method, reimbursement_or_advance,
                         financial_report_forms,
                         audit_threshold_or_audit_reference,
                         indirect_cost_language, procurement_language

performance_requirements performance_measures, required_outputs,
                         required_outcomes, evaluation_required,
                         data_collection_required,
                         demographic_reporting_required,
                         geospatial_reporting_required,
                         participant_tracking_required,
                         service_delivery_tracking_required

compliance_requirements  certifications, assurances, civil_rights_requirements,
                         environmental_review, tribal_resolution_required,
                         data_security_requirements, privacy_requirements,
                         subrecipient_monitoring, procurement_standards,
                         record_retention, closeout_requirements

lifecycle_burden         estimated_admin_complexity,
                         estimated_reporting_complexity,
                         estimated_data_system_need, estimated_staffing_need,
                         customer_capacity_risk,
                         nativeforge_support_opportunity, blocked_reasons
```

`tribal_resolution_required` deserves particular care: it is a real and frequent
requirement, it takes weeks to obtain, and missing it turns a pursuable
opportunity into an unmeetable deadline.

## Services to build

```text
src/nativeforge/services/grant_reporting_requirement_extraction_service.py
    extract post-award obligations from opportunity source text

src/nativeforge/services/grant_lifecycle_obligation_service.py
    turn extracted requirements into a customer-facing obligation profile
```

The second emits `grant_lifecycle_profile`: opportunity id, title, agency,
program, lifecycle status, application deadline, expected award period,
reporting calendar, compliance checklist, financial/performance/closeout
profiles, staffing burden, system burden, risk summary, customer action items,
human review items.

## Customer-facing outputs

Seven, of which the campaign has built parts of three:

```text
1. Pursuit Fit           should we pursue?              not built
2. Eligibility Fit       can we apply?                  partially built (Gates 79-83)
3. Funding Fit           can this pay for the work?     partially built (Gate 90E)
4. Reporting Burden Fit  can we comply after award?     NOT BUILT
5. Lifecycle Calendar    what deadlines follow award?   NOT BUILT
6. Evidence Packet       what text supports each?       partially built (Gate 81/82)
7. Human Review Queue    what needs a grants office?    NOT BUILT
```

## New scoring dimension: `reporting_burden_fit`

```text
manageable | manageable_with_support | high_burden |
requires_dedicated_staff | requires_new_systems | unclear |
human_review_required
```

Rules, and they matter:

- **High burden does not mean ineligible.** It is a pursuit signal, not an
  eligibility verdict, and must not be wired into the exclusion model.
- **Unclear burden does not mean no-go.** It means human review before the
  pursuit decision.
- System burden feeds NativeForge support recommendations — which is a
  commercial interest, and therefore needs the same separation Gate 90E
  enforces between "worth looking at" and "this can be bought".

That last point is worth stating plainly: this lane will surface places where
NativeForge is the answer. A burden profile that overstates burden sells more
software. The evidence rules above are what keep that honest, and any scoring
that rewards higher burden estimates should be treated as a defect.

## Customer UI lane: "What You Are Signing Up For"

Sections: reports you must submit; how often; systems or portals you must use;
data you must collect; financial documentation you must maintain; staff time
likely required; compliance risks; closeout obligations; where NativeForge can
help; what still needs human, legal or grants-office review.

**Visible before the pursuit decision**, not after.

## What Gate 90 did for this lane

One thing, and only because it was already true: the registry preserves every
source field the extraction lane will need.

```text
data_format                monitoring_method        source_type
program_examples           notes                    software_cost_allowability
eligibility_classes        agency_or_org            subagency
url                        robots_or_terms_risk
```

All 11 survive the import, the JSON artifact and the seed CSV.
`test_reporting_lane_fields_survive_import` and
`test_reporting_lane_fields_survive_the_artifacts` pin each one, and
`test_reporting_lane_fields_carry_real_content` checks they are populated rather
than merely present — `notes` and `subagency` are legitimately sparse, the other
nine are on all 55 rows.

Nothing else about this lane exists.

## Recommended sequence

```text
Gate 90  external source registry intake                 DONE
Gate 91  reporting requirements extraction contract
         + awarded-vs-pursuit lane contract (doc 509)
Gate 92  award_transition_service: Mark as Awarded + undo (doc 509)
Gate 93  customer-facing "What You Are Signing Up For" profile
Gate 94  pursuit scoring integration with reporting_burden_fit
Gate 95  lifecycle calendar / compliance checklist workspace
```

## Where the projected burden becomes real

A burden profile is a projection until a customer wins the award. Doc 509
governs that transition - the explicit "Mark as Awarded" action, its undo, and
the rule that a projected burden only becomes active obligation tracking once
award details are entered.

The two documents meet there: 508 extracts what a NOFO would impose, 509
governs when a customer takes it on. Conflating them would show a customer an
estimated reporting date as though it were a real federal deadline.

## A sequencing caution worth recording

Gates 91–92 need NOFO text to extract from, and the corpus has very little.
Gate 88 established that 18 of 185 records have an independent recording behind
them, and Gate 85 found 108 of 185 carry any eligibility text at all — most of
it a single templated line rather than a full notice.

The Gate 81/82 notice-extraction machinery works, and it has been exercised
against **synthetic fixtures and one real recorded transport**. An extraction
contract can be built and tested on those. A *useful* burden profile for a real
customer needs real notices, which needs monitoring, which needs terms clearance.

So Gate 91 is buildable now and Gate 93 is not, and the gap between them is the
same legal review that gates everything else. Building 91–92 against synthetic
fixtures is worthwhile — it is how Gates 81 and 82 were built — provided the
resulting coverage claims stay as honest as those did.
