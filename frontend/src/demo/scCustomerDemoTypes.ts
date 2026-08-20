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
  next_actions: string[];
  rows: ScCustomerDemoRow[];
  row_sample_note?: string;
  ui_flags: {
    show_activation_controls: boolean;
    show_submit_controls: boolean;
    advisory_banner: string;
  };
};
