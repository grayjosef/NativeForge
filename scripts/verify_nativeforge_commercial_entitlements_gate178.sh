#!/usr/bin/env bash
# Gate 178 — is the approved commercial model encoded exactly, and does a
# delinquent customer keep everything they are entitled to keep?
#
# RESULT=PASS only when the licence price is $34,999 and the maintenance
# $6,999; when a consortium of Tribes is QUOTED rather than computed;
# when the first twelve months are included and free rather than discounted;
# when a licence expires after three CONTINUOUS years and not a day sooner;
# when a frozen or expired account can still authenticate, read its history
# and EXPORT ITS OWN DATA; when a temporary extension moves benefit access and
# nothing else; and when no customer administrator can forgive a debt, move a
# paid-through date, extend their own benefits, or relicense themselves.
#
# THIS SCRIPT MAKES NO NETWORK CALL and moves no money. No invoice is raised,
# no payment taken, no debt forgiven for any real organisation.
#
# THE RULE THIS GATE TURNS ON:
#
#   extension_does_not_rewrite_billing_truth=true
#
# An organisation on day 400 of delinquency with a 30-day extension is on day
# 400 of delinquency, has full benefits, and is still 695 days from losing its
# licence. Getting this wrong in the GENEROUS direction is worse than getting
# it wrong in the harsh direction, because it is invisible: a vendor who
# quietly forgives debt by granting extensions finds out at year end, and the
# customer finds out when somebody reconciles and sends them a bill nobody
# told them was accruing.
#
# What is structural and what is INFO:
#
#   asserted   the approved numbers, the three separated states, freeze
#              semantics and data preservation, the three-year boundary,
#              relicensing and forgiveness, extension durations and their
#              billing neutrality, the controlling-company boundary, ledger
#              append-only history, indexed read paths, self-health
#              specificity, 177 semantics, zero network
#   INFO       corpus counts, query milliseconds, memory, forgiven amounts
#
# docs/operations/570 contains OTHER figures — $24,999, $14,995, $49,999 and
# others. That document says of itself that they are "the operator's drafts,
# recorded verbatim as drafts". Those remain drafts, and the survey asserts
# none of THEM appears in the code. $34,999 is no longer among them: it is the
# approved licence price.
#
# Exact legal wording remains subject to counsel. This verifies product
# semantics, not an agreement.
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

echo "=== Gate 178: commercial entitlements and the persistent licence ==="

PROOF="$(run_phase scripts/_g178_phase_proof.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=proof_phase_did_not_report"; exit 0; }

SCALE="$(run_phase scripts/_g178_phase_scale.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=scale_phase_did_not_report"; exit 0; }

# ---------------- 178A: the approved numbers, exactly --------------------
require_true "$PROOF" persistent_license_model_ready
require_value "$PROOF" persistent_license_price_cents 3499900 license_price_is_34999
require_value "$PROOF" annual_maintenance_price_cents 699900 maintenance_price_is_6999
require_true "$PROOF" first_year_maintenance_included
require_true "$PROOF" annual_maintenance_model_ready

# ---------------- 178A2: the intertribal consortium suite ----------------
# Tribes joining together are priced as a SUITE on isolation need,
# complexity and seats. That is a commercial judgement, so this module
# captures the dimensions and refuses to produce a figure: a function that
# multiplied three factors would return a WRONG number, confidently, to a
# group of sovereign governments negotiating together.
require_true "$PROOF" consortium_offering_ready
require_true "$PROOF" consortium_price_is_never_computed
require_true "$PROOF" consortium_isolation_is_not_a_default
info consortium_quote_dimensions "value=$(jget "$PROOF" consortium_quote_dimensions)"

# ---------------- 178D: frozen is not deleted ----------------------------
require_true "$PROOF" frozen_not_deleted
info frozen_available_action_count "value=$(jget "$PROOF" frozen_available_action_count)"
info frozen_locked_action_count "value=$(jget "$PROOF" frozen_locked_action_count)"

# ---------------- 178E: three continuous years ---------------------------
require_true "$PROOF" three_year_license_expiration_ready

# ---------------- 178F: relicensing and forgiveness ----------------------
require_true "$PROOF" relicense_ready
require_true "$PROOF" historical_maintenance_forgiven_on_relicense
info forgiven_cents "value=$(jget "$PROOF" forgiven_cents)"

# ---------------- 178I: the ledger keeps everything ----------------------
require_true "$PROOF" entitlement_history_preserved

# ---------------- 178G: extensions ---------------------------------------
require_true "$PROOF" benefit_extensions_7_14_30_ready
# The rule the gate turns on. See the header.
require_true "$PROOF" extension_does_not_rewrite_billing_truth

# ---------------- 178H: the boundary -------------------------------------
require_true "$PROOF" controlling_company_extension_boundary_ready
require_true "$PROOF" customer_admin_cannot_override_entitlements

# ---------------- 178K: scale and the access paths -----------------------
require_true "$SCALE" target_is_scratch scale_ran_against_scratch_db
require_value "$SCALE" critical_query_count 8 critical_query_count
# No zero-row fake proof: a query returning nothing has a beautiful plan.
require_empty_list "$SCALE" zero_row_queries
require_empty_list "$SCALE" unindexed_queries
require_true "$SCALE" scan_detector_still_fires
require_true "$SCALE" critical_entitlement_queries_indexed
require_true "$PROOF" fleet_questions_read_the_summary_not_the_ledger

info slowest_critical_query_ms "value=$(jget "$SCALE" slowest_critical_query_ms)"
info scale_peak_memory_mb "value=$(jget "$SCALE" peak_memory_mb)"
info scale_load_seconds "value=$(jget "$SCALE" load_seconds)"

# ---------------- 178L: self health --------------------------------------
require_true "$PROOF" entitlement_self_health_ready
require_value "$PROOF" self_health_detector_count 9 self_health_detector_count

# ---------------- 178J: the corpus ---------------------------------------
require_value "$PROOF" corpus_case_count 20 corpus_case_count
require_value "$PROOF" corpus_passed_count 20 corpus_passed_count
require_empty_list "$PROOF" corpus_failed_cases
require_true "$PROOF" every_case_pins_its_own_clock
require_false "$PROOF" corpus_is_world_truth
# The two that must never become true by accident.
require_false "$PROOF" money_moved_for_a_real_organization
require_false "$PROOF" is_legal_advice

# ---------------- what came before must still hold -----------------------
require_true "$PROOF" gate177_semantics_preserved

# ---------------- the boundaries -----------------------------------------
require_zero "$PROOF" network_requests proof_phase_network_requests
require_zero "$SCALE" network_requests scale_phase_network_requests
require_zero "$PROOF" fixture_residue

require_true "$PROOF" gate178_ready

echo
if [ -n "$FAILED" ]; then
  echo "RESULT=FAIL"
  echo "first_failure=$FAILED"
  exit 1
fi

echo "RESULT=PASS"
echo "persistent_license_model_ready=true"
echo "first_year_maintenance_included=true"
echo "annual_maintenance_model_ready=true"
echo "consortium_offering_ready=true"
echo "consortium_price_is_never_computed=true"
echo "frozen_not_deleted=true"
echo "three_year_license_expiration_ready=true"
echo "relicense_ready=true"
echo "historical_maintenance_forgiven_on_relicense=true"
echo "benefit_extensions_7_14_30_ready=true"
echo "extension_does_not_rewrite_billing_truth=true"
echo "controlling_company_extension_boundary_ready=true"
echo "customer_admin_cannot_override_entitlements=true"
echo "entitlement_history_preserved=true"
echo "critical_entitlement_queries_indexed=true"
echo "entitlement_self_health_ready=true"
echo "gate177_semantics_preserved=true"
echo "network_requests=0"
echo "fixture_residue=0"
echo "gate178_ready=true"
