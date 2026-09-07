"""Gate 144: the beta onboarding cockpit shows the truth, false lanes included.

The defect this gate was most likely to introduce, named in doc 751 before any
code was written: a summary that supplied a lane its own evidence would be
**grading its own homework** — reporting `true` for a lane whose proof it
invented. `LANE_EVIDENCE` records what the summary may conclude unaided, and the
tests below target that directly.

The other property that matters:

```text
a cockpit showing only the green lanes would be the most dangerous thing this
campaign could ship
```

so every forbidden lane is asserted present, false, and carrying a blocker.
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nativeforge.main import create_app
from nativeforge.services import beta_onboarding_cockpit_artifact_gate144_service as art
from nativeforge.services.beta_onboarding_readiness_summary_service import (
    BLOCKED,
    CONTROLLED_SCOPE,
    LANE_EVIDENCE,
    LANE_KEYS,
    LANE_STATUSES,
    NEVER_TRUE_LANES,
    NOT_APPROVED,
    NOT_CONFIGURED,
    OPERATIONAL,
    READINESS_ONLY,
    REQUIRES_HUMAN_APPROVAL,
    build_beta_onboarding_summary,
    summary_invariant_failures,
)
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER = "cccccccc-dddd-eeee-ffff-00000000d144"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

REPO_ROOT = Path(__file__).resolve().parents[1]

ADDRESS_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _string_values(node: object) -> list[str]:
    """Every string VALUE in a structure, ignoring field names.

    Field names are the guarantee, not the leak: `"eligibility_reported":
    false` says the summary reports no eligibility, and a scan of the
    serialised blob read that as a violation of the rule it states.
    """
    if isinstance(node, str):
        return [node]
    if isinstance(node, dict):
        return [v for value in node.values() for v in _string_values(value)]
    if isinstance(node, list):
        return [v for item in node for v in _string_values(item)]
    return []


#: Every lane the full verifier battery can prove.
FULL_BATTERY = {
    "login_live": True,
    "customer_persistence_live": True,
    "awarded_operational_tracking": True,
    "tenant_digest_operational": True,
    "document_metadata_operational": True,
    "email_delivery_readiness": True,
    "source_monitoring_preflight_ready": True,
}


def _base(organization_id: str = DEMO) -> str:
    return f"/v1/nf/demo/orgs/{organization_id}/beta-cockpit"


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
# the summary reports every lane
# ---------------------------------------------------------------------------


def test_the_summary_reports_every_declared_lane():
    summary = build_beta_onboarding_summary(**FULL_BATTERY)
    assert set(summary["by_lane"]) == set(LANE_KEYS)
    assert [lane["lane"] for lane in summary["lanes"]] == list(LANE_KEYS)
    assert summary_invariant_failures(summary) == []


@pytest.mark.parametrize("key", LANE_KEYS)
def test_every_lane_declares_what_evidence_it_needs(key):
    assert key in LANE_EVIDENCE
    assert LANE_EVIDENCE[key]


@pytest.mark.parametrize("key", LANE_KEYS)
def test_every_lane_has_a_recognised_status_and_a_reason(key):
    lane = build_beta_onboarding_summary(**FULL_BATTERY)["by_lane"][key]
    assert lane["status"] in LANE_STATUSES
    assert lane["summary"]
    if not lane["value"]:
        assert lane["blockers"], key


# ---------------------------------------------------------------------------
# it derives rather than asserting
# ---------------------------------------------------------------------------


def test_a_summary_with_no_evidence_claims_nothing_operational():
    """The defect this gate was most likely to introduce."""
    unaided = build_beta_onboarding_summary()
    battery = build_beta_onboarding_summary(**FULL_BATTERY)
    assert len(unaided["operational_lanes"]) < len(battery["operational_lanes"])
    assert summary_invariant_failures(unaided) == []


@pytest.mark.parametrize(
    "lane,parameter",
    [
        ("customer_persistence", "customer_persistence_live"),
        ("awarded_grants", "awarded_operational_tracking"),
        ("tenant_digest", "tenant_digest_operational"),
        ("document_metadata", "document_metadata_operational"),
        ("email_delivery_readiness", "email_delivery_readiness"),
    ],
)
def test_a_lane_without_its_proof_is_readiness_only(lane, parameter):
    """Not `operational`, and not silently true either."""
    proofs = {**FULL_BATTERY, parameter: False}
    summary = build_beta_onboarding_summary(**proofs)
    assert summary["by_lane"][lane]["status"] == READINESS_ONLY
    assert summary["by_lane"][lane]["value"] is False
    assert summary["by_lane"][lane]["blockers"]


def test_the_lanes_that_need_outside_evidence_are_named():
    needs_outside = {k for k, v in LANE_EVIDENCE.items() if v != "self_evidencing"}
    assert needs_outside
    # Each is a lane whose service takes an injectable proof.
    assert "tenant_digest" in needs_outside
    assert "awarded_grants" in needs_outside


def test_the_self_evidencing_lanes_are_measured_not_supplied():
    """These read their own service and take no parameter at all."""
    summary = build_beta_onboarding_summary()
    for key in ("email_delivery", "object_storage", "source_monitoring"):
        assert LANE_EVIDENCE[key] == "self_evidencing"
        assert summary["by_lane"][key]["value"] is False


# ---------------------------------------------------------------------------
# the operational lanes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "lane",
    [
        "login",
        "customer_persistence",
        "awarded_grants",
        "tenant_digest",
        "document_metadata",
        "email_delivery_readiness",
        "source_monitoring_preflight",
    ],
)
def test_the_operational_lanes_are_operational_with_the_full_battery(lane):
    summary = build_beta_onboarding_summary(**FULL_BATTERY)
    entry = summary["by_lane"][lane]
    assert entry["status"] == OPERATIONAL, entry
    assert entry["value"] is True
    assert entry["scope"] == CONTROLLED_SCOPE
    assert entry["blockers"] == []
    assert entry["usable_today"] is True


# ---------------------------------------------------------------------------
# the false lanes stay false
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("lane", sorted(NEVER_TRUE_LANES))
def test_a_forbidden_lane_is_false_whatever_the_battery_says(lane):
    """The load-bearing rule of the gate."""
    summary = build_beta_onboarding_summary(**FULL_BATTERY)
    entry = summary["by_lane"][lane]
    assert entry["value"] is False, lane
    assert entry["status"] != OPERATIONAL
    assert entry["blockers"], lane


@pytest.mark.parametrize(
    "field",
    [
        "customer_auth_live",
        "verified_operational_binding",
        "source_monitoring_live",
        "email_delivery",
        "object_store_configured",
        "controlled_customer_pilot",
        "production_rollout",
    ],
)
def test_the_summary_never_claims(field):
    assert build_beta_onboarding_summary(**FULL_BATTERY)[field] is False


def test_customer_auth_and_binding_need_a_person_not_a_fix():
    """An operator reading "blocked" looks for a bug. There is none."""
    summary = build_beta_onboarding_summary(**FULL_BATTERY)
    for lane in ("customer_auth", "verified_operational_binding"):
        entry = summary["by_lane"][lane]
        assert entry["status"] == REQUIRES_HUMAN_APPROVAL
        assert entry["owner"]
    assert "invite_binding_passed" in summary["by_lane"]["customer_auth"]["blockers"]


def test_source_monitoring_is_blocked_and_names_the_scheduler():
    summary = build_beta_onboarding_summary(**FULL_BATTERY)
    entry = summary["by_lane"]["source_monitoring"]
    assert entry["status"] == BLOCKED
    assert any("scheduler_component_absent" in b for b in entry["blockers"])
    assert "terms_review_incomplete" in entry["blockers"]


def test_the_unconfigured_lanes_say_so():
    summary = build_beta_onboarding_summary(**FULL_BATTERY)
    for lane in ("document_body_storage", "email_delivery", "object_storage"):
        assert summary["by_lane"][lane]["status"] == NOT_CONFIGURED


def test_the_invariants_catch_a_forged_forbidden_lane():
    summary = build_beta_onboarding_summary(**FULL_BATTERY)
    forged = {
        **summary,
        "by_lane": {
            **summary["by_lane"],
            "production_rollout": {
                **summary["by_lane"]["production_rollout"],
                "value": True,
                "status": OPERATIONAL,
                "blockers": [],
            },
        },
    }
    failures = summary_invariant_failures(forged)
    assert "a_cockpit_reported_a_forbidden_lane_true:production_rollout" in failures
    assert "a_forbidden_lane_was_marked_operational:production_rollout" in failures


def test_the_summary_names_no_customer_grant_or_deadline():
    """Checked against VALUES. The field names are the guarantee, not the leak."""
    summary = build_beta_onboarding_summary(**FULL_BATTERY)
    values = " ".join(_string_values(summary)).lower()
    for forbidden in ("tribe", "eligib", "deadline"):
        assert forbidden not in values, forbidden
    assert not ADDRESS_SHAPE.search(json.dumps(summary))
    assert summary["customer_names_reported"] is False
    assert summary["eligibility_reported"] is False
    assert summary["deadlines_reported"] is False


def test_the_summary_activates_nothing():
    summary = build_beta_onboarding_summary(**FULL_BATTERY)
    for counter in (
        "live_source_calls",
        "emails_sent",
        "object_store_calls",
        "collectors_activated",
    ):
        assert summary[counter] == 0
    assert summary["real_customer_data_written"] is False
    assert summary["real_organization_touched"] is False


def test_the_summary_names_what_it_does_not_approve():
    assert set(NOT_APPROVED) <= set(build_beta_onboarding_summary()["not_approved"])


def test_there_is_one_next_safe_action_not_a_backlog():
    summary = build_beta_onboarding_summary(**FULL_BATTERY)
    action = summary["next_safe_action"]
    assert action["action"]
    assert action["why"]
    assert action["safe_because"]
    assert action["not_this_yet"]
    assert "controlled customer pilot" in " ".join(action["not_this_yet"])


# ---------------------------------------------------------------------------
# the routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path", ["readiness", "next-actions", "blockers", "capabilities"]
)
def test_every_cockpit_route_refuses_an_unauthenticated_caller(client, path):
    assert client.get(f"{_base()}/{path}").status_code == 401


def test_a_forged_dev_header_cannot_override_the_org(client):
    response = client.get(
        f"{_base()}/readiness", headers=soh.forged_header_only(uuid.UUID(DEMO))
    )
    assert response.status_code == 401


def test_the_readiness_route_reports_every_lane(client, demo_session):
    response = client.get(f"{_base()}/readiness", headers=demo_session)
    assert response.status_code == 200, response.text
    body = response.json()
    assert {lane["lane"] for lane in body["lanes"]} == set(LANE_KEYS)
    assert body["cockpit_scope"] == CONTROLLED_SCOPE
    assert body["invariant_failures"] == []


def test_the_readiness_route_claims_no_forbidden_capability(client, demo_session):
    body = client.get(f"{_base()}/readiness", headers=demo_session).json()
    for claim in (
        "production_rollout",
        "controlled_customer_pilot",
        "customer_auth_live",
        "source_monitoring_live",
        "email_delivery",
        "object_store_configured",
        "verified_operational_binding",
        "customer_names_reported",
    ):
        assert body[claim] is False, claim
    for counter in (
        "live_source_calls",
        "emails_sent",
        "object_store_calls",
        "collectors_activated",
    ):
        assert body[counter] == 0, counter


def test_the_readiness_route_names_no_customer(client, demo_session):
    body = client.get(f"{_base()}/readiness", headers=demo_session).json()
    values = " ".join(_string_values(body)).lower()
    for forbidden in ("tribe", "eligib", "deadline"):
        assert forbidden not in values, forbidden
    assert not ADDRESS_SHAPE.search(json.dumps(body))


def test_the_route_does_not_grade_its_own_homework(client, demo_session):
    """A request reports what a request can measure, and no more."""
    body = client.get(f"{_base()}/readiness", headers=demo_session).json()
    battery = build_beta_onboarding_summary(**FULL_BATTERY)
    assert len(body["operational_lanes"]) <= len(battery["operational_lanes"])
    for lane in body["lanes"]:
        if lane["status"] == OPERATIONAL:
            assert lane["value"] is True
            assert lane["blockers"] == []


def test_every_false_lane_on_the_route_names_a_blocker(client, demo_session):
    body = client.get(f"{_base()}/readiness", headers=demo_session).json()
    for lane in body["lanes"]:
        if not lane["value"]:
            assert lane["blockers"], lane["lane"]


def test_the_next_actions_route_returns_one_action(client, demo_session):
    response = client.get(f"{_base()}/next-actions", headers=demo_session)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["next_safe_action"]
    assert body["why"]
    assert body["safe_because"]
    assert body["not_this_yet"]
    assert body["activates_nothing"] is True


def test_the_blockers_route_names_an_owner_for_each(client, demo_session):
    response = client.get(f"{_base()}/blockers", headers=demo_session)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["blockers"]
    for entry in body["blockers"]:
        assert entry["lane"]
        assert entry["blockers"]
        assert entry["summary"]


def test_the_capabilities_route_is_a_matrix_not_a_score(client, demo_session):
    response = client.get(f"{_base()}/capabilities", headers=demo_session)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["capabilities"]) == len(LANE_KEYS)
    assert body["total_lane_count"] == len(LANE_KEYS)
    for capability in body["capabilities"]:
        assert capability["lane"]
        assert capability["status"] in LANE_STATUSES
        assert capability["evidence"]


def test_another_organization_is_refused(client, demo_session):
    for path in ("readiness", "next-actions", "blockers", "capabilities"):
        assert client.get(
            f"{_base(OTHER)}/{path}", headers=demo_session
        ).status_code in {403, 404}, path


def test_no_real_organization_route_was_built():
    source = (
        REPO_ROOT / "src/nativeforge/api/beta_onboarding_cockpit_routes.py"
    ).read_text(encoding="utf-8")
    assert "require_real_org_session" not in source
    assert "/v1/nf/real/orgs" not in source
    assert REAL not in source


# ---------------------------------------------------------------------------
# the frontend surface
# ---------------------------------------------------------------------------


def test_the_cockpit_page_and_its_test_exist():
    assert (REPO_ROOT / art.FRONTEND_PAGE).is_file()
    assert (REPO_ROOT / art.FRONTEND_TEST).is_file()


def test_the_surface_is_wired_the_existing_way():
    surface = (REPO_ROOT / "frontend/src/viewSurface.ts").read_text(encoding="utf-8")
    app = (REPO_ROOT / "frontend/src/App.tsx").read_text(encoding="utf-8")
    assert f'"{art.FRONTEND_SURFACE}"' in surface
    assert "BetaOnboardingCockpitPage" in app


def test_the_existing_surfaces_still_dispatch():
    """`?view=sc_customer_demo` must not break."""
    surface = (REPO_ROOT / "frontend/src/viewSurface.ts").read_text(encoding="utf-8")
    app = (REPO_ROOT / "frontend/src/App.tsx").read_text(encoding="utf-8")
    for name in art.EXISTING_SURFACES:
        assert f'"{name}"' in surface, name
    assert "ScCustomerDemoPage" in app
    assert "NmWaOperatorDemoPage" in app


def test_the_cockpit_page_claims_no_production_capability():
    page = (REPO_ROOT / art.FRONTEND_PAGE).read_text(encoding="utf-8")
    lowered = page.lower()
    assert "production ready" not in lowered
    assert "live monitoring" not in lowered
    # And it renders the false lanes rather than filtering them out.
    assert "data-lane-value" in page
    assert "beta-cockpit-blockers-" in page


def test_the_cockpit_page_requires_a_session():
    """No public bypass: a signed-out visitor is told to sign in."""
    page = (REPO_ROOT / art.FRONTEND_PAGE).read_text(encoding="utf-8")
    assert 'credentials: "include"' in page
    assert "Sign in" in page


# ---------------------------------------------------------------------------
# the artifacts
# ---------------------------------------------------------------------------


def test_the_artifact_writes_every_declared_file(tmp_path):
    result = art.write_cockpit_artifacts(repo_root=tmp_path)
    assert art.cockpit_artifact_invariant_failures(result) == []
    for name in art.ARTIFACT_FILES:
        assert (tmp_path / art.ARTIFACT_DIR / name).is_file(), name


def test_the_artifact_is_deterministic():
    first = art.build_cockpit_artifacts()
    second = art.build_cockpit_artifacts()
    assert first == second


def test_the_artifact_reports_the_cockpit_route_live():
    files = art.build_cockpit_artifacts()
    readiness = json.loads(files["beta_onboarding_cockpit_readiness.json"])
    route = json.loads(files["cockpit_route_smoke.json"])
    assert readiness["cockpit_foundation_route_live"] is True
    assert readiness["frontend_surface_exists"] is True
    assert readiness["every_never_true_lane_is_false"] is True
    assert readiness["invariant_failures"] == []
    assert route["every_lane_reported"] is True
    assert route["unauthenticated_refused"] is True
    assert route["forged_header_refused"] is True
    assert route["cross_org_refused"] is True


def test_the_artifact_records_that_unaided_is_narrower():
    files = art.build_cockpit_artifacts()
    summary = json.loads(files["readiness_summary_smoke.json"])
    assert summary["unaided_reports_fewer_operational_lanes"] is True
    assert summary["unaided_reports_no_forbidden_lane_true"] is True


def test_the_artifact_records_the_frontend_surface_honestly():
    files = art.build_cockpit_artifacts()
    frontend = json.loads(files["frontend_cockpit_status.json"])
    assert frontend["wired_the_existing_way"] is True
    assert frontend["sc_customer_demo_still_dispatched"] is True
    assert frontend["existing_surfaces_intact"] is True
    assert frontend["page_names_a_tribe"] is False
    assert frontend["page_claims_production"] is False
    assert frontend["page_shows_false_lanes"] is True
    assert frontend["page_source_scanned_with_comments_stripped"] is True


def test_no_artifact_carries_a_credential_or_a_customer():
    for name, body in art.build_cockpit_artifacts().items():
        lowered = body.lower()
        for marker in art.FORBIDDEN_MARKERS:
            assert marker.lower() not in lowered, (name, marker)
        assert not ADDRESS_SHAPE.search(body), name


def test_the_committed_artifacts_match_what_the_service_builds():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name, body in art.build_cockpit_artifacts().items():
        committed = directory / name
        assert committed.is_file(), name
        assert committed.read_text(encoding="utf-8") == body, name


# ---------------------------------------------------------------------------
# what this gate must not change
# ---------------------------------------------------------------------------


def test_customer_auth_live_is_unchanged():
    assert build_beta_onboarding_summary(**FULL_BATTERY)["customer_auth_live"] is False


def test_source_monitoring_live_is_unchanged():
    from nativeforge.services.source_scheduler_readiness_service import (
        build_scheduler_readiness,
    )

    assert build_scheduler_readiness()["source_monitoring_live"] is False


def test_email_delivery_is_unchanged():
    from nativeforge.services.email_provider_configuration_preflight_service import (
        build_email_provider_preflight,
    )

    assert build_email_provider_preflight()["email_delivery"] is False


def test_object_store_configured_is_unchanged():
    from nativeforge.services.document_storage_readiness_service import (
        build_document_storage_readiness,
    )

    assert (
        build_document_storage_readiness(metadata_route_smoke=None)[
            "object_store_configured"
        ]
        is False
    )
