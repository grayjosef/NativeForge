"""Tests: Gate 68A security audit sink.

The sink's job is to decide which modeled audit events the current schema can
honestly store, and to refuse the rest loudly. The single most important
assertion in this file is that ``cross_org_access_attempt`` is never written —
followed closely by the accounting invariant, which is what makes "no security
event is silently dropped" checkable rather than aspirational.
"""

from __future__ import annotations

import pathlib

import pytest

from nativeforge.domain.enums import SECURITY_AUDIT_ACTIONS, AuditAction
from nativeforge.services.security_audit_sink_service import (
    MIGRATION_FOR_MULTI_ORG_EVENTS,
    classify_event,
    repository_writer,
    sink_result_invariant_failures,
    submit_events,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
ORG = "11111111-1111-1111-1111-111111111111"


def _event(action: str, **over: object) -> dict[str, object]:
    base: dict[str, object] = {
        "event_type": action,
        "organization_profile_id": ORG,
        "actor_id": "22222222-2222-2222-2222-222222222222",
        "subject_id": "auth0|abc",
        "detail": {},
        "persisted": False,
    }
    base.update(over)
    return base


class _Recorder:
    """A writer that records what it was handed. Never a real database."""

    def __init__(self, ok: bool = True) -> None:
        self.seen: list[str] = []
        self._ok = ok

    def __call__(self, event: dict) -> bool:
        self.seen.append(str(event.get("event_type")))
        return self._ok


# ── classification ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    "action",
    [
        "membership_created",
        "membership_revoked",
        "membership_expired",
        "role_changed",
        "tenant_access_denied",
        "authority_sensitive_action_blocked",
        "authority_proof_submitted",
        "authority_proof_verified",
        "source_candidate_promoted",
        "source_candidate_blocked",
        "feedback_alert_attempted",
        "feedback_alert_failed",
    ],
)
def test_single_org_security_events_are_persistable(action: str) -> None:
    """Twelve of the thirteen concern exactly one org, which the schema has."""
    v = classify_event(_event(action))
    assert v["classification"] == "persistable"
    assert v["persistable"] is True
    assert v["blocked_reasons"] == []


def test_cross_org_access_attempt_is_unpersistable_with_migration_named() -> None:
    """The one refusal that matters."""
    v = classify_event(_event("cross_org_access_attempt"))
    assert v["classification"] == "unpersistable"
    assert v["persistable"] is False
    assert v["migration_required"] == "0028"
    assert any(
        r.startswith("action_not_representable_by_current_schema")
        for r in v["blocked_reasons"]
    )


def test_exactly_one_security_verb_is_unpersistable() -> None:
    unpersistable = {
        a.value
        for a in SECURITY_AUDIT_ACTIONS
        if classify_event(_event(a.value))["classification"] == "unpersistable"
    }
    assert unpersistable == {"cross_org_access_attempt"}


def test_unknown_action_denied() -> None:
    v = classify_event(_event("definitely_not_a_verb"))
    assert v["classification"] == "unknown"
    assert v["persistable"] is False
    assert any(r.startswith("unknown_audit_action") for r in v["blocked_reasons"])


@pytest.mark.parametrize("bad", [None, "", 42, "role_changed "])
def test_malformed_actions_denied(bad: object) -> None:
    v = classify_event(_event("x", event_type=bad))
    assert v["persistable"] is False


def test_missing_organization_id_refused() -> None:
    """organization_id is NOT NULL, so the row cannot be inserted at all."""
    for missing in (None, "", "   "):
        v = classify_event(_event("role_changed", organization_profile_id=missing))
        assert v["persistable"] is False
        assert "missing_organization_id_required_by_schema" in v["blocked_reasons"]


def test_event_claiming_persisted_true_is_refused() -> None:
    """The one input shape that could let a false persistence claim through."""
    v = classify_event(_event("role_changed", persisted=True))
    assert v["persistable"] is False
    assert "event_arrived_claiming_persisted_true" in v["blocked_reasons"]


def test_alternate_field_names_are_accepted() -> None:
    """Emitters differ: some say event_type/organization_profile_id, others
    say action/organization_id. The sink must read both."""
    v = classify_event({"action": "role_changed", "organization_id": ORG})
    assert v["persistable"] is True


# ── batch accounting ────────────────────────────────────────────────────────


def test_modeled_mode_writes_nothing_and_claims_nothing() -> None:
    r = submit_events([_event("membership_created"), _event("role_changed")])
    assert r["mode"] == "modeled"
    assert r["persisted"] is False
    assert r["events_written"] == []
    assert len(r["events_refused"]) == 2
    for rec in r["events_refused"]:
        assert rec["reason_not_written"] == "sink_in_modeled_mode"
    assert not sink_result_invariant_failures(r)


def test_no_event_is_silently_dropped() -> None:
    """written + refused must equal input, always."""
    events = [
        _event("membership_created"),
        _event("cross_org_access_attempt"),
        _event("not_a_verb"),
        _event("role_changed", organization_profile_id=None),
        _event("membership_revoked", persisted=True),
    ]
    r = submit_events(events)
    assert r["event_count"] == 5
    assert len(r["events_written"]) + len(r["events_refused"]) == 5
    assert not sink_result_invariant_failures(r)


def test_every_refusal_carries_a_reason() -> None:
    r = submit_events([_event("cross_org_access_attempt"), _event("nope")])
    for rec in r["events_refused"]:
        assert rec["blocked_reasons"] or rec.get("reason_not_written")


def test_empty_batch_is_accepted_and_accounts_to_zero() -> None:
    r = submit_events([])
    assert r["accepted"] is True
    assert r["event_count"] == 0
    assert not sink_result_invariant_failures(r)


def test_none_batch_is_handled() -> None:
    r = submit_events(None)
    assert r["event_count"] == 0


def test_batch_with_an_unpersistable_event_names_the_migration() -> None:
    r = submit_events(
        [_event("membership_created"), _event("cross_org_access_attempt")]
    )
    assert r["migration_required"] == MIGRATION_FOR_MULTI_ORG_EVENTS
    assert any("pending_migration" in w for w in r["warnings"])


def test_batch_without_unpersistable_events_names_no_migration() -> None:
    r = submit_events([_event("membership_created")])
    assert r["migration_required"] is None


# ── live mode ───────────────────────────────────────────────────────────────


def test_live_mode_without_a_writer_is_a_configuration_error() -> None:
    """Falling back to modeled would tell a caller who asked for persistence
    that everything is fine while writing nothing."""
    r = submit_events([_event("role_changed")], mode="live")
    assert r["accepted"] is False
    assert "live_mode_requires_a_writer" in r["blocked_reasons"]
    assert r["persisted"] is False


def test_live_mode_writes_persistable_events() -> None:
    w = _Recorder()
    r = submit_events([_event("membership_created")], mode="live", writer=w)
    assert r["accepted"] is True
    assert r["persisted"] is True
    assert len(r["events_written"]) == 1
    assert w.seen == ["membership_created"]
    assert not sink_result_invariant_failures(r)


def test_live_mode_never_hands_the_writer_an_unpersistable_event() -> None:
    """The whole point: the writer must not even see it."""
    w = _Recorder()
    r = submit_events(
        [_event("cross_org_access_attempt"), _event("role_changed")],
        mode="live",
        writer=w,
    )
    assert "cross_org_access_attempt" not in w.seen
    assert w.seen == ["role_changed"]
    assert not sink_result_invariant_failures(r)


def test_live_mode_never_hands_the_writer_a_malformed_event() -> None:
    w = _Recorder()
    submit_events(
        [
            _event("not_a_verb"),
            _event("role_changed", organization_profile_id=None),
            _event("membership_revoked", persisted=True),
        ],
        mode="live",
        writer=w,
    )
    assert w.seen == []


def test_writer_returning_false_is_recorded_as_a_refusal() -> None:
    r = submit_events([_event("role_changed")], mode="live", writer=_Recorder(ok=False))
    assert r["events_written"] == []
    assert "writer_returned_false" in r["events_refused"][0]["blocked_reasons"]


def test_writer_raising_surfaces_rather_than_being_swallowed() -> None:
    """A failed audit write must be visible; the request should fail."""

    def boom(event: dict) -> bool:
        raise RuntimeError("connection lost")

    r = submit_events([_event("role_changed")], mode="live", writer=boom)
    assert r["events_written"] == []
    assert any(
        c.startswith("writer_raised") for c in r["events_refused"][0]["blocked_reasons"]
    )
    assert "audit_write_failed_request_should_fail" in r["warnings"]


def test_unknown_mode_denied() -> None:
    r = submit_events([_event("role_changed")], mode="fire_and_forget")
    assert r["accepted"] is False
    assert any(m.startswith("unknown_sink_mode") for m in r["blocked_reasons"])


# ── the repository guard remains the last line of defence ───────────────────


def test_repository_writer_refuses_a_bad_organization_id() -> None:
    w = repository_writer(session=None)
    assert (
        w({"event_type": "role_changed", "organization_profile_id": "not-a-uuid"})
        is False
    )


def test_repository_still_raises_if_ever_handed_the_unpersistable_verb() -> None:
    """The sink should never reach here. If it does, raising is correct."""
    from nativeforge.repositories.audit_events import append_org_audit_event

    with pytest.raises(ValueError, match="cannot be persisted"):
        append_org_audit_event(
            None,
            organization_id=None,
            is_demo=False,
            action=AuditAction.cross_org_access_attempt,
            payload={},
            actor_id=None,
        )


# ── claims ──────────────────────────────────────────────────────────────────


def test_production_persistence_is_never_claimed() -> None:
    for r in (
        submit_events([_event("role_changed")]),
        submit_events([_event("role_changed")], mode="live", writer=_Recorder()),
    ):
        assert r["production_persistence_claimed"] is False


def test_invariants_reject_a_forged_cross_org_write() -> None:
    r = submit_events([_event("cross_org_access_attempt")])
    r["events_written"] = [
        {
            "action": "cross_org_access_attempt",
            "classification": "persistable",
            "blocked_reasons": [],
        }
    ]
    fails = sink_result_invariant_failures(r)
    assert "wrote_cross_org_access_attempt" in fails


def test_invariants_reject_persistence_claimed_in_modeled_mode() -> None:
    r = submit_events([_event("role_changed")])
    r["persisted"] = True
    fails = sink_result_invariant_failures(r)
    assert "persistence_claimed_outside_live_mode" in fails


def test_invariants_reject_a_lost_event() -> None:
    r = submit_events([_event("role_changed"), _event("membership_created")])
    r["events_refused"] = r["events_refused"][:1]
    assert "event_accounting_mismatch" in sink_result_invariant_failures(r)


def test_survey_documents_the_persistence_boundary() -> None:
    doc = (ROOT / "docs" / "operations" / "408_GATE68A_AUDIT_SINK_SURVEY.md").read_text(
        encoding="utf-8"
    )
    assert "cross_org_access_attempt" in doc
    assert "Actually persisted right now:       0" in doc
