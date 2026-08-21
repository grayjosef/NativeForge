import { describe, expect, it } from "vitest";

import { loadScCustomerDemoPayload } from "../demo/loadScCustomerDemo";
import { ScCustomerDemoPage } from "./ScCustomerDemoPage";
import { renderToStaticMarkup } from "react-dom/server";

describe("ScCustomerDemoPage", () => {
  it("renders buyer story and honest flags from static payload", () => {
    const payload = loadScCustomerDemoPayload();
    const html = renderToStaticMarkup(<ScCustomerDemoPage payload={payload} />);
    expect(html).toContain("sc-customer-demo-page");
    expect(html).toContain("live_ingestion=false");
    expect(html).toContain("final_eligibility_claim_allowed=false");
    expect(html).toContain("live_ingest_claimed=false");
    expect(html).toContain("What NativeForge found");
    expect(html).toContain("south_carolina=");
    expect(html).toContain("federal=");
    expect(html).toContain("nofo_pdf_extraction=NOT_SUPPORTED");
    expect(html).toContain("sc-demo-nofo-showcase");
    expect(html).toContain("What NativeForge found");
    expect(html).toContain("Application plan skeleton");
    expect(html).toContain("live_ingest_claimed=false");
    expect(html).toContain("nofo_pdf_extraction_claimed=false");
    expect(html).toContain("proposal_drafting_claimed=false");
    expect(html).toContain("sc-demo-opening-line");
    expect(html).toContain("sc-demo-closing-line");
    expect(html).toContain("sc-demo-trust-strip");
    expect(html).toContain("curated-current");
    expect(html).toContain("not automated live ingest");
    expect(html).toContain("Forbidden claims");
    expect(html).toContain("sc-demo-opportunity-engine");
    expect(html).toContain("Durable opportunity engine foundation");
    expect(html).toContain("org_geo_filters_federal=false");
    expect(html).toContain("sc-demo-eligibility-evidence");
    expect(html).toContain("final_eligibility_claimed=false");
    expect(html).toContain("Evidence-backed eligibility");
    expect(html).toContain("sc-demo-pursuit-workspace");
    expect(html).toContain("Pursuit workspace / application package");
    expect(html).toContain("submission_ready_claimed=false");
    expect(html).toContain("proposal_drafting_claimed=false");
    expect(html).toContain("not_submission_ready=");
    expect(html).toContain("sc-demo-application-checklist");
    expect(html).toContain("Application checklist / package build plan");
    expect(html).toContain("submission_allowed=false");
    expect(html).toContain("application_complete_claimed=false");
    expect(html).toContain("sc-demo-intake-approvals");
    expect(html).toContain("Intake &amp; approvals / package gaps");
    expect(html).toContain("upload_persistence_claimed=false");
    expect(html).toContain("approval_persistence_claimed=false");
    expect(html).toContain("package_readiness_unlocked=false");
    expect(html).toContain("sc-demo-narrative-budget");
    expect(html).toContain("Narrative &amp; budget scaffold");
    expect(html).toContain("generated_prose_produced=false");
    expect(html).toContain("drafting_supported=false");
    expect(html).toContain("budget_claimed_complete=false");
    expect(html).toContain("match_claimed_complete=false");
    expect(html).toContain("sc-demo-readiness-queue");
    expect(html).toContain("Readiness &amp; review queue");
    expect(html).toContain("submission_ready_claimed=false");
    expect(html).toContain("final_eligibility_claimed=false");
    expect(html).toContain("not_submission_ready=true");
    expect(html).toContain("sc-demo-org-evidence-memory");
    expect(html).toContain("Organization evidence memory");
    expect(html).toContain("customer_data_persistence_claimed=false");
    expect(html).toContain("binary_upload_persistence_supported=false");
    expect(html).toContain("None auto-approved without review.");
    expect(html).toContain("Must not claim");
    expect(html).toContain("sc-demo-nofo-extraction-pilot");
    expect(html).toContain("NOFO extraction pilot");
    expect(html).toContain("full_pdf_extraction_claimed=false");
    expect(html).toContain("broad_pdf_support_claimed=false");
    expect(html).toContain("pdf_bytes_parsed=false");
    expect(html).toContain("sc-demo-source-freshness");
    expect(html).toContain("Source freshness / source health");
    expect(html).toContain("external_live_check_not_run=true");
    expect(html).toContain("continuous_monitoring_claimed=false");
    expect(html).toContain("production_activation_claimed=false");
    expect(html).toContain("sc-demo-draft-workspace");
    expect(html).toContain("Draft workspace (human-authored)");
    expect(html).toContain("ai_drafting_enabled=false");
    expect(html).toContain("generated_prose_present=false");
    expect(html).toContain("customer_prose_persistence_claimed=false");
    expect(html).toContain("sc-demo-controlled-drafting");
    expect(html).toContain("Controlled draft v0");
    expect(html).toContain("complete_proposal_claimed=false");
    expect(html).toContain("sc-demo-ai-governance");
    expect(html).toContain("AI governance / QA gates");
    expect(html).toContain("qa_passed=false");
    expect(html).toContain("export_allowed=false");
    expect(html).toContain("submission_allowed=false");
    expect(html).toContain("sc-demo-feedback-loop");
    expect(html).toContain("sc-demo-package-export-preview");
    expect(html).toContain("sc-demo-forms-attachments-map");
    expect(html).toContain("Customer feedback / reporting");
    expect(html).toContain("slack_live_sent_claimed=false");
    expect(html).toContain("collaboration_feature_enabled=false");
    expect(payload.buyer_demo?.opening_line).toBeTruthy();
    expect(payload.pursuit_workspace?.workspace_count).toBeGreaterThanOrEqual(1);
    expect(payload.pursuit_workspace?.final_submission_allowed).toBe(false);
    expect(payload.pursuit_workspace?.proposal_drafting_claimed).toBe(false);
    expect(
      payload.application_plan_workspace?.workspace_count,
    ).toBeGreaterThanOrEqual(1);
    expect(payload.application_plan_workspace?.submission_allowed).toBe(false);
    expect(payload.application_plan_workspace?.proposal_drafting_claimed).toBe(
      false,
    );
    expect(payload.application_plan_workspace?.application_complete_claimed).toBe(
      false,
    );
    expect(
      payload.intake_approval_workspace?.workspace_count,
    ).toBeGreaterThanOrEqual(1);
    expect(
      payload.intake_approval_workspace?.binary_upload_persistence_claimed,
    ).toBe(false);
    expect(payload.intake_approval_workspace?.approval_persistence_claimed).toBe(
      false,
    );
    expect(payload.intake_approval_workspace?.package_readiness_unlocked).toBe(
      false,
    );
    expect(
      payload.narrative_budget_scaffold?.workspace_count,
    ).toBeGreaterThanOrEqual(1);
    expect(payload.narrative_budget_scaffold?.generated_prose_produced).toBe(false);
    expect(payload.narrative_budget_scaffold?.drafting_supported).toBe(false);
    expect(payload.narrative_budget_scaffold?.budget_claimed_complete).toBe(false);
    expect(payload.narrative_budget_scaffold?.match_claimed_complete).toBe(false);
    expect(
      payload.package_readiness_queue?.workspace_count,
    ).toBeGreaterThanOrEqual(1);
    expect(payload.package_readiness_queue?.submission_ready_claimed).toBe(false);
    expect(payload.package_readiness_queue?.final_eligibility_claimed).toBe(false);
    expect(payload.package_readiness_queue?.not_submission_ready_label).toBe(true);
    expect(
      payload.organization_evidence_memory?.profile_count,
    ).toBeGreaterThanOrEqual(1);
    expect(payload.organization_evidence_memory?.federal_count).toBeGreaterThanOrEqual(
      1,
    );
    expect(
      payload.organization_evidence_memory?.state_only_count,
    ).toBeGreaterThanOrEqual(1);
    expect(
      payload.organization_evidence_memory?.customer_data_persistence_claimed,
    ).toBe(false);
    expect(payload.organization_evidence_memory?.final_eligibility_claimed).toBe(
      false,
    );
    expect(payload.organization_evidence_memory?.fabricated_org_facts).toBe(false);
    expect(payload.nofo_extraction_pilot?.pilot_opportunity_id).toBe("la-real-006");
    expect(payload.nofo_extraction_pilot?.full_pdf_extraction_claimed).toBe(false);
    expect(payload.nofo_extraction_pilot?.broad_pdf_support_claimed).toBe(false);
    expect(payload.nofo_extraction_pilot?.pdf_bytes_parsed).toBe(false);
    expect(payload.source_freshness_pilot?.source_count).toBeGreaterThanOrEqual(1);
    expect(payload.source_freshness_pilot?.live_ingest_claimed).toBe(false);
    expect(payload.source_freshness_pilot?.continuous_monitoring_claimed).toBe(false);
    expect(payload.source_freshness_pilot?.production_activation_claimed).toBe(false);
    expect(payload.source_freshness_pilot?.external_live_check_not_run).toBe(true);
    expect(payload.draft_workspace?.workspace_count).toBeGreaterThanOrEqual(1);
    expect(payload.draft_workspace?.ai_drafting_enabled).toBe(false);
    expect(payload.draft_workspace?.generated_prose_present).toBe(false);
    expect(payload.draft_workspace?.customer_prose_persistence_claimed).toBe(false);
    expect(payload.controlled_drafting?.workspace_count).toBeGreaterThanOrEqual(1);
    expect(payload.controlled_drafting?.complete_proposal_claimed).toBe(false);
    expect(payload.controlled_drafting?.submission_ready_claimed).toBe(false);
    expect(payload.controlled_drafting?.final_text_claimed).toBe(false);
    expect(payload.ai_governance?.qa_passed).toBe(false);
    expect(payload.ai_governance?.export_allowed).toBe(false);
    expect(payload.ai_governance?.submission_allowed).toBe(false);
    expect(payload.feedback_loop?.report_hook_count).toBeGreaterThanOrEqual(10);
    expect(payload.feedback_loop?.slack_live_sent_claimed).toBe(false);
    expect(payload.feedback_loop?.persistence_claimed).toBe(false);
    expect(
      payload.feedback_loop?.collaboration.collaboration_feature_enabled,
    ).toBe(false);
    expect(payload.package_export_preview?.export_allowed).toBe(false);
    expect(payload.package_export_preview?.final_export_claimed).toBe(false);
    expect(payload.package_export_preview?.submission_ready_claimed).toBe(false);
    expect(payload.package_export_preview?.download_supported).toBe(false);
    expect(payload.forms_attachments_map?.binary_upload_supported).toBe(false);
    expect(payload.forms_attachments_map?.attachment_persistence_claimed).toBe(
      false,
    );
    expect(payload.forms_attachments_map?.form_completion_claimed).toBe(false);
    expect(payload.forms_attachments_map?.submission_ready_claimed).toBe(false);
    expect(payload.opportunity_engine?.combined_workflow.counts.sc_state).toBeGreaterThanOrEqual(
      1,
    );
    expect(
      payload.opportunity_engine?.combined_workflow.counts.federal,
    ).toBeGreaterThanOrEqual(1);
    expect(
      payload.opportunity_engine?.combined_workflow.eligibility_evidence_handoff
        ?.federal_pairs_visible,
    ).toBe(true);
    expect(
      payload.opportunity_engine?.combined_workflow.eligibility_evidence_handoff
        ?.final_eligibility_claimed,
    ).toBe(false);
    expect(payload.nofo_showcase?.sc_selected_count).toBeGreaterThanOrEqual(1);
    expect(payload.nofo_showcase?.federal_selected_count).toBeGreaterThanOrEqual(1);
    expect(payload.opportunities.south_carolina_count).toBeGreaterThanOrEqual(1);
    expect(payload.opportunities.federal_count).toBeGreaterThanOrEqual(1);
  });

  it("renders loading empty and error states", () => {
    expect(renderToStaticMarkup(<ScCustomerDemoPage loading />)).toContain(
      "sc-demo-loading",
    );
    expect(
      renderToStaticMarkup(<ScCustomerDemoPage error="boom" payload={null} />),
    ).toContain("sc-demo-error");
    expect(renderToStaticMarkup(<ScCustomerDemoPage payload={null} />)).toContain(
      "sc-demo-empty",
    );
  });
});
