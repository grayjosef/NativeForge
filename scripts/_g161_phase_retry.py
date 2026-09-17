"""Gate 161 verifier phase: what a transport outcome means for a retry.

Writes nothing. Every key is a decision, and the last one checks that the
invariant checker CATCHES a doctored decision - a checker that cannot fail has
not verified the checks that passed.
"""

from __future__ import annotations

import json
import sys
from datetime import UTC, datetime

sys.path.insert(0, "src")

from nativeforge.services.source_collection_execution_retry_service import (  # noqa: E402,E501
    MAX_RETRY_AFTER_SECONDS,
    evaluate_execution_retry,
    execution_retry_invariant_failures,
)

NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
TRANSIENT = "transient_worker_failure"
PERMANENT = "permanent_worker_failure"

out: dict[str, object] = {}
detail: list[str] = []


def decide(**kw: object) -> dict:
    result = evaluate_execution_retry(now=NOW, attempt_count=0, **kw)
    fails = execution_retry_invariant_failures(result)
    if fails:
        detail.append(f"{kw}:{fails}")
    return result


timeout = decide(outcome="timeout")
out["timeout_is_transient"] = bool(
    timeout["failure_class"] == TRANSIENT and timeout["should_retry"]
)

rate = decide(
    outcome="response_received",
    http_status=429,
    response_headers={"Retry-After": "120"},
)
out["rate_limit_is_transient"] = bool(
    rate["failure_class"] == TRANSIENT and rate["should_retry"]
)
out["retry_after_is_honoured"] = bool(
    rate["retry_after_was_honoured"]
    and rate["backoff_seconds"] == 120
    and rate["schedule_source"] == "the_sources_retry_after"
    # It WON over the computed schedule, which is the point.
    and rate["computed_backoff_seconds"] != 120
)

capped = decide(
    outcome="response_received",
    http_status=429,
    response_headers={"Retry-After": "999999"},
)
out["retry_after_is_capped"] = bool(
    capped["backoff_seconds"] == MAX_RETRY_AFTER_SECONDS
    # And SAYS it capped, rather than quietly shortening the wait.
    and capped["retry_after_notes"]
)

server = decide(outcome="response_received", http_status=503)
out["server_error_is_transient"] = bool(
    server["failure_class"] == TRANSIENT and server["should_retry"]
)

missing = decide(outcome="response_received", http_status=404)
out["not_found_is_permanent"] = bool(
    missing["failure_class"] == PERMANENT and not missing["should_retry"]
)

permanent_with_header = decide(
    outcome="response_received",
    http_status=404,
    response_headers={"Retry-After": "60"},
)
out["retry_after_is_not_honoured_for_a_permanent_failure"] = bool(
    not permanent_with_header["retry_after_was_honoured"]
    and not permanent_with_header["should_retry"]
)

malformed = decide(
    outcome="response_received_malformed_body", http_status=200
)
out["malformed_is_not_retried"] = bool(not malformed["should_retry"])

refused = decide(outcome="refused_before_dispatch")
out["refusal_is_not_retried"] = bool(
    not refused["should_retry"] and refused["failure_class"] == "none"
)

human = all(
    not decide(outcome="timeout", refusal_reasons=[reason])["should_retry"]
    for reason in (
        "refused_by_activation",
        "terms_blocked",
        "human_review_blocked",
    )
)
out["human_blockers_are_not_retried"] = bool(human)

# The checker, on a decision that retries something a timer cannot fix.
liar = dict(missing, should_retry=True, next_retry_at="2026-09-16T12:01:00+00:00")
caught = execution_retry_invariant_failures(liar)
out["the_checker_catches_a_retried_permanent_failure"] = bool(
    f"retried_a_non_transient_class:{PERMANENT}" in caught
)

out["detail"] = "; ".join(detail) if detail else None
print(json.dumps(out, sort_keys=True))
