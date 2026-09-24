#!/usr/bin/env bash
# Gate 179 — can a real customer understand and use this, and does it hold at
# fleet scale?
#
# RESULT=PASS only when every recommendation comes from the CANONICAL GRAPH
# rather than a hand-made spark; when each one can say why it is relevant, why
# the organisation appears eligible or uncertain, what evidence supports that
# and what remains unknown; when watch/dismiss/pursue are durable decisions
# naming an actor; when dismissing hides a row from ONE feed and changes
# nothing the graph knows; when a customer cannot reach source activation, a
# plane toggle, a verifier surface or an entitlement override; and when a
# thousand-source fleet does not turn into an opportunity x tenant x document
# catastrophe.
#
# THE MEASUREMENT THIS GATE FLIPS
#
# The 179A survey found:
#
#   buyer_feed_depends_on_hand_made_sparks = true
#   api_imports_canonical_intelligence     = false
#   canonical_modules_with_no_importer     = [canonical_opportunity_store,
#                                             document_fact_extraction]
#
# Nine gates of intelligence, and not one of them reached a buyer. That is
# what canonical_graph_feeds_customer=true is asserting has changed.
#
# THIS SCRIPT MAKES NO NETWORK CALL and touches no real organisation. The demo
# story runs only on the protected demo organisation and refuses any other id.
#
# WHAT THE 1,000-SOURCE REHEARSAL IS NOT
#
#   claims_real_thousand_source_coverage = false
#
# It is an ARCHITECTURE rehearsal on a synthetic fleet. NativeForge monitors
# 40 real sources and 3 active ones. "We rehearsed 1,000 sources" and "we
# monitor 1,000 sources" are a sentence apart and a company apart.
#
# CONCURRENCY
#
#   postgres_concurrency_status = UNKNOWN_NOT_MEASURED
#
# The database here is SQLite. It proves single-writer serialisation, that the
# schema's constraints hold under write, and index selection for these query
# shapes. It proves nothing about Postgres row-level locking, concurrent
# writer throughput, or contention under load, and no such harness has been
# run. 179K forbids claiming otherwise.
#
# What is structural and what is INFO:
#
#   asserted   the journey contract, canonical-graph sourcing, the four
#              explanations, durable decisions and tenant-scoped dismissal,
#              the dashboard, customisation and personal overrides, the
#              customer/operator boundary, trust without internals, the demo
#              story, the rehearsal, indexed read paths, self-health
#              specificity, 178 semantics, zero network
#   INFO       fleet composition, query milliseconds, memory, checklist size
#
# The UX checklist is INFO and arrives UNWALKED. Claude Code has not navigated
# a UI; a checklist pre-marked PASS would answer the question it exists to ask.
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
require_at_least() {
  local v; v="$(jget "$1" "$2")"
  if [ "$v" != "None" ] && [ "$v" -ge "$3" ] 2>/dev/null; then
    pass "${4:-$2}" "value=$v"
  else
    fail "${4:-$2}" "expected>=$3 got=$v"
  fi
}

run_phase() {
  local out
  out="$(.venv/bin/python "$1" 2>&1 | tail -1)"
  printf '%s' "$out" | grep -q '^{' || return 1
  printf '%s' "$out"
}

echo "=== Gate 179: customer experience, customisation and industrial scale ==="

PROOF="$(run_phase scripts/_g179_phase_proof.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=proof_phase_did_not_report"; exit 0; }

REHEARSAL="$(run_phase scripts/_g179_phase_rehearsal.py)" || {
  echo "RESULT=BLOCKED"; echo "blocker=rehearsal_phase_did_not_report"; exit 0; }

# ---------------- 179A: the journey ---------------------------------------
require_true "$PROOF" customer_journey_contract_ready

# ---------------- 179B: the feed comes from the graph ---------------------
require_true "$PROOF" buyer_recommendation_feed_ready
# The measurement this gate flips. See the header.
require_true "$PROOF" canonical_graph_feeds_customer

# ---------------- 179C: it explains itself --------------------------------
require_true "$PROOF" why_relevant_explainable
require_true "$PROOF" eligibility_explainable
require_true "$PROOF" document_evidence_explainable
require_true "$PROOF" uncertainty_reaches_the_customer

# ---------------- 179D: durable decisions ---------------------------------
require_true "$PROOF" watch_dismiss_pursue_ready
require_true "$PROOF" dismiss_does_not_delete_intelligence

# ---------------- 179E/F: dashboard and customisation ---------------------
require_true "$PROOF" customer_dashboard_ready
require_true "$PROOF" tenant_customization_persistent
require_true "$PROOF" user_overrides_separate

# ---------------- 179G/H: surfaces and trust ------------------------------
require_true "$PROOF" customer_operator_surfaces_separated
require_true "$PROOF" trust_experience_ready

# ---------------- 179L/M: the demo story and the checklist ----------------
require_true "$PROOF" demo_customer_story_ready
require_true "$PROOF" demo_story_refuses_the_real_organization
require_true "$PROOF" demo_story_is_deterministic
# The checklist must arrive UNWALKED, or it is answering its own question.
require_false "$PROOF" ux_checklist_results_prefilled
require_false "$PROOF" ux_checklist_customer_ready_prefilled
info ux_checklist_step_count "value=$(jget "$PROOF" ux_checklist_step_count)"

# ---------------- 179I: the rehearsal -------------------------------------
require_true "$REHEARSAL" target_is_scratch rehearsal_ran_against_scratch_db
require_at_least "$REHEARSAL" source_count 1000 source_count
require_value "$REHEARSAL" source_kind_count 12 source_kind_count
require_true "$REHEARSAL" every_kind_represented
require_true "$REHEARSAL" every_health_state_represented
require_true "$REHEARSAL" one_lease_per_source
require_true "$REHEARSAL" fair_distribution
require_at_least "$REHEARSAL" sources_refused_by_state 1 sources_refused_by_state
require_true "$REHEARSAL" thousand_source_rehearsal_ready
# Asserted FALSE on purpose. See the header.
require_false "$REHEARSAL" claims_real_thousand_source_coverage
require_true "$REHEARSAL" is_architecture_rehearsal

info fleet_by_health "value=$(jget "$REHEARSAL" sources_by_health)"
info real_sources_monitored "value=$(jget "$REHEARSAL" real_sources_monitored)"
info real_sources_active "value=$(jget "$REHEARSAL" real_sources_active)"

# ---------------- 179J: bounded work, indexed reads -----------------------
require_true "$REHEARSAL" global_intelligence_not_recomputed_per_tenant
require_true "$REHEARSAL" tenant_matching_is_bounded
require_true "$REHEARSAL" no_cartesian_catastrophe
require_true "$REHEARSAL" every_recommendation_explains_itself
require_true "$REHEARSAL" feed_sourced_from_canonical_graph
require_empty_list "$REHEARSAL" customer_zero_row_queries
require_empty_list "$REHEARSAL" customer_unindexed_queries
require_true "$REHEARSAL" scan_detector_still_fires
require_true "$REHEARSAL" critical_customer_queries_indexed
require_true "$PROOF" every_customer_query_is_tenant_scoped

info cartesian_if_done_naively "value=$(jget "$REHEARSAL" cartesian_if_done_naively)"
info cartesian_avoided_factor "value=$(jget "$REHEARSAL" cartesian_avoided_factor)"
info slowest_customer_query_ms "value=$(jget "$REHEARSAL" slowest_customer_query_ms)"
info rehearsal_peak_memory_mb "value=$(jget "$REHEARSAL" peak_memory_mb)"

# ---------------- 179K: what the database proves --------------------------
# Reported, never asserted true. See the header.
echo "check=postgres_concurrency_status status=INFO value=$(jget "$REHEARSAL" postgres_concurrency_status)"
info sqlite_proves "value=$(jget "$REHEARSAL" sqlite_proves)"
info sqlite_does_not_prove "value=$(jget "$REHEARSAL" sqlite_does_not_prove)"

# ---------------- 179N: self health ---------------------------------------
require_true "$PROOF" customer_self_health_ready
require_value "$PROOF" self_health_detector_count 9 self_health_detector_count

# ---------------- what came before must still hold ------------------------
require_true "$PROOF" gate178_semantics_preserved

# ---------------- the boundaries ------------------------------------------
require_zero "$PROOF" network_requests proof_phase_network_requests
require_zero "$REHEARSAL" network_requests rehearsal_phase_network_requests
require_zero "$PROOF" fixture_residue

require_true "$PROOF" gate179_ready

echo
if [ -n "$FAILED" ]; then
  echo "RESULT=FAIL"
  echo "first_failure=$FAILED"
  exit 1
fi

echo "RESULT=PASS"
echo "customer_journey_contract_ready=true"
echo "buyer_recommendation_feed_ready=true"
echo "canonical_graph_feeds_customer=true"
echo "why_relevant_explainable=true"
echo "eligibility_explainable=true"
echo "document_evidence_explainable=true"
echo "watch_dismiss_pursue_ready=true"
echo "customer_dashboard_ready=true"
echo "tenant_customization_persistent=true"
echo "user_overrides_separate=true"
echo "customer_operator_surfaces_separated=true"
echo "trust_experience_ready=true"
echo "demo_customer_story_ready=true"
echo "thousand_source_rehearsal_ready=true"
echo "global_intelligence_not_recomputed_per_tenant=true"
echo "critical_customer_queries_indexed=true"
echo "customer_self_health_ready=true"
echo "postgres_concurrency_status=UNKNOWN_NOT_MEASURED"
echo "gate178_semantics_preserved=true"
echo "network_requests=0"
echo "fixture_residue=0"
echo "gate179_ready=true"
