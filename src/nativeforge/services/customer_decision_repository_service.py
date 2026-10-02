"""Persist Gate 179 customer decisions (0065 tables)."""

from __future__ import annotations

import datetime as dt
import hashlib
from typing import Any

import sqlalchemy as sa

from nativeforge.services.customer_decision_service import (
    build_decision_id,
    decision_invariant_failures,
)
from nativeforge.services.customer_repository_service import DECISIONS, HISTORY

SCHEMA_VERSION = "nf_customer_decision_repository_v1"


def _history_id(*, organization_id: str, canonical_id: str, superseded_at: str) -> str:
    raw = f"{organization_id}|{canonical_id}|{superseded_at}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def load_current_decision(
    connection: sa.engine.Connection,
    *,
    organization_id: str,
    canonical_id: str,
) -> dict[str, Any] | None:
    row = connection.execute(
        sa.text(
            f"SELECT organization_id, canonical_id, decision_state, previous_state, "
            f"actor_id, decided_at, reason, model_version "
            f"FROM {DECISIONS} WHERE organization_id = :org AND canonical_id = :cid"
        ),
        {"org": organization_id, "cid": canonical_id},
    ).mappings().first()
    return dict(row) if row else None


def persist_decision(
    connection: sa.engine.Connection,
    *,
    decision: dict[str, Any],
    previous: dict[str, Any] | None,
    is_demo: bool,
) -> dict[str, Any]:
    failures = decision_invariant_failures(decision)
    if failures:
        return {"persisted": False, "failures": failures}

    org = str(decision["organization_id"])
    cid = str(decision["canonical_id"])
    now = dt.datetime.now(dt.UTC)

    if previous is not None:
        hist_id = _history_id(
            organization_id=org,
            canonical_id=cid,
            superseded_at=str(previous.get("decided_at") or now.isoformat()),
        )
        connection.execute(
            sa.text(
                f"INSERT INTO {HISTORY} "
                f"(history_id, organization_id, canonical_id, decision_state, "
                f"previous_state, actor_id, decided_at, reason, superseded_at, "
                f"is_demo, model_version) "
                f"VALUES (:hid, :org, :cid, :state, :prev, :actor, :at, :reason, "
                f":sup_at, :demo, :mv)"
            ),
            {
                "hid": hist_id,
                "org": org,
                "cid": cid,
                "state": previous.get("decision_state"),
                "prev": previous.get("previous_state"),
                "actor": previous.get("actor_id"),
                "at": previous.get("decided_at"),
                "reason": previous.get("reason"),
                "sup_at": now,
                # A real bool, not 1/0. `is_demo` is `boolean` in PostgreSQL,
                # and psycopg binds a Python int as smallint, so the integer
                # form raises DatatypeMismatch there while SQLite accepts it
                # silently. The suite runs on SQLite, so this reached
                # controlled-live and 500'd the first substantive demo write
                # that got past the entitlement gate.
                "demo": bool(is_demo),
                "mv": previous.get("model_version") or decision.get("model_version"),
            },
        )

    connection.execute(
        sa.text(
            f"INSERT INTO {DECISIONS} "
            f"(organization_id, canonical_id, decision_state, previous_state, "
            f"actor_id, decided_at, reason, is_demo, model_version) "
            f"VALUES (:org, :cid, :state, :prev, :actor, :at, :reason, :demo, :mv) "
            f"ON CONFLICT(organization_id, canonical_id) DO UPDATE SET "
            f"decision_state = excluded.decision_state, "
            f"previous_state = excluded.previous_state, "
            f"actor_id = excluded.actor_id, "
            f"decided_at = excluded.decided_at, "
            f"reason = excluded.reason, "
            f"is_demo = excluded.is_demo, "
            f"model_version = excluded.model_version"
        ),
        {
            "org": org,
            "cid": cid,
            "state": decision.get("decision_state"),
            "prev": decision.get("previous_state"),
            "actor": decision.get("actor_id"),
            "at": decision.get("decided_at"),
            "reason": decision.get("reason"),
            # See the history insert above: bool, not 1/0.
            "demo": bool(is_demo),
            "mv": decision.get("model_version"),
        },
    )
    return {
        "persisted": True,
        "decision_id": build_decision_id(
            organization_id=org, canonical_id=cid
        ),
    }
