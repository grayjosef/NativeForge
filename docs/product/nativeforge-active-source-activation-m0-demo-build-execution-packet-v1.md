# NativeForge active source activation M0 demo build execution packet (v1)

## Sprint 117 purpose

Sprint 117 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_m0_demo_build_execution_packet_v1`** artifacts. Each packet is the first post-Sprint-116 operational planning artifact: it converts NativeForge Product Intelligence Report themes into an **M0 demo build execution plan** for operators.

Sprint 117 creates an **operator-facing packet generator** only. It defines the M0 demo build sequence, feature gates, guardrails, risks, and acceptance criteria. It does **not** perform runtime activation, live Grants.gov or SAM.gov ingestion, LLM calls, production form generation, customer onboarding, or runnable workflow code. It is **deterministic** and **side-effect-free**.

Sprint 116 and prior activation packets remain the activation-planning chain. Sprint 117 begins **M0 demo build readiness** documentation while preserving preview-only posture.

## Inputs

None. The builder emits a fixed packet from in-repo constants.

## Outputs

The packet includes:

- **`sprint_number`**: `117`
- **`packet_name`**: `NativeForge M0 Demo Build Execution Packet`
- **`packet_version`**: `v1`
- **`artifact_type`**: `nf_active_source_activation_m0_demo_build_execution_packet_v1`
- **`artifact_version`**: integer schema version `1`
- **`version`**: semantic packet version string `v1`
- **`generated_at`**: deterministic timestamp constant for reproducible artifacts
- **Guard booleans**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`** all `true`
- **Planning allowances**: **`may_generate_operator_packet`**, **`may_define_m0_demo_scope`**, **`may_define_acceptance_criteria`**, **`may_define_guardrails`**, **`may_define_sequencing`** all `true`
- **Zero actuals**: **`actual_external_calls`**, **`actual_source_ingestions`**, **`actual_ai_generations`**, **`actual_form_submissions`**, **`actual_customer_data_access`**, **`actual_runtime_writes`** all `0`
- **`m0_build_sequence`**: ordered list of ten M0 demo scope items (organizational profile through human review gates)
- **`m0_demo_features`**: structured rows with priorities, titles, and at least three acceptance criteria each
- **`risks_and_mitigations`**: at least eight documented risks with mitigations
- **`sprint_117_m0_demo_build_execution_packet_proof`**: statelessness and no-live-work assertions for CI and audits

`render_active_source_activation_m0_demo_build_execution_packet_markdown` returns markdown containing the titled sections **NativeForge M0 Demo Build Execution Packet v1** through Sprint 118 guidance, including demo-safe data rules, human review gates, sovereignty guardrails, and explicit exclusions such as **no live Grants.gov ingestion**.

## Design rules

- **Deterministic**: repeated calls return identical dicts and markdown for the same inputs (there are no inputs).
- **Preview-only**: the artifact may define scope and criteria; it must not trigger execution, activation, ingestion, or external calls.
- **Demo-safe posture**: all M0 narratives assume seeded or demo-safe data only until a future sprint explicitly authorizes runtime engineering.

## Relationship to Sprint 116

Sprint 116 concluded the operator final activation packet gate for activation planning. Sprint 117 does not reopen live activation; it layers **M0 demo build execution planning** as the next operator artifact family for product walkthrough readiness.
