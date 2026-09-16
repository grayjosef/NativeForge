"""Orchestration cycle identity (Gate 159D).

## A cycle is not a job, and its id must not be one

Gate 158's `job_id` identifies *one slot of work for one source*. A cycle
identifies *one pass of the loop*, covering every source. One cycle produces
many jobs, so reusing `job_id` as `cycle_id` would make the two concepts
indistinguishable the first time anything tried to count cycles.

They are digested from different tuples and this module never imports Gate 99B's
job digest, so the two cannot accidentally converge.

## What the identity is derived from

```text
cadence     how often the loop is meant to wake   e.g. hourly
version     the orchestration contract version
slot        the trigger slot the cycle serves     e.g. 2026-09-16T12
```

And explicitly NOT from:

```text
a PID                  two restarts of one slot would be two cycles
a worker id            two hosts serving one slot would be two cycles
a startup timestamp    every restart would re-serve every slot
a random UUID alone    nothing could ever be recognised as a repeat
```

Every one of those would make duplicate-trigger suppression impossible, because
suppression works by *recognising* that a slot has already been served. An
identity that cannot repeat cannot be recognised.

A random component is available for the OWNER id - see
`build_owner_id` - because an owner is deliberately the opposite: two processes
contending for one cycle must be distinguishable.

## Slot arithmetic

A slot is a floor, not a rounding. `2026-09-16T12:59:59Z` at hourly cadence is
slot `2026-09-16T12`, the same as `12:00:00`. That is what makes repeated
polling inside one window resolve to one cycle, and it mirrors the measurement
in doc 827: Gate 156's `next_run_at` is also independent of where in the window
the observer happens to look.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

SCHEMA_VERSION = "nf_source_collection_orchestration_identity_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: The orchestration contract version. It is part of the digest so that a
#: deliberate change to what a cycle MEANS produces new cycle ids rather than
#: silently reusing the ids of cycles that did something different.
ORCHESTRATION_VERSION = "gate159.v1"

#: Supported cadences, and the slot width each implies.
CADENCE_SECONDS: dict[str, int] = {
    "every_five_minutes": 300,
    "every_fifteen_minutes": 900,
    "hourly": 3600,
    "every_six_hours": 21600,
    "daily": 86400,
}

DEFAULT_CADENCE = "hourly"

#: The epoch every slot boundary is measured from. Fixed, so a slot index does
#: not depend on when the process started.
SLOT_EPOCH = datetime(2026, 1, 1, tzinfo=UTC)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _digest(*parts: Any) -> str:
    return hashlib.sha256(
        "|".join(str(part if part is not None else "") for part in parts).encode(
            "utf-8"
        )
    ).hexdigest()


def _as_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    text = str(value).strip()
    if not text:
        return None
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def normalize_cadence(cadence: Any) -> str:
    """Through the supported set. An unknown cadence does not silently widen."""
    text = str(cadence or "").strip()
    return text if text in CADENCE_SECONDS else DEFAULT_CADENCE


def cadence_seconds(cadence: Any) -> int:
    return CADENCE_SECONDS[normalize_cadence(cadence)]


def compute_slot_index(*, now: Any, cadence: Any = DEFAULT_CADENCE) -> int | None:
    """Which slot `now` falls in, counted from a fixed epoch.

    A floor, so every instant inside one window gives the same index.
    """
    moment = _as_datetime(now)
    if moment is None:
        return None
    width = cadence_seconds(cadence)
    elapsed = (moment - SLOT_EPOCH).total_seconds()
    # Python floor-divides toward negative infinity, which is what a slot
    # before the epoch should do rather than rounding toward it.
    return int(elapsed // width)


def slot_started_at(*, slot_index: int, cadence: Any = DEFAULT_CADENCE) -> datetime:
    """The instant a slot opened."""
    return SLOT_EPOCH + timedelta(seconds=cadence_seconds(cadence) * int(slot_index))


def build_slot_key(*, now: Any, cadence: Any = DEFAULT_CADENCE) -> str | None:
    """A readable name for the slot. Not an input to the digest.

    Kept out of the identity deliberately: if it were digested, a change to
    this formatting would silently change every cycle id and re-serve every
    slot as new work.
    """
    index = compute_slot_index(now=now, cadence=cadence)
    if index is None:
        return None
    started = slot_started_at(slot_index=index, cadence=cadence)
    return started.strftime("%Y-%m-%dT%H:%M:%SZ")


def build_cycle_id(
    *, slot_index: Any, cadence: Any = DEFAULT_CADENCE, version: str | None = None
) -> str:
    """Deterministic. The same slot is always the same cycle."""
    return _digest(
        "nf_orchestration_cycle",
        version or ORCHESTRATION_VERSION,
        normalize_cadence(cadence),
        slot_index,
    )


def build_owner_id(*, host: Any = None, pid: Any = None, nonce: Any = None) -> str:
    """The identity of a CONTENDER, which is the opposite problem.

    A cycle id must repeat so a duplicate can be recognised. An owner id must
    NOT repeat, or two processes racing for one cycle would look like one
    process and the loser would believe it had won.

    So this one does carry a nonce, and it is never part of a cycle id.
    """
    return "-".join(
        [
            str(host or "unknown-host"),
            str(pid or "0"),
            str(nonce or uuid.uuid4().hex[:12]),
        ]
    )


def build_orchestration_identity(
    *,
    now: Any,
    cadence: Any = DEFAULT_CADENCE,
    version: str | None = None,
) -> dict[str, Any]:
    """The identity of the cycle that serves the slot containing `now`."""
    resolved_cadence = normalize_cadence(cadence)
    slot_index = compute_slot_index(now=now, cadence=resolved_cadence)

    if slot_index is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "scope": CONTROLLED_SCOPE,
                "usable": False,
                "blocked_reasons": ["no_clock_supplied"],
                "cadence": resolved_cadence,
                "cadence_requested": str(cadence or "").strip() or None,
                "cadence_was_normalized": (
                    str(cadence or "").strip() != resolved_cadence
                ),
                "slot_index": None,
                "slot_key": None,
                "cycle_id": None,
                "source_monitoring_live": False,
            }
        )

    cycle_id = build_cycle_id(
        slot_index=slot_index, cadence=resolved_cadence, version=version
    )
    recomputed = build_cycle_id(
        slot_index=slot_index, cadence=resolved_cadence, version=version
    )
    started = slot_started_at(slot_index=slot_index, cadence=resolved_cadence)
    width = cadence_seconds(resolved_cadence)

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "usable": True,
            "blocked_reasons": [],
            "orchestration_version": version or ORCHESTRATION_VERSION,
            "cadence": resolved_cadence,
            "cadence_requested": str(cadence or "").strip() or None,
            "cadence_was_normalized": str(cadence or "").strip() != resolved_cadence,
            "cadence_seconds": width,
            "slot_index": slot_index,
            "slot_key": build_slot_key(now=now, cadence=resolved_cadence),
            "slot_started_at": started,
            "slot_ends_at": started + timedelta(seconds=width),
            "cycle_id": cycle_id,
            # Recomputed rather than asserted. A determinism claim that does
            # not recompute has the same shape as a count with no evidence.
            "determinism_proof": {
                "recomputed_cycle_id": recomputed,
                "matches": recomputed == cycle_id,
            },
            "derived_from": ["orchestration_version", "cadence", "slot_index"],
            "not_derived_from": [
                "pid",
                "worker_id",
                "owner_id",
                "startup_timestamp",
                "random_uuid",
                "wall_clock_position_within_the_slot",
            ],
            # Said explicitly, because a cycle id that equalled a job id would
            # make "how many cycles ran" and "how many jobs exist" the same
            # question.
            "is_a_collection_job_id": False,
            "implies_a_cycle_ran": False,
            "implies_source_approval": False,
            "source_monitoring_live": False,
        }
    )


def orchestration_identity_invariant_failures(identity: dict[str, Any]) -> list[str]:
    """Refuse an identity that is not deterministic, or claims something."""
    fails: list[str] = []

    if not identity.get("usable"):
        # An unusable identity must say why, and must not carry an id.
        if not identity.get("blocked_reasons"):
            fails.append("unusable_identity_named_no_reason")
        if identity.get("cycle_id"):
            fails.append("unusable_identity_still_produced_a_cycle_id")
        return sorted(set(fails))

    proof = identity.get("determinism_proof") or {}
    if not proof.get("matches"):
        fails.append("cycle_id_was_not_reproducible")
    if proof.get("recomputed_cycle_id") != identity.get("cycle_id"):
        fails.append("recomputed_cycle_id_differs_from_the_reported_one")

    cycle_id = str(identity.get("cycle_id") or "")
    if len(cycle_id) != 64:
        fails.append("cycle_id_is_not_a_sha256_digest")

    if identity.get("slot_index") is None:
        fails.append("usable_identity_without_a_slot_index")

    if str(identity.get("cadence")) not in CADENCE_SECONDS:
        fails.append(f"cadence_outside_vocabulary:{identity.get('cadence')}")

    for claim in (
        "is_a_collection_job_id",
        "implies_a_cycle_ran",
        "implies_source_approval",
        "source_monitoring_live",
    ):
        if identity.get(claim):
            fails.append(f"identity_claimed:{claim}")

    return sorted(set(fails))
