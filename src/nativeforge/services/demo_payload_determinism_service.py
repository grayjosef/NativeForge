"""Deterministic demo payload generation (Gate 83B-B).

Makes ``frontend/src/demo/sc_customer_demo.json`` reproducible from its inputs,
so a diff of that file shows what a change actually did.

## What made it nondeterministic

Three causes, found by diffing two consecutive builds leaf by leaf and
snapshotting every mutable module global around a build:

1. **Wall clock.** Leaf services call ``datetime.now(UTC)`` directly. There is
   no shared ``now()`` helper; 41 loaded modules expose the class.
2. **Randomness.** ``uuid.uuid4().hex[:8]`` supplies nonces, event ids and id
   suffixes across 37 loaded modules. (``secrets``, ``random`` and ``time`` are
   not used on this path at all.)
3. **Module-global accumulators.** Thirty services hold a module-level
   ``_AUDIT`` list that is appended to on every call and sliced into the payload
   as ``audit_refs``. Every one of them *doubles* per build, so the payload
   depended on how many times the process had already built one — and the lists
   grow without bound in any long-running process.

The third is why freezing the clock alone would not have worked.

## How determinism works

:func:`deterministic_demo_generation` is a context manager that, for the
duration of one generation:

* replaces ``mod.datetime`` with a fixed-``now()`` subclass on every loaded
  ``nativeforge.`` module where that attribute is the real class;
* replaces ``mod.uuid`` with a shim whose ``uuid4()`` is derived from the seed
  and a call counter rather than from entropy;
* clears every module-level ``_AUDIT`` list so a generation depends on its
  inputs and not on process history;
* restores all three exactly on exit, including on exception.

Patching module attributes in a scoped context was chosen over threading a
seed/clock parameter through 40+ services: that would put a demo-only concern
into the runtime API of services used elsewhere, and a missed service would fail
silently by simply continuing to churn.

## Runtime impact

**None, by construction.** Nothing at runtime enters this context — it is used
only by the demo generator and the determinism verifier. A test asserts the real
``datetime`` and ``uuid`` are restored afterwards, and that
``datetime.now()`` moves again once the context exits.

The dynamic (real clock, real entropy) path remains the default everywhere else;
determinism is opt-in and applies only to the committed demo artifact.

This module makes no product claim, touches no eligibility logic, and performs
no I/O.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import tempfile
import uuid as _real_uuid
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from types import ModuleType
from typing import Any

SCHEMA_VERSION = "nf_demo_payload_determinism_v1"

# Captured at import so the patch loop compares against a stable reference.
#
# This module is itself a `nativeforge.` module exposing `datetime`, so an
# earlier version patched *itself* partway through the scan - which rebound the
# global the loop was comparing against, and every module visited afterwards
# silently failed the identity check. Only a handful of modules ended up frozen
# and the payload kept churning. Hence a captured constant plus an explicit
# self-exclusion below.
_REAL_DATETIME = datetime
_REAL_UUID_MODULE = _real_uuid

# Pinned generation instant for the committed demo payload. Changing it changes
# every timestamp in the artifact, so it is a deliberate, reviewable edit.
DEFAULT_GENERATED_AT = "2026-01-01T00:00:00+00:00"
DEFAULT_SEED = "nativeforge-sc-customer-demo"

DEFAULT_ID_NAMESPACE = "demo-id"
DEFAULT_NONCE_NAMESPACE = "demo-nonce"

# Fixed scratch directory name. Must be stable, not random: at least one
# redirected path is embedded in the payload.
SCRATCH_DIR_NAME = "nativeforge-demo-determinism"

# Only modules under this prefix are patched. Standard library and third-party
# modules keep their real primitives.
PATCH_PREFIX = "nativeforge."

# Module-level accumulator names reset per generation. Discovered empirically:
# thirty services use `_AUDIT` and every one of them doubles across a build.
ACCUMULATOR_ATTRS: tuple[str, ...] = ("_AUDIT",)

# Path constants redirected to a fresh temporary directory for the duration of
# a generation.
#
# Freezing the clock and identity surfaced this: one surface runs a real SQLite
# lifecycle smoke that INSERTs a row keyed by a uuid-derived id. With ids no
# longer random, a second generation reproduced the same id and collided with
# the row the first one had left behind - a UNIQUE constraint failure.
#
# The collision was the symptom; the finding is that generation had on-disk side
# effects and its output depended on accumulated database state. Redirecting the
# path makes each generation start from an empty database and stops it writing
# into a persistent artifact at all.
REDIRECTED_PATH_ATTRS: tuple[tuple[str, str], ...] = (
    (
        "nativeforge.services.persistence_approval_assembler_service",
        "_DEMO_LIFECYCLE_DB",
    ),
    # Generation also *writes* into artifacts/ - a no-secret unlock log, an
    # auth0 smoke record, an evidence blob and a placeholder, every run. One of
    # those directories had accumulated 4,379 files.
    #
    # That accumulation was not merely untidy: with the clock and identity
    # frozen, three separate processes still produced three different payloads,
    # because output depended on what previous runs had left on disk. Pointing
    # these at a scratch directory makes a generation a pure function of the
    # repository, and stops it growing artifacts/ at all.
    (
        "nativeforge.services.validated_persistent_evidence_adapter_service",
        "DEFAULT_BLOB_ROOT",
    ),
    (
        "nativeforge.services.auth0_mode_b_live_unlock_service",
        "DEFAULT_LOG_DIR",
    ),
    (
        "nativeforge.services.auth0_validation_smoke_service",
        "DEFAULT_OUT",
    ),
)


def _parse_instant(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


class DeterministicContext:
    """Seeded clock and identity source for one generation."""

    def __init__(
        self,
        *,
        seed: str = DEFAULT_SEED,
        generated_at: str = DEFAULT_GENERATED_AT,
        id_namespace: str = DEFAULT_ID_NAMESPACE,
        nonce_namespace: str = DEFAULT_NONCE_NAMESPACE,
    ) -> None:
        self.seed = seed
        self.generated_at = generated_at
        self.id_namespace = id_namespace
        self.nonce_namespace = nonce_namespace
        self.instant = _parse_instant(generated_at)
        self._counter = 0

    # -- clock -----------------------------------------------------------

    def now(self, tz: Any = None) -> datetime:
        """Fixed instant. Honours a requested tz so callers behave normally."""
        return self.instant.astimezone(tz) if tz is not None else self.instant

    # -- identity --------------------------------------------------------

    def next_id(self, namespace: str | None = None) -> str:
        """Counter-derived hex. Stable for a seed, distinct across calls.

        The counter is included so two calls never collide, and the namespace is
        included so the same counter value under different namespaces cannot.
        """
        self._counter += 1
        material = f"{self.seed}::{namespace or self.id_namespace}::{self._counter}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def next_uuid(self) -> _real_uuid.UUID:
        return _real_uuid.UUID(hex=self.next_id(self.id_namespace)[:32])

    def stable_key(self, *parts: Any) -> str:
        """Content-derived id for callers that have natural key material.

        Unlike :meth:`next_id` this does not advance the counter, so the same
        inputs always give the same id regardless of call order.
        """
        material = f"{self.seed}::" + "::".join(str(p) for p in parts)
        return hashlib.sha256(material.encode("utf-8")).hexdigest()

    def describe(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "seed": self.seed,
            "generated_at": self.generated_at,
            "id_namespace": self.id_namespace,
            "nonce_namespace": self.nonce_namespace,
            "ids_issued": self._counter,
            "deterministic": True,
        }


def stable_sorted(items: list[Any], *, key: Any = None) -> list[Any]:
    """Ordering helper for callers assembling sets into lists.

    Python's sort is stable, so this only guarantees the *input* is ordered;
    the point is to give callers one obvious place to reach for rather than
    leaving set iteration order in a payload.
    """
    return sorted(items, key=key) if key else sorted(items, key=repr)


def _nativeforge_modules() -> list[tuple[str, ModuleType]]:
    """Loaded nativeforge modules, excluding this one.

    Self-exclusion is deliberate: patching this module's own ``datetime`` would
    rebind the reference the patch loop depends on.
    """
    return [
        (name, mod)
        for name, mod in list(sys.modules.items())
        if name.startswith(PATCH_PREFIX) and mod is not None and name != __name__
    ]


def _make_frozen_datetime(ctx: DeterministicContext) -> type[datetime]:
    instant = ctx.instant

    class _FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz: Any = None) -> datetime:  # type: ignore[override]
            return instant.astimezone(tz) if tz is not None else instant

        @classmethod
        def utcnow(cls) -> datetime:  # type: ignore[override]
            return instant.replace(tzinfo=None)

        @classmethod
        def today(cls) -> datetime:  # type: ignore[override]
            return instant

    return _FrozenDatetime


class _SeededUUIDModule:
    """Stands in for the ``uuid`` module during a deterministic generation.

    Only the surface the services actually use is overridden; everything else
    falls through to the real module, so a service reaching for
    ``uuid.UUID`` still gets the real class.
    """

    def __init__(self, ctx: DeterministicContext) -> None:
        self._ctx = ctx

    def uuid4(self) -> _real_uuid.UUID:
        return self._ctx.next_uuid()

    def __getattr__(self, name: str) -> Any:
        return getattr(_real_uuid, name)


@contextmanager
def deterministic_demo_generation(
    *,
    seed: str = DEFAULT_SEED,
    generated_at: str = DEFAULT_GENERATED_AT,
) -> Iterator[DeterministicContext]:
    """Freeze clock and identity, reset accumulators, restore on exit.

    Entered only by the demo payload generator and the determinism verifier.
    """
    ctx = DeterministicContext(seed=seed, generated_at=generated_at)
    frozen = _make_frozen_datetime(ctx)
    fake_uuid = _SeededUUIDModule(ctx)

    patched_datetime: list[ModuleType] = []
    patched_uuid: list[ModuleType] = []
    saved_accumulators: list[tuple[ModuleType, str, list[Any]]] = []
    saved_paths: list[tuple[ModuleType, str, Any]] = []

    # A *fixed* scratch root, not mkdtemp: one of these redirected paths is
    # embedded in the payload (`no_secret_log_path`), so a random directory name
    # would reintroduce the very churn this context exists to remove.
    # Generation is sequential, so a stable shared name is safe here.
    scratch = Path(tempfile.gettempdir()) / SCRATCH_DIR_NAME
    shutil.rmtree(scratch, ignore_errors=True)
    scratch.mkdir(parents=True, exist_ok=True)
    tmpdir = str(scratch)
    for module_name, attr in REDIRECTED_PATH_ATTRS:
        mod = sys.modules.get(module_name)
        if mod is None:
            continue
        original = getattr(mod, attr, None)
        if original is None:
            continue
        saved_paths.append((mod, attr, original))
        setattr(mod, attr, Path(tmpdir) / Path(str(original)).name)

    for _name, mod in _nativeforge_modules():
        if getattr(mod, "datetime", None) is _REAL_DATETIME:
            mod.datetime = frozen  # type: ignore[attr-defined]
            patched_datetime.append(mod)
        if getattr(mod, "uuid", None) is _REAL_UUID_MODULE:
            mod.uuid = fake_uuid  # type: ignore[assignment]
            patched_uuid.append(mod)
        for attr in ACCUMULATOR_ATTRS:
            value = getattr(mod, attr, None)
            if isinstance(value, list):
                # Keep the same list object so any closure over it stays valid;
                # clear it so this generation starts from nothing.
                saved_accumulators.append((mod, attr, list(value)))
                value.clear()

    try:
        yield ctx
    finally:
        for mod in patched_datetime:
            mod.datetime = _REAL_DATETIME  # type: ignore[attr-defined]
        for mod in patched_uuid:
            mod.uuid = _REAL_UUID_MODULE  # type: ignore[assignment]
        for mod, attr, original in saved_accumulators:
            current = getattr(mod, attr, None)
            if isinstance(current, list):
                current.clear()
                current.extend(original)
        for mod, attr, original_path in saved_paths:
            setattr(mod, attr, original_path)
        shutil.rmtree(tmpdir, ignore_errors=True)


def determinism_invariant_failures(described: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if described.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if not described.get("seed"):
        fails.append("missing_seed")
    if not described.get("generated_at"):
        fails.append("missing_generated_at")
    if described.get("deterministic") is not True:
        fails.append("context_not_marked_deterministic")
    try:
        _parse_instant(str(described.get("generated_at")))
    except (TypeError, ValueError):
        fails.append("generated_at_is_not_an_instant")
    return fails
