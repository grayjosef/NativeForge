#!/usr/bin/env bash
# Gate 157I — a worker that claims every job and is refused by every one.
#
# THIS DOES NOT MAKE SOURCE MONITORING LIVE, AND CANNOT.
# Zero sources are approved, no collector exists, and the lease table's own
# constraints refuse any row claiming a fetch happened.
#
# What this proves by running it:
#
#   a worker claims a job, with an explicit worker id
#   a SECOND worker's claim on a held job is refused
#   a lease past its expiry IS reclaimable, by another worker
#   a retry decision at the attempt budget refuses to retry
#   an activation refusal is NOT retried as a transient failure
#   a terms refusal is NOT retried
#   a human-review refusal is NOT retried
#   a transient failure IS retried, with a deterministic backoff
#   the scheduler and the worker compose: 177 offered, 177 refused
#   a restart finds its state, because the state is the lease table
#
# The permitting branch is exercised too. A retry policy that refuses
# everything proves nothing about the refusals.
#
# What it deliberately does NOT clear:
#
#   `scheduler_component_absent:background_worker` looks for a
#   nativeforge.workers module or a console entry point. This gate adds a
#   script, so Gate 143 keeps listing it - the same shape as Gate 156 and the
#   scheduler package. A detector looking for a package is not a capability.
#
# Every fixture row this verifier writes is removed before it exits.
#
# No secrets, tokens, cookies, state, PKCE verifier, provider subject, API keys
# or recipient addresses.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

BACKEND="${NF_BACKEND_OVERRIDE:-http://127.0.0.1:8000}"
TIMEOUT=20

FAILED=""

pass() { echo "check=$1 status=PASS ${2:-}"; }
fail() { echo "check=$1 status=FAIL ${2:-}"; [ -z "$FAILED" ] && FAILED="$1"; }
info() { echo "check=$1 status=INFO ${2:-}"; }

echo "verify=source_worker_runtime"

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

# ------------------------- 2. the guards this gate must not weaken, RUN
for v in no_live_source_calls source_monitoring_preflight \
  source_scheduler_runtime; do
  r="$(timeout 900 bash "scripts/verify_nativeforge_${v}.sh" 2>/dev/null \
    | grep -E '^RESULT=' | tail -1)"
  if [ "$r" = "RESULT=PASS" ]; then
    pass "existing_guard_still_passes:$v"
  else
    fail "existing_guard_still_passes:$v" "${r:-no result}"
  fi
done

# ------------------------------------------------------- 3. the worker runtime
REPORT="$(
  .venv/bin/python - <<'PYEOF' 2>/dev/null || true
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

import sqlalchemy as sa

from nativeforge.db.session import SessionLocal, engine
from nativeforge.services import (
    source_worker_artifact_gate157_service as art,
)
from nativeforge.services.source_collection_job_lease_service import (
    TABLE_NAME,
    claim_job,
    lease_invariant_failures,
)
from nativeforge.services.source_collection_retry_policy_service import (
    HUMAN_REVIEW_BLOCKED,
    PERMANENT_WORKER_FAILURE,
    REFUSED_BY_ACTIVATION,
    TERMS_BLOCKED,
    TRANSIENT_WORKER_FAILURE,
    classify_blockers,
    evaluate_retry,
    retry_invariant_failures,
)
from nativeforge.services.source_collection_scheduler_loop_service import (
    run_scheduler_cycle,
)
from nativeforge.services.source_collection_worker_health_service import (
    build_worker_health,
    worker_health_invariant_failures,
)
from nativeforge.services.source_collection_worker_runtime_service import (
    run_worker_cycle,
    worker_cycle_invariant_failures,
)
from nativeforge.services.source_monitoring_approved_source_service import (
    load_registry_rows,
)
from nativeforge.services.source_scheduler_readiness_service import (
    build_scheduler_readiness,
)

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
T0 = "2026-09-15T12:00:00Z"
T_LATER = "2026-09-15T12:10:00Z"
PREFIX = "nf-verify-157"

out = {"invariant_failures": []}

# Clean slate. Deleted by ORGANIZATION, not by a job_id prefix: job_id is
# Gate 99B's sha256 digest, so a prefix match on it finds nothing this
# verifier wrote. An earlier version matched the prefix, removed one row of
# 278, and then counted the same empty pattern to report a clean exit.
with engine.begin() as c:
    c.execute(
        sa.text(f"DELETE FROM {TABLE_NAME} WHERE organization_id = :o"),
        {"o": DEMO.replace("-", "")},
    )

# -- classification ------------------------------------------------------
out["classify_terms_first"] = (
    classify_blockers(
        ["source_terms_not_approved", "source_activation_not_approved"]
    )
    == TERMS_BLOCKED
)
out["classify_human_review"] = (
    classify_blockers(["source_requires_human_review"]) == HUMAN_REVIEW_BLOCKED
)
out["classify_activation"] = (
    classify_blockers(["source_activation_not_approved"]) == REFUSED_BY_ACTIVATION
)
out["classify_unmapped_is_not_transient"] = (
    classify_blockers(["something_nobody_mapped"]) != TRANSIENT_WORKER_FAILURE
)

# -- retry policy --------------------------------------------------------
not_retried = {}
for klass in (
    REFUSED_BY_ACTIVATION,
    TERMS_BLOCKED,
    HUMAN_REVIEW_BLOCKED,
    PERMANENT_WORKER_FAILURE,
):
    d = evaluate_retry(failure_class=klass, attempt_count=0, max_attempts=3, now=T0)
    out["invariant_failures"].extend(retry_invariant_failures(d))
    not_retried[klass] = not d["should_retry"]
out["non_transient_not_retried"] = not_retried
out["non_transient_that_retried"] = sorted(
    k for k, v in not_retried.items() if not v
)

transient = evaluate_retry(
    failure_class=TRANSIENT_WORKER_FAILURE, attempt_count=0, max_attempts=3, now=T0
)
out["invariant_failures"].extend(retry_invariant_failures(transient))
out["transient_is_retried"] = transient["should_retry"]
out["transient_backoff"] = transient["backoff_seconds"]
out["backoff_is_deterministic"] = (
    evaluate_retry(
        failure_class=TRANSIENT_WORKER_FAILURE,
        attempt_count=0,
        max_attempts=3,
        now=T0,
    )
    == transient
)

exhausted = evaluate_retry(
    failure_class=TRANSIENT_WORKER_FAILURE, attempt_count=3, max_attempts=3, now=T0
)
out["retry_is_bounded"] = not exhausted["should_retry"]
out["invariant_failures"].extend(retry_invariant_failures(exhausted))

# -- claim, duplicate, expiry -------------------------------------------
with SessionLocal() as session:
    c = session.connection()
    first = claim_job(
        connection=c,
        organization_id=DEMO,
        job_id=f"{PREFIX}-claim",
        source_id="verify-src",
        worker_id="verify-worker-1",
        now=T0,
        lease_seconds=300,
    )
    out["invariant_failures"].extend(lease_invariant_failures(first))
    out["first_claim_succeeded"] = first["claimed"]

    dup = claim_job(
        connection=c,
        organization_id=DEMO,
        job_id=f"{PREFIX}-claim",
        source_id="verify-src",
        worker_id="verify-worker-2",
        now=T0,
    )
    out["duplicate_claim_refused"] = not dup["claimed"]
    out["duplicate_reasons"] = dup["blocked_reasons"]

    reclaim = claim_job(
        connection=c,
        organization_id=DEMO,
        job_id=f"{PREFIX}-claim",
        source_id="verify-src",
        worker_id="verify-worker-2",
        now=T_LATER,
    )
    out["expired_lease_reclaimed"] = reclaim["claimed"]
    out["reclaim_was_of_an_expired_lease"] = bool(
        reclaim.get("reclaimed_expired_lease")
    )

    # The real organization is refused by name.
    real = claim_job(
        connection=c,
        organization_id=REAL,
        job_id=f"{PREFIX}-real",
        source_id="verify-src",
        worker_id="verify-worker-1",
        now=T0,
    )
    out["real_org_refused"] = (
        not real["claimed"]
        and "real_organization_refused_by_name" in real["blocked_reasons"]
    )
    session.commit()

# -- scheduler + worker compose -----------------------------------------
registry = load_registry_rows()
jobs = run_scheduler_cycle(
    now=T0,
    sources=[
        {
            "source_id": f"{PREFIX}-{key}",
            "check_interval_days": None,
            "next_check_due_at": None,
            "last_checked_at": None,
            "is_enabled": True,
            "activation_state": "activation_blocked",
            "terms_state": "terms_unknown",
            "human_review_state": "human_review_required",
            "collector_registered": False,
        }
        for key in sorted(registry)
    ],
)["jobs"]

with SessionLocal() as session:
    cycle = run_worker_cycle(
        connection=session.connection(),
        organization_id=DEMO,
        worker_id="verify-worker-cycle",
        jobs=jobs,
        now=T0,
        max_jobs=1000,
    )
    session.commit()

out["invariant_failures"].extend(worker_cycle_invariant_failures(cycle))
out["registry_rows"] = len(registry)
out["jobs_offered"] = cycle["jobs_offered"]
out["jobs_seen"] = cycle["jobs_seen"]
out["jobs_not_reached"] = cycle["jobs_not_reached_this_cycle"]
out["jobs_claimed"] = cycle["jobs_claimed"]
out["jobs_refused"] = cycle["jobs_refused"]
out["jobs_retryable"] = cycle["jobs_retryable"]
out["jobs_completed"] = cycle["jobs_completed"]
out["collectors_invoked"] = cycle["collectors_invoked"]
out["live_source_calls"] = cycle["live_source_calls"]
out["network_calls"] = cycle["network_calls"]
out["threads_started"] = cycle["threads_started"]
out["api_key_required"] = cycle["api_key_required"]
out["worker_monitoring_live"] = cycle["source_monitoring_live"]
out["every_registry_row_offered"] = cycle["jobs_offered"] == len(registry)

# -- restart recovery: the state is the table ---------------------------
with engine.connect() as c:
    persisted = c.execute(
        sa.text(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE organization_id = :o"),
        {"o": DEMO.replace("-", "")},
    ).scalar()
    claiming_a_fetch = c.execute(
        sa.text(
            f"SELECT COUNT(*) FROM {TABLE_NAME} "
            "WHERE collector_invoked = 1 OR url_fetched = 1 "
            "OR raw_payload_written = 1"
        )
    ).scalar()
    over_budget = c.execute(
        sa.text(
            f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE attempt_count > max_attempts"
        )
    ).scalar()
out["leases_persisted"] = int(persisted or 0)
out["restart_recovery_possible"] = int(persisted or 0) > 0
out["rows_claiming_a_fetch"] = int(claiming_a_fetch or 0)
out["rows_over_attempt_budget"] = int(over_budget or 0)

# -- the permitting branch, reachable -----------------------------------
with SessionLocal() as session:
    permitted_cycle = run_worker_cycle(
        connection=session.connection(),
        organization_id=DEMO,
        worker_id="verify-worker-permitted",
        jobs=[
            {
                "job_id": f"{PREFIX}-permitted",
                "source_id": "verify-src-permitted",
                "executable": True,
                "blockers": [],
            }
        ],
        now=T0,
    )
    session.commit()
out["permitted_job_was_claimed"] = permitted_cycle["jobs_claimed"] == 1
# Even a permitted job cannot complete: there is no handler.
out["permitted_job_did_not_complete"] = permitted_cycle["jobs_completed"] == 0
out["permitted_job_reason"] = (
    permitted_cycle["results"][0]["blocked_reasons"]
    if permitted_cycle["results"]
    else []
)
out["invariant_failures"].extend(
    worker_cycle_invariant_failures(permitted_cycle)
)

# -- health --------------------------------------------------------------
health = build_worker_health(
    cycle=cycle,
    duplicate_claim_refused=out["duplicate_claim_refused"],
    expired_lease_reclaimed=out["expired_lease_reclaimed"],
    retry_bounded=out["retry_is_bounded"],
    worker_process_active=None,
    jobs_available=len(jobs),
    jobs_claimable=0,
    stale_leases=0,
    activation_allowlist_count=0,
)
out["invariant_failures"].extend(worker_health_invariant_failures(health))
out["worker_runtime_ready"] = health["worker_runtime_ready"]
out["health_blockers"] = health["blockers"]
out["health_monitoring_live"] = health["source_monitoring_live"]

# A completed job must be refused by an invariant.
out["completed_job_guard_fires"] = bool(
    worker_health_invariant_failures({**health, "jobs_completed": 1})
)
out["retryable_guard_fires"] = bool(
    worker_health_invariant_failures({**health, "jobs_retryable": 2})
)

# -- the detector this gate does not satisfy ----------------------------
sched = build_scheduler_readiness()
out["background_worker_still_absent"] = not sched["background_worker_available"]

# -- no module reaches the network --------------------------------------
import ast

MODULES = [
    "src/nativeforge/services/source_collection_worker_runtime_service.py",
    "src/nativeforge/services/source_collection_job_lease_service.py",
    "src/nativeforge/services/source_collection_retry_policy_service.py",
    "src/nativeforge/services/source_collection_worker_health_service.py",
    "src/nativeforge/services/source_worker_artifact_gate157_service.py",
    "src/nativeforge/api/source_collection_worker_routes.py",
    "scripts/run_source_collection_worker.py",
]
NETWORK = {
    "httpx", "requests", "urllib", "urllib3", "http", "socket", "aiohttp",
    "ftplib", "telnetlib", "smtplib", "subprocess",
}
offenders = []
for path in MODULES:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in NETWORK:
                    offenders.append(f"{path}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in NETWORK:
                offenders.append(f"{path}:{node.module}")
out["network_import_offenders"] = sorted(set(offenders))
control = ast.parse(
    Path("src/nativeforge/services/backend_health_readiness_service.py").read_text(
        encoding="utf-8"
    )
)
out["network_scan_finds_a_known_import"] = any(
    isinstance(n, ast.Import)
    and any(a.name.split(".")[0] in NETWORK for a in n.names)
    for n in ast.walk(control)
)

# -- artifacts ----------------------------------------------------------
built = art.build_worker_artifacts()
out["artifact_count"] = len(built)
out["artifacts_deterministic"] = art.build_worker_artifacts() == built
directory = Path(art.ARTIFACT_DIR)
out["artifacts_on_disk_match"] = all(
    (directory / n).is_file() and (directory / n).read_text(encoding="utf-8") == b
    for n, b in built.items()
)
blob = "\n".join(built.values()).lower()
out["artifact_claims_monitoring_live"] = '"source_monitoring_live": true' in blob

# -- clean up every fixture row -----------------------------------------
#
# Counted BEFORE the delete, so the number reported is what this run actually
# created rather than what a pattern happened to match.
with engine.connect() as c:
    out["lease_rows_before_cleanup"] = int(
        c.execute(sa.text(f"SELECT COUNT(*) FROM {TABLE_NAME}")).scalar() or 0
    )
with engine.begin() as c:
    c.execute(
        sa.text(f"DELETE FROM {TABLE_NAME} WHERE organization_id = :o"),
        {"o": DEMO.replace("-", "")},
    )
with engine.connect() as c:
    # The whole table, not a pattern. Nothing but fixtures lives here, so a
    # non-zero total after cleanup is a real finding.
    out["fixture_rows_remaining"] = int(
        c.execute(sa.text(f"SELECT COUNT(*) FROM {TABLE_NAME}")).scalar() or 0
    )
    out["real_org_lease_rows"] = int(
        c.execute(
            sa.text(f"SELECT COUNT(*) FROM {TABLE_NAME} WHERE organization_id = :o"),
            {"o": "aaaaaaaabbbbccccddddeeeeeeeeeeee"},
        ).scalar()
        or 0
    )

out["invariant_failures"] = sorted(set(out["invariant_failures"]))
print(json.dumps(out, sort_keys=True, default=str))
PYEOF
)"

if [ -z "$REPORT" ]; then
  fail worker_evaluated "empty"
  echo
  echo "RESULT=BLOCKED"
  echo "blocker=worker_could_not_evaluate"
  exit 1
fi
pass worker_evaluated

get() { printf '%s' "$REPORT" | .venv/bin/python -c "
import json,sys
v=json.load(sys.stdin).get(sys.argv[1])
print('' if v is None else v)
" "$1" 2>/dev/null; }

getlist() { printf '%s' "$REPORT" | .venv/bin/python -c "
import json,sys
v=json.load(sys.stdin).get(sys.argv[1]) or []
print(','.join(str(x) for x in v) if v else 'none')
" "$1" 2>/dev/null; }

# ----------------------------------------------- 4. routes registered
for path in health jobs leases dry-run; do
  n="$(curl -s --max-time "$TIMEOUT" "$BACKEND/openapi.json" 2>/dev/null \
    | .venv/bin/python -c "
import json,sys
spec=json.load(sys.stdin)
want='/source-worker/' + sys.argv[1]
print(sum(1 for p in spec.get('paths',{}) if p.endswith(want)))
" "$path" 2>/dev/null || echo 0)"
  if [ "$n" = "1" ]; then
    pass "route_registered:$path"
  else
    fail "route_registered:$path" "found=$n"
  fi
done

# ------------------------------------------------------ 5. the process
if .venv/bin/python scripts/run_source_collection_worker.py --once \
  --now 2026-09-15T12:00:00Z --worker-id nf-verify-process >/dev/null 2>&1; then
  pass worker_process_runs_one_shot "exit 0"
else
  fail worker_process_runs_one_shot "non-zero exit"
fi

# ------------------------------------------- 6. claiming and leases
if [ "$(get first_claim_succeeded)" = "True" ]; then
  pass a_worker_can_claim_a_job
else
  fail a_worker_can_claim_a_job
fi

if [ "$(get duplicate_claim_refused)" = "True" ]; then
  pass duplicate_claim_refused "$(getlist duplicate_reasons)"
else
  fail duplicate_claim_refused "a second worker took a held lease"
fi

if [ "$(get expired_lease_reclaimed)" = "True" ] &&
   [ "$(get reclaim_was_of_an_expired_lease)" = "True" ]; then
  pass expired_lease_reclaimable "a dead worker does not block a job forever"
else
  fail expired_lease_reclaimable
fi

if [ "$(get real_org_refused)" = "True" ]; then
  pass real_organization_refused_by_name
else
  fail real_organization_refused_by_name
fi

# ---------------------------------------- 7. retry classification
for klass in refused_by_activation terms_blocked human_review_blocked \
  permanent_worker_failure; do
  n="$(printf '%s' "$REPORT" | .venv/bin/python -c "
import json,sys
d=json.load(sys.stdin).get('non_transient_not_retried') or {}
print(d.get(sys.argv[1], ''))
" "$klass" 2>/dev/null)"
  if [ "$n" = "True" ]; then
    pass "not_retried:$klass"
  else
    fail "not_retried:$klass" "it was retried as a transient failure"
  fi
done

if [ "$(get transient_is_retried)" = "True" ]; then
  pass transient_failure_is_retried "backoff=$(get transient_backoff)s"
else
  fail transient_failure_is_retried "the retry branch is unreachable"
fi

if [ "$(get retry_is_bounded)" = "True" ]; then
  pass retry_is_bounded "at the attempt budget, should_retry is false"
else
  fail retry_is_bounded "unbounded retry"
fi

if [ "$(get backoff_is_deterministic)" = "True" ]; then
  pass backoff_is_deterministic
else
  fail backoff_is_deterministic
fi

for c in classify_terms_first classify_human_review classify_activation \
  classify_unmapped_is_not_transient; do
  if [ "$(get "$c")" = "True" ]; then
    pass "$c"
  else
    fail "$c"
  fi
done

# ------------------------------------- 8. scheduler + worker compose
info registry_rows "$(get registry_rows)"
info lease_rows_cleaned "$(get lease_rows_before_cleanup) rows removed at exit"
info cycle "offered=$(get jobs_offered) seen=$(get jobs_seen) not_reached=$(get jobs_not_reached)"

if [ "$(get every_registry_row_offered)" = "True" ]; then
  pass scheduler_and_worker_compose "n=$(get jobs_offered)"
else
  fail scheduler_and_worker_compose
fi

if [ "$(get jobs_refused)" = "$(get jobs_seen)" ] &&
   [ "$(get jobs_completed)" = "0" ]; then
  pass every_job_refused "none completed, because no handler exists"
else
  fail every_job_refused \
    "refused=$(get jobs_refused) seen=$(get jobs_seen) completed=$(get jobs_completed)"
fi

if [ "$(get jobs_retryable)" = "0" ]; then
  pass no_job_was_marked_retryable "every refusal needs a person, not a retry"
else
  fail no_job_was_marked_retryable "n=$(get jobs_retryable)"
fi

# The permitting branch must be reachable, or the refusals prove nothing.
if [ "$(get permitted_job_was_claimed)" = "True" ] &&
   [ "$(get permitted_job_did_not_complete)" = "True" ]; then
  pass permitting_branch_reachable_and_still_refuses \
    "$(getlist permitted_job_reason)"
else
  fail permitting_branch_reachable_and_still_refuses
fi

# ------------------------------------------ 9. restart recovery
if [ "$(get lease_rows_before_cleanup)" -gt 100 ] 2>/dev/null; then
  pass cleanup_had_something_to_clean "$(get lease_rows_before_cleanup) rows"
else
  fail cleanup_had_something_to_clean \
    "n=$(get lease_rows_before_cleanup); a cleanup that removes nothing proves nothing"
fi

if [ "$(get restart_recovery_possible)" = "True" ]; then
  pass restart_recovery_possible "leases=$(get leases_persisted) rows survive"
else
  fail restart_recovery_possible "nothing persisted"
fi

if [ "$(get rows_claiming_a_fetch)" = "0" ]; then
  pass no_lease_row_claims_a_fetch "the database refuses it"
else
  fail no_lease_row_claims_a_fetch "n=$(get rows_claiming_a_fetch)"
fi

if [ "$(get rows_over_attempt_budget)" = "0" ]; then
  pass no_row_exceeds_its_attempt_budget
else
  fail no_row_exceeds_its_attempt_budget "n=$(get rows_over_attempt_budget)"
fi

# ------------------------------------------------ 10. what stays zero
for zero in collectors_invoked live_source_calls network_calls threads_started \
  fixture_rows_remaining real_org_lease_rows; do
  if [ "$(get "$zero")" = "0" ]; then
    pass "stays_zero:$zero"
  else
    fail "stays_zero:$zero" "n=$(get "$zero")"
  fi
done

for flag in api_key_required worker_monitoring_live health_monitoring_live \
  artifact_claims_monitoring_live; do
  if [ "$(get "$flag")" = "False" ]; then
    pass "stays_false:$flag"
  else
    fail "stays_false:$flag" "became true"
  fi
done

# ------------------------------------- 11. guards are falsifiable
if [ "$(get completed_job_guard_fires)" = "True" ] &&
   [ "$(get retryable_guard_fires)" = "True" ]; then
  pass health_guards_are_falsifiable
else
  fail health_guards_are_falsifiable "a guard that never fires proves nothing"
fi

# ----------------------------- 12. no module reaches the network
if [ "$(getlist network_import_offenders)" = "none" ]; then
  pass no_worker_module_imports_the_network "parsed, not grepped"
else
  fail no_worker_module_imports_the_network "$(getlist network_import_offenders)"
fi

if [ "$(get network_scan_finds_a_known_import)" = "True" ]; then
  pass network_scan_can_actually_detect_one "control: backend_health_readiness"
else
  fail network_scan_can_actually_detect_one "the scan is blind"
fi

# ------------------------- 13. the detector this gate does not satisfy
if [ "$(get background_worker_still_absent)" = "True" ]; then
  pass background_worker_detector_deliberately_unsatisfied \
    "it looks for a module or an entry point; this gate adds a script"
else
  fail background_worker_detector_deliberately_unsatisfied
fi

# ------------------------------------------------------ 14. artifacts
if [ "$(get artifact_count)" = "9" ] &&
   [ "$(get artifacts_deterministic)" = "True" ] &&
   [ "$(get artifacts_on_disk_match)" = "True" ]; then
  pass artifacts "9 files, deterministic, match the builder"
else
  fail artifacts \
    "n=$(get artifact_count) det=$(get artifacts_deterministic) match=$(get artifacts_on_disk_match)"
fi

# ------------------------------------------------------ 15. the lane
if [ "$(getlist invariant_failures)" = "none" ]; then
  pass invariants "none_failed"
else
  fail invariants "$(getlist invariant_failures)"
fi

if [ "$(get worker_runtime_ready)" = "True" ]; then
  pass worker_runtime_ready
else
  fail worker_runtime_ready "$(getlist health_blockers)"
fi

# ---------------------------------------------------- 16. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

echo "RESULT=PASS"
echo "worker_runtime_ready=true"
echo "source_monitoring_live=false"
echo "scope=controlled_dev_demo"
echo "registry_rows=$(get registry_rows)"
echo "jobs_offered=$(get jobs_offered)"
echo "jobs_claimed=$(get jobs_claimed)"
echo "jobs_refused=$(get jobs_refused)"
echo "jobs_retryable=0"
echo "jobs_completed=0"
echo "duplicate_claim=refused"
echo "expired_lease=reclaimable"
echo "retry_bound=3 attempts, deterministic backoff, no jitter"
echo "non_transient_refusals_retried=0"
echo "permitting_branch=reachable_and_still_refuses"
echo "restart_recovery=lease_table"
echo "activation_allowlist_count=0"
echo "collectors_invoked=0"
echo "live_source_calls=0"
echo "network_calls=0"
echo "threads_started=0"
echo "api_key_required=false"
echo "background_worker_detector=still_absent (deliberately)"
echo "fixture_rows_remaining=0"
echo "alembic_head=0043 (nf_source_collection_job_leases)"
echo "next=docs/operations/821_GATE157_SOURCE_RUNTIME_DELTA.md"
exit 0
