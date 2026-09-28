"""Deployment identity reads provider commit stamps when NF_GIT_SHA is blank."""

from __future__ import annotations

from nativeforge.lib.deployment_identity import resolve_deployment_sha
from nativeforge.lib.settings import Settings, get_settings


SHA = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"


def test_railway_sha_is_used_when_product_stamp_is_unknown(
    monkeypatch,
) -> None:
    monkeypatch.delenv("NF_GIT_SHA", raising=False)
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", SHA)
    assert resolve_deployment_sha() == SHA


def test_settings_fill_provider_sha(monkeypatch) -> None:
    monkeypatch.setenv("NF_GIT_SHA", "unknown")
    monkeypatch.setenv("RAILWAY_GIT_COMMIT_SHA", SHA)
    get_settings.cache_clear()
    try:
        settings = Settings(_env_file=None)
        assert settings.nf_git_sha == SHA
    finally:
        get_settings.cache_clear()


def test_unknown_when_no_stamp(monkeypatch) -> None:
    for key in (
        "NF_GIT_SHA",
        "RAILWAY_GIT_COMMIT_SHA",
        "COMMIT_SHA",
        "SOURCE_VERSION",
        "GITHUB_SHA",
    ):
        monkeypatch.delenv(key, raising=False)
    assert resolve_deployment_sha() == "unknown"
