"""Canonical artifact generation may not read developer-machine state (164E).

Gate 163 nearly committed a developer's Auth0 configuration as repository
evidence: regenerating five artifact sets on a machine with a populated `.env`
flipped `provider_env_present_actual` false -> true and deleted three real
blockers. The artifacts would have recorded that customer-auth provider
configuration was present - true of that laptop, false of the repository.

Gate 164 measured how wide that is. Varying ONE input at a time, with the
database pinned so "the database moved" is never the variable:

```text
baseline run twice            0 builders differ  -> they ARE deterministic
unrelated env vars present    0 builders differ
relative vs absolute root     0 builders differ
cwd / .env discovery         68 builders differ
provider credentials present 21 builders differ  <- the Gate 163 defect class
```

Twenty-one, not five. Forty files.

## The boundary, not a list of unset variables

The tempting fix is to unset `OIDC_*` before generating. That is not a
boundary: it is a ritual that works until someone forgets it, and it would
have to be repeated at every call site forever.

The boundary is that CANONICAL generation cannot read ambient secret-backed
state at all. `auth_environment_overlay` and `auth_environment_presence` are
the two functions that turn credential presence into a fact, and inside a
canonical build they raise instead.

Fail closed. A builder that tries to consume ambient secret state during
canonical generation gets an exception, not a quietly different artifact.

## Canonical is not the only kind of evidence

An artifact that reports whether THIS deployment has its provider configured
is doing something legitimate - it is just not canonical. Those are
environment-scoped, they describe a machine, and they are excluded from
canonical equivalence rather than forced to lie.

```text
canonical            derived from the repository and its recorded evidence.
                     Identical on every machine. Committed.
environment_scoped   describes a deployment. Differs by machine BY DESIGN,
                     and says so in its own output.
```

The separation is what makes both honest: canonical artifacts stop varying,
and environment-scoped ones stop pretending they do not.

## What it does not do

It does not read, log or serialize any secret VALUE. The refusal is about
presence-derived facts; no value crosses this module in either direction.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Iterator
from contextvars import ContextVar
from typing import Any

SCHEMA_VERSION = "nf_canonical_artifact_build_context_v1"

CANONICAL = "canonical"
ENVIRONMENT_SCOPED = "environment_scoped"

SCOPES: tuple[str, ...] = (CANONICAL, ENVIRONMENT_SCOPED)

#: A ContextVar, not `threading.local()`.
#:
#: The first draft used thread-local storage, which is correct only if work
#: never moves between threads and threads are never shared between tasks.
#: Neither holds here. Every FastAPI endpoint in this app is `def`, not
#: `async def` - 57 route modules, zero `async def` - so Starlette runs them
#: in anyio's worker THREADPOOL, and those worker threads are reused across
#: requests. Thread-local state that outlived a request would be inherited by
#: whatever ran next on that thread.
#:
#: A ContextVar is correct under both: each asyncio task and each threadpool
#: worker gets its own context, a `set` in one is invisible to another, and
#: the token-based reset restores exactly the previous value rather than
#: guessing at a default.
_CANONICAL: ContextVar[bool] = ContextVar("nf_canonical_artifact_build", default=False)


class AmbientStateRefused(RuntimeError):
    """Raised when canonical generation reaches for developer-machine state.

    Carries the reader that was refused, because "something ambient" is not a
    thing an operator can act on.
    """

    def __init__(self, reader: str, *, detail: str = "") -> None:
        super().__init__(
            f"canonical artifact generation may not read ambient state: {reader}"
            + (f" ({detail})" if detail else "")
        )
        self.reader = reader
        self.detail = detail


def in_canonical_build() -> bool:
    """Is a canonical artifact build active in THIS execution context?"""
    return bool(_CANONICAL.get())


def refuse_ambient(reader: str, *, detail: str = "") -> None:
    """Called BY the ambient readers. Raises during a canonical build.

    Placed at the reader rather than at the call site on purpose: a check the
    caller has to remember is a check that will eventually be forgotten, and
    the whole point is that forgetting is what happened in Gate 163.
    """
    if in_canonical_build():
        raise AmbientStateRefused(reader, detail=detail)


@contextlib.contextmanager
def canonical_build(*, reason: str = "") -> Iterator[dict[str, Any]]:
    """Generate canonical artifacts with ambient secret state refused.

    Re-entrant and exception-safe: the token restores the PREVIOUS value on
    the way out, so a raised `AmbientStateRefused` does not leave the flag set
    and turn every later build into a refusal, and a nested build restores to
    its enclosing state rather than to the default.
    """
    token = _CANONICAL.set(True)
    try:
        yield {
            "schema_version": SCHEMA_VERSION,
            "scope": CANONICAL,
            "reason": reason,
            "ambient_secret_state": "refused",
        }
    finally:
        _CANONICAL.reset(token)


@contextlib.contextmanager
def environment_scoped_build(*, reason: str = "") -> Iterator[dict[str, Any]]:
    """Generate artifacts that DESCRIBE a deployment, ambient reads permitted.

    The permission is the point: these artifacts are supposed to differ by
    machine. What they must not do is get committed as canonical evidence, and
    `describe_scope` below is what a verifier reads to tell them apart.

    Nested inside a canonical build, this genuinely relaxes the refusal for
    its own body and then restores it - which is what makes a canonical build
    able to delegate one environment-scoped section without abandoning the
    rule for everything after it.
    """
    token = _CANONICAL.set(False)
    try:
        yield {
            "schema_version": SCHEMA_VERSION,
            "scope": ENVIRONMENT_SCOPED,
            "reason": reason,
            "ambient_secret_state": "permitted, and this output describes one machine",
        }
    finally:
        _CANONICAL.reset(token)


def describe_scope(scope: str) -> dict[str, Any]:
    """What a scope means, carried in the artifact rather than in a docstring."""
    canonical = scope == CANONICAL
    return json.loads(
        json.dumps(
            {
                "schema_version": SCHEMA_VERSION,
                "scope": scope,
                "is_canonical": canonical,
                "identical_on_every_machine": canonical,
                "reads_ambient_secret_state": not canonical,
                "meaning": (
                    "derived from the repository and its recorded evidence; "
                    "byte-identical on every machine"
                    if canonical
                    else "describes one deployment; differs by machine by design "
                    "and must not be read as repository evidence"
                ),
                "not_implied": [
                    "a canonical artifact is not a statement about any deployment",
                    "an environment-scoped artifact is not repository evidence",
                    "no secret VALUE appears in either kind",
                ],
            },
            sort_keys=True,
        )
    )


def build_context_invariant_failures(context: dict[str, Any]) -> list[str]:
    """Refuse a build context that contradicts itself."""
    fails: list[str] = []

    if context.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")

    scope = str(context.get("scope") or "")
    if scope not in SCOPES:
        fails.append(f"scope_outside_vocabulary:{scope}")

    ambient = str(context.get("ambient_secret_state") or "")
    if scope == CANONICAL and ambient != "refused":
        fails.append("a_canonical_build_did_not_refuse_ambient_state")
    if scope == ENVIRONMENT_SCOPED and ambient == "refused":
        fails.append("an_environment_scoped_build_refused_what_it_exists_to_read")

    return sorted(set(fails))
