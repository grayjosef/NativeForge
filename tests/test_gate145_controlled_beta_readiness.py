"""Gate 145: the controlled beta decision matrix, and what it may never say.

The block closes by answering one question — can a controlled customer beta
start? — for three scopes that differ not in how much software works but in
**who is on the other side**.

The five conflations this gate exists to prevent, each of which reads as the
same thing to anyone who has not followed the gates:

```text
email_delivery_readiness          is not  email_delivery
source_monitoring_preflight_ready is not  source_monitoring_live
document_metadata_operational     is not  document_body_storage_ready
customer_persistence_live         is not  customer_auth_live
the demo organization             is not  a customer organization
```
"""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from nativeforge.main import create_app
from nativeforge.services import controlled_beta_artifact_gate145_service as art
from nativeforge.services.controlled_beta_readiness_decision_service import (
    CONFLATIONS,
    CONTROLLED_CUSTOMER_BETA,
    CUSTOMER_BETA_CONDITIONS,
    GO,
    HUMAN_APPROVALS,
    INTERNAL_DEMO_BETA,
    INTERNAL_DEMO_CONDITIONS,
    INTERNAL_DEMO_MUST_BE_FALSE,
    LIMITED_GO,
    NO_GO,
    PRODUCTION_ROLLOUT,
    SCOPES,
    TECHNICAL_BLOCKERS,
    UNSAFE_CLAIMS,
    build_controlled_beta_decision,
    decision_invariant_failures,
)
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER = "cccccccc-dddd-eeee-ffff-00000000d145"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

REPO_ROOT = Path(__file__).resolve().parents[1]
ADDRESS_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")

FULL_BATTERY = dict(art.FULL_BATTERY)


def _base(organization_id: str = DEMO) -> str:
    return f"/v1/nf/demo/orgs/{organization_id}/beta-decision"


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
# three scopes, decided separately
# ---------------------------------------------------------------------------


def test_the_decision_covers_all_three_scopes():
    decision = build_controlled_beta_decision(**FULL_BATTERY)
    assert set(decision["by_scope"]) == set(SCOPES)
    assert decision_invariant_failures(decision) == []


def test_internal_demo_is_go_with_the_full_battery():
    decision = build_controlled_beta_decision(**FULL_BATTERY)
    entry = decision["by_scope"][INTERNAL_DEMO_BETA]
    assert entry["decision"] == GO
    assert entry["blockers"] == []
    assert entry["constraints"]
    assert set(entry["conditions_met"]) == set(INTERNAL_DEMO_CONDITIONS)


@pytest.mark.parametrize("condition", INTERNAL_DEMO_CONDITIONS)
def test_internal_demo_is_limited_without_each_condition(condition):
    decision = build_controlled_beta_decision(**{**FULL_BATTERY, condition: False})
    entry = decision["by_scope"][INTERNAL_DEMO_BETA]
    assert entry["decision"] == LIMITED_GO
    assert f"condition_not_met:{condition}" in entry["blockers"]


def test_internal_demo_is_no_go_with_nothing_proved():
    decision = build_controlled_beta_decision()
    assert decision["by_scope"][INTERNAL_DEMO_BETA]["decision"] == NO_GO
    assert decision_invariant_failures(decision) == []


def test_a_demo_that_switched_a_capability_on_would_not_be_a_demo():
    """`INTERNAL_DEMO_MUST_BE_FALSE` is the honesty condition, not a nicety."""
    assert "source_monitoring_live" in INTERNAL_DEMO_MUST_BE_FALSE
    assert "email_delivery" in INTERNAL_DEMO_MUST_BE_FALSE
    assert "production_rollout" in INTERNAL_DEMO_MUST_BE_FALSE
    decision = build_controlled_beta_decision(**FULL_BATTERY)
    measured = decision["measured_capabilities"]
    for name in INTERNAL_DEMO_MUST_BE_FALSE:
        assert measured[name] is False, name


# ---------------------------------------------------------------------------
# the customer beta cannot be unconditional
# ---------------------------------------------------------------------------


def test_controlled_customer_beta_is_limited_go_not_go():
    decision = build_controlled_beta_decision(**FULL_BATTERY)
    entry = decision["by_scope"][CONTROLLED_CUSTOMER_BETA]
    assert entry["decision"] == LIMITED_GO
    assert entry["blockers"]
    assert entry["constraints"]


def test_controlled_customer_beta_cannot_be_go_while_customer_auth_is_false():
    """The load-bearing rule. Every condition but the auth one, and still not GO."""
    decision = build_controlled_beta_decision(
        **FULL_BATTERY,
        verified_operational_binding=True,
        consent_and_data_boundary_documented=True,
        customer_beta_scope_approved=True,
    )
    entry = decision["by_scope"][CONTROLLED_CUSTOMER_BETA]
    assert entry["decision"] == LIMITED_GO
    assert "approval_absent:customer_auth_live" in entry["blockers"]


def test_the_customer_beta_go_branch_is_reachable():
    """Otherwise every refusal above it is unfalsifiable — Gate 134F's lesson."""
    decision = build_controlled_beta_decision(
        **FULL_BATTERY,
        customer_auth_live=True,
        verified_operational_binding=True,
        consent_and_data_boundary_documented=True,
        customer_beta_scope_approved=True,
    )
    entry = decision["by_scope"][CONTROLLED_CUSTOMER_BETA]
    assert entry["decision"] == GO
    assert entry["blockers"] == []
    assert decision_invariant_failures(decision) == []


@pytest.mark.parametrize("condition", CUSTOMER_BETA_CONDITIONS)
def test_the_customer_beta_needs_every_condition(condition):
    approvals = dict.fromkeys(CUSTOMER_BETA_CONDITIONS, True)
    approvals[condition] = False
    decision = build_controlled_beta_decision(**FULL_BATTERY, **approvals)
    entry = decision["by_scope"][CONTROLLED_CUSTOMER_BETA]
    assert entry["decision"] == LIMITED_GO
    assert f"approval_absent:{condition}" in entry["blockers"]


def test_the_customer_beta_is_no_go_if_the_internal_one_is():
    decision = build_controlled_beta_decision(
        customer_auth_live=True,
        verified_operational_binding=True,
        consent_and_data_boundary_documented=True,
        customer_beta_scope_approved=True,
    )
    assert decision["by_scope"][CONTROLLED_CUSTOMER_BETA]["decision"] == NO_GO


def test_the_demo_org_is_not_a_customer_org():
    decision = build_controlled_beta_decision(**FULL_BATTERY)
    constraints = " ".join(
        decision["by_scope"][CONTROLLED_CUSTOMER_BETA]["constraints"]
    )
    assert "demo organization scope only" in constraints
    conflation = [c for c in CONFLATIONS if "demo organization" in c["readiness"]]
    assert conflation, "the demo/customer org conflation must be named"


# ---------------------------------------------------------------------------
# production is NO_GO, always
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "approvals",
    [
        {},
        dict.fromkeys(CUSTOMER_BETA_CONDITIONS, True),
    ],
)
def test_production_rollout_is_no_go_whatever_is_supplied(approvals):
    decision = build_controlled_beta_decision(**FULL_BATTERY, **approvals)
    assert decision["by_scope"][PRODUCTION_ROLLOUT]["decision"] == NO_GO
    assert decision["production_rollout"] == NO_GO
    assert decision["production_approved"] is False


def test_the_invariants_catch_a_forged_production_go():
    decision = build_controlled_beta_decision(**FULL_BATTERY)
    forged = {
        **decision,
        "production_rollout": GO,
        "by_scope": {
            **decision["by_scope"],
            PRODUCTION_ROLLOUT: {
                **decision["by_scope"][PRODUCTION_ROLLOUT],
                "decision": GO,
                "blockers": [],
            },
        },
    }
    failures = decision_invariant_failures(forged)
    assert f"a_never_go_scope_was_not_no_go:{PRODUCTION_ROLLOUT}" in failures
    assert "production_rollout_was_not_no_go:GO" in failures


def test_the_invariants_catch_an_unconditional_customer_go():
    decision = build_controlled_beta_decision(**FULL_BATTERY)
    forged = {
        **decision,
        "by_scope": {
            **decision["by_scope"],
            CONTROLLED_CUSTOMER_BETA: {
                **decision["by_scope"][CONTROLLED_CUSTOMER_BETA],
                "decision": GO,
                "blockers": [],
            },
        },
    }
    assert (
        f"unconditional_go_without_customer_auth:{CONTROLLED_CUSTOMER_BETA}"
        in decision_invariant_failures(forged)
    )


# ---------------------------------------------------------------------------
# the five conflations
# ---------------------------------------------------------------------------


def test_every_conflation_is_named_with_its_difference():
    assert len(CONFLATIONS) == 5
    for conflation in CONFLATIONS:
        assert conflation["readiness"]
        assert conflation["capability"]
        assert conflation["difference"]


def test_readiness_is_not_treated_as_capability():
    """Every readiness flag true, and every capability beside it still false."""
    decision = build_controlled_beta_decision(**FULL_BATTERY)
    measured = decision["measured_capabilities"]
    supplied = decision["supplied_readiness"]

    assert supplied["email_delivery_readiness"] is True
    assert measured["email_delivery"] is False

    assert supplied["source_monitoring_preflight_ready"] is True
    assert measured["source_monitoring_live"] is False

    assert supplied["document_metadata_operational"] is True
    assert measured["document_body_storage_ready"] is False

    assert supplied["customer_persistence_live"] is True
    assert measured["customer_auth_live"] is False


def test_the_capability_flags_are_measured_not_supplied():
    """A caller cannot hand this service a capability it did not measure."""
    import inspect

    signature = inspect.signature(build_controlled_beta_decision)
    for capability in (
        "email_delivery",
        "source_monitoring_live",
        "object_store_configured",
        "document_body_storage_ready",
    ):
        assert capability not in signature.parameters, capability


# ---------------------------------------------------------------------------
# the lists
# ---------------------------------------------------------------------------


def test_the_unsafe_claims_are_listed_with_a_true_alternative():
    assert len(UNSAFE_CLAIMS) >= 7
    for claim in UNSAFE_CLAIMS:
        assert claim["claim"]
        assert claim["why_unsafe"]
        assert claim["true_statement"]


def test_the_unsafe_claims_include_the_ones_that_matter():
    claims = " ".join(c["claim"] for c in UNSAFE_CLAIMS).lower()
    for forbidden in ("monitor grant sources", "digest by email", "65%"):
        assert forbidden in claims, forbidden


def test_the_human_approvals_name_an_owner_and_a_reason():
    assert len(HUMAN_APPROVALS) >= 8
    for approval in HUMAN_APPROVALS:
        assert approval["approval"]
        assert approval["unlocks"]
        assert approval["owner"]
        assert approval["why_not_automatable"]


def test_the_technical_blockers_are_separate_from_the_approvals():
    """An operator needs to know whether to write code or to decide."""
    assert len(TECHNICAL_BLOCKERS) >= 5
    approval_texts = {a["approval"] for a in HUMAN_APPROVALS}
    for blocker in TECHNICAL_BLOCKERS:
        assert blocker["blocker"]
        assert blocker["blocks"]
        assert blocker["blocker"] not in approval_texts


def test_no_improvement_figure_is_claimed():
    decision = build_controlled_beta_decision(**FULL_BATTERY)
    assert decision["improvement_claims"] == []
    # And the prohibition is recorded, so it can be refused rather than found.
    assert any("65%" in c["claim"] for c in UNSAFE_CLAIMS)


# ---------------------------------------------------------------------------
# nothing is activated
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "field",
    [
        "controlled_customer_pilot_activated",
        "production_approved",
        "real_customer_data_written",
        "real_organization_touched",
        "customer_names_reported",
    ],
)
def test_the_decision_never_claims(field):
    assert build_controlled_beta_decision(**FULL_BATTERY)[field] is False


def test_the_decision_activates_nothing():
    decision = build_controlled_beta_decision(**FULL_BATTERY)
    for counter in (
        "live_source_calls",
        "emails_sent",
        "object_store_calls",
        "collectors_activated",
    ):
        assert decision[counter] == 0


def test_the_decision_names_no_customer():
    decision = build_controlled_beta_decision(**FULL_BATTERY)
    assert not ADDRESS_SHAPE.search(json.dumps(decision))
    assert REAL not in json.dumps(decision)


# ---------------------------------------------------------------------------
# the routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "path", ["readiness", "blockers", "unsafe-claims", "approvals"]
)
def test_every_route_refuses_an_unauthenticated_caller(client, path):
    assert client.get(f"{_base()}/{path}").status_code == 401


def test_a_forged_dev_header_cannot_override_the_org(client):
    response = client.get(
        f"{_base()}/readiness", headers=soh.forged_header_only(uuid.UUID(DEMO))
    )
    assert response.status_code == 401


def test_the_readiness_route_decides_all_three_scopes(client, demo_session):
    response = client.get(f"{_base()}/readiness", headers=demo_session)
    assert response.status_code == 200, response.text
    body = response.json()
    assert set(body["by_scope"]) == set(SCOPES)
    assert body["production_rollout"] == NO_GO
    assert body["invariant_failures"] == []


def test_the_readiness_route_claims_nothing_forbidden(client, demo_session):
    body = client.get(f"{_base()}/readiness", headers=demo_session).json()
    for claim in (
        "controlled_customer_pilot_activated",
        "production_approved",
        "customer_auth_live",
        "source_monitoring_live",
        "email_delivery",
        "object_store_configured",
        "real_customer_data_written",
    ):
        assert body[claim] is False, claim
    for counter in (
        "live_source_calls",
        "emails_sent",
        "object_store_calls",
        "collectors_activated",
    ):
        assert body[counter] == 0, counter


def test_the_blockers_route_separates_code_from_decisions(client, demo_session):
    response = client.get(f"{_base()}/blockers", headers=demo_session)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["technical_blockers"]
    assert body["human_approvals_required"]


def test_the_unsafe_claims_route_lists_them(client, demo_session):
    response = client.get(f"{_base()}/unsafe-claims", headers=demo_session)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["unsafe_claim_count"] >= 7
    assert body["conflation_count"] == 5
    assert body["improvement_claims"] == []


def test_the_approvals_route_grants_none(client, demo_session):
    response = client.get(f"{_base()}/approvals", headers=demo_session)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["approval_count"] >= 8
    assert body["none_of_these_is_automatable"] is True
    assert body["approvals_granted_by_this_route"] == 0
    assert body["production_approved"] is False


def test_another_organization_is_refused(client, demo_session):
    for path in ("readiness", "blockers", "unsafe-claims", "approvals"):
        assert client.get(
            f"{_base(OTHER)}/{path}", headers=demo_session
        ).status_code in {403, 404}, path


def test_no_real_organization_route_was_built():
    source = (
        REPO_ROOT / "src/nativeforge/api/controlled_beta_readiness_routes.py"
    ).read_text(encoding="utf-8")
    assert "require_real_org_session" not in source
    assert "/v1/nf/real/orgs" not in source
    assert REAL not in source


# ---------------------------------------------------------------------------
# the cockpit does not claim production
# ---------------------------------------------------------------------------


def test_the_cockpit_page_shows_the_decision_and_no_production_claim():
    page = (REPO_ROOT / "frontend/src/pages/BetaOnboardingCockpitPage.tsx").read_text(
        encoding="utf-8"
    )
    assert "beta-decision" in page
    assert "NO-GO" in page
    lowered = page.lower()
    assert "production ready" not in lowered
    assert "live monitoring" not in lowered


def test_the_cockpit_renders_the_constraints_on_a_limited_go():
    page = (REPO_ROOT / "frontend/src/pages/BetaOnboardingCockpitPage.tsx").read_text(
        encoding="utf-8"
    )
    assert "beta-decision-constraints-" in page
    assert "beta-decision-blockers-" in page


# ---------------------------------------------------------------------------
# the artifacts
# ---------------------------------------------------------------------------


def test_the_artifact_writes_every_declared_file(tmp_path):
    result = art.write_controlled_beta_artifacts(repo_root=tmp_path)
    assert art.controlled_beta_artifact_invariant_failures(result) == []
    for name in art.ARTIFACT_FILES:
        assert (tmp_path / art.ARTIFACT_DIR / name).is_file(), name


def test_the_artifact_is_deterministic():
    first = art.build_controlled_beta_artifacts()
    second = art.build_controlled_beta_artifacts()
    assert first == second


def test_the_artifact_records_the_three_verdicts():
    files = art.build_controlled_beta_artifacts()
    matrix = json.loads(files["controlled_beta_decision_matrix.json"])
    assert matrix["internal_demo_beta"] == GO
    assert matrix["controlled_customer_beta"] == LIMITED_GO
    assert matrix["production_rollout"] == NO_GO
    assert matrix["invariant_failures"] == []
    assert matrix["unaided_is_never_more_permissive"] is True


def test_the_artifact_says_why_the_customer_beta_is_limited():
    files = art.build_controlled_beta_artifacts()
    customer = json.loads(files["controlled_customer_beta_decision.json"])
    assert customer["is_unconditional_go"] is False
    assert "customer_auth_live" in customer["cannot_be_unconditional_go_because"]
    assert customer["what_limited_go_does_not_permit"]


def test_the_artifact_records_production_as_always_no_go():
    files = art.build_controlled_beta_artifacts()
    production = json.loads(files["production_rollout_decision.json"])
    assert production["decision"] == NO_GO
    assert production["decision_is_always"] == NO_GO
    assert production["no_branch_returns_anything_else"] is True
    assert production["production_approved"] is False


def test_the_artifact_records_the_prohibited_claims():
    files = art.build_controlled_beta_artifacts()
    claims = json.loads(files["unsafe_claims_to_avoid.json"])
    assert claims["unsafe_claim_count"] >= 7
    assert claims["each_paired_with_a_true_statement"] is True
    assert claims["improvement_claims"] == []
    # The inventory must actually record the prohibition it exists for.
    assert any("65%" in c["claim"] for c in claims["unsafe_claims"])


def test_the_artifact_records_the_approvals_and_the_blockers():
    files = art.build_controlled_beta_artifacts()
    approvals = json.loads(files["human_approval_checklist.json"])
    blockers = json.loads(files["technical_blockers_remaining.json"])
    assert approvals["none_is_automatable"] is True
    assert approvals["approvals_granted_by_this_gate"] == 0
    assert approvals["each_names_an_owner"] is True
    assert blockers["blocker_count"] >= 5
    assert blockers["each_names_what_it_blocks"] is True


def test_no_artifact_carries_a_credential_or_a_customer():
    files = art.build_controlled_beta_artifacts()
    for name, body in files.items():
        assert not ADDRESS_SHAPE.search(body), name
        if name == art.CLAIM_INVENTORY_FILE:
            # The do-not-say list is exempt from the marker scan by design, and
            # is required to carry the prohibition instead.
            assert "65%" in body
            continue
        lowered = body.lower()
        for marker in art.FORBIDDEN_MARKERS:
            assert marker.lower() not in lowered, (name, marker)


def test_the_committed_artifacts_match_what_the_service_builds():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name, body in art.build_controlled_beta_artifacts().items():
        committed = directory / name
        assert committed.is_file(), name
        assert committed.read_text(encoding="utf-8") == body, name


# ---------------------------------------------------------------------------
# what this gate must not change
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "capability",
    [
        "customer_auth_live",
        "source_monitoring_live",
        "email_delivery",
        "object_store_configured",
    ],
)
def test_no_capability_flag_changed(capability):
    assert build_controlled_beta_decision(**FULL_BATTERY)[capability] is False
