# NativeForge active source activation M0 requirement extraction checklist preview planning packet (v1)

## Sprint 125 purpose

Sprint 125 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_m0_requirement_extraction_checklist_preview_planning_packet_v1`** artifacts. Each packet is the M0 planning layer for **demo-safe requirement checklist previews** sourced from **seeded NOFO summary content** and **seeded opportunity records**—without real NOFO parsing, LLM extraction, Grants.gov API calls, SAM.gov integration, agency scraping, runtime checklist engines, production task creation, or real user assignment.

Sprint 125 creates an **operator-facing planning packet** only. It defines checklist preview foundations, eighteen checklist field groups with field-level acceptance criteria, ten demo-safe requirement categories, demo-safe requirement rules, missing-data and confidence rules, human review gates, sovereignty and trust requirements, checklist preview to M0 feature mapping, risks, mitigations, M0 exit criteria for checklist planning, and **Sprint 126** guidance. It does **not** add database migrations, frontend UI, external validation, or access to production customer data.

Sprint **124** defined SF-424 autofill preview readiness. Sprint 125 defines **how opportunity requirements can become a visible checklist preview** in demo-safe conditions without parsing real NOFOs or creating production tasks.

## Inputs

None. The builder emits a fixed packet from in-repo constants.

## Outputs

The packet includes:

- **`sprint_number`**: `125`
- **`packet_name`**: `NativeForge M0 Requirement Extraction Checklist Preview Planning Packet`
- **`packet_version`**: `v1`
- **`artifact_type`**: `nf_active_source_activation_m0_requirement_extraction_checklist_preview_planning_packet_v1`
- **`artifact_version`**: integer schema version `1`
- **`version`**: semantic packet version string `v1`
- **`generated_at`**: deterministic timestamp constant for reproducible artifacts
- **Guard booleans**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`** all `true`
- **Planning allowances**: **`may_generate_operator_packet`**, **`may_define_requirement_checklist_scope`**, **`may_define_demo_safe_requirement_fields`**, **`may_define_acceptance_criteria`**, **`may_define_guardrails`** all `true`
- **Zero actuals**: **`actual_external_calls`**, **`actual_source_ingestions`**, **`actual_api_calls`**, **`actual_scrapes`**, **`actual_ai_generations`**, **`actual_form_submissions`**, **`actual_customer_data_access`**, **`actual_runtime_writes`**, **`actual_requirement_extractions`**, **`actual_checklist_creations`**, **`actual_task_creations`** all `0`
- **`m0_requirement_checklist_preview_foundations`**: ten statements from NOFO checklist preview through future runtime checklist readiness
- **`checklist_field_groups`**: eighteen structured rows with priorities, names, purposes, and at least two acceptance criteria each
- **`requirement_categories`**: ten demo-safe category definitions
- **`checklist_preview_to_m0_feature_mapping`**: rows mapping checklist usage to NOFO summary preview, SF-424 preview readiness, pursuit pipeline card, deadline calendar preview, attachment readiness preview, human review workflow, source provenance display, sovereignty trust explainer, and future export readiness
- **`missing_data_and_confidence_rules`**, **`human_review_gates`**, **`sovereignty_and_trust_requirements`**, **`sprint_125_does_not_build`**, **`m0_checklist_preview_planning_exit_criteria`**: operator-ready lists
- **`risks_and_mitigations`**: at least eight documented risks with mitigations
- **`sprint_125_m0_requirement_checklist_preview_planning_packet_proof`**: statelessness and preview-only assertions for CI and audits

`render_active_source_activation_m0_requirement_extraction_checklist_preview_planning_packet_markdown` returns markdown titled **NativeForge M0 Requirement Extraction Checklist Preview Planning Packet v1** with fifteen numbered sections.

## Design rules

- **Deterministic**: repeated calls return identical dicts and markdown for the same inputs (there are no inputs).
- **Preview-only**: the artifact may define checklist scope, demo-safe requirement fields, guardrails, and criteria; it must not trigger execution, activation, live ingestion, external API calls, scrapes, LLM generation, real NOFO parsing, runtime checklist creation, production tasks, or real user assignment.
- **Demo-safe posture**: all M0 checklist previews assume seeded NOFO summary content and seeded opportunity records only until a future sprint explicitly authorizes runtime engineering.

## Relationship to Sprint 124

Sprint 124 defined SF-424 autofill preview planning. Sprint 125 does not replace that work; it supplies **requirement checklist preview planning depth** that shows opportunity obligations in demo-safe conditions without opening real NOFO parsing, LLM extraction, or production task paths.
