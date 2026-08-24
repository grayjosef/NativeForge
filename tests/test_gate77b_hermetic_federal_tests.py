"""Tests: Gate 77B hermetic federal tests and fixture write-back lockdown.

Two defaults proved here, both of which were false before this gate: the suite
cannot call a third-party API, and it cannot rewrite committed evidence.

The combination was the dangerous part. An online run of
`test_sprint345_nf15_corrected_corpus` would have written a live `HHS-IHS`
response over the recorded `SAMHSA / HHS` row and committed fabricated agency
ownership, produced by nothing more than running the suite. Nothing in this file
touches the network — the "live-like IHS response" case is a stub.
"""

from __future__ import annotations

import json
import pathlib

import pytest

from nativeforge.services.hermetic_test_guard_service import (
    ARTIFACT_WRITEBACK_DIR,
    ENV_ALLOW_CORPUS_WRITEBACK,
    ENV_ALLOW_LIVE_NETWORK,
    ENV_ALLOW_SOURCE_FIXTURE_OVERWRITE,
    LiveNetworkBlockedError,
    RecordedTransportMissingError,
    assert_live_network_allowed,
    corpus_writeback_allowed,
    guarded_write_json,
    hermetic_status,
    hermetic_status_invariant_failures,
    is_source_controlled,
    live_network_allowed,
    load_recorded_transport,
    recorded_transport_metadata,
    resolve_writeback_path,
    source_fixture_overwrite_allowed,
)
from nativeforge.services.source_program_ownership_guard_service import (
    CrossProgramProxyError,
    assert_source_program_ownership,
)

ROOT = pathlib.Path(__file__).resolve().parents[1]
COMMITTED_FIXTURE = (
    ROOT / "fixtures" / "real_grants_corpus" / "nf15_eligibility_reingest_pulls.json"
)
RECORDED_TRANSPORT = "nf_seed_2026_fed_021_samhsa_sm_26_024.json"

ALL_FLAGS = (
    ENV_ALLOW_LIVE_NETWORK,
    ENV_ALLOW_CORPUS_WRITEBACK,
    ENV_ALLOW_SOURCE_FIXTURE_OVERWRITE,
)


@pytest.fixture(autouse=True)
def _clear_flags(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every test starts from the default, locked-down state."""
    for flag in ALL_FLAGS:
        monkeypatch.delenv(flag, raising=False)


# ── network: default deny ───────────────────────────────────────────────────


def test_live_network_denied_by_default() -> None:
    assert live_network_allowed() is False
    with pytest.raises(LiveNetworkBlockedError, match="disabled by default"):
        assert_live_network_allowed(url="https://api.grants.gov/v1/api/search2")


def test_the_grants_gov_client_itself_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The choke point every live call funnels through."""
    from nativeforge.services.grants_gov_search_api_adapter_service import (
        default_grants_gov_http_post,
    )

    with pytest.raises(LiveNetworkBlockedError):
        default_grants_gov_http_post(
            "https://api.grants.gov/v1/api/search2", {"keyword": "x"}
        )


def test_explicit_flag_permits_live_network(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv(ENV_ALLOW_LIVE_NETWORK, "1")
    assert live_network_allowed() is True
    assert_live_network_allowed(url="https://example.gov")  # does not raise


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_truthy_flag_values(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
    monkeypatch.setenv(ENV_ALLOW_LIVE_NETWORK, value)
    assert live_network_allowed() is True


@pytest.mark.parametrize("value", ["", "0", "false", "no", "flase", "maybe", " "])
def test_unrecognised_flag_values_stay_off(
    monkeypatch: pytest.MonkeyPatch, value: str
) -> None:
    """A guard that disables itself on a typo is not a guard."""
    monkeypatch.setenv(ENV_ALLOW_LIVE_NETWORK, value)
    assert live_network_allowed() is False


def test_blocked_network_names_the_flag_and_the_doc() -> None:
    """Whoever hits this needs to know what to do about it."""
    with pytest.raises(LiveNetworkBlockedError) as exc:
        assert_live_network_allowed(url="https://api.grants.gov", caller="x")
    message = str(exc.value)
    assert ENV_ALLOW_LIVE_NETWORK in message
    assert "429_GATE77B_HERMETIC_GRANTS_GOV_TEST_POLICY" in message


# ── write-back: default redirect ────────────────────────────────────────────


def test_writeback_flags_default_off() -> None:
    assert corpus_writeback_allowed() is False
    assert source_fixture_overwrite_allowed() is False


def test_committed_fixture_is_recognised_as_source_controlled() -> None:
    assert is_source_controlled(COMMITTED_FIXTURE) is True
    assert is_source_controlled(ROOT / "fixtures" / "anything.json") is True
    assert is_source_controlled(ROOT / "tests" / "fixtures" / "x.json") is True
    assert is_source_controlled(ROOT / "artifacts" / "x.json") is False


def test_write_to_committed_fixture_is_redirected_by_default() -> None:
    decision = resolve_writeback_path(COMMITTED_FIXTURE)
    assert decision["redirected"] is True
    assert decision["source_controlled"] is True
    assert "refusing_to_overwrite_committed_evidence" in decision["reasons"]
    assert str(ARTIFACT_WRITEBACK_DIR) in decision["path"]
    assert decision["path"] != str(COMMITTED_FIXTURE)


def test_non_source_path_is_not_redirected(tmp_path: pathlib.Path) -> None:
    target = tmp_path / "out.json"
    decision = resolve_writeback_path(target)
    assert decision["redirected"] is False
    assert decision["path"] == str(target)


def test_writeback_flag_alone_does_not_permit_source_overwrite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Routine write-back must not also grant clobbering committed evidence."""
    monkeypatch.setenv(ENV_ALLOW_CORPUS_WRITEBACK, "1")
    assert corpus_writeback_allowed() is True
    assert source_fixture_overwrite_allowed() is False
    assert resolve_writeback_path(COMMITTED_FIXTURE)["redirected"] is True


def test_overwrite_flag_alone_does_not_permit_source_overwrite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(ENV_ALLOW_SOURCE_FIXTURE_OVERWRITE, "1")
    assert source_fixture_overwrite_allowed() is False
    assert resolve_writeback_path(COMMITTED_FIXTURE)["redirected"] is True


def test_both_flags_together_permit_source_overwrite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The gate must be passable for a deliberate re-record."""
    monkeypatch.setenv(ENV_ALLOW_CORPUS_WRITEBACK, "1")
    monkeypatch.setenv(ENV_ALLOW_SOURCE_FIXTURE_OVERWRITE, "1")
    assert source_fixture_overwrite_allowed() is True
    decision = resolve_writeback_path(COMMITTED_FIXTURE)
    assert decision["redirected"] is False
    assert decision["path"] == str(COMMITTED_FIXTURE)


def test_guarded_write_actually_writes_the_redirect(tmp_path: pathlib.Path) -> None:
    decision = guarded_write_json(
        COMMITTED_FIXTURE, {"probe": True}, label="gate77b_probe"
    )
    written = pathlib.Path(decision["path"])
    assert decision["redirected"] is True
    assert written.is_file()
    assert json.loads(written.read_text(encoding="utf-8")) == {"probe": True}
    written.unlink()


# ── the committed evidence survives ─────────────────────────────────────────


def _samhsa_row() -> dict:
    data = json.loads(COMMITTED_FIXTURE.read_text(encoding="utf-8"))
    return next(r for r in data["results"] if r.get("grant_id") == "nf13-real-fed-021")


def test_committed_fixture_still_records_samhsa_evidence() -> None:
    """The row Gate 77 nearly lost."""
    row = _samhsa_row()
    assert row["updated_grant"]["agency"] == "SAMHSA / HHS"
    assert row["updated_grant"]["opportunity_number"] == "SM-26-024"
    assert row["chosen_opportunity_id"] == "361976"
    assert row["reingested"] is True


def test_committed_fixture_carries_no_connection_error_placeholder() -> None:
    """The exact corruption an offline run produced in Gate 77."""
    body = COMMITTED_FIXTURE.read_text(encoding="utf-8")
    assert "Connection refused" not in body
    assert "search_api_error" not in body


def test_committed_fixture_carries_no_ihs_substitution() -> None:
    """The corruption an online run would have produced."""
    body = COMMITTED_FIXTURE.read_text(encoding="utf-8")
    assert "HHS-IHS" not in body
    assert "IHS-SPIP" not in body


def test_default_reingest_run_does_not_touch_the_committed_fixture() -> None:
    before = COMMITTED_FIXTURE.read_bytes()
    from nativeforge.services.tribal_grant_eligibility_reingest_service import (
        reingest_nf13_placeholder_grants,
    )

    report = reingest_nf13_placeholder_grants(
        http_post=load_recorded_transport(RECORDED_TRANSPORT)
    )
    assert report["writeback_redirected"] is True
    assert COMMITTED_FIXTURE.read_bytes() == before


def test_reingest_without_a_transport_is_blocked_not_live() -> None:
    """No transport must mean refused, never a live fetch."""
    from nativeforge.services.tribal_grant_eligibility_reingest_service import (
        reingest_nf13_placeholder_grants,
    )

    before = COMMITTED_FIXTURE.read_bytes()
    report = reingest_nf13_placeholder_grants()
    fed021 = next(r for r in report["results"] if r["grant_id"] == "nf13-real-fed-021")
    # The live call was refused, so the seed reports no live NOFO rather than
    # returning someone else's opportunity.
    assert fed021.get("no_live_nofo") is True
    assert "disabled by default" in str(fed021.get("diagnosis"))
    assert COMMITTED_FIXTURE.read_bytes() == before


# ── recorded transport ──────────────────────────────────────────────────────


def test_recorded_transport_reproduces_the_samhsa_row() -> None:
    from nativeforge.services.tribal_grant_eligibility_reingest_service import (
        reingest_nf13_placeholder_grants,
    )

    report = reingest_nf13_placeholder_grants(
        http_post=load_recorded_transport(RECORDED_TRANSPORT)
    )
    fed021 = next(r for r in report["results"] if r["grant_id"] == "nf13-real-fed-021")
    assert fed021["reingested"] is True
    assert fed021["updated_grant"]["agency"] == "SAMHSA / HHS"
    assert fed021["updated_grant"]["opportunity_number"] == "SM-26-024"
    assert report["proxy_substitution_count"] == 0


def test_recorded_transport_is_labelled_as_repo_recorded() -> None:
    meta = recorded_transport_metadata(RECORDED_TRANSPORT)
    assert meta["provenance"] == "repo-recorded, NOT live-fetched"
    assert meta["recorded_agency"] == "SAMHSA / HHS"
    assert meta["recorded_opportunity_number"] == "SM-26-024"


def test_recorded_transport_contains_no_ihs_data() -> None:
    body = (ROOT / "tests" / "fixtures" / "grants_gov" / RECORDED_TRANSPORT).read_text(
        encoding="utf-8"
    )
    # The meta block names HHS-IHS when explaining what live returns; the
    # response payloads must not contain it.
    responses = json.dumps(json.loads(body)["responses"])
    assert "HHS-IHS" not in responses
    assert "IHS-SPIP" not in responses


def test_missing_recorded_transport_raises_rather_than_fetching() -> None:
    """ "We have no recording" must never become "so ask the internet"."""
    with pytest.raises(RecordedTransportMissingError):
        load_recorded_transport("no_such_recording.json")


def test_unrecorded_url_returns_no_hits_not_an_invented_opportunity() -> None:
    transport = load_recorded_transport(RECORDED_TRANSPORT)
    result = transport("https://api.grants.gov/v1/api/unknown", {})
    assert result["errorcode"] == 0
    assert result["data"]["oppHits"] == []


# ── the guard is intact ─────────────────────────────────────────────────────


def test_ihs_response_still_triggers_the_cross_program_guard() -> None:
    """A live-like IHS payload against a SAMHSA source must still be refused.

    Stubbed, not fetched — proving the guard does not require the network.
    """
    source = {
        "seed_id": "nf-seed-2026-fed-021",
        "source_name": "SAMHSA / HHS — AI/AN Zero Suicide & Suicide Prevention",
    }
    ihs_grant = {
        "grant_id": "nf13-real-fed-021",
        "agency": "HHS-IHS",
        "opportunity_number": "HHS-2027-IHS-SPIP-0001",
        "opportunity_title": "Suicide Prevention, Intervention, and Postvention",
    }
    with pytest.raises(CrossProgramProxyError, match="does not match source agency"):
        assert_source_program_ownership(source=source, grant=ihs_grant)


def test_samhsa_response_passes_the_cross_program_guard() -> None:
    source = {
        "seed_id": "nf-seed-2026-fed-021",
        "source_name": "SAMHSA / HHS — AI/AN Zero Suicide & Suicide Prevention",
    }
    samhsa_grant = {
        "grant_id": "nf13-real-fed-021",
        "agency": "SAMHSA / HHS",
        "opportunity_number": "SM-26-024",
        "opportunity_title": "Tribal Behavioral Health: Suicide Prevention",
    }
    assert_source_program_ownership(source=source, grant=samhsa_grant)  # no raise


def test_the_guard_source_was_not_weakened() -> None:
    guard = (
        ROOT
        / "src"
        / "nativeforge"
        / "services"
        / "source_program_ownership_guard_service.py"
    ).read_text(encoding="utf-8")
    assert "class CrossProgramProxyError" in guard
    assert "raise CrossProgramProxyError" in guard
    assert "def assert_source_program_ownership" in guard


# ── status reporting and claims ─────────────────────────────────────────────


def test_hermetic_status_reports_the_default_mode() -> None:
    status = hermetic_status()
    assert status["mode"] == "hermetic"
    assert status["live_network_allowed"] is False
    assert not hermetic_status_invariant_failures(status)


def test_hermetic_status_reports_live_mode(monkeypatch: pytest.MonkeyPatch) -> None:
    """Live mode must be visible in the result, not silent."""
    monkeypatch.setenv(ENV_ALLOW_LIVE_NETWORK, "1")
    status = hermetic_status()
    assert status["mode"] == "live"
    assert status["live_network_allowed"] is True
    assert not hermetic_status_invariant_failures(status)


def test_invariants_reject_live_network_without_live_mode() -> None:
    status = hermetic_status()
    status["live_network_allowed"] = True
    assert "live_network_without_live_mode" in hermetic_status_invariant_failures(
        status
    )


def test_no_live_federal_coverage_is_claimed() -> None:
    doc = (
        ROOT / "docs" / "operations" / "432_GATE77B_PRODUCTION_READINESS_DELTA.md"
    ).read_text(encoding="utf-8")
    assert "Live federal source coverage: NONE" in doc
    assert "65% improvement:              NOT CLAIMED" in doc
    assert "Controlled customer pilot:    NO_GO" in doc


def test_no_fabricated_agency_ownership_claimed() -> None:
    doc = (
        ROOT
        / "docs"
        / "operations"
        / "431_GATE77B_CORRECTED_CORPUS_UNQUARANTINE_STATUS.md"
    ).read_text(encoding="utf-8")
    assert "SAMHSA / HHS" in doc
    assert "guard" in doc.lower()
