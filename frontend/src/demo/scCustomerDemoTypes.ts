/** Types for SC Monday customer demo bridge payload (read-only). */

export type ScCustomerDemoRow = {
  profile_id: string;
  recognition_type: string;
  grant_id: string;
  opportunity_title: string;
  funding_geography: string;
  data_label: string;
  live_ingest_not_claimed: boolean;
  classification_label: string;
  match_readiness_label: string;
  discoverability: string;
  confidence: string;
  missing_data: string[];
  blockers: string[];
  operator_next_check: string[];
  provenance_evidence_notes: string[];
  human_review_required: boolean;
  final_eligibility_claim_allowed: boolean;
  confirm_active_round?: boolean;
  excluded_from_match_set?: boolean;
};

export type ScCustomerDemoPayload = {
  schema_version: string;
  title: string;
  demo_route_path: string;
  demo_dev_only: boolean;
  offline_only: boolean;
  read_only_advisory: boolean;
  live_ingestion: boolean;
  source_activation: boolean;
  external_urls_used: boolean;
  auth_required: boolean;
  final_eligibility_claim_allowed: boolean;
  pack_id: string;
  capture_date: string;
  content_digest: string;
  claim_matrix: Record<string, unknown>;
  profiles: {
    profile_count: number;
    federal_recognized_count: number;
    state_only_count: number;
    fixture_keys: string[];
  };
  opportunities: {
    total: number;
    south_carolina_count: number;
    federal_count: number;
    by_data_label: Record<string, number>;
    opportunity_ids: string[];
  };
  classify_match: Record<string, unknown>;
  combined_summary: {
    row_count: number;
    south_carolina_row_count: number;
    federal_row_count: number;
    human_review_required_count: number;
    confidence_distribution: Record<string, number>;
  };
  missing_data_summary: {
    rows_with_missing_data: number;
    hidden_missing_data: boolean;
  };
  provenance_evidence_summary: {
    notes_visible: boolean;
    pack_evidence_required: boolean;
  };
  what_nativeforge_did: string[];
  what_requires_attention: string[];
  why_this_matters?: string[];
  workload_reduction_statement?: string;
  next_actions: string[];
  rows: ScCustomerDemoRow[];
  row_sample_note?: string;
  ui_flags: {
    show_activation_controls: boolean;
    show_submit_controls: boolean;
    advisory_banner: string;
  };
  buyer_demo?: {
    schema_version: string;
    demo_route_path: string;
    opening_line: string;
    closing_line: string;
    required_story_labels: string[];
    allowed_claims: string[];
    forbidden_claims: string[];
    trust_cues_required?: string[];
    claim_matrix?: Record<string, string>;
    live_ingest_claimed: boolean;
    nofo_pdf_extraction_claimed: boolean;
    proposal_drafting_claimed: boolean;
    final_eligibility_claim_allowed: boolean;
  };
  opportunity_engine?: {
    schema_version: string;
    campaign_block: number;
    block_name: string;
    live_ingest_claimed: boolean;
    source_activation_claimed: boolean;
    final_eligibility_claim_allowed: boolean;
    buyer_summary: string[];
    sc_state_adapter: Record<string, unknown>;
    combined_workflow: {
      counts: Record<string, number>;
      organization_geography_filters_federal: boolean;
      missing_data_summary: Record<string, unknown>;
      human_review: Record<string, unknown>;
      eligibility_readiness_handoff: Record<string, unknown>;
      eligibility_evidence_handoff?: {
        pair_count?: number;
        federal_pairs_visible?: boolean;
        final_eligibility_claimed?: boolean;
        scoring_math_changed?: boolean;
        human_review_required?: boolean;
        sample_pairs?: Array<Record<string, unknown>>;
      };
      provenance_summary: Record<string, unknown>;
      combined_ordering_sample: Array<Record<string, unknown>>;
      next_checks_sample: string[];
    };
  };
  pursuit_workspace?: {
    schema_version: string;
    campaign_block: number;
    title: string;
    workspace_count: number;
    showcase_opportunity_ids: string[];
    final_submission_allowed: boolean;
    submission_ready_claimed: boolean;
    proposal_drafting_claimed: boolean;
    live_ingest_claimed: boolean;
    scoring_math_changed: boolean;
    buyer_summary: string[];
    workspaces: Array<{
      workspace: {
        pursuit_workspace_id: string;
        opportunity_id: string;
        organization_profile_id: string;
        opportunity_source_layer: string;
        readiness_status: string;
        pursuit_status: string;
        missing_information_summary: string[];
        human_review_required: boolean;
        operator_next_actions: string[];
        customer_next_actions: string[];
        why_worth_review?: string;
        final_submission_allowed: boolean;
        submission_ready_claimed: boolean;
        proposal_drafting_claimed: boolean;
        not_submission_ready_label?: boolean;
        what_nativeforge_prebuilt?: string[];
        what_customer_must_provide?: string[];
      };
      evidence_binder: {
        item_count: number;
        missing_or_needs_confirmation_ids: string[];
        human_review_required: boolean;
        proposal_drafting_claimed: boolean;
        submission_ready_claimed: boolean;
      };
      readiness: {
        readiness_status: string;
        not_submission_ready: boolean;
        operator_next_actions: string[];
        customer_next_actions: string[];
      };
      application_plan_summary?: Record<string, unknown>;
      nofo_intelligence_present?: boolean;
    }>;
  };
  application_plan_workspace?: {
    schema_version: string;
    campaign_block: number;
    title: string;
    workspace_count: number;
    showcase_opportunity_ids: string[];
    submission_allowed: boolean;
    submission_ready_claimed: boolean;
    proposal_drafting_claimed: boolean;
    application_complete_claimed: boolean;
    nofo_pdf_extraction_claimed: boolean;
    live_ingest_claimed: boolean;
    scoring_math_changed: boolean;
    buyer_summary: string[];
    workspaces: Array<{
      application_workspace: {
        application_workspace_id: string;
        pursuit_workspace_id: string;
        opportunity_id: string;
        organization_profile_id: string;
        section_count: number;
        item_count: number;
        checklist_sections: Array<{ section_id: string; title: string }>;
        checklist_items: Array<{
          item_id: string;
          section_id: string;
          label: string;
          item_status: string;
          what_nativeforge_knows?: string;
          what_is_missing?: string[];
          next_action?: string;
          required_human_review?: boolean;
          unsupported_claim_guard?: boolean;
        }>;
        submission_allowed: boolean;
        why_submission_not_allowed?: string;
      };
      questionnaire: {
        question_count: number;
        questions: Array<{
          question_id: string;
          group: string;
          prompt: string;
          answer: null;
        }>;
        customer_next_actions?: string[];
        operator_next_actions?: string[];
      };
      opportunity_id: string;
      organization_profile_id: string;
      opportunity_source_layer: string;
      incomplete_item_count: number;
      question_count: number;
      what_nativeforge_knows?: string[];
      what_customer_must_provide?: string[];
      what_requires_human_review?: string[];
      why_submission_not_allowed?: string;
      unsupported_claims?: string[];
      submission_allowed: boolean;
      proposal_drafting_claimed: boolean;
      application_complete_claimed: boolean;
    }>;
  };
  intake_approval_workspace?: {
    schema_version: string;
    campaign_block: number;
    title: string;
    workspace_count: number;
    showcase_opportunity_ids: string[];
    binary_upload_persistence_supported: boolean;
    binary_upload_persistence_claimed: boolean;
    approval_persistence_supported: boolean;
    approval_persistence_claimed: boolean;
    submission_allowed: boolean;
    submission_ready_claimed: boolean;
    proposal_drafting_claimed: boolean;
    package_readiness_unlocked: boolean;
    live_ingest_claimed: boolean;
    scoring_math_changed: boolean;
    buyer_summary: string[];
    workspaces: Array<{
      application_workspace_id: string;
      pursuit_workspace_id: string;
      opportunity_id: string;
      organization_profile_id: string;
      opportunity_source_layer: string;
      intake_item_count: number;
      approval_count: number;
      open_approval_count: number;
      customer_must_provide: string[];
      operator_must_verify: string[];
      required_reviewer_roles: string[];
      what_remains_blocked: string[];
      why_package_not_ready: string;
      binary_upload_persistence_supported: boolean;
      binary_upload_persistence_claimed: boolean;
      approval_persistence_supported: boolean;
      approval_persistence_claimed: boolean;
      submission_allowed: boolean;
      submission_ready_claimed: boolean;
      proposal_drafting_claimed: boolean;
      package_readiness_unlocked: boolean;
      intake_plan: {
        intake_items: Array<{
          intake_item_id: string;
          intake_type: string;
          item_label: string;
          current_status: string;
          accepted_evidence_types: string[];
          customer_action_required: boolean;
          operator_action_required: boolean;
          approval_status: string;
          why_it_matters?: string;
          what_remains_blocked?: string;
          source_checklist_section?: string;
        }>;
      };
      approval_workflow: {
        approvals: Array<{
          approval_id: string;
          approval_type: string;
          required_reviewer_role: string;
          approval_status: string;
          cannot_unlock_reason?: string;
        }>;
      };
    }>;
  };
  nofo_showcase?: {
    schema_version: string;
    title: string;
    pack_id: string;
    selected_count: number;
    sc_selected_count: number;
    federal_selected_count: number;
    live_ingest_claimed: boolean;
    nofo_pdf_extraction_claimed: boolean;
    proposal_drafting_claimed: boolean;
    buyer_sections: string[];
    cards: Array<{
      opportunity_id: string;
      source_layer: string;
      source_name?: string | null;
      title?: string | null;
      data_mode?: string | null;
      live_ingest_claimed: boolean;
      human_review_required: boolean;
      field_status_counts: Record<string, number>;
      unresolved_fields: string[];
      what_nativeforge_found: Record<string, unknown>;
      what_this_means?: string | null;
      what_is_missing: Array<Record<string, unknown>>;
      what_needs_human_review: string[];
      what_to_do_next: string[];
      application_plan: {
        recommendation_label?: string;
        application_checklist?: Array<Record<string, unknown>>;
        narrative_section_scaffold?: Array<Record<string, unknown>>;
        forms_checklist?: Array<Record<string, unknown>>;
        attachment_checklist?: Array<Record<string, unknown>>;
        missing_information_questions?: Array<Record<string, unknown>>;
        completeness?: Record<string, unknown>;
        proposal_drafting_claimed: boolean;
        nofo_pdf_extraction_claimed: boolean;
      };
      evidence_provenance: Record<string, unknown>;
      limitations: string[];
    }>;
  };
};
