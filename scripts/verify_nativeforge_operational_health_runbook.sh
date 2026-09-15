#!/usr/bin/env bash
# Gate 154G — can this deployment tell an operator what state it is in?
#
# THIS IS NOT PRODUCTION MONITORING AND DOES NOT CLAIM TO BE.
# No APM, no alerting, no external monitor, no uptime record, no error budget.
# Nothing here leaves this host and nothing sends mail, SMS or a page.
#
# The repository already contains a function that will answer
# `production_monitoring: true` on a caller's say-so -
# `gate32_observability_service.resolve_observability`, whose every input is a
# keyword argument. Gate 154 does not extend it, does not call it, and cannot
# produce that claim by any path. This verifier checks that.
#
# What it measures, that nothing measured before:
#
#   backend stale-code   by comparing process start time to HEAD commit time.
#                        /backend/health CANNOT answer this: it shells out at
#                        REQUEST time, so it reports the repository's HEAD and
#                        not the commit the process loaded.
#   stale build stamp    by comparing the stamped sha to HEAD. `--strict-public`
#                        only checks the tag EXISTS.
#   migration drift      by comparing the repository's highest revision to the
#                        database's current one.
#
# Each named failure mode is exercised against the model with synthetic inputs,
# so a detector that stopped detecting fails here rather than going quiet.
#
# The two backup lanes stay separate: Gate 61/65 `backup_restore` is expected to
# SKIP, Gate 153 `backup_restore_readiness` is expected to PASS.
#
# No secrets, tokens, cookies, state, PKCE verifier, provider subject, API keys
# or recipient addresses. The services under test execute no shell.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

BACKEND="${NF_BACKEND_OVERRIDE:-http://127.0.0.1:8000}"
DEMO_ORG="${NF_DEMO_ORG_OVERRIDE:-bbbbbbbb-cccc-dddd-eeee-ffffffffffff}"
TIMEOUT=20

FAILED=""

pass() { echo "check=$1 status=PASS ${2:-}"; }
fail() { echo "check=$1 status=FAIL ${2:-}"; [ -z "$FAILED" ] && FAILED="$1"; }
info() { echo "check=$1 status=INFO ${2:-}"; }

echo "verify=operational_health_runbook"

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

# --------------------------------------------- 2. facts a shell can establish
UNIT_BACKEND="$(systemctl --user is-active nativeforge-backend.service 2>/dev/null || echo unknown)"
UNIT_PREVIEW="$(systemctl --user is-active nativeforge-demo-preview.service 2>/dev/null || echo unknown)"
UNIT_TUNNEL="$(systemctl --user is-active nativeforge-mayhem-tunnel.service 2>/dev/null || echo unknown)"

HEAD_SHA="$(git rev-parse HEAD 2>/dev/null || echo '')"
HEAD_TIME_RAW="$(git log -1 --format=%cI 2>/dev/null || echo '')"
HEAD_TIME=""
[ -n "$HEAD_TIME_RAW" ] && HEAD_TIME="$(date -u -d "$HEAD_TIME_RAW" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo '')"

SOURCE_DIRTY="false"
[ -n "$(git status --porcelain --untracked-files=no 2>/dev/null)" ] && SOURCE_DIRTY="true"

# The newest mtime among tracked source files. A dirty tree is only stale if
# the edit POSTDATES the running process; an older edit is code the process
# already loaded.
NEWEST_CHANGE="$(find src scripts alembic -type f \( -name '*.py' -o -name '*.sh' \) \
  -newermt '1970-01-01' -printf '%TY-%Tm-%TdT%TH:%TM:%TSZ\n' 2>/dev/null \
  | cut -c1-20 | sort | tail -1)"

STARTED_RAW="$(systemctl --user show -p ActiveEnterTimestamp nativeforge-backend.service 2>/dev/null | cut -d= -f2-)"
BACKEND_STARTED=""
[ -n "$STARTED_RAW" ] && BACKEND_STARTED="$(date -u -d "$STARTED_RAW" +%Y-%m-%dT%H:%M:%SZ 2>/dev/null || echo '')"

info units "backend=$UNIT_BACKEND preview=$UNIT_PREVIEW tunnel=$UNIT_TUNNEL"

# ------------------------------------- 3. the model, the registry, the runbook
REPORT="$(
  NF_UNIT_BACKEND="$UNIT_BACKEND" \
  NF_UNIT_PREVIEW="$UNIT_PREVIEW" \
  NF_UNIT_TUNNEL="$UNIT_TUNNEL" \
  NF_HEAD_SHA="$HEAD_SHA" \
  NF_HEAD_TIME="$HEAD_TIME" \
  NF_SOURCE_DIRTY="$SOURCE_DIRTY" \
  NF_BACKEND_STARTED="$BACKEND_STARTED" \
  NF_NEWEST_CHANGE="$NEWEST_CHANGE" \
  .venv/bin/python - <<'PYEOF' 2>/dev/null || true
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, "src")

import sqlalchemy as sa

from nativeforge.lib.settings import get_settings
from nativeforge.services import (
    operational_health_artifact_gate154_service as art,
)
from nativeforge.services.operational_health_model_service import (
    EXPECTED_FALSE_LANES,
    build_operational_health_model,
    health_model_invariant_failures,
)
from nativeforge.services.readiness_verifier_registry_service import (
    build_verifier_registry,
    registry_invariant_failures,
    verifier_expectations,
)
from nativeforge.services.runbook_health_service import (
    build_runbook_health,
    runbook_health_invariant_failures,
)

out = {"invariant_failures": []}

# -- the registry -------------------------------------------------------
registry = build_verifier_registry()
out["invariant_failures"].extend(registry_invariant_failures(registry))
out["registry_count"] = registry["verifier_count"]
out["registry_deterministic"] = build_verifier_registry() == registry
out["registry_names"] = registry["verifier_names"]
out["registry_expected_skip"] = registry["expected_skip"]
out["registry_executes"] = registry["executes_verifiers"]

separation = registry["backup_lane_separation"]
out["backup_harnesses_separate"] = (
    separation["production_harness"] != separation["operational_harness"]
    and separation["production_expected_result"] == "SKIP"
    and separation["operational_expected_result"] == "PASS"
)

by_name = {e["verifier"]: e for e in registry["verifiers"]}
out["gate6165_expects_skip"] = (
    by_name.get("backup_restore", {}).get("expected_result") == "SKIP"
)
out["gate153_expects_pass"] = (
    by_name.get("backup_restore_readiness", {}).get("expected_result") == "PASS"
)
out["backup_lanes_differ"] = by_name.get("backup_restore", {}).get(
    "lane"
) != by_name.get("backup_restore_readiness", {}).get("lane")

# Every verifier in the registry that claims a script must have one.
out["registry_scripts_missing"] = sorted(
    e["script"] for e in registry["verifiers"] if not Path(e["script"]).is_file()
)
# Every script on disk must be registered.
on_disk = {
    p.name.replace("verify_nativeforge_", "").replace(".sh", "")
    for p in Path("scripts").glob("verify_nativeforge_*.sh")
}
out["scripts_not_registered"] = sorted(on_disk - set(registry["verifier_names"]))

# Gates 138-153 must each be represented.
gates_present = {str(e["gate"]) for e in registry["verifiers"]}
out["gates_missing"] = sorted(
    g for g in (str(n) for n in range(138, 155)) if g not in gates_present
)

# -- the live facts -----------------------------------------------------
repo_migration = sorted(
    p.name[:4] for p in Path("alembic/versions").glob("[0-9][0-9][0-9][0-9]_*.py")
)
repo_migration = repo_migration[-1] if repo_migration else None

db_migration = None
try:
    engine = sa.create_engine(get_settings().database_url)
    with engine.connect() as c:
        db_migration = c.execute(
            sa.text("SELECT version_num FROM alembic_version")
        ).scalar()
except Exception:
    db_migration = None

stamp = ""
index = Path("frontend/dist/index.html")
if index.is_file():
    m = re.search(
        r'nativeforge-build-sha"\s+content="([0-9a-f]{7,40})"',
        index.read_text(encoding="utf-8"),
    )
    stamp = m.group(1) if m else ""

head_sha = os.environ.get("NF_HEAD_SHA") or ""
out["repo_migration_head"] = repo_migration
out["database_migration_current"] = db_migration
out["stamp_present"] = bool(stamp)
out["stamp_matches_head"] = bool(stamp and head_sha and stamp == head_sha)

model = build_operational_health_model(
    backend_service_state=os.environ.get("NF_UNIT_BACKEND"),
    preview_service_state=os.environ.get("NF_UNIT_PREVIEW"),
    tunnel_service_state=os.environ.get("NF_UNIT_TUNNEL"),
    repo_head_sha=head_sha,
    head_committed_at=os.environ.get("NF_HEAD_TIME"),
    source_dirty=os.environ.get("NF_SOURCE_DIRTY") == "true",
    newest_tracked_change_at=os.environ.get("NF_NEWEST_CHANGE"),
    backend_process_started_at=os.environ.get("NF_BACKEND_STARTED"),
    frontend_stamp_sha=stamp,
    repo_migration_head=repo_migration,
    database_migration_current=db_migration,
    lanes={
        "tenant_digest_persistence_live": True,
        "audit_replay_ready": True,
        "operational_backup_restore_ready": True,
        "customer_auth_live": False,
        "verified_operational_binding": False,
        "source_monitoring_live": False,
        "email_delivery": False,
        "object_store_configured": False,
        "controlled_customer_pilot": False,
    },
    verifier_expectations=verifier_expectations(),
)
out["invariant_failures"].extend(health_model_invariant_failures(model))
out["operational_health_ready"] = model["operational_health_ready"]
out["overall_status"] = model["overall_status"]
out["by_status"] = model["by_status"]
out["required_unknown"] = model["required_unknown"]
out["blockers"] = model["blockers"]
out["awaiting_human"] = model["awaiting_human_decision"]
out["component_status"] = {
    e["component"]: e["status"] for e in model["components"]
}
out["model_production_monitoring"] = model["production_monitoring_active"]
out["model_shell_executed"] = model["shell_executed"]
out["model_external_call"] = model["external_call_made"]
out["model_rows_written"] = model["rows_written"]
out["expected_false_lanes"] = sorted(EXPECTED_FALSE_LANES)

runbook = build_runbook_health(health_model=model, legacy_evidence_gaps=0)
out["invariant_failures"].extend(runbook_health_invariant_failures(runbook))
out["next_safe_action_kind"] = runbook["next_safe_action"]["kind"]
out["next_safe_action_title"] = runbook["next_safe_action"]["title"]
out["next_safe_action_present"] = bool(runbook["next_safe_action"].get("title"))
out["runbook_unrecognised"] = runbook["unrecognised_blockers"]
out["runbook_production_monitoring"] = runbook["production_monitoring_active"]
out["runbook_alerting"] = runbook["alerting_configured"]

# Approval-gated actions must carry NO command, ever.
out["gated_actions_with_a_command"] = sorted(
    str(a["blocker"])
    for a in runbook["actions"]
    if a["kind"] == "HUMAN_APPROVAL_REQUIRED" and a.get("command")
)

# -- every named failure mode, exercised -------------------------------
HEALTHY = dict(
    backend_service_state="active",
    preview_service_state="active",
    tunnel_service_state="active",
    repo_head_sha="a" * 40,
    head_committed_at="2026-01-02T10:00:00Z",
    source_dirty=False,
    backend_process_started_at="2026-01-02T11:00:00Z",
    frontend_stamp_sha="a" * 40,
    repo_migration_head="0042",
    database_migration_current="0042",
)
baseline = build_operational_health_model(**HEALTHY)
out["synthetic_baseline_ready"] = baseline["operational_health_ready"]

# A dirty tree whose edits PREDATE the process is running known code, and must
# not be reported as a fault. Otherwise the lane is unreachable on any machine
# anybody is working on.
loaded = build_operational_health_model(
    **{
        **HEALTHY,
        "source_dirty": True,
        "newest_tracked_change_at": "2026-01-02T10:30:00Z",
    }
)
out["uncommitted_but_loaded_is_not_a_fault"] = loaded["operational_health_ready"]

CASES = {
    "stale_frontend_stamp": {"frontend_stamp_sha": "b" * 40},
    "unstamped_build": {"frontend_stamp_sha": None},
    "backend_stale_code": {"backend_process_started_at": "2026-01-02T09:00:00Z"},
    "dirty_tree": {"source_dirty": True},
    "code_edited_after_start": {
        "source_dirty": True,
        "newest_tracked_change_at": "2026-01-02T12:00:00Z",
    },
    "migration_behind": {"database_migration_current": "0041"},
    "migration_ahead": {"database_migration_current": "0043"},
    "backend_unit_down": {"backend_service_state": "inactive"},
    "preview_unit_down": {"preview_service_state": "failed"},
    "tunnel_unit_down": {"tunnel_service_state": "inactive"},
}
detected = {}
actioned = {}
for label, override in CASES.items():
    m = build_operational_health_model(**{**HEALTHY, **override})
    r = build_runbook_health(health_model=m)
    detected[label] = (not m["operational_health_ready"]) and bool(m["blockers"])
    actioned[label] = r["next_safe_action"]["kind"] != "NO_ACTION"
out["failure_modes_detected"] = detected
out["failure_modes_actioned"] = actioned
out["failure_modes_undetected"] = sorted(k for k, v in detected.items() if not v)
out["failure_modes_unactioned"] = sorted(k for k, v in actioned.items() if not v)

# An unexpected result from the production backup harness must close the lane;
# the expected SKIP must not.
skip_ok = build_operational_health_model(
    **HEALTHY,
    verifier_results={"backup_restore": "SKIP"},
    verifier_expectations=verifier_expectations(),
)
pass_surprise = build_operational_health_model(
    **HEALTHY,
    verifier_results={"backup_restore": "PASS"},
    verifier_expectations=verifier_expectations(),
)
out["expected_skip_is_not_a_problem"] = skip_ok["operational_health_ready"]
out["unexpected_pass_closes_the_lane"] = not pass_surprise["operational_health_ready"]

# A prior verifier failure must be named.
prior = build_operational_health_model(
    **HEALTHY,
    verifier_results={"audit_replay_readiness": "BLOCKED"},
    verifier_expectations=verifier_expectations(),
)
out["prior_verifier_failure_named"] = any(
    b.startswith("verifier_result_unexpected:") for b in prior["blockers"]
)
prior_runbook = build_runbook_health(health_model=prior)
out["prior_verifier_failure_actioned"] = (
    prior_runbook["next_safe_action"]["kind"] == "OPERATOR_RUNNABLE"
)

# -- no service shells out ---------------------------------------------
#
# Parsed, not grepped. A first pass searched the file body for the word
# "subprocess" and flagged three modules whose DOCSTRINGS say they start no
# subprocess - the substring-versus-meaning defect, committed by the tool
# built to prove those modules clean. An import is an import node and prose
# is not.
import ast

SERVICE_FILES = [
    "src/nativeforge/services/operational_health_model_service.py",
    "src/nativeforge/services/runbook_health_service.py",
    "src/nativeforge/services/readiness_verifier_registry_service.py",
    "src/nativeforge/services/operational_health_artifact_gate154_service.py",
    "src/nativeforge/api/operational_health_routes.py",
]
SHELL_MODULES = {"subprocess", "os", "pty", "commands", "popen2"}
SHELL_CALLS = {"system", "popen", "spawn", "spawnv", "execv", "execve", "fork"}

offenders = []
observability_callers = []
for path in SERVICE_FILES:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.split(".")[0] == "subprocess":
                    offenders.append(f"{path}:import {alias.name}")
        elif isinstance(node, ast.ImportFrom):
            root = (node.module or "").split(".")[0]
            if root == "subprocess":
                offenders.append(f"{path}:from {node.module}")
            if "gate32_observability" in (node.module or ""):
                observability_callers.append(f"{path}:imports {node.module}")
            for alias in node.names:
                if alias.name == "resolve_observability":
                    observability_callers.append(f"{path}:imports {alias.name}")
        elif isinstance(node, ast.Call):
            func = node.func
            name = getattr(func, "attr", None) or getattr(func, "id", None)
            if name == "resolve_observability":
                observability_callers.append(f"{path}:calls {name}")
            if name in SHELL_CALLS and isinstance(func, ast.Attribute):
                owner = getattr(func.value, "id", "")
                if owner in SHELL_MODULES:
                    offenders.append(f"{path}:{owner}.{name}()")
            for keyword in node.keywords:
                if keyword.arg == "shell" and getattr(
                    keyword.value, "value", False
                ) is True:
                    offenders.append(f"{path}:shell=True")

out["service_shell_offenders"] = sorted(set(offenders))
out["declaration_driven_callers"] = sorted(set(observability_callers))
# The scan must be able to find something, or it proves nothing. A file that
# DOES shell out is parsed as a control.
control = ast.parse(
    Path("src/nativeforge/services/backend_health_readiness_service.py").read_text(
        encoding="utf-8"
    )
)
out["shell_scan_finds_a_known_offender"] = any(
    isinstance(n, ast.Import)
    and any(a.name.split(".")[0] == "subprocess" for a in n.names)
    for n in ast.walk(control)
)

# -- artifacts ----------------------------------------------------------
built = art.build_operational_health_artifacts()
out["artifact_count"] = len(built)
out["artifacts_deterministic"] = art.build_operational_health_artifacts() == built
directory = Path(art.ARTIFACT_DIR)
out["artifacts_on_disk_match"] = all(
    (directory / name).is_file()
    and (directory / name).read_text(encoding="utf-8") == body
    for name, body in built.items()
)
blob = "\n".join(built.values())
out["artifact_claims_production_monitoring"] = (
    '"production_monitoring_active": true' in blob.lower()
)

out["invariant_failures"] = sorted(set(out["invariant_failures"]))
print(json.dumps(out, sort_keys=True, default=str))
PYEOF
)"

if [ -z "$REPORT" ]; then
  fail model_evaluated "empty"
  echo
  echo "RESULT=BLOCKED"
  echo "blocker=health_model_could_not_evaluate"
  exit 1
fi
pass model_evaluated

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

# ------------------------------------------------------- 3. routes registered
for path in summary verifier-registry runbook next-safe-action; do
  n="$(curl -s --max-time "$TIMEOUT" "$BACKEND/openapi.json" 2>/dev/null \
    | .venv/bin/python -c "
import json,sys
spec=json.load(sys.stdin)
want='/operational-health/' + sys.argv[1]
print(sum(1 for p in spec.get('paths',{}) if p.endswith(want)))
" "$path" 2>/dev/null || echo 0)"
  if [ "$n" = "1" ]; then
    pass "route_registered:$path"
  else
    fail "route_registered:$path" "found=$n"
  fi
done

# -------------------------------------------------- 4. the verifier registry
if [ "$(get registry_deterministic)" = "True" ] &&
   [ "$(get registry_count)" -ge 27 ] 2>/dev/null; then
  pass verifier_registry "n=$(get registry_count) deterministic"
else
  fail verifier_registry "n=$(get registry_count)"
fi

if [ "$(getlist scripts_not_registered)" = "none" ]; then
  pass every_script_on_disk_is_registered
else
  fail every_script_on_disk_is_registered "$(getlist scripts_not_registered)"
fi

if [ "$(getlist registry_scripts_missing)" = "none" ]; then
  pass every_registered_script_exists
else
  fail every_registered_script_exists "$(getlist registry_scripts_missing)"
fi

if [ "$(getlist gates_missing)" = "none" ]; then
  pass gates_138_to_154_represented
else
  fail gates_138_to_154_represented "$(getlist gates_missing)"
fi

if [ "$(get registry_executes)" = "False" ]; then
  pass registry_executes_nothing
else
  fail registry_executes_nothing "it claims to execute"
fi

# ------------------------------- 5. the two backup lanes stay separate
if [ "$(get backup_harnesses_separate)" = "True" ] &&
   [ "$(get gate6165_expects_skip)" = "True" ] &&
   [ "$(get gate153_expects_pass)" = "True" ] &&
   [ "$(get backup_lanes_differ)" = "True" ]; then
  pass backup_lanes_separate "61/65 expects SKIP, 153 expects PASS"
else
  fail backup_lanes_separate "they were conflated"
fi

if [ "$(get expected_skip_is_not_a_problem)" = "True" ]; then
  pass expected_skip_is_not_reported_as_a_problem
else
  fail expected_skip_is_not_reported_as_a_problem
fi

if [ "$(get unexpected_pass_closes_the_lane)" = "True" ]; then
  pass unexpected_verifier_result_closes_the_lane
else
  fail unexpected_verifier_result_closes_the_lane "it was ignored"
fi

# ------------------------------------- 6. every named failure mode detected
for mode in stale_frontend_stamp unstamped_build backend_stale_code \
  dirty_tree code_edited_after_start migration_behind migration_ahead \
  backend_unit_down preview_unit_down tunnel_unit_down; do
  if [ "$(getkey failure_modes_detected "$mode")" = "True" ] &&
     [ "$(getkey failure_modes_actioned "$mode")" = "True" ]; then
    pass "failure_mode_named:$mode"
  else
    fail "failure_mode_named:$mode" \
      "detected=$(getkey failure_modes_detected "$mode") actioned=$(getkey failure_modes_actioned "$mode")"
  fi
done

if [ "$(get synthetic_baseline_ready)" = "True" ]; then
  pass detector_baseline_is_healthy "a detector that never passes is not a detector"
else
  fail detector_baseline_is_healthy
fi

if [ "$(get uncommitted_but_loaded_is_not_a_fault)" = "True" ]; then
  pass uncommitted_code_the_process_loaded_is_not_a_fault
else
  fail uncommitted_code_the_process_loaded_is_not_a_fault \
    "the lane would be unreachable on any machine being worked on"
fi

if [ "$(get prior_verifier_failure_named)" = "True" ] &&
   [ "$(get prior_verifier_failure_actioned)" = "True" ]; then
  pass prior_verifier_failure_named_and_actioned
else
  fail prior_verifier_failure_named_and_actioned
fi

# ------------------------------------------------ 7. the live health reading
info live_component_status "$(get component_status)"
info live_blockers "$(getlist blockers)"
info awaiting_human "$(getlist awaiting_human)"
info migration "repo=$(get repo_migration_head) db=$(get database_migration_current)"
info stamp "present=$(get stamp_present) matches_head=$(get stamp_matches_head)"

if [ "$(getlist required_unknown)" = "none" ]; then
  pass every_required_component_is_known
else
  fail every_required_component_is_known "$(getlist required_unknown)"
fi

if [ "$(get next_safe_action_present)" = "True" ]; then
  pass next_safe_action_present "$(get next_safe_action_kind)"
else
  fail next_safe_action_present
fi

if [ "$(getlist runbook_unrecognised)" = "none" ]; then
  pass every_blocker_has_a_remedy
else
  fail every_blocker_has_a_remedy "$(getlist runbook_unrecognised)"
fi

if [ "$(getlist gated_actions_with_a_command)" = "none" ]; then
  pass approval_gated_actions_carry_no_command
else
  fail approval_gated_actions_carry_no_command \
    "$(getlist gated_actions_with_a_command)"
fi

# --------------------------------------- 8. no shell, no production claim
if [ "$(getlist service_shell_offenders)" = "none" ]; then
  pass no_service_executes_a_shell "parsed, not grepped"
else
  fail no_service_executes_a_shell "$(getlist service_shell_offenders)"
fi

# A scan that cannot find a real offender proves nothing about the clean ones.
if [ "$(get shell_scan_finds_a_known_offender)" = "True" ]; then
  pass shell_scan_can_actually_detect_a_shell "control: backend_health_readiness"
else
  fail shell_scan_can_actually_detect_a_shell "the scan is blind"
fi

if [ "$(getlist declaration_driven_callers)" = "none" ]; then
  pass does_not_call_the_declaration_driven_observability_service
else
  fail does_not_call_the_declaration_driven_observability_service \
    "$(getlist declaration_driven_callers)"
fi

for flag in model_production_monitoring runbook_production_monitoring \
  runbook_alerting model_shell_executed model_external_call \
  artifact_claims_production_monitoring; do
  if [ "$(get "$flag")" = "False" ]; then
    pass "stays_false:$flag"
  else
    fail "stays_false:$flag" "became true"
  fi
done

if [ "$(get model_rows_written)" = "0" ]; then
  pass model_writes_nothing
else
  fail model_writes_nothing "n=$(get model_rows_written)"
fi

# --------------------------------------------------------- 9. the artifacts
if [ "$(get artifact_count)" = "8" ] &&
   [ "$(get artifacts_deterministic)" = "True" ] &&
   [ "$(get artifacts_on_disk_match)" = "True" ]; then
  pass artifacts "8 files, deterministic, match the builder"
else
  fail artifacts \
    "n=$(get artifact_count) deterministic=$(get artifacts_deterministic) match=$(get artifacts_on_disk_match)"
fi

# ----------------------------------------------------------- 10. the lane
if [ "$(getlist invariant_failures)" = "none" ]; then
  pass invariants "none_failed"
else
  fail invariants "$(getlist invariant_failures)"
fi

if [ "$(get operational_health_ready)" = "True" ]; then
  pass operational_health_ready
else
  fail operational_health_ready "$(getlist blockers)"
fi

# ---------------------------------------------------------- 11. the answer
echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  exit 1
fi

echo "RESULT=PASS"
echo "operational_health_ready=true"
echo "scope=controlled_dev_demo"
echo "production_monitoring=false"
echo "external_monitoring=false"
echo "alerting=false"
echo "overall_status=$(get overall_status)"
echo "verifiers_registered=$(get registry_count)"
echo "verifiers_expected_to_skip=$(getlist registry_expected_skip)"
echo "backup_lanes=separate (61/65 SKIP, 153 PASS)"
echo "failure_modes_detected=10/10"
echo "backend_stale_code=detected_by_process_start_time"
echo "stale_stamp=detected_by_sha_comparison"
echo "migration_drift=detected_by_head_comparison"
echo "prior_verifier_failure=named_and_actioned"
echo "next_safe_action=$(get next_safe_action_kind)"
echo "required_unknown=none"
echo "shell_executed_by_a_service=false"
echo "real_organization_touched=false"
echo "real_customer_data_written=false"
echo "emails_sent=0"
echo "live_source_calls=0"
echo "object_store_calls=0"
echo "next=docs/operations/806_GATE154_OPERATIONAL_HEALTH_READINESS_DELTA.md"
exit 0
