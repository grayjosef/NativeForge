#!/usr/bin/env bash
# Gate 164 — is the first live collection replayable, auditable and canonically
# reproducible, whatever is on the developer machine?
#
# RESULT=PASS only when the recorded collection recovers its exact bytes from a
# FRESH connection with no network, its audit chain composes from existing rows,
# every tamper is refused, and canonical artifact generation is provably
# unaffected by a local `.env`.
#
# THIS SCRIPT MAKES NO NETWORK CALL, and does not take anyone's word for that:
# each phase replaces `socket.socket` with one that raises and reports how many
# times anything tried.
#
# It derives rather than accepts. Every number below is read from a phase that
# measured it on this checkout - none is passed in by a caller.
#
# The count of authorized live collections is REPORTED, never required to be 1.
# One is the current state, not an architectural maximum: a second authorized
# source would raise the count and must not fail this verifier.
#
# No secrets, tokens, credentials, request URLs or customer data. Counts,
# booleans, hashes and identifiers only.
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

require_true() {
  # $1 phase json, $2 key, $3 optional label
  local value
  value="$(jget "$1" "$2")"
  if [ "$value" = "True" ]; then
    pass "${3:-$2}"
  else
    fail "${3:-$2}" "value=$value"
  fi
}

if [ ! -x .venv/bin/python ]; then
  echo "check=venv_present status=FAIL"
  echo "RESULT=BLOCKED"
  echo "blocker=no_virtualenv"
  exit 0
fi

# ---------------------------------------------------------- 1. replay
REPLAY="$(.venv/bin/python scripts/_g164_phase_replay.py 2>&1 | tail -1)"
if ! printf '%s' "$REPLAY" | grep -q '^{'; then
  echo "check=replay_phase_ran status=FAIL"
  echo "RESULT=BLOCKED"
  echo "blocker=replay_phase_did_not_report"
  exit 0
fi

require_true "$REPLAY" the_collection_exists live_collection_exists
require_true "$REPLAY" replay_hash_verified hash_verified
require_true "$REPLAY" exact_bytes_recovered
require_true "$REPLAY" sha256_recomputes
require_true "$REPLAY" source_id_survives
require_true "$REPLAY" authorized_source_id_survives authorization_linkage_valid
require_true "$REPLAY" request_fingerprint_survives request_fingerprint_valid
require_true "$REPLAY" execution_proof_present
require_true "$REPLAY" normalization_reproduced normalization_reproduced
require_true "$REPLAY" fresh_connection_replay
require_true "$REPLAY" replay_without_network
require_true "$REPLAY" http_status_is_still_unknown

info recovered_byte_count "$(jget "$REPLAY" recovered_byte_count)"
info recomputed_sha256 "$(jget "$REPLAY" recomputed_sha256)"
info reproduced_opportunity "$(jget "$REPLAY" reproduced_opportunity)"
info replay_network_calls "$(jget "$REPLAY" network_calls_during_replay)"
REPLAY_DETAIL="$(jget "$REPLAY" detail)"
[ "$REPLAY_DETAIL" != "None" ] && info replay_detail "$REPLAY_DETAIL"

# ------------------------------------------- 2. tamper and ambient guard
TAMPER="$(.venv/bin/python scripts/_g164_phase_tamper_and_ambient.py 2>&1 | tail -1)"
if ! printf '%s' "$TAMPER" | grep -q '^{'; then
  echo "check=tamper_phase_ran status=FAIL"
  echo "RESULT=BLOCKED"
  echo "blocker=tamper_phase_did_not_report"
  exit 0
fi

for key in \
  an_untouched_copy_still_verifies \
  changed_raw_bytes_are_refused \
  a_changed_payload_hash_is_refused \
  a_changed_source_id_breaks_the_audit \
  a_stripped_authorized_source_id_is_refused \
  a_changed_request_authority_is_refused \
  a_missing_execution_proof_breaks_the_chain \
  a_proof_that_names_other_bytes_is_refused \
  a_backfilled_http_status_is_refused \
  an_unexplained_absent_status_is_refused \
  canonical_refuses_ambient_secret_state \
  the_flag_is_restored_after_a_refusal \
  an_explicit_environ_is_still_an_input \
  a_contradictory_context_is_refused \
  no_settings_secret_value_appears_in_the_audit \
  the_secret_scan_had_something_to_look_for \
  no_network_during_tamper_and_guard
do
  require_true "$TAMPER" "$key"
done

info settings_secret_values_checked "$(jget "$TAMPER" settings_secret_values_checked)"
TAMPER_DETAIL="$(jget "$TAMPER" detail)"
[ "$TAMPER_DETAIL" != "None" ] && info tamper_detail "$TAMPER_DETAIL"

# ------------------------------------------- 3. build-context isolation
CONTEXT="$(.venv/bin/python scripts/_g164_phase_context_isolation.py 2>&1 | tail -1)"
if ! printf '%s' "$CONTEXT" | grep -q '^{'; then
  echo "check=context_phase_ran status=FAIL"
  echo "RESULT=BLOCKED"
  echo "blocker=context_phase_did_not_report"
  exit 0
fi

for key in \
  an_exception_restores_the_prior_state \
  nesting_restores_to_the_enclosing_state \
  environment_scoped_does_not_leak_after_exit \
  another_thread_is_unaffected \
  a_reused_pooled_worker_does_not_inherit_the_flag \
  a_concurrent_task_on_the_same_thread_is_unaffected \
  parallel_canonical_and_environment_scoped_do_not_cross \
  the_context_is_clean_at_the_end
do
  require_true "$CONTEXT" "$key"
done

# ------------------------------------ 4. health, provenance, no network
HEALTH="$(.venv/bin/python scripts/_g164_phase_health_and_provenance.py 2>&1 | tail -1)"
if ! printf '%s' "$HEALTH" | grep -q '^{'; then
  echo "check=health_phase_ran status=FAIL"
  echo "RESULT=BLOCKED"
  echo "blocker=health_phase_did_not_report"
  exit 0
fi

require_true "$HEALTH" canonical_artifact_generation_hermetic
require_true "$HEALTH" health_is_healthy_with_known_gap
require_true "$HEALTH" the_gap_is_named
require_true "$HEALTH" no_unmet_health_conditions
require_true "$HEALTH" health_invariants_clean
require_true "$HEALTH" a_gap_cannot_be_reported_as_plain_healthy
require_true "$HEALTH" a_gap_status_must_name_a_gap
require_true "$HEALTH" customer_provenance_safe
require_true "$HEALTH" an_internal_field_in_the_dto_is_refused
require_true "$HEALTH" no_internal_marker_in_the_customer_dto
require_true "$HEALTH" no_network_during_health_and_provenance

HEALTH_STATUS="$(jget "$HEALTH" health_status)"
info health_status "$HEALTH_STATUS"
info known_evidence_gap "$(jget "$HEALTH" known_evidence_gaps)"

# The audit chain, from the health phase's own composition.
AUDIT_COMPLETE="$(jget "$HEALTH" no_unmet_health_conditions)"
if [ "$AUDIT_COMPLETE" = "True" ]; then
  pass audit_chain_complete
else
  fail audit_chain_complete
fi

# --------------------------------------------- 5. the safety counters
UNAUTH_ATTEMPTS="$(jget "$HEALTH" unauthorized_live_attempts)"
UNAUTH_ROWS="$(jget "$HEALTH" unauthorized_live_rows)"
LIVE_ATTEMPTS="$(jget "$HEALTH" live_attempts)"
AUTHORIZED_ATTEMPTS="$(jget "$HEALTH" authorized_live_attempts)"

if [ "$UNAUTH_ATTEMPTS" = "0" ]; then
  pass unauthorized_live_attempts "n=0"
else
  fail unauthorized_live_attempts "n=$UNAUTH_ATTEMPTS"
fi
if [ "$UNAUTH_ROWS" = "0" ]; then
  pass unauthorized_live_rows "n=0"
else
  fail unauthorized_live_rows "n=$UNAUTH_ROWS"
fi

# REPORTED, not required. A second authorized source would raise this and must
# not fail the gate; what must stay zero is the UNAUTHORIZED count above.
info live_attempts "$LIVE_ATTEMPTS"
info authorized_live_collection_count "$AUTHORIZED_ATTEMPTS"
if [ "$AUTHORIZED_ATTEMPTS" != "None" ] && [ "$AUTHORIZED_ATTEMPTS" -ge 1 ] 2>/dev/null
then
  pass at_least_one_authorized_live_collection "n=$AUTHORIZED_ATTEMPTS"
else
  fail at_least_one_authorized_live_collection "n=$AUTHORIZED_ATTEMPTS"
fi

# ------------------------------- 6. every artifact writer is classified
CLASSIFICATION="artifacts/live_collection_audit_gate164/artifact_writer_classification.json"
if [ -f "$CLASSIFICATION" ]; then
  UNCLASSIFIED="$(.venv/bin/python -c \
    'import json,sys;print(json.load(open(sys.argv[1]))["counts"]["unclassified_writers"])' \
    "$CLASSIFICATION" 2>/dev/null || echo "None")"
  TOTAL="$(.venv/bin/python -c \
    'import json,sys;print(json.load(open(sys.argv[1]))["counts"]["total_writers"])' \
    "$CLASSIFICATION" 2>/dev/null || echo "None")"
  NOT_MEASURED="$(.venv/bin/python -c \
    'import json,sys;print(json.load(open(sys.argv[1]))["counts"]["not_measured_writers"])' \
    "$CLASSIFICATION" 2>/dev/null || echo "None")"
  info artifact_writers_total "$TOTAL"
  if [ "$UNCLASSIFIED" = "0" ]; then
    pass artifact_writers_unclassified "n=0"
  else
    fail artifact_writers_unclassified "n=$UNCLASSIFIED"
  fi
  # A writer that was never measured is not a classified writer, and an
  # earlier run of this gate reported exactly that after the tree moved
  # underneath the measurement.
  if [ "$NOT_MEASURED" = "0" ]; then
    pass artifact_writers_all_measured "n=0 unmeasured"
  else
    fail artifact_writers_all_measured "n=$NOT_MEASURED"
  fi
else
  fail artifact_writer_classification_present "missing $CLASSIFICATION"
fi

# ------------------------------------------------- 7. the total network
REPLAY_NET="$(jget "$REPLAY" network_calls_during_replay)"
TAMPER_NET="$(jget "$TAMPER" network_attempts_during_this_phase)"
HEALTH_NET="$(jget "$HEALTH" network_requests_during_this_phase)"
TOTAL_NET=$(( ${REPLAY_NET:-1} + ${TAMPER_NET:-1} + ${HEALTH_NET:-1} ))
info network_requests_during_gate164 "$TOTAL_NET"
if [ "$TOTAL_NET" = "0" ]; then
  pass network_requests_during_gate164_is_zero
else
  fail network_requests_during_gate164_is_zero "n=$TOTAL_NET"
fi

echo "known_evidence_gap=http_status_not_captured"
echo "health_status=$HEALTH_STATUS"

if [ -n "$FAILED" ]; then
  echo "RESULT=FAIL"
  echo "first_failure=$FAILED"
  echo "gate164_ready=false"
  exit 0
fi

echo "RESULT=PASS"
echo "gate164_ready=true"
