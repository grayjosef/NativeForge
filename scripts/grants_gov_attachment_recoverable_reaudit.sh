#!/usr/bin/env bash
# One-command Path B gate: attachment-only tribal-relevant recoverable count vs threshold.
set -euo pipefail
cd "$(dirname "$0")/.."

export NF_APP_ENV=staging

uv run python << 'PY'
from nativeforge.services.grants_gov_attachment_recoverable_reaudit_service import (
    ATTACHMENT_ONLY_THRESHOLD,
    run_attachment_recoverable_reaudit,
)

report = run_attachment_recoverable_reaudit(allow_live_fetch=True)
print("attachment_only_recoverable_count", report["attachment_only_recoverable_count"])
print("threshold", ATTACHMENT_ONLY_THRESHOLD)
print("path_b_approved", report["path_b_approved"])
print("candidates", report["candidates"])
print("skipped_no_gg_id", report["skipped_no_gg_id"])
if report["path_b_approved"]:
    print("PATH B: threshold met — attachment fetch/parse block may proceed.")
else:
    print("PATH B: DEFERRED — below threshold; attachment PDF/OCR block remains gated.")
PY
