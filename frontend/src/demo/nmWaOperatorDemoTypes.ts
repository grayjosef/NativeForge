/** Types for NM/WA operator demo bridge payload (read-only). */

export type NmWaOperatorDemoRow = {
  profile_id: string;
  state_cohort: string;
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
};

export type NmWaOperatorDemoPayload = {
  schema_version: string;
  title: string;
  demo_dev_only: boolean;
  offline_only: boolean;
  read_only_advisory: boolean;
  live_ingestion: boolean;
  source_activation: boolean;
  external_urls_used: boolean;
  auth_required: boolean;
  final_eligibility_claim_allowed: boolean;
  prior_offline_smoke_run_id: string;
  content_digest: string;
  nm_summary: {
    profile_count: number;
    expected: number;
    classify_match_profiles: number;
    operator_report_rows: number;
  };
  wa_summary: {
    profile_count: number;
    expected: number;
    classify_match_profiles: number;
    operator_report_rows: number;
  };
  combined_summary: {
    combined_profile_count: number;
    combined_review_needed_count: number;
    combined_missing_data_count: number;
    confidence_distribution: Record<string, number>;
  };
  missing_data_summary: {
    nm_missing_evidence_categories: Record<string, number>;
    wa_missing_evidence_categories: Record<string, number>;
    combined_missing_data_count: number;
    hidden_missing_data: boolean;
  };
  provenance_evidence_summary: {
    combined_evidence_provenance_summary: Record<string, number>;
    notes_visible: boolean;
  };
  operator_next_check_summary: {
    combined_review_needed_count: number;
    rows_with_next_checks: number;
    human_review_required_count: number;
  };
  rows: NmWaOperatorDemoRow[];
  ui_flags: {
    show_activation_controls: boolean;
    show_submit_controls: boolean;
    advisory_banner: string;
  };
};
