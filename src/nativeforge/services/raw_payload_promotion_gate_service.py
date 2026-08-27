"""Raw payload promotion gate (Gate 95E).

Decides whether a stored payload may back a collected opportunity record. It
promotes nothing on its own — it returns a decision, and the caller writes it.

## Everything starts in quarantine

``build_payload_evidence`` always constructs at ``quarantine``. Promotion is a
separate act with its own reasons, so a record cannot arrive already trusted.
That is the difference between this and the corpus flags Gates 87–89 unpicked,
where ``never_synthesized: True`` was set at construction and then checked
against itself.

## Ten requirements, all affirmative

```text
source_id present              retrieved_at present
response_body_hash present     raw_payload_ref present
secret_scan_status clean       redaction resolved
terms not TERMS_REVIEW_REQUIRED
terms not HUMAN_REVIEW_ONLY
parser_status parsed or not_started
activation permits the storage/promotion path
```

Each is checked for an affirmative value, never for the absence of a negative.
A ``secret_scan_status`` of ``pending`` fails: nobody has looked yet, and "not
yet found to be dirty" is not "clean".

## Human review is a distinct outcome

``HUMAN_REVIEW_ONLY`` terms produce ``human_review_required`` and
``promotion_status: quarantine`` — not ``rejected``. The payload is not bad;
it is not machine-promotable. Rejecting it would lose it, and losing evidence
is the thing this whole lane exists to stop.

## Activation is consulted, not assumed

The gate takes a preflight result rather than a boolean. A payload with **no**
preflight is blocked, because the absence of a check is not a check that
passed — the Gate 93D rule, applied one layer down.

A **fixture** payload does not need activation: no source was contacted, so
there is no activation to have. Requiring one would make it impossible to build
test evidence without pretending a collector is live, which is how pretending
starts.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.raw_payload_evidence_model_service import (
    EVIDENCE_CRITICAL_FIELDS,
    PARSER_SATISFYING,
    PROMOTION_PERMITTING,
    PROMOTION_STATUSES,
    REDACTION_SATISFYING,
    SECRET_SCAN_SATISFYING,
    TERMS_BLOCKING,
    TERMS_HUMAN_ONLY,
)

SCHEMA_VERSION = "nf_raw_payload_promotion_gate_v1"

# The requirement names, in reporting order.
REQUIREMENT_KEYS: tuple[str, ...] = (
    "source_id",
    "retrieved_at",
    "response_body_hash",
    "raw_payload_ref",
    "secret_scan_clean",
    "redaction_resolved",
    "terms_cleared",
    "parser_status_ok",
    "activation_permits_storage",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def evaluate_payload_promotion(
    *,
    payload: dict[str, Any],
    activation_preflight: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Can this payload be evidence? Nothing is promoted or written."""
    record = payload if isinstance(payload, dict) else {}

    satisfied: list[str] = []
    missing: list[str] = []
    blocked_reasons: list[str] = []

    def record_requirement(key: str, ok: bool, reason: str) -> None:
        if ok:
            satisfied.append(key)
        else:
            missing.append(key)
            blocked_reasons.append(reason)

    for field in EVIDENCE_CRITICAL_FIELDS:
        record_requirement(
            field,
            bool(str(record.get(field) or "").strip()),
            f"missing_evidence_field:{field}",
        )

    scan = record.get("secret_scan_status")
    record_requirement(
        "secret_scan_clean",
        scan in SECRET_SCAN_SATISFYING,
        f"secret_scan_not_clean:{scan}",
    )

    redaction = record.get("redaction_status")
    record_requirement(
        "redaction_resolved",
        redaction in REDACTION_SATISFYING,
        f"redaction_not_resolved:{redaction}",
    )

    terms = record.get("terms_status")
    human_review_required = terms in TERMS_HUMAN_ONLY
    record_requirement(
        "terms_cleared",
        terms not in TERMS_BLOCKING and not human_review_required,
        f"terms_status_blocks:{terms}",
    )

    parser = record.get("parser_status")
    record_requirement(
        "parser_status_ok",
        parser in PARSER_SATISFYING,
        f"parser_status_blocks:{parser}",
    )

    # Activation. A fixture payload never touched a source, so there is no
    # activation to require; a live payload with no preflight is blocked.
    from_fixture = bool(record.get("created_from_fixture"))
    if from_fixture:
        activation_ok = True
        activation_reason = "fixture_payload_requires_no_activation"
    elif activation_preflight is None:
        activation_ok = False
        activation_reason = "activation_preflight_absent"
    else:
        activation_ok = bool(activation_preflight.get("activation_allowed"))
        activation_reason = (
            "activation_not_allowed:"
            f"{activation_preflight.get('activation_status', 'unknown')}"
        )
    record_requirement("activation_permits_storage", activation_ok, activation_reason)

    can_promote = not missing and not human_review_required

    if can_promote:
        promotion_status = "evidence_ready"
    elif human_review_required:
        # Not rejected: the payload is fine, it just cannot be machine-promoted.
        promotion_status = "quarantine"
    else:
        promotion_status = "quarantine"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "payload_id": record.get("payload_id"),
            "source_id": record.get("source_id"),
            "can_promote": can_promote,
            "promotion_status": promotion_status,
            "evidence_ready": promotion_status in PROMOTION_PERMITTING,
            "blocked_reasons": sorted(set(blocked_reasons)),
            "human_review_required": human_review_required,
            "requirements_satisfied": sorted(satisfied),
            "requirements_missing": sorted(missing),
            "activation_preflight_present": activation_preflight is not None,
            "created_from_fixture": from_fixture,
            # This gate decides. It does not write, and it does not fetch.
            "promotion_performed": False,
            "fetch_performed": False,
            "implies_live_coverage": False,
            "fabricated": False,
        }
    )


def apply_promotion(
    *, payload: dict[str, Any], decision: dict[str, Any]
) -> dict[str, Any]:
    """Return a copy of the payload carrying the decision's promotion status."""
    updated = dict(payload)
    updated["promotion_status"] = decision.get("promotion_status", "quarantine")
    updated["blocked_reasons"] = sorted(
        set(decision.get("blocked_reasons") or [])
    )
    return _json_safe(updated)


def promotion_invariant_failures(decision: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if decision.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if decision.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")
    if decision.get("promotion_performed") is not False:
        fails.append("gate_claimed_a_promotion")
    if decision.get("fetch_performed") is not False:
        fails.append("gate_claimed_a_fetch")
    if decision.get("implies_live_coverage") is not False:
        fails.append("gate_claimed_live_coverage")

    status = decision.get("promotion_status")
    if status not in PROMOTION_STATUSES:
        fails.append("promotion_status_out_of_vocabulary")

    # evidence_ready is derived from the single permitting status.
    if decision.get("evidence_ready") != (status in PROMOTION_PERMITTING):
        fails.append("evidence_ready_disagrees_with_promotion_status")
    if decision.get("can_promote") != decision.get("evidence_ready"):
        fails.append("can_promote_disagrees_with_evidence_ready")

    if decision.get("can_promote"):
        if decision.get("requirements_missing"):
            fails.append("promotion_allowed_with_missing_requirements")
        if decision.get("blocked_reasons"):
            fails.append("promotion_allowed_with_blocked_reasons")
        if decision.get("human_review_required"):
            fails.append("promotion_allowed_while_requiring_human_review")

    if not decision.get("can_promote") and not decision.get("blocked_reasons"):
        fails.append("refusal_without_a_reason")

    # Human review parks a payload; it never discards it.
    if decision.get("human_review_required") and status == "rejected":
        fails.append("human_review_payload_rejected_rather_than_quarantined")

    # A live payload promoted with no preflight would be the Gate 93 hole.
    if (
        decision.get("can_promote")
        and not decision.get("created_from_fixture")
        and not decision.get("activation_preflight_present")
    ):
        fails.append("live_payload_promoted_without_a_preflight")

    satisfied = set(decision.get("requirements_satisfied") or [])
    missing = set(decision.get("requirements_missing") or [])
    if satisfied & missing:
        fails.append("requirement_both_satisfied_and_missing")
    if satisfied | missing != set(REQUIREMENT_KEYS):
        fails.append("requirement_dropped_from_the_checklist")

    return fails
