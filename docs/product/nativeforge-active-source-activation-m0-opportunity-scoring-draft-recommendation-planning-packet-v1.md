# NativeForge active source activation M0 opportunity scoring and draft recommendation planning packet (v1)

## Sprint 122 purpose

Sprint 122 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_m0_opportunity_scoring_draft_recommendation_planning_packet_v1`** artifacts. Each packet is the M0 planning layer for **demo-safe opportunity scoring rollup** and **draft pursuit recommendation previews** built from seeded opportunity data, entity profile context, tribal eligibility preview, mission fit preview, and NOFO summary preview—without runtime scoring, production recommendations, live eligibility adjudication, or AI drafting.

Sprint 122 creates an **operator-facing planning packet** only. It defines recommendation preview foundations, eighteen recommendation factor groups, factor-level acceptance criteria, demo-safe recommendation rules, recommendation preview tiers (each explicitly not a final pursuit decision and not a final eligibility determination), draft recommendation narrative constraints, human review gates, sovereignty and trust requirements, recommendation preview to M0 feature mapping, risks, mitigations, M0 exit criteria for recommendation planning, and **Sprint 123** guidance. It does **not** score real opportunities, call Grants.gov or SAM.gov, scrape agencies, parse real NOFOs, invoke LLMs, perform database migrations, ship frontend UI, or implement a runtime recommendation engine.

Sprints **118** through **121** defined organizational entity profile context, seeded Grants.gov-style opportunity interfaces, tribal eligibility and mission fit scoring preview, and NOFO plain-language summary preview. Sprint 122 defines **how those layers roll up** into a **pursuit recommendation preview** narrative scope for demos.

## Inputs

None. The builder emits a fixed packet from in-repo constants.

## Outputs

The packet includes:

- **`sprint_number`**: `122`
- **`packet_name`**: `NativeForge M0 Opportunity Scoring and Draft Recommendation Planning Packet`
- **`packet_version`**: `v1`
- **`artifact_type`**: `nf_active_source_activation_m0_opportunity_scoring_draft_recommendation_planning_packet_v1`
- **`artifact_version`**: integer schema version `1`
- **`version`**: semantic packet version string `v1`
- **`generated_at`**: deterministic timestamp constant for reproducible artifacts
- **Guard booleans**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`** all `true`
- **Planning allowances**: **`may_generate_operator_packet`**, **`may_define_recommendation_preview_scope`**, **`may_define_demo_safe_recommendation_factors`**, **`may_define_acceptance_criteria`**, **`may_define_guardrails`** all `true`
- **Zero actuals**: **`actual_external_calls`**, **`actual_source_ingestions`**, **`actual_api_calls`**, **`actual_scrapes`**, **`actual_ai_generations`**, **`actual_form_submissions`**, **`actual_customer_data_access`**, **`actual_runtime_writes`**, **`actual_eligibility_adjudications`**, **`actual_submission_recommendations`**, **`actual_draft_generations`** all `0`
- **`m0_recommendation_preview_foundations`**: ten statements from pursuit recommendation preview through future pursuit pipeline handoff readiness
- **`recommendation_factor_groups`**: eighteen structured rows with priorities, names, purposes, and at least two acceptance criteria each
- **`recommendation_preview_to_m0_feature_mapping`**: rows mapping factor usage to M0 surfaces (pursuit preview, pipeline kanban, deadline calendar, SF-424 readiness, checklist, human review, provenance, sovereignty explainer)
- **`recommendation_preview_tiers`**: six demo-safe tiers, each stating they are not a final pursuit decision and not a final eligibility determination
- **`draft_recommendation_narrative_constraints`**, **`human_review_gates`**, **`sovereignty_and_trust_requirements`**, **`sprint_122_does_not_build`**, **`m0_recommendation_planning_exit_criteria`**: operator-ready lists
- **`risks_and_mitigations`**: at least eight documented risks with mitigations
- **`sprint_122_m0_opportunity_scoring_draft_recommendation_planning_packet_proof`**: statelessness and preview-only assertions for CI and audits

`render_active_source_activation_m0_opportunity_scoring_draft_recommendation_planning_packet_markdown` returns markdown titled **NativeForge M0 Opportunity Scoring and Draft Recommendation Planning Packet v1** with fifteen numbered sections.

## Design rules

- **Deterministic**: repeated calls return identical dicts and markdown for the same inputs (there are no inputs).
- **Preview-only**: the artifact may define recommendation preview scope, demo-safe factors, guardrails, and criteria; it must not trigger execution, activation, live ingestion, external API calls, scrapes, LLM generation, or draft output for production use.
- **Demo-safe posture**: all M0 recommendation previews assume seeded or demo-safe profile, opportunity, eligibility, mission fit, and NOFO summary text only until a future sprint explicitly authorizes runtime engineering.

## Relationship to Sprint 121

Sprint 121 defined NOFO plain-language summary preview planning. Sprint 122 does not replace that work; it supplies the **recommendation rollup and draft pursuit preview planning depth** that sits on top of summary, eligibility, and mission fit previews without opening live scoring or recommendation engines.
