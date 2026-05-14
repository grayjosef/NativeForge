# NativeForge active source activation M0 SF-424 autofill preview planning packet (v1)

## Sprint 124 purpose

Sprint 124 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_m0_sf424_autofill_preview_planning_packet_v1`** artifacts. Each packet is the M0 planning layer for **demo-safe SF-424 autofill previews** sourced from **seeded organizational entity profiles** and **seeded opportunity data**—without real SF-424 generation, form submission, Grants.gov Workspace integration, Grants.gov API calls, SAM.gov integration, runtime autofill engines, or production form package changes.

Sprint 124 creates an **operator-facing planning packet** only. It defines SF-424 preview foundations, eighteen SF-424 field groups with field-level acceptance criteria, demo-safe autofill rules, missing-data and validation preview rules, human review gates, sovereignty and trust requirements, SF-424 preview to M0 feature mapping, risks, mitigations, M0 exit criteria for SF-424 preview planning, and **Sprint 125** guidance. It does **not** add database migrations, frontend UI, external validation, real customer data access, or Grants.gov Workspace connectivity.

Sprint **123** defined pursuit pipeline and deadline tracking previews. Sprint 124 defines **how a pursued opportunity can show SF-424 form readiness** through planning-scope autofill previews without producing or submitting a real form.

## Inputs

None. The builder emits a fixed packet from in-repo constants.

## Outputs

The packet includes:

- **`sprint_number`**: `124`
- **`packet_name`**: `NativeForge M0 SF-424 Autofill Preview Planning Packet`
- **`packet_version`**: `v1`
- **`artifact_type`**: `nf_active_source_activation_m0_sf424_autofill_preview_planning_packet_v1`
- **`artifact_version`**: integer schema version `1`
- **`version`**: semantic packet version string `v1`
- **`generated_at`**: deterministic timestamp constant for reproducible artifacts
- **Guard booleans**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`** all `true`
- **Planning allowances**: **`may_generate_operator_packet`**, **`may_define_sf424_preview_scope`**, **`may_define_demo_safe_autofill_fields`**, **`may_define_acceptance_criteria`**, **`may_define_guardrails`** all `true`
- **Zero actuals**: **`actual_external_calls`**, **`actual_source_ingestions`**, **`actual_api_calls`**, **`actual_scrapes`**, **`actual_ai_generations`**, **`actual_form_submissions`**, **`actual_customer_data_access`**, **`actual_runtime_writes`**, **`actual_form_generations`**, **`actual_autofill_writes`**, **`actual_grants_workspace_calls`** all `0`
- **`m0_sf424_preview_foundations`**: ten statements from entity profile mapping through future form package readiness
- **`sf424_field_groups`**: eighteen structured rows with priorities, names, purposes, and at least two acceptance criteria each
- **`sf424_preview_to_m0_feature_mapping`**: rows mapping preview usage to organizational entity profile, seeded opportunity, pursuit pipeline card, requirement checklist preview, human review workflow, source provenance display, sovereignty trust explainer, and future export readiness
- **`missing_data_and_validation_preview_rules`**, **`human_review_gates`**, **`sovereignty_and_trust_requirements`**, **`sprint_124_does_not_build`**, **`m0_sf424_preview_planning_exit_criteria`**: operator-ready lists
- **`risks_and_mitigations`**: at least eight documented risks with mitigations
- **`sprint_124_m0_sf424_autofill_preview_planning_packet_proof`**: statelessness and preview-only assertions for CI and audits

`render_active_source_activation_m0_sf424_autofill_preview_planning_packet_markdown` returns markdown titled **NativeForge M0 SF-424 Autofill Preview Planning Packet v1** with fourteen numbered sections.

## Design rules

- **Deterministic**: repeated calls return identical dicts and markdown for the same inputs (there are no inputs).
- **Preview-only**: the artifact may define SF-424 preview scope, demo-safe autofill fields, guardrails, and criteria; it must not trigger execution, activation, live ingestion, external API calls, scrapes, LLM generation, form submission, Grants.gov Workspace calls, form generation, or autofill writes.
- **Demo-safe posture**: all M0 SF-424 autofill previews assume seeded or demo-safe entity profiles and opportunity records only until a future sprint explicitly authorizes runtime engineering.

## Relationship to Sprint 123

Sprint 123 defined pursuit pipeline kanban and deadline tracking preview planning. Sprint 124 does not replace that work; it supplies **SF-424 autofill preview planning depth** that shows form readiness in demo-safe conditions without opening real form generation or submission paths.
