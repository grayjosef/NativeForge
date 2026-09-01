#!/usr/bin/env bash
# Gate 84C — prove the recurring gate `-k` selection still reaches the tests
# that must never fail invisibly.
#
# Gate 84B measured the full suite for the first time and found six failing
# tests behind a regression number that had read "0 failed" for several gates.
# All six were deterministic failures; the recurring scoped `-k` simply never
# selected them.
#
# This script does not demand 100% selection - the broad expression is a
# deliberate subset and running everything takes ~35 minutes. It demands that
# the tests we know can rot silently are inside it.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

# shellcheck disable=SC1091
source .venv/bin/activate

# The broad expression used by the recurring gate validation. Keep in step with
# the gate prompts; a keyword dropped here is a keyword dropped there.
#
# `fit_dimension`, `readiness` and `gate37` were added by Gate 84C. Without them
# the expression did not reach four of the six critical tests below - which is
# precisely how those tests failed unnoticed for several gates.
#
# `deadline`, `normalization` and `freshness` were added by Gate 86. Its 71 new
# tests landed in a module whose name shares no keyword with this expression,
# so only 6 of them were selected - the same failure this guard exists to catch,
# caught here by the guard rather than several gates later by accident.
#
# `awarded`, `pursuit`, `reporting`, `lifecycle`, `attachment` and `extraction`
# were added by Gate 91, for the same reason and caught the same way: 3 of its
# 67 tests were selected. Twice now the guard has caught a new module falling
# outside the expression on the gate that introduced it, which is the intended
# cadence.
#
# `network`, `http`, `robots`, `chokepoint`, `user_agent` and `guard` were added
# by Gate 94 — the fourth time. Two of its critical tests
# (robots-fails-closed, does-not-route-around-gate77b) shared no keyword with
# the expression, so the guard failed on the gate that introduced them rather
# than several gates later by accident.
#
# `payload`, `redaction`, `promotion`, `evidence`, `secret` and `store` were
# added by Gate 95, pre-emptively this time: its module name shares only
# `raw_payload` with anything here, and the pattern is now established
# enough to widen the expression when a gate lands rather than after it
# fails.
#
# `migration`, `alembic`, `schema` and `repository` were added by Gate 96,
# also pre-emptively. Its critical tests are about a DB migration, and no
# keyword here reached that vocabulary before.
#
# `body_store`, `object_store`, `settings`, `credential` and `s3` were added
# by Gate 97. Its module name shares `payload` with Gate 95, but its
# critical tests are about settings detection and credential handling,
# which no keyword reached.
#
# `scheduler`, `schedule`, `circuit`, `breaker`, `monitor` and `check_run`
# were added by Gate 98. `source` already collects the module, but the four
# facts this gate holds - no runtime, no worker, nothing monitoring, not
# ready - live in tests whose names are about scheduling rather than sources,
# and a rename inside the file would have dropped them silently.
#
# `job`, `queue`, `dry_run`, `idempotency` and `runtime` were added by Gate 99.
# Its critical tests are about a job queue and a runtime mode; `scheduler`
# reaches the module but not the test names, and the one test that holds
# `live_jobs_created` at zero is named for the queue rather than the scheduler.
#
# `worker`, `broker` and `dependency` were added by Gate 100. Its critical
# tests are about a background worker that does not exist and a broker nobody
# has chosen; `dry_run` and `runtime` reach the module, but the tests holding
# `production_worker_live` and `background_worker_available` at false are named
# for the worker, which no earlier keyword reached.
#
# `backend`, `persistent`, `systemd`, `loopback` and `lifespan` were added by
# Gate 101. Its critical tests are about a backend process that does not run
# and a unit template that must bind loopback only; `runtime` and `health`
# reach the module, but the test proving the template never binds a public
# interface is named for systemd and loopback, which nothing else reached.
#
# `proof`, `install` and `attach` were added by Gate 102. Its critical tests
# are about an observation that must carry a pid and a passing healthcheck,
# and an attach point with nothing attached to it; `backend` and `lifespan`
# reach the module, but the tests holding the five proof requirements are
# named for the proof, which no earlier keyword reached.
#
# `tenant`, `entitlement`, `allowability`, `fixture` and `recognition` were
# added by Gate 103 - the first product-contract gate. Its critical tests are
# about tenant facts that must stay unknown and a self-assessment that must
# stay capped; `eligibility` and `source` reach parts of the module, but the
# tests holding the NativeForge allowability cap and the no-real-Tribe rule
# are named for the tenant and the fixture, which nothing else reached.
#
# `digest`, `snapshot`, `suppression` and `nofo` were added by Gate 104.
# `tenant` reaches the module, but the tests holding the four rules that keep
# a digest honest - no email, no deletion, first_seen without a baseline, and
# deadline changes gated on provenance - are named for the digest, the
# snapshot and the suppression, which nothing earlier reached. `nofo` also
# picks up the older notice tests, which is a bonus rather than the reason.
#
# `bridge`, `shadow` and `classification` were added by Gate 105. `tribal`,
# `eligibility` and `corpus` already reach the module, but the tests that
# matter here are about a canonical name being re-shadowed and a classifier
# under-detecting against it - named for the bridge and the shadow, which
# nothing else reached. Under-detection is the failure this gate fixed, so the
# test that proves the fix is load-bearing is selected explicitly rather than
# left to a keyword.
#
# `attestation`, `regeneration` and `drift` were added by Gate 106. `corpus`
# and `fixture` reach the module, but the tests that matter are about a
# fixture that must NOT be written and a refusal that must be derived rather
# than declared - named for the attestation and the regeneration, which
# nothing earlier reached.
#
# `honest`, `empty` and `unknown` were added by Gate 107. The tests that matter
# are about what derivation must NOT write - a synopsis into eligibility text,
# a negative nobody earned - and they are named for the honesty and the
# unknown, which no earlier keyword reached.
#
# `obligation` and `calendar` were added by Gate 108. `awarded`, `proof` and
# `reporting` already reach the module - deliberately not re-added - but the
# tests that matter are about what the awarded workspace must refuse: a
# projection becoming a duty, an estimate becoming a countdown. Those are named
# for the obligation and the calendar, which no earlier keyword reached.
#
# `binding` and `cross_tenant` were added by Gate 109. `tenant`, `identity` and
# `org` already reach the module, but the tests that matter are about two
# identity spaces that must never be silently equated - named for the binding
# and the cross-tenant risk, which no earlier keyword reached.
#
# `canonicalization` and `rls` were added by Gate 110. `identity`, `org` and
# `binding` already reach the module, but the tests that matter are about which
# identity the database actually enforces on and what may never be written
# under a label - named for the canonicalization and the RLS authority, which
# no earlier keyword reached.
#
# `principal`, `binder` and `verified_org` were added by Gate 111. `auth`,
# `login` and `oidc` already reach the module - deliberately not re-added - but
# the tests that matter are about what authentication does NOT establish:
# named for the principal and the binder, which no earlier keyword reached.
#
# `resolution`, `membership` and `profile_id` were added by Gate 112. `oidc`
# and `org` already reach the module, but the tests that matter are about a
# claim stopping one identifier short of the RLS authority - named for the
# resolution and the profile id, which no earlier keyword reached.
GATE_K='order_independence or recognition_requirement_coverage_expansion or sprint348_nf15_closeout or fit_dimension or readiness or gate37 or audit_state or audit_refs or demo_payload or negative_intelligence or sc_customer_demo or notice_ingestion or notice_artifact or html_notice or pdf_notice or nofo or notice or amendment or eligibility_exclusion or excluded_by_evidence or funding_lane or south_carolina or sc_state or sc_source or sc_native or state_recognized or federally_recognized or grants_gov or federal or corpus or fixture or source or opportunity or discovery or stale or duplicate or native or capability or audit or invite or approval or backup or restore or storage or postgres or rls or membership or identity or oidc or auth or token or tenant or rbac or role or authority or claim or demo or deadline or normalization or freshness or awarded or pursuit or reporting or lifecycle or attachment or extraction or network or http or robots or chokepoint or user_agent or guard or payload or redaction or promotion or evidence or secret or store or migration or alembic or schema or repository or body_store or object_store or settings or credential or s3 or scheduler or schedule or circuit or breaker or monitor or check_run or job or queue or dry_run or idempotency or runtime or worker or broker or dependency or backend or persistent or systemd or loopback or lifespan or proof or install or attach or tenant or entitlement or allowability or fixture or recognition or digest or snapshot or suppression or nofo or bridge or shadow or classification or attestation or regeneration or drift or honest or empty or unknown or obligation or calendar or binding or cross_tenant or canonicalization or rls or principal or binder or verified_org or resolution or membership or profile_id or binding_store or provenance or persistence_capability or spine or activation or role_mapping or session_policy or auth_route or enforcement or pkce or redirect_flow or session_format or state_store or session or replay or signing_key or authorization_url or redirect_state or live_redirect or binding_repository or verified_binding or workflow or preflight or provider_readiness or runbook or activation_blocker or dev_header or org_context or replacement or tenant_profile or operating_state or recognition or awarded_grant or award_status or active_obligation or projected_burden or lineage or archive or award_requirement or requirement_source or due_date or proof or submission or document_reference or proof_event or audit_trail or supersede or retention or event_type or event_status or document_store or object_store or object_key or legal_hold or customer_visible or metadata or callback_url or callback_route or public_origin or derived_callback or config_schema or operating_shell or truth_label or demo_live or auth_settings or secret_safe or api_runtime or discovery or well_known or endpoint or google or provider_metadata or conventional or reliability or tunnel or verifier or talk_track or hermetic or restart_policy or live_stack or pkce or verifier_encryption or token_exchange or state_store or minting or one_time or replay_refused'

# Tests that have already rotted invisibly once, plus the few whose silent loss
# would be worst. Every one is a node id, so a rename shows up here as a failure
# rather than as silent loss of coverage.
CRITICAL=(
  "tests/test_recognition_requirement_coverage_expansion.py::test_unknown_count_drops_ac1"
  "tests/test_sprint348_nf15_closeout.py::test_nf15_gate_and_closeout"
  "tests/test_sprint197_eligibility_fit_assessment_dimension_vocabulary.py::test_fit_dimensions_are_the_declared_set"
  "tests/test_sprint222_matching_readiness_readiness_evaluator.py::test_incomplete_profile_blocked_readiness"
  "tests/test_sprint4202_gate37_production_grade_hardening.py::test_busy_preview_port_blocks_serve"
  "tests/test_sprint4202_gate37_production_grade_hardening.py::test_verifier_fail_when_server_down"
  # Gate 85. Not yet rotted, but these are the two whose quiet disappearance
  # would be hardest to notice and most expensive: one holds the federally
  # recognized / state recognized split apart, the other keeps the baseline
  # from claiming a source is monitored.
  "tests/test_gate85_discovery_baseline_x.py::test_recognition_tiers_are_not_collapsed_into_one_answer"
  "tests/test_gate85_discovery_baseline_x.py::test_no_source_is_monitored"
  # Gate 86. The two that keep normalization from turning into fabrication:
  # one bounds freshness to records that have both a date and a check, the
  # other keeps the raw deadline count from moving.
  "tests/test_gate86_deadline_normalization.py::test_freshness_requires_both_a_normalized_date_and_a_check"
  "tests/test_gate86_deadline_normalization.py::test_raw_deadline_count_is_preserved"
  # Gate 91. The rule that a grant may not become an awarded record by
  # backend assignment - GrantPipelineStage.awarded is still an assignable
  # enum member, so this is the test most likely to matter and most likely
  # to be quietly lost in a refactor.
  "tests/test_gate91_awarded_vs_pursuit_reporting_parser.py::test_backend_enum_assignment_alone_is_not_a_valid_transition"
  "tests/test_gate91_awarded_vs_pursuit_reporting_parser.py::test_projected_and_active_are_structurally_distinct"
  # Gate 92. Three whose quiet loss would each be expensive in a different
  # way: the recall set is the product's whole reason for existing (a filter
  # on 07|11 alone looks clean and silently drops tribally-eligible money);
  # the Grants.gov attribution is a legal build requirement that must survive
  # verbatim; and the geography gate is the one place where "unknown" must
  # mean withheld rather than shown.
  "tests/test_gate92_v2_source_registry_spine.py::test_unrestricted_and_others_stay_in_the_recall_set"
  "tests/test_gate92_v2_source_registry_spine.py::test_grants_gov_attribution_is_verbatim"
  "tests/test_gate92_v2_source_registry_spine.py::test_geography_gate_denies_by_default"
  # Gate 93. The three that keep Phase 1 activation blocked: the preflight
  # default, the rule that attribution in a docs file does not count, and
  # the check that the notice actually reaches the runtime payload a
  # customer receives.
  "tests/test_gate93_phase1_collector_readiness.py::test_preflight_defaults_to_blocked"
  "tests/test_gate93_phase1_collector_readiness.py::test_attribution_in_docs_only_does_not_satisfy"
  "tests/test_gate93_phase1_collector_readiness.py::test_attribution_is_present_in_the_live_trust_manifest"
  # Gate 94. The three that keep the codebase-wide claim true: the scan
  # that fails when a seventh network call site appears, the robots
  # fail-closed behaviour that was fail-open until this gate, and the
  # proof that the new guard does not route around Gate 77B.
  "tests/test_gate94_global_http_chokepoint.py::test_source_scan_has_zero_unapproved_call_sites"
  "tests/test_gate94_global_http_chokepoint.py::test_polite_http_get_robots_fails_closed_on_timeout"
  "tests/test_gate94_global_http_chokepoint.py::test_gate94_guard_does_not_route_around_gate77b"
  # Gate 95. Three whose quiet loss would each be expensive: the store
  # refusing to write by default, the scanner refusing to print a secret
  # value, and the rule that a local store is never reported as production
  # storage.
  "tests/test_gate95_raw_payload_store.py::test_local_store_refuses_writes_by_default"
  "tests/test_gate95_raw_payload_store.py::test_jwt_is_detected_without_printing_the_value"
  "tests/test_gate95_raw_payload_store.py::test_preflight_never_claims_production_storage"
  # Gate 96. The three that hold the gate's whole distinction: a metadata
  # table is not production storage, the derived availability flag cannot
  # be faked, and a live collection may not run on a local-only store.
  "tests/test_gate96_production_raw_payload_storage.py::test_a_metadata_table_alone_is_not_production_storage"
  "tests/test_gate96_production_raw_payload_storage.py::test_local_store_does_not_count_toward_production"
  "tests/test_gate96_production_raw_payload_storage.py::test_live_collection_requires_the_production_store"
  # Gate 97. Three that hold the credential and configuration boundary: a
  # placeholder is not configuration, a secret never reaches a readiness
  # output, and configuring storage starts nothing.
  "tests/test_gate97_object_body_store.py::test_secret_never_appears_in_readiness_output"
  "tests/test_gate97_object_body_store.py::test_artifacts_hold_no_secret_even_when_configured"
  "tests/test_gate97_object_body_store.py::test_collectors_remain_inactive_even_when_fully_configured"

  # Gate 98. Five that hold the scheduler boundary: the four required facts
  # read false, the runtime detection is real rather than a hardcoded false,
  # a declared scheduler policy does not buy scheduling, an unrecognised
  # manual override blocks instead of permitting, and a missing schedule is a
  # question for a person rather than a licence to run now.
  "tests/test_gate98_scheduler_circuit_breaker.py::test_the_three_facts_that_must_stay_false_are_false"
  "tests/test_gate98_scheduler_circuit_breaker.py::test_the_runtime_detection_is_live_not_a_hardcoded_false"
  "tests/test_gate98_scheduler_circuit_breaker.py::test_a_cleared_source_may_activate_but_may_not_be_scheduled"
  "tests/test_gate98_scheduler_circuit_breaker.py::test_an_unrecognised_override_blocks_rather_than_reads_as_no_override"
  "tests/test_gate98_scheduler_circuit_breaker.py::test_a_missing_due_date_is_unknown_not_immediate"

  # Gate 99. Five that hold the dry-run boundary: no live job is ever created,
  # live collection stays refused even with every precondition satisfied, a
  # dry-run runtime is not monitoring, the CLI refuses rather than does live
  # work, and Gate 98F is unaffected - a dry-run runtime makes no source
  # schedulable.
  "tests/test_gate99_scheduler_runtime_dry_run.py::test_live_jobs_created_is_zero"
  "tests/test_gate99_scheduler_runtime_dry_run.py::test_live_collection_is_blocked_by_default"
  "tests/test_gate99_scheduler_runtime_dry_run.py::test_the_three_facts_gate_99_may_not_change_remain_false"
  "tests/test_gate99_scheduler_runtime_dry_run.py::test_the_cli_refuses_when_a_live_job_appears"
  "tests/test_gate99_scheduler_runtime_dry_run.py::test_a_dry_run_runtime_does_not_make_any_source_schedulable"

  # Gate 100. Five that hold the worker boundary: no production worker is
  # live, no background worker exists, the dry-run worker refuses live jobs
  # and never executes one, and the CLI refuses rather than does live work.
  "tests/test_gate100_background_worker_runtime.py::test_production_worker_live_remains_false"
  "tests/test_gate100_background_worker_runtime.py::test_background_worker_available_remains_false"
  "tests/test_gate100_background_worker_runtime.py::test_the_worker_refuses_live_collection_jobs"
  "tests/test_gate100_background_worker_runtime.py::test_the_worker_executes_nothing"
  "tests/test_gate100_background_worker_runtime.py::test_the_cli_exits_nonzero_for_a_live_job"

  # Gate 101. Five that hold the backend boundary: the unit template never
  # binds a public interface (the one mistake here that would reach the running
  # tunnel), a smoke script is not a backend, live needs process proof, health
  # never claims production readiness, and readiness keeps every NO_GO.
  "tests/test_gate101_persistent_backend_process.py::test_the_unit_template_binds_loopback_only"
  "tests/test_gate101_persistent_backend_process.py::test_smoke_script_only_does_not_count_as_a_persistent_backend"
  "tests/test_gate101_persistent_backend_process.py::test_persistent_backend_live_remains_false_without_process_proof"
  "tests/test_gate101_persistent_backend_process.py::test_health_never_claims_production_readiness"
  "tests/test_gate101_persistent_backend_process.py::test_readiness_preserves_the_no_go_statuses"

  # Gate 102. Five that hold the proof and attach boundary: live needs a
  # passing healthcheck and a pid, the hook starts no scheduler and no
  # collectors, and the unit is started but never enabled.
  "tests/test_gate102_backend_unit_lifespan.py::test_a_proof_requires_a_passing_healthcheck"
  "tests/test_gate102_backend_unit_lifespan.py::test_a_proof_requires_a_pid"
  "tests/test_gate102_backend_unit_lifespan.py::test_the_hook_starts_no_scheduler"
  "tests/test_gate102_backend_unit_lifespan.py::test_the_hook_starts_no_collectors"
  "tests/test_gate102_backend_unit_lifespan.py::test_the_unit_is_enabled_only_under_a_recorded_approval"

  # Gate 103. Five that hold the tenant truth boundary: recognition is never
  # inferred, no demo fixture names a real Tribe, SC priority is per-tenant,
  # the NativeForge allowability self-assessment is capped, and enabling the
  # watchlist never implies monitoring.
  "tests/test_gate103_tenant_beta_feature_contract.py::test_recognition_status_is_never_inferred"
  "tests/test_gate103_tenant_beta_feature_contract.py::test_no_demo_fixture_names_a_real_tribe"
  "tests/test_gate103_tenant_beta_feature_contract.py::test_a_non_sc_tenant_gets_no_sc_tier"
  "tests/test_gate103_tenant_beta_feature_contract.py::test_nativeforge_self_assessment_is_capped_at_human_review"
  "tests/test_gate103_tenant_beta_feature_contract.py::test_enabling_the_watchlist_does_not_imply_monitoring"

  # Gate 104. Five that keep the digest honest: no email leaves the building,
  # suppression deletes nothing and stays tenant-scoped, a first run says
  # first_seen rather than new, and a deadline change needs verified
  # provenance on both sides rather than two dates that differ.
  "tests/test_gate104_tenant_nofo_digest_suppression.py::test_the_digest_is_preview_only"
  "tests/test_gate104_tenant_nofo_digest_suppression.py::test_suppression_never_deletes_anything"
  "tests/test_gate104_tenant_nofo_digest_suppression.py::test_suppression_is_tenant_specific"
  "tests/test_gate104_tenant_nofo_digest_suppression.py::test_no_previous_snapshot_means_first_seen_not_new"
  "tests/test_gate104_tenant_nofo_digest_suppression.py::test_deadline_changed_requires_verified_provenance_on_both_sides"

  # Gate 105. Five that keep the Tribal eligibility bridge honest: the shadow
  # cannot come back, the fix is load-bearing rather than incidental, the
  # guard fires on real drift, and widening detection never becomes licence to
  # invent eligibility.
  "tests/test_gate105_tribal_eligibility_classification_bridge.py::test_mixed_corpus_does_not_define_a_local_shadow"
  "tests/test_gate105_tribal_eligibility_classification_bridge.py::test_mixed_corpus_uses_the_canonical_pattern_object_itself"
  "tests/test_gate105_tribal_eligibility_classification_bridge.py::test_the_free_text_probe_would_have_failed_before_the_fix"
  "tests/test_gate105_tribal_eligibility_classification_bridge.py::test_guard_catches_drift_when_the_shadow_is_restored"
  "tests/test_gate105_tribal_eligibility_classification_bridge.py::test_guard_catches_an_over_claim"

  # Gate 106. Five that keep a corpus regeneration honest: the fixture is not
  # written, the refusal is derived from measurements rather than declared,
  # fabrication risk can never permit a commit, and the permission path is
  # reachable so the refusal means something.
  "tests/test_gate106_mixed_corpus_regeneration_attestation.py::test_attestation_defaults_to_fixture_not_mutated"
  "tests/test_gate106_mixed_corpus_regeneration_attestation.py::test_the_committed_fixture_hash_matches_the_attested_before_hash"
  "tests/test_gate106_mixed_corpus_regeneration_attestation.py::test_safe_to_regenerate_is_derived_not_caller_declared"
  "tests/test_gate106_mixed_corpus_regeneration_attestation.py::test_fabrication_risk_can_never_permit_regeneration"
  "tests/test_gate106_mixed_corpus_regeneration_attestation.py::test_a_clean_diff_would_permit_regeneration"

  # Gate 107. Five that keep derivation honest about what it does not know: a
  # synopsis never becomes eligibility evidence, a negative is only asserted
  # when earned, and the attestation that permitted the regeneration still
  # refuses the shape it blocked at Gate 106.
  "tests/test_gate107_honest_mixed_corpus_derivation.py::test_no_row_anywhere_carries_its_own_synopsis_as_eligibility_text"
  "tests/test_gate107_honest_mixed_corpus_derivation.py::test_none_is_not_narrowed_to_false_without_evidence"
  "tests/test_gate107_honest_mixed_corpus_derivation.py::test_false_is_still_reached_when_the_negative_is_earned"
  "tests/test_gate107_honest_mixed_corpus_derivation.py::test_the_attestation_was_not_relaxed_to_permit_this"
  "tests/test_gate107_honest_mixed_corpus_derivation.py::test_the_honest_row_is_untouched_in_the_committed_fixture"

  # Gate 108. Five that keep the Awarded Grants workspace honest: a projection
  # never becomes a duty, an estimate never becomes a countdown, an unknown
  # date stays visible, proof is never invented, and marking a grant awarded
  # creates a record rather than obligations.
  "tests/test_gate108_awarded_grants_requirements_tracking.py::test_a_projected_burden_is_not_an_active_obligation"
  "tests/test_gate108_awarded_grants_requirements_tracking.py::test_an_estimate_is_never_counted_down"
  "tests/test_gate108_awarded_grants_requirements_tracking.py::test_the_calendar_does_not_hide_unknown_due_dates"
  "tests/test_gate108_awarded_grants_requirements_tracking.py::test_proof_is_never_fabricated"
  "tests/test_gate108_awarded_grants_requirements_tracking.py::test_a_transition_never_creates_active_obligations"

  # Gate 109. Five that keep two identity spaces apart: matching strings never
  # bind, a demo binding is never production verification, an unbound or
  # pending pair never writes, and an operational attempt without a verified
  # binding is reported as a cross-tenant risk rather than passing quietly.
  "tests/test_gate109_tenant_customer_org_identity_binding.py::test_matching_strings_do_not_create_a_verified_binding"
  "tests/test_gate109_tenant_customer_org_identity_binding.py::test_a_demo_binding_is_not_production_verification"
  "tests/test_gate109_tenant_customer_org_identity_binding.py::test_a_demo_binding_never_reaches_an_operational_surface"
  "tests/test_gate109_tenant_customer_org_identity_binding.py::test_cross_tenant_risk_is_true_whenever_binding_is_absent_or_conflicting"
  "tests/test_gate109_tenant_customer_org_identity_binding.py::test_a_write_cannot_be_permitted_without_a_verified_binding"

  # Gate 110. Five that keep customer data inside the boundary the database
  # actually enforces: organization_id is the authority, a UUID-shaped
  # tenant_id is still not, a label never carries a write however well bound,
  # and the binding store is never keyed on a label.
  "tests/test_gate110_org_identity_canonicalization.py::test_organization_id_is_the_rls_authority"
  "tests/test_gate110_org_identity_canonicalization.py::test_a_uuid_shaped_tenant_id_is_still_not_the_authority"
  "tests/test_gate110_org_identity_canonicalization.py::test_tenant_id_cannot_persist_awarded_grants_even_with_a_verified_binding"
  "tests/test_gate110_org_identity_canonicalization.py::test_a_satisfied_binding_still_does_not_let_a_label_carry_the_write"
  "tests/test_gate110_org_identity_canonicalization.py::test_the_binding_store_anchors_to_the_rls_authority"

  # Gate 111. Five that keep authentication from over-claiming: a demo
  # principal is not production auth, edge access is not app auth, being
  # authenticated does not establish an organization, a demo principal
  # verifies demo bindings only, and no unauthenticated header claim reaches
  # the RLS context.
  "tests/test_gate111_customer_auth_verified_binder.py::test_demo_auth_is_not_production_auth"
  "tests/test_gate111_customer_auth_verified_binder.py::test_cloudflare_access_is_not_customer_app_auth"
  "tests/test_gate111_customer_auth_verified_binder.py::test_authenticated_does_not_imply_verified_organization_membership"
  "tests/test_gate111_customer_auth_verified_binder.py::test_a_demo_principal_may_verify_a_demo_binding_only"
  "tests/test_gate111_customer_auth_verified_binder.py::test_the_dev_request_header_is_not_an_authenticated_claim"

  # Gate 112. Five that keep a claim from reaching the RLS boundary without
  # resolving to the authority: a profile id is never promoted, membership is
  # required as well as an org claim, and the dev header is never
  # production-safe however well contained the deployment happens to be.
  "tests/test_gate112_oidc_organization_id_resolution.py::test_organization_profile_id_alone_cannot_set_rls"
  "tests/test_gate112_oidc_organization_id_resolution.py::test_organization_profile_id_is_never_promoted"
  "tests/test_gate112_oidc_organization_id_resolution.py::test_verified_membership_is_required_for_rls_context"
  "tests/test_gate112_oidc_organization_id_resolution.py::test_rls_context_requires_verified_membership"
  "tests/test_gate112_oidc_organization_id_resolution.py::test_the_dev_header_is_never_production_safe"

  # Gate 113. Five that keep a new store from becoming a new claim: a
  # profile-shaped string never reaches the organization_id predicate, a label
  # never anchors a stored binding, creating the table permits no storage by
  # itself, no binding of any provenance lets a label carry a write, and
  # exactly one fixture case is operational however many are storable.
  "tests/test_gate113_identity_binding_store_membership_wiring.py::test_lookup_membership_refuses_a_profile_shaped_organization"
  "tests/test_gate113_identity_binding_store_membership_wiring.py::test_only_organization_id_may_anchor_a_stored_binding"
  "tests/test_gate113_identity_binding_store_membership_wiring.py::test_creating_the_table_permits_no_storage_by_itself"
  "tests/test_gate113_identity_binding_store_membership_wiring.py::test_a_binding_of_any_provenance_still_never_lets_a_label_write"
  "tests/test_gate113_identity_binding_store_membership_wiring.py::test_exactly_one_fixture_case_is_operational"

  # Gate 114. Five that keep a persistence contract from reading as
  # persistence: schema available is not operational, no label is a write
  # authority, a verified binding still needs somebody authenticated behind it,
  # and the spine names auth rather than the next lane it could build.
  "tests/test_gate114_org_scoped_customer_persistence.py::test_schema_available_does_not_imply_operational"
  "tests/test_gate114_org_scoped_customer_persistence.py::test_the_binding_store_schema_does_not_imply_customer_persistence_live"
  "tests/test_gate114_org_scoped_customer_persistence.py::test_tenant_id_alone_cannot_write_customer_data"
  "tests/test_gate114_org_scoped_customer_persistence.py::test_a_verified_binding_alone_does_not_allow_a_write_without_auth"
  "tests/test_gate114_org_scoped_customer_persistence.py::test_the_spine_names_auth_as_the_next_gate"

  # Gate 115. Five that keep an auth boundary from reading as auth: a planted
  # secret reaches no artifact, route existence is not enforcement, an unknown
  # provider role grants nothing, the dev header blocks activation while still
  # permitting a login flow, and the actual environment is not auth live.
  "tests/test_gate115_customer_auth_activation_boundary.py::test_a_planted_secret_never_reaches_an_artifact"
  "tests/test_gate115_customer_auth_activation_boundary.py::test_route_existence_does_not_imply_enforcement"
  "tests/test_gate115_customer_auth_activation_boundary.py::test_an_unknown_provider_role_grants_no_privilege"
  "tests/test_gate115_customer_auth_activation_boundary.py::test_the_dev_header_blocks_auth_activation_but_not_login"
  "tests/test_gate115_customer_auth_activation_boundary.py::test_the_actual_environment_is_not_auth_live"

  # Gate 116. Five that keep a route spine from reading as authentication: no
  # route creates a session, a declared security scheme is not enforcement,
  # route existence moves neither login_live nor customer_auth_live, and the
  # auth routes existing does not make the dev header removable.
  "tests/test_gate116_customer_auth_routes_session_policy.py::test_no_route_creates_a_real_session_while_auth_is_not_live"
  "tests/test_gate116_customer_auth_routes_session_policy.py::test_a_declared_security_scheme_is_not_enforcement"
  "tests/test_gate116_customer_auth_routes_session_policy.py::test_route_existence_does_not_imply_customer_auth_live"
  "tests/test_gate116_customer_auth_routes_session_policy.py::test_only_the_callback_may_ever_mint_a_session"
  "tests/test_gate116_customer_auth_routes_session_policy.py::test_auth_routes_existing_does_not_make_the_dev_header_removable"

  # Gate 117. Five that keep a refusal from reading as authentication: the
  # required dependency returns 401, enforcement is not liveness, the token
  # exchange is blocked by the network alone, nothing creates a session, and a
  # route that refuses is not a replacement for the dev header.
  "tests/test_gate117_customer_auth_route_enforcement.py::test_current_user_returns_401_while_unauthenticated"
  "tests/test_gate117_customer_auth_route_enforcement.py::test_route_auth_is_enforced_and_that_is_not_liveness"
  "tests/test_gate117_customer_auth_route_enforcement.py::test_token_exchange_is_not_performed_when_the_network_is_disallowed"
  "tests/test_gate117_customer_auth_route_enforcement.py::test_the_session_creation_branch_is_reachable_and_still_creates_nothing"
  "tests/test_gate117_customer_auth_route_enforcement.py::test_a_refusing_route_does_not_make_the_dev_header_removable"

  # Gate 118. Five that keep a session format from reading as a session: a
  # genuinely-signed profile id is still refused, a valid fixture session is
  # not live auth, a consumed state cannot be replayed, /current-user still
  # returns 401, and no credential reaches a committed file.
  "tests/test_gate118_customer_session_state.py::test_a_genuinely_signed_profile_id_session_is_still_refused"
  "tests/test_gate118_customer_session_state.py::test_the_rls_branch_is_reachable_and_auth_is_still_not_live"
  "tests/test_gate118_customer_session_state.py::test_a_state_is_single_use_and_a_replay_is_detected"
  "tests/test_gate118_customer_session_state.py::test_current_user_remains_401_without_a_valid_session"
  "tests/test_gate118_customer_session_state.py::test_no_session_cookie_state_or_verifier_is_committed"
  "tests/test_gate119_live_redirect_signing_boundary.py::test_the_local_dev_fixture_can_never_sign_a_production_session"
  "tests/test_gate119_live_redirect_signing_boundary.py::test_the_client_secret_never_reaches_a_url"
  "tests/test_gate119_live_redirect_signing_boundary.py::test_what_lands_in_the_row_is_a_digest"
  "tests/test_gate119_live_redirect_signing_boundary.py::test_a_state_is_consumed_exactly_once"
  "tests/test_gate119_live_redirect_signing_boundary.py::test_login_returns_neither_the_state_nor_the_verifier"
  "tests/test_gate120_identity_binding_repository_workflow.py::test_organization_profile_id_is_refused_rather_than_ignored"
  "tests/test_gate120_identity_binding_repository_workflow.py::test_a_production_verified_binding_requires_a_verifier_identity"
  "tests/test_gate120_identity_binding_repository_workflow.py::test_a_revoked_binding_is_retained"
  "tests/test_gate120_identity_binding_repository_workflow.py::test_a_grants_manager_may_inspect_but_may_not_approve"
  "tests/test_gate120_identity_binding_repository_workflow.py::test_auth_not_live_blocks_an_operational_verified_binding"
  "tests/test_gate121_customer_auth_activation_preflight.py::test_the_preflight_never_exposes_an_environment_value"
  "tests/test_gate121_customer_auth_activation_preflight.py::test_provider_readiness_makes_no_network_call_by_default"
  "tests/test_gate121_customer_auth_activation_preflight.py::test_an_unconfigured_environment_reports_no_callback"
  "tests/test_gate121_customer_auth_activation_preflight.py::test_a_configured_callback_on_the_wrong_path_still_blocks"
  "tests/test_gate121_customer_auth_activation_preflight.py::test_the_database_blocker_tracks_the_database_rather_than_a_constant"
  "tests/test_gate121_customer_auth_activation_preflight.py::test_no_runbook_command_can_print_a_variable"
  "tests/test_gate121_customer_auth_activation_preflight.py::test_the_last_fixture_case_is_complete_and_still_not_live"
  "tests/test_gate122_dev_header_replacement.py::test_production_mode_refuses_the_dev_header_as_authority"
  "tests/test_gate122_dev_header_replacement.py::test_optional_mode_does_not_fabricate_an_organization"
  "tests/test_gate122_dev_header_replacement.py::test_a_valid_session_without_membership_cannot_set_rls_context"
  "tests/test_gate122_dev_header_replacement.py::test_the_provider_module_is_not_counted_as_a_route"
  "tests/test_gate122_dev_header_replacement.py::test_a_replacement_existing_does_not_make_the_header_safe"
  "tests/test_gate123_tenant_profile_persistence.py::test_a_mailing_address_does_not_override_operating_states"
  "tests/test_gate123_tenant_profile_persistence.py::test_organization_profile_id_is_refused_as_an_anchor"
  "tests/test_gate123_tenant_profile_persistence.py::test_an_unknown_recognition_status_cannot_claim_an_established_fact"
  "tests/test_gate123_tenant_profile_persistence.py::test_archive_retains_the_profile"
  "tests/test_gate123_tenant_profile_persistence.py::test_a_repository_does_not_make_beta_onboarding_live"
  "tests/test_gate124_awarded_grants_persistence.py::test_a_fully_evidenced_projection_establishes_no_obligation"
  "tests/test_gate124_awarded_grants_persistence.py::test_lineage_is_recorded_and_is_never_a_reason_to_create_an_award"
  "tests/test_gate124_awarded_grants_persistence.py::test_a_claim_is_reported_separately_from_the_derivation"
  "tests/test_gate124_awarded_grants_persistence.py::test_nothing_in_the_repository_deletes"
  "tests/test_gate124_awarded_grants_persistence.py::test_readiness_reports_storage_built_and_tracking_still_blocked"
  "tests/test_gate125_award_requirements_persistence.py::test_awarded_grant_id_cannot_substitute_for_organization_id"
  "tests/test_gate125_award_requirements_persistence.py::test_a_projection_is_stored_and_is_not_an_obligation"
  "tests/test_gate125_award_requirements_persistence.py::test_an_estimated_due_date_is_not_treated_as_known"
  "tests/test_gate125_award_requirements_persistence.py::test_a_document_reference_does_not_imply_a_document_store"
  "tests/test_gate125_award_requirements_persistence.py::test_capability_operational_is_not_the_same_as_ready_to_operate"
  "tests/test_gate126_award_requirement_proof_audit_persistence.py::test_superseding_retains_the_predecessor"
  "tests/test_gate126_award_requirement_proof_audit_persistence.py::test_a_rejection_retains_the_proof"
  "tests/test_gate126_award_requirement_proof_audit_persistence.py::test_a_submitted_proof_is_not_an_accepted_proof"
  "tests/test_gate126_award_requirement_proof_audit_persistence.py::test_every_mapped_repository_module_imports"
  "tests/test_gate126_award_requirement_proof_audit_persistence.py::test_the_extension_kept_every_gate_108_action"
  "tests/test_gate127_award_document_store_persistence.py::test_an_object_key_is_refused_when_the_store_is_unconfigured"
  "tests/test_gate127_award_document_store_persistence.py::test_nothing_in_the_repository_opens_a_file_or_reaches_a_store"
  "tests/test_gate127_award_document_store_persistence.py::test_the_repository_is_not_named_award_document_store_service"
  "tests/test_gate127_award_document_store_persistence.py::test_legal_hold_prevents_archive"
  "tests/test_gate127_award_document_store_persistence.py::test_readiness_reports_metadata_built_and_storage_still_false"
  "tests/test_gate128_customer_auth_activation_execution.py::test_no_hardcoded_callback_url_remains_in_the_code"
  "tests/test_gate128_customer_auth_activation_execution.py::test_the_route_path_is_imported_rather_than_restated"
  "tests/test_gate128_customer_auth_activation_execution.py::test_unconfigured_environment_yields_no_callback"
  "tests/test_gate128_customer_auth_activation_execution.py::test_invariant_fires_on_the_exact_literal_that_used_to_be_frozen"
  "tests/test_gate128_customer_auth_activation_execution.py::test_invariant_does_not_fire_on_absence"
  "tests/test_gate129_demo_live_auth_unfuck.py::test_the_shell_has_every_required_section"
  "tests/test_gate129_demo_live_auth_unfuck.py::test_every_truth_label_is_active_today"
  "tests/test_gate129_demo_live_auth_unfuck.py::test_a_label_deactivates_when_the_thing_it_names_goes_live"
  "tests/test_gate129_demo_live_auth_unfuck.py::test_settings_declares_every_auth_key"
  "tests/test_gate129_demo_live_auth_unfuck.py::test_the_two_secrets_are_secret_typed_and_never_serialize"
  "tests/test_gate129_demo_live_auth_unfuck.py::test_the_callback_refuses_rather_than_404ing"
  "tests/test_gate130_google_oauth_login_smoke.py::test_google_offline_refuses_rather_than_guessing"
  "tests/test_gate130_google_oauth_login_smoke.py::test_google_with_metadata_yields_googles_real_endpoints"
  "tests/test_gate130_google_oauth_login_smoke.py::test_googles_token_and_jwks_are_not_on_the_issuer_host"
  "tests/test_gate130_google_oauth_login_smoke.py::test_google_authorization_url_targets_googles_endpoint"
  "tests/test_gate130_google_oauth_login_smoke.py::test_the_callback_url_has_no_trailing_slash"
  "tests/test_gate130_demo_reliability_oauth_war_gate.py::test_the_verifier_refuses_1033"
  "tests/test_gate130_demo_reliability_oauth_war_gate.py::test_the_verifier_fails_any_5xx_rather_than_a_named_list"
  "tests/test_gate130_demo_reliability_oauth_war_gate.py::test_the_tracked_units_restart_on_a_clean_exit"
  "tests/test_gate130_demo_reliability_oauth_war_gate.py::test_the_suite_does_not_read_the_machine_s_dotenv"
  "tests/test_gate130_demo_reliability_oauth_war_gate.py::test_an_unconfigured_provider_is_what_the_suite_sees"
  "tests/test_gate131_oauth_state_session_minting.py::test_login_state_is_stored_durably_and_hashed"
  "tests/test_gate131_oauth_state_session_minting.py::test_state_is_one_time_use"
  "tests/test_gate131_oauth_state_session_minting.py::test_an_expired_state_is_refused"
  "tests/test_gate131_oauth_state_session_minting.py::test_identity_alone_cannot_mint_a_session"
  "tests/test_gate131_oauth_state_session_minting.py::test_no_exchange_is_attempted_without_a_verifier"
  "tests/test_gate131_oauth_state_session_minting.py::test_the_verifier_round_trips_and_the_value_never_enters_a_report"
)

FAIL=0
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "verify=test_selection_coverage"

python -m pytest tests -q --collect-only 2>/dev/null \
  | grep '::' > "$TMP/all.txt" || true
python -m pytest tests -q --collect-only -k "$GATE_K" 2>/dev/null \
  | grep '::' > "$TMP/selected.txt" || true

TOTAL="$(wc -l < "$TMP/all.txt" | tr -d ' ')"
SELECTED="$(wc -l < "$TMP/selected.txt" | tr -d ' ')"
UNSELECTED=$((TOTAL - SELECTED))

if [[ "$TOTAL" -lt 1 ]]; then
  echo "check=collection status=FAIL collected nothing"
  echo "RESULT=FAIL"
  exit 1
fi

PCT=$(( SELECTED * 100 / TOTAL ))
echo "check=collected status=PASS total=${TOTAL}"
echo "check=selected_by_gate_expression status=PASS selected=${SELECTED} (${PCT}%)"
echo "check=unselected status=INFO unselected=${UNSELECTED}"

# Every critical test must exist, and must be inside the gate selection.
for node in "${CRITICAL[@]}"; do
  name="${node##*::}"
  if ! grep -qF "$node" "$TMP/all.txt"; then
    echo "check=critical_exists:${name} status=FAIL not collected (renamed or removed?)"
    FAIL=1
    continue
  fi
  if grep -qF "$node" "$TMP/selected.txt"; then
    echo "check=critical_selected:${name} status=PASS"
  else
    echo "check=critical_selected:${name} status=FAIL not reached by the gate -k"
    FAIL=1
  fi
done

# A selection that has collapsed to almost nothing is a broken expression, not
# a deliberate subset.
if [[ "$PCT" -lt 50 ]]; then
  echo "check=selection_breadth status=FAIL only ${PCT}% selected"
  FAIL=1
else
  echo "check=selection_breadth status=PASS ${PCT}%"
fi

if [[ "$FAIL" -eq 0 ]]; then
  echo "RESULT=PASS"
else
  echo "RESULT=FAIL"
fi
exit "$FAIL"
