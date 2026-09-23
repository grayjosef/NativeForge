"""Alembic 0058: durable source operations events and operator alerts.

Gate 172's survey found the operational substrate already rich - cadence,
stale thresholds, failure counts and disable fields all live on the activation
row, and the circuit breaker, retry policy, freshness and lease services all
exist. Almost nothing here needed a table.

Two things did, and only because they are HISTORY rather than current state:

```text
nf_source_operations_events   what CHANGED, and when it first changed
nf_source_operator_alerts     what a human still needs to do about it
```

## Why events are not derivable

Current state answers "is this source stale". It cannot answer "when did it
go stale", "has it done this before", or "did it recover on its own last
time". Those are the questions that decide whether a source is flaky or
merely unlucky, and they need a row per TRANSITION.

## Identity makes idempotence a primary key, not a convention

```text
event_id = sha256(source_id | event_type | from_state | to_state)
```

Derived from the TRANSITION alone - no timestamp, deliberately. A health
sweep that runs every minute and finds the same source still stale writes
nothing on the second pass, and a time bucket in this hash would undo
exactly that. 172Y is explicit that polling
noise is the failure mode: an event stream that re-emits on every poll is a
log, and nobody reads it.

`first_detected_at` is never rewritten, `latest_detected_at` advances. That is
the same shape Gate 170 gave conflicts, for the same reason - "this has been
true for eleven days" is the fact an operator acts on.

## Source-global, deliberately

Neither table carries a tenant. Source health is a property of the source, not
of who is watching it, and a per-tenant copy would be five thousand rows
saying the same thing and eventually disagreeing.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision: str = "0058"
down_revision: str | None = "0057"
branch_labels: str | None = None
depends_on: str | None = None

EVENTS = "nf_source_operations_events"
ALERTS = "nf_source_operator_alerts"

EVENT_TYPES = (
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

SEVERITIES = ("INFO", "WARNING", "CRITICAL")

ALERT_STATES = ("open", "acknowledged", "resolved")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    rendered = ", ".join(f"'{value}'" for value in values)
    return f"{column} IN ({rendered})"


def upgrade() -> None:
    op.create_table(
        EVENTS,
        sa.Column("event_id", sa.String(length=64), primary_key=True),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("event_type", sa.String(length=48), nullable=False),
        sa.Column("from_state", sa.String(length=32), nullable=True),
        sa.Column("to_state", sa.String(length=32), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        # Never rewritten. The whole value of the row is that it says when
        # this started, not when it was last noticed.
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latest_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("detection_count", sa.Integer(), nullable=False, default=1),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.Column("dimension", sa.String(length=48), nullable=True),
        sa.Column("failure_type", sa.String(length=48), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            _in_list("event_type", EVENT_TYPES), name=f"ck_{EVENTS}_type"
        ),
        sa.CheckConstraint(
            _in_list("severity", SEVERITIES), name=f"ck_{EVENTS}_severity"
        ),
        sa.CheckConstraint("length(event_id) = 64", name=f"ck_{EVENTS}_id_length"),
        # A transition from a state to itself is not a transition. This is the
        # constraint that makes "no event every poll" a property of the
        # schema rather than a promise in the writer.
        sa.CheckConstraint(
            "from_state IS NULL OR from_state <> to_state",
            name=f"ck_{EVENTS}_is_a_transition",
        ),
        sa.CheckConstraint("detection_count >= 1", name=f"ck_{EVENTS}_detection_count"),
        sa.CheckConstraint(
            "latest_detected_at >= first_detected_at",
            name=f"ck_{EVENTS}_ordering",
        ),
    )
    op.create_index(f"ix_{EVENTS}_source", EVENTS, ["source_id"])
    op.create_index(f"ix_{EVENTS}_type", EVENTS, ["event_type"])
    op.create_index(
        f"ix_{EVENTS}_source_latest", EVENTS, ["source_id", "latest_detected_at"]
    )

    op.create_table(
        ALERTS,
        sa.Column("alert_id", sa.String(length=64), primary_key=True),
        sa.Column("source_id", sa.Text(), nullable=False),
        sa.Column("condition", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=16), nullable=False),
        sa.Column("operational_state", sa.String(length=32), nullable=False),
        sa.Column("first_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("latest_detected_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=True),
        sa.Column("recommended_action", sa.Text(), nullable=False),
        sa.Column("alert_state", sa.String(length=16), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acknowledged_by", sa.Text(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        # Gate 172Z builds alert READINESS. Nothing in this gate delivers,
        # and the column exists so a later gate cannot claim delivery
        # happened without recording when.
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            _in_list("severity", SEVERITIES), name=f"ck_{ALERTS}_severity"
        ),
        sa.CheckConstraint(
            _in_list("alert_state", ALERT_STATES), name=f"ck_{ALERTS}_state"
        ),
        sa.CheckConstraint("length(alert_id) = 64", name=f"ck_{ALERTS}_id_length"),
        # An acknowledgement nobody signed is not an acknowledgement.
        sa.CheckConstraint(
            "alert_state <> 'acknowledged' OR "
            "(acknowledged_at IS NOT NULL AND acknowledged_by IS NOT NULL)",
            name=f"ck_{ALERTS}_acknowledged_is_signed",
        ),
        sa.CheckConstraint(
            "alert_state <> 'resolved' OR resolved_at IS NOT NULL",
            name=f"ck_{ALERTS}_resolved_has_a_time",
        ),
        sa.CheckConstraint(
            "length(recommended_action) > 0",
            name=f"ck_{ALERTS}_action_is_not_empty",
        ),
        sa.CheckConstraint(
            "latest_detected_at >= first_detected_at",
            name=f"ck_{ALERTS}_ordering",
        ),
    )
    op.create_index(f"ix_{ALERTS}_source", ALERTS, ["source_id"])
    # The operator's own question: what is still open, worst first.
    op.create_index(
        f"ix_{ALERTS}_open", ALERTS, ["alert_state", "severity", "latest_detected_at"]
    )


def downgrade() -> None:
    op.drop_index(f"ix_{ALERTS}_open", table_name=ALERTS)
    op.drop_index(f"ix_{ALERTS}_source", table_name=ALERTS)
    op.drop_table(ALERTS)
    op.drop_index(f"ix_{EVENTS}_source_latest", table_name=EVENTS)
    op.drop_index(f"ix_{EVENTS}_type", table_name=EVENTS)
    op.drop_index(f"ix_{EVENTS}_source", table_name=EVENTS)
    op.drop_table(EVENTS)
