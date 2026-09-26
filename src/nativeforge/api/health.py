"""Health check (no database required).

The response carries the deployment identity, because a health endpoint that
only says `ok` cannot be used to verify a deployment - it proves that
*something* is answering, not that the thing answering is the thing you
shipped. `git_sha` is what makes "is the new version live?" a question with an
answer.

Both facts are stamped into the environment at build time rather than derived
at runtime. The workstation services read them with `git rev-parse HEAD` and
`git status --porcelain`; a container has neither a `.git` directory nor a git
binary, so the same approach would report `unknown` in exactly the environment
where the answer matters most.

`source_dirty` is `true`, `false`, or `null`. Null is not a synonym for
clean - it means nothing told us, which is a different claim from "the tree
was clean", and conflating them would let an unstamped image assert something
it has no evidence for.
"""

from typing import Any

from fastapi import APIRouter

from nativeforge.lib.settings import get_settings

router = APIRouter(tags=["health"])

#: Values accepted as booleans in `NF_SOURCE_DIRTY`. Anything else, including
#: the `unknown` default, reads as "not stated".
_TRUE = frozenset({"true", "1", "yes", "y", "on"})
_FALSE = frozenset({"false", "0", "no", "n", "off"})


def _source_dirty(raw: str) -> bool | None:
    value = (raw or "").strip().lower()
    if value in _TRUE:
        return True
    if value in _FALSE:
        return False
    return None


@router.get("/health")
def health() -> dict[str, Any]:
    settings = get_settings()
    return {
        "status": "ok",
        "service": "nativeforge",
        "git_sha": settings.nf_git_sha,
        "source_dirty": _source_dirty(settings.nf_source_dirty),
    }
