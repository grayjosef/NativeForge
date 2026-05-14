# NativeForge active source activation M0 NOFO plain-language summary preview planning packet (v1)

## Sprint 121 purpose

Sprint 121 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_m0_nofo_plain_language_summary_preview_planning_packet_v1`** artifacts. Each packet is the M0 planning layer for **demo-safe plain-language summaries** of **seeded or fixture NOFO-style opportunities** only.

Sprint 121 creates an **operator-facing planning packet** only. It defines seventeen summary preview field groups, field-level acceptance criteria, demo-safe summary rules, summary preview to M0 feature mapping, human review gates, sovereignty and trust requirements, risks, mitigations, and M0 exit criteria. It does **not** parse live NOFOs, call Grants.gov or SAM.gov, scrape agencies, invoke LLMs, generate real summary text from production sources, perform database migrations, ship frontend UI, or run live workflows. It remains **preview-only** and **non-runtime** unless a future sprint explicitly authorizes implementation work.

Sprint 120 tribal eligibility and mission fit scoring preview planning remains upstream. Sprint 121 defines **how summaries narrate** those demo-safe signals without opening live parsing or generation paths.

## Inputs

None. The builder emits a fixed packet from in-repo constants.

## Outputs

The packet includes:

- **`sprint_number`**: `121`
- **`packet_name`**: `NativeForge M0 NOFO Plain-Language Summary Preview Planning Packet`
- **`packet_version`**: `v1`
- **`artifact_type`**: `nf_active_source_activation_m0_nofo_plain_language_summary_preview_planning_packet_v1`
- **`artifact_version`**: integer schema version `1`
- **`version`**: semantic packet version string `v1`
- **`generated_at`**: deterministic timestamp constant for reproducible artifacts
- **Guard booleans**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`** all `true`
- **Planning allowances**: **`may_generate_operator_packet`**, **`may_define_demo_safe_summary_scope`**, **`may_define_plain_language_mapping_rules`**, **`may_define_acceptance_criteria`**, **`may_define_guardrails`** all `true`
- **Zero actuals**: **`actual_external_calls`**, **`actual_source_ingestions`**, **`actual_api_calls`**, **`actual_scrapes`**, **`actual_ai_generations`**, **`actual_form_submissions`**, **`actual_customer_data_access`**, **`actual_runtime_writes`** all `0`
- **`m0_nofo_summary_preview_foundations`**: ten statements from demo-safe summary generation through future runtime-ready summary generation
- **`summary_preview_field_groups`**: seventeen structured rows with priorities, names, purposes, and at least two acceptance criteria each
- **`summary_preview_to_m0_feature_mapping`**: rows mapping field usage to M0 summary-related features
- **`human_review_gates`**, **`sovereignty_and_trust_requirements`**, **`sprint_121_does_not_build`**, **`m0_nofo_summary_preview_planning_exit_criteria`**: operator-ready lists
- **`risks_and_mitigations`**: at least eight documented risks with mitigations
- **`sprint_121_m0_nofo_summary_preview_planning_packet_proof`**: statelessness and preview-only assertions for CI and audits

`render_active_source_activation_m0_nofo_plain_language_summary_preview_planning_packet_markdown` returns markdown titled **NativeForge M0 NOFO Plain-Language Summary Preview Planning Packet v1** with thirteen numbered sections covering purpose, sequencing after tribal eligibility scoring, objectives, demo-safe summary rules, field groups, acceptance criteria, feature mapping, human review gates, sovereignty requirements, explicit exclusions (including **no live NOFO parsing**, **no real plain-language text generation from live sources**, and **no LLM calls**), exit criteria, risks, and **Sprint 122** guidance for the **M0 Opportunity Scoring & Draft Recommendation Planning Packet**.

## Design rules

- **Deterministic**: repeated calls return identical dicts and markdown for the same inputs (there are no inputs).
- **Preview-only**: the artifact may define summary preview scope, mapping rules, and criteria; it must not trigger execution, activation, live parsing, external API calls, scrapes, or LLM generation.
- **Demo-safe posture**: all M0 summary preview narratives assume seeded or demo-safe opportunity data only until a future sprint explicitly authorizes runtime engineering.

## Relationship to Sprint 120

Sprint 120 defines eligibility and mission fit scoring previews on seeded records. Sprint 121 does not replace that work; it supplies the **plain-language summary preview planning depth** that narrates those artifacts without live NOFO parsing, Grants.gov, SAM.gov, LLMs, or runtime summary engines.
