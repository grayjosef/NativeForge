"""The diagnostic that must never become the leak.

This event is emitted from inside the OAuth callback, which at that moment is
holding an authorization code, an ID token, the client secret and a session
cookie. A diagnostic added in a hurry to a request like that is exactly how
credentials end up in a log aggregator.

So the emitter takes booleans, enums and short reason codes, and withholds
anything else rather than trusting its callers. These tests are mostly about
what does not come out.

The other half is the three-valued reads. Under row-level security a refused
read and an absent row both return nothing, so `NOT_FOUND` and `ACCESS_DENIED`
have to be distinguishable or the log sends the reader after the wrong bug.
"""

from __future__ import annotations

import json
import logging

import pytest

from nativeforge.services.demo_bootstrap_decision_log_service import (
    EVENT,
    FIELDS,
    UNKNOWN,
    WITHHELD,
    build_decision_event,
    emit,
)

SECRETS = [
    "eyJhbGciOiJSUzI1NiIsImtpZCI6ImFiYyJ9.eyJzdWIiOiIxIn0.sig",  # id token
    "GOCSPX-a1b2c3d4e5f6g7h8i9j0klmno",  # client secret shape
    "4/0AeanS0b7Qk2mVv9x-authorization-code",  # auth code
    "nf1.eyJvcmciOiJiYmJiIn0.signature",  # session cookie
    "postgresql://user:password@host:5432/db",  # database url
    "somebody@example.com",  # address
    "https://accounts.google.com/o/oauth2/v2/auth?state=abc",  # url with state
]


# ------------------------------------------------------ nothing leaks


@pytest.mark.parametrize("secret", SECRETS)
def test_a_secret_shaped_value_is_withheld_not_logged(secret: str):
    event = build_decision_event(tenant_context_blocked_reasons=[secret])
    blob = json.dumps(event)
    assert secret not in blob
    assert event["tenant_context_blocked_reasons"] == [WITHHELD]


@pytest.mark.parametrize("secret", SECRETS)
def test_a_secret_in_a_scalar_field_is_withheld_too(secret: str):
    event = build_decision_event(target_org_lookup=secret)
    assert secret not in json.dumps(event)


def test_an_email_address_never_survives():
    event = build_decision_event(insert_blocked_reasons=["user@tribe.example"])
    assert "@" not in json.dumps(event)


def test_an_unexpected_object_is_withheld_rather_than_stringified():
    class Carrier:
        def __str__(self):
            return "GOCSPX-secret-in-repr"

    event = build_decision_event(identity_validated=Carrier())
    assert "GOCSPX" not in json.dumps(event)
    assert event["identity_validated"] == WITHHELD


def test_the_whole_event_is_json_and_flat():
    event = build_decision_event(bootstrap_attempted=True)
    json.dumps(event)
    for key, value in event.items():
        assert isinstance(value, (bool, int, str, list)), key


# --------------------------------------------- the reasons that must appear


def test_a_refusal_reason_survives():
    """Withholding everything would be safe and useless."""
    event = build_decision_event(
        tenant_context_blocked_reasons=["organization_already_has_memberships:3"]
    )
    assert event["tenant_context_blocked_reasons"] == [
        "organization_already_has_memberships:3"
    ]


def test_a_success_is_legible():
    event = build_decision_event(
        bootstrap_attempted=True,
        tenant_context_opened=True,
        insert_succeeded=True,
        callback_session_allowed=True,
    )
    assert event["tenant_context_opened"] is True
    assert event["insert_succeeded"] is True
    assert event["callback_session_allowed"] is True


def test_every_field_is_always_present():
    """A missing key says neither "we did not get there" nor "nobody wrote it
    down". Absence is not a diagnostic."""
    event = build_decision_event()
    for name in FIELDS:
        assert name in event
    assert event["identity_validated"] == UNKNOWN


# ------------------------------------- not-found is not access-denied


def test_access_denied_and_not_found_are_distinct_values():
    denied = build_decision_event(target_org_lookup="ACCESS_DENIED")
    missing = build_decision_event(target_org_lookup="NOT_FOUND")
    assert denied["target_org_lookup"] != missing["target_org_lookup"]


def test_an_unreadable_membership_count_is_not_a_count_of_zero():
    """The distinction this whole file exists for.

    A bootstrap that cannot read the membership table must not conclude the
    organization is empty and proceed.
    """
    event = build_decision_event(
        membership_count_lookup="ACCESS_DENIED",
        existing_membership_count_zero=None,
    )
    assert event["membership_count_lookup"] == "ACCESS_DENIED"
    assert event["existing_membership_count_zero"] == UNKNOWN
    assert event["existing_membership_count_zero"] is not False


def test_the_context_service_reports_the_same_vocabulary():
    from nativeforge.services.demo_bootstrap_tenant_context_service import (
        ACCESS_DENIED,
        FOUND,
        NOT_FOUND,
    )

    assert {FOUND, NOT_FOUND, ACCESS_DENIED} == {"FOUND", "NOT_FOUND", "ACCESS_DENIED"}


# -------------------------------------------- it changes no decision


def test_emit_returns_the_event_it_logged(caplog):
    with caplog.at_level(logging.INFO, logger=EVENT):
        returned = emit(bootstrap_attempted=True, insert_succeeded=False)

    assert returned["bootstrap_attempted"] is True
    logged = json.loads(caplog.records[-1].message)
    assert logged == returned


def test_a_broken_logger_does_not_break_authentication(monkeypatch):
    """Observability failing must not become authentication failing."""
    import nativeforge.services.demo_bootstrap_decision_log_service as mod

    class Exploding:
        def info(self, *_a, **_k):
            raise RuntimeError("log sink is down")

    monkeypatch.setattr(mod, "LOGGER", Exploding())
    event = mod.emit(bootstrap_attempted=True)
    assert event["bootstrap_attempted"] is True


def test_the_emitter_touches_no_database_and_no_policy():
    """Instrumentation only. It reads nothing and writes nothing."""
    from pathlib import Path

    import nativeforge.services.demo_bootstrap_decision_log_service as mod

    source = Path(mod.__file__).read_text(encoding="utf-8").upper()
    for forbidden in ("SELECT ", "INSERT ", "UPDATE ", "SET_CONFIG", "POLICY", "SA."):
        assert forbidden not in source, forbidden


def test_the_callback_emits_exactly_once():
    from pathlib import Path

    source = Path("src/nativeforge/api/auth.py").read_text(encoding="utf-8")
    assert source.count("emit_bootstrap_decision(") == 1


def test_the_callback_emits_before_the_session_is_minted():
    """So a refusal is recorded even when no session follows it."""
    from pathlib import Path

    source = Path("src/nativeforge/api/auth.py").read_text(encoding="utf-8")
    assert source.index("emit_bootstrap_decision(") < source.index(
        "if organization_id_resolved and membership_verified:"
    )
