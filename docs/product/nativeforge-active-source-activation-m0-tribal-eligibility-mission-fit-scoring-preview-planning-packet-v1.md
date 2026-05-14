# NativeForge active source activation M0 tribal eligibility and mission fit scoring preview planning packet (v1)

## Sprint 120 purpose

Sprint 120 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_m0_tribal_eligibility_mission_fit_scoring_preview_planning_packet_v1`** artifacts. Each packet is the M0 planning layer for **demo-safe tribal eligibility tagging previews** and **mission fit scoring previews** using **seeded profile and opportunity data only**.

Sprint 120 creates an **operator-facing planning packet** only. It defines seventeen scoring factor groups, factor-level acceptance criteria, demo-safe scoring rules, recommendation preview tiers (each explicitly **not a final eligibility determination**), human review gates, sovereignty and trust requirements, scoring-to-feature mapping, risks, mitigations, and M0 exit criteria. It does **not** perform real eligibility scoring, final eligibility determinations, live Grants.gov ingestion, Grants.gov API calls, SAM.gov integration, agency scraping, real NOFO parsing, LLM scoring, database migrations, frontend UI, runtime scoring engines, or production recommendation engines. It remains **preview-only** and **non-runtime** unless a future sprint explicitly authorizes implementation work.

Sprint 118 organizational entity profile planning and Sprint 119 seeded opportunity planning remain upstream. Sprint 120 defines **how demo-safe records are compared** for previews without live adjudication.

## Inputs

None. The builder emits a fixed packet from in-repo constants.

## Outputs

The packet includes:

- **`sprint_number`**: `120`
- **`packet_name`**: `NativeForge M0 Tribal Eligibility Tagging and Mission Fit Scoring Preview Planning Packet`
- **`packet_version`**: `v1`
- **`artifact_type`**: `nf_active_source_activation_m0_tribal_eligibility_mission_fit_scoring_preview_planning_packet_v1`
- **`artifact_version`**: integer schema version `1`
- **`version`**: semantic packet version string `v1`
- **`generated_at`**: deterministic timestamp constant for reproducible artifacts
- **Guard booleans**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`** all `true`
- **Planning allowances**: **`may_generate_operator_packet`**, **`may_define_scoring_preview_scope`**, **`may_define_demo_safe_scoring_factors`**, **`may_define_acceptance_criteria`**, **`may_define_guardrails`** all `true`
- **Zero actuals**: **`actual_external_calls`**, **`actual_source_ingestions`**, **`actual_api_calls`**, **`actual_scrapes`**, **`actual_ai_generations`**, **`actual_form_submissions`**, **`actual_customer_data_access`**, **`actual_runtime_writes`**, **`actual_eligibility_adjudications`**, **`actual_submission_recommendations`** all `0`
- **`m0_scoring_preview_foundations`**: ten statements from tribal eligibility tagging through human review
- **`scoring_factor_groups`**: seventeen structured rows with priorities, names, purposes, and at least two acceptance criteria each
- **`scoring_preview_to_m0_feature_mapping`**: rows mapping factor usage to M0 preview features (including SF-424 preview readiness and source provenance display)
- **`recommendation_preview_tiers`**: six demo-safe tiers, each stating the tier is **not a final eligibility determination**
- **`human_review_gates`**, **`sovereignty_and_trust_requirements`**, **`sprint_120_does_not_build`**, **`m0_scoring_preview_planning_exit_criteria`**: operator-ready lists
- **`risks_and_mitigations`**: at least eight documented risks with mitigations
- **`sprint_120_m0_scoring_preview_planning_packet_proof`**: statelessness and preview-only assertions for CI and audits

`render_active_source_activation_m0_tribal_eligibility_mission_fit_scoring_preview_planning_packet_markdown` returns markdown titled **NativeForge M0 Tribal Eligibility Tagging and Mission Fit Scoring Preview Planning Packet v1** with fourteen numbered sections covering purpose, sequencing after seeded opportunity planning, objectives, demo-safe scoring rules, factor groups, acceptance criteria, feature mapping, recommendation preview tiers, human review gates, sovereignty requirements, explicit exclusions (including **no real eligibility scoring**, **no final eligibility determination**, and **no database migration**), exit criteria, risks, and **Sprint 121** guidance for the **M0 NOFO Plain-Language Summary Preview Planning Packet**.

## Design rules

- **Deterministic**: repeated calls return identical dicts and markdown for the same inputs (there are no inputs).
- **Preview-only**: the artifact may define scoring preview scope, factors, and criteria; it must not trigger execution, activation, live adjudication, external API calls, scrapes, or LLM scoring.
- **Demo-safe posture**: all M0 scoring preview narratives assume seeded or demo-safe profile and opportunity data only until a future sprint explicitly authorizes runtime engineering.

## Relationship to Sprint 118 and Sprint 119

Sprint 118 defines entity profile context; Sprint 119 defines seeded opportunity records. Sprint 120 does not replace that work; it supplies the **scoring preview planning depth** that compares those demo-safe artifacts without opening live Grants.gov, SAM.gov, production data, or runtime scoring paths.
