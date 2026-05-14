# NativeForge active source activation M0 demo narrative and buyer walkthrough packet (v1)

## Sprint 128 purpose

Sprint 128 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_m0_demo_narrative_buyer_walkthrough_packet_v1`** artifacts. Each packet is the M0 planning layer for a **demo-safe buyer narrative and walkthrough** from buyer problem framing through human review closeout—without generating live sales scripts, creating buyer records, running CRM automation, accessing customer data, submitting applications, performing final eligibility determinations, calling external services, adding database migrations, shipping frontend UI, registering API routes, or changing production workflows.

Sprint 128 creates an **operator-facing planning packet** only. It defines twelve narrative chapters, twelve walkthrough stages (each with explicit seeded-data and non-submission boundaries), eighteen walkthrough field groups with field-level acceptance criteria, buyer walkthrough mapping across ten M0 features, buyer proof points, demo caveats, sovereignty and trust requirements, what Sprint 128 does not build, M0 exit criteria for demo narrative planning, nine documented risks with mitigations, and **Sprint 129** guidance.

Sprint **127** defined human review gates and demo closeout criteria. Sprint **128** packages the **buyer-facing story** those gates protect.

## Inputs

None. The builder emits a fixed packet from in-repo constants.

## Outputs

The packet includes:

- **`sprint_number`**: `128`
- **`packet_name`**: `NativeForge M0 Demo Narrative and Buyer Walkthrough Packet`
- **`packet_version`**: `v1`
- **`artifact_type`**: `nf_active_source_activation_m0_demo_narrative_buyer_walkthrough_packet_v1`
- **`artifact_version`**: integer schema version `1`
- **`version`**: semantic packet version string `v1`
- **`generated_at`**: deterministic timestamp constant for reproducible artifacts
- **Guard booleans**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`** all `true`
- **Planning allowances**: **`may_generate_operator_packet`**, **`may_define_demo_narrative_scope`**, **`may_define_buyer_walkthrough_steps`**, **`may_define_acceptance_criteria`**, **`may_define_guardrails`** all `true`
- **Zero actuals**: all `actual_*` counters including **`actual_demo_scripts_generated`**, **`actual_buyer_records_created`**, and **`actual_sales_automation_runs`** are `0`
- **`m0_demo_narrative_chapters`**: twelve chapters from buyer problem framing through human review closeout
- **`walkthrough_field_groups`**: eighteen structured rows with priorities, names, purposes, and at least two acceptance criteria each
- **`walkthrough_stages`**: twelve stages with purposes and mandatory demo boundary statements
- **`demo_safe_narrative_rules`**, **`buyer_walkthrough_by_m0_feature`**, **`buyer_proof_points`**, **`demo_caveats_and_boundaries`**, **`sovereignty_and_trust_requirements`**, **`sprint_128_does_not_build`**, **`m0_demo_narrative_planning_exit_criteria`**: operator-ready lists
- **`risks_and_mitigations`**: nine documented risks with mitigations
- **`sprint_129_recommended_next_step`**: forward-only operator guidance for the M0 Demo Readiness Evidence Pack and Operator Checklist Packet
- **`sprint_128_m0_demo_narrative_buyer_walkthrough_packet_proof`**: statelessness and preview-only assertions for CI and audits

`render_active_source_activation_m0_demo_narrative_buyer_walkthrough_packet_markdown` returns markdown titled **NativeForge M0 Demo Narrative and Buyer Walkthrough Packet v1** with fifteen numbered sections.

## Design rules

- **Deterministic**: repeated calls return identical dicts and markdown for the same inputs (there are no inputs).
- **Preview-only**: the artifact may define demo narrative scope, buyer walkthrough steps, guardrails, and acceptance criteria; it must not trigger execution, activation, live ingestion, external API calls, scrapes, AI generation, sales script generation, buyer record creation, CRM automation, or production workflow changes.
- **Demo-safe posture**: all M0 demo narrative planning assumes seeded or demo-safe records only until a future sprint explicitly authorizes runtime engineering.

## Relationship to Sprint 127

Sprint 127 defined human review gates and demo closeout planning. Sprint 128 does not replace that work; it supplies the **buyer walkthrough narrative structure** so operators can rehearse a coherent story while review boundaries, provenance, and sovereignty caveats stay visible.
