"""Gate 146: the second-person invite event, and what may not stand in for it.

`customer_auth_live` has one blocker left and it is not a decision anybody has
withheld. It is an event: a real second Google account completing real OAuth,
being invited, and having that invite accepted for them.

The tests below exist mostly to prove that nothing *else* can satisfy it. A
typed identity row, a minted session, a synthetic subject, a directly written
membership, the owner's own login, and the real organization are each refused,
and each refusal is checked rather than asserted in a comment.

The second thing they prove is the distinction Gate 145 named five times:

```text
readiness_passed     the path is correct and runnable
customer_auth_live   somebody walked it
```

Both are reported. Neither is allowed to stand for the other.
"""

from __future__ import annotations

import inspect
import json
import re
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.main import create_app
from nativeforge.services import (
    customer_auth_second_person_artifact_gate146_service as art,
)
from nativeforge.services.customer_auth_second_person_event_checklist_service import (
    DEMO_ORGANIZATION_ID,
    GOOGLE_TEST_USER_ENROLMENT,
    REFUSED_ORGANIZATION_ID,
    REFUSED_SHORTCUTS,
    STAGE_COMPLETE,
    STAGE_INVITE_ACCEPTED,
    STAGE_INVITE_ISSUED,
    STAGE_SECOND_IDENTITY,
    STAGES,
    UNKNOWN,
    build_second_person_checklist,
    checklist_invariant_failures,
)
from tests import session_org_helper as soh

DEMO = DEMO_ORGANIZATION_ID
OTHER = "cccccccc-dddd-eeee-ffff-00000000d146"
REAL = REFUSED_ORGANIZATION_ID

REPO_ROOT = Path(__file__).resolve().parents[1]
ADDRESS_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
SUBJECT_SHAPE = re.compile(r"\b\d{18,}\b")


def _base(organization_id: str = DEMO) -> str:
    return f"/v1/nf/demo/orgs/{organization_id}/auth-readiness"


def _evidence(**overrides):
    """A neutral evidence dict: nothing has happened yet."""
    base = {
        "identity_rows": 1,
        "invite_rows": 0,
        "approved_invite_rows": 0,
        "accepted_invite_rows": 0,
        "membership_rows": 1,
        "memberships_from_a_completed_invite": 0,
        "memberships_matching_an_accepter_by_identity_only": 0,
        "invite_binding_passed": False,
        "blocked_reasons": ["no_invite_has_been_recorded"],
    }
    base.update(overrides)
    return base


def _complete_evidence():
    """The shape the live database will have once the event has happened."""
    return _evidence(
        identity_rows=2,
        invite_rows=1,
        approved_invite_rows=1,
        accepted_invite_rows=1,
        membership_rows=2,
        memberships_from_a_completed_invite=1,
        invite_binding_passed=True,
        blocked_reasons=[],
    )


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def demo_session():
    soh.ensure_signing_key()
    soh.ensure_org(DEMO, "demo")
    soh.ensure_org(OTHER, "demo")
    soh.ensure_member(DEMO)
    return soh.session_headers(uuid.UUID(DEMO))


# ---------------------------------------------------------------------------
# the blocker, and where it actually is
# ---------------------------------------------------------------------------


def test_the_checklist_names_the_invite_binding_blocker():
    result = build_second_person_checklist(evidence=_evidence())
    assert result["invite_binding_passed"] is False
    assert result["customer_auth_live"] is False
    assert "no_invite_has_been_recorded" in result["blockers"]


def test_the_stage_is_the_earliest_unsatisfied_one_not_the_conjunction():
    """Told only "invite_binding_passed", an operator looks for an invite.

    There is no invite, and nobody has signed in to accept one. The honest next
    action is two stages earlier than the blocker's name suggests.
    """
    result = build_second_person_checklist(evidence=_evidence())
    assert result["stage"] == STAGE_SECOND_IDENTITY
    assert result["next_human_action"]["stage"] == STAGE_SECOND_IDENTITY
    assert result["next_human_action"]["who"] == "the second person"


def test_the_stage_advances_as_each_one_is_satisfied():
    signed_in = build_second_person_checklist(evidence=_evidence(identity_rows=2))
    assert signed_in["stage"] == STAGE_INVITE_ISSUED
    assert signed_in["next_human_action"]["who"] == "the operator"

    issued = build_second_person_checklist(
        evidence=_evidence(identity_rows=2, invite_rows=1)
    )
    assert issued["stage"] == STAGE_INVITE_ACCEPTED


def test_the_complete_state_reaches_customer_auth_live():
    """The permitted branch is reachable, or every refusal above it is unfalsifiable.

    Gate 134F's lesson. Nothing in runtime reaches this today.
    """
    result = build_second_person_checklist(evidence=_complete_evidence())
    assert result["stage"] == STAGE_COMPLETE
    assert result["customer_auth_live"] is True
    assert result["invite_binding_passed"] is True
    assert result["blockers"] == []
    assert result["next_human_action"] is None
    assert checklist_invariant_failures(result) == []


@pytest.mark.parametrize("stage", STAGES)
def test_every_stage_has_an_owner_and_needs_a_human(stage):
    result = build_second_person_checklist(evidence=_evidence())
    entry = next(s for s in STAGES if s == stage)
    from nativeforge.services.customer_auth_second_person_event_checklist_service import (  # noqa: E501
        STAGE_OWNERS,
    )

    assert STAGE_OWNERS[entry]["who"]
    assert STAGE_OWNERS[entry]["requires_human"] is True
    assert result["stages"][entry] is False


# ---------------------------------------------------------------------------
# readiness is not the event
# ---------------------------------------------------------------------------


def test_readiness_passes_while_the_event_has_not_happened():
    result = build_second_person_checklist(evidence=_evidence())
    assert result["readiness_passed"] is True
    assert result["customer_auth_live"] is False
    assert checklist_invariant_failures(result) == []


def test_readiness_is_false_when_nothing_was_read():
    result = build_second_person_checklist(evidence=None)
    assert result["readiness_passed"] is False
    assert result["customer_auth_live"] is False
    assert "no_evidence_supplied" in result["blockers"]


def test_customer_auth_live_is_not_a_parameter():
    """A caller cannot assert the thing the gate exists to measure.

    The same structural rule Gate 145 applied to the capability flags.
    """
    signature = inspect.signature(build_second_person_checklist)
    assert "customer_auth_live" not in signature.parameters
    assert "invite_binding_passed" not in signature.parameters
    assert "readiness_passed" not in signature.parameters


def test_the_invariants_catch_a_forged_customer_auth_live():
    forged = build_second_person_checklist(evidence=_evidence())
    forged["customer_auth_live"] = True
    failures = checklist_invariant_failures(forged)
    assert "customer_auth_live_without_invite_binding" in failures
    assert "customer_auth_live_alongside_blockers" in failures
    assert "customer_auth_live_before_every_stage" in failures


def test_the_invariants_catch_a_live_claim_without_a_membership():
    forged = build_second_person_checklist(evidence=_complete_evidence())
    forged["counts"]["memberships_from_a_completed_invite"] = 0
    failures = checklist_invariant_failures(forged)
    assert "customer_auth_live_without_a_membership_from_one" in failures


# ---------------------------------------------------------------------------
# what may not stand in for the event
# ---------------------------------------------------------------------------


def test_a_fake_identity_does_not_satisfy_customer_auth_live():
    """An identity row with no invite behind it moves the stage and nothing else."""
    result = build_second_person_checklist(evidence=_evidence(identity_rows=2))
    assert result["customer_auth_live"] is False
    assert result["invite_binding_passed"] is False
    assert result["stage"] == STAGE_INVITE_ISSUED


def test_a_fake_session_does_not_satisfy_customer_auth_live():
    """A session writes no identity row, so it cannot even move stage one."""
    result = build_second_person_checklist(evidence=_evidence())
    assert result["stages"][STAGE_SECOND_IDENTITY] is False
    assert result["customer_auth_live"] is False
    assert result["session_minted_by_this_module"] is False


def test_a_membership_written_directly_does_not_satisfy_the_gate():
    """The near-miss the campaign has already fixed once, kept visible."""
    result = build_second_person_checklist(
        evidence=_evidence(
            identity_rows=2,
            invite_rows=1,
            accepted_invite_rows=1,
            membership_rows=2,
            memberships_from_a_completed_invite=0,
            memberships_matching_an_accepter_by_identity_only=1,
            blocked_reasons=["no_active_membership_came_through_a_completed_invite"],
        )
    )
    assert result["customer_auth_live"] is False
    assert result["counts"]["memberships_matching_an_accepter_by_identity_only"] == 1
    assert result["counts"]["memberships_from_a_completed_invite"] == 0


def test_owner_only_login_does_not_satisfy_customer_auth_live():
    """One identity and one membership is the state measured today."""
    result = build_second_person_checklist(evidence=_evidence(), owner_identities=1)
    assert result["stages"][STAGE_SECOND_IDENTITY] is False
    assert result["customer_auth_live"] is False


def test_the_second_identity_must_be_distinct_from_the_owner():
    result = build_second_person_checklist(evidence=_evidence())
    assert result["second_identity_must_be_distinct_from_owner"] is True
    shortcuts = {s["shortcut"] for s in REFUSED_SHORTCUTS}
    assert any("owner" in s for s in shortcuts)


def test_every_refused_shortcut_says_why():
    assert len(REFUSED_SHORTCUTS) >= 6
    for entry in REFUSED_SHORTCUTS:
        assert entry["shortcut"].strip()
        assert entry["refused_because"].strip()


def test_a_synthetic_provider_subject_is_named_as_refused():
    shortcuts = {s["shortcut"] for s in REFUSED_SHORTCUTS}
    assert any("synthesize a provider subject" in s for s in shortcuts)


def test_the_accept_script_has_no_bypass_flag():
    """The faked user this gate exists to avoid must stay unreachable."""
    source = (REPO_ROOT / "scripts" / "nativeforge_demo_invite_accept.py").read_text(
        encoding="utf-8"
    )
    for flag in ("--force", "--skip-identity", "--no-identity", "--synthetic"):
        assert flag not in source


def test_neither_script_sends_email():
    for name in (
        "nativeforge_demo_invite_issue.py",
        "nativeforge_demo_invite_accept.py",
    ):
        source = (REPO_ROOT / "scripts" / name).read_text(encoding="utf-8")
        for module in ("smtplib", "sendgrid", "boto3.client('ses'", "mailgun"):
            assert module not in source


# ---------------------------------------------------------------------------
# the real organization
# ---------------------------------------------------------------------------


def test_the_real_organization_is_refused_by_name():
    result = build_second_person_checklist(evidence=_evidence(), organization_id=REAL)
    assert result["organization_refused"] is True
    assert result["refusal_reason"] == "real_organization_refused_by_name"
    assert result["readiness_passed"] is False
    assert result["customer_auth_live"] is False


def test_a_third_organization_is_refused_as_not_the_demo_one():
    result = build_second_person_checklist(evidence=_evidence(), organization_id=OTHER)
    assert result["organization_refused"] is True
    assert result["refusal_reason"] == "not_the_demo_organization"


def test_the_invariants_catch_a_real_organization_that_was_not_refused():
    forged = build_second_person_checklist(evidence=_evidence(), organization_id=REAL)
    forged["organization_refused"] = False
    assert "real_organization_not_refused" in checklist_invariant_failures(forged)


def test_the_module_activates_nothing():
    result = build_second_person_checklist(evidence=_complete_evidence())
    for flag in (
        "invite_issued_by_this_module",
        "invite_accepted_by_this_module",
        "identity_written_by_this_module",
        "session_minted_by_this_module",
        "email_sent",
        "real_organization_touched",
    ):
        assert result[flag] is False


# ---------------------------------------------------------------------------
# the step nothing here can observe
# ---------------------------------------------------------------------------


def test_google_test_user_enrolment_stays_unknown():
    """Inferring it from a failure that looks like several others would be a guess."""
    assert GOOGLE_TEST_USER_ENROLMENT["state"] == UNKNOWN
    assert GOOGLE_TEST_USER_ENROLMENT["observable_from_here"] is False
    assert GOOGLE_TEST_USER_ENROLMENT["why_unknown"].strip()


def test_publishing_the_app_is_named_as_the_thing_not_to_do():
    assert "publish" in GOOGLE_TEST_USER_ENROLMENT["must_not"]


# ---------------------------------------------------------------------------
# nothing leaks
# ---------------------------------------------------------------------------


def test_no_address_or_subject_shape_in_the_checklist():
    for payload in (
        build_second_person_checklist(evidence=_evidence()),
        build_second_person_checklist(evidence=_complete_evidence()),
        build_second_person_checklist(evidence=_evidence(), organization_id=REAL),
    ):
        assert payload["leaked_shapes"] == []
        body = json.dumps(payload, default=str)
        assert not ADDRESS_SHAPE.search(body)
        assert not SUBJECT_SHAPE.search(body)


def test_the_leak_scan_actually_fires():
    """A guard nobody has seen fail is a guard nobody has tested."""
    from nativeforge.services.customer_auth_second_person_event_checklist_service import (  # noqa: E501
        _leaked_shapes,
    )

    assert _leaked_shapes({"x": "somebody@example.org"}) == ["email_address"]
    assert _leaked_shapes({"x": "112233445566778899001"}) == ["provider_subject"]
    assert _leaked_shapes({"x": "nf_session=abc"}) == ["session_cookie"]
    assert _leaked_shapes({"x": "nothing to see"}) == []


def test_a_leaked_payload_fails_its_invariants():
    payload = build_second_person_checklist(evidence=_evidence())
    payload["leaked_shapes"] = ["email_address"]
    assert "leaked:email_address" in checklist_invariant_failures(payload)


# ---------------------------------------------------------------------------
# routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path", ["second-person", "blockers", "next-action"]
)
def test_every_route_refuses_an_unauthenticated_caller(client, path):
    assert client.get(f"{_base()}/{path}").status_code == 401


def test_a_forged_dev_header_cannot_override_the_org(client):
    response = client.get(
        f"{_base()}/second-person",
        headers={"X-NF-Org-Id": REAL, "X-NF-Dev-Org-Id": REAL},
    )
    assert response.status_code == 401


def test_the_readiness_route_reports_both_answers(client, demo_session):
    body = client.get(f"{_base()}/second-person", headers=demo_session).json()
    data = body.get("data", body)
    assert data["readiness_passed"] is True
    assert data["customer_auth_live"] is False
    assert data["stage"] in {*STAGES, STAGE_COMPLETE}
    assert "readiness_is_not_the_event" in data


def test_the_readiness_route_leaks_nothing(client, demo_session):
    raw = client.get(f"{_base()}/second-person", headers=demo_session).text
    assert not ADDRESS_SHAPE.search(raw)
    assert not SUBJECT_SHAPE.search(raw)
    assert "nf_session=" not in raw


def test_the_blockers_route_lists_the_refused_shortcuts(client, demo_session):
    body = client.get(f"{_base()}/blockers", headers=demo_session).json()
    data = body.get("data", body)
    assert len(data["refused_shortcuts"]) == len(REFUSED_SHORTCUTS)
    assert data["controlled_customer_pilot"] is False
    assert data["production_rollout"] is False


def test_the_next_action_route_names_one_step(client, demo_session):
    body = client.get(f"{_base()}/next-action", headers=demo_session).json()
    data = body.get("data", body)
    assert data["no_route_performs_these_steps"] is True
    if data["next_human_action"] is not None:
        assert data["next_human_action"]["stage"] in STAGES


def test_another_organization_is_refused(client, demo_session):
    response = client.get(f"{_base(OTHER)}/second-person", headers=demo_session)
    assert response.status_code in {401, 403, 404}


def test_no_route_issues_or_accepts_an_invite():
    """There is no POST here, and that is the design rather than an oversight."""
    from nativeforge.api import customer_auth_readiness_routes as routes

    methods = set()
    for route in routes.router.routes:
        methods |= set(getattr(route, "methods", set()))
    assert methods == {"GET"}


def test_no_real_organization_route_was_built():
    from nativeforge.api import customer_auth_readiness_routes as routes

    assert routes.router.prefix == "/v1/nf/demo/orgs"
    source = Path(routes.__file__).read_text(encoding="utf-8")
    assert "/v1/nf/real" not in source


# ---------------------------------------------------------------------------
# artifacts
# ---------------------------------------------------------------------------


def test_the_artifact_writes_every_declared_file(tmp_path):
    result = art.write_second_person_artifacts(repo_root=tmp_path)
    assert sorted(result["files_written"]) == sorted(art.ARTIFACT_FILES)
    assert art.second_person_artifact_invariant_failures(result) == []
    for name in art.ARTIFACT_FILES:
        assert (tmp_path / art.ARTIFACT_DIR / name).read_text(encoding="utf-8")


def test_the_artifact_is_deterministic():
    assert art.build_second_person_artifacts() == art.build_second_person_artifacts()


def test_the_artifact_reads_no_database():
    """Live counts would be wrong the moment the event happens."""
    signature = inspect.signature(art.build_second_person_artifacts)
    assert signature.parameters == {}


def test_the_artifacts_record_the_blocker_and_the_stages():
    files = art.build_second_person_artifacts()
    blockers = json.loads(files[art.BLOCKERS_FILE])
    assert blockers["blocker"] == "invite_binding_passed"
    assert blockers["blocker_kind"] == "an event, not a decision"
    assert [s["stage"] for s in blockers["stages"]] == list(STAGES)


def test_the_artifacts_record_what_stays_false():
    files = art.build_second_person_artifacts()
    blockers = json.loads(files[art.BLOCKERS_FILE])
    for name in (
        "customer_auth_live",
        "invite_binding_passed",
        "controlled_customer_pilot",
        "production_rollout",
    ):
        assert name in blockers["stays_false_after_this_gate"]


def test_the_artifacts_record_what_must_never_be_printed():
    files = art.build_second_person_artifacts()
    survey = json.loads(files[art.SURVEY_FILE])
    values = {item["value"] for item in survey["never_printed"]}
    assert "the invited address" in values
    assert "the provider subject" in values
    assert survey["safe_to_print"]["value"] == "the invite id"


def test_the_artifacts_record_that_the_accept_step_refuses():
    files = art.build_second_person_artifacts()
    accept = json.loads(files[art.ACCEPT_FILE])
    assert accept["refuses_when_the_person_has_not_signed_in"] is True
    assert accept["has_a_bypass_flag"] is False
    assert accept["refusal"] == "no_identity_has_signed_in_with_that_address"


def test_no_artifact_carries_a_credential_an_address_or_a_subject():
    for name, body in art.build_second_person_artifacts().items():
        assert not ADDRESS_SHAPE.search(body), name
        assert not SUBJECT_SHAPE.search(body), name
        for marker in ("GOCSPX-", "eyJ", "nf_session=", "AKIA", "BEGIN PRIVATE KEY"):
            assert marker not in body, name


def test_the_artifact_shape_scan_actually_fires():
    with pytest.raises(AssertionError):
        art._assert_no_forbidden_shape("x.json", '{"a": "somebody@example.org"}')


def test_the_committed_artifacts_match_what_the_service_builds():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    built = art.build_second_person_artifacts()
    for name, body in built.items():
        committed = (directory / name).read_text(encoding="utf-8")
        assert committed == body, name


# ---------------------------------------------------------------------------
# the lanes that must not move
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "flag",
    [
        "customer_auth_live",
        "invite_binding_passed",
        "controlled_customer_pilot",
        "production_rollout",
    ],
)
def test_no_lane_was_flipped_by_this_gate(flag):
    files = art.build_second_person_artifacts()
    blockers = json.loads(files[art.BLOCKERS_FILE])
    assert flag in blockers["stays_false_after_this_gate"]


def test_the_live_database_still_says_the_event_has_not_happened():
    """A regression that quietly satisfied the gate would show up here.

    Read-only, counts only. Skips rather than fails where no database is
    reachable, because that is an environment fact and not a defect.
    """
    from nativeforge.lib.settings import get_settings
    from nativeforge.services.membership_invite_repository_service import (
        build_invite_binding_evidence,
    )

    try:
        engine = sa.create_engine(get_settings().database_url)
        with engine.connect() as connection:
            evidence = build_invite_binding_evidence(connection=connection)
    except Exception:  # noqa: BLE001
        pytest.skip("no database reachable in this environment")

    if evidence.get("invite_binding_passed"):
        pytest.skip("the second-person event has happened; re-decide at Gate 150")

    result = build_second_person_checklist(evidence=evidence)
    assert result["customer_auth_live"] is False
    assert checklist_invariant_failures(result) == []
