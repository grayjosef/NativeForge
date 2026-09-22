"""Gate 171O: fleet health for three live sources. No network.

Health is per SOURCE and derived from storage, never from a config file that
says a source is fine. The three sources are read from the activation table
rather than listed here, so a fourth appears without an edit.

## The gap is a field, not a footnote

BIA's robots response BODY was not retained - the request succeeded, the row
insert failed on a CHECK constraint, and the bytes went with the process. The
status, byte count, sha256 and derived verdict are all on file, so the verdict
is re-derivable and migration 0049's constraint is satisfied.

`robots_body_retained` is therefore a named boolean on the source, and
`known_gaps` carries the reason. A single `healthy: true` that swallowed this
would be the exact failure this campaign keeps finding: a green with two
possible causes.

A source is not healthy because it is authorized. It is healthy when it has
recent evidence, that evidence parsed, and nothing about it is unknown.
"""

from __future__ import annotations

import datetime as dt
import json
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
        raise OSError("gate171 fleet health makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_authority_service import (  # noqa: E402
    resolve_source_authority,
)
from nativeforge.services.source_monitoring_approved_source_service import (  # noqa: E402,E501
    load_registry_rows,
)

DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")

#: Every field Gate 171O asks for. Named so a missing one is visible rather
#: than absent.
REQUIRED_HEALTH_FIELDS = (
    "source_id",
    "source_name",
    "adapter_key",
    "authorization_state",
    "activation_state",
    "last_attempt",
    "last_success",
    "last_failure",
    "payload_count",
    "observation_count",
    "canonical_outcome_count",
    "latest_evidence_age_seconds",
    "collection_duration_seconds",
    "robots_decision",
    "robots_body_retained",
    "known_gaps",
    "health_state",
)

HEALTH_STATES = ("healthy", "degraded", "unknown", "never_collected", "disabled")


def t(name: str, *columns: sa.Column) -> sa.Table:
    return sa.Table(name, sa.MetaData(), *columns)


ACTIVE = t(
    "nf_active_opportunity_sources",
    sa.Column("source_id", sa.Text()),
    sa.Column("organization_id", sa.Uuid(as_uuid=True)),
    sa.Column("source_name", sa.Text()),
    sa.Column("collection_method", sa.Text()),
    sa.Column("source_status", sa.Text()),
    sa.Column("source_health_status", sa.Text()),
    sa.Column("disabled_at", sa.DateTime(timezone=True)),
    sa.Column("activation_approved_at", sa.DateTime(timezone=True)),
)
PAYLOADS = t(
    "nf_source_collection_raw_payloads",
    sa.Column("source_id", sa.Text()),
    sa.Column("organization_id", sa.Uuid(as_uuid=True)),
    sa.Column("received_at", sa.DateTime(timezone=True)),
    sa.Column("response_status", sa.Integer()),
    sa.Column("payload_size_bytes", sa.Integer()),
)
OBSERVATIONS = t(
    "nf_opportunity_source_observations",
    sa.Column("source_id", sa.Text()),
    sa.Column("canonical_id", sa.Text()),
    # `observed_at`, not `retrieved_at`. The payload table uses `received_at`
    # and this one uses `observed_at`; guessing produced a column that does
    # not exist, which SQLite said so plainly.
    sa.Column("observed_at", sa.DateTime(timezone=True)),
)
ROBOTS = t(
    "nf_source_robots_evidence",
    sa.Column("fetched_for_source_id", sa.Text()),
    sa.Column("organization_id", sa.Uuid(as_uuid=True)),
    sa.Column("fetched_at", sa.DateTime(timezone=True)),
    sa.Column("http_status", sa.Integer()),
    sa.Column("decision", sa.Text()),
    sa.Column("payload_sha256", sa.Text()),
    sa.Column("evidence_ref", sa.Text()),
)

out: dict[str, object] = {"schema_version": "nf_gate171_fleet_health_v1"}
now = dt.datetime.now(dt.UTC)

registry = load_registry_rows()

session = SessionLocal()
try:
    sources = (
        session.execute(
            sa.select(ACTIVE)
            .where(ACTIVE.c.organization_id == DEMO_ORG)
            .order_by(ACTIVE.c.source_id)
        )
        .mappings()
        .all()
    )

    fleet: list[dict] = []
    for row in sources:
        source_id = str(row["source_id"])
        gaps: list[str] = []

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
                sa.select(OBSERVATIONS).where(
                    OBSERVATIONS.c.source_id == source_id
                )
            )
            .mappings()
            .all()
        )
        robots = (
            session.execute(
                sa.select(ROBOTS)
                .where(ROBOTS.c.fetched_for_source_id == source_id)
                .order_by(ROBOTS.c.fetched_at.desc())
            )
            .mappings()
            .first()
        )

        authority = resolve_source_authority(
            connection=session,
            organization_id=DEMO_ORG,
            source_id=source_id,
            registered=True,
            now=now,
        )

        latest = payloads[0] if payloads else None
        successes = [p for p in payloads if (p.get("response_status") or 0) == 200]
        failures = [
            p
            for p in payloads
            if p.get("response_status") is None
            or int(p.get("response_status") or 0) >= 400
        ]

        def stamp(value: object) -> str | None:
            return value.isoformat() if isinstance(value, dt.datetime) else None

        age = None
        if latest is not None and isinstance(latest.get("received_at"), dt.datetime):
            received = latest["received_at"]
            if received.tzinfo is None:
                received = received.replace(tzinfo=dt.UTC)
            age = round((now - received).total_seconds(), 1)

        # Robots body retention, per source. The evidence_ref records it too,
        # so the boolean and the reference cannot disagree silently.
        robots_ref = str((robots or {}).get("evidence_ref") or "")
        body_retained = bool(robots) and "body-not-retained" not in robots_ref
        if robots and not body_retained:
            gaps.append(
                "robots_response_body_not_retained:"
                "status_bytes_and_sha256_are_on_file_but_the_bytes_are_not"
            )
        if not robots:
            gaps.append("no_robots_evidence_on_file")
        if not payloads:
            gaps.append("no_payload_collected")
        if not observations:
            gaps.append("no_observation_normalized")
        if not authority.get("governance_complete"):
            gaps.append(
                f"authorization_incomplete:{authority.get('state')}"
            )

        if row.get("disabled_at") is not None:
            state = "disabled"
        elif not payloads:
            state = "never_collected"
        elif gaps:
            # Named gaps mean degraded, never healthy. A source with an
            # unretained robots body is still collecting - it is not fine.
            state = "degraded"
        else:
            state = "healthy"

        # The catalog row is the adapter binding the attribution resolver uses,
        # so it is the truthful answer to "which adapter". Gate 163 set this
        # source's `collection_method` to `documented_public_api`, which is a
        # collection STYLE and predates the adapter-key convention; reporting
        # it as the adapter key would be reporting a category as an identity.
        catalog_key = str(registry.get(source_id, {}).get("adapter_key") or "")
        entry = {
            "source_id": source_id,
            "source_name": row.get("source_name"),
            "adapter_key": catalog_key or row.get("collection_method"),
            "collection_method": row.get("collection_method"),
            "authorization_state": authority.get("state"),
            "activation_state": (
                "disabled" if row.get("disabled_at") else "activated"
            ),
            "last_attempt": stamp((latest or {}).get("received_at")),
            "last_success": stamp(
                (successes[0] if successes else {}).get("received_at")
            ),
            "last_failure": stamp(
                (failures[0] if failures else {}).get("received_at")
            ),
            "payload_count": len(payloads),
            "observation_count": len(observations),
            "canonical_outcome_count": len(
                {str(o["canonical_id"]) for o in observations}
            ),
            "latest_evidence_age_seconds": age,
            "collection_duration_seconds": None,
            "robots_decision": (robots or {}).get("decision"),
            "robots_http_status": (robots or {}).get("http_status"),
            "robots_payload_sha256": (robots or {}).get("payload_sha256"),
            "robots_body_retained": body_retained,
            "known_gaps": sorted(gaps),
            "health_state": state,
        }
        fleet.append(entry)

    out["fleet"] = fleet
    out["source_count"] = len(fleet)
    out["every_required_field_present"] = all(
        all(name in entry for name in REQUIRED_HEALTH_FIELDS) for entry in fleet
    )
    out["every_health_state_in_vocabulary"] = all(
        entry["health_state"] in HEALTH_STATES for entry in fleet
    )
    out["three_live_sources_registered"] = len(fleet) >= 3
    out["three_live_sources_authorized"] = sum(
        1
        for entry in fleet
        if str(entry["authorization_state"])
        in ("live_opted_in", "authorized_for_live")
    ) >= 3
    out["three_live_sources_collectable"] = sum(
        1 for entry in fleet if int(entry["payload_count"]) > 0
    ) >= 3
    out["adapters_in_use"] = sorted({str(e["adapter_key"]) for e in fleet})
    out["heterogeneous_adapters"] = len(out["adapters_in_use"]) >= 3

    bia = next(
        (e for e in fleet if e["source_id"] == "nf-seed-2026-fed-007"), None
    )
    out["bia_robots_body_retained"] = bool(
        (bia or {}).get("robots_body_retained")
    )
    out["bia_robots_evidence_gap_named"] = bool(
        bia and any("robots_response_body_not_retained" in g for g in bia["known_gaps"])
    )
    # A gap that is named is not hidden inside a healthy boolean.
    out["gap_is_not_hidden_in_a_healthy_flag"] = bool(
        bia and bia["health_state"] != "healthy"
    )
    out["sources_with_named_gaps"] = sorted(
        str(e["source_id"]) for e in fleet if e["known_gaps"]
    )
finally:
    session.close()

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
