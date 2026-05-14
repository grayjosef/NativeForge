# NativeForge active source activation M0 data sovereignty policy and export preview planning packet (v1)

## Sprint 126 purpose

Sprint 126 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_m0_data_sovereignty_policy_export_preview_planning_packet_v1`** artifacts. Each packet is the M0 planning layer for **demo-safe data sovereignty policy and export readiness previews**—without real data export, customer data access, policy setting changes, retention changes, database migrations, frontend UI, API routes, tenant administration, legal analysis, external storage integration, or a runtime governance engine.

Sprint 126 creates an **operator-facing planning packet** only. It defines sovereignty and export preview foundations, eighteen policy field groups with field-level acceptance criteria, demo-safe sovereignty rules, export preview rules, AI usage and consent rules, human review gates, sovereignty and trust requirements, sovereignty preview to M0 feature mapping, risks, mitigations, M0 exit criteria for sovereignty and export planning, and **Sprint 127** guidance.

Sprint **125** defined requirement checklist preview readiness. Sprint 126 defines the **trust layer** that must be visible before NativeForge can credibly demo buyer-owned data, exportability, provenance, and AI usage boundaries.

## Inputs

None. The builder emits a fixed packet from in-repo constants.

## Outputs

The packet includes:

- **`sprint_number`**: `126`
- **`packet_name`**: `NativeForge M0 Data Sovereignty Policy and Export Preview Planning Packet`
- **`packet_version`**: `v1`
- **`artifact_type`**: `nf_active_source_activation_m0_data_sovereignty_policy_export_preview_planning_packet_v1`
- **`artifact_version`**: integer schema version `1`
- **`version`**: semantic packet version string `v1`
- **`generated_at`**: deterministic timestamp constant for reproducible artifacts
- **Guard booleans**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`** all `true`
- **Planning allowances**: **`may_generate_operator_packet`**, **`may_define_sovereignty_policy_scope`**, **`may_define_demo_safe_export_fields`**, **`may_define_acceptance_criteria`**, **`may_define_guardrails`** all `true`
- **Zero actuals**: all `actual_*` counters including **`actual_exports_created`**, **`actual_policy_changes`**, and **`actual_retention_changes`** are `0`
- **`m0_sovereignty_and_export_preview_foundations`**: ten statements from tribe or customer-owned data policy preview through future private deployment readiness
- **`policy_field_groups`**: eighteen structured rows with priorities, names, purposes, and at least two acceptance criteria each
- **`sovereignty_preview_to_m0_feature_mapping`**: rows mapping policy preview fields to M0 surfaces including organizational entity profile, seeded opportunities, SF-424 preview, requirement checklist preview, pursuit pipeline preview, audit and export readiness, source provenance display, human review workflow, and future tenant governance
- **`export_preview_rules`**, **`ai_usage_and_consent_rules`**, **`human_review_gates`**, **`sovereignty_and_trust_requirements`**, **`sprint_126_does_not_build`**, **`m0_sovereignty_export_planning_exit_criteria`**: operator-ready lists
- **`risks_and_mitigations`**: at least eight documented risks with mitigations
- **`sprint_126_m0_data_sovereignty_export_preview_planning_packet_proof`**: statelessness and preview-only assertions for CI and audits

`render_active_source_activation_m0_data_sovereignty_policy_export_preview_planning_packet_markdown` returns markdown titled **NativeForge M0 Data Sovereignty Policy and Export Preview Planning Packet v1** with fifteen numbered sections.

## Design rules

- **Deterministic**: repeated calls return identical dicts and markdown for the same inputs (there are no inputs).
- **Preview-only**: the artifact may define sovereignty policy scope, demo-safe export fields, guardrails, and criteria; it must not trigger execution, activation, live ingestion, external API calls, scrapes, AI generation, real exports, policy changes, retention changes, or production governance changes.
- **Demo-safe posture**: all M0 sovereignty and export previews assume seeded or demo-safe policy content only until a future sprint explicitly authorizes runtime engineering.

## Relationship to Sprint 125

Sprint 125 defined requirement checklist preview planning. Sprint 126 does not replace that work; it supplies **data sovereignty, consent, export preview, audit, retention, and human-review planning depth** that buyers should see alongside checklist and pipeline previews—still without accessing customer data or changing production settings.
