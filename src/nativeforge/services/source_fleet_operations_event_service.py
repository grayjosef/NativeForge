"""Gate 172Y/Z: transitions, not polling noise - and what a human should do.

A health sweep runs often. If it emits an event every time it finds a source
still stale, the stream becomes a log, and an operator who cannot see the
signal stops looking. So an event is written when a source CHANGES state, and
the same transition observed again advances a counter instead of adding a row.

```text
event_id = sha256(source_id | event_type | from_state | to_state)
```

Derived, so idempotence is a primary-key collision rather than a comparison
somebody has to remember to write. `first_detected_at` is never rewritten:
"this source went stale on the 3rd" survives every later sweep that agrees.

## Alerts are readiness, not delivery

172Z is explicit. This produces the record an operator would act on -
severity, condition, evidence, recommended action - and sends nothing. There
is no email, no webhook, no queue. `notified_at` exists on the row so a later
gate cannot quietly claim delivery happened.

## Severity is a table, not a judgement

No model decides how bad something is. Each condition maps to one severity
with a reason, and the reason is the thing worth arguing with.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from typing import Any

import sqlalchemy as sa

SCHEMA_VERSION = "nf_source_fleet_operations_event_v1"

EVENTS_TABLE = "nf_source_operations_events"
ALERTS_TABLE = "nf_source_operator_alerts"

# ---- 172Y: the transitions worth recording -----------------------

EVENT_TYPES: tuple[str, ...] = (
    "SOURCE_BECAME_STALE",
    "SOURCE_RECOVERED",
    "SOURCE_BECAME_FAILING",
    "RATE_LIMIT_DETECTED",
    "CIRCUIT_OPENED",
    "CIRCUIT_HALF_OPEN",
    "CIRCUIT_CLOSED",
    "SCHEMA_DRIFT_DETECTED",
    "PARSER_DRIFT_DETECTED",
    "AUTHORIZATION_REVOKED",
    "AUTHORIZATION_RESTORED",
    "SOURCE_DISABLED",
    "SOURCE_ENABLED",
    "BACKLOG_THRESHOLD_CROSSED",
    "BACKLOG_RECOVERED",
    "WORKER_UNAVAILABLE",
    "WORKER_RECOVERED",
)

INFO = "INFO"
WARNING = "WARNING"
CRITICAL = "CRITICAL"
SEVERITIES: tuple[str, ...] = (INFO, WARNING, CRITICAL)

#: Which operational state transition produces which event. Keyed by the
#: DESTINATION state, because that is what changed.
STATE_TO_EVENT: dict[str, str] = {
    "STALE": "SOURCE_BECAME_STALE",
    "FAILING": "SOURCE_BECAME_FAILING",
    "RATE_LIMITED": "RATE_LIMIT_DETECTED",
    "AUTHORIZATION_REQUIRED": "AUTHORIZATION_REVOKED",
    "DISABLED": "SOURCE_DISABLED",
    "REVIEW_REQUIRED": "SCHEMA_DRIFT_DETECTED",
    "HEALTHY": "SOURCE_RECOVERED",
}

#: Severity per event. A table, with the reasoning attached, so raising or
#: lowering one is a reviewable change rather than a tweak.
EVENT_SEVERITY: dict[str, tuple[str, str]] = {
    "SOURCE_BECAME_STALE": (WARNING, "collection is late but nothing is broken"),
    "SOURCE_RECOVERED": (INFO, "good news needs no escalation"),
    "SOURCE_BECAME_FAILING": (CRITICAL, "repeated failure means no intelligence"),
    "RATE_LIMIT_DETECTED": (WARNING, "the source is asking us to slow down"),
    "CIRCUIT_OPENED": (CRITICAL, "collection has stopped for this source"),
    "CIRCUIT_HALF_OPEN": (INFO, "a probe is scheduled"),
    "CIRCUIT_CLOSED": (INFO, "collection resumed"),
    "SCHEMA_DRIFT_DETECTED": (CRITICAL, "the adapter is reading a shape that moved"),
    "PARSER_DRIFT_DETECTED": (CRITICAL, "records are being lost silently"),
    "AUTHORIZATION_REVOKED": (
        CRITICAL,
        "collection must stop until permission returns",
    ),
    "AUTHORIZATION_RESTORED": (INFO, "permission is back"),
    "SOURCE_DISABLED": (INFO, "an operator did this deliberately"),
    "SOURCE_ENABLED": (INFO, "an operator did this deliberately"),
    "BACKLOG_THRESHOLD_CROSSED": (WARNING, "work is arriving faster than it clears"),
    "BACKLOG_RECOVERED": (INFO, "the queue drained"),
    "WORKER_UNAVAILABLE": (CRITICAL, "nothing will run until a worker returns"),
    "WORKER_RECOVERED": (INFO, "workers are back"),
}

# ---- 172Z: the alert contract -------------------------------------

ALERT_CONDITIONS: tuple[str, ...] = (
    "authorization_revoked",
    "breaking_schema_drift",
    "sustained_collection_failure",
    "circuit_open",
    "freshness_sla_breached",
    "repeated_rate_limit",
    "backlog_critical",
    "parser_degraded",
    "source_recovered",
    "source_disabled",
)

#: Condition -> (severity, what an operator should actually DO). The action
#: is required by the schema: an alert that does not say what to do is a
#: notification, and notifications get muted.
ALERT_CONTRACT: dict[str, tuple[str, str]] = {
    "authorization_revoked": (
        CRITICAL,
        "restore or re-record the live-fetch decision; collection is refused "
        "before transport until then",
    ),
    "breaking_schema_drift": (
        CRITICAL,
        "compare the stored payload against the adapter contract and correct "
        "the adapter; do not let it auto-adapt",
    ),
    "sustained_collection_failure": (
        CRITICAL,
        "check the failure type: transport failures may recover, policy "
        "refusals will not",
    ),
    "circuit_open": (
        CRITICAL,
        "the breaker stopped useless work; confirm the source is reachable "
        "before forcing it closed",
    ),
    "freshness_sla_breached": (
        WARNING,
        "confirm the cadence is still right for this source before treating "
        "it as broken",
    ),
    "repeated_rate_limit": (
        WARNING,
        "lower this source's cadence rather than retrying harder",
    ),
    "backlog_critical": (
        WARNING,
        "add worker capacity or reduce cadence; the queue is not draining",
    ),
    "parser_degraded": (
        WARNING,
        "records are being dropped; inspect a stored payload against the "
        "adapter's required fields",
    ),
    "source_recovered": (INFO, "no action; recorded so the outage stays visible"),
    "source_disabled": (INFO, "no action; an operator turned this off"),
}

#: Which operational states raise which condition.
STATE_TO_CONDITION: dict[str, str] = {
    "AUTHORIZATION_REQUIRED": "authorization_revoked",
    "REVIEW_REQUIRED": "breaking_schema_drift",
    "FAILING": "sustained_collection_failure",
    "BLOCKED": "circuit_open",
    "STALE": "freshness_sla_breached",
    "RATE_LIMITED": "repeated_rate_limit",
    "DISABLED": "source_disabled",
    "HEALTHY": "source_recovered",
}

#: States that do not warrant an operator alert at all. DEGRADED is here on
#: purpose: a source with a named, understood gap is not an incident, and
#: paging somebody about it every sweep is how alerts get ignored.
NO_ALERT_STATES: frozenset[str] = frozenset({"DEGRADED", "UNKNOWN", "RETIRED"})


def _json_safe(value: Any) -> Any:
    json.dumps(value, default=str)
    return value


def build_event_id(
    *, source_id: Any, event_type: Any, from_state: Any, to_state: Any
) -> str:
    """Derived, so the same transition cannot produce two rows."""
    parts = [
        str(source_id or ""),
        str(event_type or ""),
        "" if from_state is None else str(from_state),
        str(to_state or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()


def build_alert_id(*, source_id: Any, condition: Any) -> str:
    """One open alert per (source, condition). Not one per sweep."""
    return hashlib.sha256(
        f"{source_id}|{condition}".encode()
    ).hexdigest()


def plan_transition(
    *, source_id: str, previous_state: Any, current_state: str, evidence: Any = None
) -> dict[str, Any] | None:
    """The event for one state change, or None when nothing changed.

    Returning None for "no change" is the whole design. A caller that has to
    filter afterwards will eventually forget to.
    """
    if previous_state is not None and str(previous_state) == str(current_state):
        return None
    event_type = STATE_TO_EVENT.get(str(current_state))
    if event_type is None:
        return None
    # A first sighting is not a recovery. Without this, every source in the
    # fleet emits SOURCE_RECOVERED the first time health is ever computed.
    if previous_state is None and event_type == "SOURCE_RECOVERED":
        return None

    severity, why = EVENT_SEVERITY[event_type]
    return _json_safe(
        {
            "event_id": build_event_id(
                source_id=source_id,
                event_type=event_type,
                from_state=previous_state,
                to_state=current_state,
            ),
            "source_id": source_id,
            "event_type": event_type,
            "from_state": None if previous_state is None else str(previous_state),
            "to_state": str(current_state),
            "severity": severity,
            "why_this_severity": why,
            "evidence": evidence,
        }
    )


def plan_alert(
    *, source_id: str, operational_state: str, evidence: Any = None
) -> dict[str, Any] | None:
    """The operator record for one state, or None when none is warranted."""
    state = str(operational_state)
    if state in NO_ALERT_STATES:
        return None
    condition = STATE_TO_CONDITION.get(state)
    if condition is None:
        return None
    severity, action = ALERT_CONTRACT[condition]
    return _json_safe(
        {
            "alert_id": build_alert_id(source_id=source_id, condition=condition),
            "source_id": source_id,
            "condition": condition,
            "severity": severity,
            "operational_state": state,
            "recommended_action": action,
            "evidence": evidence,
            "alert_state": "resolved" if condition == "source_recovered" else "open",
        }
    )


def _events_table() -> sa.Table:
    return sa.Table(
        EVENTS_TABLE,
        sa.MetaData(),
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("source_id", sa.Text()),
        sa.Column("event_type", sa.String(length=48)),
        sa.Column("from_state", sa.String(length=32)),
        sa.Column("to_state", sa.String(length=32)),
        sa.Column("severity", sa.String(length=16)),
        sa.Column("first_detected_at", sa.DateTime(timezone=True)),
        sa.Column("latest_detected_at", sa.DateTime(timezone=True)),
        sa.Column("detection_count", sa.Integer()),
        sa.Column("evidence_json", sa.Text()),
        sa.Column("dimension", sa.String(length=48)),
        sa.Column("failure_type", sa.String(length=48)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def _alerts_table() -> sa.Table:
    return sa.Table(
        ALERTS_TABLE,
        sa.MetaData(),
        sa.Column("alert_id", sa.String(length=64), primary_key=True),
        sa.Column("source_id", sa.Text()),
        sa.Column("condition", sa.String(length=64)),
        sa.Column("severity", sa.String(length=16)),
        sa.Column("operational_state", sa.String(length=32)),
        sa.Column("first_detected_at", sa.DateTime(timezone=True)),
        sa.Column("latest_detected_at", sa.DateTime(timezone=True)),
        sa.Column("evidence_json", sa.Text()),
        sa.Column("recommended_action", sa.Text()),
        sa.Column("alert_state", sa.String(length=16)),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True)),
        sa.Column("acknowledged_by", sa.Text()),
        sa.Column("resolved_at", sa.DateTime(timezone=True)),
        sa.Column("notified_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True)),
    )


def record_transitions(
    *, connection: Any, planned: list[dict[str, Any]], now: Any = None
) -> dict[str, Any]:
    """Write new transitions; advance the ones already on file.

    Two statements for the whole sweep, not two per source - the same
    discipline Gate 170 arrived at after issuing one UPDATE per event.
    """
    stamp = now or dt.datetime.now(dt.UTC)
    table = _events_table()
    rows = [entry for entry in planned if entry]
    if not rows:
        return _json_safe(
            {"events_inserted": 0, "events_advanced": 0, "statements": 0}
        )

    ids = sorted({str(entry["event_id"]) for entry in rows})
    existing: set[str] = set()
    for start in range(0, len(ids), 400):
        for row in connection.execute(
            sa.select(table.c.event_id).where(
                table.c.event_id.in_(ids[start : start + 400])
            )
        ):
            existing.add(str(row[0]))

    to_insert = []
    to_advance = []
    seen: set[str] = set()
    for entry in rows:
        event_id = str(entry["event_id"])
        if event_id in seen:
            continue
        seen.add(event_id)
        if event_id in existing:
            to_advance.append({"target_event_id": event_id, "seen_at": stamp})
            continue
        to_insert.append(
            {
                "event_id": event_id,
                "source_id": entry["source_id"],
                "event_type": entry["event_type"],
                "from_state": entry.get("from_state"),
                "to_state": entry["to_state"],
                "severity": entry["severity"],
                "first_detected_at": stamp,
                "latest_detected_at": stamp,
                "detection_count": 1,
                "evidence_json": json.dumps(entry.get("evidence"), default=str)
                if entry.get("evidence") is not None
                else None,
                "dimension": entry.get("dimension"),
                "failure_type": entry.get("failure_type"),
                "created_at": stamp,
            }
        )

    statements = 0
    if to_insert:
        connection.execute(sa.insert(table), to_insert)
        statements += 1
    if to_advance:
        connection.execute(
            sa.update(table)
            .where(table.c.event_id == sa.bindparam("target_event_id"))
            .values(
                latest_detected_at=sa.bindparam("seen_at"),
                detection_count=table.c.detection_count + 1,
            ),
            to_advance,
        )
        statements += 1

    return _json_safe(
        {
            "events_inserted": len(to_insert),
            "events_advanced": len(to_advance),
            "statements": statements,
            "first_detected_at_is_never_rewritten": True,
        }
    )


def record_alerts(
    *, connection: Any, planned: list[dict[str, Any]], now: Any = None
) -> dict[str, Any]:
    """Same shape: one open alert per (source, condition), advanced not duplicated."""
    stamp = now or dt.datetime.now(dt.UTC)
    table = _alerts_table()
    rows = [entry for entry in planned if entry]
    if not rows:
        return _json_safe(
            {"alerts_inserted": 0, "alerts_advanced": 0, "statements": 0}
        )

    ids = sorted({str(entry["alert_id"]) for entry in rows})
    existing: set[str] = set()
    for start in range(0, len(ids), 400):
        for row in connection.execute(
            sa.select(table.c.alert_id).where(
                table.c.alert_id.in_(ids[start : start + 400])
            )
        ):
            existing.add(str(row[0]))

    to_insert = []
    to_advance = []
    seen: set[str] = set()
    for entry in rows:
        alert_id = str(entry["alert_id"])
        if alert_id in seen:
            continue
        seen.add(alert_id)
        if alert_id in existing:
            to_advance.append({"target_alert_id": alert_id, "seen_at": stamp})
            continue
        resolved = entry.get("alert_state") == "resolved"
        to_insert.append(
            {
                "alert_id": alert_id,
                "source_id": entry["source_id"],
                "condition": entry["condition"],
                "severity": entry["severity"],
                "operational_state": entry["operational_state"],
                "first_detected_at": stamp,
                "latest_detected_at": stamp,
                "evidence_json": json.dumps(entry.get("evidence"), default=str)
                if entry.get("evidence") is not None
                else None,
                "recommended_action": entry["recommended_action"],
                "alert_state": entry.get("alert_state") or "open",
                "acknowledged_at": None,
                "acknowledged_by": None,
                "resolved_at": stamp if resolved else None,
                # Nothing is delivered in this gate.
                "notified_at": None,
                "created_at": stamp,
            }
        )

    statements = 0
    if to_insert:
        connection.execute(sa.insert(table), to_insert)
        statements += 1
    if to_advance:
        connection.execute(
            sa.update(table)
            .where(table.c.alert_id == sa.bindparam("target_alert_id"))
            .values(latest_detected_at=sa.bindparam("seen_at")),
            to_advance,
        )
        statements += 1

    return _json_safe(
        {
            "alerts_inserted": len(to_insert),
            "alerts_advanced": len(to_advance),
            "statements": statements,
            "notifications_sent": 0,
        }
    )


def event_invariant_failures(event: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if str(event.get("event_type")) not in EVENT_TYPES:
        failures.append("event_type_outside_vocabulary")
    if str(event.get("severity")) not in SEVERITIES:
        failures.append("severity_outside_vocabulary")
    if len(str(event.get("event_id") or "")) != 64:
        failures.append("event_id_is_not_a_sha256")
    if event.get("from_state") is not None and event.get("from_state") == event.get(
        "to_state"
    ):
        failures.append("an_event_that_is_not_a_transition")
    if not event.get("why_this_severity"):
        failures.append("severity_without_a_reason")
    return sorted(set(failures))


def alert_invariant_failures(alert: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    if str(alert.get("condition")) not in ALERT_CONDITIONS:
        failures.append("condition_outside_vocabulary")
    if str(alert.get("severity")) not in SEVERITIES:
        failures.append("severity_outside_vocabulary")
    if not str(alert.get("recommended_action") or "").strip():
        failures.append("an_alert_that_does_not_say_what_to_do")
    if alert.get("notified_at"):
        failures.append("this_gate_delivered_a_notification")
    return sorted(set(failures))


def describe_event_model() -> dict[str, Any]:
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "event_types": list(EVENT_TYPES),
            "severities": list(SEVERITIES),
            "event_severity": {k: list(v) for k, v in EVENT_SEVERITY.items()},
            "alert_conditions": list(ALERT_CONDITIONS),
            "alert_contract": {k: list(v) for k, v in ALERT_CONTRACT.items()},
            "no_alert_states": sorted(NO_ALERT_STATES),
            "every_event_has_a_severity": all(
                e in EVENT_SEVERITY for e in EVENT_TYPES
            ),
            "every_condition_has_an_action": all(
                bool(ALERT_CONTRACT[c][1]) for c in ALERT_CONDITIONS
            ),
            "severity_is_a_table_not_a_judgement": True,
            "delivery_is_not_built_in_this_gate": True,
        }
    )
