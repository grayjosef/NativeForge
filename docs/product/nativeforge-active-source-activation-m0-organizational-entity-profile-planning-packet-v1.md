# NativeForge active source activation M0 Organizational Entity Profile planning packet (v1)

## Sprint 118 purpose

Sprint 118 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_m0_organizational_entity_profile_planning_packet_v1`** artifacts. Each packet is the first concrete M0 implementation planning layer for NativeForge's reusable **Organizational Entity Profile**, the highest-priority M0 data foundation.

Sprint 118 creates an **operator-facing planning packet** only. It defines fifteen field groups, acceptance criteria, demo-safe rules, human review gates, sovereignty and trust requirements, entity-profile-to-feature mapping, risks, mitigations, and M0 exit criteria. It does **not** add database migrations, API routes, frontend forms, SAM.gov integration, customer data ingestion, LLM calls, form generation, or billing. It remains **preview-only** and **non-runtime** unless a future sprint explicitly authorizes implementation work.

Sprint 117 M0 demo build execution planning remains the sequencing context. Sprint 118 deepens **entity profile schema and governance planning** while preserving the same demo-safe posture.

## Inputs

None. The builder emits a fixed packet from in-repo constants.

## Outputs

The packet includes:

- **`sprint_number`**: `118`
- **`packet_name`**: `NativeForge M0 Organizational Entity Profile Planning Packet`
- **`packet_version`**: `v1`
- **`artifact_type`**: `nf_active_source_activation_m0_organizational_entity_profile_planning_packet_v1`
- **`artifact_version`**: integer schema version `1`
- **`version`**: semantic packet version string `v1`
- **`generated_at`**: deterministic timestamp constant for reproducible artifacts
- **Guard booleans**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`** all `true`
- **Planning allowances**: **`may_generate_operator_packet`**, **`may_define_entity_profile_scope`**, **`may_define_demo_safe_schema`**, **`may_define_acceptance_criteria`**, **`may_define_guardrails`** all `true`
- **Zero actuals**: **`actual_external_calls`**, **`actual_source_ingestions`**, **`actual_ai_generations`**, **`actual_form_submissions`**, **`actual_customer_data_access`**, **`actual_runtime_writes`** all `0`
- **`m0_entity_profile_foundations`**: ten statements tying the profile to eligibility, mission fit, SF-424 preview, contacts, indirect rates, narratives, human-reviewed forms, audit and export readiness, sovereignty, and future schema expansion
- **`entity_profile_field_groups`**: fifteen structured rows with priorities, names, purposes, and at least two acceptance criteria each
- **`entity_profile_to_m0_feature_mapping`**: rows mapping profile usage to M0 preview features
- **`human_review_gates`**, **`sovereignty_and_trust_requirements`**, **`sprint_118_does_not_build`**, **`m0_entity_profile_planning_exit_criteria`**: operator-ready lists
- **`risks_and_mitigations`**: at least eight documented risks with mitigations
- **`sprint_118_m0_entity_profile_planning_packet_proof`**: statelessness and preview-only assertions for CI and audits

`render_active_source_activation_m0_organizational_entity_profile_planning_packet_markdown` returns markdown titled **NativeForge M0 Organizational Entity Profile Planning Packet v1** with thirteen numbered sections covering purpose, demo-safe rules, field groups, acceptance criteria, feature mapping, human review gates, sovereignty requirements, explicit exclusions (including **no SAM.gov integration** and **no database migration**), exit criteria, risks, and **Sprint 119** guidance for the **Grants.gov Seeded Opportunity Ingestion Interface Planning Packet**.

## Design rules

- **Deterministic**: repeated calls return identical dicts and markdown for the same inputs (there are no inputs).
- **Preview-only**: the artifact may define scope, schema intent, and criteria; it must not trigger execution, activation, ingestion, or external calls.
- **Demo-safe posture**: all M0 profile narratives assume seeded or demo-safe data only until a future sprint explicitly authorizes runtime engineering.

## Relationship to Sprint 117

Sprint 117 sequences M0 demo engineering themes. Sprint 118 does not replace that sequence; it supplies the **entity profile planning depth** those themes depend on, without opening runtime or live data paths.
