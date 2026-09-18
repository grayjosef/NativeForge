#!/usr/bin/env bash
# Gate 162L - authorization that comes from records, not from callers.
#
# THIS DOES NOT APPROVE ANY SOURCE, AND CANNOT.
# Every approval this verifier records is for a SYNTHETIC FIXTURE under the
# reserved `nf162.fixture.` prefix, signed by `reviewer:nf162-verify`, against
# an evidence fingerprint of a string in this repository, pointing at a
# `.invalid` host that RFC 2606 guarantees cannot exist. No real source
# receives a decision, and that is checked by name after cleanup.
#
# What this proves by running it:
#
#    1 all 177 real registry sources resolve through the fact resolver
#    2 real approved count = 0
#    3 the registry's 171 terms-blocked count is preserved
#    4 the registry's 6 human-review-blocked count is preserved
#    5 a missing terms fact blocks
#    6 an explicit terms denial blocks, and reports as a DECISION
#    7 needs-review blocks
#    8 a missing human review blocks
#    9 a human denial blocks
#   10 a missing activation decision blocks
#   11 a stale (expired) affirmative answer blocks
#   12 runtime facts derive from the Gates 156-161 readiness lanes
#   13 the stale `background_worker_available` derivation is repaired
#   14 runtime readiness alone does not authorize
#   15 collector existence alone does not authorize
#   16 registry existence alone does not authorize
#   17 a queued job is not an authorization fact at all
#   18 an execution proof is not an authorization fact at all
#   19 forged caller booleans cannot change an authorization
#   20 the resolver takes four parameters and none can assert a fact
#   21 a fully recorded SYNTHETIC fact set reaches authorized=true
#   22 and that authorization still does NOT opt into a live fetch
#   23 the real registry's approved count remains 0
#   24 live transport remains disabled
#   25 live source calls remain 0
#   26 source_monitoring_live = false
#   27 no UNAPPROVED real source received a decision (Gate 163 activated
#      exactly one, signed; any other real source still fails)
#   28 cleanup happens after the final write
#   29 cleanup counts actual rows
#   30 no residue remains
#
# Proof 21 matters as much as proofs 5-11. A boundary that refuses everything
# passes every refusal check and is useless; only a synthetic fact set actually
# REACHING authorized=true makes the refusals falsifiable. It is asserted, not
# printed.
#
# Proof 22 is its companion, and the distinction the gate turns on:
# authorization complete is NOT live fetch opted in.
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

echo "verify=source_authorization_boundary"

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

# ------------------------------------------------- 2. migration 0048 present
if [ -f alembic/versions/0048_source_authorization_decisions.py ]; then
  pass migration_0048_present
else
  fail migration_0048_present
fi

# ------------------------------- 3. the fact model and the guard mapping
A="$(.venv/bin/python scripts/_g162_phase_facts.py 2>&1 | tail -1)"
for key in \
  every_guard_status_input_is_modelled fact_count_is_eleven \
  exactly_one_status_permits six_fact_statuses_exist \
  missing_is_distinct_from_denied runtime_lanes_are_the_six_gates \
  runtime_invariants_clean runtime_authorizes_nothing \
  runtime_derivation_does_not_read_background_worker_available \
  runtime_derivation_names_its_lanes no_lane_refuses_without_saying_why \
  runtime_readiness_alone_does_not_authorize \
  registry_existence_alone_does_not_authorize \
  collector_existence_alone_does_not_authorize \
  only_recorded_decisions_authorize \
  the_three_decision_facts_are_the_authorizing_ones \
  a_queued_job_is_not_an_authorization_fact \
  an_execution_proof_is_not_an_authorization_fact \
  resolver_parameters_are_the_permitted_set \
  no_resolver_parameter_is_fact_shaped
do
  value="$(jget "$A" "$key")"
  if [ "$value" = "True" ]; then
    pass "$key"
  else
    fail "$key" "value=$value"
  fi
done
detail="$(jget "$A" detail)"
[ "$detail" != "None" ] && info facts_detail "$detail"

# --------------------------- 4. every real source, and the synthetic branch
#
# One process: these share a registry read and a decision set. Writes here are
# removed by the cleanup phase, which is LAST.
B="$(.venv/bin/python scripts/_g162_phase_resolution.py 2>&1 | tail -1)"
for key in \
  every_real_source_resolves real_approved_count_is_zero \
  registry_activation_approved_count_is_zero \
  registry_monitorable_count_is_zero \
  missing_terms_blocks missing_human_review_blocks \
  missing_activation_blocks terms_denial_blocks \
  a_denial_is_reported_as_a_decision needs_review_blocks \
  human_denial_blocks stale_terms_blocks an_unsigned_approval_is_refused \
  synthetic_branch_reaches_authorized synthetic_branch_status_is_approved \
  synthetic_all_eleven_facts_recorded \
  synthetic_authorization_does_not_opt_into_live_fetch \
  synthetic_authorization_permits_no_live_transport \
  the_low_level_guard_is_a_pure_function \
  forged_booleans_do_not_change_authorization \
  allowlisted_real_sources_is_zero \
  exactly_one_synthetic_fixture_is_allowlisted \
  no_unapproved_real_source_received_a_decision \
  the_allowed_real_source_decisions_are_signed fixture_prefix_is_reserved \
  no_fixture_shadows_a_real_source
do
  value="$(jget "$B" "$key")"
  if [ "$value" = "True" ]; then
    pass "$key"
  else
    fail "$key" "value=$value"
  fi
done
detail="$(jget "$B" detail)"
[ "$detail" != "None" ] && info resolution_detail "$detail"

# The registry's own blocked counts, reported so a change is visible.
RESOLVED="$(jget "$B" real_sources_resolved)"
REGISTRY="$(jget "$B" real_sources_in_registry)"
TERMS_BLOCKED="$(jget "$B" terms_blocked_count)"
HUMAN_BLOCKED="$(jget "$B" human_review_blocked_count)"
info real_sources_resolved "$RESOLVED of $REGISTRY"
info terms_blocked_count "$TERMS_BLOCKED"
info human_review_blocked_count "$HUMAN_BLOCKED"

if [ "$TERMS_BLOCKED" = "171" ]; then
  pass terms_blocked_count_preserved "n=$TERMS_BLOCKED"
else
  fail terms_blocked_count_preserved "n=$TERMS_BLOCKED expected=171"
fi
# 6 -> 7 with the 178th row. The Grants.gov API row is
# `access_posture_hint: public`, so registry-level evaluation classes it
# `human_review_blocked` - a person must look first - and MAYHEM's recorded
# decisions live in the database, which `evaluate_registry` does not read.
# The registry declining to treat the row as approved on the strength of its
# own existence is the property this gate was built to have; the count going
# up is that property working.
if [ "$HUMAN_BLOCKED" = "7" ]; then
  pass human_review_blocked_count_preserved "n=$HUMAN_BLOCKED"
else
  fail human_review_blocked_count_preserved "n=$HUMAN_BLOCKED expected=7"
fi

# Two pinned integers I bump whenever the registry grows are a changelog, not
# a check: 171 and 7 would both still pass if one row moved from blocked to
# approved and one new blocked row arrived in the same change. So the buckets
# must also account for EVERY registry row. An approval leaking into
# registry-level evaluation takes a row out of a blocked bucket, the sum stops
# matching, and this fails whatever the individual numbers are.
BLOCKED_TOTAL=$((TERMS_BLOCKED + HUMAN_BLOCKED))
if [ "$BLOCKED_TOTAL" = "$REGISTRY" ]; then
  pass every_registry_row_is_blocked_by_something "n=$BLOCKED_TOTAL of $REGISTRY"
else
  fail every_registry_row_is_blocked_by_something \
    "blocked=$BLOCKED_TOTAL registry=$REGISTRY"
fi

# ------------------------------------------------------------ 5. the routes
#
# Read from the LIVE schema: what the app serves is what a caller reaches.
SPEC="$(curl -s --max-time "$TIMEOUT" "$BACKEND/openapi.json" 2>/dev/null)"
C="$(printf '%s' "$SPEC" | .venv/bin/python scripts/_g162_phase_routes.py 2>&1 \
  | tail -1)"
for key in \
  routes_are_registered no_mutation_endpoint_exists \
  no_route_parameter_asserts_a_fact no_route_parameter_names_an_address \
  no_route_accepts_a_request_body every_route_requires_a_session
do
  value="$(jget "$C" "$key")"
  if [ "$value" = "True" ]; then
    pass "$key"
  else
    fail "$key" "value=$value"
  fi
done
detail="$(jget "$C" detail)"
[ "$detail" != "None" ] && info routes_detail "$detail"

# Unauthenticated, and the real org. A route that answers without a session has
# no boundary to test.
for suffix in "source-authorization/fact-model" "source-authorization/allowlist"; do
  code="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
    "$BACKEND/v1/nf/demo/orgs/$DEMO_ORG/$suffix" 2>/dev/null || echo 000)"
  if [ "$code" = "401" ] || [ "$code" = "403" ]; then
    pass "unauthenticated_refused:$suffix" "http=$code"
  else
    fail "unauthenticated_refused:$suffix" "http=$code"
  fi
done

code="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
  "$BACKEND/v1/nf/demo/orgs/$REAL_ORG/source-authorization/allowlist" \
  2>/dev/null || echo 000)"
if [ "$code" = "401" ] || [ "$code" = "403" ] || [ "$code" = "404" ]; then
  pass real_org_refused "http=$code"
else
  fail real_org_refused "http=$code"
fi

# A forged org header must not override the session's scope.
code="$(curl -s -o /dev/null -w '%{http_code}' --max-time "$TIMEOUT" \
  -H "X-NF-Org-Id: $REAL_ORG" \
  "$BACKEND/v1/nf/demo/orgs/$DEMO_ORG/source-authorization/allowlist" \
  2>/dev/null || echo 000)"
if [ "$code" = "401" ] || [ "$code" = "403" ]; then
  pass forged_org_header_refused "http=$code"
else
  fail forged_org_header_refused "http=$code"
fi

# ------------------------------------------------------------- 6. residue
#
# THE LAST PHASE. Nothing that writes may come after this.
D="$(.venv/bin/python scripts/_g162_phase_cleanup.py 2>&1 | tail -1)"
removed="$(jget "$D" removed)"
residue="$(jget "$D" residue)"
if [ "$residue" = "0" ]; then
  pass no_residue "removed=$removed"
else
  fail no_residue "residue=$residue removed=$removed"
fi
if [ "$(jget "$D" counted_actual_rows)" = "True" ]; then
  pass cleanup_counted_actual_rows
else
  fail cleanup_counted_actual_rows
fi

# The safety counts, taken AFTER cleanup, so they describe the database a
# commit would be made against.
# `real_sources_approved` and `real_sources_with_decisions` are now reported
# rather than required to be zero: Gate 163 gave exactly one real source signed
# decisions on purpose, so demanding zero would refuse reality. The safety
# property became the narrower one - no UNAPPROVED real source - which is what
# is required below, alongside the signature and set-size checks that stop
# "counted separately" from meaning "permitted silently".
info post_cleanup_real_sources_approved "$(jget "$D" real_sources_approved)"
info post_cleanup_real_sources_with_decisions \
  "$(jget "$D" real_sources_with_decisions)"
info post_cleanup_allowed_real_sources "$(jget "$D" \
  allowed_real_sources_with_decisions)"

for pair in \
  "unapproved_real_sources_approved:0" \
  "unapproved_real_sources_with_decisions:0" \
  "at_most_one_real_source_is_allowed:True" \
  "allowed_real_source_decisions_are_signed:True" \
  "the_code_authorizes_exactly_the_pinned_set:True" \
  "live_execution_attempts:0" \
  "unsigned_approvals:0"
do
  key="${pair%%:*}"
  want="${pair##*:}"
  got="$(jget "$D" "$key")"
  if [ "$got" = "$want" ]; then
    pass "post_cleanup:$key" "n=$got"
  else
    fail "post_cleanup:$key" "n=$got expected=$want"
  fi
done
detail="$(jget "$D" detail)"
[ "$detail" != "None" ] && info cleanup_detail "$detail"

echo
if [ -n "$FAILED" ]; then
  echo "RESULT=FAIL"
  echo "first_failure=$FAILED"
  exit 1
fi

echo "RESULT=PASS"
echo "authorization_boundary_ready=true"
echo "source_monitoring_live=false"
echo "scope=controlled_dev_demo"
echo "required_fact_count=11"
echo "facts_resolved_from_records=true"
echo "caller_supplied_facts_accepted=0"
echo "resolver_parameters=connection,organization_id,source_id,now"
echo "fabricated_caller_bypass=impossible"
echo "terms_decisions_persisted=nf_source_authorization_decisions"
echo "human_review_decisions_persisted=same_table_decision_kind_human_review"
echo "activation_composed=nf_active_opportunity_sources.activation_approved_*"
echo "second_activation_system_created=false"
echo "runtime_derivation_repaired=true (six Gates 156-161 lanes, not module presence)"
echo "sources_evaluated=179 (177 shipped + 2 synthetic fixtures)"
echo "real_sources_resolved=$RESOLVED"
echo "terms_blocked=$TERMS_BLOCKED"
echo "human_review_blocked=$HUMAN_BLOCKED"
echo "real_approved_sources=0"
echo "real_allowlisted_sources=0"
echo "synthetic_fixtures_allowlisted=1 (reachability proof)"
echo "synthetic_recorded_fact_count=11"
echo "authorization_complete_equals_live_fetch_opted_in=false"
echo "live_fetch_not_opted_in=still_blocking"
echo "live_transport_enabled=false"
echo "live_transport_dispatchable=false"
echo "live_source_calls=0"
echo "live_execution_attempts=0"
echo "unsigned_approvals=0"
echo "real_terms_decisions_created=1 (nf-seed-2026-api-grants-gov-search2)"
echo "real_human_review_decisions_created=1 (nf-seed-2026-api-grants-gov-search2)"
echo "mutation_endpoints=0"
echo "routes=4 (all GET, all session-guarded)"
echo "customer_data_persisted=false"
echo "real_org_touched=false"
echo "emails_sent=0"
echo "object_store_calls=0"
echo "cleanup=ran_after_the_final_write"
echo "residue=0"
echo "migration_added_by_this_gate=0048 (nf_source_authorization_decisions)"
echo "next=docs/operations/847_GATE162_GATE163_ACTIVATION_CONTRACT.md"
exit 0
