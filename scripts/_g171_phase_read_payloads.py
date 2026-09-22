"""Gate 171H/I: read the two persisted payloads back and check the hypotheses.

Offline. The bytes are already durable; this opens no socket and re-requests
nothing. Its whole job is to answer, from storage, the question the approval
packet left open: does each adapter's `read_records` actually match what the
source returned?

A conformance report over synthetic fixtures said `fixtures_are_real: false`.
This is the run that can change that answer, and it reports the answer it
finds rather than the one that would be convenient.
"""

from __future__ import annotations

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
        raise OSError("gate171 payload readback makes no network request")


socket.socket = _Refused  # type: ignore[misc,assignment]

import importlib  # noqa: E402

import sqlalchemy as sa  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.services.source_adapter_contract_service import (  # noqa: E402
    PageCursor,
    record_failures,
)

DEMO_ORG = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
ADAPTER_PACKAGE = "nativeforge.services.source_adapters"

PAYLOADS = sa.Table(
    "nf_source_collection_raw_payloads",
    sa.MetaData(),
    sa.Column("source_id", sa.Text()),
    sa.Column("organization_id", sa.Uuid(as_uuid=True)),
    sa.Column("attempt_id", sa.Text()),
    sa.Column("received_at", sa.DateTime(timezone=True)),
    sa.Column("response_status", sa.Integer()),
    sa.Column("media_type", sa.Text()),
    sa.Column("body_bytes", sa.LargeBinary()),
    sa.Column("payload_size_bytes", sa.Integer()),
    sa.Column("payload_sha256", sa.Text()),
    sa.Column("live_fetch_performed", sa.Boolean()),
)

ACTIVE = sa.Table(
    "nf_active_opportunity_sources",
    sa.MetaData(),
    sa.Column("source_id", sa.Text()),
    sa.Column("organization_id", sa.Uuid(as_uuid=True)),
    sa.Column("collection_method", sa.Text()),
    sa.Column("source_url_or_search_target", sa.Text()),
)

GATE171_SOURCES = (
    "nf-seed-2026-fed-007",
    "nf-seed-2026-api-federal-register-documents",
)

out: dict[str, object] = {"schema_version": "nf_gate171_payload_readback_v1"}
reports: list[dict] = []

session = SessionLocal()
try:
    for source_id in GATE171_SOURCES:
        report: dict[str, object] = {"source_id": source_id}
        row = (
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
        if row is None:
            report["payload_on_file"] = False
            reports.append(report)
            continue

        body = bytes(row.get("body_bytes") or b"")
        report["payload_on_file"] = True
        report["http_status"] = row.get("response_status")
        report["bytes"] = int(row.get("payload_size_bytes") or 0)
        report["payload_sha256"] = row.get("payload_sha256")
        report["media_type"] = row.get("media_type")
        report["live_fetch_performed"] = bool(row.get("live_fetch_performed"))
        report["body_readback_bytes"] = len(body)
        report["body_matches_recorded_size"] = len(body) == int(
            row.get("payload_size_bytes") or -1
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
        adapter_key = str((activation or {}).get("collection_method") or "")
        report["adapter_key"] = adapter_key

        adapter = importlib.import_module(f"{ADAPTER_PACKAGE}.{adapter_key}")
        descriptor = adapter.build_descriptor(
            source_id=source_id,
            source_url=str((activation or {}).get("source_url_or_search_target")),
        )
        media = descriptor.expected_media_types[0]

        try:
            cursor = PageCursor(
                max_pages=descriptor.max_pages, max_records=descriptor.max_records
            )
            records = list(
                adapter.read_records(
                    descriptor=descriptor,
                    body_bytes=body,
                    media_type=media,
                    cursor=cursor,
                )
            )
            report["hypothesis_held"] = True
            report["records_read"] = len(records)
            report["record_failures"] = sorted(
                {f for r in records for f in record_failures(r)}
            )
            report["first_record"] = (
                {
                    "source_record_id": records[0].source_record_id,
                    "supported_fields": list(records[0].supported_fields),
                    "documents": len(records[0].documents),
                    "fields": {
                        k: (str(v)[:70] if v is not None else None)
                        for k, v in records[0].fields.items()
                    },
                }
                if records
                else None
            )
        except Exception as exc:  # noqa: BLE001 - the answer is the answer
            report["hypothesis_held"] = False
            report["records_read"] = 0
            report["read_error"] = f"{type(exc).__name__}: {exc}"

        reports.append(report)
finally:
    session.close()

out["sources"] = reports
out["both_payloads_on_file"] = all(r.get("payload_on_file") for r in reports)
out["both_hypotheses_held"] = all(r.get("hypothesis_held") for r in reports)
out["total_records_read"] = sum(int(r.get("records_read") or 0) for r in reports)

socket.socket = _real_socket  # type: ignore[misc,assignment]
out["network_attempts_during_this_phase"] = _NETWORK["attempts"]
print(json.dumps(out, sort_keys=True, default=str))
