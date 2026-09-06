#!/usr/bin/env bash
# Gate 143E — is any live-source call path active anywhere in this checkout?
#
# RESULT=PASS only when nothing can reach a grant source: no collector is
# activated, no unapproved network call site exists in `services/`, and no
# monitoring module imports a network client outside Gate 94's choke point.
#
# THIS SCRIPT MAKES NO NETWORK CALL. It reads source with `ast` and reads the
# scheduler's own runtime mode. A verifier that proved "no live calls" by making
# one would be answering a different question.
#
# `urllib.parse` is not a network client and `urllib.request` is. Gate 94's
# enforcement service owns that distinction and this asks it rather than keeping
# a second list that could disagree.
#
# No secrets, tokens, cookies, state, PKCE verifier, provider subject or API
# keys. File paths, module names, counts and booleans only.
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

FAILED=""
pass() { echo "check=$1 status=PASS ${2:-}"; }
fail() { echo "check=$1 status=FAIL ${2:-}"; [ -z "$FAILED" ] && FAILED="$1"; }

echo "verify=no_live_source_calls"

MEASURED="$(.venv/bin/python - <<'PY' 2>&1
import json
import sys

sys.path.insert(0, "src")

out = {}

# -- Gate 94's choke point scan, over every service module ------------------
from nativeforge.services.hermetic_network_enforcement_service import (
    enforcement_invariant_failures,
    scan_for_network_call_sites,
)

scan = scan_for_network_call_sites()
out["chokepoint_clean"] = bool(scan.get("clean"))
out["files_scanned"] = int(scan.get("files_scanned") or 0)
out["unapproved_count"] = int(scan.get("unapproved_count") or 0)
out["finding_count"] = int(scan.get("finding_count") or 0)
out["chokepoint_invariant_failures"] = enforcement_invariant_failures(scan)
# Offenders by FILE and MODULE, so a failure names what to open.
out["offenders"] = [
    {
        "file": str(f.get("file") or f.get("path") or "?"),
        "module": str(f.get("module") or f.get("name") or "?"),
        "kind": str(f.get("kind") or "?"),
    }
    for f in (scan.get("findings") or [])
][:20]

# -- the monitoring modules, parsed --------------------------------------
from nativeforge.services.source_monitoring_readiness_service import (
    detect_network_imports,
)

imports = detect_network_imports()
out["monitoring_network_imports"] = imports["network_imports"]
out["any_monitoring_network_import"] = bool(imports["any_network_library_imported"])
out["monitoring_modules_missing"] = imports["modules_missing"]

# -- collector activation, from the scheduler's own derivation ------------
from nativeforge.services.source_scheduler_readiness_service import (
    build_scheduler_readiness,
)

scheduler = build_scheduler_readiness()
out["source_monitoring_live"] = bool(scheduler.get("source_monitoring_live"))
out["runtime_mode"] = scheduler.get("runtime_mode")
out["runtime_executes_jobs"] = bool(scheduler.get("runtime_executes_jobs"))
out["background_worker_available"] = bool(scheduler.get("background_worker_available"))
out["scheduler_components_missing"] = list(scheduler.get("components_missing") or [])

# -- nothing in the registry is approved for collection -------------------
from nativeforge.services.source_monitoring_approved_source_service import (
    evaluate_registry,
)

evaluation = evaluate_registry()
out["monitorable_count"] = int(evaluation["monitorable_count"])
out["registry_row_count"] = int(evaluation["registry_row_count"])
out["evaluation_network_calls"] = int(evaluation["network_calls"])
out["evaluation_fetch_performed"] = bool(evaluation["fetch_performed"])

print(json.dumps(out))
PY
)"

LAST_LINE="$(echo "$MEASURED" | tail -n 1)"
if ! echo "$LAST_LINE" | .venv/bin/python -c "import json,sys; json.load(sys.stdin)" 2>/dev/null; then
  fail measurement_available "scan_failed"
  echo "$MEASURED" | tail -n 6
  echo
  echo "RESULT=BLOCKED"
  echo "blocker=measurement_unavailable"
  exit 1
fi
MEASURED="$LAST_LINE"
pass measurement_available

get() { echo "$MEASURED" | .venv/bin/python -c "import json,sys;print(json.load(sys.stdin).get('$1'))"; }
getlist() {
  echo "$MEASURED" | .venv/bin/python -c \
    "import json,sys;v=json.load(sys.stdin).get('$1') or [];print(' '.join(str(x) for x in v))"
}

echo "count=files_scanned n=$(get files_scanned)"
echo "count=registry_rows n=$(get registry_row_count)"

# ------------------------------------------------- 1. the choke point is clean
[ "$(get chokepoint_clean)" = "True" ] && pass chokepoint_clean "no unapproved call sites" \
  || fail chokepoint_clean "unapproved=$(get unapproved_count)"
[ "$(get unapproved_count)" = "0" ] && pass no_unapproved_call_sites \
  || fail no_unapproved_call_sites "n=$(get unapproved_count)"

OFFENDERS="$(echo "$MEASURED" | .venv/bin/python -c \
  "import json,sys;v=json.load(sys.stdin).get('offenders') or [];print('; '.join(f\"{o['file']}:{o['module']}:{o['kind']}\" for o in v))")"
[ -n "$OFFENDERS" ] && echo "offenders=$OFFENDERS"

# --------------------------- 2. no monitoring module imports a network client
[ "$(get any_monitoring_network_import)" = "False" ] && pass no_monitoring_network_import \
  || fail no_monitoring_network_import "$(get monitoring_network_imports)"
MISSING="$(getlist monitoring_modules_missing)"
[ -z "$MISSING" ] && pass monitoring_modules_present \
  || fail monitoring_modules_present "$MISSING"

# --------------------------------------------- 3. no collector is running
[ "$(get source_monitoring_live)" = "False" ] && pass source_monitoring_live_is_false \
  || fail source_monitoring_live_is_false "$(get source_monitoring_live)"
[ "$(get runtime_executes_jobs)" = "False" ] && pass runtime_executes_no_jobs \
  "mode=$(get runtime_mode)" \
  || fail runtime_executes_no_jobs "mode=$(get runtime_mode)"
[ "$(get background_worker_available)" = "False" ] && pass no_background_worker \
  || fail no_background_worker "$(get background_worker_available)"
echo "scheduler_components_missing=$(getlist scheduler_components_missing)"

# ---------------------------- 4. nothing in the registry is cleared to collect
[ "$(get monitorable_count)" = "0" ] && pass no_source_is_cleared_for_collection \
  || fail no_source_is_cleared_for_collection "n=$(get monitorable_count)"

# ------------------------------- 5. the evaluation itself contacted nothing
[ "$(get evaluation_network_calls)" = "0" ] && pass evaluation_made_no_network_call \
  || fail evaluation_made_no_network_call "n=$(get evaluation_network_calls)"
[ "$(get evaluation_fetch_performed)" = "False" ] && pass evaluation_fetched_nothing \
  || fail evaluation_fetched_nothing "$(get evaluation_fetch_performed)"

INV="$(getlist chokepoint_invariant_failures)"
[ -z "$INV" ] && pass chokepoint_invariants "none_failed" || fail chokepoint_invariants "$INV"

echo
if [ -n "$FAILED" ]; then
  echo "RESULT=BLOCKED"
  echo "blocker=check_failed:$FAILED"
  [ -n "$OFFENDERS" ] && echo "offender=$OFFENDERS"
  exit 1
fi

echo "RESULT=PASS"
echo "no_live_source_call_path_is_active=true"
echo "chokepoint_clean=true"
echo "files_scanned=$(get files_scanned)"
echo "unapproved_call_sites=0"
echo "collectors_activated=0"
echo "source_monitoring_live=false"
echo "sources_cleared_for_collection=0"
echo "network_calls_by_this_verifier=0"
exit 0
