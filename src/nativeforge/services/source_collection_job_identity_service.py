"""Collection job identity (Gate 158D).

## This composes Gate 99B. It does not reimplement it.

Gate 99B already has deterministic identity, and Gate 158's survey measured it
rather than assuming:

```text
same source + same slot, twice     -> same id          True
same source, different slot        -> different id     True
idempotency key is mode-independent                    True
neither reads a clock, a PID or a random UUID          True
```

So `build_job_identity` calls `build_job_id` and `build_idempotency_key` and
adds only what the store needs on top: a readable `schedule_key`, and a
`determinism_proof` that re-derives the id a second time and compares.

A second sha256 here would be a second source of truth for the same fact, which
is how two parts of a system come to disagree about whether two jobs are the
same job. Gate 156 composed the job model, Gate 157 composed the worker
contracts, and this is the same discipline applied to identity.

## What a slot is

A job identifies a *slot of work*, not a source:

```text
source S, due 2026-09-20   one job
source S, due 2026-09-27   a different job
source S, no cadence       ONE job, forever
```

That last line is what bounds the store. The survey measured it: a source with
no `check_interval_days` has `scheduled_for = None`, which digests to a single
perpetual slot. Repeated scheduler cycles re-enqueue that same id and the unique
index refuses the duplicate, so 177 refused sources hold the store at 177 rows
instead of adding 177 every cycle.

## Identity is not permission

An id can be computed for a source nobody approved, whose terms nobody read,
for which no collector exists. That is intentional: the campaign needs to count
how long that work has been waiting. Computing an identity is not deciding the
work may run, and this module reads no allowlist, opens no connection and
contacts nothing.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.source_scheduler_job_model_service import (
    DEFAULT_EXECUTION_MODE as GATE_99B_DEFAULT_EXECUTION_MODE,
)
from nativeforge.services.source_scheduler_job_model_service import (
    DEFAULT_JOB_TYPE as GATE_99B_DEFAULT_JOB_TYPE,
)
from nativeforge.services.source_scheduler_job_model_service import (
    EXECUTION_MODES,
    JOB_TYPES,
    build_idempotency_key,
    build_job_id,
)

SCHEMA_VERSION = "nf_source_collection_job_identity_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: Gate 158 enqueues one kind of work, and names it the same way every time.
#: A varying job_type would change the digest and break deduplication across
#: cycles, which is the whole point of the identity.
#:
#: These are IMPORTED from Gate 99B rather than spelled again here. Gate 158
#: measured why that matters: Gate 156 passes `job_type="scheduled_check"`,
#: which is not in `JOB_TYPES`, so Gate 99B normalizes it to `"source_check"`
#: and digests that instead. An identity service with its own copy of the word
#: produced a different id in all four measured cases - ids the store would
#: have held and the scheduler would never have reported.
DEFAULT_JOB_TYPE = GATE_99B_DEFAULT_JOB_TYPE

DEFAULT_EXECUTION_MODE = GATE_99B_DEFAULT_EXECUTION_MODE


#: The label for a source with no cadence: one slot that never advances.
PERPETUAL_SLOT = "perpetual"

#: Where the digest comes from. Named so a reader can go check.
COMPOSED_FROM = (
    "source_scheduler_job_model_service.build_job_id",
    "source_scheduler_job_model_service.build_idempotency_key",
)


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _normalize(value: Any, vocabulary: frozenset[str], *, fallback: str) -> str:
    """Gate 99B's own normalization, over Gate 99B's own vocabulary.

    Mirrors `source_scheduler_job_model_service._norm`, which is private. The
    vocabulary is imported rather than restated, so the set can never drift;
    only this two-line membership test is repeated.
    """
    text = str(value or "").strip()
    return text if text in vocabulary else fallback


def build_schedule_key(scheduled_for: Any) -> str:
    """A readable name for the slot. Never an input to the digest.

    This exists so an operator can see *which* window a row is for without
    decoding a sha256. It is deliberately not part of the identity: if it were,
    a change to this formatting would silently change every job id and
    re-enqueue the whole store as new work.
    """
    text = str(scheduled_for or "").strip()
    if not text:
        return PERPETUAL_SLOT
    return text


def build_job_identity(
    *,
    source_id: Any,
    scheduled_for: Any = None,
    collector_id: Any = None,
    job_type: str = DEFAULT_JOB_TYPE,
    execution_mode: str = DEFAULT_EXECUTION_MODE,
) -> dict[str, Any]:
    """The identity of one slot of collection work.

    Deterministic: the same arguments always give the same ids, and the returned
    `determinism_proof` says so by recomputing rather than by asserting.
    """
    # Passed to the digest EXACTLY as given. Gate 99B does not strip it, and a
    # `.strip()` here was measured producing a different id for a padded
    # source_id than the id the scheduler reports - a second normalization of
    # the same fact, which is what this module exists not to do.
    source = source_id
    present = bool(str(source_id or "").strip())

    # Normalized the way Gate 99B will normalize it anyway. Doing it here means
    # the id this service reports is the id Gate 99B digests, and a caller that
    # passed an out-of-vocabulary word is told so rather than silently given a
    # digest of a different word.
    resolved_job_type = _normalize(job_type, JOB_TYPES, fallback=DEFAULT_JOB_TYPE)
    resolved_mode = _normalize(
        execution_mode, EXECUTION_MODES, fallback=DEFAULT_EXECUTION_MODE
    )

    job_id = build_job_id(
        source_id=source,
        collector_id=collector_id,
        job_type=resolved_job_type,
        scheduled_for=scheduled_for,
        execution_mode=resolved_mode,
    )
    idempotency_key = build_idempotency_key(
        source_id=source,
        collector_id=collector_id,
        job_type=resolved_job_type,
        scheduled_for=scheduled_for,
    )

    # Recomputed, not assumed. A determinism claim that does not recompute is
    # the same shape as a count with no evidence behind it.
    recomputed = build_job_id(
        source_id=source,
        collector_id=collector_id,
        job_type=resolved_job_type,
        scheduled_for=scheduled_for,
        execution_mode=resolved_mode,
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "source_id": source if source is None else str(source),
            "job_id": job_id,
            "idempotency_key": idempotency_key,
            "schedule_key": build_schedule_key(scheduled_for),
            "scheduled_for": scheduled_for if scheduled_for is None else str(
                scheduled_for
            ),
            "job_type": resolved_job_type,
            "execution_mode": resolved_mode,
            # Surfaced rather than swallowed. This is the field that would have
            # caught Gate 156 passing a word outside the vocabulary.
            "job_type_requested": str(job_type or "").strip() or None,
            "job_type_was_normalized": (
                str(job_type or "").strip() != resolved_job_type
            ),
            "execution_mode_requested": str(execution_mode or "").strip() or None,
            "execution_mode_was_normalized": (
                str(execution_mode or "").strip() != resolved_mode
            ),
            # The live mode never reaches a digest from here. Gate 99B would
            # downgrade it and digest the downgrade; this service normalizes
            # only against the vocabulary, so a caller asking for live gets a
            # live id that no worker in this campaign can act on. Say so.
            "requested_a_live_mode": str(execution_mode or "").strip()
            == "live_collection",
            "collector_id": collector_id if collector_id is None else str(collector_id),
            "is_perpetual_slot": not str(scheduled_for or "").strip(),
            "determinism_proof": {
                "recomputed_job_id": recomputed,
                "matches": recomputed == job_id,
            },
            "composed_from": list(COMPOSED_FROM),
            # Identity is not permission. Computing an id for a source nobody
            # approved is how the backlog gets counted.
            "implies_source_approval": False,
            "implies_collection_permitted": False,
            "source_monitoring_live": False,
            "usable_as_input": present,
        }
    )


def identity_invariant_failures(identity: dict[str, Any]) -> list[str]:
    """Refuse an identity that is not deterministic, or claims a permission."""
    fails: list[str] = []

    proof = identity.get("determinism_proof") or {}
    if not proof.get("matches"):
        fails.append("job_id_was_not_reproducible")
    if proof.get("recomputed_job_id") != identity.get("job_id"):
        fails.append("recomputed_job_id_differs_from_the_reported_one")

    for field in ("job_id", "idempotency_key", "schedule_key"):
        if not str(identity.get(field) or "").strip():
            fails.append(f"identity_field_missing:{field}")

    # A sha256 hexdigest, or the composition is not what it says it is.
    for field in ("job_id", "idempotency_key"):
        value = str(identity.get(field) or "")
        if value and len(value) != 64:
            fails.append(f"identity_field_is_not_a_sha256_digest:{field}")

    if identity.get("job_id") == identity.get("idempotency_key"):
        # They digest different tuples, so equality means one of the two calls
        # was wired to the wrong arguments.
        fails.append("job_id_and_idempotency_key_are_identical")

    for claim in (
        "implies_source_approval",
        "implies_collection_permitted",
        "source_monitoring_live",
    ):
        if identity.get(claim):
            fails.append(f"identity_claimed:{claim}")

    return sorted(set(fails))
