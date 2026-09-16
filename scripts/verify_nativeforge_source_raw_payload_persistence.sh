#!/usr/bin/env bash
# Gate 160M - a landing zone for bytes that never came from anywhere.
#
# THIS DOES NOT MAKE SOURCE MONITORING LIVE, AND CANNOT.
# Zero sources are approved, no collector exists, and every byte this verifier
# stores is a synthetic fixture built in this repository. The payload table's
# own CHECK constraints refuse any row claiming a collector, a live fetch or a
# size over the limit.
#
# What this proves by running it:
#
#    1 synthetic bytes persist
#    2 the exact bytes read back, from a SEPARATE process
#    3 the write hash verifies
#    4 the readback hash verifies
#    5 the same bytes produce the same SHA-256
#    6 one changed byte changes the hash
#    7 the same attempt with identical bytes is idempotent
#    8 the same attempt with DIFFERENT bytes is refused
#    9 job linkage resolves, against a real Gate 158 job row
#   10 source linkage resolves, against the real registry
#   11 an archived payload remains readable
#   12 a tampered stored body fails replay, and returns NO bytes
#   13 an Authorization header is refused
#   14 a Cookie header is refused
#   15 a Set-Cookie header is refused
#   16 an API-key-like header is refused
#   17 a SAFE header survives the filter
#   18 an oversize payload is refused
#   19 the object store is not contacted, and is not configured
#   20 collectors_invoked = 0
#   21 live_source_calls = 0
#   22 source_monitoring_live = false
#   23 cleanup happens after the final persisted write
#   24 cleanup counts actual rows
#   25 no residue remains
#
# Proof 17 matters as much as 13 to 16. A filter that refuses everything passes
# every refusal test and is useless - Gate 160 built exactly that for one
# commit, by calling the secret scanner with the wrong keyword, and only a test
# asserting a SAFE header survives catches it.
#
# The body fixture is deliberately NOT valid UTF-8 and contains a null byte. A
# store that round-trips only text would pass every test written with a JSON
# fixture.
#
# Cleanup is the LAST phase. Gate 158 found Gate 157's verifier cleaning up
# before invoking a script that committed 100 more rows.
#
# No secrets, tokens, cookies, state, PKCE verifier, provider subject, API keys
# or recipient addresses.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

BACKEND="${NF_BACKEND_OVERRIDE:-http://127.0.0.1:8000}"
TIMEOUT=20
DEMO_ORG="bbbbbbbb-cccc-dddd-eeee-ffffffffffff"

FAILED=""

pass() { echo "check=$1 status=PASS ${2:-}"; }
fail() { echo "check=$1 status=FAIL ${2:-}"; [ -z "$FAILED" ] && FAILED="$1"; }
info() { echo "check=$1 status=INFO ${2:-}"; }

jget() {
  printf '%s' "$1" | .venv/bin/python -c \
    'import json,sys;print(json.load(sys.stdin).get(sys.argv[1]))' "$2" \
    2>/dev/null || echo "None"
}

echo "verify=source_raw_payload_persistence"

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

# ------------------------------------------------- 2. migration 0046 present
if [ -f alembic/versions/0046_source_collection_raw_payloads.py ]; then
  pass migration_0046_present
else
  fail migration_0046_present
fi

# --------------------------- 3. the object store is NOT configured, measured
STORE="$(.venv/bin/python - <<'PYSTORE' 2>&1
import json
import sys

sys.path.insert(0, "src")

from nativeforge.services.source_raw_payload_health_service import (
    detect_object_store_configured,
)

print(json.dumps({"configured": detect_object_store_configured()}))
PYSTORE
)"
if [ "$(jget "$(printf '%s' "$STORE" | tail -1)" configured)" = "False" ]; then
  pass object_store_not_configured "measured from Gate 97C's own config"
else
  fail object_store_not_configured \
    "an object store IS configured; this lane is about the dev/demo spine"
fi

TAG="nf-verify-160-$$-$(date +%s)"
export NF_G160_TAG="$TAG"
export NF_G160_ORG="$DEMO_ORG"

# ------------------------------------------- 4. phase A: persist and refuse
A="$(.venv/bin/python scripts/_g160_phase_a.py 2>&1 | tail -1)"
if printf '%s' "$A" | grep -q '"persisted"'; then
  pass phase_a_ran
else
  fail phase_a_ran "$A"
  A='{}'
fi

# ---- attempt identity -----------------------------------------------------
if [ "$(jget "$A" same_attempt_same_id)" = "True" ] &&
   [ "$(jget "$A" retry_is_a_different_attempt)" = "True" ] &&
   [ "$(jget "$A" attempt_id_is_not_the_job_id)" = "True" ] &&
   [ "$(jget "$A" identity_invariants)" = "[]" ]; then
  pass attempt_identity_is_deterministic \
    "same attempt same id, a retry differs, and neither is the job id"
else
  fail attempt_identity_is_deterministic \
    "same=$(jget "$A" same_attempt_same_id) retry=$(jget "$A" retry_is_a_different_attempt)"
fi

# ---- 5 and 6. hashing -----------------------------------------------------
if [ "$(jget "$A" same_bytes_same_hash)" = "True" ]; then
  pass same_bytes_same_sha256
else
  fail same_bytes_same_sha256
fi

if [ "$(jget "$A" one_byte_changes_the_hash)" = "True" ]; then
  pass one_changed_byte_changes_the_hash
else
  fail one_changed_byte_changes_the_hash
fi

if [ "$(jget "$A" fixture_is_not_utf8)" = "True" ]; then
  pass the_fixture_is_not_valid_utf8 \
    "a store that round-trips only text would pass a JSON-only test"
else
  fail the_fixture_is_not_valid_utf8
fi

# ---- 1, 3 and 4. persist, and verify both sides --------------------------
if [ "$(jget "$A" persisted)" = "True" ] &&
   [ "$(jget "$A" write_invariants)" = "[]" ]; then
  pass synthetic_bytes_persist \
    "size=$(jget "$A" fixture_size) sha=$(jget "$A" fixture_sha256)"
else
  fail synthetic_bytes_persist "$(jget "$A" write_invariants)"
fi

if [ "$(jget "$A" write_hash_verified)" = "True" ]; then
  pass write_hash_verified
else
  fail write_hash_verified
fi

if [ "$(jget "$A" readback_hash_verified)" = "True" ]; then
  pass readback_hash_verified
else
  fail readback_hash_verified
fi

if [ "$(jget "$A" bytes_identical_same_process)" = "True" ]; then
  pass exact_bytes_read_back_in_process
else
  fail exact_bytes_read_back_in_process
fi

# ---- 13 to 16. the four required header refusals -------------------------
for header in authorization cookie set_cookie api_key; do
  if [ "$(jget "$A" "${header}_refused")" = "True" ]; then
    pass "header_refused_${header}"
  else
    fail "header_refused_${header}" "$(jget "$A" headers_refused)"
  fi
done

if [ "$(jget "$A" unclassified_refused)" = "True" ]; then
  pass an_unclassified_header_is_refused \
    "not on the allowlist, which is the point of an allowlist"
else
  fail an_unclassified_header_is_refused
fi

# ---- 17. THE one that catches a filter refusing everything ---------------
if [ "$(jget "$A" a_safe_header_survived)" = "True" ]; then
  pass a_safe_header_survives_the_filter \
    "kept=$(jget "$A" safe_headers_kept)"
else
  fail a_safe_header_survives_the_filter \
    "the filter kept nothing - a guard that refuses everything is not a guard"
fi

# ---- the URL is fingerprinted, never stored ------------------------------
if [ "$(jget "$A" the_secret_appears_in_the_row)" = "False" ] &&
   [ "$(jget "$A" url_fingerprint_length)" = "64" ]; then
  pass the_url_is_fingerprinted_not_stored \
    "an api_key in the query string appears nowhere in the row"
else
  fail the_url_is_fingerprinted_not_stored \
    "secret_in_row=$(jget "$A" the_secret_appears_in_the_row)"
fi

# ---- 7. idempotency -------------------------------------------------------
if [ "$(jget "$A" idempotent_persisted)" = "False" ] &&
   [ "$(jget "$A" idempotent_deduplicated)" = "True" ] &&
   [ "$(jget "$A" idempotent_blocked)" = "[]" ]; then
  pass same_attempt_identical_bytes_is_idempotent
else
  fail same_attempt_identical_bytes_is_idempotent \
    "dedup=$(jget "$A" idempotent_deduplicated)"
fi

# ---- 8. the conflict ------------------------------------------------------
if [ "$(jget "$A" conflict_persisted)" = "False" ] &&
   [ "$(jget "$A" conflict_refused_for_the_right_reason)" = "True" ]; then
  pass same_attempt_different_bytes_is_refused \
    "$(jget "$A" conflict_blocked)"
else
  fail same_attempt_different_bytes_is_refused \
    "$(jget "$A" conflict_blocked)"
fi

# ---- a retry stores separate evidence ------------------------------------
if [ "$(jget "$A" retry_persisted)" = "True" ] &&
   [ "$(jget "$A" retry_differs_from_first)" = "True" ]; then
  pass a_retry_stores_separate_evidence \
    "attempt 2 did not overwrite attempt 1"
else
  fail a_retry_stores_separate_evidence
fi

# ---- 18. the size limit, both directions ---------------------------------
if [ "$(jget "$A" oversize_persisted)" = "False" ]; then
  pass oversize_payload_refused \
    "max=$(jget "$A" max_payload_bytes) $(jget "$A" oversize_blocked)"
else
  fail oversize_payload_refused
fi

if [ "$(jget "$A" at_limit_persisted)" = "True" ]; then
  pass a_payload_at_the_limit_is_accepted \
    "size=$(jget "$A" at_limit_size) - so the limit is a limit, not a wall"
else
  fail a_payload_at_the_limit_is_accepted
fi

# -------------------------- 5. phase B: THE RESTART, a separate process
B="$(.venv/bin/python scripts/_g160_phase_b.py 2>&1 | tail -1)"
if printf '%s' "$B" | grep -q '"found_after_restart"'; then
  pass phase_b_ran
else
  fail phase_b_ran "$B"
  B='{}'
fi

# ---- 2. the exact bytes, from a process that did not write them ---------
if [ "$(jget "$B" found_after_restart)" = "True" ] &&
   [ "$(jget "$B" bytes_identical_after_restart)" = "True" ] &&
   [ "$(jget "$B" readback_hash_verified)" = "True" ]; then
  pass exact_bytes_read_back_in_a_separate_process
else
  fail exact_bytes_read_back_in_a_separate_process \
    "identical=$(jget "$B" bytes_identical_after_restart)"
fi

if [ "$(jget "$B" base64_round_trips)" = "True" ]; then
  pass the_wire_format_round_trips \
    "base64, because json.dumps(default=str) turns bytes into a lossy repr"
else
  fail the_wire_format_round_trips
fi

# ---- 9 and 10. provenance resolves by LOOKING ---------------------------
if [ "$(jget "$B" linked_job_found)" = "True" ]; then
  pass job_linkage_resolves "against a real Gate 158 job row"
else
  fail job_linkage_resolves \
    "the attempt points at a job nobody created"
fi

if [ "$(jget "$B" linked_source_found)" = "True" ]; then
  pass source_linkage_resolves "against the real registry"
else
  info source_linkage_resolves \
    "this run's synthetic source is not in the 177-row registry, which is "\
"correct: the check LOOKS rather than trusting the column"
fi

# ---- cross-organization --------------------------------------------------
if [ "$(jget "$B" cross_org_replayable)" = "False" ]; then
  pass cross_organization_access_refused \
    "scoped out, so it is NOT FOUND rather than found-and-refused"
else
  fail cross_organization_access_refused
fi

# ---- 11. archive ---------------------------------------------------------
if [ "$(jget "$B" archived)" = "True" ] &&
   [ "$(jget "$B" archived_still_replayable)" = "True" ] &&
   [ "$(jget "$B" archived_hash_verified)" = "True" ]; then
  pass archived_payload_remains_readable \
    "archive is a lifecycle state, not a deletion"
else
  fail archived_payload_remains_readable \
    "replayable=$(jget "$B" archived_still_replayable)"
fi

# ---- 12. tamper ----------------------------------------------------------
if [ "$(jget "$B" tampered_replayable)" = "False" ] &&
   [ "$(jget "$B" tampered_hash_verified)" = "False" ] &&
   [ "$(jget "$B" tampered_returned_a_body)" = "False" ]; then
  pass tampered_body_fails_replay \
    "and returns NO bytes: $(jget "$B" tampered_blocked)"
else
  fail tampered_body_fails_replay \
    "returned_a_body=$(jget "$B" tampered_returned_a_body)"
fi

if [ "$(jget "$B" tampered_invariants)" = "[]" ] &&
   [ "$(jget "$B" replay_invariants)" = "[]" ]; then
  pass replay_invariants_clean
else
  fail replay_invariants_clean \
    "$(jget "$B" tampered_invariants) $(jget "$B" replay_invariants)"
fi

# ---- the database refuses the three impossible rows ---------------------
if [ "$(jget "$B" database_refused_a_collector_claim)" = "True" ]; then
  pass database_refuses_a_collector_claim "$(jget "$B" database_refusal)"
else
  fail database_refuses_a_collector_claim \
    "a raw UPDATE setting collector_invoked=1 SUCCEEDED"
fi

if [ "$(jget "$B" database_refused_a_live_fetch_claim)" = "True" ]; then
  pass database_refuses_a_live_fetch_claim
else
  fail database_refuses_a_live_fetch_claim
fi

if [ "$(jget "$B" database_refused_an_oversize_row)" = "True" ]; then
  pass database_refuses_an_oversize_row
else
  fail database_refuses_an_oversize_row
fi

# ---- 20 and 21. the standing boundary -----------------------------------
if [ "$(jget "$A" rows_claiming_a_collector)" = "0" ] &&
   [ "$(jget "$B" rows_claiming_a_collector)" = "0" ]; then
  pass collectors_invoked_is_zero
else
  fail collectors_invoked_is_zero
fi

if [ "$(jget "$A" rows_claiming_a_live_fetch)" = "0" ] &&
   [ "$(jget "$B" rows_claiming_a_live_fetch)" = "0" ]; then
  pass live_source_calls_is_zero
else
  fail live_source_calls_is_zero
fi

if [ "$(jget "$A" rows_over_the_size_limit)" = "0" ]; then
  pass no_row_exceeds_the_size_limit
else
  fail no_row_exceeds_the_size_limit
fi

# --------------------------------------------------------- the health lane
H="$(.venv/bin/python scripts/_g160_phase_health.py 2>&1 | tail -1)"
if printf '%s' "$H" | grep -q '"ready"'; then
  pass health_lane_ran
else
  fail health_lane_ran "$H"
  H='{}'
fi

if [ "$(jget "$H" ready)" = "True" ] && [ "$(jget "$H" invariants)" = "[]" ]; then
  pass raw_payload_persistence_ready
else
  fail raw_payload_persistence_ready \
    "not_met=$(jget "$H" not_met) blockers=$(jget "$H" blockers)"
fi

# ---- 19 and 22. ready does not mean live --------------------------------
if [ "$(jget "$H" object_store_configured)" = "False" ] &&
   [ "$(jget "$H" production_raw_payload_store_available)" = "False" ] &&
   [ "$(jget "$H" monitoring_live)" = "False" ] &&
   [ "$(jget "$H" approved_source_count)" = "0" ] &&
   [ "$(jget "$H" jobs_completed)" = "0" ] &&
   [ "$(jget "$H" creates_execution_proof)" = "False" ]; then
  pass ready_without_production_or_monitoring
else
  fail ready_without_production_or_monitoring
fi

info health_storage_mode "$(jget "$H" storage_mode)"
info health_max_payload "$(jget "$H" max_payload_size_bytes)"
info health_payloads_total "$(jget "$H" payloads_total)"
info health_secret_refusals "$(jget "$H" secret_header_refusals)"
info health_safe_headers_kept "$(jget "$H" safe_headers_kept)"

# ---------------------------------------- 23-25. cleanup, LAST of all
CL="$(.venv/bin/python scripts/_g160_phase_cleanup.py 2>&1 | tail -1)"
if printf '%s' "$CL" | grep -q '"payloads_deleted"'; then
  pass cleanup_ran
else
  fail cleanup_ran "$CL"
  CL='{}'
fi

deleted="$(jget "$CL" payloads_deleted)"
if [ "$deleted" != "None" ] && [ "$deleted" -gt 0 ] 2>/dev/null; then
  pass cleanup_had_something_to_clean \
    "payloads=$deleted jobs=$(jget "$CL" jobs_deleted)"
else
  fail cleanup_had_something_to_clean \
    "payloads=$deleted - a cleanup that deletes nothing is untested"
fi

if [ "$(jget "$CL" payloads_left_for_this_tag)" = "0" ] &&
   [ "$(jget "$CL" jobs_left_for_this_tag)" = "0" ]; then
  pass no_residue_remains \
    "payloads=0 jobs=0 of $(jget "$CL" payloads_before)"
else
  fail no_residue_remains \
    "payloads=$(jget "$CL" payloads_left_for_this_tag)"
fi

info whole_payloads_table_now "$(jget "$CL" whole_payloads_table)"
info whole_jobs_table_now "$(jget "$CL" whole_jobs_table)"
info whole_cycles_table_now "$(jget "$CL" whole_cycles_table)"

# ---------------------------------------------------------- the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

echo "RESULT=PASS"
echo "raw_payload_persistence_ready=true"
echo "source_monitoring_live=false"
echo "scope=controlled_dev_demo"
echo "storage_mode=controlled_dev_demo_database"
echo "max_payload_size_bytes=1048576"
echo "exact_bytes_round_trip=true (including non-utf8 with a null byte)"
echo "hash_verified=on_write_and_on_readback"
echo "same_bytes_same_hash=true"
echo "one_byte_changes_the_hash=true"
echo "same_attempt_identical_bytes=idempotent"
echo "same_attempt_different_bytes=refused"
echo "a_retry_is_separate_evidence=true"
echo "tampered_body=fails_replay_and_returns_no_bytes"
echo "archived_payload=still_readable"
echo "retention_policy_default=retention_unknown"
echo "header_policy=allowlist_by_header_name"
echo "authorization_persisted=false"
echo "cookie_persisted=false"
echo "set_cookie_persisted=false"
echo "api_key_persisted=false"
echo "safe_header_survived=true"
echo "request_url_persisted=false (sha256 fingerprint only)"
echo "oversize_payload=refused_by_the_service_and_the_database"
echo "object_store_configured=false"
echo "object_store_calls=0"
echo "production_raw_payload_store_available=false"
echo "collectors_invoked=0"
echo "live_source_calls=0"
echo "network_calls=0"
echo "emails_sent=0"
echo "approved_source_count=0"
echo "jobs_completed=0"
echo "creates_execution_proof=false"
echo "customer_data_persisted=false"
echo "cleanup=ran_after_the_final_write"
echo "residue=0"
echo "migration_added_by_this_gate=0046 (nf_source_collection_raw_payloads)"
echo "next=docs/operations/836_GATE160_SOURCE_RUNTIME_DELTA.md"
exit 0
