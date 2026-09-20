"""The Gate 166 canonical evidence (166K).

Written inside `canonical_build()`, so a developer `.env` cannot change a byte
of it - the boundary Gate 164 established and proved. The database is an
EXPLICIT input for the same reason: ambient state that decides evidence is
evidence nobody can reproduce.

No generation timestamp. A file that changes every time it is written cannot be
compared against the committed copy, and a diff nobody can read is a diff
nobody checks.

Counts, booleans and identifiers only. No secrets, no request URLs, no
customer data.
"""

from __future__ import annotations

import json
import pathlib
from typing import Any

SCHEMA_VERSION = "nf_source_authority_gate166_v1"

ARTIFACT_DIR = "artifacts/source_authority_gate166"


def _dump(value: Any) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str) + "\n"


def build_authority_evidence(
    *, connection: Any = None, organization_id: Any = None
) -> dict[str, Any]:
    """Compose the gate's evidence from services that already measured it."""
    from nativeforge.services.source_attribution_contract_service import (
        describe_contracts,
    )
    from nativeforge.services.source_authority_service import (
        REQUIRED_DECISION_KINDS,
        SOURCE_AUTHORITY_STATES,
        derive_authorized_source_ids,
    )
    from nativeforge.services.source_authority_sweep_service import (
        sweep_invariant_failures,
        sweep_source_authority,
    )
    from nativeforge.services.source_definition_service import (
        describe_field_classification,
    )
    from nativeforge.services.source_fleet_fact_scope_service import (
        COVERED_TRANSITIVELY,
        FLEET_FACTS,
    )

    sweep = sweep_source_authority(
        connection=connection, organization_id=organization_id
    )
    authorized = derive_authorized_source_ids(
        connection=connection, organization_id=organization_id
    )

    return {
        "authority_model.json": {
            "schema_version": SCHEMA_VERSION,
            "fact": "what sources exist, and which of them may execute",
            "states": list(SOURCE_AUTHORITY_STATES),
            "required_decision_kinds": list(REQUIRED_DECISION_KINDS),
            "derived_from": [
                "nf_source_authorization_decisions",
                "nf_active_opportunity_sources",
                "the seed catalog",
            ],
            "derived_from_source_code_constant": False,
            "removed_in_this_gate": "source_live_warrant_service.AUTHORIZED_SOURCE_IDS",
            "why_removed": (
                "it restated a guarantee the database already enforces - "
                "migration 0048 makes an unsigned approved decision "
                "unwritable - in a place nobody could audit, and at 1,000 "
                "sources it would have made every activation a deploy"
            ),
            "not_implied": [
                "a catalog row is not an authorization",
                "an adapter existing is not an authorization",
                "governance complete is not a permitted request: robots, "
                "attribution, collector capability and runtime readiness are "
                "conditions of the moment and are checked per request",
                "retired wins outright; it is evaluated before the ladder",
            ],
        },
        "authority_sweep.json": {
            "schema_version": SCHEMA_VERSION,
            "fact": "every registered source, evaluated in one fleet-fact scope",
            "registered_sources": sweep["registered_sources"],
            "evaluated_sources": sweep["evaluated_sources"],
            "counts_by_state": sweep["counts_by_state"],
            "authorized_source_ids": sorted(authorized),
            "authorized_count_is_reported_not_asserted": (
                "Gate 163's world had one authorized source. Gate 166 exists "
                "so the next one is a data change, and a verifier asserting 1 "
                "would have to be edited to permit what this gate enables."
            ),
            "invariant_failures": sweep_invariant_failures(sweep),
        },
        "fleet_fact_scope.json": {
            "schema_version": SCHEMA_VERSION,
            "fact": "fleet-wide facts are computed once per sweep",
            "fleet_facts": list(FLEET_FACTS),
            "covered_transitively": dict(COVERED_TRANSITIVELY),
            "computations_during_this_sweep": sweep["fleet_facts"]["computations"],
            "primitive": "contextvars.ContextVar",
            "why_not_thread_local": (
                "all 57 API route modules are sync, so Starlette runs them in "
                "anyio's worker threadpool with REUSED workers; thread-local "
                "state would leak one request's scope into the next request "
                "that landed on the same worker"
            ),
            "why_not_a_cache": (
                "explicit lifetime, immutable for one sweep, discarded on "
                "exit. With no scope open every call computes, which is "
                "byte-for-byte the pre-Gate-166 behaviour. A scope opened for "
                "another organization is BYPASSED rather than answered from - "
                "a mismatch costs time, never correctness."
            ),
        },
        "source_definition_contract.json": describe_field_classification(),
        "attribution_contracts.json": describe_contracts(),
    }


def write_authority_artifacts(
    *,
    repo_root: str | pathlib.Path,
    connection: Any = None,
    organization_id: Any = None,
) -> dict[str, Any]:
    """Write the canonical set. Refuses to run outside a canonical build."""
    from nativeforge.services.canonical_artifact_build_context_service import (
        canonical_build,
        in_canonical_build,
    )

    root = pathlib.Path(repo_root)
    target = root / ARTIFACT_DIR
    target.mkdir(parents=True, exist_ok=True)

    def _write() -> list[str]:
        evidence = build_authority_evidence(
            connection=connection, organization_id=organization_id
        )
        written: list[str] = []
        for name, payload in sorted(evidence.items()):
            (target / name).write_text(_dump(payload), encoding="utf-8")
            written.append(name)
        return written

    if in_canonical_build():
        names = _write()
    else:
        with canonical_build(reason="gate166_source_authority_evidence"):
            names = _write()

    return {
        "schema_version": SCHEMA_VERSION,
        "scope": "canonical",
        "directory": ARTIFACT_DIR,
        "files": names,
        "file_count": len(names),
        "carries_a_generation_timestamp": False,
    }
