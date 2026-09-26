"""Gate 181: /health reports what is actually deployed.

A health endpoint that only says `ok` cannot verify a deployment. It proves
something is answering; it does not prove the thing answering is the thing you
shipped. `git_sha` turns "is the new version live?" into a question with an
answer, which is the whole point of the check after a cutover.

Derived from the environment, never from git. The workstation services run
`git rev-parse HEAD` and `git status --porcelain`, which works in a checkout
and returns nothing useful in a container - no `.git`, no git binary. That is
precisely the environment where the answer matters, so the value is stamped
into the image at build time instead.

The `source_dirty` tri-state is the part worth defending. `null` is not a
synonym for clean. An unstamped image has been told nothing, and reporting
`false` there would assert cleanliness on no evidence - the same mistake as a
gate that clears a blocker because a variable was never set.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from nativeforge.api.health import _source_dirty
from nativeforge.lib.settings import Settings, get_settings
from nativeforge.main import app


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_health_carries_the_deployment_identity(client: TestClient) -> None:
    body = client.get("/health").json()
    assert set(body) == {"status", "service", "git_sha", "source_dirty"}


def test_unstamped_is_unknown_not_a_fabricated_sha() -> None:
    settings = Settings(_env_file=None)
    assert settings.nf_git_sha == "unknown"
    assert settings.nf_source_dirty == "unknown"


def test_an_unstamped_build_does_not_claim_a_clean_tree() -> None:
    """Absence of evidence is not evidence of cleanliness."""
    assert _source_dirty("unknown") is None
    assert _source_dirty("") is None
    assert _source_dirty("   ") is None


@pytest.mark.parametrize("raw", ["true", "TRUE", "1", "yes", "on"])
def test_dirty_values_read_as_true(raw: str) -> None:
    assert _source_dirty(raw) is True


@pytest.mark.parametrize("raw", ["false", "FALSE", "0", "no", "off"])
def test_clean_values_read_as_false(raw: str) -> None:
    assert _source_dirty(raw) is False


def test_the_stamp_reaches_the_response(monkeypatch: pytest.MonkeyPatch) -> None:
    """What the build sets is what the endpoint reports."""
    sha = "0123456789abcdef0123456789abcdef01234567"
    monkeypatch.setenv("NF_GIT_SHA", sha)
    monkeypatch.setenv("NF_SOURCE_DIRTY", "false")
    get_settings.cache_clear()
    try:
        body = TestClient(app).get("/health").json()
        assert body["git_sha"] == sha
        assert body["source_dirty"] is False
    finally:
        get_settings.cache_clear()


def test_health_carries_no_credential(client: TestClient) -> None:
    text = client.get("/health").text
    for marker in ("-----BEGIN", "eyJ", "Bearer ", "postgresql://", "password="):
        assert marker not in text, marker
