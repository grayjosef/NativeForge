# NativeForge active source activation M0 Grants.gov seeded opportunity ingestion interface planning packet (v1)

## Sprint 119 purpose

Sprint 119 adds a deterministic, side-effect-free Python service that builds **`nf_active_source_activation_m0_grants_gov_seeded_opportunity_ingestion_interface_planning_packet_v1`** artifacts. Each packet is the M0 planning layer for a **demo-safe Grants.gov-style opportunity ingestion interface** that uses **seeded or fixture data only**.

Sprint 119 creates an **operator-facing planning packet** only. It defines fifteen seeded opportunity field groups, acceptance criteria, demo-safe source rules, human review gates, source provenance and freshness requirements, sovereignty and trust requirements, opportunity-to-feature mapping, risks, mitigations, and M0 exit criteria. It does **not** add live Grants.gov ingestion, Grants.gov API calls, SAM.gov integration, agency scraping, real NOFO parsing, LLM extraction, database migrations, frontend UI, runtime ingestion workers, or production source activation. It remains **preview-only** and **non-runtime** unless a future sprint explicitly authorizes implementation work.

Sprint 118 Organizational Entity Profile planning remains the upstream matching context. Sprint 119 deepens **seeded opportunity contract and governance planning** while preserving the same demo-safe posture.

## Inputs

None. The builder emits a fixed packet from in-repo constants.

## Outputs

The packet includes:

- **`sprint_number`**: `119`
- **`packet_name`**: `NativeForge M0 Grants.gov Seeded Opportunity Ingestion Interface Planning Packet`
- **`packet_version`**: `v1`
- **`artifact_type`**: `nf_active_source_activation_m0_grants_gov_seeded_opportunity_ingestion_interface_planning_packet_v1`
- **`artifact_version`**: integer schema version `1`
- **`version`**: semantic packet version string `v1`
- **`generated_at`**: deterministic timestamp constant for reproducible artifacts
- **Guard booleans**: **`preview_only`**, **`no_execution`**, **`no_activation`**, **`no_runnable_plan`** all `true`
- **Planning allowances**: **`may_generate_operator_packet`**, **`may_define_seeded_ingestion_scope`**, **`may_define_demo_safe_opportunity_contract`**, **`may_define_acceptance_criteria`**, **`may_define_guardrails`** all `true`
- **Zero actuals**: **`actual_external_calls`**, **`actual_source_ingestions`**, **`actual_api_calls`**, **`actual_scrapes`**, **`actual_ai_generations`**, **`actual_form_submissions`**, **`actual_customer_data_access`**, **`actual_runtime_writes`** all `0`
- **`m0_seeded_opportunity_foundations`**: ten statements tying seeded opportunities to discovery, tribal relevance, mission fit, NOFO and requirement previews, pursuit handoff, deadlines, provenance, human review, and future live readiness without activation
- **`seeded_opportunity_field_groups`**: fifteen structured rows with priorities, names, purposes, and at least two acceptance criteria each
- **`seeded_opportunity_to_m0_feature_mapping`**: rows mapping opportunity field usage to M0 preview features
- **`human_review_gates`**, **`source_provenance_and_freshness_requirements`**, **`sovereignty_and_trust_requirements`**, **`sprint_119_does_not_build`**, **`m0_seeded_opportunity_planning_exit_criteria`**: operator-ready lists
- **`risks_and_mitigations`**: at least eight documented risks with mitigations
- **`sprint_119_m0_seeded_opportunity_planning_packet_proof`**: statelessness and preview-only assertions for CI and audits

`render_active_source_activation_m0_grants_gov_seeded_opportunity_ingestion_interface_planning_packet_markdown` returns markdown titled **NativeForge M0 Grants.gov Seeded Opportunity Ingestion Interface Planning Packet v1** with fourteen numbered sections covering purpose, entity-profile sequencing, objectives, demo-safe rules, field groups, acceptance criteria, feature mapping, human review gates, provenance and freshness, sovereignty requirements, explicit exclusions (including **no live Grants.gov ingestion**, **no Grants.gov API call**, and **no database migration**), exit criteria, risks, and **Sprint 120** guidance for the **M0 Tribal Eligibility Tagging and Mission Fit Scoring Preview Planning Packet**.

## Design rules

- **Deterministic**: repeated calls return identical dicts and markdown for the same inputs (there are no inputs).
- **Preview-only**: the artifact may define scope, contract intent, and criteria; it must not trigger execution, activation, ingestion, external API calls, or scrapes.
- **Demo-safe posture**: all M0 opportunity narratives assume seeded or demo-safe data only until a future sprint explicitly authorizes runtime engineering.

## Relationship to Sprint 118

Sprint 118 defines the Organizational Entity Profile planning depth that eligibility, mission fit, contacts, capacity, and form preview readiness depend on. Sprint 119 does not replace that work; it supplies the **seeded opportunity interface planning depth** those previews consume, without opening live Grants.gov or production data paths.
