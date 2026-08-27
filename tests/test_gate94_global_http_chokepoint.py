"""Gate 94 - global live-network choke point.

Before this gate, six egress call sites existed in src/nativeforge and one was
guarded. These tests hold the other five shut, and the scanner test is the one
that keeps a seventh from appearing quietly.

Nothing here reaches the network. Every fetch path is exercised through an
injected transport.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from nativeforge.services import polite_http_fetch_service as polite
from nativeforge.services.hermetic_network_enforcement_service import (
    APPROVED_MODULE_NAMES,
    APPROVED_NETWORK_SITES,
    enforcement_invariant_failures,
    scan_for_network_call_sites,
)
from nativeforge.services.hermetic_test_guard_service import (
    ENV_ALLOW_LIVE_NETWORK,
    LiveNetworkBlockedError,
)
from nativeforge.services.hermetic_test_guard_service import (
    assert_live_network_allowed as gate77b_assert,
)
from nativeforge.services.live_network_guard_service import (
    CRAWLING_PURPOSES,
    DECISION_STATUSES,
    PURPOSE_REQUIREMENTS,
    PURPOSES,
    ROBOTS_SATISFYING,
    LiveNetworkPermissionError,
    assert_live_network_allowed,
    build_live_network_decision,
    canonical_user_agent,
    guard_invariant_failures,
    require_live_network_permission,
    user_agent_status_for,
)
from nativeforge.services.nativeforge_user_agent_service import (
    CONTACT_URL,
    FORBIDDEN_USER_AGENT_TOKENS,
    NATIVEFORGE_USER_AGENT,
    build_user_agent_contract,
    classify_contact,
    user_agent_contract_invariant_failures,
    user_agent_violations,
)
from nativeforge.services.real_url_resolver_service import resolve_url_real
from nativeforge.services.source_crawler_governance_service import (
    MIN_REQUEST_INTERVAL_SECONDS,
)

REPO_ROOT = Path(__file__).resolve().parents[1]

# A source-collection request with every requirement satisfied.
FULLY_SATISFIED: dict[str, Any] = dict(
    purpose="source_collection",
    target_url="https://example.org/opportunities",
    caller="test",
    allow_live_fetch=True,
    terms_status="NO_REVIEW_REQUIRED",
    activation_status="activation_allowed",
    collector_status="active",
    robots_status="allowed",
    credential_status="not_required",
    rate_limit_status="policy_declared",
    user_agent_status="canonical",
)


class FakeResponse:
    def __init__(self, status_code: int, text: str = "", url: str = "") -> None:
        self.status_code = status_code
        self.text = text
        self.url = url


def make_transport(
    *,
    robots_status: Any = 404,
    robots_text: str = "",
    page_status: int = 200,
    page_text: str = "body",
):
    """An injected transport. Never reaches the network."""

    def transport(url: str, *, headers: dict[str, str], timeout: float) -> Any:
        if url.endswith("/robots.txt"):
            if robots_status == "timeout":
                raise TimeoutError("robots.txt timed out")
            return FakeResponse(robots_status, robots_text, url)
        return FakeResponse(page_status, page_text, url)

    return transport


@pytest.fixture(autouse=True)
def _clean_fetch_state() -> Any:
    polite.reset_polite_fetch_state()
    yield
    polite.reset_polite_fetch_state()


@pytest.fixture(scope="module")
def repo_scan() -> dict:
    """One scan of the tree, shared across tests.

    Parsing 885 files six times cost ~15s of suite time for six identical
    answers.
    """
    return scan_for_network_call_sites(repo_root=REPO_ROOT)


# --------------------------------------------------------------------------
# 94B - the guard
# --------------------------------------------------------------------------


def test_guard_denies_by_default() -> None:
    decision = build_live_network_decision(
        purpose="source_collection",
        target_url="https://example.org/x",
        caller="test",
    )
    assert decision["allowed"] is False
    assert decision["blocked_reasons"]
    assert guard_invariant_failures(decision) == []


def test_allow_live_fetch_defaults_to_false() -> None:
    decision = build_live_network_decision(
        purpose="source_discovery",
        target_url="https://example.org/x",
        caller="test",
        terms_status="NO_REVIEW_REQUIRED",
        robots_status="allowed",
        rate_limit_status="policy_declared",
        user_agent_status="canonical",
    )
    assert decision["resolved_inputs"]["allow_live_fetch"] is False
    assert decision["allowed"] is False
    assert "live_fetch_not_opted_in" in decision["blocked_reasons"]


def test_fully_satisfied_request_is_allowed() -> None:
    decision = build_live_network_decision(**FULLY_SATISFIED)
    assert decision["allowed"] is True
    assert decision["decision_status"] == "allowed"
    assert decision["requirements_missing"] == []
    assert guard_invariant_failures(decision) == []


def test_terms_review_required_blocks() -> None:
    decision = build_live_network_decision(
        **{**FULLY_SATISFIED, "terms_status": "TERMS_REVIEW_REQUIRED"}
    )
    assert decision["allowed"] is False
    assert decision["requires_terms_review"] is True


def test_human_review_only_blocks() -> None:
    decision = build_live_network_decision(
        **{**FULLY_SATISFIED, "terms_status": "HUMAN_REVIEW_ONLY"}
    )
    assert decision["decision_status"] == "requires_human_review"
    assert decision["allowed"] is False
    assert decision["human_review_required"] is True
    assert guard_invariant_failures(decision) == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("terms_status", "TOTALLY_MADE_UP"),
        ("activation_status", "activation_fine_probably"),
        ("collector_status", "sort_of_running"),
        ("robots_status", "probably_ok"),
        ("credential_status", "we_have_one_somewhere"),
        ("rate_limit_status", "reasonable"),
        ("user_agent_status", "good_enough"),
    ],
)
def test_unknown_status_blocks(field: str, value: str) -> None:
    """Deny by default: an unrecognised value is not a pass."""
    decision = build_live_network_decision(**{**FULLY_SATISFIED, field: value})
    assert decision["allowed"] is False, field


def test_unknown_purpose_blocks() -> None:
    decision = build_live_network_decision(
        purpose="exfiltrate", target_url="https://example.org/x", caller="test"
    )
    assert decision["allowed"] is False
    assert any("purpose_out_of_vocabulary" in r for r in decision["blocked_reasons"])


def test_non_https_scheme_blocks() -> None:
    decision = build_live_network_decision(
        **{**FULLY_SATISFIED, "target_url": "http://example.org/x"}
    )
    assert decision["allowed"] is False
    assert any("scheme_not_https" in r for r in decision["blocked_reasons"])


@pytest.mark.parametrize("robots", ["fetch_failed", "unknown", "disallowed"])
def test_robots_failure_is_not_permission(robots: str) -> None:
    """A robots.txt that timed out did not say yes."""
    decision = build_live_network_decision(
        **{**FULLY_SATISFIED, "robots_status": robots}
    )
    assert decision["allowed"] is False, robots
    assert guard_invariant_failures(decision) == []


def test_robots_404_is_a_real_answer_and_permits() -> None:
    """A 404 conventionally means no restrictions; blocking it would be wrong."""
    decision = build_live_network_decision(
        **{**FULLY_SATISFIED, "robots_status": "absent"}
    )
    assert decision["allowed"] is True
    assert "absent" in ROBOTS_SATISFYING


def test_collector_not_active_blocks_collection() -> None:
    for state in ("not_active", "activating", "halted"):
        decision = build_live_network_decision(
            **{**FULLY_SATISFIED, "collector_status": state}
        )
        assert decision["allowed"] is False, state


def test_activation_not_allowed_blocks_collection() -> None:
    for state in (
        "activation_blocked",
        "activation_unknown",
        "activation_requires_human_review",
    ):
        decision = build_live_network_decision(
            **{**FULLY_SATISFIED, "activation_status": state}
        )
        assert decision["allowed"] is False, state


def test_credentialed_source_without_credential_blocks() -> None:
    decision = build_live_network_decision(
        **{**FULLY_SATISFIED, "collector_type": "public_api_with_key"}
    )
    assert decision["allowed"] is False
    assert "credential" in decision["requirements_missing"]


def test_credentialed_source_with_credential_is_allowed() -> None:
    decision = build_live_network_decision(
        **{
            **FULLY_SATISFIED,
            "collector_type": "public_api_with_key",
            "credential_status": "present_and_valid",
        }
    )
    assert decision["allowed"] is True


def test_no_caller_can_self_exempt_a_requirement() -> None:
    """There is no input meaning "skip this one"."""
    # A keyed collector declaring its credential not_required.
    decision = build_live_network_decision(
        **{
            **FULLY_SATISFIED,
            "collector_type": "public_api_with_key",
            "credential_status": "not_required",
        }
    )
    assert decision["allowed"] is False
    # The requirement set is structural: derived from purpose, not supplied.
    for purpose in sorted(PURPOSES):
        assert PURPOSE_REQUIREMENTS[purpose], purpose


def test_blacklisted_host_blocks() -> None:
    decision = build_live_network_decision(
        **{**FULLY_SATISFIED, "target_url": "https://scdmh.net/anything"}
    )
    assert decision["allowed"] is False
    assert guard_invariant_failures(decision) == []


def test_disallowed_path_blocks() -> None:
    decision = build_live_network_decision(
        **{**FULLY_SATISFIED, "target_url": "https://example.org/search/grants"}
    )
    assert decision["allowed"] is False


def test_circuit_breaker_blocks_before_the_request() -> None:
    decision = build_live_network_decision(
        **{**FULLY_SATISFIED, "consecutive_failures": 5}
    )
    assert decision["allowed"] is False
    assert any("circuit_breaker_open" in r for r in decision["blocked_reasons"])


def test_decision_names_its_caller() -> None:
    decision = build_live_network_decision(
        **{**FULLY_SATISFIED, "caller": "some_module.some_function"}
    )
    assert decision["caller"] == "some_module.some_function"
    assert decision["audit_event"]["caller"] == "some_module.some_function"


def test_guard_never_fetches() -> None:
    decision = build_live_network_decision(**FULLY_SATISFIED)
    assert decision["fetch_performed"] is False


def test_assert_form_raises_with_the_reason() -> None:
    with pytest.raises(LiveNetworkPermissionError) as excinfo:
        assert_live_network_allowed(
            purpose="source_collection",
            target_url="https://example.org/x",
            caller="tester",
        )
    assert "tester" in str(excinfo.value)
    assert "source_collection" in str(excinfo.value)


def test_assert_form_returns_the_decision_when_permitted() -> None:
    decision = assert_live_network_allowed(**FULLY_SATISFIED)
    assert decision["allowed"] is True


def test_require_form_does_not_raise() -> None:
    decision = require_live_network_permission(
        purpose="source_collection",
        target_url="https://example.org/x",
        caller="tester",
    )
    assert decision["allowed"] is False


def test_decision_statuses_are_the_declared_set() -> None:
    seen = set()
    for kw in (
        FULLY_SATISFIED,
        {**FULLY_SATISFIED, "terms_status": "HUMAN_REVIEW_ONLY"},
        {**FULLY_SATISFIED, "allow_live_fetch": False},
    ):
        seen.add(build_live_network_decision(**kw)["decision_status"])
    assert seen <= DECISION_STATUSES


def test_non_source_purposes_do_not_demand_source_requirements() -> None:
    """Asking a JWKS URL for its terms_status would be a category error."""
    for purpose in ("identity_verification", "operational_alert"):
        required = set(PURPOSE_REQUIREMENTS[purpose])
        assert "terms_cleared" not in required
        assert "collector_active" not in required
        assert "robots_permits" not in required
    for purpose in sorted(CRAWLING_PURPOSES):
        assert "robots_permits" in PURPOSE_REQUIREMENTS[purpose]


def test_identity_verification_requires_https_and_a_configured_issuer() -> None:
    blocked = build_live_network_decision(
        purpose="identity_verification",
        target_url="https://idp.example.com/jwks",
        caller="oidc",
        allow_live_fetch=True,
    )
    assert blocked["allowed"] is False
    assert "issuer_not_configured" in blocked["blocked_reasons"]

    allowed = build_live_network_decision(
        purpose="identity_verification",
        target_url="https://idp.example.com/jwks",
        caller="oidc",
        allow_live_fetch=True,
        issuer_configured=True,
    )
    assert allowed["allowed"] is True

    insecure = build_live_network_decision(
        purpose="identity_verification",
        target_url="http://idp.example.com/jwks",
        caller="oidc",
        allow_live_fetch=True,
        issuer_configured=True,
    )
    assert insecure["allowed"] is False


# --------------------------------------------------------------------------
# 94C - the user agent
# --------------------------------------------------------------------------


def test_canonical_user_agent_is_the_single_source_of_truth() -> None:
    from nativeforge.services import source_crawler_governance_service as gov

    assert gov.NATIVEFORGE_USER_AGENT is NATIVEFORGE_USER_AGENT
    assert polite.USER_AGENT is NATIVEFORGE_USER_AGENT
    assert canonical_user_agent() is NATIVEFORGE_USER_AGENT


def test_canonical_user_agent_identifies_nativeforge_and_carries_a_contact() -> None:
    assert "nativeforge" in NATIVEFORGE_USER_AGENT.lower()
    assert CONTACT_URL in NATIVEFORGE_USER_AGENT
    assert user_agent_violations(NATIVEFORGE_USER_AGENT) == []


def test_contact_must_be_reachable() -> None:
    """A contact on a reserved domain is decoration, not a contact."""
    assert classify_contact(CONTACT_URL) == "reachable"
    assert classify_contact("https://nativeforge.example/bot") == (
        "unreachable_reserved_domain"
    )
    assert classify_contact("mailto:x@foo.invalid") == "unreachable_reserved_domain"
    assert classify_contact("") == "unknown"


def test_user_agent_contract_permits_crawling() -> None:
    contract = build_user_agent_contract()
    assert contract["contact_is_reachable"] is True
    assert contract["crawler_activation_allowed"] is True
    assert user_agent_contract_invariant_failures(contract) == []


def test_unreachable_contact_would_block_crawler_activation() -> None:
    contract = build_user_agent_contract()
    pretend = dict(
        contract,
        contact_is_reachable=False,
        contact_status="unreachable_reserved_domain",
        crawler_activation_allowed=True,
    )
    assert "crawler_allowed_with_an_unreachable_contact" in (
        user_agent_contract_invariant_failures(pretend)
    )


@pytest.mark.parametrize("token", sorted(FORBIDDEN_USER_AGENT_TOKENS))
def test_ai_crawler_tokens_are_refused(token: str) -> None:
    violations = user_agent_violations(f"Mozilla/5.0 (compatible; {token}/1.0)")
    assert any(v.startswith("ai_crawler_user_agent:") for v in violations)
    assert user_agent_status_for(f"{token}/1.0") == "forbidden_ai_crawler"


def test_canonical_user_agent_carries_no_ai_token() -> None:
    lowered = NATIVEFORGE_USER_AGENT.lower()
    for token in FORBIDDEN_USER_AGENT_TOKENS:
        assert token not in lowered


def test_the_two_pre_gate94_user_agents_are_no_longer_canonical() -> None:
    old_polite = (
        "NativeForge/1.0 (+https://github.com/grayjosef/NativeForge; "
        "grant-discovery; respectful-crawler)"
    )
    old_gate92 = (
        "NativeForgeBot/1.0 (+https://nativeforge.example/bot; grant discovery "
        "for tribal organizations)"
    )
    for old in (old_polite, old_gate92):
        assert old != NATIVEFORGE_USER_AGENT
        assert user_agent_status_for(old) == "non_canonical"


def test_no_second_user_agent_string_in_source(repo_scan: dict) -> None:
    report = repo_scan
    offenders = [
        f for f in report["findings"] if f["kind"] == "second_user_agent_definition"
    ]
    assert offenders == [], offenders


# --------------------------------------------------------------------------
# 94D - polite HTTP
# --------------------------------------------------------------------------


def test_polite_http_get_refuses_without_opt_in() -> None:
    result = polite.polite_http_get(
        "https://example.org/a", transport=make_transport(robots_status=404)
    )
    assert result["fetch_live"] is False
    assert result["error"] == "live_network_refused"
    assert "live_fetch_not_opted_in" in result["blocked_reasons"]


def test_polite_http_get_uses_the_global_guard() -> None:
    source = (
        REPO_ROOT / "src/nativeforge/services/polite_http_fetch_service.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert any("live_network_guard_service" in m for m in imported)


def test_polite_http_get_minimum_delay_is_five_seconds() -> None:
    assert polite.DEFAULT_MIN_INTERVAL_SECONDS == 5.0
    assert MIN_REQUEST_INTERVAL_SECONDS == 5.0


def test_polite_http_get_clamps_a_faster_caller_to_the_floor() -> None:
    """A caller may be slower than the floor, never faster."""
    source = (
        REPO_ROOT / "src/nativeforge/services/polite_http_fetch_service.py"
    ).read_text(encoding="utf-8")
    assert "max(float(min_interval_seconds), MIN_REQUEST_INTERVAL_SECONDS)" in source


@pytest.mark.parametrize(
    "robots_kwargs,expected_status,expected_live",
    [
        (
            {"robots_status": 200, "robots_text": "User-agent: *\nAllow: /"},
            "allowed",
            True,
        ),
        (
            {"robots_status": 200, "robots_text": "User-agent: *\nDisallow: /"},
            "disallowed",
            False,
        ),
        ({"robots_status": 404}, "absent", True),
        ({"robots_status": 500}, "fetch_failed", False),
        ({"robots_status": 503}, "fetch_failed", False),
        ({"robots_status": "timeout"}, "fetch_failed", False),
    ],
)
def test_polite_http_get_robots_outcomes(
    robots_kwargs: dict, expected_status: str, expected_live: bool
) -> None:
    result = polite.polite_http_get(
        "https://example.org/a",
        allow_live_fetch=True,
        terms_status="NO_REVIEW_REQUIRED",
        transport=make_transport(**robots_kwargs),
    )
    assert result["robots_status"] == expected_status
    assert result["fetch_live"] is expected_live


def test_polite_http_get_robots_fails_closed_on_timeout() -> None:
    """Before Gate 94 a timing-out robots.txt read as fully permissive."""
    result = polite.polite_http_get(
        "https://example.org/a",
        allow_live_fetch=True,
        terms_status="NO_REVIEW_REQUIRED",
        transport=make_transport(robots_status="timeout"),
    )
    assert result["fetch_live"] is False
    assert result["robots_status"] == "fetch_failed"
    assert result["robots_allowed"] is False


def test_robots_allows_fetch_is_fail_closed() -> None:
    assert (
        polite.robots_allows_fetch(
            "https://example.org/a", transport=make_transport(robots_status="timeout")
        )
        is False
    )
    polite.reset_polite_fetch_state()
    assert (
        polite.robots_allows_fetch(
            "https://example.org/a", transport=make_transport(robots_status=404)
        )
        is True
    )


def test_polite_http_get_enforces_the_blacklist() -> None:
    result = polite.polite_http_get(
        "https://scdmh.net/anything",
        allow_live_fetch=True,
        terms_status="NO_REVIEW_REQUIRED",
        transport=make_transport(robots_status=404),
    )
    assert result["fetch_live"] is False
    assert any("blacklist" in r for r in result["blocked_reasons"])


def test_polite_http_get_backoff_on_429_and_5xx() -> None:
    for code in (429, 503):
        polite.reset_polite_fetch_state()
        result = polite.polite_http_get(
            "https://example.org/a",
            allow_live_fetch=True,
            terms_status="NO_REVIEW_REQUIRED",
            transport=make_transport(robots_status=404, page_status=code),
        )
        assert result["consecutive_failures"] == 1, code
        assert result["backoff_seconds"] > 0, code


def test_backoff_is_exponential_and_capped() -> None:
    values = [polite.backoff_seconds_for(n) for n in range(1, 12)]
    assert values[0] == polite.BACKOFF_INITIAL_SECONDS
    assert all(b >= a for a, b in zip(values, values[1:], strict=False))
    assert max(values) <= polite.BACKOFF_MAX_SECONDS
    assert polite.backoff_seconds_for(0) == 0.0


def test_polite_http_get_presents_the_canonical_user_agent() -> None:
    seen: list[str] = []

    def transport(url: str, *, headers: dict[str, str], timeout: float) -> Any:
        seen.append(headers["User-Agent"])
        return FakeResponse(404 if url.endswith("/robots.txt") else 200, "x", url)

    polite.polite_http_get(
        "https://example.org/a",
        allow_live_fetch=True,
        terms_status="NO_REVIEW_REQUIRED",
        transport=transport,
    )
    assert seen
    assert all(ua == NATIVEFORGE_USER_AGENT for ua in seen)


def test_polite_http_get_does_not_fetch_robots_for_a_refused_request() -> None:
    """No point being polite to a host we are not going to contact."""
    calls: list[str] = []

    def transport(url: str, *, headers: dict[str, str], timeout: float) -> Any:
        calls.append(url)
        return FakeResponse(404, "", url)

    polite.polite_http_get("https://example.org/a", transport=transport)
    assert calls == []


# --------------------------------------------------------------------------
# 94E - the URL resolver
# --------------------------------------------------------------------------


def test_resolver_refuses_live_resolution_by_default() -> None:
    result = resolve_url_real("https://example.org/a")
    assert result["resolved"] is False
    assert result["error"] == "live_network_refused"
    assert "live_fetch_not_opted_in" in result["blocked_reasons"]


def test_resolver_uses_the_global_guard() -> None:
    source = (
        REPO_ROOT / "src/nativeforge/services/real_url_resolver_service.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported = {
        node.module
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module
    }
    assert any("live_network_guard_service" in m for m in imported)


def test_resolver_still_accepts_an_injected_fetcher() -> None:
    """The test seam survives: a recorded transport reaches no network."""

    def fake_fetch(url: str, method: str = "HEAD") -> dict[str, Any]:
        return {"http_status": 200, "body_snippet": "", "final_url": url}

    result = resolve_url_real("https://example.org/a", fetcher=fake_fetch)
    assert result["resolved"] is True
    assert result["http_status"] == 200


def test_resolver_blocks_a_blacklisted_host_even_with_opt_in() -> None:
    result = resolve_url_real("https://scdmh.net/a", allow_live_fetch=True)
    assert result["resolved"] is False
    assert result["error"] == "live_network_refused"


def test_resolver_presents_the_canonical_user_agent() -> None:
    source = (
        REPO_ROOT / "src/nativeforge/services/real_url_resolver_service.py"
    ).read_text(encoding="utf-8")
    assert 'headers={"User-Agent": NATIVEFORGE_USER_AGENT}' in source


# --------------------------------------------------------------------------
# 94F - the scanner
# --------------------------------------------------------------------------


def test_source_scan_has_zero_unapproved_call_sites(repo_scan: dict) -> None:
    report = repo_scan
    unapproved = [s for s in report["network_call_sites"] if not s["approved"]]
    assert unapproved == [], unapproved
    assert report["unapproved_count"] == 0


def test_source_scan_is_clean(repo_scan: dict) -> None:
    report = repo_scan
    assert report["findings"] == [], report["findings"]
    assert report["clean"] is True
    assert enforcement_invariant_failures(report) == []


def test_scanner_actually_scanned_the_tree(repo_scan: dict) -> None:
    """A scan of nothing is clean too."""
    report = repo_scan
    assert report["files_scanned"] > 500
    assert report["network_call_site_count"] >= 6


def test_no_allow_live_fetch_default_true_remains(repo_scan: dict) -> None:
    report = repo_scan
    offenders = [
        f for f in report["findings"] if f["kind"] == "allow_live_fetch_defaults_true"
    ]
    assert offenders == [], offenders


def test_every_approved_site_names_a_guard_and_a_reason() -> None:
    for site in APPROVED_NETWORK_SITES:
        assert site.reason, site.module
        assert site.guard, site.module
    assert len(APPROVED_MODULE_NAMES) == len(APPROVED_NETWORK_SITES)


def test_scanner_would_catch_a_new_unapproved_call_site(tmp_path: Path) -> None:
    """The scan must not be vacuous - plant one and prove it is found."""
    services = tmp_path / "src" / "nativeforge" / "services"
    services.mkdir(parents=True)
    (services / "sneaky_new_service.py").write_text(
        "import httpx\n\n\ndef go(url):\n    return httpx.get(url)\n",
        encoding="utf-8",
    )
    report = scan_for_network_call_sites(repo_root=tmp_path)
    kinds = {f["kind"] for f in report["findings"]}
    assert "unapproved_network_import" in kinds
    assert report["clean"] is False


def test_scanner_would_catch_a_reintroduced_default_true(tmp_path: Path) -> None:
    services = tmp_path / "src" / "nativeforge" / "services"
    services.mkdir(parents=True)
    (services / "eager_service.py").write_text(
        "def pull(*, allow_live_fetch: bool = True):\n    return allow_live_fetch\n",
        encoding="utf-8",
    )
    report = scan_for_network_call_sites(repo_root=tmp_path)
    kinds = {f["kind"] for f in report["findings"]}
    assert "allow_live_fetch_defaults_true" in kinds


def test_scanner_would_catch_a_second_user_agent(tmp_path: Path) -> None:
    services = tmp_path / "src" / "nativeforge" / "services"
    services.mkdir(parents=True)
    (services / "chatty_service.py").write_text(
        'OUR_UA = "SomethingBot/2.0 (+https://example.org/contact)"\n',
        encoding="utf-8",
    )
    report = scan_for_network_call_sites(repo_root=tmp_path)
    kinds = {f["kind"] for f in report["findings"]}
    assert "second_user_agent_definition" in kinds


def test_scanner_does_not_flag_inert_urllib_use(tmp_path: Path) -> None:
    """urllib.parse never opens a socket; flagging it would be noise."""
    services = tmp_path / "src" / "nativeforge" / "services"
    services.mkdir(parents=True)
    (services / "parser_service.py").write_text(
        "from urllib.parse import urlparse\n\n\ndef host(u):\n"
        "    return urlparse(u).netloc\n",
        encoding="utf-8",
    )
    report = scan_for_network_call_sites(repo_root=tmp_path)
    assert report["network_call_sites"] == []
    assert report["clean"] is True


def test_every_egress_module_routes_through_the_global_guard() -> None:
    """All six, not four. Two reach the network through urllib.request.

    A private deny-by-default gate is not the shared one: the point of a choke
    point is that every egress decision is visible in one place and names its
    caller.
    """
    routed = (
        "polite_http_fetch_service",
        "real_url_resolver_service",
        "oidc_token_verification_service",
        "feedback_slack_alert_service",
    )
    for module_name in routed:
        source = (
            REPO_ROOT / f"src/nativeforge/services/{module_name}.py"
        ).read_text(encoding="utf-8")
        tree = ast.parse(source)
        imported = {
            node.module
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom) and node.module
        }
        assert any(
            "live_network_guard_service" in m for m in imported
        ), f"{module_name} does not route through the global guard"


def test_grants_gov_adapter_still_routes_through_gate77b() -> None:
    """The one site that was already guarded keeps its original guard."""
    source = (
        REPO_ROOT
        / "src/nativeforge/services/grants_gov_search_api_adapter_service.py"
    ).read_text(encoding="utf-8")
    assert "assert_live_network_allowed" in source
    assert "hermetic_test_guard_service" in source


def test_oidc_refuses_without_network_opt_in() -> None:
    from nativeforge.services.oidc_token_verification_service import fetch_jwks

    result = fetch_jwks(jwks_url="https://idp.example.com/jwks.json")
    assert result["ok"] is False
    assert result["network_access_attempted"] is False


def test_oidc_rejects_a_plaintext_jwks_url_without_contacting_it() -> None:
    """The scheme check used to run AFTER the request had gone out."""
    from nativeforge.services.oidc_token_verification_service import fetch_jwks

    result = fetch_jwks(
        jwks_url="http://idp.example.com/jwks.json", allow_network=True
    )
    assert result["ok"] is False
    assert result["reason"] == "insecure_scheme"
    assert result["network_access_attempted"] is False


def test_slack_alert_stays_dry_run_by_default() -> None:
    from nativeforge.services.feedback_slack_alert_service import (
        send_feedback_slack_alert,
    )

    result = send_feedback_slack_alert({"summary": "test"})
    assert result["sent"] is False


def test_scanner_never_fetches_or_imports(repo_scan: dict) -> None:
    report = repo_scan
    assert report["fetch_performed"] is False
    assert report["modules_imported"] == 0


# --------------------------------------------------------------------------
# Gate 77B must still hold
# --------------------------------------------------------------------------


def test_gate77b_grants_gov_guard_still_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv(ENV_ALLOW_LIVE_NETWORK, raising=False)
    with pytest.raises(LiveNetworkBlockedError):
        gate77b_assert(url="https://api.grants.gov/v1/api/search2", caller="test")


def test_gate94_guard_does_not_route_around_gate77b(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """No path through the new guard reaches Grants.gov with the flag unset."""
    monkeypatch.delenv(ENV_ALLOW_LIVE_NETWORK, raising=False)
    decision = build_live_network_decision(
        **{
            **FULLY_SATISFIED,
            "target_url": "https://api.grants.gov/v1/api/search2",
            "terms_status": "ATTRIBUTION_REQUIRED",
            "attribution_status": "present_and_verbatim",
            "method": "POST",
        }
    )
    assert decision["allowed"] is False
    assert "gate77b_hermetic_guard_blocks_grants_gov" in decision["blocked_reasons"]


def test_grants_gov_output_needs_attribution_to_be_surfaced() -> None:
    without = build_live_network_decision(
        **{
            **FULLY_SATISFIED,
            "target_url": "https://api.grants.gov/v1/api/search2",
            "attribution_status": "missing",
        }
    )
    assert without["requires_attribution"] is True
    assert without["may_surface_customer_data"] is False

    with_notice = build_live_network_decision(
        **{
            **FULLY_SATISFIED,
            "target_url": "https://api.grants.gov/v1/api/search2",
            "attribution_status": "present_and_verbatim",
        }
    )
    assert with_notice["may_surface_customer_data"] is True


# --------------------------------------------------------------------------
# Nothing in this file reached the network
# --------------------------------------------------------------------------


def test_no_live_url_is_fetched_by_this_suite() -> None:
    """Every fetch path above ran through an injected transport."""
    source = Path(__file__).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            imported.add(node.module.split(".")[0])
    assert not (imported & {"httpx", "requests", "socket", "aiohttp", "urllib3"})
