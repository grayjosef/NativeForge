"""Resolve the commit a process is actually running.

`NF_GIT_SHA` is the product stamp. Hosting providers also publish the same
commit under their own names. Production reported `unknown` when only the
provider variable was set, so this reads the known provider names after the
product stamp — never inventing a SHA, never logging the rest of the env.
"""

from __future__ import annotations

import os
import re

_HEX_SHA = re.compile(r"^[0-9a-f]{40}$")

PROVIDER_SHA_KEYS: tuple[str, ...] = (
    "NF_GIT_SHA",
    "RAILWAY_GIT_COMMIT_SHA",
    "COMMIT_SHA",
    "SOURCE_VERSION",
    "GITHUB_SHA",
)


def normalize_git_sha(raw: str | None) -> str | None:
    sha = (raw or "").strip().lower()
    if sha.startswith("sha-"):
        sha = sha[4:]
    if _HEX_SHA.fullmatch(sha):
        return sha
    return None


def resolve_deployment_sha() -> str:
    for key in PROVIDER_SHA_KEYS:
        found = normalize_git_sha(os.environ.get(key))
        if found:
            return found
    return "unknown"
