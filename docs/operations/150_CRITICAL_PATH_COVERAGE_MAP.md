# Critical-Path Coverage Map (Gate 06 / Block 17)

Schema: `nf_critical_path_coverage_map_v1`

Paths mapped: **20**

Classification counts: `{"strong": 3, "adequate": 16, "partial": 1}`

## Paths

- **sc_customer_demo_route** (strong): SC customer demo route — ScCustomerDemoPage.test.tsx, sc_customer_demo.smoke.spec.ts, sc_monday_demo_bridge_service
- **opportunity_engine** (adequate): Opportunity engine — campaign block01 smokes, bridge invariants
- **eligibility_evidence** (adequate): Eligibility evidence — campaign block02, demo panel assertions
- **org_memory** (adequate): Organization evidence memory — organization_evidence_memory_*, campaign08
- **pursuit_workspace** (adequate): Pursuit workspace — pursuit_workspace_assembler, campaign03
- **evidence_binder** (partial): Evidence binder — pursuit binder fields; fewer dedicated isolation tests
- **checklist** (adequate): Application checklist — application_plan_workspace
- **intake_approvals** (adequate): Intake / approvals — intake_approval_workspace
- **narrative_budget** (adequate): Narrative / budget scaffold — narrative_budget_scaffold; budget fabrication guards
- **readiness_queue** (adequate): Readiness / operator queue — package_readiness_queue
- **nofo_extraction_pilot** (adequate): NOFO extraction pilot — nofo_extraction_pilot_*; no full PDF claim
- **source_freshness_pilot** (adequate): Source freshness pilot — source_freshness_pilot_*; external live not claimed
- **draft_workspace** (adequate): Draft workspace — draft_workspace_*; AI drafting disabled
- **controlled_drafting** (strong): Controlled drafting v0 — evidence_cited_drafting; $ fabrication fail
- **ai_governance** (strong): AI governance / QA gates — proposal_qa_gate; personalization checker
- **feedback_report_hooks** (adequate): Feedback / report hooks — feedback_loop_assembler; report contract
- **slack_alert_plumbing** (adequate): Slack alert plumbing — feedback_slack_alert_service; dry-run default
- **collaboration_dark_flags** (adequate): Collaboration dark flags — collaboration_dark_flag_service
- **package_export_preview** (adequate): Package export preview — package_export_preview_*; export_allowed=false
- **forms_attachments_map** (adequate): Forms / attachments mapping — forms_attachments_*; completion/persistence false

## Strongest

- sc_customer_demo_route
- controlled_drafting
- ai_governance

## Weakest / partial

- evidence_binder

## Recommended Block 18 focus

- prompt injection / adversarial fixtures
- cross-profile data isolation
- Slack message injection escaping
- QA / claim / export bypass resistance
- HTML/script rendering safety

## Honesty

- full_suite_run: `False`
- pen_test_ready_claimed: `False`
