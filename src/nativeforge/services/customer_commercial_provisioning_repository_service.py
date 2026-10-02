"""Persistence for commercial intent / provisioning requests."""

from __future__ import annotations

import datetime as dt
import json
import uuid
from typing import Any

import sqlalchemy as sa

TABLE = "nf_commercial_provisioning_requests"
SCHEMA_VERSION = "nf_commercial_provisioning_repository_v1"


def _json_dumps(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def insert_request(
    connection: sa.engine.Connection,
    *,
    identity_id: str,
    lifecycle_status: str,
    product_code: str,
    requested_org_display_name: str | None,
    requested_org_hint: str | None = None,
    organization_id: str | None = None,
    operator_actor: str | None = None,
    blocked_reasons: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    is_demo: bool = False,
    request_id: str | None = None,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    moment = now or dt.datetime.now(dt.UTC)
    rid = request_id or str(uuid.uuid4())
    connection.execute(
        sa.text(
            f"INSERT INTO {TABLE} "
            f"(request_id, identity_id, lifecycle_status, product_code, "
            f"requested_org_display_name, requested_org_hint, organization_id, "
            f"operator_actor, blocked_reasons_json, metadata_json, is_demo, "
            f"created_at, updated_at) "
            f"VALUES (:rid, :iid, :status, :product, :name, :hint, :oid, "
            f":op, :blocked, :meta, :demo, :created, :updated)"
        ),
        {
            "rid": rid,
            "iid": str(identity_id),
            "status": lifecycle_status,
            "product": product_code,
            "name": requested_org_display_name,
            "hint": requested_org_hint,
            "oid": organization_id,
            "op": operator_actor,
            "blocked": _json_dumps(sorted(set(blocked_reasons or []))),
            "meta": _json_dumps(metadata or {}),
            "demo": bool(is_demo),
            "created": moment,
            "updated": moment,
        },
    )
    return load_request(connection, request_id=rid) or {}


def update_request(
    connection: sa.engine.Connection,
    *,
    request_id: str,
    lifecycle_status: str | None = None,
    organization_id: str | None = None,
    operator_actor: str | None = None,
    blocked_reasons: list[str] | None = None,
    metadata: dict[str, Any] | None = None,
    merge_metadata: bool = True,
    now: dt.datetime | None = None,
) -> dict[str, Any]:
    existing = load_request(connection, request_id=request_id)
    if not existing:
        return {}
    moment = now or dt.datetime.now(dt.UTC)
    status = lifecycle_status or existing["lifecycle_status"]
    oid = organization_id if organization_id is not None else existing.get("organization_id")
    op = operator_actor if operator_actor is not None else existing.get("operator_actor")
    blocked = blocked_reasons if blocked_reasons is not None else existing.get("blocked_reasons") or []
    meta = dict(existing.get("metadata") or {})
    if metadata:
        if merge_metadata:
            meta.update(metadata)
        else:
            meta = metadata
    connection.execute(
        sa.text(
            f"UPDATE {TABLE} SET lifecycle_status = :status, organization_id = :oid, "
            f"operator_actor = :op, blocked_reasons_json = :blocked, "
            f"metadata_json = :meta, updated_at = :updated "
            f"WHERE request_id = :rid"
        ),
        {
            "rid": request_id,
            "status": status,
            "oid": oid,
            "op": op,
            "blocked": _json_dumps(sorted(set(blocked))),
            "meta": _json_dumps(meta),
            "updated": moment,
        },
    )
    return load_request(connection, request_id=request_id) or {}


def load_request(
    connection: sa.engine.Connection, *, request_id: str
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            sa.text(f"SELECT * FROM {TABLE} WHERE request_id = :rid"),
            {"rid": request_id},
        )
        .mappings()
        .first()
    )
    return _row_to_dict(row) if row else None


def load_latest_for_identity(
    connection: sa.engine.Connection, *, identity_id: str
) -> dict[str, Any] | None:
    row = (
        connection.execute(
            sa.text(
                f"SELECT * FROM {TABLE} WHERE identity_id = :iid "
                f"ORDER BY updated_at DESC LIMIT 1"
            ),
            {"iid": str(identity_id)},
        )
        .mappings()
        .first()
    )
    return _row_to_dict(row) if row else None


def _row_to_dict(row: sa.RowMapping) -> dict[str, Any]:
    blocked = json.loads(row["blocked_reasons_json"] or "[]")
    meta = json.loads(row["metadata_json"] or "{}")
    return {
        "schema_version": SCHEMA_VERSION,
        "request_id": row["request_id"],
        "identity_id": row["identity_id"],
        "lifecycle_status": row["lifecycle_status"],
        "product_code": row["product_code"],
        "requested_org_display_name": row["requested_org_display_name"],
        "requested_org_hint": row["requested_org_hint"],
        "organization_id": row["organization_id"],
        "operator_actor": row["operator_actor"],
        "blocked_reasons": list(blocked),
        "metadata": meta,
        "is_demo": bool(row["is_demo"]),
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
