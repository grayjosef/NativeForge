#!/usr/bin/env bash
# Gate 83B — prove the SC customer demo payload is reproducible.
#
# Generates the payload twice into a scratch directory and compares byte for
# byte, then checks the claim boundaries that must hold for a payload carrying
# customer-facing eligibility content.
#
# Writes to a temporary path, never to the committed JSON, so running the
# verifier can never itself dirty the tree.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -P)"
cd "$ROOT"

# shellcheck disable=SC1091
source .venv/bin/activate

TMPDIR_RUN="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_RUN"' EXIT

FAIL=0

check() {
  local name="$1" ok="$2" detail="${3:-}"
  if [[ "$ok" == "1" ]]; then
    echo "check=${name} status=PASS ${detail}"
  else
    echo "check=${name} status=FAIL ${detail}"
    FAIL=1
  fi
}

echo "verify=demo_payload_determinism"

python - "$TMPDIR_RUN" <<'PY'
import hashlib
import json
import sys
import warnings
from pathlib import Path

warnings.filterwarnings("ignore")

from nativeforge.services.sc_monday_demo_bridge_service import (
    DEFAULT_FRONTEND_JSON,
    write_sc_customer_demo_bridge_json,
)

out_dir = Path(sys.argv[1])
first = out_dir / "run1.json"
second = out_dir / "run2.json"

write_sc_customer_demo_bridge_json(path=first)
write_sc_customer_demo_bridge_json(path=second)

a = first.read_bytes()
b = second.read_bytes()

results = {
    "byte_identical": a == b,
    "sha_first": hashlib.sha256(a).hexdigest(),
    "sha_second": hashlib.sha256(b).hexdigest(),
}

payload = json.loads(a)
ni = payload.get("negative_intelligence") or {}
results["negative_intelligence_present"] = bool(ni)
results["negative_intelligence_rows"] = len(ni.get("rows") or [])
results["synthetic_demo"] = ni.get("synthetic_demo")
results["live_coverage_claimed"] = ni.get("live_coverage_claimed")
results["source_monitored"] = ni.get("source_monitored")
results["freshness_claimed"] = ni.get("freshness_claimed")
results["payload_live_ingestion"] = payload.get("live_ingestion")

# The committed artifact must equal what the generator produces now, except
# for the fields derived from the current git HEAD.
#
# Those cannot match by construction: committing the payload changes HEAD,
# which changes the payload, so demanding byte equality would require a fixed
# point that does not exist. HEAD is a legitimate *input* to the generator.
#
# So the fields are excluded from the comparison and checked separately: the
# stronger property is that HEAD dependence stays confined to them, which is
# what `head_dependence_isolated` below asserts.
HEAD_DERIVED_PATHS = (
    ("operator_readiness", "contract", "current_head"),
    ("operator_readiness", "contract", "operator_readiness_id"),
)


def _blank_head_fields(doc):
    import copy

    out = copy.deepcopy(doc)
    for path in HEAD_DERIVED_PATHS:
        node = out
        for key in path[:-1]:
            node = node.get(key) if isinstance(node, dict) else None
            if node is None:
                break
        if isinstance(node, dict) and path[-1] in node:
            node[path[-1]] = "<head-derived>"
    return out


committed = Path(DEFAULT_FRONTEND_JSON)
results["committed_present"] = committed.is_file()

if committed.is_file():
    committed_doc = json.loads(committed.read_text(encoding="utf-8"))
    fresh_doc = json.loads(a.decode("utf-8"))
    results["committed_matches_regeneration"] = _blank_head_fields(
        committed_doc
    ) == _blank_head_fields(fresh_doc)

    # Every leaf that differs must be one of the declared HEAD-derived fields.
    differing = []

    def walk(x, y, path):
        if type(x) is not type(y):
            differing.append(path)
            return
        if isinstance(x, dict):
            for k in sorted(set(x) | set(y)):
                walk(x.get(k), y.get(k), path + (k,))
        elif isinstance(x, list):
            if len(x) != len(y):
                differing.append(path)
                return
            for i, (u, v) in enumerate(zip(x, y)):
                walk(u, v, path + (str(i),))
        elif x != y:
            differing.append(path)

    walk(committed_doc, fresh_doc, ())
    results["head_dependence_isolated"] = all(
        p in HEAD_DERIVED_PATHS for p in differing
    )
    results["unexpected_differing_paths"] = [
        ".".join(p) for p in differing if p not in HEAD_DERIVED_PATHS
    ][:5]
else:
    results["committed_matches_regeneration"] = False
    results["head_dependence_isolated"] = False
    results["unexpected_differing_paths"] = []

(out_dir / "results.json").write_text(json.dumps(results), encoding="utf-8")
PY

RESULTS="$TMPDIR_RUN/results.json"

get() { python -c "import json,sys;print(json.load(open(sys.argv[1])).get(sys.argv[2]))" "$RESULTS" "$1"; }

BYTE_IDENTICAL="$(get byte_identical)"
SHA1="$(get sha_first)"
SHA2="$(get sha_second)"
NI_PRESENT="$(get negative_intelligence_present)"
NI_ROWS="$(get negative_intelligence_rows)"
SYNTHETIC="$(get synthetic_demo)"
LIVE_COVERAGE="$(get live_coverage_claimed)"
MONITORED="$(get source_monitored)"
FRESHNESS="$(get freshness_claimed)"
LIVE_INGEST="$(get payload_live_ingestion)"
COMMITTED_PRESENT="$(get committed_present)"
COMMITTED_MATCHES="$(get committed_matches_regeneration)"

# Two generations from the same HEAD must be byte-identical.
[[ "$BYTE_IDENTICAL" == "True" ]] && check payload_byte_identical 1 "sha=${SHA1:0:16}" \
  || check payload_byte_identical 0 "sha1=${SHA1:0:16} sha2=${SHA2:0:16}"

# The Gate 83 surface must not have been dropped by a regeneration.
[[ "$NI_PRESENT" == "True" ]] && check negative_intelligence_present 1 \
  || check negative_intelligence_present 0 "missing negative_intelligence surface"

[[ "$NI_ROWS" -ge 2 ]] 2>/dev/null && check negative_intelligence_rows 1 "rows=$NI_ROWS" \
  || check negative_intelligence_rows 0 "rows=$NI_ROWS expected>=2"

# Claim boundaries.
[[ "$SYNTHETIC" == "True" ]] && check synthetic_demo_true 1 \
  || check synthetic_demo_true 0 "synthetic_demo=$SYNTHETIC"

[[ "$LIVE_COVERAGE" == "False" ]] && check no_live_coverage_claimed 1 \
  || check no_live_coverage_claimed 0 "live_coverage_claimed=$LIVE_COVERAGE"

[[ "$MONITORED" == "False" ]] && check no_source_monitoring_claimed 1 \
  || check no_source_monitoring_claimed 0 "source_monitored=$MONITORED"

[[ "$FRESHNESS" == "False" ]] && check no_freshness_claimed 1 \
  || check no_freshness_claimed 0 "freshness_claimed=$FRESHNESS"

[[ "$LIVE_INGEST" == "False" ]] && check payload_live_ingestion_false 1 \
  || check payload_live_ingestion_false 0 "live_ingestion=$LIVE_INGEST"

# The committed artifact must be the generator's current output.
[[ "$COMMITTED_PRESENT" == "True" ]] && check committed_payload_present 1 \
  || check committed_payload_present 0

[[ "$COMMITTED_MATCHES" == "True" ]] && check committed_matches_regeneration 1 "head-derived fields excluded" \
  || check committed_matches_regeneration 0 "regenerate frontend/src/demo/sc_customer_demo.json"

HEAD_ISOLATED="$(get head_dependence_isolated)"
UNEXPECTED="$(get unexpected_differing_paths)"
[[ "$HEAD_ISOLATED" == "True" ]] && check head_dependence_isolated 1 \
  || check head_dependence_isolated 0 "unexpected head-dependent paths: $UNEXPECTED"

if [[ "$FAIL" -eq 0 ]]; then
  echo "RESULT=PASS"
else
  echo "RESULT=FAIL"
fi
exit "$FAIL"
