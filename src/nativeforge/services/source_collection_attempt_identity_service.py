"""Collection attempt identity (Gate 160B).

## An attempt is not a job, and its id must not be one

```text
a job      one slot of work for one source          Gate 158
an attempt one TRY at that work                     here
a cycle    one pass of the orchestration loop       Gate 159
```

A job that is retried three times is one job and three attempts. Reusing
`job_id` as `attempt_id` would make the second attempt overwrite the first one's
evidence, which is the opposite of what a raw payload spine is for: the whole
point is that the bytes from attempt 1 and attempt 2 are separately inspectable
when they differ.

So the digest includes `attempt_number`, and this module never imports Gate
99B's `build_job_id`. A test parses the AST to prove it.

## Derived from

```text
job_id             which slot of work
source_id          which source
attempt_number     which try
collector_version  which code produced the bytes
```

And explicitly NOT from:

```text
a random UUID alone    the same attempt described twice would differ, so a
                       duplicate write could never be recognised
a PID                  a retry after a restart would look like new work
a worker id alone      two workers on one attempt would be two attempts
the wall clock alone   every read of the clock would mint a new identity
```

`collector_version` is in the digest on purpose. When a collector changes, the
bytes it produces for the same slot may legitimately differ, and those are
different evidence rather than a contradiction. Without it, the store would have
to choose between refusing the new bytes and silently overwriting the old.

## Identity is not permission, and not a fetch

An attempt id can be computed for a source nobody approved, by a collector that
does not exist. Computing one asserts nothing about whether bytes were ever
retrieved.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_source_collection_attempt_identity_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: The attempt contract version. Part of the digest so that a deliberate change
#: to what an attempt MEANS produces new ids rather than silently reusing the
#: ids of attempts that meant something else.
ATTEMPT_VERSION = "gate160.v1"

#: Used when a caller has no collector yet, which is every caller in this gate:
#: no collector exists until Gate 161.
UNKNOWN_COLLECTOR_VERSION = "no_collector_registered"

#: The first attempt is 1, not 0. An attempt_number of 0 reads as "no attempt
#: has been made", and an identity for a thing that did not happen is a
#: contradiction the repository would then have to carry.
FIRST_ATTEMPT = 1

MAX_ATTEMPT_NUMBER = 1000


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _digest(*parts: Any) -> str:
    return hashlib.sha256(
        "|".join(str(part if part is not None else "") for part in parts).encode(
            "utf-8"
        )
    ).hexdigest()


def _as_attempt_number(value: Any) -> int | None:
    if value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    if number < FIRST_ATTEMPT or number > MAX_ATTEMPT_NUMBER:
        return None
    return number


def build_attempt_id(
    *,
    job_id: Any,
    source_id: Any,
    attempt_number: Any,
    collector_version: Any = UNKNOWN_COLLECTOR_VERSION,
    version: str | None = None,
) -> str:
    """Deterministic. The same logical attempt is always the same id."""
    return _digest(
        "nf_collection_attempt",
        version or ATTEMPT_VERSION,
        job_id,
        source_id,
        attempt_number,
        collector_version,
    )


def build_attempt_identity(
    *,
    job_id: Any,
    source_id: Any,
    attempt_number: Any = FIRST_ATTEMPT,
    collector_version: Any = UNKNOWN_COLLECTOR_VERSION,
    version: str | None = None,
) -> dict[str, Any]:
    """The identity of one try at one slot of work."""
    job = str(job_id or "").strip()
    source = str(source_id or "").strip()
    number = _as_attempt_number(attempt_number)
    collector = str(collector_version or "").strip() or UNKNOWN_COLLECTOR_VERSION

    blocked: list[str] = []
    if not job:
        blocked.append("no_job_id_supplied")
    if not source:
        blocked.append("no_source_id_supplied")
    if number is None:
        blocked.append(
            f"attempt_number_outside_1_to_{MAX_ATTEMPT_NUMBER}:{attempt_number}"
        )

    if blocked:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "scope": CONTROLLED_SCOPE,
                "usable": False,
                "blocked_reasons": sorted(blocked),
                "attempt_id": None,
                "job_id": job or None,
                "source_id": source or None,
                "attempt_number": number,
                "collector_version": collector,
                "source_monitoring_live": False,
            }
        )

    attempt_id = build_attempt_id(
        job_id=job,
        source_id=source,
        attempt_number=number,
        collector_version=collector,
        version=version,
    )
    # Recomputed, not asserted. A determinism claim that does not recompute has
    # the same shape as a count with no evidence behind it.
    recomputed = build_attempt_id(
        job_id=job,
        source_id=source,
        attempt_number=number,
        collector_version=collector,
        version=version,
    )
    # The NEXT attempt, computed here so a caller does not have to know the
    # rule - and so a test can show the two differ without reimplementing it.
    next_attempt = (
        build_attempt_id(
            job_id=job,
            source_id=source,
            attempt_number=number + 1,
            collector_version=collector,
            version=version,
        )
        if number < MAX_ATTEMPT_NUMBER
        else None
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "usable": True,
            "blocked_reasons": [],
            "attempt_version": version or ATTEMPT_VERSION,
            "attempt_id": attempt_id,
            "job_id": job,
            "source_id": source,
            "attempt_number": number,
            "is_first_attempt": number == FIRST_ATTEMPT,
            "collector_version": collector,
            "collector_is_registered": collector != UNKNOWN_COLLECTOR_VERSION,
            "next_attempt_id": next_attempt,
            "determinism_proof": {
                "recomputed_attempt_id": recomputed,
                "matches": recomputed == attempt_id,
                "differs_from_next_attempt": next_attempt != attempt_id,
            },
            "derived_from": [
                "attempt_version",
                "job_id",
                "source_id",
                "attempt_number",
                "collector_version",
            ],
            "not_derived_from": [
                "random_uuid",
                "pid",
                "worker_id",
                "wall_clock",
                "response_body",
            ],
            # Said explicitly. An attempt id that equalled a job id would make
            # "how many attempts were made" and "how many jobs exist" the same
            # question, and would let a retry overwrite the previous evidence.
            "is_a_collection_job_id": False,
            "implies_an_attempt_occurred": False,
            "implies_bytes_were_retrieved": False,
            "implies_source_approval": False,
            "source_monitoring_live": False,
        }
    )


def attempt_identity_invariant_failures(identity: dict[str, Any]) -> list[str]:
    """Refuse an identity that is not deterministic, or claims something."""
    fails: list[str] = []

    if not identity.get("usable"):
        if not identity.get("blocked_reasons"):
            fails.append("unusable_identity_named_no_reason")
        if identity.get("attempt_id"):
            fails.append("unusable_identity_still_produced_an_attempt_id")
        return sorted(set(fails))

    proof = identity.get("determinism_proof") or {}
    if not proof.get("matches"):
        fails.append("attempt_id_was_not_reproducible")
    if proof.get("recomputed_attempt_id") != identity.get("attempt_id"):
        fails.append("recomputed_attempt_id_differs_from_the_reported_one")
    # A retry MUST be a different attempt, or evidence would overwrite evidence.
    if identity.get("next_attempt_id") and not proof.get(
        "differs_from_next_attempt"
    ):
        fails.append("the_next_attempt_has_the_same_id_as_this_one")

    attempt_id = str(identity.get("attempt_id") or "")
    if len(attempt_id) != 64:
        fails.append("attempt_id_is_not_a_sha256_digest")

    if attempt_id and attempt_id == str(identity.get("job_id") or ""):
        fails.append("the_attempt_id_equals_the_job_id")

    number = identity.get("attempt_number")
    if not isinstance(number, int) or number < FIRST_ATTEMPT:
        fails.append(f"attempt_number_is_not_a_positive_integer:{number}")

    for claim in (
        "is_a_collection_job_id",
        "implies_an_attempt_occurred",
        "implies_bytes_were_retrieved",
        "implies_source_approval",
        "source_monitoring_live",
    ):
        if identity.get(claim):
            fails.append(f"identity_claimed:{claim}")

    return sorted(set(fails))
