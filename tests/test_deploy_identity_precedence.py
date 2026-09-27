"""Which commit a deployment reports, when two sources disagree.

`/health`'s `git_sha` exists to make "is the new version live?" answerable.
It was answering wrongly: production served endpoints that commit 98814839
had never contained while reporting 98814839, because `scripts/deploy_railway.sh`
sets `NF_GIT_SHA` as a Railway *service* variable - which persists - and the
entrypoint preferred it over the platform's own per-deployment variable.
Railway also auto-deploys on push, bypassing the wrapper entirely, so every
such deployment inherited the stamp from whenever the wrapper last ran.

These run the real entrypoint. The `*` branch execs whatever it is given, so
`env` prints the environment the serve branch would have used, after the
identity block has resolved it.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

ENTRYPOINT = Path(__file__).resolve().parents[1] / "deploy" / "docker-entrypoint.sh"

PROVIDER_SHA = "1111111111111111111111111111111111111111"
EXPLICIT_SHA = "2222222222222222222222222222222222222222"


def _resolve(**env: str) -> tuple[str, str]:
    """Return (resolved NF_GIT_SHA, entrypoint log output)."""
    # A clean environment: this machine's own CI variables would otherwise be
    # inherited and silently supply a candidate the test never set.
    base = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "NF_RUN_MIGRATIONS": "false",
    }
    for name in (
        "NF_GIT_SHA",
        "RAILWAY_GIT_COMMIT_SHA",
        "SOURCE_VERSION",
        "VERCEL_GIT_COMMIT_SHA",
        "GITHUB_SHA",
        "CI_COMMIT_SHA",
    ):
        base.pop(name, None)
    base.update(env)

    done = subprocess.run(
        ["bash", str(ENTRYPOINT), "env"],
        capture_output=True,
        text=True,
        env=base,
        timeout=60,
        check=False,
    )
    resolved = ""
    for line in done.stdout.splitlines():
        if line.startswith("NF_GIT_SHA="):
            resolved = line.split("=", 1)[1]
    return resolved, done.stdout + done.stderr


def test_the_platform_commit_wins_over_a_stale_explicit_stamp():
    """The exact production defect, as a test.

    A provider commit variable is set per deployment and cannot go stale. An
    explicit one can, and did.
    """
    resolved, _ = _resolve(
        NF_GIT_SHA=EXPLICIT_SHA,
        RAILWAY_GIT_COMMIT_SHA=PROVIDER_SHA,
    )
    assert resolved == PROVIDER_SHA


def test_a_disagreement_is_reported_rather_than_resolved_silently():
    """Picking one and saying nothing is how this went unnoticed for a week."""
    _, output = _resolve(
        NF_GIT_SHA=EXPLICIT_SHA,
        RAILWAY_GIT_COMMIT_SHA=PROVIDER_SHA,
    )
    assert "disagrees with the provider's commit" in output
    assert EXPLICIT_SHA in output
    assert PROVIDER_SHA in output


def test_an_explicit_stamp_is_used_when_no_provider_variable_exists():
    """The wrapper still works on a provider that sets nothing of its own."""
    resolved, output = _resolve(NF_GIT_SHA=EXPLICIT_SHA)
    assert resolved == EXPLICIT_SHA
    assert "disagrees" not in output


def test_agreement_is_not_reported_as_a_disagreement():
    resolved, output = _resolve(
        NF_GIT_SHA=PROVIDER_SHA,
        RAILWAY_GIT_COMMIT_SHA=PROVIDER_SHA,
    )
    assert resolved == PROVIDER_SHA
    assert "disagrees" not in output


def test_other_providers_are_still_honoured():
    for name in (
        "SOURCE_VERSION",
        "VERCEL_GIT_COMMIT_SHA",
        "GITHUB_SHA",
        "CI_COMMIT_SHA",
    ):
        resolved, _ = _resolve(**{name: PROVIDER_SHA})
        assert resolved == PROVIDER_SHA, name


def test_an_anonymous_build_resolves_to_nothing_rather_than_a_guess():
    resolved, _ = _resolve()
    assert resolved == ""
