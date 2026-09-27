"""The fifth network purpose, and what it deliberately does not grant.

`customer_supplied_url` exists because a signed-in customer naming one exact
public URL is a different thing from a crawler working a source. The two are
gated on different evidence: a source is authorized per host, in advance, by a
recorded decision, and a pasted link has none of that and never can.

The risk in adding a purpose is that it becomes a way around the gates the
other four carry. These tests are mostly about what it still refuses.
"""

from __future__ import annotations

import pytest

from nativeforge.services.live_network_guard_service import (
    PURPOSE_REQUIREMENTS,
    PURPOSES,
    build_live_network_decision,
)

PURPOSE = "customer_supplied_url"
PUBLIC_URL = "https://www.hud.gov/program_offices/public_indian_housing/ih/codetalk"


def decide(**overrides):
    args = {
        "purpose": PURPOSE,
        "target_url": PUBLIC_URL,
        "caller": "customer_supplied_url_fetch_service",
        "allow_live_fetch": True,
        "user_agent_status": "canonical",
        "rate_limit_status": "policy_declared",
        "robots_status": "allowed",
        "destination_status": "public",
    }
    args.update(overrides)
    return build_live_network_decision(**args)


# ------------------------------------------------------------ the happy path


def test_a_signed_in_customers_public_link_is_allowed():
    decision = decide()
    assert decision["decision_status"] == "allowed"
    assert decision["requirements_missing"] == []
    assert decision["blocked_reasons"] == []


def test_the_purpose_is_in_the_vocabulary():
    assert PURPOSE in PURPOSES


# --------------------------------------------------- what it still refuses


@pytest.mark.parametrize(
    ("override", "missing"),
    [
        ({"allow_live_fetch": False}, "live_fetch_opt_in"),
        ({"target_url": "http://www.hud.gov/x"}, "https_scheme"),
        ({"robots_status": "disallowed"}, "robots_permits"),
        ({"user_agent_status": "non_canonical"}, "user_agent_canonical"),
        ({"rate_limit_status": "missing"}, "rate_limit_policy"),
        ({"destination_status": "loopback"}, "public_destination"),
    ],
)
def test_each_requirement_blocks_on_its_own(override: dict, missing: str):
    decision = decide(**override)
    assert decision["decision_status"] != "allowed"
    assert missing in decision["requirements_missing"]


def test_a_caller_that_forgets_the_destination_check_is_refused():
    """Not waved through.

    The parameter defaults to None and anything but "public" fails, so a
    caller that never resolved the host - or never thought to - is blocked
    rather than trusted.
    """
    decision = decide(destination_status=None)
    assert decision["decision_status"] != "allowed"
    assert "public_destination" in decision["requirements_missing"]


@pytest.mark.parametrize(
    "status", ["loopback", "private", "link_local", "multicast", "unknown", ""]
)
def test_only_the_word_public_satisfies_the_destination_check(status: str):
    assert (
        "public_destination"
        in decide(destination_status=status)["requirements_missing"]
    )


def test_politeness_on_somebody_elses_host_still_applies():
    """A customer naming a URL does not make NativeForge welcome to ignore
    robots or to hammer the host."""
    required = PURPOSE_REQUIREMENTS[PURPOSE]
    assert "robots_permits" in required
    assert "rate_limit_policy" in required
    assert "user_agent_canonical" in required


def test_the_grants_gov_choke_point_is_not_bypassed():
    """Gate 77B owns Grants.gov, and a new purpose must not route around it."""
    decision = decide(target_url="https://www.grants.gov/search-results")
    assert decision["decision_status"] != "allowed"
    assert any("grants_gov" in r for r in decision["blocked_reasons"])


# ------------------------------------------------ what it does NOT grant


def test_it_does_not_require_or_grant_source_activation():
    """The three per-source authorizations are absent on purpose.

    Requiring them would make the purpose unusable, because no recorded
    decision exists for an address a customer typed a moment ago. Their
    absence must therefore never be read as the purpose *having* them: it
    authorizes one request, and nothing about a source.
    """
    required = PURPOSE_REQUIREMENTS[PURPOSE]
    assert "activation_allowed" not in required
    assert "collector_active" not in required
    assert "terms_cleared" not in required

    decision = decide()
    assert decision["requires_activation"] is False


def test_it_authorizes_one_request_and_reports_a_rate_limit():
    # A per-host interval still comes back, because one customer-named URL
    # today is one more tomorrow and the host does not care why.
    decision = decide()
    assert decision["min_request_interval_seconds"] > 0


def test_the_other_four_purposes_are_untouched():
    """Adding a purpose must not relax an existing one."""
    assert PURPOSE_REQUIREMENTS["source_collection"] == (
        "live_fetch_opt_in",
        "https_scheme",
        "host_permitted",
        "user_agent_canonical",
        "rate_limit_policy",
        "terms_cleared",
        "activation_allowed",
        "collector_active",
        "robots_permits",
        "credential",
    )
    assert "public_destination" not in PURPOSE_REQUIREMENTS["source_discovery"]
    assert "public_destination" not in PURPOSE_REQUIREMENTS["identity_verification"]


def test_an_unknown_purpose_is_still_refused():
    decision = build_live_network_decision(
        purpose="customer_supplied_anything",
        target_url=PUBLIC_URL,
        caller="t",
        allow_live_fetch=True,
    )
    assert decision["decision_status"] == "blocked"
    assert any("purpose_out_of_vocabulary" in r for r in decision["blocked_reasons"])
