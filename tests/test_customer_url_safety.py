"""Which destinations a customer may send this server to.

The addresses that matter are not the ones that look dangerous. They are
`169.254.169.254`, `localhost`, `::1`, and a hostname whose DNS record
happens to point inside the deployment's own network — so every class gets a
case here, including the ones that only bite when wrapped in IPv6.

These need no network, which is the point of keeping the decision separate
from the request.
"""

from __future__ import annotations

import pytest

from nativeforge.services.customer_url_safety_service import (
    MAX_RESPONSE_BYTES,
    classify_address,
    evaluate_content_type,
    evaluate_length,
    evaluate_url,
)

PUBLIC = ["93.184.216.34"]


def _allow(url: str, addresses=None):
    return evaluate_url(url, resolved_addresses=addresses or PUBLIC)


# ----------------------------------------------------------- the happy path


def test_a_public_https_document_url_is_allowed():
    decision = _allow("https://www.grants.gov/web/grants/view-opportunity.html?oppId=1")
    assert decision.allowed is True
    assert decision.blocked_reasons == ()
    assert decision.host == "www.grants.gov"
    assert decision.port == 443


# ------------------------------------------------------- address classes


@pytest.mark.parametrize(
    ("address", "label"),
    [
        ("127.0.0.1", "loopback"),
        ("127.255.255.254", "loopback"),
        ("10.0.0.1", "private"),
        ("172.16.31.9", "private"),
        ("192.168.1.1", "private"),
        ("169.254.169.254", "link_local"),
        ("169.254.1.1", "link_local"),
        ("0.0.0.0", "unspecified"),
        ("224.0.0.1", "multicast"),
        ("100.64.0.1", "not_global"),
        ("::1", "loopback"),
        ("fe80::1", "link_local"),
        ("fc00::1", "private"),
        ("fd00:ec2::254", "private"),
        ("ff02::1", "multicast"),
        ("::", "unspecified"),
    ],
)
def test_every_non_public_class_is_refused_and_named(address: str, label: str):
    ok, got = classify_address(address)
    assert ok is False
    assert got == label


@pytest.mark.parametrize("address", ["93.184.216.34", "8.8.8.8", "2606:2800:220:1::1"])
def test_public_addresses_are_allowed(address: str):
    ok, label = classify_address(address)
    assert ok is True
    assert label == "global"


@pytest.mark.parametrize(
    "address",
    ["::ffff:127.0.0.1", "::ffff:169.254.169.254", "::ffff:10.0.0.1"],
)
def test_an_ipv4_mapped_address_is_seen_through(address: str):
    """`::ffff:169.254.169.254` is the metadata endpoint in a different hat.

    `is_global` on the v6 wrapper does not see the address inside it, so the
    mapping is unwrapped before anything is decided.
    """
    ok, _ = classify_address(address)
    assert ok is False


def test_something_that_is_not_an_address_is_not_public():
    ok, label = classify_address("not-an-address")
    assert ok is False
    assert label == "not_an_ip_address"


# ---------------------------------------------------------------- the URL


def test_an_unresolved_host_is_never_allowed():
    """Unresolved means unproven.

    Treating "no addresses supplied" as "nothing wrong" is the hole this
    module exists to close: it would allow every hostname, including the ones
    that resolve inside the network.
    """
    decision = evaluate_url("https://example.gov/notice")
    assert decision.allowed is False
    assert "host_was_not_resolved" in decision.blocked_reasons


def test_a_host_resolving_anywhere_internal_is_refused():
    # One bad address in the set is enough: the client could connect to any
    # of them.
    decision = _allow("https://sneaky.example/notice", ["93.184.216.34", "10.0.0.5"])
    assert decision.allowed is False
    assert any(
        r.startswith("destination_not_public:") for r in decision.blocked_reasons
    )


def test_a_refusal_does_not_name_the_internal_address():
    """It would be a small map of the network, handed to whoever sent the URL."""
    decision = _allow("https://sneaky.example/notice", ["10.11.12.13"])
    assert "10.11.12.13" not in repr(decision.blocked_reasons)


@pytest.mark.parametrize(
    "url",
    [
        "http://www.grants.gov/notice",
        "file:///etc/passwd",
        "ftp://example.gov/notice",
        "gopher://example.gov/",
        "//example.gov/notice",
    ],
)
def test_only_https_is_accepted(url: str):
    decision = _allow(url)
    assert decision.allowed is False
    assert any(r.startswith("scheme_not_allowed") for r in decision.blocked_reasons)


def test_a_non_standard_port_is_refused():
    """An arbitrary port is how a URL reaches an internal HTTP service."""
    decision = _allow("https://example.gov:8080/notice")
    assert decision.allowed is False
    assert "port_not_allowed:8080" in decision.blocked_reasons


def test_credentials_in_the_url_are_refused():
    # A way to make one host look like another, and a way to hand a secret to
    # whatever is actually at the far end.
    decision = _allow("https://user:secret@example.gov/notice")
    assert decision.allowed is False
    assert "url_contains_credentials" in decision.blocked_reasons


def test_an_empty_or_unparseable_url_is_refused():
    assert evaluate_url("").allowed is False
    assert evaluate_url("   ").allowed is False
    assert evaluate_url("https://").allowed is False


def test_reasons_are_not_repeated():
    decision = _allow("https://sneaky.example/x", ["10.0.0.1", "10.0.0.2", "10.0.0.3"])
    assert len(decision.blocked_reasons) == len(set(decision.blocked_reasons))


def test_the_decision_serialises_without_the_addresses_becoming_a_leak():
    decision = _allow("https://www.grants.gov/notice")
    payload = decision.as_dict()
    assert payload["allowed"] is True
    assert payload["host"] == "www.grants.gov"


# ------------------------------------------------------------- responses


@pytest.mark.parametrize(
    "value",
    ["text/html", "text/html; charset=utf-8", "application/pdf", "TEXT/PLAIN"],
)
def test_document_content_types_are_accepted(value: str):
    ok, _ = evaluate_content_type(value)
    assert ok is True


@pytest.mark.parametrize(
    "value",
    ["application/zip", "image/png", "application/octet-stream", "", None],
)
def test_other_content_types_are_refused(value):
    ok, _ = evaluate_content_type(value)
    assert ok is False


def test_an_oversized_declared_body_is_refused_before_transfer():
    ok, reason = evaluate_length(str(MAX_RESPONSE_BYTES + 1))
    assert ok is False
    assert reason.startswith("response_too_large")


def test_a_missing_or_unparseable_length_is_not_by_itself_a_refusal():
    """The reader enforces the real limit as bytes arrive.

    A server can understate `Content-Length` or omit it, so this check can
    only reject the honest oversized response. Refusing every response that
    omits the header would reject most chunked ones.
    """
    assert evaluate_length(None)[0] is True
    assert evaluate_length("")[0] is True
    assert evaluate_length("banana")[0] is True
    assert evaluate_length(str(MAX_RESPONSE_BYTES))[0] is True
