"""Hermetic test guard (Gate 77B).

Two defaults this module makes true, both of which were false before:

  1. **No live HTTP.** Calling a third-party API is opt-in behind an explicit,
     deliberately unpleasant environment flag.
  2. **No writing committed fixtures.** A write aimed at a source-controlled
     path is redirected under ``artifacts/`` unless two separate flags say
     otherwise.

Gate 77 found why both matter. `tests/test_sprint345_nf15_corrected_corpus.py`
called `api.grants.gov` at test time, so its result depended on a third party's
search ranking — and the same code path wrote its results back over
`fixtures/real_grants_corpus/nf15_eligibility_reingest_pulls.json`, a committed
record of a real grant.

The combination is the dangerous part. An online run would have written a live
`HHS-IHS` response over the recorded `SAMHSA / HHS` evidence and committed
fabricated agency ownership, produced by nothing more than running the suite.
Separating the two flags means a live refresh cannot silently become a rewrite
of the evidence it is supposed to be checked against.

**Redirect, not refuse, for writes.** A blocked write returns an artifact path
rather than raising, because the caller's real work (fetching, deriving,
reporting) is still valid and the output is still worth keeping. The redirect is
reported so it cannot be mistaken for a successful fixture update. Network is
the opposite: it raises, because there is no useful partial answer to "we were
not allowed to ask".
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_hermetic_test_guard_v1"

# Named to be conspicuous in a CI config or a shell history. Someone reading
# `NATIVEFORGE_ALLOW_LIVE_GRANTS_GOV_TESTS=1` should feel it.
ENV_ALLOW_LIVE_NETWORK = "NATIVEFORGE_ALLOW_LIVE_GRANTS_GOV_TESTS"
ENV_ALLOW_CORPUS_WRITEBACK = "NATIVEFORGE_ALLOW_CORPUS_WRITEBACK"
ENV_ALLOW_SOURCE_FIXTURE_OVERWRITE = "NATIVEFORGE_ALLOW_SOURCE_FIXTURE_OVERWRITE"

REPO_ROOT = Path(__file__).resolve().parents[3]

# Directories whose contents are committed evidence. A write landing here is
# rewriting the record, not producing an output.
SOURCE_CONTROLLED_DIRS = (
    REPO_ROOT / "fixtures",
    REPO_ROOT / "tests" / "fixtures",
    REPO_ROOT / "src" / "nativeforge" / "data",
)

# Where redirected writes go instead. Untracked.
ARTIFACT_WRITEBACK_DIR = REPO_ROOT / "artifacts" / "corpus_writeback"

TRUTHY = frozenset({"1", "true", "yes", "on"})


class LiveNetworkBlockedError(RuntimeError):
    """Raised when code attempts a live HTTP call without explicit permission."""


class SourceFixtureWriteBlockedError(RuntimeError):
    """Raised when a source-controlled fixture write is refused outright."""


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _flag(name: str) -> bool:
    """Read an opt-in flag. Anything unset or unrecognised is off.

    Deliberately strict: a typo'd value is off, not on. A guard that turns
    itself off on ``NATIVEFORGE_ALLOW_LIVE_GRANTS_GOV_TESTS=flase`` is not a
    guard.
    """
    return str(os.environ.get(name, "")).strip().lower() in TRUTHY


def live_network_allowed() -> bool:
    return _flag(ENV_ALLOW_LIVE_NETWORK)


def corpus_writeback_allowed() -> bool:
    return _flag(ENV_ALLOW_CORPUS_WRITEBACK)


def source_fixture_overwrite_allowed() -> bool:
    """Overwriting committed evidence needs BOTH flags.

    The second flag alone is not enough. Requiring both means an operator who
    enabled routine write-back cannot also clobber committed fixtures without a
    separate, conscious act.
    """
    return corpus_writeback_allowed() and _flag(ENV_ALLOW_SOURCE_FIXTURE_OVERWRITE)


def assert_live_network_allowed(*, url: str = "", caller: str = "") -> None:
    """Refuse a live HTTP call unless explicitly permitted.

    Raises rather than returning a sentinel: there is no useful partial answer
    to a request we were not allowed to make, and a silent empty result would
    be indistinguishable from a genuine no-results response — which is exactly
    how the corpus fixture got overwritten with a placeholder.
    """
    if live_network_allowed():
        return
    raise LiveNetworkBlockedError(
        "live HTTP is disabled by default. "
        f"caller={caller or 'unknown'} url={url or 'unknown'}. "
        f"Set {ENV_ALLOW_LIVE_NETWORK}=1 to permit a deliberate live fetch. "
        "Tests should inject a recorded transport instead — see "
        "docs/operations/429_GATE77B_HERMETIC_GRANTS_GOV_TEST_POLICY.md"
    )


def is_source_controlled(path: Path | str) -> bool:
    """Whether a path lands inside committed evidence."""
    try:
        resolved = Path(path).resolve()
    except (OSError, RuntimeError):  # pragma: no cover - defensive
        return False
    for root in SOURCE_CONTROLLED_DIRS:
        try:
            resolved.relative_to(root.resolve())
            return True
        except ValueError:
            continue
    return False


def resolve_writeback_path(
    target: Path | str, *, label: str = "corpus_writeback"
) -> dict[str, Any]:
    """Decide where a write may actually land.

    Returns the path to use plus whether it was redirected and why, so a caller
    can report the redirect rather than believing it updated a fixture.
    """
    original = Path(target)
    source_controlled = is_source_controlled(original)
    reasons: list[str] = []

    if not source_controlled:
        # Not committed evidence; the caller may write where it intended.
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "requested_path": str(original),
                "path": str(original),
                "source_controlled": False,
                "redirected": False,
                "reasons": [],
                "writeback_allowed": corpus_writeback_allowed(),
                "source_overwrite_allowed": source_fixture_overwrite_allowed(),
            }
        )

    if source_fixture_overwrite_allowed():
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "requested_path": str(original),
                "path": str(original),
                "source_controlled": True,
                "redirected": False,
                "reasons": ["explicitly_permitted_source_fixture_overwrite"],
                "writeback_allowed": True,
                "source_overwrite_allowed": True,
            }
        )

    if not corpus_writeback_allowed():
        reasons.append(f"{ENV_ALLOW_CORPUS_WRITEBACK}_not_set")
    if not _flag(ENV_ALLOW_SOURCE_FIXTURE_OVERWRITE):
        reasons.append(f"{ENV_ALLOW_SOURCE_FIXTURE_OVERWRITE}_not_set")
    reasons.append("refusing_to_overwrite_committed_evidence")

    redirected = ARTIFACT_WRITEBACK_DIR / label / original.name
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "requested_path": str(original),
            "path": str(redirected),
            "source_controlled": True,
            "redirected": True,
            "reasons": reasons,
            "writeback_allowed": corpus_writeback_allowed(),
            "source_overwrite_allowed": False,
        }
    )


def guarded_write_json(
    target: Path | str, payload: Any, *, label: str = "corpus_writeback"
) -> dict[str, Any]:
    """Write JSON to the resolved path, creating parents. Never clobbers
    committed evidence unless both flags are set."""
    decision = resolve_writeback_path(target, label=label)
    path = Path(decision["path"])
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    decision["written"] = True
    return decision


RECORDED_TRANSPORT_DIR = REPO_ROOT / "tests" / "fixtures" / "grants_gov"


class RecordedTransportMissingError(FileNotFoundError):
    """Raised when a recorded transport fixture is absent.

    Deliberately an error rather than a silent fall-through to the live client:
    "we have no recording" must never become "so ask the internet".
    """


def load_recorded_transport(name: str) -> Any:
    """Build an ``http_post(url, body)`` from a recorded fixture.

    Any URL the recording does not cover returns an empty, well-formed
    success — ``errorcode: 0`` with no hits. That models "the search found
    nothing", which is a real Grants.gov outcome and the one the corpus already
    records for ``nf-seed-2026-fed-025``. It invents no opportunity.
    """
    path = RECORDED_TRANSPORT_DIR / name
    if not path.is_file():
        raise RecordedTransportMissingError(
            f"recorded transport fixture not found: {path}. "
            "Record one deliberately; do not fall back to a live fetch."
        )
    recorded = json.loads(path.read_text(encoding="utf-8"))
    responses = recorded.get("responses") or {}

    def _post(url: str, body: dict[str, Any]) -> dict[str, Any]:
        hit = responses.get(url)
        if hit is not None:
            return json.loads(json.dumps(hit))
        return {"errorcode": 0, "msg": "recorded: no match", "data": {"oppHits": []}}

    return _post


def recorded_transport_metadata(name: str) -> dict[str, Any]:
    """Read a recording's ``_meta`` block without building a transport."""
    path = RECORDED_TRANSPORT_DIR / name
    if not path.is_file():
        raise RecordedTransportMissingError(f"recorded transport not found: {path}")
    return dict(json.loads(path.read_text(encoding="utf-8")).get("_meta") or {})


def hermetic_status() -> dict[str, Any]:
    """Report the current mode, so a run can say what it was allowed to do."""
    live = live_network_allowed()
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "live_network_allowed": live,
            "corpus_writeback_allowed": corpus_writeback_allowed(),
            "source_fixture_overwrite_allowed": source_fixture_overwrite_allowed(),
            "mode": "live" if live else "hermetic",
            "flags": {
                ENV_ALLOW_LIVE_NETWORK: live,
                ENV_ALLOW_CORPUS_WRITEBACK: corpus_writeback_allowed(),
                ENV_ALLOW_SOURCE_FIXTURE_OVERWRITE: _flag(
                    ENV_ALLOW_SOURCE_FIXTURE_OVERWRITE
                ),
            },
            "artifact_writeback_dir": str(ARTIFACT_WRITEBACK_DIR),
        }
    )


def hermetic_status_invariant_failures(status: dict[str, Any]) -> list[str]:
    fails: list[str] = []
    if status.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if status.get("mode") not in {"live", "hermetic"}:
        fails.append("mode_invalid")
    if status.get("live_network_allowed") and status.get("mode") != "live":
        fails.append("live_network_without_live_mode")
    # Source overwrite implies routine write-back; the reverse is not true.
    if status.get("source_fixture_overwrite_allowed") and not status.get(
        "corpus_writeback_allowed"
    ):
        fails.append("source_overwrite_without_writeback_flag")
    return fails
