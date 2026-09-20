#!/usr/bin/env bash
# Gate 166 — does source authorization come from governed data rather than from
# source code, and does one evaluation cost the same as five thousand?
#
# RESULT=PASS only when no module holds an authorization allowlist, the live
# warrant derives its authority from signed rows, a DIFFERENT source id with
# complete persisted decisions can be authorized without a code edit, and a
# sweep computes each fleet fact exactly once whatever the population.
#
# THIS SCRIPT MAKES NO NETWORK CALL, and does not take anyone's word for that:
# each phase replaces `socket.socket` with one that raises and counts attempts.
#
# It derives rather than accepts. Every number below is read from a phase that
# measured it on this checkout - none is passed in by a caller.
#
# The count of authorized sources is REPORTED, never required to be 1. Gate 166
# exists so that the second authorized source is a data change; a verifier that
# asserted 1 would have to be edited to permit the thing this gate was built to
# allow. What IS asserted is structural: the buckets total the population, and
# fleet facts stay O(1) per sweep at 10, 100, 1,000 and 5,000 sources.
#
# No secrets, tokens, credentials, request URLs or customer data. Counts,
# booleans and identifiers only.
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
  local value
  value="$(jget "$1" "$2")"
  if [ "$value" = "True" ]; then
    pass "${3:-$2}"
  else
    fail "${3:-$2}" "value=$value"
  fi
}

require_false() {
  local value
  value="$(jget "$1" "$2")"
  if [ "$value" = "False" ]; then
    pass "${3:-$2}"
  else
    fail "${3:-$2}" "value=$value"
  fi
}

require_zero() {
  local value
  value="$(jget "$1" "$2")"
  if [ "$value" = "0" ]; then
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

# ------------------------------------------------- 1. source authority
AUTH="$(.venv/bin/python scripts/_g166_phase_authority.py 2>&1 | tail -1)"
if ! printf '%s' "$AUTH" | grep -q '^{'; then
  echo "check=authority_phase_ran status=FAIL"
  echo "RESULT=BLOCKED"
  echo "blocker=authority_phase_did_not_report"
  exit 0
fi

require_true "$AUTH" grants_gov_authorized_by_its_data
require_false "$AUTH" derived_from_source_code_constant \
  authorization_not_from_a_constant
require_true "$AUTH" retired_beats_a_complete_ladder
require_true "$AUTH" all_refusal_states_reachable

# The negative controls. The same id, refused because its DATA changed - which
# a membership test against a frozen set could never produce.
require_true "$AUTH" same_id_without_opt_in_refused
require_true "$AUTH" same_id_unsigned_refused

# The factory unlock, stated as the property it is: a source nothing in the
# codebase names can be authorized by its records alone.
require_true "$AUTH" different_id_authorized_without_a_code_edit
require_false "$AUTH" different_id_appears_in_source_code

info grants_gov_authority_state "$(jget "$AUTH" grants_gov_state)"
info derived_authorized_source_ids "$(jget "$AUTH" derived_authorized_source_ids)"
info authority_derived_from "$(jget "$AUTH" grants_gov_derived_from)"

# ------------------------------------------------------- 2. the warrant
WARRANT="$(.venv/bin/python scripts/_g166_phase_warrant.py 2>&1 | tail -1)"
if ! printf '%s' "$WARRANT" | grep -q '^{'; then
  echo "check=warrant_phase_ran status=FAIL"
  echo "RESULT=BLOCKED"
  echo "blocker=warrant_phase_did_not_report"
  exit 0
fi

require_false "$WARRANT" module_still_defines_a_hardcoded_set \
  hardcoded_authority_absent
require_true "$WARRANT" derived_from_persisted_decisions
require_false "$WARRANT" derived_from_source_code_constant \
  warrant_authority_not_from_a_constant
require_true "$WARRANT" real_source_permitted
require_true "$WARRANT" preflight_permitted

# Enforcement SURVIVED the removal. One positive case cannot show this: the
# real source would still pass if the check had simply been deleted.
require_true "$WARRANT" every_negative_control_refused
require_false "$WARRANT" unknown_source_permitted
require_false "$WARRANT" other_real_source_permitted \
  registered_but_unauthorized_source_refused
require_false "$WARRANT" no_connection_permitted
require_true "$WARRANT" forged_state_caught
require_true "$WARRANT" forged_constant_origin_caught

info other_real_source_state "$(jget "$WARRANT" other_real_source_authority_state)"

# ---------------------------------------- 3. definition and genericity
GEN="$(.venv/bin/python scripts/_g166_phase_definition_and_genericity.py 2>&1 | tail -1)"
if ! printf '%s' "$GEN" | grep -q '^{'; then
  echo "check=genericity_phase_ran status=FAIL"
  echo "RESULT=BLOCKED"
  echo "blocker=genericity_phase_did_not_report"
  exit 0
fi

# A typo in the module list would scan fewer files and report a clean result
# about code nobody looked at.
require_true "$GEN" every_named_module_was_scanned
require_zero "$GEN" generic_layer_leaks
require_true "$GEN" runtime_source_authority_not_seed_count
require_true "$GEN" definition_usable_by_an_adapter \
  source_definition_projection_ready
require_true "$GEN" contract_names_no_store \
  definition_hides_which_store_answered
require_true "$GEN" unknown_source_not_usable
require_zero "$GEN" unclassified_fields
require_false "$GEN" consolidation_performed no_risky_schema_consolidation

info modules_scanned "$(jget "$GEN" modules_scanned)"
info adapter_descriptor_hits "$(jget "$GEN" adapter_descriptor_hits)"
info fields_classified "$(jget "$GEN" fields_classified)"
GEN_DISAGREE="$(jget "$GEN" definition_store_disagreements)"
[ "$GEN_DISAGREE" != "None" ] && info store_disagreements "$GEN_DISAGREE"

# ---------------------------------------------------------- 4. scale
SCALE="$(.venv/bin/python scripts/_g166_phase_scale.py 2>&1 | tail -1)"
if ! printf '%s' "$SCALE" | grep -q '^{'; then
  echo "check=scale_phase_ran status=FAIL"
  echo "RESULT=BLOCKED"
  echo "blocker=scale_phase_did_not_report"
  exit 0
fi

require_true "$SCALE" fleet_facts_are_o1_per_sweep \
  fleet_facts_computed_once_per_sweep
require_true "$SCALE" all_scales_invariant_clean
require_true "$SCALE" synthetic_sources_are_only_registered
require_true "$SCALE" no_synthetic_source_became_authorized
require_zero "$SCALE" rows_written scale_proof_wrote_no_rows

info fleet_computations_by_scale "$(jget "$SCALE" fleet_computations_by_scale)"
info computations_avoided_at_5000 "$(jget "$SCALE" computations_avoided_at_5000)"
info real_sweep_registered "$(jget "$SCALE" real_sweep_registered)"
info real_sweep_evaluated "$(jget "$SCALE" real_sweep_evaluated)"
# REPORTED, never asserted. See the header.
info authorized_source_count "$(jget "$SCALE" real_sweep_authorized)"
info real_sweep_counts "$(jget "$SCALE" real_sweep_counts)"
info scale_limits_not_measured "$(jget "$SCALE" not_measured)"

SWEEP_FAILS="$(jget "$SCALE" real_sweep_invariant_failures)"
if [ "$SWEEP_FAILS" = "[]" ]; then
  pass real_sweep_invariants_clean
else
  fail real_sweep_invariants_clean "value=$SWEEP_FAILS"
fi

# -------------------------------- 5. unauthorized live evidence stays 0
LIVE="$(.venv/bin/python scripts/_g166_phase_live_safety.py 2>&1 | tail -1)"
if ! printf '%s' "$LIVE" | grep -q '^{'; then
  echo "check=live_safety_phase_ran status=FAIL"
  echo "RESULT=BLOCKED"
  echo "blocker=live_safety_phase_did_not_report"
  exit 0
fi

require_zero "$LIVE" unauthorized_live_attempts
require_zero "$LIVE" unauthorized_live_rows
require_true "$LIVE" every_live_row_traces_to_a_derived_authorization
require_true "$LIVE" live_evidence_unchanged_by_gate166

info live_attempts "$(jget "$LIVE" live_attempts)"
info live_payload_rows "$(jget "$LIVE" live_payload_rows)"
info live_payload_sha256 "$(jget "$LIVE" live_payload_sha256)"

# ----------------------------------------------------- 6. the network
A_NET="$(jget "$AUTH" network_attempts_during_this_phase)"
W_NET="$(jget "$WARRANT" network_attempts_during_this_phase)"
G_NET="$(jget "$GEN" network_attempts_during_this_phase)"
S_NET="$(jget "$SCALE" network_attempts_during_this_phase)"
L_NET="$(jget "$LIVE" network_attempts_during_this_phase)"
TOTAL_NET=$(( ${A_NET:-1} + ${W_NET:-1} + ${G_NET:-1} + ${S_NET:-1} + ${L_NET:-1} ))
info network_requests_during_gate166 "$TOTAL_NET"
if [ "$TOTAL_NET" = "0" ]; then
  pass network_requests_during_gate166_is_zero
else
  fail network_requests_during_gate166_is_zero "n=$TOTAL_NET"
fi

if [ -n "$FAILED" ]; then
  echo "RESULT=FAIL"
  echo "first_failure=$FAILED"
  echo "gate166_ready=false"
  exit 0
fi

echo "RESULT=PASS"
echo "hardcoded_authority_absent=true"
echo "authorization_derived_from_persisted_decisions=true"
echo "source_definition_projection_ready=true"
echo "runtime_source_authority_not_seed_count=true"
echo "fleet_facts_computed_once_per_sweep=true"
echo "generic_layer_leaks=0"
echo "unauthorized_live_attempts=0"
echo "unauthorized_live_rows=0"
echo "network_requests=0"
echo "gate166_ready=true"
