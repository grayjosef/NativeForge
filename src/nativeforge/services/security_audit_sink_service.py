"""Security audit sink (Gate 68A).

Services across the codebase return modeled audit events to their callers, and
the callers drop them. This module is the thing that collects them, decides
which ones the current schema can honestly store, and refuses the rest loudly.

It is step 4 of doc 391's plan, and it is deliberately the only step taken here:
services stay pure functions that return events, and the sink is injected at the
boundary. Threading a database session into the service layer would be the
easier change and the wrong one — it would make every trust decision in the
product depend on having a session.

**The refusal that matters.** ``cross_org_access_attempt`` cannot be stored by
the current schema at all. The event concerns at least three organizations — the
actor's, the target's, and the one the caller claimed — and
``nf_audit_events.organization_id`` is ``NOT NULL`` and is the RLS predicate, so
there is exactly one slot. Writing the actor's org hides the event from the
tenant that was attacked; writing the target's org attributes the attack to the
victim. Both are worse than not writing it, so this sink refuses until migration
0028 adds the columns. See docs 401 and 408.

**Nothing is silently dropped.** Every refusal appears in ``events_refused``
with a reason. A security event that vanishes is worse than a request that
fails, because nobody finds out.

Default mode is ``modeled`` — classify and account, write nothing. A live
repository write is possible only for currently-representable events and only
when a caller explicitly supplies a writer.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Mapping, Sequence
from typing import Any

from nativeforge.domain.enums import (
    UNPERSISTABLE_AUDIT_ACTIONS,
    AuditAction,
    audit_action_is_persistable,
)

SCHEMA_VERSION = "nf_security_audit_sink_v1"

SINK_MODES = frozenset({"modeled", "live"})

CLASSIFICATIONS = frozenset({"persistable", "unpersistable", "unknown"})

# The migration that would make the refused verb representable. Surfaced in the
# result so an operator hitting the refusal knows what unblocks it rather than
# having to find the doc.
MIGRATION_FOR_MULTI_ORG_EVENTS = "0028"

# A writer takes one classified event and persists it, returning True on
# success. In a provisioned environment this wraps
# repositories.audit_events.append_org_audit_event; there is no default, so
# "modeled" cannot accidentally become "live".
EventWriter = Callable[[Mapping[str, Any]], bool]


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def classify_event(event: Mapping[str, Any]) -> dict[str, Any]:
    """Decide whether one modeled event can be honestly stored today.

    Checks are ordered so the most fundamental problem is reported first: an
    unrecognised action is a worse signal than a missing org, because it means
    the emitter and this sink disagree about what events exist.
    """
    reasons: list[str] = []
    raw_action = event.get("event_type") or event.get("action")

    action: AuditAction | None = None
    try:
        action = AuditAction(raw_action)
    except (ValueError, TypeError):
        reasons.append(f"unknown_audit_action:{raw_action!r}")

    classification = "unknown"
    migration_required: str | None = None

    if action is not None:
        if action in UNPERSISTABLE_AUDIT_ACTIONS:
            classification = "unpersistable"
            migration_required = MIGRATION_FOR_MULTI_ORG_EVENTS
            reasons.append(f"action_not_representable_by_current_schema:{action.value}")
        else:
            classification = "persistable"

        # Belt and braces: the enum helper is the authority, and disagreeing
        # with it here would mean one of the two is wrong.
        if audit_action_is_persistable(action) != (classification == "persistable"):
            reasons.append("classification_disagrees_with_enum_helper")

    # organization_id is NOT NULL in the schema, so an event without one cannot
    # be inserted regardless of its action.
    org = event.get("organization_profile_id") or event.get("organization_id")
    if not org or not str(org).strip():
        reasons.append("missing_organization_id_required_by_schema")

    # An event arriving already claiming persistence is the one input shape that
    # could let a false claim through the accounting. Refuse it rather than
    # normalising it, because something upstream is lying or confused.
    if event.get("persisted") is True:
        reasons.append("event_arrived_claiming_persisted_true")

    return _json_safe(
        {
            "action": action.value if action else None,
            "raw_action": raw_action if action is None else None,
            "classification": classification,
            "persistable": classification == "persistable" and not reasons,
            "blocked_reasons": reasons,
            "migration_required": migration_required,
            "organization_id": str(org) if org else None,
        }
    )


def submit_events(
    events: Sequence[Mapping[str, Any]] | None,
    *,
    mode: str = "modeled",
    writer: EventWriter | None = None,
) -> dict[str, Any]:
    """Classify and account for a batch of modeled audit events.

    ``mode="modeled"`` writes nothing. ``mode="live"`` writes only events
    classified persistable, and only when a ``writer`` was supplied — a live mode
    with no writer is a configuration error, not a silent no-op.
    """
    blocked: list[str] = []
    warnings: list[str] = []
    written: list[dict[str, Any]] = []
    refused: list[dict[str, Any]] = []

    normalized_mode = mode if mode in SINK_MODES else "unknown"
    if normalized_mode == "unknown":
        blocked.append(f"unknown_sink_mode:{mode!r}")
    if normalized_mode == "live" and writer is None:
        # Falling back to modeled here would mean a caller who asked for
        # persistence gets none and is told everything is fine.
        blocked.append("live_mode_requires_a_writer")

    batch = list(events or ())
    accepted = not blocked

    for event in batch:
        verdict = classify_event(event)
        record = {
            "action": verdict["action"] or verdict["raw_action"],
            "classification": verdict["classification"],
            "blocked_reasons": verdict["blocked_reasons"],
            "migration_required": verdict["migration_required"],
        }

        if not verdict["persistable"]:
            refused.append(record)
            continue

        if not accepted or normalized_mode != "live":
            # Classified fine, but this sink is not writing. Not a refusal —
            # accounted separately so "would have been stored" stays visible.
            record["reason_not_written"] = (
                "sink_in_modeled_mode" if accepted else "sink_not_accepted"
            )
            refused.append(record)
            continue

        try:
            ok = bool(writer(event)) if writer else False
        except Exception as exc:  # noqa: BLE001 - a failed audit write must surface
            record["blocked_reasons"] = [
                *record["blocked_reasons"],
                f"writer_raised:{type(exc).__name__}",
            ]
            refused.append(record)
            warnings.append("audit_write_failed_request_should_fail")
            continue

        if ok:
            written.append(record)
        else:
            record["blocked_reasons"] = [
                *record["blocked_reasons"],
                "writer_returned_false",
            ]
            refused.append(record)

    # Nothing may be lost between input and accounting. This is the invariant
    # that makes "no security event is silently dropped" checkable rather than
    # aspirational.
    if len(written) + len(refused) != len(batch):
        blocked.append("event_accounting_mismatch")
        accepted = False

    unpersistable = [r for r in refused if r["classification"] == "unpersistable"]
    if unpersistable:
        warnings.append(
            f"events_refused_pending_migration_{MIGRATION_FOR_MULTI_ORG_EVENTS}"
        )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "mode": normalized_mode,
            "accepted": accepted,
            # Only a live write makes this true, and only for what actually wrote.
            "persisted": bool(written) and normalized_mode == "live",
            "persistable_count": len(written)
            + len([r for r in refused if r["classification"] == "persistable"]),
            "blocked_reasons": blocked,
            "warnings": warnings,
            "event_count": len(batch),
            "events_written": written,
            "events_refused": refused,
            "migration_required": (
                MIGRATION_FOR_MULTI_ORG_EVENTS if unpersistable else None
            ),
            # No provisioned database and no proven audit persistence. This is
            # False from this module by construction.
            "production_persistence_claimed": False,
        }
    )


def repository_writer(session: Any, *, is_demo: bool = False) -> EventWriter:
    """Build a writer backed by the existing repository.

    Imported lazily so this module stays importable without SQLAlchemy, and so
    a test can exercise classification without a database.

    The repository's own Gate 65 guard raises on an unpersistable action. That
    guard stays the last line of defence: this sink should never hand it one, and
    if it does, raising is the correct outcome.
    """

    def _write(event: Mapping[str, Any]) -> bool:
        import uuid as _uuid

        from nativeforge.repositories.audit_events import append_org_audit_event

        action = AuditAction(event.get("event_type") or event.get("action"))
        org_raw = event.get("organization_profile_id") or event.get("organization_id")
        actor_raw = event.get("actor_id")

        def _as_uuid(value: Any) -> Any:
            try:
                return _uuid.UUID(str(value))
            except (ValueError, TypeError, AttributeError):
                return None

        org_id = _as_uuid(org_raw)
        if org_id is None:
            return False

        append_org_audit_event(
            session,
            organization_id=org_id,
            is_demo=is_demo,
            action=action,
            payload=dict(event.get("detail") or {}),
            actor_id=_as_uuid(actor_raw),
        )
        return True

    return _write


def sink_result_invariant_failures(result: Mapping[str, Any]) -> list[str]:
    fails: list[str] = []
    if result.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if result.get("mode") not in (SINK_MODES | {"unknown"}):
        fails.append("mode_invalid")

    written = result.get("events_written") or []
    refused = result.get("events_refused") or []

    if len(written) + len(refused) != result.get("event_count"):
        fails.append("event_accounting_mismatch")

    for record in written:
        if record.get("classification") != "persistable":
            fails.append("wrote_a_non_persistable_event")
        if record.get("action") == AuditAction.cross_org_access_attempt.value:
            fails.append("wrote_cross_org_access_attempt")
        if record.get("blocked_reasons"):
            fails.append("wrote_an_event_with_blocked_reasons")

    if result.get("persisted") and result.get("mode") != "live":
        fails.append("persistence_claimed_outside_live_mode")
    if result.get("persisted") and not written:
        fails.append("persistence_claimed_with_nothing_written")

    # Every refusal must say why, or it is a silent drop wearing a record.
    for record in refused:
        if not record.get("blocked_reasons") and not record.get("reason_not_written"):
            fails.append("refused_without_reason")

    if result.get("production_persistence_claimed") is not False:
        fails.append("forbidden_claim:production_persistence_claimed")
    return fails
