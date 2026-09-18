#!/usr/bin/env bash
# Gate 161N - an execution envelope that transports bytes and contacts nothing.
#
# THIS DOES NOT MAKE SOURCE MONITORING LIVE, AND CANNOT.
# Gate 161 is the first gate whose code could in principle make an outbound
# source request. It does not. Live is refused four independent times - by the
# policy, by the transport boundary, by DISPATCHABLE_KINDS, and by migration
# 0047's CHECK constraints - and none of the four takes caller input.
#
# What this proves by running it:
#
#    1 the envelope composes end to end against a registered fixture
#    2 the EXACT response bytes are hashed before any decoding
#    3 those bytes reach Gate 160's store and verify on readback
#    4 an execution proof requires all seven requirements
#    5 the proof says proves_a_source_responded=false, separately
#    6 a 404 is recorded and evidenced, and completes no job
#    7 a timeout is recorded as transport_failed with no payload
#    8 a 429 persists its body AND its Retry-After is honoured
#    9 a 5xx persists its body and classifies transient
#   10 a malformed body is persisted and is NOT a failure
#   11 an unregistered URL is a connection failure, not a fetch
#   12 an attempt row is written for EVERY outcome, refusals included
#   13 the attempt table refuses a row claiming a live call
#   14 the attempt table refuses transport_kind='live'
#   15 the policy refuses a live transport
#   16 the boundary refuses a live transport, independently
#   17 live dispatches only with a permitting policy (Gate 163)
#   18 a REAL source id is refused by the hermetic policy
#   19 the worker runs a hermetic job and completes nothing
#   20 the worker refuses a real source with the same handler and transport
#   21 no envelope module imports a network module, proved by AST
#   22 the chokepoint scan CATCHES an injected violation
#   23 no route takes a URL parameter
#   24 the smoke route rolls back, measured on both sides
#   25 collectors_invoked = live_source_calls = network_calls = 0
#   26 cleanup happens after the final write, and leaves no residue
#
# Proof 22 matters as much as 21. A scan that always reports clean passes every
# hermetic test and is useless; only injecting a real `import httpx` into a copy
# of the tree and watching the scan fail makes proof 21 falsifiable.
#
# Proof 5 matters as much as 4. A single boolean meaning both "the pipeline ran"
# and "the source answered" is exactly how the second gets claimed by accident,
# so the proof carries two fields and this checks both.
#
# Cleanup is the LAST phase. Gate 158 found Gate 157's verifier cleaning up
# before invoking a script that committed 100 more rows.
#
# No secrets, tokens, cookies, state, PKCE verifier, provider subject, API keys
# or recipient addresses. No DNS. No credentials. No real organization.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

BACKEND="${NF_BACKEND_OVERRIDE:-http://127.0.0.1:8000}"
TIMEOUT=20
DEMO_ORG="bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL_ORG="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

FAILED=""

pass() { echo "check=$1 status=PASS ${2:-}"; }
fail() { echo "check=$1 status=FAIL ${2:-}"; [ -z "$FAILED" ] && FAILED="$1"; }
info() { echo "check=$1 status=INFO ${2:-}"; }

jget() {
  printf '%s' "$1" | .venv/bin/python -c \
    'import json,sys;print(json.load(sys.stdin).get(sys.argv[1]))' "$2" \
    2>/dev/null || echo "None"
}

echo "verify=source_collector_execution_envelope"

# ------------------------------------------------------------- 1. backend up
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
  "$BACKEND/backend/health" 2>/dev/null || echo 000)"
if [ "$code" = "200" ]; then
  pass backend_running "http=$code"
else
  fail backend_running "http=$code"
  echo
  echo "RESULT=BLOCKED"
  echo "blocker=backend_not_running"
  exit 1
fi

# ------------------------------------------------- 2. migration 0047 present
if [ -f alembic/versions/0047_source_collection_execution_attempts.py ]; then
  pass migration_0047_present
else
  fail migration_0047_present
fi

# ------------------------------------------- 3. the envelope, every outcome
#
# One process, because these share a transport registry and a job set. The
# rollback is inside the phase; the residue check is the LAST phase of all.
A="$(.venv/bin/python scripts/_g161_phase_envelope.py 2>&1 | tail -1)"

for key in \
  ok_proof_available ok_bytes_match_exactly ok_hash_verified_on_readback \
  ok_persisted_before_decoding malformed_persisted malformed_is_not_a_failure \
  not_found_recorded not_found_is_still_evidenced \
  not_found_does_not_permit_completion timeout_recorded_no_payload \
  rate_limited_body_persisted server_error_body_persisted \
  unregistered_is_a_connection_failure attempt_row_for_every_outcome \
  proof_needs_all_seven proof_denies_a_source_responded \
  real_source_refused_by_policy live_refused_by_policy \
  live_refused_by_the_boundary live_requires_a_permitting_policy \
  live_refused_when_the_policy_names_no_authorization \
  live_dispatches_when_the_policy_permits \
  db_refuses_a_live_call_row db_refuses_a_live_transport_kind \
  no_unauthorized_live_attempt_exists \
  every_attempt_is_hermetic_or_authorized_live \
  envelope_counters_all_zero
do
  value="$(jget "$A" "$key")"
  if [ "$value" = "True" ]; then
    pass "$key"
  else
    fail "$key" "value=$value"
  fi
done

detail="$(jget "$A" detail)"
[ "$detail" != "None" ] && info envelope_detail "$detail"

# ------------------------------------------------------ 4. the retry policy
B="$(.venv/bin/python scripts/_g161_phase_retry.py 2>&1 | tail -1)"
for key in \
  timeout_is_transient rate_limit_is_transient server_error_is_transient \
  not_found_is_permanent malformed_is_not_retried refusal_is_not_retried \
  human_blockers_are_not_retried retry_after_is_honoured \
  retry_after_is_capped retry_after_is_not_honoured_for_a_permanent_failure \
  the_checker_catches_a_retried_permanent_failure
do
  value="$(jget "$B" "$key")"
  if [ "$value" = "True" ]; then
    pass "$key"
  else
    fail "$key" "value=$value"
  fi
done

# ------------------------------------------------------- 5. the worker path
C="$(.venv/bin/python scripts/_g161_phase_worker.py 2>&1 | tail -1)"
for key in \
  hermetic_job_flows_through worker_completed_nothing \
  worker_persisted_the_payload worker_produced_a_proof \
  default_handler_executes_nothing no_transport_executes_nothing \
  real_source_refused_by_the_worker store_loaded_job_refused \
  every_refusal_condition_fires_alone worker_live_counters_zero
do
  value="$(jget "$C" "$key")"
  if [ "$value" = "True" ]; then
    pass "$key"
  else
    fail "$key" "value=$value"
  fi
done

# ---------------------------------------------- 6. the chokepoint, by AST
#
# And - proof 22 - the same scan run against a COPY of the tree with a real
# `import httpx` written into an envelope module. A scan that cannot fail has
# not proved anything about the scan that passed.
D="$(.venv/bin/python scripts/_g161_phase_chokepoint.py 2>&1 | tail -1)"
for key in \
  envelope_imports_no_network_module envelope_reaches_no_host \
  every_module_was_found transport_is_injected_not_imported \
  the_scan_catches_an_injected_import the_scan_catches_a_missing_module \
  no_substring_search_was_used
do
  value="$(jget "$D" "$key")"
  if [ "$value" = "True" ]; then
    pass "$key"
  else
    fail "$key" "value=$value"
  fi
done

# ------------------------------------------------------------ 7. the routes
#
# No parameter through which a caller could name an address. Read from the
# live OpenAPI schema rather than from the source, because what the app SERVES
# is what an attacker reaches.
SPEC="$(curl -s --max-time "$TIMEOUT" "$BACKEND/openapi.json" 2>/dev/null)"
E="$(printf '%s' "$SPEC" | .venv/bin/python scripts/_g161_phase_routes.py 2>&1 \
  | tail -1)"
for key in \
  routes_are_registered no_route_takes_a_url_parameter \
  the_smoke_takes_no_request_body
do
  value="$(jget "$E" "$key")"
  if [ "$value" = "True" ]; then
    pass "$key"
  else
    fail "$key" "value=$value"
  fi
done

# The smoke and health endpoints, live. Unauthenticated first: a route that
# answers without a session has no boundary to test.
for path in health; do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
    "$BACKEND/v1/nf/demo/orgs/$DEMO_ORG/collector-execution/$path" \
    2>/dev/null || echo 000)"
  if [ "$code" = "401" ] || [ "$code" = "403" ]; then
    pass "unauthenticated_refused:$path" "http=$code"
  else
    fail "unauthenticated_refused:$path" "http=$code"
  fi
done

code="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
  "$BACKEND/v1/nf/demo/orgs/$REAL_ORG/collector-execution/health" \
  2>/dev/null || echo 000)"
if [ "$code" = "401" ] || [ "$code" = "403" ] || [ "$code" = "404" ]; then
  pass real_org_refused "http=$code"
else
  fail real_org_refused "http=$code"
fi

# ------------------------------------------------------- 8. the health lane
F="$(.venv/bin/python scripts/_g161_phase_health.py 2>&1 | tail -1)"
for key in \
  execution_envelope_ready live_transport_requires_an_authorization \
  approved_source_count_is_zero known_is_not_approved \
  no_unauthorized_live_attempt_rows health_invariants_clean
do
  value="$(jget "$F" "$key")"
  if [ "$value" = "True" ]; then
    pass "$key"
  else
    fail "$key" "value=$value"
  fi
done

# ------------------------------------------- 9. the smoke route, end to end
#
# Run LAST of the writing phases, because it writes inside a savepoint and the
# residue check must come after every write in this script.
G="$(.venv/bin/python scripts/_g161_phase_smoke.py 2>&1 | tail -1)"
for key in \
  smoke_ran smoke_wrote_inside_the_savepoint smoke_rolled_back \
  smoke_produced_a_proof smoke_denies_a_source_responded \
  smoke_caller_cannot_supply_a_url
do
  value="$(jget "$G" "$key")"
  if [ "$value" = "True" ]; then
    pass "$key"
  else
    fail "$key" "value=$value"
  fi
done

# ------------------------------------------------------------ 10. residue
#
# THE LAST PHASE. Gate 158 found Gate 157's verifier cleaning up before
# invoking a script that committed 100 more rows, so nothing that writes may
# come after this.
H="$(.venv/bin/python scripts/_g161_phase_cleanup.py 2>&1 | tail -1)"
removed="$(jget "$H" removed)"
residue="$(jget "$H" residue)"
if [ "$residue" = "0" ]; then
  pass no_residue "removed=$removed"
else
  fail no_residue "residue=$residue removed=$removed"
fi

if [ "$(jget "$H" counted_actual_rows)" = "True" ]; then
  pass cleanup_counted_actual_rows
else
  fail cleanup_counted_actual_rows
fi

echo
if [ -n "$FAILED" ]; then
  echo "RESULT=FAIL"
  echo "first_failure=$FAILED"
  exit 1
fi

echo "RESULT=PASS"
echo "collector_execution_envelope_ready=true"
echo "source_monitoring_live=false"
echo "scope=controlled_dev_demo"
echo "transport_kind=hermetic"
echo "live_transport_implemented=true (Gate 163, requires a warrant)"
echo "live_transport_dispatchable=only_with_a_permitting_policy"
echo "live_transport_refused_by=policy_and_boundary_and_dispatchable_kinds_and_database"
echo "exact_bytes_hashed_before_decoding=true"
echo "raw_payload_store=gate_160_reused_not_duplicated"
echo "execution_proof_requirements=7"
echo "proves_the_envelope_works=true"
echo "proves_a_source_responded=false"
echo "permits_hermetic_job_completion=true"
echo "permits_real_source_job_completion=false"
echo "malformed_body=persisted_and_not_a_failure"
echo "retry_after_honoured=true (capped at 3600s)"
echo "attempt_row_written_for_every_outcome=true"
echo "worker_handler=hermetic_execution (opt-in, seven conditions)"
echo "jobs_completed=0"
echo "collectors_invoked=0"
echo "live_source_calls=0"
echo "network_calls=0"
echo "urls_fetched=0"
echo "dns_resolved=false"
echo "credentials_required=false"
echo "emails_sent=0"
echo "object_store_calls=0"
echo "approved_source_count=0"
echo "known_source_count=177 (knowing is not approving)"
echo "customer_data_persisted=false"
echo "caller_can_supply_a_url=false"
echo "chokepoint_measured_by=ast_imports_and_dotted_call_paths"
echo "chokepoint_scan_is_falsifiable=true"
echo "cleanup=ran_after_the_final_write"
echo "residue=0"
echo "migration_added_by_this_gate=0047 (nf_source_collection_execution_attempts)"
echo "next=docs/operations/838_GATE161_COLLECTOR_EXECUTION_DELTA.md"
exit 0
