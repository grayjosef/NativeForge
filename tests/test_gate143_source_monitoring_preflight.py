"""Gate 143: source monitoring preflight, without calling a source.

Doc 746 found the fact that shapes this gate: the registry has **no terms
column**. It carries a url, a tier, an adapter key, an access posture, a health
status and a resolver status — and nothing about what any publisher's terms say.

So an unreviewed row is `UNKNOWN`, and `live_network_guard_service` already puts
`UNKNOWN` in `TERMS_BLOCKING`. Deny by default is what the registry actually
supports rather than a rule imposed on it.

The claims the gate is forbidden from making get their own tests and their own
reachable branches:

```text
preflight readiness is not monitoring, and a preflight may never activate one
no live source is called, and no monitoring module imports a network client
an approval never clears a terms blocker
a fixture source is never monitorable
`urllib.parse` is not a network client and `urllib.request` is
```
"""

from __future__ import annotations

import ast
import json
import uuid
from pathlib import Path

import pytest
import sqlalchemy as sa
from fastapi.testclient import TestClient

from nativeforge.main import create_app
from nativeforge.services import source_monitoring_artifact_gate143_service as art
from nativeforge.services import tenant_source_watchlist_service as watchlist
from nativeforge.services.source_collector_configuration_preflight_service import (
    LIVE_CAPABLE_PAYLOAD_POLICIES,
    REQUIRED_CONFIG_KEYS,
    build_collector_preflight,
    collector_preflight_invariant_failures,
)
from nativeforge.services.source_monitoring_approved_source_service import (
    ACTIVATION_APPROVED,
    API_KEY_MISSING,
    EVALUATION_STATES,
    FIXTURE_ALLOWED,
    FIXTURE_SOURCE_PREFIX,
    HUMAN_REVIEW_BLOCKED,
    TERMS_BLOCKED,
    UNKNOWN_SOURCE,
    allowlist_invariant_failures,
    evaluate_registry,
    evaluate_source,
    load_registry_rows,
)
from nativeforge.services.source_monitoring_readiness_service import (
    CONTROLLED_SCOPE,
    MONITORING_MODULES,
    NOT_APPROVED,
    SCOPE_NONE,
    _is_network_module,
    build_source_monitoring_readiness,
    detect_network_imports,
    detect_readiness_route_module,
    source_monitoring_readiness_invariant_failures,
)
from tests import session_org_helper as soh

DEMO = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
OTHER = "cccccccc-dddd-eeee-ffff-00000000d143"
REAL = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

REPO_ROOT = Path(__file__).resolve().parents[1]

EXAMPLE_SOURCE = "nf-seed-2026-fed-001"
GRANTS_GOV_SOURCE = "nf-seed-2026-fed-013"
FIXTURE_SOURCE = f"{FIXTURE_SOURCE_PREFIX}gate143-test"

REVIEWED = {EXAMPLE_SOURCE: "NO_REVIEW_REQUIRED"}

#: A SAM.gov-shaped row. The shipped registry has none, and inventing one in
#: the registry would be fabricating a source - so it is supplied per call.
SAM_PROBE = {
    "nf-seed-sam-probe": {
        "seed_id": "nf-seed-sam-probe",
        "canonical_source_id": "nf:source:nf-seed-sam-probe",
        "source_name": "SAM.gov probe row (not in the shipped registry)",
        "source_url": "https://sam.gov/",
        "access_posture_hint": "public",
        "resolver_url_status": "resolved",
        "source_health_status": "healthy",
    }
}

DRY_RUN_COLLECTOR = {
    "source_id": EXAMPLE_SOURCE,
    "fetch_mode": "dry_run",
    "rate_limit_policy": "polite_default",
    "attribution_requirement": "not_required",
    "user_agent_policy": "nativeforge_canonical",
    "raw_payload_storage_policy": "local_dev_ignored",
    "activation_approval": True,
}


def _base(organization_id: str = DEMO) -> str:
    return f"/v1/nf/demo/orgs/{organization_id}/source-monitoring"


def _clear(organization_id: str) -> None:
    from nativeforge.db.session import SessionLocal

    with SessionLocal() as session:
        session.execute(
            sa.text(
                "DELETE FROM nf_source_watchlist_entries WHERE organization_id = :o"
            ),
            {"o": uuid.UUID(organization_id).hex},
        )
        session.commit()


@pytest.fixture
def client():
    return TestClient(create_app(), raise_server_exceptions=False)


@pytest.fixture
def demo_session():
    from nativeforge.db.session import SessionLocal

    soh.ensure_signing_key()
    soh.ensure_org(DEMO, "demo")
    soh.ensure_org(OTHER, "demo")
    identity = soh.ensure_member(DEMO)
    _clear(DEMO)
    _clear(OTHER)
    with SessionLocal() as session:
        watchlist.add_watchlist_entry(
            connection=session.connection(),
            entry_id=uuid.uuid4(),
            organization_id=DEMO,
            source_id=EXAMPLE_SOURCE,
            watchlist_source="registry_entry",
            source_name="Gate 143 test probe",
            jurisdiction="federal",
            fact_status="demo_fixture",
            is_demo=True,
            created_by_identity_id=identity,
        )
        session.commit()
    yield soh.session_headers(uuid.UUID(DEMO))
    _clear(DEMO)
    _clear(OTHER)


# ---------------------------------------------------------------------------
# nothing can reach a source
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("relative", MONITORING_MODULES)
def test_no_monitoring_module_imports_a_network_client(relative):
    """Parsed, not searched. A docstring naming httpx is not an import."""
    tree = ast.parse((REPO_ROOT / relative).read_text(encoding="utf-8"))
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module)
    offenders = sorted(name for name in imported if _is_network_module(name))
    assert not offenders, offenders


def test_the_detector_finds_nothing_and_is_not_simply_blind():
    """A detector that returns nothing because it looks at nothing is useless."""
    found = detect_network_imports()
    assert found["any_network_library_imported"] is False
    assert found["modules_missing"] == []
    # It can still tell the difference.
    assert _is_network_module("urllib.request") is True
    assert _is_network_module("http.client") is True
    assert _is_network_module("httpx") is True
    assert _is_network_module("socket") is True


def test_urllib_parse_is_not_a_network_client():
    """The first version flagged this gate's own allowlist for using urlsplit."""
    assert _is_network_module("urllib.parse") is False
    assert _is_network_module("urllib.robotparser") is False
    assert _is_network_module("json") is False


def test_direct_http_outside_the_chokepoint_is_detected(tmp_path):
    """The detector must catch a real one, not just report clean."""
    offender = tmp_path / MONITORING_MODULES[0]
    offender.parent.mkdir(parents=True, exist_ok=True)
    offender.write_text("import httpx\n", encoding="utf-8")
    for relative in MONITORING_MODULES[1:]:
        path = tmp_path / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("x = 1\n", encoding="utf-8")

    found = detect_network_imports(repo_root=tmp_path)
    assert found["any_network_library_imported"] is True
    assert found["network_imports"][MONITORING_MODULES[0]] == ["httpx"]


def test_the_chokepoint_scan_is_clean():
    from nativeforge.services.hermetic_network_enforcement_service import (
        enforcement_invariant_failures,
        scan_for_network_call_sites,
    )

    scan = scan_for_network_call_sites()
    assert scan["clean"] is True
    assert int(scan["unapproved_count"]) == 0
    assert scan["files_scanned"] > 500
    assert enforcement_invariant_failures(scan) == []


def test_no_real_organization_route_was_built():
    source = (
        REPO_ROOT / "src/nativeforge/api/source_monitoring_readiness_routes.py"
    ).read_text(encoding="utf-8")
    assert "require_real_org_session" not in source
    assert "/v1/nf/real/orgs" not in source
    assert REAL not in source


# ---------------------------------------------------------------------------
# the allowlist
# ---------------------------------------------------------------------------


def test_the_registry_loads_and_is_not_empty():
    """A bare except here once refused every source while looking strict."""
    rows = load_registry_rows()
    assert len(rows) > 100
    assert EXAMPLE_SOURCE in rows
    assert GRANTS_GOV_SOURCE in rows


def test_an_unknown_source_id_is_refused():
    result = evaluate_source(source_id="nf-seed-9999-not-real")
    assert result["state"] == UNKNOWN_SOURCE
    assert result["monitorable"] is False
    assert "source_id_is_not_in_the_source_registry" in result["blocked_reasons"]
    assert allowlist_invariant_failures(result) == []


def test_an_unreviewed_registry_row_is_terms_blocked():
    """The registry has no terms column, so UNKNOWN, so blocking."""
    result = evaluate_source(source_id=EXAMPLE_SOURCE)
    assert result["state"] == TERMS_BLOCKED
    assert result["terms_status"] == "UNKNOWN"
    assert result["monitorable"] is False
    assert "registry_has_no_terms_column_for_this_source" in result["blocked_reasons"]


def test_a_human_review_only_source_is_refused():
    result = evaluate_source(source_id=GRANTS_GOV_SOURCE)
    assert result["state"] == HUMAN_REVIEW_BLOCKED
    assert result["terms_status"] == "HUMAN_REVIEW_ONLY"
    assert result["human_review_required"] is True
    assert result["monitorable"] is False


def test_grants_gov_is_matched_by_domain_not_by_exact_host():
    """simpler.grants.gov, www.grants.gov and grants.gov are one publisher.

    An exact-match host list missed four rows on the first probe.
    """
    rows = load_registry_rows()
    grants_rows = [
        seed_id
        for seed_id, row in rows.items()
        if "grants.gov" in str(row.get("source_url") or "").lower()
    ]
    assert len(grants_rows) >= 4
    for seed_id in grants_rows:
        result = evaluate_source(source_id=seed_id, registry=rows)
        assert result["state"] == HUMAN_REVIEW_BLOCKED, seed_id


def test_a_lookalike_domain_is_not_matched():
    """A suffix test without a label boundary would match evilgrants.gov."""
    result = evaluate_source(
        source_id="nf-seed-lookalike",
        registry={
            "nf-seed-lookalike": {
                "seed_id": "nf-seed-lookalike",
                "source_url": "https://evilgrants.gov/",
                "access_posture_hint": "public",
                "resolver_url_status": "resolved",
                "source_health_status": "healthy",
            }
        },
    )
    assert result["state"] == TERMS_BLOCKED
    assert result["human_review_required"] is False


def test_a_source_needing_a_credential_is_refused():
    result = evaluate_source(source_id="nf-seed-sam-probe", registry=SAM_PROBE)
    assert result["state"] == API_KEY_MISSING
    assert result["credential_required"] is True
    assert result["monitorable"] is False
    assert any("api_key" in r or "role" in r for r in result["blocked_reasons"])


def test_sam_gov_stays_blocked_even_with_an_activation_approval():
    result = evaluate_source(
        source_id="nf-seed-sam-probe",
        registry=SAM_PROBE,
        activation_approvals=["nf-seed-sam-probe"],
        terms_statuses={"nf-seed-sam-probe": "NO_REVIEW_REQUIRED"},
    )
    assert result["monitorable"] is False
    assert result["state"] == API_KEY_MISSING


def test_the_shipped_registry_contains_no_sam_gov_row():
    rows = load_registry_rows()
    assert not [
        seed_id
        for seed_id, row in rows.items()
        if "sam.gov" in str(row.get("source_url") or "").lower()
    ]


def test_a_fixture_source_is_refused_outside_a_test():
    result = evaluate_source(source_id=FIXTURE_SOURCE)
    assert result["state"] == UNKNOWN_SOURCE
    assert (
        "fixture_sources_are_not_permitted_outside_hermetic_tests"
        in result["blocked_reasons"]
    )


def test_a_fixture_source_evaluates_hermetically_and_is_never_monitorable():
    result = evaluate_source(source_id=FIXTURE_SOURCE, allow_fixture=True)
    assert result["state"] == FIXTURE_ALLOWED
    assert result["monitorable"] is False
    assert "fixture_sources_are_never_monitored" in result["blocked_reasons"]
    assert allowlist_invariant_failures(result) == []


def test_a_reviewed_and_approved_source_becomes_monitorable():
    """The permitted branch, kept reachable so the refusals are falsifiable."""
    result = evaluate_source(
        source_id=EXAMPLE_SOURCE,
        terms_statuses=REVIEWED,
        activation_approvals=[EXAMPLE_SOURCE],
    )
    assert result["state"] == ACTIVATION_APPROVED
    assert result["monitorable"] is True
    assert result["blocked_reasons"] == []
    assert allowlist_invariant_failures(result) == []


@pytest.mark.parametrize(
    "kwargs",
    [
        {"terms_statuses": REVIEWED},
        {"activation_approvals": [EXAMPLE_SOURCE]},
    ],
)
def test_a_review_alone_and_an_approval_alone_are_both_insufficient(kwargs):
    result = evaluate_source(source_id=EXAMPLE_SOURCE, **kwargs)
    assert result["monitorable"] is False
    assert result["blocked_reasons"]


def test_an_approval_never_clears_a_terms_blocker():
    result = evaluate_source(
        source_id=EXAMPLE_SOURCE,
        terms_statuses={EXAMPLE_SOURCE: "TERMS_REVIEW_REQUIRED"},
        activation_approvals=[EXAMPLE_SOURCE],
    )
    assert result["state"] == TERMS_BLOCKED
    assert result["monitorable"] is False


def test_an_attribution_required_review_still_permits_collection():
    """ATTRIBUTION_REQUIRED is non-blocking terms; the duty moves to the fetch."""
    result = evaluate_source(
        source_id=EXAMPLE_SOURCE,
        terms_statuses={EXAMPLE_SOURCE: "ATTRIBUTION_REQUIRED"},
        activation_approvals=[EXAMPLE_SOURCE],
    )
    assert result["state"] == ACTIVATION_APPROVED


def test_no_source_in_the_shipped_registry_is_monitorable():
    evaluation = evaluate_registry()
    assert evaluation["registry_row_count"] > 100
    assert evaluation["monitorable_count"] == 0
    assert evaluation["monitorable_source_ids"] == []
    assert allowlist_invariant_failures(evaluation) == []


def test_every_registry_row_is_classified():
    evaluation = evaluate_registry()
    assert evaluation["evaluated_count"] == evaluation["registry_row_count"]
    assert sum(evaluation["by_state"].values()) == evaluation["registry_row_count"]
    assert set(evaluation["by_state"]) == set(EVALUATION_STATES)


def test_evaluating_the_whole_registry_calls_nothing():
    evaluation = evaluate_registry()
    assert evaluation["network_calls"] == 0
    assert evaluation["fetch_performed"] is False
    assert evaluation["collector_activated"] is False
    assert evaluation["source_monitoring_live"] is False


# ---------------------------------------------------------------------------
# the collector preflight
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("key", sorted(REQUIRED_CONFIG_KEYS))
def test_a_collector_missing_a_required_key_is_refused(key):
    config = {k: v for k, v in DRY_RUN_COLLECTOR.items() if k != key}
    result = build_collector_preflight(
        config=config, terms_statuses=REVIEWED, activation_approvals=[EXAMPLE_SOURCE]
    )
    assert result["collector_may_run_live"] is False
    assert f"collector_config_missing:{key}" in result["blocked_reasons"]


def test_a_fully_declared_dry_run_collector_passes():
    result = build_collector_preflight(
        config=DRY_RUN_COLLECTOR,
        terms_statuses=REVIEWED,
        activation_approvals=[EXAMPLE_SOURCE],
    )
    assert result["state"] == "configured_dry_run_only"
    assert result["collector_may_run_live"] is False
    assert result["blocked_reasons"] == []
    assert collector_preflight_invariant_failures(result) == []


def test_live_fetch_is_refused_without_an_activation_approval():
    result = build_collector_preflight(
        config={
            **DRY_RUN_COLLECTOR,
            "fetch_mode": "live_fetch",
            "activation_approval": False,
        },
        terms_statuses=REVIEWED,
        activation_approvals=[EXAMPLE_SOURCE],
    )
    assert result["collector_may_run_live"] is False
    assert (
        "live_fetch_requested_without_an_activation_approval"
        in result["blocked_reasons"]
    )


def test_live_fetch_is_refused_without_somewhere_for_the_bytes_to_land():
    result = build_collector_preflight(
        config={**DRY_RUN_COLLECTOR, "fetch_mode": "live_fetch"},
        terms_statuses=REVIEWED,
        activation_approvals=[EXAMPLE_SOURCE],
    )
    assert result["collector_may_run_live"] is False
    assert any(
        "raw_payload_storage_not_live_capable" in r for r in result["blocked_reasons"]
    )


def test_live_fetch_is_refused_for_a_source_that_is_not_permitted():
    result = build_collector_preflight(
        config={
            **DRY_RUN_COLLECTOR,
            "fetch_mode": "live_fetch",
            "raw_payload_storage_policy": "s3_compatible_configured",
        }
    )
    assert result["collector_may_run_live"] is False
    assert result["state"] == "source_not_permitted"


def test_attribution_required_needs_verbatim_text():
    """Gate 94's rule, preserved: intending to attribute is not attributing."""
    without = build_collector_preflight(
        config={**DRY_RUN_COLLECTOR, "attribution_requirement": "attribution_required"},
        terms_statuses=REVIEWED,
        activation_approvals=[EXAMPLE_SOURCE],
    )
    assert (
        "attribution_required_but_no_verbatim_text_is_carried"
        in without["blocked_reasons"]
    )

    with_text = build_collector_preflight(
        config={
            **DRY_RUN_COLLECTOR,
            "attribution_requirement": "attribution_required",
            "attribution_text_verbatim": True,
        },
        terms_statuses=REVIEWED,
        activation_approvals=[EXAMPLE_SOURCE],
    )
    assert with_text["blocked_reasons"] == []


def test_a_non_canonical_user_agent_is_refused():
    result = build_collector_preflight(
        config={**DRY_RUN_COLLECTOR, "user_agent_policy": "custom"},
        terms_statuses=REVIEWED,
        activation_approvals=[EXAMPLE_SOURCE],
    )
    assert any(
        "user_agent_policy_not_acceptable" in r for r in result["blocked_reasons"]
    )


def test_an_undeclared_rate_limit_is_refused():
    result = build_collector_preflight(
        config={**DRY_RUN_COLLECTOR, "rate_limit_policy": "unknown"},
        terms_statuses=REVIEWED,
        activation_approvals=[EXAMPLE_SOURCE],
    )
    assert any("rate_limit_policy_not_declared" in r for r in result["blocked_reasons"])


def test_a_fully_configured_live_collector_is_reachable():
    """The permitted branch, so every refusal above it is falsifiable."""
    result = build_collector_preflight(
        config={
            **DRY_RUN_COLLECTOR,
            "fetch_mode": "live_fetch",
            "raw_payload_storage_policy": next(iter(LIVE_CAPABLE_PAYLOAD_POLICIES)),
        },
        terms_statuses=REVIEWED,
        activation_approvals=[EXAMPLE_SOURCE],
    )
    assert result["state"] == "activation_approved"
    assert result["collector_may_run_live"] is True
    assert collector_preflight_invariant_failures(result) == []
    # And it still activated nothing.
    assert result["collector_activated"] is False
    assert result["source_monitoring_live"] is False
    assert result["network_calls"] == 0


def test_no_collector_preflight_reports_a_key_value():
    for policy in ("local_dev_ignored", "s3_compatible_configured"):
        result = build_collector_preflight(
            config={**DRY_RUN_COLLECTOR, "raw_payload_storage_policy": policy},
            terms_statuses=REVIEWED,
            activation_approvals=[EXAMPLE_SOURCE],
        )
        assert result["api_key_values_reported"] is False
        rendered = json.dumps(result)
        for marker in ("api_key=", "Bearer ", "AKIA", "-----BEGIN"):
            assert marker not in rendered


# ---------------------------------------------------------------------------
# readiness
# ---------------------------------------------------------------------------


def _proofs(**overrides):
    base = {
        "collector_preflight": build_collector_preflight(
            config=DRY_RUN_COLLECTOR,
            terms_statuses=REVIEWED,
            activation_approvals=[EXAMPLE_SOURCE],
        ),
        "watchlist_can_name_sources": True,
        "tenant_digest_operational": True,
    }
    base.update(overrides)
    return base


def test_preflight_is_ready_and_monitoring_is_not_live():
    readiness = build_source_monitoring_readiness(**_proofs())
    assert readiness["source_monitoring_preflight_ready"] is True
    assert readiness["source_monitoring_live"] is False
    assert readiness["scope"] == CONTROLLED_SCOPE
    assert readiness["blocked_reasons"] == []
    assert source_monitoring_readiness_invariant_failures(readiness) == []


def test_readiness_does_not_require_a_monitorable_source():
    """There are zero, and requiring one would make this lane unreachable."""
    readiness = build_source_monitoring_readiness(**_proofs())
    assert readiness["monitorable_count"] == 0
    assert readiness["monitorable_source_required_for_readiness"] is False
    assert readiness["collector_required_for_readiness"] is False
    assert readiness["scheduler_runtime_required_for_readiness"] is False
    assert readiness["live_source_access_required_for_readiness"] is False


@pytest.mark.parametrize(
    "override,reason",
    [
        ({"collector_preflight": {}}, "no_collector_preflight_was_supplied"),
        ({"watchlist_can_name_sources": False}, "cannot_name_a_registry_source"),
        ({"tenant_digest_operational": False}, "tenant_digest_is_not_operational"),
    ],
)
def test_readiness_is_false_without_each_piece(override, reason):
    readiness = build_source_monitoring_readiness(**_proofs(**override))
    assert readiness["source_monitoring_preflight_ready"] is False
    assert readiness["scope"] == SCOPE_NONE
    assert any(reason in r for r in readiness["blocked_reasons"])


def test_readiness_is_false_when_the_route_module_is_absent(tmp_path):
    readiness = build_source_monitoring_readiness(**_proofs(), repo_root=tmp_path)
    assert readiness["source_monitoring_preflight_ready"] is False
    assert any("route_module_does_not_exist" in r for r in readiness["blocked_reasons"])


def test_readiness_is_false_if_the_chokepoint_is_dirty():
    readiness = build_source_monitoring_readiness(
        **_proofs(), chokepoint_scan={"clean": False, "unapproved_count": 3}
    )
    assert readiness["source_monitoring_preflight_ready"] is False
    assert any("unapproved_call_sites" in r for r in readiness["blocked_reasons"])


def test_readiness_is_false_if_anything_made_a_network_call():
    readiness = build_source_monitoring_readiness(
        **_proofs(
            collector_preflight={
                **build_collector_preflight(
                    config=DRY_RUN_COLLECTOR,
                    terms_statuses=REVIEWED,
                    activation_approvals=[EXAMPLE_SOURCE],
                ),
                "network_calls": 2,
            }
        )
    )
    assert readiness["source_monitoring_preflight_ready"] is False
    assert "a_network_call_was_made:2" in readiness["blocked_reasons"]


def test_readiness_is_false_if_a_collector_was_activated():
    readiness = build_source_monitoring_readiness(
        **_proofs(
            collector_preflight={
                **build_collector_preflight(
                    config=DRY_RUN_COLLECTOR,
                    terms_statuses=REVIEWED,
                    activation_approvals=[EXAMPLE_SOURCE],
                ),
                "collector_activated": True,
            }
        )
    )
    assert readiness["source_monitoring_preflight_ready"] is False
    assert "a_collector_was_activated" in readiness["blocked_reasons"]


def test_the_activation_blockers_are_named_with_an_owner():
    """ "47 blockers" tells an operator nothing about what to do next."""
    readiness = build_source_monitoring_readiness(**_proofs())
    blockers = readiness["activation_blockers"]
    assert blockers
    for blocker in blockers:
        assert blocker["blocker"]
        assert blocker["owner"]
        assert blocker["why"]
    names = {b["blocker"] for b in blockers}
    assert "terms_review_incomplete" in names
    assert "human_review_only_sources" in names


@pytest.mark.parametrize(
    "field",
    [
        "collector_activated",
        "fetch_performed",
        "live_source_coverage",
        "production_source_monitoring",
        "customer_auth_live",
        "real_organization_touched",
        "api_key_values_reported",
    ],
)
def test_readiness_never_claims(field):
    readiness = build_source_monitoring_readiness(**_proofs())
    assert readiness[field] is False


def test_readiness_names_what_it_does_not_approve():
    readiness = build_source_monitoring_readiness()
    assert set(NOT_APPROVED) <= set(readiness["not_approved"])


def test_the_readiness_invariants_catch_a_preflight_that_activated_monitoring():
    forged = {
        **build_source_monitoring_readiness(**_proofs()),
        "source_monitoring_live": True,
    }
    assert "a_preflight_activated_source_monitoring" in (
        source_monitoring_readiness_invariant_failures(forged)
    )


def test_source_monitoring_live_comes_from_the_scheduler_and_stays_false():
    from nativeforge.services.source_scheduler_readiness_service import (
        build_scheduler_readiness,
    )

    scheduler = build_scheduler_readiness()
    readiness = build_source_monitoring_readiness(**_proofs())
    assert scheduler["source_monitoring_live"] is False
    assert readiness["source_monitoring_live"] is False
    assert readiness["scheduler_components_missing"]


# ---------------------------------------------------------------------------
# the routes
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", f"{_base()}/readiness"),
        ("GET", f"{_base()}/blockers"),
        ("POST", f"{_base()}/evaluate"),
    ],
)
def test_every_route_refuses_an_unauthenticated_caller(client, method, path):
    assert client.request(method, path, json={}).status_code == 401


def test_a_forged_dev_header_cannot_override_the_org(client):
    response = client.get(
        f"{_base()}/readiness", headers=soh.forged_header_only(uuid.UUID(DEMO))
    )
    assert response.status_code == 401


def test_the_readiness_route_reports_what_is_and_is_not_ready(client, demo_session):
    response = client.get(f"{_base()}/readiness", headers=demo_session)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_monitoring_live"] is False
    assert body["fetch_performed"] is False
    assert body["collector_activated"] is False
    assert body["production_source_monitoring"] is False
    assert body["registry_row_count"] > 100
    assert body["monitorable_count"] == 0


def test_the_blockers_route_names_each_class(client, demo_session):
    response = client.get(f"{_base()}/blockers", headers=demo_session)
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["activation_blockers"]
    assert body["terms_blocked_count"] > 0
    assert body["human_review_blocked_count"] > 0
    assert body["monitorable_source_ids"] == []
    assert body["api_key_values_reported"] is False


def test_evaluate_answers_for_a_watched_source(client, demo_session):
    response = client.post(
        f"{_base()}/evaluate", json={"source_id": EXAMPLE_SOURCE}, headers=demo_session
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["source_id"] == EXAMPLE_SOURCE
    assert body["state"] == TERMS_BLOCKED
    assert body["monitorable"] is False
    assert body["fetch_performed"] is False
    assert body["robots_fetched"] is False
    assert body["dns_resolved"] is False
    assert body["blocked_reasons"]


def test_evaluate_refuses_a_source_this_organization_does_not_watch(
    client, demo_session
):
    response = client.post(
        f"{_base()}/evaluate",
        json={"source_id": GRANTS_GOV_SOURCE},
        headers=demo_session,
    )
    assert response.status_code == 404
    assert "does_not_watch_this_source" in json.dumps(response.json())


def test_the_watchlist_can_reference_a_registry_source(client, demo_session):
    """Gate 140 made this real. Watching is still not monitoring."""
    known = watchlist.known_registry_source_ids()
    assert EXAMPLE_SOURCE in known
    response = client.post(
        f"{_base()}/evaluate", json={"source_id": EXAMPLE_SOURCE}, headers=demo_session
    )
    assert response.status_code == 200
    assert response.json()["registry_known"] is True
    assert response.json()["source_monitoring_live"] is False


def test_another_organization_is_refused(client, demo_session):
    soh.ensure_member(OTHER)
    other = soh.session_headers(uuid.UUID(OTHER))
    for path in ("readiness", "blockers"):
        assert client.get(f"{_base(OTHER)}/{path}", headers=other).status_code in {
            200,
            403,
            404,
        }
    assert client.get(
        f"{_base(OTHER)}/readiness", headers=demo_session
    ).status_code in {
        403,
        404,
    }


def test_the_route_module_is_session_wired_and_makes_no_live_call():
    detected = detect_readiness_route_module()
    assert detected["route_module_available"] is True
    assert detected["session_wired"] is True
    assert detected["makes_no_live_call"] is True
    assert detected["blocked_reasons"] == []


# ---------------------------------------------------------------------------
# what this gate must not change
# ---------------------------------------------------------------------------


def test_email_delivery_is_unchanged():
    from nativeforge.services.email_provider_configuration_preflight_service import (
        build_email_provider_preflight,
    )

    assert build_email_provider_preflight()["email_delivery"] is False


def test_customer_auth_live_is_unchanged():
    readiness = build_source_monitoring_readiness(**_proofs())
    assert readiness["source_monitoring_preflight_ready"] is True
    assert readiness["customer_auth_live"] is False


def test_the_terms_review_queue_is_not_bypassed():
    from nativeforge.services.source_terms_review_queue_service import (
        build_terms_review_queue,
        queue_invariant_failures,
    )

    queue = build_terms_review_queue()
    assert queue["queue_length"] >= 5
    assert queue["approved_count"] == 0
    assert queue["sources_activated"] == 0
    assert queue["automation_blocked_count"] == queue["queue_length"]
    assert queue_invariant_failures(queue) == []


# ---------------------------------------------------------------------------
# the artifacts
# ---------------------------------------------------------------------------


def test_the_artifact_writes_every_declared_file(tmp_path):
    result = art.write_source_monitoring_artifacts(repo_root=tmp_path)
    assert art.source_monitoring_artifact_invariant_failures(result) == []
    for name in art.ARTIFACT_FILES:
        assert (tmp_path / art.ARTIFACT_DIR / name).is_file(), name


def test_the_artifact_is_deterministic():
    first = art.build_source_monitoring_artifacts()
    second = art.build_source_monitoring_artifacts()
    assert first == second


def test_the_artifact_reports_ready_and_not_live():
    files = art.build_source_monitoring_artifacts()
    readiness = json.loads(files["source_monitoring_preflight_readiness.json"])
    status = json.loads(files["source_monitoring_live_status.json"])
    assert readiness["source_monitoring_preflight_ready"] is True
    assert readiness["source_monitoring_live"] is False
    assert readiness["scope"] == CONTROLLED_SCOPE
    assert readiness["invariant_failures"] == []
    assert status["source_monitoring_live"] is False
    assert status["collectors_activated"] == 0
    assert status["live_source_calls"] == 0
    assert status["sources_cleared_for_collection"] == 0
    assert status["improvement_claims"] == []


def test_the_artifact_records_every_refusal_class():
    files = art.build_source_monitoring_artifacts()
    allow = json.loads(files["approved_source_allowlist_smoke.json"])
    states = {case["state"] for case in allow["cases"].values()}
    assert {
        UNKNOWN_SOURCE,
        TERMS_BLOCKED,
        HUMAN_REVIEW_BLOCKED,
        API_KEY_MISSING,
        FIXTURE_ALLOWED,
        ACTIVATION_APPROVED,
    } <= states
    assert allow["an_approval_never_clears_a_blocker"] is True
    assert allow["a_fixture_is_never_monitorable"] is True
    assert allow["network_calls"] == 0


def test_the_artifact_records_the_terms_queue_untouched():
    files = art.build_source_monitoring_artifacts()
    terms = json.loads(files["source_terms_review_blockers.json"])
    assert terms["terms_review_bypassed"] is False
    assert terms["human_review_bypassed"] is False
    assert terms["sources_activated"] == 0
    assert terms["approved_count"] == 0


def test_no_artifact_carries_a_credential_or_a_key():
    for name, body in art.build_source_monitoring_artifacts().items():
        lowered = body.lower()
        for marker in art.FORBIDDEN_MARKERS:
            assert marker.lower() not in lowered, (name, marker)


def test_the_committed_artifacts_match_what_the_service_builds():
    directory = REPO_ROOT / art.ARTIFACT_DIR
    for name, body in art.build_source_monitoring_artifacts().items():
        committed = directory / name
        assert committed.is_file(), name
        assert committed.read_text(encoding="utf-8") == body, name
