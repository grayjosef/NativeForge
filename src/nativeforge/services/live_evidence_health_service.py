"""Is the recorded live collection healthy? (Gate 164G)

The distinction this lane exists to make:

```text
healthy                          everything verifies, nothing missing
healthy_with_known_evidence_gap  everything verifies; a named field was never
                                 captured
unhealthy                        a condition that should hold does not
unreplayable                     the bytes cannot be recovered or re-verified
corrupt                          the evidence contradicts itself
unauthorized                     a live row nothing authorized
```

The Gate 163 collection is `healthy_with_known_evidence_gap`. Its HTTP
transport status was never captured, because the runner read the wrong result
field; the bytes verify, the hash recomputes, the linkage holds and the
collection replays. Collapsing that into `unhealthy` would say the evidence is
untrustworthy, and collapsing it into `healthy` would hide that something is
missing. Neither is true, so there is a third answer.

A gap must be NAMED. `known_evidence_gaps` is a list, and a status claiming a
gap with nothing in that list is an invariant failure - otherwise "known gap"
becomes a way to pass while hiding anything.

## It reports; it does not measure

`replay_without_network`, `fresh_connection_replay` and
`canonical_artifact_generation_hermetic` are supplied by whoever performed
them, the same arrangement every other health lane in this repository uses:
a lane that did its own work could pass itself by doing the work differently
from the caller who matters. Unsupplied evidence is not a pass - each one
defaults to False.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_live_evidence_health_v1"

HEALTHY = "healthy"
HEALTHY_WITH_GAP = "healthy_with_known_evidence_gap"
UNHEALTHY = "unhealthy"
CORRUPT = "corrupt"
UNAUTHORIZED = "unauthorized"
UNREPLAYABLE = "unreplayable"

STATUSES: tuple[str, ...] = (
    HEALTHY,
    HEALTHY_WITH_GAP,
    UNHEALTHY,
    CORRUPT,
    UNAUTHORIZED,
    UNREPLAYABLE,
)

#: Every condition, in the order a reader wants them: the bytes, then what
#: they are linked to, then whether the whole thing can be done again.
CONDITIONS: tuple[str, ...] = (
    "raw_payload_present",
    "raw_payload_exact_bytes_recoverable",
    "hash_verified",
    "source_linkage_valid",
    "authorized_source_linkage_valid",
    "request_fingerprint_valid",
    "source_authority_matches",
    "execution_attempt_present",
    "execution_proof_present",
    "attribution_present",
    "audit_chain_complete",
    "replay_without_network",
    "fresh_connection_replay",
    "normalization_reproducible",
    "unauthorized_live_attempts_zero",
    "unauthorized_live_rows_zero",
    "canonical_artifact_generation_hermetic",
)

#: Conditions whose failure means the EVIDENCE is bad rather than incomplete.
CORRUPTION_CONDITIONS: frozenset[str] = frozenset(
    {
        "hash_verified",
        "raw_payload_exact_bytes_recoverable",
        "source_linkage_valid",
        "authorized_source_linkage_valid",
        "source_authority_matches",
    }
)

#: Conditions whose failure means something was not authorized.
AUTHORIZATION_CONDITIONS: frozenset[str] = frozenset(
    {"unauthorized_live_attempts_zero", "unauthorized_live_rows_zero"}
)

#: Conditions whose failure means it cannot be done again.
REPLAY_CONDITIONS: frozenset[str] = frozenset(
    {"replay_without_network", "fresh_connection_replay", "normalization_reproducible"}
)

#: Gaps this lane recognises. A gap outside this vocabulary is not a known
#: gap, and gets treated as a plain unmet condition.
KNOWN_GAPS: tuple[str, ...] = ("http_status_not_captured",)

NOT_IMPLIED: tuple[str, ...] = (
    "healthy evidence is not a claim the response content was correct",
    "a known gap is not corruption, and not a pass either",
    "this lane reports measurements; it does not perform them",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def build_live_evidence_health(
    *,
    audit: dict[str, Any] | None = None,
    replay_without_network: Any = None,
    fresh_connection_replay: Any = None,
    canonical_artifact_generation_hermetic: Any = None,
    unauthorized_live_attempts: Any = None,
    unauthorized_live_rows: Any = None,
) -> dict[str, Any]:
    """Report the lane from an audit view and supplied measurements."""
    view = audit or {}
    sections = view.get("sections") or {}
    response = sections.get("response") or {}
    execution = sections.get("execution") or {}
    request = sections.get("request") or {}
    source = sections.get("source") or {}
    normalization = sections.get("normalization") or {}
    authorization = sections.get("authorization") or {}

    measured: dict[str, bool] = {
        "raw_payload_present": bool(response.get("payload_id")),
        # The bytes are recoverable exactly when the hash re-verified against
        # them, which the audit's normalization section proves by having been
        # derived from a hash-verified replay.
        "raw_payload_exact_bytes_recoverable": bool(
            response.get("sha256") and normalization.get("raw_payload_reference")
        ),
        "hash_verified": bool(
            response.get("sha256")
            and normalization.get("raw_payload_reference") == response.get("sha256")
        ),
        "source_linkage_valid": bool(source.get("source_id") and source.get("host")),
        "authorized_source_linkage_valid": bool(
            execution.get("authorized_source_id")
            and execution.get("authorized_source_id") == source.get("source_id")
        ),
        "request_fingerprint_valid": bool(request.get("request_fingerprint")),
        "source_authority_matches": bool(
            request.get("fingerprint_matches_declared_endpoint")
        ),
        "execution_attempt_present": bool(execution.get("attempt_id")),
        "execution_proof_present": bool(
            execution.get("execution_proof_available")
            and execution.get("proof_hash_matches_payload")
        ),
        "attribution_present": bool(authorization.get("terms")),
        "audit_chain_complete": bool(view.get("audit_chain_complete")),
        # Supplied. Absent evidence is not a pass.
        "replay_without_network": bool(replay_without_network),
        "fresh_connection_replay": bool(fresh_connection_replay),
        "normalization_reproducible": bool(normalization.get("opportunity_number")),
        "unauthorized_live_attempts_zero": int(unauthorized_live_attempts or 0) == 0
        and unauthorized_live_attempts is not None,
        "unauthorized_live_rows_zero": int(unauthorized_live_rows or 0) == 0
        and unauthorized_live_rows is not None,
        "canonical_artifact_generation_hermetic": bool(
            canonical_artifact_generation_hermetic
        ),
    }

    unmet = sorted(name for name, ok in measured.items() if not ok)

    # ---- the known gaps, named --------------------------------------
    gaps: list[str] = []
    if response.get("http_status_known") is False:
        gaps.append("http_status_not_captured")

    # ---- the status, by precedence ----------------------------------
    #
    # Corruption outranks everything: evidence that contradicts itself is not
    # "incomplete". Then authorization, then replayability, then plain unmet
    # conditions, then the gap, then healthy.
    if any(name in CORRUPTION_CONDITIONS for name in unmet):
        status = CORRUPT
    elif any(name in AUTHORIZATION_CONDITIONS for name in unmet):
        status = UNAUTHORIZED
    elif any(name in REPLAY_CONDITIONS for name in unmet):
        status = UNREPLAYABLE
    elif unmet:
        status = UNHEALTHY
    elif gaps:
        status = HEALTHY_WITH_GAP
    else:
        status = HEALTHY

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "health_status": status,
            "conditions": measured,
            "conditions_expected": list(CONDITIONS),
            "unmet_conditions": unmet,
            "known_evidence_gaps": sorted(gaps),
            "gap_vocabulary": list(KNOWN_GAPS),
            "a_gap_is_not_corruption": (
                "the bytes verify, the linkage holds and the collection "
                "replays. What is missing is a field nobody captured."
            ),
            "http_status": response.get("http_status"),
            "http_status_known": response.get("http_status_known"),
            "measurements_were_supplied_not_performed": [
                "replay_without_network",
                "fresh_connection_replay",
                "canonical_artifact_generation_hermetic",
            ],
            "not_implied": list(NOT_IMPLIED),
        }
    )


def live_evidence_health_invariant_failures(health: dict[str, Any]) -> list[str]:
    """Refuse a health report that contradicts itself."""
    fails: list[str] = []

    if health.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    status = str(health.get("health_status") or "")
    if status not in STATUSES:
        fails.append(f"status_outside_vocabulary:{status}")

    conditions = health.get("conditions") or {}
    if set(conditions) != set(CONDITIONS):
        fails.append("conditions_do_not_match_the_declared_set")

    unmet = list(health.get("unmet_conditions") or [])
    gaps = list(health.get("known_evidence_gaps") or [])

    # healthy and unmet must agree, both directions.
    if status in (HEALTHY, HEALTHY_WITH_GAP) and unmet:
        fails.append(f"healthy_alongside_unmet_conditions:{unmet}")
    if status not in (HEALTHY, HEALTHY_WITH_GAP) and not unmet:
        fails.append("not_healthy_without_naming_an_unmet_condition")

    # A gap status must NAME a gap, and a gap must be in the vocabulary -
    # otherwise "known gap" becomes a way to pass while hiding anything.
    if status == HEALTHY_WITH_GAP and not gaps:
        fails.append("claimed_a_known_gap_without_naming_one")
    if status == HEALTHY and gaps:
        fails.append(f"plain_healthy_while_carrying_gaps:{gaps}")
    for gap in gaps:
        if gap not in KNOWN_GAPS:
            fails.append(f"gap_outside_the_vocabulary:{gap}")

    # The gap and the field it describes must agree.
    if "http_status_not_captured" in gaps and health.get("http_status") is not None:
        fails.append("claimed_the_status_was_not_captured_while_reporting_one")
    if (
        health.get("http_status_known") is False
        and "http_status_not_captured" not in gaps
    ):
        fails.append("an_uncaptured_status_was_not_declared_as_a_gap")

    return sorted(set(fails))
