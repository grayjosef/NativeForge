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
      provenance_summary: Record<string, unknown>;
      combined_ordering_sample: Array<Record<string, unknown>>;
      next_checks_sample: string[];
    };
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
