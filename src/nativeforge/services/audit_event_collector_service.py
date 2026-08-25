"""Request-scoped audit event collector (Gate 84B).

Replaces the module-level ``_AUDIT`` lists that thirty services used to keep.

Those lists lived for the life of the process, so a service's output depended on
what earlier calls had appended: ``audit_refs`` is a tail slice, and on a warm
process it returned other callers' events. Gate 83B measured every one of the
thirty *doubling* per demo payload build, and had to clear them all before each
generation to make the payload reproducible. That fixed the payload, not the
design.

The fix is ownership. A collector instance owns its events, and **the caller
defines the request boundary**: a caller that wants one audit trail across three
service calls passes one collector to all three. Nothing is shared implicitly.

Design rules this module holds to:

* no module-level mutable state of any kind - not a list, not a registry, not a
  "current" collector;
* no global singleton and no implicit default instance;
* cheap enough to instantiate per call, simple enough to use in thirty services;
* reads never mutate - :meth:`snapshot` and :meth:`tail` copy.

This module records events. It does not persist them: that is
``security_audit_sink_service`` and ``repositories/audit_events``, neither of
which is touched here.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from typing import Any

SCHEMA_VERSION = "nf_audit_event_collector_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


class AuditEventCollector:
    """Owns the audit events emitted during one logical operation.

    Instantiate per call. Pass it down to helpers explicitly - never reach for
    a shared instance, because a shared instance is the bug this replaces.
    """

    __slots__ = ("_events", "_event_id_factory")

    def __init__(
        self,
        *,
        event_id_factory: Callable[[int, str], str] | None = None,
    ) -> None:
        # Instance-owned. There is deliberately no class-level container.
        self._events: list[dict[str, Any]] = []
        # Supplied by the caller when ids must be reproducible - e.g. the
        # deterministic demo generation context. Never derived from a global
        # clock or entropy source here.
        self._event_id_factory = event_id_factory

    # -- writing ---------------------------------------------------------

    def record(
        self, event: str, detail: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Record an event and return it.

        The returned dict is the stored one, so a caller can read the id it was
        given without a second lookup.
        """
        entry: dict[str, Any] = {"event": str(event)}
        if detail:
            entry.update(detail)
        if self._event_id_factory is not None:
            entry["event_id"] = self._event_id_factory(len(self._events), str(event))
        self._events.append(entry)
        return entry

    def add(self, entry: dict[str, Any]) -> dict[str, Any]:
        """Record an already-built event dict."""
        stored = dict(entry)
        self._events.append(stored)
        return stored

    # -- reading (never mutates) -----------------------------------------

    def snapshot(self) -> tuple[dict[str, Any], ...]:
        """Immutable view of every event recorded so far."""
        return tuple(dict(e) for e in self._events)

    def tail(self, count: int) -> list[dict[str, Any]]:
        """Last ``count`` events, oldest first. Does not mutate."""
        if count <= 0:
            return []
        return [dict(e) for e in self._events[-count:]]

    def event_names(self, count: int | None = None) -> list[str]:
        """Event names, optionally just the last ``count``.

        This is the shape ``audit_refs`` has always had.
        """
        events = self._events if count is None else self._events[-max(count, 0):]
        return [str(e.get("event")) for e in events]

    def has_event(self, *names: str) -> bool:
        wanted = {str(n) for n in names}
        return any(str(e.get("event")) in wanted for e in self._events)

    def clear(self) -> None:
        """Reset *this* collector. Affects no other instance."""
        self._events.clear()

    def __len__(self) -> int:
        return len(self._events)

    def __iter__(self) -> Iterator[dict[str, Any]]:
        return iter(self.snapshot())

    def __bool__(self) -> bool:
        # Explicit: an empty collector is still a usable collector, so truthiness
        # follows event count rather than instance existence.
        return bool(self._events)

    def describe(self) -> dict[str, Any]:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "event_count": len(self._events),
                "event_names": self.event_names(),
                "request_scoped": True,
                "module_level_state": False,
            }
        )


class NoopAuditCollector(AuditEventCollector):
    """Accepts events and keeps none.

    For callers that must satisfy the interface but genuinely do not want a
    trail. It is *not* the default anywhere: silence has to be chosen, so an
    audit trail is never lost by accident.
    """

    __slots__ = ()

    def record(
        self, event: str, detail: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        entry: dict[str, Any] = {"event": str(event)}
        if detail:
            entry.update(detail)
        return entry

    def add(self, entry: dict[str, Any]) -> dict[str, Any]:
        return dict(entry)


def new_collector(
    collector: AuditEventCollector | None = None,
    *,
    event_id_factory: Callable[[int, str], str] | None = None,
) -> AuditEventCollector:
    """Return the caller's collector, or a fresh one.

    The one-line idiom every patched service uses::

        collector = new_collector(collector)

    A caller that passes nothing gets an isolated collector for that call. A
    caller that passes one owns the request boundary spanning several calls.
    """
    if collector is not None:
        return collector
    return AuditEventCollector(event_id_factory=event_id_factory)


def collector_invariant_failures(described: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if described.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if described.get("request_scoped") is not True:
        fails.append("collector_not_request_scoped")
    if described.get("module_level_state") is not False:
        fails.append("forbidden_claim:module_level_state")
    count = described.get("event_count")
    names = described.get("event_names")
    if not isinstance(count, int) or count < 0:
        fails.append("event_count_invalid")
    if not isinstance(names, list) or len(names) != count:
        fails.append("event_names_disagree_with_count")
    return fails
