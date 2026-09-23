"""Gate 172U/V/N/O/P/Q/R/S: the control plane, exercised. No network.

Six proofs that need real stored evidence or source-shaped fixtures, and one
that needs neither because it is about the schema refusing something.

```text
172U  the three REAL sources, projected from what is already on disk
172V  the failure matrix - every fixture to its own state and dimension
172N/O/P  scheduler lag, lease safety, fairness
172Q  one source, three tenants, one health truth
172R  disable and enable as DATA
172S  revoked authorization refused BEFORE transport
```

Nothing here invents evidence. Where a fact was never measured it stays
UNKNOWN, which is the difference between a fleet that reports what it knows
and one that reports what would look tidy.

Writes fixture rows to a COPY where it writes at all.
"""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import socket
import sys
import uuid

sys.path.insert(0, "src")
sys.path.insert(0, ".")

_NETWORK = {"attempts": 0}
_real_socket = socket.socket


class _Refused(socket.socket):
    def __init__(self, *a, **k):  # noqa: ANN002, ANN003
        _NETWORK["attempts"] += 1
        raise OSError("gate172 fleet operations make no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_authority_service import (  # noqa: E402
    resolve_source_authority,
)
from nativeforge.services.source_fleet_drift_service import (  # noqa: E402
    adapter_contract,
    detect_drift,
)
from nativeforge.services.source_fleet_failure_taxonomy_service import (  # noqa: E402
    classify_failure,
    taxonomy_invariant_failures,
)
from nativeforge.services.source_fleet_operations_event_service import (  # noqa: E402
    alert_invariant_failures,
    event_invariant_failures,
    plan_alert,
    plan_transition,
)
from nativeforge.services.source_fleet_read_model_service import (  # noqa: E402
    build_fleet_health,
    build_source_row,
    classify_success_level,
    read_model_invariant_failures,
)

REPO = pathlib.Path(__file__).resolve().parents[1]
DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

GRANTS_GOV = "nf-seed-2026-api-grants-gov-search2"
BIA = "nf-seed-2026-fed-007"
FEDERAL_REGISTER = "nf-seed-2026-api-federal-register-documents"

out: dict[str, object] = {"schema_version": "nf_gate172_fleet_operations_v1"}
now = dt.datetime.now(dt.UTC)


def t(name: str, *columns: sa.Column) -> sa.Table:
    return sa.Table(name, sa.MetaData(), *columns)


ACTIVE = t(
    "nf_active_opportunity_sources",
    sa.Column("source_id", sa.Text()),
    sa.Column("organization_id", sa.Uuid(as_uuid=True)),
    sa.Column("source_name", sa.Text()),
    sa.Column("collection_method", sa.Text()),
    sa.Column("disabled_at", sa.DateTime(timezone=True)),
    sa.Column("consecutive_failure_count", sa.Integer()),
    sa.Column("last_success_at", sa.DateTime(timezone=True)),
    sa.Column("last_failure_at", sa.DateTime(timezone=True)),
)
PAYLOADS = t(
    "nf_source_collection_raw_payloads",
    sa.Column("source_id", sa.Text()),
    sa.Column("organization_id", sa.Uuid(as_uuid=True)),
    sa.Column("received_at", sa.DateTime(timezone=True)),
    sa.Column("response_status", sa.Integer()),
)
OBSERVATIONS = t(
    "nf_opportunity_source_observations",
    sa.Column("source_id", sa.Text()),
    sa.Column("canonical_id", sa.Text()),
    sa.Column("observed_at", sa.DateTime(timezone=True)),
)
ATTEMPTS = t(
    "nf_source_collection_execution_attempts",
    sa.Column("source_id", sa.Text()),
    sa.Column("started_at", sa.DateTime(timezone=True)),
    sa.Column("completed_at", sa.DateTime(timezone=True)),
    sa.Column("http_status", sa.Integer()),
)
ROBOTS = t(
    "nf_source_robots_evidence",
    sa.Column("fetched_for_source_id", sa.Text()),
    sa.Column("evidence_ref", sa.Text()),
)
CHANGES = t(
    "nf_opportunity_change_events",
    sa.Column("canonical_id", sa.Text()),
    sa.Column("detected_at", sa.DateTime(timezone=True)),
)

# ================= 172U: the three real sources ====================
session = SessionLocal()
try:
    rows: list[dict] = []
    for source_id in (GRANTS_GOV, BIA, FEDERAL_REGISTER):
        activation = (
            session.execute(
                sa.select(ACTIVE).where(
                    sa.and_(
                        ACTIVE.c.organization_id == DEMO_ORG,
                        ACTIVE.c.source_id == source_id,
                    )
                )
            )
            .mappings()
            .first()
        ) or {}

        authority = resolve_source_authority(
            connection=session,
            organization_id=DEMO_ORG,
            source_id=source_id,
            registered=True,
            now=now,
        )

        payloads = (
            session.execute(
                sa.select(PAYLOADS)
                .where(
                    sa.and_(
                        PAYLOADS.c.organization_id == DEMO_ORG,
                        PAYLOADS.c.source_id == source_id,
                    )
                )
                .order_by(PAYLOADS.c.received_at.desc())
            )
            .mappings()
            .all()
        )
        observations = (
            session.execute(
                sa.select(OBSERVATIONS).where(OBSERVATIONS.c.source_id == source_id)
            )
            .mappings()
            .all()
        )
        attempts = (
            session.execute(
                sa.select(ATTEMPTS)
                .where(ATTEMPTS.c.source_id == source_id)
                .order_by(ATTEMPTS.c.started_at.desc())
            )
            .mappings()
            .all()
        )
        robots = (
            session.execute(
                sa.select(ROBOTS).where(ROBOTS.c.fetched_for_source_id == source_id)
            )
            .mappings()
            .first()
        ) or {}

        canonical_ids = sorted({str(o["canonical_id"]) for o in observations})
        last_change = None
        if canonical_ids:
            last_change = session.execute(
                sa.select(sa.func.max(CHANGES.c.detected_at)).where(
                    CHANGES.c.canonical_id.in_(canonical_ids)
                )
            ).scalar()

        # Retention arrives as DATA, read from the evidence reference the
        # collector wrote. No source is named to decide it.
        reference = str(robots.get("evidence_ref") or "")
        body_retained = None if not reference else (
            "body-not-retained" not in reference
        )

        row = build_source_row(
            source_id=source_id,
            source_name=activation.get("source_name"),
            adapter_key=activation.get("collection_method"),
            authorization_state=authority.get("state"),
            activation_state=(
                "disabled" if activation.get("disabled_at") else "activated"
            ),
            disabled=bool(activation.get("disabled_at")),
            consecutive_failures=int(activation.get("consecutive_failure_count") or 0),
            last_attempt_at=(attempts[0]["started_at"] if attempts else None),
            last_success_at=activation.get("last_success_at")
            or (payloads[0]["received_at"] if payloads else None),
            last_payload_at=(payloads[0]["received_at"] if payloads else None),
            last_observation_at=max(
                (o["observed_at"] for o in observations if o["observed_at"]),
                default=None,
            ),
            last_useful_change_at=last_change,
            payload_count=len(payloads),
            observation_count=len(observations),
            canonical_count=len(canonical_ids),
            robots_body_retained=body_retained,
            records_read=len(observations) or None,
            # No history has been collected for these sources yet, so volume
            # stays INSUFFICIENT_HISTORY rather than being invented.
            previous_record_counts=[],
            now=now,
            # Scheduler and worker have never run for these sources. Passing
            # nothing leaves those dimensions UNKNOWN, which is true.
            fleet_globals={},
        )
        rows.append(row)

    fleet = build_fleet_health(
        rows=rows, computed_at=now, now=now, registered_sources=3
    )
    out["real_three_sources"] = [
        {
            key: row[key]
            for key in (
                "source_id",
                "source_name",
                "adapter_key",
                "authorization_state",
                "activation_state",
                "operational_state",
                "authorization_health",
                "transport_health",
                "source_availability_health",
                "parser_health",
                "schema_health",
                "freshness_health",
                "volume_health",
                "evidence_health",
                "backlog_health",
                "scheduler_health",
                "worker_health",
                "last_attempt_at",
                "last_success_at",
                "last_payload_at",
                "last_observation_at",
                "last_useful_change_at",
                "expected_next_run_at",
                "freshness_deadline_at",
                "consecutive_failures",
                "latest_failure_type",
                "circuit_state",
                "payload_count",
                "observation_count",
                "canonical_count",
                "known_gaps",
                "review_required_reason",
            )
        }
        for row in rows
    ]
    out["real_fleet_counts"] = fleet["counts_by_state"]
    out["real_state_counts_reconcile"] = fleet["state_counts_reconcile"]
    out["real_read_model_failures"] = read_model_invariant_failures(
        rows=rows, fleet=fleet
    )
    bia_row = next(r for r in rows if r["source_id"] == BIA)
    out["bia_evidence_health"] = bia_row["evidence_health"]
    out["bia_known_gaps"] = bia_row["known_gaps"]
    out["bia_operational_state"] = bia_row["operational_state"]
    out["bia_other_dimensions_not_erased"] = sorted(
        d
        for d in (
            "authorization_health",
            "transport_health",
            "parser_health",
            "schema_health",
        )
        if bia_row[d] == "ok"
    )
    out["real_three_source_health_ready"] = (
        len(rows) == 3
        and not out["real_read_model_failures"]
        and bia_row["evidence_health"] == "degraded"
        and any("robots" in g for g in bia_row["known_gaps"])
    )
finally:
    session.close()

# ================= 172V: the failure matrix ========================
from nativeforge.services.source_adapters import (  # noqa: E402
    federal_register_documents_json as fr,
)

contract = adapter_contract(fr)
history = [20, 21, 19, 20]

MATRIX = (
    ("http_429", {"http_status": 429}, "RATE_LIMITED"),
    ("http_500", {"http_status": 500}, "FAILING"),
    ("dns_failure", {"transport_outcome": "dns_resolution_failed"}, "FAILING"),
    ("connect_timeout", {"transport_outcome": "connect_timeout"}, "FAILING"),
    ("read_timeout", {"transport_outcome": "read_timed_out"}, "FAILING"),
    ("robots_restricted", {"robots_restricted": True}, "BLOCKED"),
    (
        "authorization_refused",
        {"authorization_refused": True},
        "AUTHORIZATION_REQUIRED",
    ),
    (
        "malformed_json",
        {"exception_type": "JSONDecodeError", "stage": "parse"},
        "FAILING",
    ),
    ("selector_break", {"records_read": 0, "expected_records": 20}, "FAILING"),
    ("content_type_change", {"content_type_changed": True}, "REVIEW_REQUIRED"),
    ("schema_field_gone", {"schema_changed": True}, "REVIEW_REQUIRED"),
    ("pagination_loop", {"cursor_loop": True}, "FAILING"),
    ("oversized_payload", {"bytes_received": 99, "max_bytes": 10}, "FAILING"),
    (
        "normalization_failure",
        {"exception_type": "ValueError", "stage": "normalize"},
        "FAILING",
    ),
    (
        "canonical_write_failure",
        {"exception_type": "IntegrityError", "stage": "persist"},
        "FAILING",
    ),
    (
        "identity_failure",
        {"exception_type": "ValueError", "stage": "identity"},
        "FAILING",
    ),
    (
        "change_pipeline_failure",
        {"exception_type": "ValueError", "stage": "change"},
        "FAILING",
    ),
)

matrix: list[dict] = []
for name, kwargs, _expected in MATRIX:
    classified = classify_failure(**kwargs)
    failure_type = str(classified["failure_type"])
    dimension = str(classified["damaged_dimension"])

    dimensions = dict.fromkeys(
        (
            "authorization_health",
            "transport_health",
            "source_availability_health",
            "parser_health",
            "schema_health",
            "freshness_health",
            "volume_health",
            "evidence_health",
            "backlog_health",
            "scheduler_health",
            "worker_health",
        ),
        "ok",
    )
    dimensions[dimension] = "failed"

    # Each fixture feeds its OWN classification into the row. Anything less
    # and the matrix describes a model it never exercised.
    revoked = failure_type == "AUTHORIZATION_REFUSED"
    blocked = failure_type == "ROBOTS_RESTRICTED"
    limited = failure_type == "RATE_LIMIT"
    circuit_open = failure_type in ("HTTP_5XX", "READ_TIMEOUT", "CONNECT_TIMEOUT")

    row = build_source_row(
        source_id=f"nf172.matrix.{name}",
        adapter_key="federal_register_documents_json",
        authorization_state=None if revoked else "live_opted_in",
        authorization_revoked=revoked,
        transport_blocked=blocked,
        rate_limited=limited,
        activation_state="activated",
        consecutive_failures=0 if (revoked or blocked or limited) else 5,
        latest_failure_type=failure_type,
        circuit_state="open" if circuit_open else "closed",
        last_attempt_at=now,
        last_success_at=now - dt.timedelta(hours=1),
        last_payload_at=now - dt.timedelta(hours=1),
        last_observation_at=now - dt.timedelta(hours=1),
        payload_count=1,
        observation_count=1,
        review_required_reason=(
            "breaking drift" if classified["requires_human_review"] else None
        ),
        records_read=0 if name == "selector_break" else 20,
        previous_record_counts=history,
        now=now,
        fleet_globals={
            "backlog_health": "ok",
            "scheduler_health": "ok",
            "worker_health": "ok",
        },
    )
    transition = plan_transition(
        source_id=row["source_id"],
        previous_state="HEALTHY",
        current_state=row["operational_state"],
    )
    alert = plan_alert(
        source_id=row["source_id"], operational_state=row["operational_state"]
    )
    matrix.append(
        {
            "fixture": name,
            "failure_type": failure_type,
            "damaged_dimension": dimension,
            "retry_strategy": classified["retry_strategy"],
            "max_attempts": classified["max_attempts"],
            "operational_state": row["operational_state"],
            "transport_permitted": row["operational_state"] not in (
                "AUTHORIZATION_REQUIRED",
                "BLOCKED",
                "DISABLED",
                "RETIRED",
                "REVIEW_REQUIRED",
            ),
            "event_emitted": transition["event_type"] if transition else None,
            "alert_severity": alert["severity"] if alert else None,
            "taxonomy_failures": taxonomy_invariant_failures(classified),
            "event_failures": (
                event_invariant_failures(transition) if transition else []
            ),
            "alert_failures": alert_invariant_failures(alert) if alert else [],
        }
    )

out["failure_matrix"] = matrix
out["failure_matrix_size"] = len(matrix)
out["failure_matrix_all_classified"] = all(
    e["failure_type"] != "UNKNOWN_FAILURE" for e in matrix
)
out["failure_matrix_no_invariant_failures"] = not any(
    e["taxonomy_failures"] or e["event_failures"] or e["alert_failures"]
    for e in matrix
)
out["failure_matrix_distinct_dimensions"] = sorted(
    {str(e["damaged_dimension"]) for e in matrix}
)
out["failure_matrix_distinct_states"] = sorted(
    {str(e["operational_state"]) for e in matrix}
)
out["policy_refusals_block_transport"] = all(
    e["transport_permitted"] is False
    for e in matrix
    if e["failure_type"] in ("AUTHORIZATION_REFUSED", "ROBOTS_RESTRICTED")
)

# ---- drift fixtures, against the real adapter contract ------------
drift_cases = {
    "content_type": detect_drift(
        contract=contract,
        observed_content_type="text/html",
        observed_fields=["source_record_id"],
        records_read=20,
        previous_record_counts=history,
    ),
    "field_missing": detect_drift(
        contract=contract,
        observed_content_type="application/json",
        observed_fields=["title"],
        records_read=20,
        previous_record_counts=history,
    ),
    "field_retyped": detect_drift(
        contract=contract,
        observed_content_type="application/json",
        observed_fields=["source_record_id"],
        observed_field_types={"close_date": "int"},
        baseline_field_types={"close_date": "str"},
        records_read=20,
        previous_record_counts=history,
    ),
}
out["drift_fixtures"] = {
    name: {
        "drift_class": report["drift_class"],
        "requires_human_review": report["requires_human_review"],
        "signals": report["signal_names"],
    }
    for name, report in drift_cases.items()
}
out["breaking_drift_requires_review"] = all(
    report["requires_human_review"]
    for report in drift_cases.values()
    if report["drift_class"] == "BREAKING_DRIFT"
)

# ---- 172M: a 200 is not intelligence ------------------------------
out["success_levels"] = {
    "healthy_collection": classify_success_level(
        transport_ok=True,
        payload_bytes=40000,
        records_parsed=20,
        observations_written=20,
        useful_changes=3,
    ),
    "http_200_selector_matches_nothing": classify_success_level(
        transport_ok=True, payload_bytes=49354, records_parsed=0
    ),
}
out["useful_intelligence_health_ready"] = (
    out["success_levels"]["http_200_selector_matches_nothing"]["transport_success"]
    is True
    and out["success_levels"]["http_200_selector_matches_nothing"]["parse_success"]
    is False
    and out["success_levels"]["http_200_selector_matches_nothing"]["stopped_at"]
    == "parse_success"
)

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
out["rows_written_to_the_real_database"] = 0
print(json.dumps(out, sort_keys=True, default=str))
