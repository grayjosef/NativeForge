import { expect, test, type Page } from "@playwright/test";

/**
 * SC Monday customer demo Playwright smoke — curated state+federal lane.
 * Offline static bridge; no live ingest / activation / auth mutation.
 */

const DEMO_PATH = "/?view=sc_customer_demo";

async function openDemo(page: Page) {
  await page.goto(DEMO_PATH);
  await expect(page.getByTestId("sc-customer-demo-page")).toBeVisible();
}

test.describe("SC customer demo Playwright smoke", () => {
  test("renders required Monday customer surfaces", async ({ page }) => {
    await openDemo(page);

    await expect(page.getByTestId("sc-demo-opening-line")).toBeVisible();
    await expect(page.getByTestId("sc-demo-closing-line")).toBeVisible();
    await expect(page.getByTestId("sc-demo-trust-strip")).toContainText(
      "curated-current",
    );
    await expect(page.getByTestId("sc-demo-trust-strip")).toContainText(
      "not automated live ingest",
    );
    await expect(page.getByTestId("sc-demo-trust-strip")).toContainText(
      "human review required",
    );
    await expect(page.getByTestId("sc-demo-allowed-claims")).toBeVisible();
    await expect(page.getByTestId("sc-demo-forbidden-claims")).toContainText(
      "Automated live ingestion",
    );
    await expect(page.getByTestId("sc-demo-opportunity-engine")).toBeVisible();
    await expect(page.getByTestId("sc-demo-engine-flags")).toContainText(
      "live_ingest_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-engine-flags")).toContainText(
      "org_geo_filters_federal=false",
    );
    await expect(page.getByTestId("sc-demo-engine-counts")).toContainText("sc_state");
    await expect(page.getByTestId("sc-demo-engine-counts")).toContainText("federal");
    await expect(page.getByTestId("sc-demo-eligibility-evidence")).toBeVisible();
    await expect(page.getByTestId("sc-demo-eligibility-flags")).toContainText(
      "final_eligibility_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-eligibility-flags")).toContainText(
      "federal_pairs_visible=true",
    );
    await expect(page.getByTestId("sc-demo-eligibility-flags")).toContainText(
      "scoring_math_changed=false",
    );
    await expect(page.getByTestId("sc-demo-eligibility-samples")).toContainText(
      "recognition_tier=",
    );
    await expect(page.getByTestId("sc-demo-eligibility-tier-why")).toContainText(
      "Federal recognition",
    );
    await expect(page.getByTestId("sc-demo-pursuit-workspace")).toBeVisible();
    await expect(page.getByTestId("sc-demo-pursuit-flags")).toContainText(
      "submission_ready_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-pursuit-flags")).toContainText(
      "proposal_drafting_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-pursuit-flags")).toContainText(
      "final_submission_allowed=false",
    );
    await expect(page.getByTestId("sc-demo-pursuit-summary")).toContainText(
      "pursuit workspace",
    );
    await expect(
      page.locator('[data-testid^="sc-demo-pursuit-card-"]').first(),
    ).toContainText("not_submission_ready=");
    await expect(
      page.locator('[data-testid^="sc-demo-pursuit-card-"]').first(),
    ).toContainText("What NativeForge pre-built");
    await expect(page.getByTestId("sc-demo-application-checklist")).toBeVisible();
    await expect(page.getByTestId("sc-demo-checklist-flags")).toContainText(
      "submission_allowed=false",
    );
    await expect(page.getByTestId("sc-demo-checklist-flags")).toContainText(
      "proposal_drafting_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-checklist-flags")).toContainText(
      "application_complete_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-checklist-summary")).toContainText(
      "package we need to assemble",
    );
    await expect(
      page.locator('[data-testid^="sc-demo-checklist-card-"]').first(),
    ).toContainText("why_submission_not_allowed=");
    await expect(
      page.locator('[data-testid^="sc-demo-checklist-card-"]').first(),
    ).toContainText("Missing information questions");
    await expect(page.getByTestId("sc-demo-intake-approvals")).toBeVisible();
    await expect(page.getByTestId("sc-demo-intake-flags")).toContainText(
      "upload_persistence_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-intake-flags")).toContainText(
      "approval_persistence_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-intake-flags")).toContainText(
      "package_readiness_unlocked=false",
    );
    await expect(page.getByTestId("sc-demo-intake-summary")).toContainText(
      "files, confirmations, and approvals",
    );
    await expect(
      page.locator('[data-testid^="sc-demo-intake-card-"]').first(),
    ).toContainText("why_package_not_ready=");
    await expect(
      page.locator('[data-testid^="sc-demo-intake-card-"]').first(),
    ).toContainText("Required intake items");
    await expect(page.getByTestId("sc-demo-narrative-budget")).toBeVisible();
    await expect(page.getByTestId("sc-demo-narrative-flags")).toContainText(
      "generated_prose_produced=false",
    );
    await expect(page.getByTestId("sc-demo-narrative-flags")).toContainText(
      "drafting_supported=false",
    );
    await expect(page.getByTestId("sc-demo-narrative-flags")).toContainText(
      "budget_claimed_complete=false",
    );
    await expect(page.getByTestId("sc-demo-narrative-flags")).toContainText(
      "match_claimed_complete=false",
    );
    await expect(page.getByTestId("sc-demo-narrative-summary")).toContainText(
      "narrative and budget areas",
    );
    await expect(
      page.locator('[data-testid^="sc-demo-narrative-card-"]').first(),
    ).toContainText("why_drafting_not_supported=");
    await expect(
      page.locator('[data-testid^="sc-demo-narrative-card-"]').first(),
    ).toContainText("Budget / match evidence");
    await expect(page.getByTestId("sc-demo-readiness-queue")).toBeVisible();
    await expect(page.getByTestId("sc-demo-readiness-flags")).toContainText(
      "submission_ready_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-readiness-flags")).toContainText(
      "final_eligibility_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-readiness-flags")).toContainText(
      "not_submission_ready=true",
    );
    await expect(page.getByTestId("sc-demo-readiness-summary")).toContainText(
      "package readiness",
    );
    await expect(
      page.locator('[data-testid^="sc-demo-readiness-card-"]').first(),
    ).toContainText("next_safest_action=");
    await expect(
      page.locator('[data-testid^="sc-demo-readiness-card-"]').first(),
    ).toContainText("Operator review queue");
    await expect(page.getByTestId("sc-demo-org-evidence-memory")).toBeVisible();
    await expect(page.getByTestId("sc-demo-org-memory-flags")).toContainText(
      "customer_data_persistence_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-org-memory-flags")).toContainText(
      "final_eligibility_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-org-memory-flags")).toContainText(
      "binary_upload_persistence_supported=false",
    );
    await expect(page.getByTestId("sc-demo-org-memory-summary")).toContainText(
      "organization",
    );
    await expect(
      page.locator('[data-testid^="sc-demo-org-memory-card-"]').first(),
    ).toContainText("Must not claim");
    await expect(
      page.locator('[data-testid^="sc-demo-org-memory-card-"]').first(),
    ).toContainText("None auto-approved without review.");
    await expect(page.getByTestId("sc-demo-nofo-extraction-pilot")).toBeVisible();
    await expect(page.getByTestId("sc-demo-nofo-extract-flags")).toContainText(
      "full_pdf_extraction_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-nofo-extract-flags")).toContainText(
      "broad_pdf_support_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-nofo-extract-flags")).toContainText(
      "pdf_bytes_parsed=false",
    );
    await expect(page.getByTestId("sc-demo-nofo-extract-summary")).toContainText(
      "Controlled NOFO",
    );
    await expect(page.getByTestId("sc-demo-source-freshness")).toBeVisible();
    await expect(page.getByTestId("sc-demo-source-freshness-flags")).toContainText(
      "live_ingest_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-source-freshness-flags")).toContainText(
      "continuous_monitoring_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-source-freshness-flags")).toContainText(
      "external_live_check_not_run=true",
    );
    await expect(page.getByTestId("sc-demo-draft-workspace")).toBeVisible();
    await expect(page.getByTestId("sc-demo-draft-ws-flags")).toContainText(
      "ai_drafting_enabled=false",
    );
    await expect(page.getByTestId("sc-demo-draft-ws-flags")).toContainText(
      "generated_prose_present=false",
    );
    await expect(page.getByTestId("sc-demo-draft-ws-flags")).toContainText(
      "customer_prose_persistence_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-controlled-drafting")).toBeVisible();
    await expect(page.getByTestId("sc-demo-controlled-draft-flags")).toContainText(
      "complete_proposal_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-controlled-draft-flags")).toContainText(
      "submission_ready_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-ai-governance")).toBeVisible();
    await expect(page.getByTestId("sc-demo-ai-gov-flags")).toContainText(
      "qa_passed=false",
    );
    await expect(page.getByTestId("sc-demo-ai-gov-flags")).toContainText(
      "export_allowed=false",
    );
    await expect(page.getByTestId("sc-demo-ai-gov-flags")).toContainText(
      "submission_allowed=false",
    );
    await expect(page.getByTestId("sc-demo-feedback-loop")).toBeVisible();
    await expect(page.getByTestId("sc-demo-feedback-flags")).toContainText(
      "slack_live_sent_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-feedback-flags")).toContainText(
      "collaboration_feature_enabled=false",
    );
    await expect(page.getByTestId("sc-demo-package-export-preview")).toBeVisible();
    await expect(page.getByTestId("sc-demo-export-preview-flags")).toContainText(
      "export_allowed=false",
    );
    await expect(page.getByTestId("sc-demo-export-preview-flags")).toContainText(
      "final_export_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-export-preview-flags")).toContainText(
      "submission_ready_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-forms-attachments-map")).toBeVisible();
    await expect(page.getByTestId("sc-demo-forms-map-flags")).toContainText(
      "binary_upload_supported=false",
    );
    await expect(page.getByTestId("sc-demo-forms-map-flags")).toContainText(
      "form_completion_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-forms-map-flags")).toContainText(
      "attachment_persistence_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-multi-org-pilot")).toBeVisible();
    await expect(page.getByTestId("sc-demo-multi-org-flags")).toContainText(
      "production_multi_tenant_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-multi-org-flags")).toContainText(
      "live_customer_login_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-multi-org-flags")).toContainText(
      "collaboration_enabled=false",
    );
    await expect(page.getByTestId("sc-demo-collaboration-dark-launch")).toBeVisible();
    await expect(page.getByTestId("sc-demo-collab-dark-flags")).toContainText(
      "feature_enabled=false",
    );
    await expect(page.getByTestId("sc-demo-collab-dark-flags")).toContainText(
      "partner_matching_live_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-collab-dark-flags")).toContainText(
      "data_sharing_allowed=false",
    );
    await expect(page.getByTestId("sc-demo-evidence-intake")).toBeVisible();
    await expect(page.getByTestId("sc-demo-evidence-intake-flags")).toContainText(
      "upload_persistence_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-evidence-intake-flags")).toContainText(
      "package_unlock_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-evidence-intake-flags")).toContainText(
      "upload_ui_supported=false",
    );
    await expect(page.getByTestId("sc-demo-operator-readiness")).toBeVisible();
    await expect(page.getByTestId("sc-demo-operator-ready-flags")).toContainText(
      "production_ready_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-operator-ready-flags")).toContainText(
      "pen_test_passed_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-operator-ready-flags")).toContainText(
      "monday=GO",
    );
    await expect(page.getByTestId("sc-demo-operator-ready-flags")).toContainText(
      "production=NO_GO",
    );
    await expect(page.getByTestId("sc-demo-persistence-approval-gate")).toBeVisible();
    await expect(page.getByTestId("sc-demo-persist-gate-flags")).toContainText(
      "migration_applied=true",
    );
    await expect(page.getByTestId("sc-demo-persist-gate-flags")).toContainText(
      "validated_persistent_scope=local_dev_only",
    );
    await expect(page.getByTestId("sc-demo-persist-gate-flags")).toContainText(
      "production_storage_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-persist-gate-flags")).toContainText(
      "customer_data_persistence_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-customer-pilot-auth")).toBeVisible();
    await expect(page.getByTestId("sc-demo-customer-auth-flags")).toContainText(
      "login_live_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-customer-auth-flags")).toContainText(
      "production_auth_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-customer-auth-flags")).toContainText(
      "controlled_customer_pilot_status=NO_GO",
    );
    await expect(page.getByTestId("sc-demo-gate10-closeout")).toBeVisible();
    await expect(page.getByTestId("sc-demo-gate10-closeout-flags")).toContainText(
      "monday=GO",
    );
    await expect(page.getByTestId("sc-demo-gate10-closeout-flags")).toContainText(
      "pen_test_passed_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-national-coverage")).toBeVisible();
    await expect(page.getByTestId("sc-demo-national-coverage-flags")).toContainText(
      "top_15_count=15",
    );
    await expect(page.getByTestId("sc-demo-national-coverage-flags")).toContainText(
      "live_coverage_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-applicant-authority")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-applicant-authority-flags"),
    ).toContainText("submission_authority_claimed=false");
    await expect(
      page.getByTestId("sc-demo-applicant-authority-flags"),
    ).toContainText("federal_authority_claimed=false");
    await expect(page.getByTestId("sc-demo-evidence-lifecycle")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-evidence-lifecycle-flags"),
    ).toContainText("submission_unlock_status=false");
    await expect(
      page.getByTestId("sc-demo-evidence-lifecycle-flags"),
    ).toContainText("legal_compliance_claimed=false");
    await expect(page.getByTestId("sc-demo-top15-source-validation")).toBeVisible();
    await expect(page.getByTestId("sc-demo-top15-source-flags")).toContainText(
      "packet_count=15",
    );
    await expect(page.getByTestId("sc-demo-top15-source-flags")).toContainText(
      "all_top15_live=false",
    );
    await expect(page.getByTestId("sc-demo-production-enforcement")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-production-enforcement-flags"),
    ).toContainText("production_storage_claimed=false");
    await expect(
      page.getByTestId("sc-demo-production-enforcement-flags"),
    ).toContainText("pilot=NO_GO");
    await expect(page.getByTestId("sc-demo-gate13-pentest-pilot")).toBeVisible();
    await expect(page.getByTestId("sc-demo-gate13-pentest-flags")).toContainText(
      "pen_test_passed_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-gate13-pentest-flags")).toContainText(
      "sca_passed_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-live-authority-spike")).toBeVisible();
    await expect(page.getByTestId("sc-demo-live-authority-flags")).toContainText(
      "sam_uei_verified=false",
    );
    await expect(page.getByTestId("sc-demo-live-authority-flags")).toContainText(
      "submit=false",
    );
    await expect(page.getByTestId("sc-demo-sca-security-loop")).toBeVisible();
    await expect(page.getByTestId("sc-demo-sca-security-flags")).toContainText(
      "sca_passed_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-sca-security-flags")).toContainText(
      "pen_test_passed=false",
    );
    await expect(page.getByTestId("sc-demo-rbac-enforcement")).toBeVisible();
    await expect(page.getByTestId("sc-demo-rbac-enforcement-flags")).toContainText(
      "login_live=false",
    );
    await expect(page.getByTestId("sc-demo-rbac-enforcement-flags")).toContainText(
      "rbac_enforced=true",
    );
    await expect(page.getByTestId("sc-demo-audit-operator-storage")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-audit-operator-storage-flags"),
    ).toContainText("production_storage=false");
    await expect(
      page.getByTestId("sc-demo-audit-operator-storage-flags"),
    ).toContainText("pilot=NO_GO");
    await expect(page.getByTestId("sc-demo-external-pilot-auth")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-external-pilot-auth-flags"),
    ).toContainText("login_live=false");
    await expect(
      page.getByTestId("sc-demo-external-pilot-auth-flags"),
    ).toContainText("invite=draft");
    await expect(page.getByTestId("sc-demo-storage-sca-pentest")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-storage-sca-pentest-flags"),
    ).toContainText("storage_approved=false");
    await expect(
      page.getByTestId("sc-demo-storage-sca-pentest-flags"),
    ).toContainText("pen_test=false");
    await expect(page.getByTestId("sc-demo-oidc-live-path")).toBeVisible();
    await expect(page.getByTestId("sc-demo-oidc-live-path-flags")).toContainText(
      "login_live=false",
    );
    await expect(page.getByTestId("sc-demo-oidc-live-path-flags")).toContainText(
      "configured=false",
    );
    await expect(page.getByTestId("sc-demo-storage-pentest-support")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-storage-pentest-support-flags"),
    ).toContainText("storage_claimed=false");
    await expect(
      page.getByTestId("sc-demo-storage-pentest-support-flags"),
    ).toContainText("pen_test_passed=false");
    await expect(page.getByTestId("sc-demo-auth0-validation")).toBeVisible();
    await expect(page.getByTestId("sc-demo-auth0-validation-flags")).toContainText(
      "login_live=false",
    );
    await expect(page.getByTestId("sc-demo-storage-feature-flags")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-storage-feature-flags-flags"),
    ).toContainText("prod_enabled=false");
    await expect(
      page.getByTestId("sc-demo-storage-feature-flags-flags"),
    ).toContainText("storage_claimed=false");
    await expect(page.getByTestId("sc-demo-auth0-live-validation")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-auth0-live-validation-flags"),
    ).toContainText("login_live=false");
    await expect(page.getByTestId("sc-demo-storage-pilot-gate")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-storage-pilot-gate-flags"),
    ).toContainText("real_prov=false");
    await expect(
      page.getByTestId("sc-demo-storage-pilot-gate-flags"),
    ).toContainText("approval=false");
    await expect(page.getByTestId("sc-demo-auth0-mode-b")).toBeVisible();
    await expect(page.getByTestId("sc-demo-auth0-mode-b-flags")).toContainText(
      "mode=mode_a",
    );
    await expect(page.getByTestId("sc-demo-auth0-mode-b-flags")).toContainText(
      "login_live=false",
    );
    await expect(page.getByTestId("sc-demo-gate20-closeout")).toBeVisible();
    await expect(page.getByTestId("sc-demo-gate20-closeout-flags")).toContainText(
      "pen_test=false",
    );
    await expect(page.getByTestId("sc-demo-gate20-closeout-flags")).toContainText(
      "storage_claimed=false",
    );
    await expect(
      page.getByTestId("sc-demo-auth0-mode-b-live-unlock"),
    ).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-auth0-mode-b-live-unlock-flags"),
    ).toContainText("login_live=false");
    await expect(page.getByTestId("sc-demo-gate21-storage-pilot")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-gate21-storage-pilot-flags"),
    ).toContainText("approval=false");
    await expect(
      page.getByTestId("sc-demo-gate21-storage-pilot-flags"),
    ).toContainText("storage_claimed=false");
    await expect(page.getByTestId("sc-demo-production-metadata")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-production-metadata-flags"),
    ).toContainText("writes=false");
    await expect(
      page.getByTestId("sc-demo-object-storage-signed-url"),
    ).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-object-storage-signed-url-flags"),
    ).toContainText("fake_ui=false");
    await expect(
      page.getByTestId("sc-demo-object-storage-signed-url-flags"),
    ).toContainText("storage_claimed=false");
    await expect(page.getByTestId("sc-demo-customer-data-policy")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-customer-data-policy-flags"),
    ).toContainText("persistence=false");
    await expect(
      page.getByTestId("sc-demo-customer-data-policy-flags"),
    ).toContainText("default=false");
    await expect(page.getByTestId("sc-demo-retention-delete-export")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-retention-delete-export-flags"),
    ).toContainText("final_export=false");
    await expect(
      page.getByTestId("sc-demo-retention-delete-export-flags"),
    ).toContainText("fake_ui=false");
    await expect(page.getByTestId("sc-demo-auth0-login-rbac")).toBeVisible();
    await expect(page.getByTestId("sc-demo-auth0-login-rbac-flags")).toContainText(
      "login_live=false",
    );
    await expect(page.getByTestId("sc-demo-auth0-login-rbac-flags")).toContainText(
      "fake_ui=false",
    );
    await expect(page.getByTestId("sc-demo-session-tenant")).toBeVisible();
    await expect(page.getByTestId("sc-demo-session-tenant-flags")).toContainText(
      "multi_tenant=false",
    );
    await expect(page.getByTestId("sc-demo-session-tenant-flags")).toContainText(
      "fake_ui=false",
    );
    await expect(page.getByTestId("sc-demo-storage-approval-metadata")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-storage-approval-metadata-flags"),
    ).toContainText("storage=false");
    await expect(
      page.getByTestId("sc-demo-storage-approval-metadata-flags"),
    ).toContainText("fake_ui=false");
    await expect(page.getByTestId("sc-demo-object-storage-unlock")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-object-storage-unlock-flags"),
    ).toContainText("signed_live=false");
    await expect(
      page.getByTestId("sc-demo-object-storage-unlock-flags"),
    ).toContainText("fake_ui=false");
    await expect(page.getByTestId("sc-demo-security-attestation")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-security-attestation-flags"),
    ).toContainText("pen_test=false");
    await expect(
      page.getByTestId("sc-demo-security-attestation-flags"),
    ).toContainText("fake_badge=false");
    await expect(page.getByTestId("sc-demo-controlled-pilot-master")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-controlled-pilot-master-flags"),
    ).toContainText("fake_banner=false");
    await expect(
      page.getByTestId("sc-demo-controlled-pilot-master-flags"),
    ).not.toContainText("CONTROLLED_CUSTOMER_GO");
    await expect(page.getByTestId("sc-demo-owner-unlock-packet")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-owner-unlock-packet-flags"),
    ).toContainText("executed=false");
    await expect(
      page.getByTestId("sc-demo-owner-unlock-packet-flags"),
    ).toContainText("fake_mode_b=false");
    await expect(page.getByTestId("sc-demo-cutover-claim-freeze")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-cutover-claim-freeze-flags"),
    ).toContainText("fake_prod=false");
    await expect(
      page.getByTestId("sc-demo-cutover-claim-freeze-flags"),
    ).toContainText("fake_pilot=false");
    await expect(page.getByTestId("sc-demo-mode-b-rehearsal")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-mode-b-rehearsal-flags"),
    ).toContainText("executed=false");
    await expect(
      page.getByTestId("sc-demo-mode-b-rehearsal-flags"),
    ).toContainText("fake_mode_b=false");
    await expect(
      page.getByTestId("sc-demo-mode-b-rehearsal-flags"),
    ).toContainText("synthetic=true");
    await expect(page.getByTestId("sc-demo-dry-run-cutover")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-dry-run-cutover-flags"),
    ).toContainText("first_blocker=auth0_oidc_preflight");
    await expect(
      page.getByTestId("sc-demo-dry-run-cutover-flags"),
    ).toContainText("cutover_executed=false");
    await expect(
      page.getByTestId("sc-demo-dry-run-cutover-flags"),
    ).toContainText("fake=false");
    await expect(page.getByTestId("sc-demo-auth0-real-input")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-auth0-real-input-flags"),
    ).toContainText("login=false");
    await expect(
      page.getByTestId("sc-demo-auth0-real-input-flags"),
    ).toContainText("synthetic_ignored=true");
    await expect(
      page.getByTestId("sc-demo-auth0-real-input-flags"),
    ).toContainText("executed=false");
    await expect(
      page.getByTestId("sc-demo-storage-security-real-input"),
    ).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-storage-security-real-input-flags"),
    ).toContainText("storage=false");
    await expect(
      page.getByTestId("sc-demo-storage-security-real-input-flags"),
    ).toContainText("pentest=false");
    await expect(
      page.getByTestId("sc-demo-storage-security-real-input-flags"),
    ).toContainText("fake=false");
    await expect(page.getByTestId("sc-demo-operator-command-center")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-operator-command-center-flags"),
    ).toContainText("login_live=false");
    await expect(
      page.getByTestId("sc-demo-operator-command-center-flags"),
    ).toContainText("fake_green=false");
    await expect(
      page.getByTestId("sc-demo-operator-command-center-flags"),
    ).not.toContainText("CONTROLLED_CUSTOMER_GO");
    await expect(page.getByTestId("sc-demo-owner-next-action")).toBeVisible();
    await expect(page.getByTestId("sc-demo-final-closeout")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-final-closeout-flags"),
    ).toContainText("fake_prod=false");
    await expect(page.getByTestId("sc-demo-final-allowed-claims")).toBeVisible();
    await expect(page.getByTestId("sc-demo-final-forbidden-claims")).toBeVisible();
    await expect(page.getByTestId("sc-demo-buyer-trust-views")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-trust-view-buyer_landing"),
    ).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-trust-view-controlled_pilot_go_nogo"),
    ).toBeVisible();
    await expect(page.getByTestId("sc-demo-live-authority-execution")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-live-authority-execution-flags"),
    ).toContainText("can_submit=false");
    await expect(
      page.getByTestId("sc-demo-live-authority-execution-flags"),
    ).toContainText("eligibility=false");
    await expect(page.getByTestId("sc-demo-live-source-coverage")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-live-source-coverage-flags"),
    ).toContainText("top15=false");
    await expect(
      page.getByTestId("sc-demo-live-source-coverage-flags"),
    ).toContainText("broad=false");
    await expect(page.getByTestId("sc-demo-pilot-org-onboarding")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-pilot-org-onboarding-flags"),
    ).toContainText("invite_sent=false");
    await expect(page.getByTestId("sc-demo-support-triage")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-support-triage-flags"),
    ).toContainText("slack_sent=false");
    await expect(page.getByTestId("sc-demo-gate32-source-freshness")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-gate32-source-freshness-flags"),
    ).toContainText("live=false");
    await expect(page.getByTestId("sc-demo-gate32-observability")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-gate32-observability-flags"),
    ).toContainText("alert_sent=false");
    await expect(page.getByTestId("sc-demo-backup-restore")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-backup-restore-flags"),
    ).toContainText("prod_restore=false");
    await expect(page.getByTestId("sc-demo-launch-packet")).toBeVisible();
    await expect(
      page.getByTestId("sc-demo-launch-packet-flags"),
    ).not.toContainText("CONTROLLED_CUSTOMER_GO");
    await expect(page.getByTestId("sc-demo-nofo-proposal-honesty")).toContainText(
      "NOT_SUPPORTED",
    );

    await expect(page.getByTestId("sc-demo-banner")).toBeVisible();
    await expect(page.getByTestId("sc-demo-flags")).toContainText(
      "live_ingestion=false",
    );
    await expect(page.getByTestId("sc-demo-flags")).toContainText(
      "final_eligibility_claim_allowed=false",
    );
    await expect(page.getByTestId("sc-demo-flags")).toContainText(
      "source_activation=false",
    );

    await expect(page.getByTestId("sc-demo-what-nf-did")).toContainText(
      "What NativeForge found",
    );
    await expect(page.getByTestId("sc-demo-attention")).toContainText(
      "What is uncertain / needs your attention",
    );
    await expect(page.getByTestId("sc-demo-next-actions")).toContainText(
      "What to do next",
    );

    const profiles = page.getByTestId("sc-demo-profiles");
    await expect(profiles).toContainText("profiles=10");

    const opps = page.getByTestId("sc-demo-opportunities");
    await expect(opps).toContainText("south_carolina=");
    await expect(opps).toContainText("federal=");

    await expect(page.getByTestId("sc-demo-combined-summary")).toContainText(
      "human_review=",
    );
    await expect(page.getByTestId("sc-demo-missing-data")).toContainText(
      "hidden_missing_data=false",
    );
    await expect(page.getByTestId("sc-demo-provenance")).toContainText(
      "notes_visible=true",
    );
    await expect(page.getByTestId("sc-demo-provenance")).toContainText(
      "demo_real_isolation=visible",
    );

    const table = page.getByTestId("sc-demo-review-table");
    await expect(table).toBeVisible();
    await expect(table).toContainText("south_carolina");
    await expect(table).toContainText("federal");
    await expect(table).toContainText("true"); // human review
    await expect(table).toContainText("false"); // final claim

    const nofo = page.getByTestId("sc-demo-nofo-showcase");
    await expect(nofo).toBeVisible();
    await expect(page.getByTestId("sc-demo-nofo-showcase-flags")).toContainText(
      "live_ingest_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-nofo-showcase-flags")).toContainText(
      "nofo_pdf_extraction_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-nofo-showcase-flags")).toContainText(
      "proposal_drafting_claimed=false",
    );
    await expect(page.getByTestId("sc-demo-nofo-buyer-sections")).toContainText(
      "What NativeForge found",
    );
    await expect(page.getByTestId("sc-demo-nofo-buyer-sections")).toContainText(
      "What needs human review",
    );

    // At least one SC and one federal intelligence card
    await expect(
      page.locator('[data-testid^="sc-demo-nofo-card-"][data-source-layer="sc_state"]'),
    ).toHaveCount(1, { timeout: 5000 });
    await expect(
      page.locator('[data-testid^="sc-demo-nofo-card-"][data-source-layer="federal"]'),
    ).not.toHaveCount(0);

    const firstCard = page.locator('[data-testid^="sc-demo-nofo-card-"]').first();
    await expect(firstCard).toContainText("What NativeForge found");
    await expect(firstCard).toContainText("What is missing");
    await expect(firstCard).toContainText("Application plan skeleton");
    await expect(firstCard).toContainText("Evidence / provenance");
    await expect(firstCard).toContainText("not_supported");
  });
});
