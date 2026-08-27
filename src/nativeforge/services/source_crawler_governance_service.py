"""Crawler governance contracts (Gate 92H).

Nothing here crawls. It declares the rules a collector must satisfy *before*
one is written, so the rules exist ahead of the code that would break them.

## User-agent

A descriptive NativeForge UA with a contact URL. **Never an AI-crawler UA.**
hud.gov's robots.txt names ClaudeBot, GPTBot, CCBot, Amazonbot,
Applebot-Extended, Bytespider, Google-Extended, meta-externalagent and others
with ``Disallow: /``, and asserts content signals - including ``ai-train=no`` -
as a condition of access. Presenting one of those UA strings is both a robots
violation and a terms violation, so the forbidden list is enforced by
substring, case-insensitively, rather than by exact match.

## Pacing

No host in the entire research set publishes a ``Crawl-delay``. Absence of a
declared floor is not permission for speed, so the floor is self-imposed:
per-host concurrency of **1** and roughly **one request per 5 seconds**.

## Site search is off-limits almost everywhere

``Disallow: /search/`` is near-universal - sam.gov, ojp.gov, hud.gov, epa.gov,
energy.gov, grants.nih.gov, rd.usda.gov, bia.gov, with path-specific variants
on federalregister.gov and usaspending.gov. A monitor that polls site-search
URLs violates robots on almost every agency host. Poll sitemaps, listing pages,
feeds, or APIs.

## Circuit breaker, not retry

After N consecutive failures a source halts and pages a human. Retrying into a
block is how access gets revoked permanently, and SAM.gov names that
consequence explicitly.

## Dead shells beat 404s

HUD's ``/program_offices/public_indian_housing/ih`` returns **HTTP 200 with
valid HTML and zero body content**, titled ``25red-Indian Housing``. A monitor
keyed on status code reports "no change" there forever. So liveness is decided
on **body hash and content length**, never on status alone, and a
redesign-artifact title prefix (``25red-``) marks a page stale rather than
unchanged.

## Blacklist

``scdmh.net`` was fetched and found to be a **hijacked casino site** - it is
blocked outright, not merely deprioritized. The legacy ``scdhec.gov`` domain
was reorganized in 2024 into SC DES and SC DPH and is stale. CDC's ``/tribal/*``
namespace serves 2016 Zika content while the live material is under
``/healthy-tribes/*``.
"""

from __future__ import annotations

import json
import re
from typing import Any
from urllib.parse import urlsplit

from nativeforge.services.nativeforge_user_agent_service import (
    FORBIDDEN_USER_AGENT_TOKENS as _FORBIDDEN_TOKENS,
)
from nativeforge.services.nativeforge_user_agent_service import (
    NATIVEFORGE_USER_AGENT as _CANONICAL_USER_AGENT,
)

SCHEMA_VERSION = "nf_source_crawler_governance_v1"

# Gate 94C: the canonical user-agent and the forbidden-token list moved to
# `nativeforge_user_agent_service`, which now owns user-agent facts outright.
# While this module owned the string, a second one lived in the polite fetcher
# without governance knowing - and the contact in the string it did own pointed
# at `nativeforge.example`, a reserved domain nobody can reach.
#
# Re-exported here so every existing importer, including Gate 92's tests, keeps
# working against one definition rather than a copy.
NATIVEFORGE_USER_AGENT = _CANONICAL_USER_AGENT
FORBIDDEN_USER_AGENT_TOKENS = _FORBIDDEN_TOKENS

# Self-imposed floors. No host in the set declares a Crawl-delay.
PER_HOST_CONCURRENCY = 1
MIN_REQUEST_INTERVAL_SECONDS = 5.0
CIRCUIT_BREAKER_CONSECUTIVE_FAILURES = 5

# Path prefixes that robots.txt disallows on nearly every agency host.
UNIVERSALLY_DISALLOWED_PATH_PREFIXES: tuple[str, ...] = (
    "/search/",
    "/search?",
    "/admin/",
    "/user/",
    "/my/",
    "/auth/",
    "/core/",
    "/profiles/",
    "/media/oembed",
)

# Hosts that must never be fetched, with the reason each one is here.
BLACKLISTED_HOSTS: dict[str, str] = {
    "scdmh.net": "fetched and found to be a hijacked casino site",
    "scdhec.gov": (
        "legacy domain; agency reorganized in 2024 into SC DES and SC DPH"
    ),
    "www.scdmh.net": "fetched and found to be a hijacked casino site",
    "www.scdhec.gov": (
        "legacy domain; agency reorganized in 2024 into SC DES and SC DPH"
    ),
}

# Host + path-prefix pairs that are blocked without blocking the whole host.
BLACKLISTED_PATH_PREFIXES: tuple[tuple[str, str, str], ...] = (
    (
        "cdc.gov",
        "/tribal/",
        "serves 2016 Zika content; live material is under /healthy-tribes/",
    ),
    (
        "www.cdc.gov",
        "/tribal/",
        "serves 2016 Zika content; live material is under /healthy-tribes/",
    ),
)

# Known dead shells: HTTP 200, valid HTML, no body content.
DEAD_SHELL_TITLE_PREFIXES: tuple[str, ...] = ("25red-",)

# A body shorter than this on an HTTP 200 is a shell, not a page.
DEAD_SHELL_MIN_BODY_BYTES = 512

LIVENESS_VERDICTS = frozenset(
    {"live", "dead_shell", "stale_redesign_artifact", "blocked", "unknown"}
)

_HOST_RE = re.compile(r"^[a-z0-9.-]+$")


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _host_and_path(url: Any) -> tuple[str, str]:
    parts = urlsplit(str(url or ""))
    host = (parts.netloc or "").lower().split("@")[-1].split(":")[0]
    path = parts.path or "/"
    if parts.query:
        path = f"{path}?{parts.query}"
    return host, path


def user_agent_violations(user_agent: Any) -> list[str]:
    """Deny by default: an empty or unrecognised UA is a violation."""
    ua = str(user_agent or "").strip()
    fails: list[str] = []
    if not ua:
        fails.append("user_agent_empty")
        return fails
    lowered = ua.lower()
    for token in sorted(FORBIDDEN_USER_AGENT_TOKENS):
        if token in lowered:
            fails.append(f"ai_crawler_user_agent:{token}")
    if "nativeforge" not in lowered:
        fails.append("user_agent_does_not_identify_nativeforge")
    if "http" not in lowered:
        fails.append("user_agent_carries_no_contact_url")
    return fails


def evaluate_fetch_permission(*, url: Any, user_agent: Any) -> dict[str, Any]:
    """Would this fetch be permitted? This never performs the fetch."""
    host, path = _host_and_path(url)
    reasons: list[str] = []

    if not host or not _HOST_RE.match(host):
        reasons.append("host_unparseable")

    if host in BLACKLISTED_HOSTS:
        reasons.append(f"host_blacklisted:{BLACKLISTED_HOSTS[host]}")

    for bl_host, prefix, why in BLACKLISTED_PATH_PREFIXES:
        if host == bl_host and path.startswith(prefix):
            reasons.append(f"path_blacklisted:{prefix}:{why}")

    for prefix in UNIVERSALLY_DISALLOWED_PATH_PREFIXES:
        if path.startswith(prefix):
            reasons.append(f"robots_disallowed_path:{prefix}")

    reasons.extend(user_agent_violations(user_agent))

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "url": str(url or ""),
            "host": host,
            "path": path,
            "permitted": not reasons,
            "denial_reasons": reasons,
            "per_host_concurrency": PER_HOST_CONCURRENCY,
            "min_request_interval_seconds": MIN_REQUEST_INTERVAL_SECONDS,
            "fetch_performed": False,
            "fabricated": False,
        }
    )


def classify_page_liveness(
    *,
    http_status: Any = None,
    body_bytes: Any = None,
    body_hash: Any = None,
    previous_body_hash: Any = None,
    page_title: Any = None,
) -> dict[str, Any]:
    """Decide liveness from body evidence. Status code alone is never enough."""
    title = str(page_title or "")
    stale_prefix = next(
        (p for p in DEAD_SHELL_TITLE_PREFIXES if title.startswith(p)), None
    )

    size = body_bytes if isinstance(body_bytes, int) else None
    status_ok = http_status == 200

    if stale_prefix:
        # A redesign artifact is stale, and stale is not "unchanged" - it must
        # be flagged rather than diffed.
        verdict = "stale_redesign_artifact"
    elif status_ok and size is not None and size < DEAD_SHELL_MIN_BODY_BYTES:
        verdict = "dead_shell"
    elif status_ok and size is not None:
        verdict = "live"
    else:
        verdict = "unknown"

    changed = (
        body_hash is not None
        and previous_body_hash is not None
        and body_hash != previous_body_hash
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "http_status": http_status,
            "body_bytes": size,
            "page_title": title,
            "verdict": verdict,
            "stale_title_prefix": stale_prefix,
            # Only a live page may be diffed. A shell would read "unchanged"
            # forever.
            "eligible_for_diff": verdict == "live",
            "content_changed": changed if verdict == "live" else False,
            "decided_on_status_alone": False,
            "fabricated": False,
        }
    )


def build_circuit_breaker_state(
    *,
    source_id: Any,
    consecutive_failures: int = 0,
) -> dict[str, Any]:
    tripped = consecutive_failures >= CIRCUIT_BREAKER_CONSECUTIVE_FAILURES
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": source_id,
            "consecutive_failures": consecutive_failures,
            "threshold": CIRCUIT_BREAKER_CONSECUTIVE_FAILURES,
            "tripped": tripped,
            # Tripped means stop and page a human, not back off and retry.
            "halts_source": tripped,
            "pages_human": tripped,
            "auto_retries_after_trip": False,
            "fabricated": False,
        }
    )


def governance_invariant_failures(record: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if record.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if record.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    # Fetch-permission records.
    if "permitted" in record:
        if record.get("fetch_performed") is not False:
            fails.append("governance_record_claimed_a_fetch")
        if record.get("per_host_concurrency") != PER_HOST_CONCURRENCY:
            fails.append("per_host_concurrency_relaxed")
        if record.get("min_request_interval_seconds", 0) < MIN_REQUEST_INTERVAL_SECONDS:
            fails.append("request_interval_below_floor")
        host = record.get("host")
        if host in BLACKLISTED_HOSTS and record.get("permitted"):
            fails.append(f"blacklisted_host_permitted:{host}")
        if record.get("permitted") and record.get("denial_reasons"):
            fails.append("permitted_despite_denial_reasons")
        if not record.get("permitted") and not record.get("denial_reasons"):
            fails.append("denied_without_a_reason")

    # Liveness records.
    if "verdict" in record:
        if record.get("verdict") not in LIVENESS_VERDICTS:
            fails.append("liveness_verdict_out_of_vocabulary")
        if record.get("decided_on_status_alone") is not False:
            fails.append("liveness_decided_on_status_alone")
        if record.get("verdict") != "live" and record.get("eligible_for_diff"):
            fails.append("non_live_page_marked_diffable")
        if record.get("verdict") != "live" and record.get("content_changed"):
            fails.append("non_live_page_reported_a_content_change")
        if record.get("stale_title_prefix") and record.get("verdict") != (
            "stale_redesign_artifact"
        ):
            fails.append("redesign_artifact_not_flagged_stale")

    # Circuit-breaker records.
    if "tripped" in record:
        if record.get("threshold") != CIRCUIT_BREAKER_CONSECUTIVE_FAILURES:
            fails.append("circuit_breaker_threshold_altered")
        if record.get("auto_retries_after_trip") is not False:
            fails.append("circuit_breaker_retries_into_a_block")
        if record.get("tripped") and not record.get("pages_human"):
            fails.append("circuit_breaker_tripped_without_paging")
        if record.get("tripped") and not record.get("halts_source"):
            fails.append("circuit_breaker_tripped_without_halting")

    return fails
