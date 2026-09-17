"""What an execution proof requires (Gate 161H).

Gate 158 left `completed` unreachable and said why:

> `transition_job` has no `execution_proof_ref` parameter, no code in Gate 158
> sets it, and the gate that defines what an execution proof *is* has not been
> written.

This is that definition. It is deliberately narrow, and it is **scoped**.

## The seven requirements

```text
1  an execution attempt was persisted
2  the transport was invoked
3  a response was received
4  a raw payload was persisted
5  that payload's hash verified on readback
6  attempt -> job -> source all resolve
7  the policy permitted the transport kind that ran
```

Each is a fact somebody recorded, not a flag somebody set. `build_execution_proof`
reads the attempt row, the payload row and the policy verdict; it has no
parameter meaning "this succeeded".

## Hermetic proof is real, and it proves something small

A hermetic execution that satisfies all seven **does** produce
`execution_proof_available=true`. That is not a fiction: the bytes really were
transported, persisted and verified, and the path really did work end to end.

What it does not prove is that a source was contacted. So the proof carries its
scope in its own field names:

```text
proof_scope                 hermetic_execution
proves_the_envelope_works   true
proves_a_source_responded   FALSE
```

A caller that wants the second must read the second field. There is no single
boolean that means both, because a single boolean is exactly how "the pipeline
ran" becomes "the source answered".

## What this does NOT unlock

`completed` on a REAL-source job stays unreachable. Gate 158's repository still
has no execution-proof parameter, and this gate does not add one — the proof
this module issues is about an attempt, and Gate 162 decides whether any real
source may be attempted at all.

A hermetic job MAY complete, under `HERMETIC_COMPLETION_SCOPE`, because a
synthetic fixture job that transported, persisted and verified its bytes has
genuinely finished the only work it ever had - but only if the response was
USABLE. A 404 satisfies all seven requirements and completes nothing: it is
evidence that the envelope worked and that there was nothing there, which are
two facts rather than one. Doc 840 states that boundary in full.

## Why define it here rather than wait

Gate 158 deferred it because a payload spine did not exist. Gate 160 built one.
Defining the requirements now, while nothing can go live, means Gate 162 decides
*which sources may be attempted* against a proof standard that already exists —
rather than inventing one under the pressure of a first live source.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_source_collection_execution_proof_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

#: The scope a hermetic proof belongs to. A job may complete under this scope
#: and only this one.
HERMETIC_COMPLETION_SCOPE = "hermetic_execution"

#: The scope a live proof would belong to. Named so refusing it is expressible,
#: and unreachable: nothing in this gate can produce one.
LIVE_COMPLETION_SCOPE = "live_source_execution"

PROOF_SCOPES: tuple[str, ...] = (HERMETIC_COMPLETION_SCOPE, LIVE_COMPLETION_SCOPE)

#: The seven. Each is read from a record, never passed in as a verdict.
PROOF_REQUIREMENTS: tuple[str, ...] = (
    "attempt_persisted",
    "transport_invoked",
    "response_received",
    "raw_payload_persisted",
    "payload_hash_verified",
    "provenance_resolves",
    "policy_permitted_the_transport",
)

REQUIREMENT_EVIDENCE: dict[str, str] = {
    "attempt_persisted": (
        "a row in nf_source_collection_execution_attempts, written for every "
        "outcome including refusals"
    ),
    "transport_invoked": (
        "the transport boundary reported dispatched=true. A refusal before "
        "dispatch is not an execution."
    ),
    "response_received": (
        "the transport outcome was a response, not a timeout or a connection "
        "failure. Bytes may still be malformed - that is a parse problem, not "
        "an execution failure."
    ),
    "raw_payload_persisted": (
        "Gate 160 stored the exact bytes and returned a hash"
    ),
    "payload_hash_verified": (
        "Gate 160 re-hashed the bytes it read back and they matched. A store "
        "that records a hash and never checks it again has recorded an "
        "intention."
    ),
    "provenance_resolves": (
        "attempt -> job -> source, each resolved by LOOKING rather than by "
        "reading a column back to itself"
    ),
    "policy_permitted_the_transport": (
        "the execution policy allowed the transport kind that actually ran. A "
        "proof for a transport nobody permitted would be evidence of a bypass."
    ),
}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def build_execution_proof(
    *,
    attempt: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    replay: dict[str, Any] | None = None,
    policy: dict[str, Any] | None = None,
    transport_result: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Does this attempt satisfy the seven requirements, and in which scope?

    Every input is a record somebody else produced. There is no parameter
    meaning "this succeeded".
    """
    record = attempt or {}
    stored = payload or {}
    played = replay or {}
    verdict = policy or {}
    dispatch = transport_result or {}

    transport_kind = record.get("transport_kind") or dispatch.get("transport_kind")

    measured = {
        "attempt_persisted": bool(record.get("attempt_id")),
        "transport_invoked": bool(dispatch.get("dispatched")),
        # A malformed body is still a response. Parsing is a later concern and
        # must not retroactively make an execution a failure.
        "response_received": str(dispatch.get("outcome") or "").startswith(
            "response_received"
        ),
        "raw_payload_persisted": bool(
            record.get("raw_payload_persisted") or stored.get("persisted")
        ),
        "payload_hash_verified": bool(
            played.get("hash_verified") or stored.get("readback_hash_verified")
        ),
        "provenance_resolves": bool(
            played.get("linked_job_found") and played.get("provenance")
        ),
        "policy_permitted_the_transport": bool(
            (transport_kind == "hermetic" and verdict.get("hermetic_transport_allowed"))
            or (transport_kind == "live" and verdict.get("live_transport_allowed"))
        ),
    }

    missing = sorted(name for name, ok in measured.items() if not ok)
    available = all(measured.values())

    # A separate question, deliberately outside the seven.
    #
    # A 404 satisfies every requirement above - it WAS evidenced, and the
    # record of "the source said there is nothing there" is worth keeping. What
    # it must not do is let a job be called finished, so completion asks one
    # further thing that evidence does not: was the response usable?
    #
    # Folding this into the seven would make a 404 look unevidenced and lose
    # the record. Leaving it out entirely made "the fixture answered" and "the
    # work is done" the same fact.
    status = dispatch.get("status_code")
    try:
        code = int(status) if status is not None else None
    except (TypeError, ValueError):
        code = None
    usable = bool(code is not None and 200 <= code < 300)

    scope = (
        HERMETIC_COMPLETION_SCOPE
        if transport_kind == "hermetic"
        else LIVE_COMPLETION_SCOPE
        if transport_kind == "live"
        else None
    )

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "execution_proof_available": available,
            "proof_scope": scope,
            "requirements": measured,
            "requirements_expected": list(PROOF_REQUIREMENTS),
            "requirement_evidence": REQUIREMENT_EVIDENCE,
            "requirements_not_met": missing,
            "response_was_usable": usable,
            "http_status": code,
            "why_usability_is_not_a_requirement": (
                "a 404 is fully evidenced and the record of it is worth "
                "keeping. Usability asks a different question - whether the "
                "evidenced response is worth acting on - and only completion "
                "needs the answer."
            ),
            "transport_kind": transport_kind,
            "attempt_id": record.get("attempt_id"),
            "job_id": record.get("job_id"),
            "source_id": record.get("source_id"),
            "payload_sha256": record.get("raw_payload_sha256")
            or stored.get("payload_sha256"),
            "bytes_received": int(record.get("bytes_received") or 0),
            # ---- what this proves, and what it does not ------------------
            #
            # Two fields, deliberately. A single boolean meaning both is how
            # "the pipeline ran" becomes "the source answered".
            "proves_the_envelope_works": available,
            "proves_a_source_responded": False,
            "why_not": (
                "the bytes came from a registered fixture. The transport "
                "contacted nothing, and a hermetic proof says the path works "
                "rather than that anything answered."
            ),
            # ---- what it unlocks ----------------------------------------
            "permits_hermetic_job_completion": bool(
                available and usable and scope == HERMETIC_COMPLETION_SCOPE
            ),
            "permits_real_source_job_completion": False,
            "why_real_source_completion_stays_closed": (
                "Gate 158's transition_job still has no execution proof "
                "parameter, this gate does not add one, and Gate 162 decides "
                "whether any real source may be attempted at all."
            ),
            "live_source_call": False,
            "source_monitoring_live": False,
        }
    )


def execution_proof_invariant_failures(proof: dict[str, Any]) -> list[str]:
    """Refuse a proof that claims more than it measured."""
    fails: list[str] = []

    # THE invariants of this module.
    if proof.get("proves_a_source_responded"):
        fails.append("the_proof_claimed_a_source_responded")
    if proof.get("permits_real_source_job_completion"):
        fails.append("the_proof_permitted_a_real_source_job_to_complete")
    if proof.get("live_source_call"):
        fails.append("the_proof_claimed:live_source_call")
    if proof.get("source_monitoring_live"):
        fails.append("the_proof_claimed:source_monitoring_live")

    scope = proof.get("proof_scope")
    if scope is not None and scope not in PROOF_SCOPES:
        fails.append(f"proof_scope_outside_vocabulary:{scope}")
    if scope == LIVE_COMPLETION_SCOPE:
        fails.append("a_live_scoped_proof_was_produced")

    # available and not-met must agree, both directions.
    if proof.get("execution_proof_available") and proof.get("requirements_not_met"):
        fails.append("proof_available_alongside_unmet_requirements")
    if not proof.get("execution_proof_available") and not proof.get(
        "requirements_not_met"
    ):
        fails.append("proof_unavailable_without_naming_an_unmet_requirement")

    requirements = proof.get("requirements") or {}
    expected = set(proof.get("requirements_expected") or ())
    if expected and set(requirements) != expected:
        fails.append("requirements_do_not_match_the_declared_set")

    evidence = proof.get("requirement_evidence") or {}
    for name in requirements:
        if not str(evidence.get(name) or "").strip():
            fails.append(f"requirement_without_evidence:{name}")

    # A proof without a verified hash is not a proof. Named separately from the
    # generic unmet-requirement check because it is the one that would let
    # unverified bytes count as evidence.
    if proof.get("execution_proof_available") and not requirements.get(
        "payload_hash_verified"
    ):
        fails.append("a_proof_was_issued_without_a_verified_payload_hash")
    if proof.get("execution_proof_available") and not requirements.get(
        "policy_permitted_the_transport"
    ):
        fails.append("a_proof_was_issued_for_a_transport_nobody_permitted")

    # Hermetic completion is permitted only in the hermetic scope.
    if proof.get("permits_hermetic_job_completion") and scope != (
        HERMETIC_COMPLETION_SCOPE
    ):
        fails.append("hermetic_completion_permitted_outside_the_hermetic_scope")

    # And only for a response worth acting on. A 404 is evidence; it is not a
    # finished job, and a proof saying otherwise would make "the fixture
    # answered" and "the work is done" the same fact.
    if proof.get("permits_hermetic_job_completion") and not proof.get(
        "response_was_usable"
    ):
        fails.append("completion_permitted_for_an_unusable_response")

    return sorted(set(fails))
