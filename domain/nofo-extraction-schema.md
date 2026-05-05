# NOFO Extraction Schema

Distilled from source report Section 7. Every ingested NOFO becomes a structured object via LLM extraction. Confidence scoring on every field. Low-confidence fields flagged for human review.

## Top-level structure

```
{
  "metadata": { ... },
  "eligibility": { ... },
  "funding": { ... },
  "timeline": { ... },
  "requirements_forms": [ ... ],
  "requirements_attachments": [ ... ],
  "requirements_narrative": [ ... ],
  "evaluation": { ... },
  "compliance_reporting": { ... },
  "risk_flags": [ ... ],
  "ai_summary": { ... },
  "human_review_required": [ ... ]
}
```

Every field has a sibling `_confidence` (0.0–1.0). The confidence threshold for "human review required" defaults to 0.75 and is per-field configurable.

## Metadata

- opportunity_title
- opportunity_number
- cfda_assistance_listing
- issuing_agency
- sub_agency
- program_contact (name, email, phone)
- federal_register_citation
- opportunity_url
- attachment_urls (list)

## Eligibility

- eligible_entity_types (structured list mapped to entity_type values)
- federally_recognized_tribe_required (Y/N)
- alaska_native_eligible (Y/N)
- native_hawaiian_org_eligible (Y/N)
- tribal_nonprofit_eligible (Y/N)
- population_threshold (numeric, if any)
- self_governance_requirement (Y/N)
- sam_registration_required (Y/N)
- disqualifying_conditions (free-text list)

## Funding

- award_ceiling
- award_floor
- total_program_funding
- expected_awards (count)
- award_type (grant | cooperative_agreement | formula | competitive)
- match_required (Y/N)
- match_percent
- match_type (cash | in_kind | both)
- match_waiver_available (Y/N)
- indirect_cost_allowable (Y/N)
- indirect_cost_limitations (free-text)

## Timeline

- loi_deadline (datetime + tz, if applicable)
- application_deadline (datetime + tz, required)
- performance_period_start
- performance_period_end
- webinar_dates (list)
- qa_submission_deadline
- amendment_dates (list)

## Requirements — forms

List of objects, each:

- form_name (e.g., "SF-424", "SF-424A", "Tribal Resolution")
- required (Y/N)
- notes

## Requirements — attachments

List of objects, each:

- attachment_name
- description
- required (Y/N)
- format (PDF / DOCX / etc.)
- page_limit
- notes

## Requirements — narrative

List of objects, each:

- section_title (e.g., "Project Narrative", "Needs Statement")
- description (instructions verbatim)
- page_limit
- character_or_word_limit
- formatting (font, spacing, margin)
- evaluation_weight (if specified)

## Evaluation

- criteria_text (verbatim)
- criteria_structured (list of {criterion, weight, max_points})
- priority_points (list of {priority, points})
- competitive_preference_priorities (list)

## Compliance and reporting

- post_award_reporting_frequency
- post_award_reporting_types (financial / performance / both)
- financial_reporting_schedule
- performance_reporting_schedule
- special_conditions (list)
- audit_implications
- closeout_requirements

## Risk flags (AI-generated)

The extraction LLM emits flags when it sees:

- Short application window (< 30 days)
- Tight match requirement with no waiver
- No tribal priority points (competitive disadvantage)
- High reporting burden (quarterly or more)
- Eligibility ambiguity requiring human confirmation
- NEPA environmental review required
- Section 106 historic preservation review required

## AI summary

- plain_language_summary (2–3 sentences)
- key_requirements_summary (bullet list)
- top_3_competitive_differentiators
- suggested_pursuit_rationale
- suggested_do_not_pursue_rationale

## Human review required

Auto-populated list of any field with `_confidence < threshold`. Surfaced in the UI as flagged review items.

## Implementation notes for M0

- Extraction runs once during seed-data preparation. Each demo Spark's extraction is hand-verified before sealing the seed. Any field that fails human verification is corrected manually in the seed file, not by re-running the LLM.
- The `extracted` JSONB column on `nf_grant_sparks` stores the full structured object.
- Each `nf_spark_requirements` row is a denormalized projection of one item from `requirements_forms`, `requirements_attachments`, or `requirements_narrative`.
- The extraction pipeline run is recorded in `ai_runs` (input: NOFO text, output: JSON, model name, timestamp, user_id, cost). This is the audit trail for "what AI saw and produced."

## What M0 does NOT do

- Live extraction on user-uploaded NOFOs. M1.
- Amendment/version comparison. M1.
- Cross-NOFO pattern detection (e.g., "this agency typically scores X heavily"). M2.
- Confidence calibration based on past human corrections. M2.
