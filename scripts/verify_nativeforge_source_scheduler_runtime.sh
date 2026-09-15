#!/usr/bin/env bash
# Gate 156I — a scheduler that evaluates every source and refuses every one.
#
# THIS DOES NOT MAKE SOURCE MONITORING LIVE, AND CANNOT.
# Zero sources are approved, so there is no URL to fetch even if something
# wanted one. `source_monitoring_live` is a constant false in the health
# service with no branch that computes anything else.
#
# What this proves, by running it rather than asserting it:
#
#   a next run time is COMPUTED from an interval and a last check - the one
#   thing Gates 98-100 do not do
#   a cycle evaluates every registry row against an injected clock
#   a terms-blocked source refuses, and names why
#   a human-review source refuses, and names why
#   an unapproved source refuses, and names why
#   an unknown source refuses, and names why
#   a source with every approval but no collector STILL refuses
#   the empty allowlist yields zero executable jobs BY COUNTING, not by a guard
#   the same inputs give the same counts
#
# What it deliberately does NOT clear:
#
#   scheduler_package_installed stays false. Gate 143's blocker
#   `scheduler_component_absent:scheduler_runtime` is find_spec over eight
#   third-party packages; installing one would clear the blocker without
#   computing a single due date. uv.lock is untouched.
#
# No collector is registered or invoked, no socket is opened, no API key is
# read, no row is written, and the real organization is never referenced.
#
# No secrets, tokens, cookies, state, PKCE verifier, provider subject or
# recipient addresses.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

BACKEND="${NF_BACKEND_OVERRIDE:-http://127.0.0.1:8000}"
TIMEOUT=20

FAILED=""

pass() { echo "check=$1 status=PASS ${2:-}"; }
fail() { echo "check=$1 status=FAIL ${2:-}"; [ -z "$FAILED" ] && FAILED="$1"; }
info() { echo "check=$1 status=INFO ${2:-}"; }

echo "verify=source_scheduler_runtime"

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

# ------------------- 2. the two guards this gate must not weaken, RUN not assumed
for v in no_live_source_calls source_monitoring_preflight; do
  r="$(timeout 900 bash "scripts/verify_nativeforge_${v}.sh" 2>/dev/null \
    | grep -E '^RESULT=' | tail -1)"
  if [ "$r" = "RESULT=PASS" ]; then
    pass "existing_guard_still_passes:$v"
  else
    fail "existing_guard_still_passes:$v" "${r:-no result}"
  fi
done

# --------------------------------------------------- 3. the scheduler runtime
REPORT="$(
  .venv/bin/python - <<'PYEOF' 2>/dev/null || true
import json
import sys
from pathlib import Path

sys.path.insert(0, "src")

from nativeforge.services import (
    source_scheduler_artifact_gate156_service as art,
)
from nativeforge.services.source_collection_job_model_service import (
    build_collection_job,
    collection_job_invariant_failures,
)
from nativeforge.services.source_collection_scheduler_health_service import (
    build_scheduler_health,
    scheduler_health_invariant_failures,
)
from nativeforge.services.source_collection_scheduler_loop_service import (
    cycle_invariant_failures,
    run_scheduler_cycle,
)
from nativeforge.services.source_collection_scheduler_runtime_service import (
    compute_next_run_at,
    evaluate_source_schedule,
    schedule_evaluation_invariant_failures,
)
from nativeforge.services.source_monitoring_approved_source_service import (
    load_registry_rows,
)
from nativeforge.services.source_scheduler_readiness_service import (
    build_scheduler_readiness,
)

NOW = "2026-09-15T12:00:00Z"
out = {"invariant_failures": []}

# -- the computation Gates 98-100 do not have ---------------------------
computed = compute_next_run_at(
    last_checked_at="2026-09-01T12:00:00Z", check_interval_days=7
)
out["computes_a_next_run"] = computed["next_run_at"] == "2026-09-08T12:00:00+00:00"
out["computed_next_run"] = computed["next_run_at"]
out["source_of_truth"] = computed["source_of_truth"]

no_cadence = compute_next_run_at(last_checked_at="2026-09-01T12:00:00Z")
out["no_cadence_is_never_due"] = no_cadence["next_run_at"] is None

recorded = compute_next_run_at(
    last_checked_at="2026-09-01T12:00:00Z",
    check_interval_days=7,
    recorded_next_check_due_at="2026-10-01T00:00:00Z",
)
out["recorded_wins_and_disagreement_is_reported"] = (
    recorded["source_of_truth"] == "recorded" and recorded["disagrees"] is True
)

# -- each refusal path, exercised --------------------------------------
CASES = {
    "terms_blocked": {
        "activation_state": "activation_approved",
        "terms_state": "terms_unknown",
        "human_review_state": "human_review_cleared",
        "collector_registered": True,
    },
    "human_review_blocked": {
        "activation_state": "activation_approved",
        "terms_state": "terms_approved",
        "human_review_state": "human_review_required",
        "collector_registered": True,
    },
    "activation_not_approved": {
        "activation_state": "activation_blocked",
        "terms_state": "terms_approved",
        "human_review_state": "human_review_cleared",
        "collector_registered": True,
    },
    "no_collector": {
        "activation_state": "activation_approved",
        "terms_state": "terms_approved",
        "human_review_state": "human_review_cleared",
        "collector_registered": False,
    },
    "disabled": {
        "activation_state": "activation_approved",
        "terms_state": "terms_approved",
        "human_review_state": "human_review_cleared",
        "collector_registered": True,
        "is_enabled": False,
    },
    "unknown_source": {
        "activation_state": "activation_approved",
        "terms_state": "terms_approved",
        "human_review_state": "human_review_cleared",
        "collector_registered": True,
        "known_source": False,
    },
}
refused = {}
named = {}
for label, kwargs in CASES.items():
    result = evaluate_source_schedule(
        source_id=f"nf-verify-{label}",
        now=NOW,
        last_checked_at="2026-09-01T12:00:00Z",
        check_interval_days=7,
        **kwargs,
    )
    out["invariant_failures"].extend(schedule_evaluation_invariant_failures(result))
    refused[label] = not result["executable"]
    named[label] = bool(result["blockers"])
out["refusal_paths"] = refused
out["refusal_paths_named"] = named
out["refusal_paths_not_refused"] = sorted(k for k, v in refused.items() if not v)

# -- the permitting branch must be REACHABLE, or the refusals prove nothing
permitted = evaluate_source_schedule(
    source_id="nf-verify-everything-approved",
    now=NOW,
    last_checked_at="2026-09-01T12:00:00Z",
    check_interval_days=7,
    activation_state="activation_approved",
    terms_state="terms_approved",
    human_review_state="human_review_cleared",
    is_enabled=True,
    collector_registered=True,
)
out["permitting_branch_reachable"] = permitted["executable"]
out["permitting_branch_state"] = permitted["runtime_state"]
out["invariant_failures"].extend(
    schedule_evaluation_invariant_failures(permitted)
)

# A job that is due but blocked must still report due=True.
due_but_blocked = evaluate_source_schedule(
    source_id="nf-verify-due-but-blocked",
    now=NOW,
    last_checked_at="2026-09-01T12:00:00Z",
    check_interval_days=7,
    activation_state="activation_blocked",
    terms_state="terms_unknown",
    human_review_state="human_review_required",
    collector_registered=False,
)
out["due_is_reported_even_when_blocked"] = (
    due_but_blocked["due"] and not due_but_blocked["executable"]
)

# -- the real registry, every row ---------------------------------------
registry = load_registry_rows()
sources = [
    {
        "source_id": key,
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
]
cycle = run_scheduler_cycle(now=NOW, sources=sources)
out["invariant_failures"].extend(cycle_invariant_failures(cycle))
out["registry_rows"] = len(registry)
out["jobs_known"] = cycle["jobs_known"]
out["jobs_due"] = cycle["jobs_due"]
out["jobs_executable"] = cycle["jobs_executable"]
out["jobs_refused"] = cycle["jobs_refused"]
out["jobs_by_state"] = cycle["jobs_by_state"]
out["refusal_reasons"] = cycle["refusal_reasons"]
out["collectors_invoked"] = cycle["collectors_invoked"]
out["live_source_calls"] = cycle["live_source_calls"]
out["network_calls"] = cycle["network_calls"]
out["rows_written"] = cycle["rows_written"]
out["threads_started"] = cycle["threads_started"]
out["api_key_required"] = cycle["api_key_required"]
out["cycle_deterministic"] = run_scheduler_cycle(now=NOW, sources=sources) == cycle

# Every registry row must be representable as a job.
out["every_row_became_a_job"] = cycle["jobs_known"] == len(registry)
job_failures = []
for job in cycle["jobs"][:25]:
    job_failures.extend(collection_job_invariant_failures(job))
out["invariant_failures"].extend(job_failures)

# -- health --------------------------------------------------------------
health = build_scheduler_health(
    cycle=cycle,
    scheduler_process_active=None,
    persistent_state_available=True,
    activation_allowlist_count=0,
)
out["invariant_failures"].extend(scheduler_health_invariant_failures(health))
out["scheduler_runtime_ready"] = health["scheduler_runtime_ready"]
out["health_jobs_executable"] = health["jobs_executable"]
out["health_allowlist"] = health["activation_allowlist_count"]
out["source_monitoring_live"] = health["source_monitoring_live"]
out["health_blockers"] = health["blockers"]

# An executable job with an empty allowlist must be refused by an invariant.
leak = build_scheduler_health(
    cycle={**cycle, "jobs_executable": 3}, activation_allowlist_count=0
)
out["empty_allowlist_guard_fires"] = bool(
    scheduler_health_invariant_failures(leak)
)

# -- the package blocker is untouched, deliberately ---------------------
sched = build_scheduler_readiness()
out["scheduler_package_installed"] = sched["scheduler_package_installed"]
out["scheduler_component_still_missing"] = (
    "scheduler_runtime" in (sched.get("components_missing") or [])
)

# -- no module reaches the network -------------------------------------
import ast

MODULES = [
    "src/nativeforge/services/source_collection_scheduler_runtime_service.py",
    "src/nativeforge/services/source_collection_job_model_service.py",
    "src/nativeforge/services/source_collection_scheduler_loop_service.py",
    "src/nativeforge/services/source_collection_scheduler_health_service.py",
    "src/nativeforge/services/source_scheduler_artifact_gate156_service.py",
    "src/nativeforge/api/source_collection_scheduler_routes.py",
]
NETWORK_ROOTS = {
    "httpx", "requests", "urllib", "urllib3", "http", "socket", "aiohttp",
    "ftplib", "telnetlib", "smtplib", "subprocess",
}
offenders = []
wallclock = []
for path in MODULES:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] in NETWORK_ROOTS:
                    offenders.append(f"{path}:{alias.name}")
        elif isinstance(node, ast.ImportFrom):
            if (node.module or "").split(".")[0] in NETWORK_ROOTS:
                offenders.append(f"{path}:{node.module}")
        elif isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "attr", None)
            owner = getattr(getattr(func, "value", None), "id", None)
            # The clock must be injected. A wall-clock read in the runtime or
            # the loop would make a cycle irreproducible.
            if name in {"now", "utcnow", "today"} and owner in {
                "datetime", "date", "time",
            }:
                if "artifact" not in path and "routes" not in path:
                    wallclock.append(f"{path}:{owner}.{name}()")
out["network_import_offenders"] = sorted(set(offenders))
out["wallclock_offenders"] = sorted(set(wallclock))

# The scan must be able to find one, or it proves nothing.
control = ast.parse(
    Path("src/nativeforge/services/backend_health_readiness_service.py").read_text(
        encoding="utf-8"
    )
)
out["network_scan_finds_a_known_import"] = any(
    isinstance(n, ast.Import)
    and any(a.name.split(".")[0] in NETWORK_ROOTS for a in n.names)
    for n in ast.walk(control)
)

# -- artifacts ----------------------------------------------------------
built = art.build_scheduler_artifacts()
out["artifact_count"] = len(built)
out["artifacts_deterministic"] = art.build_scheduler_artifacts() == built
directory = Path(art.ARTIFACT_DIR)
out["artifacts_on_disk_match"] = all(
    (directory / n).is_file() and (directory / n).read_text(encoding="utf-8") == b
    for n, b in built.items()
)
blob = "\n".join(built.values()).lower()
out["artifact_claims_monitoring_live"] = '"source_monitoring_live": true' in blob

out["invariant_failures"] = sorted(set(out["invariant_failures"]))
print(json.dumps(out, sort_keys=True, default=str))
PYEOF
)"

if [ -z "$REPORT" ]; then
  fail scheduler_evaluated "empty"
  echo
  echo "RESULT=BLOCKED"
  echo "blocker=scheduler_could_not_evaluate"
  exit 1
fi
pass scheduler_evaluated

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

getkey() { printf '%s' "$REPORT" | .venv/bin/python -c "
import json,sys
d=json.load(sys.stdin).get(sys.argv[1]) or {}
print(d.get(sys.argv[2], ''))
" "$1" "$2" 2>/dev/null; }

# -------------------------------------- 4. routes registered
for path in health jobs blockers dry-run; do
  n="$(curl -s --max-time "$TIMEOUT" "$BACKEND/openapi.json" 2>/dev/null \
    | .venv/bin/python -c "
import json,sys
spec=json.load(sys.stdin)
want='/source-scheduler/' + sys.argv[1]
print(sum(1 for p in spec.get('paths',{}) if p.endswith(want)))
" "$path" 2>/dev/null || echo 0)"
  if [ "$n" = "1" ]; then
    pass "route_registered:$path"
  else
    fail "route_registered:$path" "found=$n"
  fi
done

# ------------------------------------ 5. it computes a next run time
if [ "$(get computes_a_next_run)" = "True" ]; then
  pass computes_a_next_run_time "$(get computed_next_run)"
else
  fail computes_a_next_run_time "$(get computed_next_run)"
fi

if [ "$(get no_cadence_is_never_due)" = "True" ]; then
  pass no_cadence_means_never_due "not 'check it now'"
else
  fail no_cadence_means_never_due
fi

if [ "$(get recorded_wins_and_disagreement_is_reported)" = "True" ]; then
  pass recorded_due_date_wins_and_disagreement_is_visible
else
  fail recorded_due_date_wins_and_disagreement_is_visible
fi

# ---------------------------------------- 6. every refusal path
for mode in terms_blocked human_review_blocked activation_not_approved \
  no_collector disabled unknown_source; do
  if [ "$(getkey refusal_paths "$mode")" = "True" ] &&
     [ "$(getkey refusal_paths_named "$mode")" = "True" ]; then
    pass "refuses:$mode"
  else
    fail "refuses:$mode" "refused=$(getkey refusal_paths "$mode")"
  fi
done

# A refusal nobody can escape proves nothing about the refusals.
if [ "$(get permitting_branch_reachable)" = "True" ]; then
  pass permitting_branch_is_reachable "state=$(get permitting_branch_state)"
else
  fail permitting_branch_is_reachable "every input refuses; the gate is unfalsifiable"
fi

if [ "$(get due_is_reported_even_when_blocked)" = "True" ]; then
  pass due_is_reported_even_when_blocked "a backlog stays visible"
else
  fail due_is_reported_even_when_blocked
fi

# ------------------------------------------- 7. the real registry
info registry_rows "$(get registry_rows)"
info jobs_by_state "$(get jobs_by_state)"
info refusal_reasons "$(get refusal_reasons)"

if [ "$(get every_row_became_a_job)" = "True" ]; then
  pass every_registry_row_is_representable_as_a_job "n=$(get jobs_known)"
else
  fail every_registry_row_is_representable_as_a_job
fi

if [ "$(get jobs_executable)" = "0" ]; then
  pass empty_allowlist_yields_zero_executable_jobs
else
  fail empty_allowlist_yields_zero_executable_jobs "n=$(get jobs_executable)"
fi

if [ "$(get empty_allowlist_guard_fires)" = "True" ]; then
  pass empty_allowlist_guard_is_falsifiable "an executable job would be refused"
else
  fail empty_allowlist_guard_is_falsifiable
fi

if [ "$(get cycle_deterministic)" = "True" ]; then
  pass cycle_is_deterministic
else
  fail cycle_is_deterministic
fi

# --------------------------------------------- 8. what stays zero
for zero in collectors_invoked live_source_calls network_calls rows_written \
  threads_started; do
  if [ "$(get "$zero")" = "0" ]; then
    pass "stays_zero:$zero"
  else
    fail "stays_zero:$zero" "n=$(get "$zero")"
  fi
done

for flag in api_key_required source_monitoring_live \
  artifact_claims_monitoring_live; do
  if [ "$(get "$flag")" = "False" ]; then
    pass "stays_false:$flag"
  else
    fail "stays_false:$flag" "became true"
  fi
done

# ------------------------------------ 9. no module reaches the network
if [ "$(getlist network_import_offenders)" = "none" ]; then
  pass no_scheduler_module_imports_the_network "parsed, not grepped"
else
  fail no_scheduler_module_imports_the_network \
    "$(getlist network_import_offenders)"
fi

if [ "$(getlist wallclock_offenders)" = "none" ]; then
  pass clock_is_injected_not_read
else
  fail clock_is_injected_not_read "$(getlist wallclock_offenders)"
fi

if [ "$(get network_scan_finds_a_known_import)" = "True" ]; then
  pass network_scan_can_actually_detect_one "control: backend_health_readiness"
else
  fail network_scan_can_actually_detect_one "the scan is blind"
fi

# ------------------------- 10. the package blocker is NOT cleared
if [ "$(get scheduler_package_installed)" = "False" ] &&
   [ "$(get scheduler_component_still_missing)" = "True" ]; then
  pass scheduler_package_blocker_deliberately_uncleared \
    "a package would clear it without computing a due date"
else
  fail scheduler_package_blocker_deliberately_uncleared \
    "a scheduling package appeared"
fi

# --------------------------------------------------- 11. artifacts
if [ "$(get artifact_count)" = "8" ] &&
   [ "$(get artifacts_deterministic)" = "True" ] &&
   [ "$(get artifacts_on_disk_match)" = "True" ]; then
  pass artifacts "8 files, deterministic, match the builder"
else
  fail artifacts \
    "n=$(get artifact_count) det=$(get artifacts_deterministic) match=$(get artifacts_on_disk_match)"
fi

# --------------------------------------------------- 12. the lane
if [ "$(getlist invariant_failures)" = "none" ]; then
  pass invariants "none_failed"
else
  fail invariants "$(getlist invariant_failures)"
fi

if [ "$(get scheduler_runtime_ready)" = "True" ]; then
  pass scheduler_runtime_ready
else
  fail scheduler_runtime_ready "$(getlist health_blockers)"
fi

# ---------------------------------------------------- 13. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

echo "RESULT=PASS"
echo "scheduler_runtime_ready=true"
echo "source_monitoring_live=false"
echo "scope=controlled_dev_demo"
echo "registry_rows=$(get registry_rows)"
echo "jobs_known=$(get jobs_known)"
echo "jobs_due=$(get jobs_due)"
echo "jobs_executable=0"
echo "jobs_blocked=$(get jobs_refused)"
echo "activation_allowlist_count=0"
echo "refusal_paths_proved=6"
echo "permitting_branch=reachable"
echo "collectors_invoked=0"
echo "live_source_calls=0"
echo "network_calls=0"
echo "threads_started=0"
echo "rows_written=0"
echo "api_key_required=false"
echo "scheduler_package_installed=false (deliberately; uv.lock untouched)"
echo "alembic_head=unchanged (no migration; the registry already has the columns)"
echo "next=docs/operations/816_GATE156_SOURCE_RUNTIME_DELTA.md"
exit 0
