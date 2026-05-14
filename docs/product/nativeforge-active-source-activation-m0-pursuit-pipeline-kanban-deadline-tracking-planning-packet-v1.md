# NativeForge active source activation M0 pursuit pipeline kanban and deadline tracking planning packet (v1)

## Sprint 123 purpose

Sprint 123 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_m0_pursuit_pipeline_kanban_deadline_tracking_planning_packet_v1`** artifacts. Each packet is the M0 planning layer for **demo-safe pursuit pipeline card previews** and **deadline tracking previews** that follow a reviewed opportunity recommendation—without runtime kanban, production tasks, calendar writes, notifications, form submission, or external calls.

Sprint 123 creates an **operator-facing planning packet** only. It defines pipeline preview foundations, eighteen pipeline field groups, eight demo-safe pipeline statuses (each stating that M0 does not submit applications, does not automate outreach, and does not create production tasks), field-level acceptance criteria, deadline tracking guardrails, human review gates, sovereignty and trust requirements, pipeline preview to M0 feature mapping, risks, mitigations, M0 exit criteria for pipeline planning, and **Sprint 124** guidance. It does **not** add database migrations, frontend UI, API routes, production kanban, real user assignment, calendar integration, notification systems, application submission, external service integration, or runtime pursuit engine changes.

Sprint **122** defined reviewed pursuit recommendation previews. Sprint 123 defines **how that reviewed context becomes a visible pursuit pipeline preview** with ownership, deadlines, readiness tracking, provenance, and human override posture for demos.

## Inputs

None. The builder emits a fixed packet from in-repo constants.

## Outputs

The packet includes:

- **`sprint_number`**: `123`
- **`packet_name`**: `NativeForge M0 Pursuit Pipeline Kanban and Deadline Tracking Planning Packet`
- **`packet_version`**: `v1`
- **`artifact_type`**: `nf_active_source_activation_m0_pursuit_pipeline_kanban_deadline_tracking_planning_packet_v1`
- **`artifact_version`**: integer schema version `1`
- **`version`**: semantic packet version string `v1`
- **`generated_at`**: deterministic timestamp constant for reproducible artifacts
- **Guard booleans**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`** all `true`
- **Planning allowances**: **`may_generate_operator_packet`**, **`may_define_pipeline_preview_scope`**, **`may_define_demo_safe_pipeline_states`**, **`may_define_deadline_tracking_fields`**, **`may_define_acceptance_criteria`**, **`may_define_guardrails`** all `true`
- **Zero actuals**: **`actual_external_calls`**, **`actual_source_ingestions`**, **`actual_api_calls`**, **`actual_scrapes`**, **`actual_ai_generations`**, **`actual_form_submissions`**, **`actual_customer_data_access`**, **`actual_runtime_writes`**, **`actual_pipeline_creations`**, **`actual_calendar_writes`**, **`actual_task_assignments`** all `0`
- **`m0_pipeline_preview_foundations`**: ten statements from reviewed opportunity handoff through future runtime pursuit workflow readiness
- **`pipeline_field_groups`**: eighteen structured rows with priorities, names, purposes, and at least two acceptance criteria each
- **`pipeline_statuses`**: eight demo-safe statuses with explicit M0 non-submission and non-automation disclaimers
- **`pipeline_preview_to_m0_feature_mapping`**: rows mapping field usage to M0 surfaces (kanban preview, deadline calendar preview, requirement checklist, SF-424 preview readiness, attachment readiness, human review and override, provenance display, sovereignty trust explainer)
- **`deadline_tracking_guardrails`**, **`human_review_gates`**, **`sovereignty_and_trust_requirements`**, **`sprint_123_does_not_build`**, **`m0_pipeline_planning_exit_criteria`**: operator-ready lists
- **`risks_and_mitigations`**: at least eight documented risks with mitigations
- **`sprint_123_m0_pursuit_pipeline_kanban_deadline_tracking_planning_packet_proof`**: statelessness and preview-only assertions for CI and audits

`render_active_source_activation_m0_pursuit_pipeline_kanban_deadline_tracking_planning_packet_markdown` returns markdown titled **NativeForge M0 Pursuit Pipeline Kanban and Deadline Tracking Planning Packet v1** with fifteen numbered sections.

## Design rules

- **Deterministic**: repeated calls return identical dicts and markdown for the same inputs (there are no inputs).
- **Preview-only**: the artifact may define pipeline preview scope, demo-safe statuses, deadline field expectations, guardrails, and criteria; it must not trigger execution, activation, live ingestion, external API calls, scrapes, LLM generation, calendar writes, task assignment, or production pipeline creation.
- **Demo-safe posture**: all M0 pursuit pipeline previews assume seeded or demo-safe opportunity, profile, and recommendation references only until a future sprint explicitly authorizes runtime engineering.

## Relationship to Sprint 122

Sprint 122 defined opportunity scoring and draft recommendation preview planning. Sprint 123 does not replace that work; it supplies the **pursuit pipeline card and deadline tracking planning depth** that follows a reviewed recommendation preview without opening runtime automation.
