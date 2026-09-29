#!/usr/bin/env bash
# Gate 180 — controlled customer launch reassessment (repeatable verifier).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
PROOF="$(python scripts/_g180_phase_proof.py)"
echo "$PROOF" | python -c "import json,sys; d=json.load(sys.stdin); assert d.get('gate180_ready'), d; print('RESULT=PASS')"
echo "controlled_launch_verifier_ready=true"
