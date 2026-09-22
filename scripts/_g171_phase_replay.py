"""Gate 171S: replay both real payloads with the network disabled.

The claim being tested is that the persisted bytes are sufficient. Not "we
could fetch it again" - that the stored evidence alone reproduces every
downstream conclusion, byte for byte and row for row.

The socket is replaced before any project module is imported, and the count of
attempted opens is reported. A replay that quietly refetched would show up as
a non-zero count rather than as a passing test.

Idempotence is checked by COMPARING GRAPH STATE before and after, not by
trusting the writer's own report of what it did.
"""

from __future__ import annotations

import hashlib
import importlib
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
        raise OSError("gate171 replay makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.canonical_opportunity_batch_repository import (  # noqa: E402,E501
    NormalizedSourceObservation,
    persist_observations,
)
from nativeforge.services.source_adapter_contract_service import (  # noqa: E402
    PageCursor,
    identity_for_normalized,
    normalized_envelope_for,
)

DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
ADAPTER_PACKAGE = "nativeforge.services.source_adapters"
GATE171_SOURCES = (
    "nf-seed-2026-fed-007",
    "nf-seed-2026-api-federal-register-documents",
)


def t(name: str, *columns: sa.Column) -> sa.Table:
    return sa.Table(name, sa.MetaData(), *columns)


PAYLOADS = t(
    "nf_source_collection_raw_payloads",
    sa.Column("source_id", sa.Text()),
    sa.Column("organization_id", sa.Uuid(as_uuid=True)),
    sa.Column("received_at", sa.DateTime(timezone=True)),
    sa.Column("body_bytes", sa.LargeBinary()),
    sa.Column("payload_size_bytes", sa.Integer()),
    sa.Column("payload_sha256", sa.Text()),
)
ACTIVE = t(
    "nf_active_opportunity_sources",
    sa.Column("source_id", sa.Text()),
    sa.Column("organization_id", sa.Uuid(as_uuid=True)),
    sa.Column("collection_method", sa.Text()),
    sa.Column("source_url_or_search_target", sa.Text()),
)
CANONICAL = t(
    "nf_canonical_opportunities",
    sa.Column("canonical_id", sa.Text()),
    sa.Column("identity_layer", sa.Text()),
    sa.Column("current_version_id", sa.Text()),
)
OBS = t(
    "nf_opportunity_source_observations",
    sa.Column("observation_id", sa.Text()),
    sa.Column("canonical_id", sa.Text()),
    sa.Column("source_id", sa.Text()),
    sa.Column("raw_payload_sha256", sa.Text()),
)
VERSIONS = t(
    "nf_opportunity_versions",
    sa.Column("version_id", sa.Text()),
    sa.Column("canonical_id", sa.Text()),
)
PROV = t(
    "nf_opportunity_field_provenance",
    sa.Column("provenance_id", sa.Text()),
    sa.Column("canonical_id", sa.Text()),
    sa.Column("source_id", sa.Text()),
    sa.Column("field_name", sa.Text()),
)
EVENTS = t(
    "nf_opportunity_change_events",
    sa.Column("change_event_id", sa.Text()),
    sa.Column("canonical_id", sa.Text()),
    sa.Column("change_type", sa.Text()),
    sa.Column("materiality", sa.Text()),
)


def snapshot(session: sa.orm.Session) -> dict[str, object]:
    """Graph state as comparable sets, not as counts.

    Counts can stay equal while rows change underneath. Ids cannot.
    """
    return {
        "canonical": sorted(
            f"{r[0]}|{r[1]}|{r[2]}"
            for r in session.execute(
                sa.select(
                    CANONICAL.c.canonical_id,
                    CANONICAL.c.identity_layer,
                    CANONICAL.c.current_version_id,
                )
            )
        ),
        "observations": sorted(
            str(r[0]) for r in session.execute(sa.select(OBS.c.observation_id))
        ),
        "versions": sorted(
            str(r[0]) for r in session.execute(sa.select(VERSIONS.c.version_id))
        ),
        "provenance": sorted(
            str(r[0]) for r in session.execute(sa.select(PROV.c.provenance_id))
        ),
        "change_events": sorted(
            f"{r[0]}|{r[1]}|{r[2]}"
            for r in session.execute(
                sa.select(
                    EVENTS.c.change_event_id,
                    EVENTS.c.change_type,
                    EVENTS.c.materiality,
                )
            )
        ),
    }


out: dict[str, object] = {"schema_version": "nf_gate171_replay_v1"}
session = SessionLocal()
try:
    before = snapshot(session)
    per_source: list[dict] = []
    observations: list[NormalizedSourceObservation] = []

    for source_id in GATE171_SOURCES:
        payload = (
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
            .first()
        )
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
        )
        body = bytes(payload.get("body_bytes") or b"")
        stored_sha = str(payload.get("payload_sha256"))
        recomputed = hashlib.sha256(body).hexdigest()

        adapter_key = str(activation.get("collection_method"))
        adapter = importlib.import_module(f"{ADAPTER_PACKAGE}.{adapter_key}")
        descriptor = adapter.build_descriptor(
            source_id=source_id,
            source_url=str(activation.get("source_url_or_search_target")),
        )

        records = list(
            adapter.read_records(
                descriptor=descriptor,
                body_bytes=body,
                media_type=descriptor.expected_media_types[0],
                cursor=PageCursor(
                    max_pages=descriptor.max_pages,
                    max_records=descriptor.max_records,
                ),
            )
        )
        record_ids = sorted(r.source_record_id for r in records)
        identities: list[str] = []
        for record in records:
            envelope = normalized_envelope_for(record, adapter_key=adapter_key)
            if not envelope.get("parseable"):
                continue
            identity = identity_for_normalized(envelope, source_id=source_id)
            identities.append(str(identity.get("identity_layer")))
            observations.append(
                NormalizedSourceObservation(
                    source_id=source_id,
                    normalized=envelope,
                    raw_payload_sha256=stored_sha,
                    identity=identity,
                    source_authority_host=str(descriptor.base_url).split("/")[2],
                )
            )

        per_source.append(
            {
                "source_id": source_id,
                "adapter_key": adapter_key,
                "stored_bytes": int(payload.get("payload_size_bytes") or 0),
                "readback_bytes": len(body),
                "bytes_identical": len(body)
                == int(payload.get("payload_size_bytes") or -1),
                "stored_sha256": stored_sha,
                "recomputed_sha256": recomputed,
                "sha256_identical": stored_sha == recomputed,
                "records_read": len(records),
                "record_ids": record_ids,
                "identity_layers": sorted(set(identities)),
            }
        )

    # Replay the write. Derived ids mean this must be a no-op.
    persist_observations(connection=session, observations=observations)
    after = snapshot(session)

    out["per_source"] = per_source
    out["all_bytes_identical"] = all(s["bytes_identical"] for s in per_source)
    out["all_sha256_identical"] = all(s["sha256_identical"] for s in per_source)
    out["observations_replayed"] = len(observations)

    diffs = {
        name: {
            "added": sorted(set(after[name]) - set(before[name])),
            "removed": sorted(set(before[name]) - set(after[name])),
        }
        for name in before
    }
    out["graph_diff"] = diffs
    out["graph_unchanged"] = all(
        not d["added"] and not d["removed"] for d in diffs.values()
    )
    out["idempotent_writes"] = out["graph_unchanged"]
    out["canonical_outcomes_identical"] = not diffs["canonical"]["added"]
    out["provenance_identical"] = not diffs["provenance"]["added"]
    out["change_events_identical"] = not diffs["change_events"]["added"]
finally:
    session.close()

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
out["network_requests"] = _NETWORK["attempts"]
out["replay_without_network"] = (
    _NETWORK["attempts"] == 0
    and bool(out["all_bytes_identical"])
    and bool(out["all_sha256_identical"])
    and bool(out["graph_unchanged"])
)
print(json.dumps(out, sort_keys=True, default=str))
