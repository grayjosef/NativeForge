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
