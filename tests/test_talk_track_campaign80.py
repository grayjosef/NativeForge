"""Tests: Campaign Block 80 talk-track."""

from nativeforge.services.gate34_talk_track_assembler_service import (
    build_talk_track_demo_surface,
    talk_track_demo_surface_invariant_failures,
)
from nativeforge.services.gate34_talk_track_service import (
    detect_risky_phrases,
    resolve_talk_track,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)


def test_talk_track_gates() -> None:
    risky = detect_risky_phrases("This is production-ready and login live")
    assert "production-ready" in risky
    assert "login live" in risky
    track = resolve_talk_track()
    assert "pending Auth0" in " ".join(track["allowed_language"]) or (
        "Controlled pilot is pending" in track["demo_script"]
    )
    unsafe = resolve_talk_track(customer_access_cta=True)
    assert unsafe["cta_safe"] is False
    safe = resolve_talk_track()
    assert safe["cta_safe"] is True
    for phrase in ("production-ready", "pilot-ready", "login live"):
        assert phrase.lower() not in safe["demo_script"].lower()
    assert "unvalidated" in safe["evidence_backed_narrative"].lower() or (
        "owner inputs" in safe["evidence_backed_narrative"].lower()
    )
    assert safe["owner_action_exposed"]


def test_demo_bridge() -> None:
    surface = build_talk_track_demo_surface()
    assert talk_track_demo_surface_invariant_failures(surface) == []
    payload = build_sc_customer_demo_bridge_payload()
    assert bridge_payload_invariant_failures(payload) == []
    assert payload["talk_track"]["cta_safe"] is True
