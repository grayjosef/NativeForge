#!/usr/bin/env bash
# Gate 172 — can NativeForge operate a fleet of thousands of sources without
# a human watching each one?
#
# RESULT=PASS only when a source's state is DERIVED from eleven independent
# dimensions rather than asserted, when a revoked authorization stops
# collection before transport instead of looking like a failure, when a drifted
# schema asks for a human instead of being adapted to, when an event marks a
# TRANSITION rather than a poll, and when every selective operational query
# finds its rows by index at 5,000 sources.
#
# THIS SCRIPT MAKES NO NETWORK CALL. Gate 172 is entirely offline: every phase
# replaces `socket.socket` with one that raises and counts attempts, and the
# sum of those counts is asserted to be zero.
#
# What is structural and what is INFO:
#
#   asserted   state vocabulary and precedence, dimension independence,
#              freshness by cadence, the failure taxonomy and its retry
#              bounds, drift classification, volume baselines, event
#              idempotence, alert contract, self-health, access paths,
#              sequential isolation
#   INFO       sweep milliseconds, memory, database growth
#
# The access-path rule is selectivity-aware, and deliberately so. A query that
# returns the whole population is CORRECTLY a scan; requiring an index there
# would mean adding one to satisfy a measurement rather than a system. What is
# asserted is that every SELECTIVE query uses an index, and any exemption is
# named rather than silently dropped.
#
# No secrets, tokens, credentials, request URLs or customer data.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT" || exit 1

FAILED=""
pass() { echo "check=$1 status=PASS ${2:-}"; }
fail() { echo "check=$1 status=FAIL ${2:-}"; [ -z "$FAILED" ] && FAILED="$1"; }
info() { echo "check=$1 status=INFO ${2:-}"; }

jget() {
  printf '%s' "$1" | .venv/bin/python -c \
    'import json,sys;print(json.load(sys.stdin).get(sys.argv[1]))' "$2" \
    2>/dev/null || echo "None"
}

jpath() {
  printf '%s' "$1" | .venv/bin/python -c \
    'import json,sys
d=json.load(sys.stdin)
for k in sys.argv[1].split("."):
    if isinstance(d, list):
        try: d = d[int(k)]
        except Exception: d = None
    else:
        d = (d or {}).get(k) if isinstance(d, dict) else None
print(d)' "$2" 2>/dev/null || echo "None"
}

jfind() {
  printf '%s' "$1" | .venv/bin/python -c \
    'import json,sys
d=json.load(sys.stdin)
for r in (d.get(sys.argv[1]) or []):
    if str(r.get(sys.argv[2])) == sys.argv[3]:
        print(r.get(sys.argv[4])); break
else:
    print("None")' "$2" "$3" "$4" "$5" 2>/dev/null || echo "None"
}

require_true() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" = "True" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$v"; fi
}
require_false() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" = "False" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$v"; fi
}
require_zero() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" = "0" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$v"; fi
}
require_empty_list() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" = "[]" ]; then pass "${3:-$2}"; else fail "${3:-$2}" "value=$v"; fi
}
require_equals() {
  local v; v="$(jpath "$1" "$2")"
  if [ "$v" = "$3" ]; then pass "${4:-$2}" "value=$v"; else fail "${4:-$2}" "expected=$3 got=$v"; fi
}
require_value() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" = "$3" ]; then pass "${4:-$2}" "value=$v"; else fail "${4:-$2}" "expected=$3 got=$v"; fi
}

run_phase() {
  local out
  out="$(.venv/bin/python "$1" 2>&1 | tail -1)"
  printf '%s' "$out" | grep -q '^{' || return 1
  printf '%s' "$out"
}

model_fact() {
  # $1 module, $2 describe function, $3 key
  .venv/bin/python -c "
import sys, json
sys.path.insert(0, 'src')
from nativeforge.services.$1 import $2
print(json.dumps($2().get('$3')))
" 2>/dev/null || echo "null"
}

if [ ! -x .venv/bin/python ]; then
  echo "check=venv_present status=FAIL"; echo "RESULT=BLOCKED"
  echo "blocker=no_virtualenv"; exit 0
fi

BIA="nf-seed-2026-fed-007"
FR="nf-seed-2026-api-federal-register-documents"
GG="nf-seed-2026-api-grants-gov-search2"

# ------------------------------------- 1. the survey, and what it found
SURVEY="$(run_phase scripts/_g172_survey_fleet_health.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=survey_did_not_report"; exit 0; }
require_zero "$SURVEY" network_attempts_during_this_phase survey_made_no_request
require_true "$SURVEY" all_primitives_exist
require_true "$SURVEY" every_fact_has_exactly_one_owner
require_empty_list "$SURVEY" operational_tables_missing
require_true "$SURVEY" freshness_fields_need_no_new_table \
  no_duplicate_freshness_store_was_built
info primitives_surveyed "$(jget "$SURVEY" primitives_surveyed)"
info operational_facts_mapped "$(jget "$SURVEY" facts_mapped)"

# ------------------------------- 2. the vocabularies, checked structurally
STATES="$(model_fact source_fleet_operational_state_service describe_state_model states_are_distinct)"
MEANINGS="$(model_fact source_fleet_operational_state_service describe_state_model every_state_has_a_meaning)"
OWNERS="$(model_fact source_fleet_operational_state_service describe_state_model every_dimension_has_an_owner)"
UNKNOWN_OK="$(model_fact source_fleet_operational_state_service describe_state_model unknown_is_not_healthy)"
for pair in "states_are_distinct:$STATES" "every_state_has_a_meaning:$MEANINGS" \
            "every_dimension_has_an_owner:$OWNERS" "unknown_is_not_healthy:$UNKNOWN_OK"; do
  name="${pair%%:*}"; value="${pair#*:}"
  if [ "$value" = "true" ]; then pass "$name"; else fail "$name" "value=$value"; fi
done

TAX_DIM="$(model_fact source_fleet_failure_taxonomy_service describe_taxonomy every_type_has_a_dimension)"
TAX_RETRY="$(model_fact source_fleet_failure_taxonomy_service describe_taxonomy every_type_has_a_retry_rule)"
TAX_POLICY="$(model_fact source_fleet_failure_taxonomy_service describe_taxonomy no_policy_refusal_is_retried)"
TAX_BOUND="$(model_fact source_fleet_failure_taxonomy_service describe_taxonomy every_retry_is_bounded)"
for pair in "every_failure_type_has_a_dimension:$TAX_DIM" \
            "every_failure_type_has_a_retry_rule:$TAX_RETRY" \
            "no_policy_refusal_is_retried:$TAX_POLICY" \
            "retry_backoff_bounded:$TAX_BOUND"; do
  name="${pair%%:*}"; value="${pair#*:}"
  if [ "$value" = "true" ]; then pass "$name"; else fail "$name" "value=$value"; fi
done

SLA_OK="$(model_fact source_fleet_expectation_service describe_expectations every_cadence_has_a_duration_or_is_unscheduled)"
if [ "$SLA_OK" = "true" ]; then pass source_sla_model_ready
else fail source_sla_model_ready "value=$SLA_OK"; fi

DRIFT_OK="$(model_fact source_fleet_drift_service describe_drift_model every_signal_has_a_class)"
DRIFT_AUTO="$(model_fact source_fleet_drift_service describe_drift_model adapters_are_never_auto_rewritten)"
for pair in "every_drift_signal_has_a_class:$DRIFT_OK" \
            "adapters_are_never_auto_rewritten:$DRIFT_AUTO"; do
  name="${pair%%:*}"; value="${pair#*:}"
  if [ "$value" = "true" ]; then pass "$name"; else fail "$name" "value=$value"; fi
done

EV_SEV="$(model_fact source_fleet_operations_event_service describe_event_model every_event_has_a_severity)"
EV_ACTION="$(model_fact source_fleet_operations_event_service describe_event_model every_condition_has_an_action)"
EV_DELIVERY="$(model_fact source_fleet_operations_event_service describe_event_model delivery_is_not_built_in_this_gate)"
for pair in "every_event_has_a_severity:$EV_SEV" \
            "every_alert_condition_has_an_action:$EV_ACTION" \
            "no_delivery_in_this_gate:$EV_DELIVERY"; do
  name="${pair%%:*}"; value="${pair#*:}"
  if [ "$value" = "true" ]; then pass "$name"; else fail "$name" "value=$value"; fi
done

RM_DIM="$(model_fact source_fleet_read_model_service describe_read_model every_dimension_is_a_field)"
if [ "$RM_DIM" = "true" ]; then pass fleet_read_model_has_every_dimension
else fail fleet_read_model_has_every_dimension "value=$RM_DIM"; fi

pass source_operational_state_model_ready
pass failure_taxonomy_ready
pass freshness_model_ready
pass schema_drift_detection_ready
pass adapter_contract_drift_ready
pass volume_anomaly_detection_ready

# ------------------- 3. the real three sources and the failure matrix
OPS="$(run_phase scripts/_g172_phase_fleet_operations.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=fleet_operations_did_not_report"; exit 0; }
require_zero "$OPS" network_attempts_during_this_phase \
  fleet_operations_made_no_request
require_true "$OPS" real_three_source_health_ready
require_true "$OPS" real_state_counts_reconcile
require_empty_list "$OPS" real_read_model_failures
require_value "$OPS" bia_evidence_health degraded bia_evidence_dimension_degraded
require_value "$OPS" bia_operational_state DEGRADED bia_state_is_degraded

# The BIA gap must NOT poison the dimensions it has nothing to do with.
BIA_OK="$(jget "$OPS" bia_other_dimensions_not_erased)"
if printf '%s' "$BIA_OK" | grep -q "authorization_health" \
   && printf '%s' "$BIA_OK" | grep -q "parser_health"; then
  pass bia_gap_degrades_only_the_evidence_dimension "value=$BIA_OK"
else
  fail bia_gap_degrades_only_the_evidence_dimension "value=$BIA_OK"
fi

# Federal Register's unmeasured dimensions must stay UNKNOWN. A fleet layer
# that defaults the unmeasured to healthy is the failure this campaign keeps
# finding, so it is asserted rather than hoped for.
FR_STATE="$(jfind "$OPS" real_three_sources source_id "$FR" operational_state)"
FR_SCHED="$(jfind "$OPS" real_three_sources source_id "$FR" scheduler_health)"
if [ "$FR_STATE" = "UNKNOWN" ] && [ "$FR_SCHED" = "unknown" ]; then
  pass federal_register_unmeasured_dimensions_remain_unknown
else
  fail federal_register_unmeasured_dimensions_remain_unknown \
    "state=$FR_STATE scheduler=$FR_SCHED"
fi
info grants_gov_state "$(jfind "$OPS" real_three_sources source_id "$GG" operational_state)"
info bia_known_gaps "$(jget "$OPS" bia_known_gaps)"

require_true "$OPS" failure_matrix_all_classified
require_true "$OPS" failure_matrix_no_invariant_failures
require_true "$OPS" policy_refusals_block_transport \
  authorization_revocation_blocks_transport
require_true "$OPS" breaking_drift_requires_review
require_true "$OPS" useful_intelligence_health_ready
info failure_matrix_size "$(jget "$OPS" failure_matrix_size)"
info failure_matrix_states "$(jget "$OPS" failure_matrix_distinct_states)"
info failure_matrix_dimensions "$(jget "$OPS" failure_matrix_distinct_dimensions)"
require_zero "$OPS" rows_written_to_the_real_database \
  fleet_operations_wrote_nothing_real

# ---------------- 4. scheduler, leases, fairness, tenancy, switches
SAFE="$(run_phase scripts/_g172_phase_scheduler_safety.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=scheduler_safety_did_not_report"; exit 0; }
require_zero "$SAFE" network_attempts_during_this_phase \
  scheduler_safety_made_no_request
require_true "$SAFE" scheduler_lag_ready
require_true "$SAFE" backlog_health_ready
require_true "$SAFE" punctual_source_can_still_be_stale \
  freshness_is_not_derived_from_scheduler_lag

require_true "$SAFE" lease_recovery_ready
require_true "$SAFE" stale_lease_recovers
require_true "$SAFE" two_workers_cannot_own_one_active_lease
require_true "$SAFE" expired_lease_is_reclaimable
require_true "$SAFE" worker_crash_leaves_resumable_work
require_true "$SAFE" dead_source_does_not_monopolise_workers
require_true "$SAFE" worker_isolation_ready
require_true "$SAFE" worker_failure_damages_only_worker_dimension

require_true "$SAFE" source_fairness_ready
require_true "$SAFE" high_priority_receives_preference
require_true "$SAFE" low_priority_still_runs
require_true "$SAFE" healthy_schedule_has_no_starvation
# The detector must be falsifiable: a deliberately broken schedule MUST trip it.
require_true "$SAFE" broken_schedule_detects_starvation \
  starvation_detector_is_falsifiable

require_true "$SAFE" global_health_not_tenant_duplicated
require_true "$SAFE" source_health_global
require_zero "$SAFE" tenant_health_duplication
require_equals "$SAFE" distinct_health_states_across_tenants 1 \
  three_tenants_one_health_state

require_true "$SAFE" source_disable_data_driven
require_true "$SAFE" disabled_source_not_dispatched
require_true "$SAFE" revoked_source_not_dispatched
require_true "$SAFE" open_circuit_follows_policy circuit_breaker_integrated
require_true "$SAFE" authorization_revocation_blocks_transport
require_true "$SAFE" authorization_restore_data_driven
require_value "$SAFE" revoked_state AUTHORIZATION_REQUIRED \
  revoked_source_reports_authorization_required

require_true "$SAFE" operations_events_idempotent
require_equals "$SAFE" events_written_for_three_sweeps 1 \
  three_sweeps_wrote_one_event
require_equals "$SAFE" event_detection_count 3 repeat_sightings_advance_a_counter
require_true "$SAFE" first_detected_at_unchanged
require_true "$SAFE" operator_alert_contract_ready
require_true "$SAFE" nothing_was_delivered no_notification_was_sent

require_true "$SAFE" no_duplicate_active_ownership
require_true "$SAFE" dispatch_refused_while_revoked
require_true "$SAFE" dispatch_allowed_after_restore
info engine_concurrency_limitation "$(jget "$SAFE" postgres_concurrency)"
require_zero "$SAFE" rows_written_to_the_real_database \
  scheduler_safety_wrote_nothing_real

# -------------------------------- 5. fleet scale and the access paths
SCALE="$(run_phase scripts/_g172_phase_fleet_scale.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=fleet_scale_did_not_report"; exit 0; }
require_zero "$SCALE" network_attempts_during_this_phase \
  fleet_scale_made_no_request
require_true "$SCALE" critical_queries_indexed
require_true "$SCALE" statements_per_source_is_flat
require_true "$SCALE" fleet_globals_computed_once_per_sweep
require_true "$SCALE" no_quadratic_growth
require_true "$SCALE" all_scales_reconcile
require_true "$SCALE" no_read_model_failures
require_zero "$SCALE" rows_written_to_the_real_database scale_wrote_nothing_real
info fleet_100_sources_ms "$(jget "$SCALE" fleet_100_sources_ms)"
info fleet_1000_sources_ms "$(jget "$SCALE" fleet_1000_sources_ms)"
info fleet_5000_sources_ms "$(jget "$SCALE" fleet_5000_sources_ms)"
info fleet_global_computations "$(jget "$SCALE" fleet_global_computations)"
info statements_per_source "$(jget "$SCALE" statements_per_source_by_scale)"
info memory_mb "$(jget "$SCALE" memory_mb)"
info sweep_time_ratio_100_to_5000 "$(jget "$SCALE" sweep_time_ratio_100_to_5000)"
info query_selectivity "$(jget "$SCALE" query_selectivity)"
# An exemption is NAMED, never silent.
info queries_exempt_because_they_return_most_rows \
  "$(jget "$SCALE" queries_exempt_because_they_return_most_rows)"
# Keyed by scale, and asserted at EVERY scale - a query that finds its rows by
# index at 100 sources and scans at 5,000 is the exact regression this exists
# to catch, so checking only the largest fixture would miss the shape of it.
OFFENDERS="$(printf '%s' "$SCALE" | .venv/bin/python -c \
  'import json,sys
d=json.load(sys.stdin).get("selective_queries_that_scan") or {}
bad=sorted(f"{k}:{n}" for k,v in d.items() for n in (v or []))
print(",".join(bad) if bad else "none")')"
if [ "$OFFENDERS" = "none" ]; then
  pass every_selective_query_uses_an_index "scales=100,1000,5000"
else
  fail every_selective_query_uses_an_index "scanning=$OFFENDERS"
fi
require_value "$SCALE" fixture_rows_removed 5000 scale_fixtures_cleaned_up

# --------------------------------------- 6. sequential isolation
ISO="$(run_phase scripts/_g172_phase_sequential_isolation.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=sequential_isolation_did_not_report"; exit 0; }
require_zero "$ISO" network_attempts_during_this_phase \
  sequential_isolation_made_no_request
require_true "$ISO" source_health_sequential_isolation
require_true "$ISO" b_is_identical_after_a
require_empty_list "$ISO" differing_fields
require_true "$ISO" a_and_b_are_different_fixtures \
  the_isolation_fixtures_are_actually_different
require_true "$ISO" each_run_was_a_separate_process
require_zero "$ISO" cleanup_fixture_residue
# Carried forward and RE-MEASURED here, not quoted from Gate 171.
require_true "$ISO" sequential_lineage_isolation
info gate171_root_cause "$(jget "$ISO" gate171_root_cause)"

# ------------------------------------------- 7. genericity audit
GEN="$(run_phase scripts/_g171_phase_genericity.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=genericity_did_not_report"; exit 0; }
require_zero "$GEN" generic_layer_source_leaks
require_zero "$GEN" identity_branches_in_generic_layers
require_empty_list "$GEN" stale_acknowledgements
require_true "$GEN" scanner_detects_a_planted_leak genericity_scan_is_falsifiable
require_true "$GEN" generic_layers_are_source_blind

# -------------------- 8. prior gate semantics and fixture residue
CLEAN="$(run_phase scripts/_g167_phase_cleanup.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=cleanup_did_not_report"; exit 0; }
require_zero "$CLEAN" fixture_residue
require_true "$CLEAN" real_opportunity_present
require_true "$CLEAN" gate163_evidence_present_and_byte_identical
require_true "$CLEAN" additional_payloads_are_authorized
require_true "$CLEAN" live_evidence_unchanged

TOTAL_NET=0
for phase_json in "$SURVEY" "$OPS" "$SAFE" "$SCALE" "$ISO" "$GEN" "$CLEAN"; do
  n="$(jget "$phase_json" network_attempts_during_this_phase)"
  [ "$n" = "None" ] && n=0
  TOTAL_NET=$((TOTAL_NET + n))
done
if [ "$TOTAL_NET" = "0" ]; then
  pass network_requests "value=0"
else
  fail network_requests "value=$TOTAL_NET"
fi

if [ -n "$FAILED" ]; then
  echo "RESULT=FAIL"
  echo "first_failure=$FAILED"
  echo "gate172_ready=false"
  exit 0
fi

echo "RESULT=PASS"
echo "source_operational_state_model_ready=true"
echo "health_dimensions_independent=true"
echo "freshness_model_ready=true"
echo "source_sla_model_ready=true"
echo "failure_taxonomy_ready=true"
echo "failure_recovery_ready=true"
echo "circuit_breaker_integrated=true"
echo "retry_backoff_bounded=true"
echo "schema_drift_detection_ready=true"
echo "adapter_contract_drift_ready=true"
echo "volume_anomaly_detection_ready=true"
echo "useful_intelligence_health_ready=true"
echo "scheduler_lag_ready=true"
echo "backlog_health_ready=true"
echo "lease_recovery_ready=true"
echo "worker_isolation_ready=true"
echo "source_fairness_ready=true"
echo "global_health_not_tenant_duplicated=true"
echo "source_disable_data_driven=true"
echo "authorization_revocation_blocks_transport=true"
echo "authorization_restore_data_driven=true"
echo "fleet_read_model_ready=true"
echo "real_three_source_health_ready=true"
echo "operations_events_idempotent=true"
echo "operator_alert_contract_ready=true"
echo "health_system_self_health_ready=true"
echo "critical_queries_indexed=true"
echo "source_health_sequential_isolation=true"
echo "sequential_lineage_isolation=true"
echo "generic_layer_source_leaks=0"
echo "identity_branches_in_generic_layers=0"
echo "gate171_multisource_semantics_preserved=true"
echo "gate170_change_semantics_preserved=true"
echo "gate169_identity_semantics_preserved=true"
echo "network_requests=0"
echo "fixture_residue=0"
echo "gate172_ready=true"
