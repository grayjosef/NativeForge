"""Gate 172J/K/L: the source changed shape, and nobody told us.

The failure mode this exists for is quiet. A publisher renames a field, adds a
wrapper object, or changes a CSS class. The request still returns 200, the
bytes are still valid, and the adapter now reads zero records out of a
perfectly healthy response. Transport says fine. Availability says fine. The
intelligence is gone.

## Drift is classified, never auto-repaired

```text
BENIGN_DRIFT      cosmetic; nothing downstream depends on it
COMPATIBLE_DRIFT  additive; the adapter still reads everything it needs
BREAKING_DRIFT    a field the adapter depends on is gone or retyped
UNKNOWN_DRIFT     changed in a way no rule covers
```

BREAKING and UNKNOWN produce REVIEW_REQUIRED with the evidence attached. This
module never rewrites an adapter: a system that silently adapts to a source's
new shape is a system that silently adopts whatever the source starts saying.

## Volume is compared to the source's OWN history

A fleet-wide "fewer than 10 records is suspicious" threshold is wrong in both
directions at once - it screams at a source that publishes 3 and sleeps
through a source that dropped from 40,000 to 12. Baselines are per source, and
the first observation is never an anomaly, because one point is not a history.
"""

from __future__ import annotations

import json
import statistics
from typing import Any

SCHEMA_VERSION = "nf_source_fleet_drift_v1"

# ---- 172J: drift classes -----------------------------------------

BENIGN_DRIFT = "BENIGN_DRIFT"
COMPATIBLE_DRIFT = "COMPATIBLE_DRIFT"
BREAKING_DRIFT = "BREAKING_DRIFT"
UNKNOWN_DRIFT = "UNKNOWN_DRIFT"
NO_DRIFT = "NO_DRIFT"

DRIFT_CLASSES: tuple[str, ...] = (
    NO_DRIFT,
    BENIGN_DRIFT,
    COMPATIBLE_DRIFT,
    BREAKING_DRIFT,
    UNKNOWN_DRIFT,
)

#: Which classes stop a source until a human looks. Additive change is not a
#: reason to stop collecting; a missing required field is.
REVIEW_REQUIRED_CLASSES: frozenset[str] = frozenset(
    {BREAKING_DRIFT, UNKNOWN_DRIFT}
)

DRIFT_SIGNALS: tuple[str, ...] = (
    "content_type_changed",
    "root_envelope_changed",
    "required_field_missing",
    "field_type_changed",
    "pagination_token_missing",
    "unknown_field_appeared",
    "record_count_collapsed",
    "selector_stopped_matching",
    "document_count_zero",
    "parse_error_rate_increased",
)

#: Signal -> class. Written as a table so the severity of each signal is a
#: reviewable decision rather than the shape of an if-chain.
SIGNAL_CLASS: dict[str, str] = {
    "content_type_changed": BREAKING_DRIFT,
    "root_envelope_changed": BREAKING_DRIFT,
    "required_field_missing": BREAKING_DRIFT,
    "field_type_changed": BREAKING_DRIFT,
    "pagination_token_missing": COMPATIBLE_DRIFT,
    "unknown_field_appeared": COMPATIBLE_DRIFT,
    "record_count_collapsed": BREAKING_DRIFT,
    "selector_stopped_matching": BREAKING_DRIFT,
    "document_count_zero": BENIGN_DRIFT,
    "parse_error_rate_increased": BREAKING_DRIFT,
}

# ---- 172L: volume states -----------------------------------------

NORMAL = "NORMAL"
LOW = "LOW"
HIGH = "HIGH"
INSUFFICIENT_HISTORY = "INSUFFICIENT_HISTORY"

VOLUME_STATES: tuple[str, ...] = (NORMAL, LOW, HIGH, INSUFFICIENT_HISTORY)

#: Below this many prior observations there is no baseline worth comparing
#: to. Three is the smallest number for which a median means anything.
MINIMUM_HISTORY = 3

#: How far from the source's own median counts as anomalous. Deliberately
#: wide: a fleet that cries wolf at every 30% swing gets ignored, and an
#: ignored alert is worse than no alert.
LOW_RATIO = 0.25
HIGH_RATIO = 4.0


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


# ---- 172K: the adapter's own declared contract --------------------

CONTRACT_FIELDS: tuple[str, ...] = (
    "expected_content_types",
    "required_record_fields",
    "optional_record_fields",
    "record_identity_fields",
    "pagination_shape",
    "minimum_parse_success_ratio",
)


def adapter_contract(module: Any) -> dict[str, Any]:
    """What an adapter promises about the shape it reads.

    Derived from the adapter's own descriptor where possible, so a new adapter
    gets a contract without declaring one twice. An adapter that declares
    nothing gets an explicitly EMPTY contract rather than a permissive one -
    "no contract" must not read as "everything is fine".
    """
    descriptor = None
    if hasattr(module, "build_descriptor"):
        try:
            descriptor = module.build_descriptor()
        except Exception:  # noqa: BLE001
            descriptor = None

    declared = getattr(module, "ADAPTER_CONTRACT", None)
    contract = dict(declared) if isinstance(declared, dict) else {}

    if descriptor is not None:
        contract.setdefault(
            "expected_content_types", list(descriptor.expected_media_types)
        )
        contract.setdefault("pagination_shape", descriptor.pagination_model)
    contract.setdefault("required_record_fields", ["source_record_id"])
    contract.setdefault("optional_record_fields", [])
    contract.setdefault("record_identity_fields", ["source_record_id"])
    contract.setdefault("minimum_parse_success_ratio", 0.5)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "adapter_key": str(getattr(module, "ADAPTER_KEY", "") or "") or None,
            **{field: contract.get(field) for field in CONTRACT_FIELDS},
            "declared_explicitly": isinstance(declared, dict),
        }
    )


def detect_drift(
    *,
    contract: dict[str, Any],
    observed_content_type: Any = None,
    observed_fields: list[str] | None = None,
    observed_field_types: dict[str, str] | None = None,
    baseline_field_types: dict[str, str] | None = None,
    records_read: Any = None,
    parse_attempts: Any = None,
    parse_failures: Any = None,
    pagination_token_present: Any = None,
    documents_found: Any = None,
    previous_record_counts: list[int] | None = None,
) -> dict[str, Any]:
    """Every signal that fired, and the worst class among them."""
    signals: list[dict[str, Any]] = []

    def fire(name: str, evidence: str) -> None:
        signals.append(
            {
                "signal": name,
                "class": SIGNAL_CLASS.get(name, UNKNOWN_DRIFT),
                "evidence": evidence,
            }
        )

    expected_types = [
        str(t).lower() for t in (contract.get("expected_content_types") or [])
    ]
    if observed_content_type and expected_types:
        observed = str(observed_content_type).split(";")[0].strip().lower()
        if observed not in expected_types:
            fire(
                "content_type_changed",
                f"expected one of {expected_types}, got {observed}",
            )

    observed_names = set(observed_fields or [])
    required = set(contract.get("required_record_fields") or [])
    if observed_fields is not None:
        missing = sorted(required - observed_names)
        if missing:
            fire("required_field_missing", f"missing {missing}")
        known = required | set(contract.get("optional_record_fields") or [])
        # Only meaningful when the adapter actually declared its optional
        # fields; otherwise every field looks new.
        if known and len(known) > len(required):
            appeared = sorted(observed_names - known)
            if appeared:
                fire("unknown_field_appeared", f"new fields {appeared}")

    if observed_field_types and baseline_field_types:
        retyped = sorted(
            name
            for name, kind in observed_field_types.items()
            if name in baseline_field_types and baseline_field_types[name] != kind
        )
        if retyped:
            fire("field_type_changed", f"retyped {retyped}")

    if (
        contract.get("pagination_shape")
        and str(contract["pagination_shape"]) != "single_document"
        and pagination_token_present is False
    ):
        fire("pagination_token_missing", "declared paginated, no token present")

    if parse_attempts:
        failures = int(parse_failures or 0)
        ratio = 1.0 - (failures / max(int(parse_attempts), 1))
        minimum = float(contract.get("minimum_parse_success_ratio") or 0.5)
        if ratio < minimum:
            fire(
                "parse_error_rate_increased",
                f"parse success {ratio:.2f} below {minimum:.2f}",
            )

    if documents_found is not None and int(documents_found) == 0:
        fire("document_count_zero", "no documents extracted")

    volume = assess_volume(
        records_read=records_read, previous_record_counts=previous_record_counts
    )
    if volume["state"] == LOW and volume["collapsed"]:
        fire(
            "record_count_collapsed",
            f"{records_read} against a median of {volume['baseline_median']}",
        )
    if (
        records_read is not None
        and int(records_read) == 0
        and volume["state"] != INSUFFICIENT_HISTORY
    ):
        fire("selector_stopped_matching", "zero records from a source with history")

    classes = [str(s["class"]) for s in signals]
    if not classes:
        worst = NO_DRIFT
    else:
        severity = (
            BREAKING_DRIFT,
            UNKNOWN_DRIFT,
            COMPATIBLE_DRIFT,
            BENIGN_DRIFT,
        )
        for candidate in severity:
            if candidate in classes:
                worst = candidate
                break
        else:
            worst = UNKNOWN_DRIFT

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "drift_class": worst,
            "signals": signals,
            "signal_names": sorted({str(s["signal"]) for s in signals}),
            "requires_human_review": worst in REVIEW_REQUIRED_CLASSES,
            "adapter_was_not_rewritten": True,
            "volume": volume,
        }
    )


def assess_volume(
    *, records_read: Any = None, previous_record_counts: list[int] | None = None
) -> dict[str, Any]:
    """Against this source's own history. The first run is never anomalous."""
    history = [int(n) for n in (previous_record_counts or []) if n is not None]
    current = None if records_read is None else int(records_read)

    if current is None or len(history) < MINIMUM_HISTORY:
        return _json_safe(
            {
                "state": INSUFFICIENT_HISTORY,
                "current": current,
                "baseline_median": None,
                "observations": len(history),
                "minimum_history": MINIMUM_HISTORY,
                "collapsed": False,
                "why": "a single observation is not a baseline",
            }
        )

    median = statistics.median(history)
    if median <= 0:
        state = NORMAL if current == 0 else HIGH
        return _json_safe(
            {
                "state": state,
                "current": current,
                "baseline_median": median,
                "observations": len(history),
                "collapsed": False,
                "why": "baseline is zero",
            }
        )

    ratio = current / median
    if ratio <= LOW_RATIO:
        state = LOW
    elif ratio >= HIGH_RATIO:
        state = HIGH
    else:
        state = NORMAL

    return _json_safe(
        {
            "state": state,
            "current": current,
            "baseline_median": median,
            "ratio": round(ratio, 3),
            "observations": len(history),
            "low_ratio": LOW_RATIO,
            "high_ratio": HIGH_RATIO,
            "collapsed": state == LOW,
        }
    )


def drift_invariant_failures(drift: dict[str, Any]) -> list[str]:
    failures: list[str] = []

    drift_class = str(drift.get("drift_class") or "")
    if drift_class not in DRIFT_CLASSES:
        failures.append(f"drift_class_outside_vocabulary:{drift_class or 'missing'}")

    for signal in drift.get("signals") or []:
        name = str(signal.get("signal"))
        if name not in DRIFT_SIGNALS:
            failures.append(f"signal_outside_vocabulary:{name}")
        if not signal.get("evidence"):
            failures.append(f"signal_without_evidence:{name}")

    if drift_class in REVIEW_REQUIRED_CLASSES and not drift.get(
        "requires_human_review"
    ):
        failures.append("breaking_drift_without_requiring_review")
    if drift_class == NO_DRIFT and drift.get("signals"):
        failures.append("no_drift_reported_while_signals_fired")
    if not drift.get("adapter_was_not_rewritten"):
        failures.append("an_adapter_was_rewritten_automatically")

    volume = dict(drift.get("volume") or {})
    if volume.get("state") not in VOLUME_STATES:
        failures.append("volume_state_outside_vocabulary")
    if (
        volume.get("state") == INSUFFICIENT_HISTORY
        and "record_count_collapsed" in (drift.get("signal_names") or [])
    ):
        failures.append("a_first_observation_was_called_anomalous")

    return sorted(set(failures))


def describe_drift_model() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "drift_classes": list(DRIFT_CLASSES),
            "drift_signals": list(DRIFT_SIGNALS),
            "signal_class": dict(SIGNAL_CLASS),
            "review_required_classes": sorted(REVIEW_REQUIRED_CLASSES),
            "volume_states": list(VOLUME_STATES),
            "minimum_history": MINIMUM_HISTORY,
            "contract_fields": list(CONTRACT_FIELDS),
            "every_signal_has_a_class": all(
                s in SIGNAL_CLASS for s in DRIFT_SIGNALS
            ),
            "baselines_are_per_source": True,
            "adapters_are_never_auto_rewritten": True,
        }
    )
