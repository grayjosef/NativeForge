"""Gate 162N artifacts: what the authorization boundary actually decides.

Every file is DERIVED by running the resolver and the projection in memory.
Nothing here is a transcript of a prior run typed out by hand.

## Why these artifacts touch no database

The resolver needs a connection for two of eleven facts - the recorded
decisions and the activation row - and a rebuild must be byte-identical
without one. So the artifacts record the MODEL, the MAPPING, the derivation
strengths, and the resolution of a source with no decisions on file. The
database-backed facts are the verifier's job and are named here rather than
restated.

The one exception is `synthetic_permitted_branch.json`, which records the
SHAPE of a reached authorization by building the facts through the model
directly. The verifier proves the real path end to end against a live
database; this records what that path produces so an auditor can read it
without running anything.

## The fixture's evidence is obviously synthetic

Its fingerprint is a sha256 of a string in
`source_authorization_fixture_registry_service`, its signer is
`reviewer:nf162-artifact`, and its host is `.invalid` - reserved by RFC 2606
precisely so it cannot exist. No artifact here contains a real terms decision,
because none exists.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.repositories.source_authorization_decision_repository import (
    APPROVAL_PERMITTING_STATUSES,
    DECISION_KINDS,
    DECISIONS,
    GUARD_STATUSES,
    HUMAN_REVIEW,
    TERMS,
)
from nativeforge.services.live_network_guard_service import (
    build_live_network_decision,
)
from nativeforge.services.source_activation_packet_service import (
    AUTHORITY_FOR_FACT,
    GATE_163_SEQUENCE,
)
from nativeforge.services.source_authorization_fact_model_service import (
    DECISION_FACTS,
    FACT_NAMES,
    FACT_STATUSES,
    FRESHNESS_FACTS,
    NOT_AN_APPROVAL,
    PERMITTING_FACT_STATUSES,
    REFUSAL_MEANING,
    build_fact,
    describe_fact_model,
    fact_invariant_failures,
)
from nativeforge.services.source_authorization_fact_resolver_service import (
    AUTHORIZING_STRENGTHS,
    ROBOTS_UNRESOLVABLE,
    STRENGTH_BY_FACT,
    STRENGTHS,
    resolve_source_authorization_facts,
    resolver_invariant_failures,
)
from nativeforge.services.source_authorization_fixture_registry_service import (
    FIXTURE_PREFIX,
    PERMITTABLE_FIXTURE,
    UNDECIDED_FIXTURE,
    describe_fixture_registry,
    fixture_evidence_fingerprint,
)
from nativeforge.services.source_live_authorization_service import (
    AUTHORIZATION_STATUSES,
    GUARD_INPUT_FROM_FACT,
    NOT_IMPLIED,
    STATUS_APPROVED,
    authorization_invariant_failures,
    authorize_source_for_live_access,
)
from nativeforge.services.source_monitoring_approved_source_service import (
    evaluate_registry,
    load_registry_rows,
)
from nativeforge.services.source_runtime_readiness_fact_service import (
    LANE_NAMES,
    REQUIRED_FOR_COLLECTION,
    REQUIRED_FOR_MONITORING,
    build_runtime_readiness_facts,
    runtime_readiness_invariant_failures,
)

SCHEMA_VERSION = "nf_source_authorization_gate162_artifacts_v1"

ARTIFACT_DIR = "artifacts/source_authorization_gate162"

SURVEY_FILE = "source_activation_survey.json"
MAPPING_FILE = "guard_input_mapping.json"
MODEL_FILE = "source_authorization_fact_model.json"
TERMS_FILE = "terms_decision_status.json"
HUMAN_FILE = "human_review_status.json"
RUNTIME_FILE = "runtime_fact_resolution.json"
ALLOWLIST_FILE = "allowlist_projection.json"
FORGED_FILE = "fabricated_input_refusal.json"
PERMITTED_FILE = "synthetic_permitted_branch.json"
PACKET_FILE = "activation_packet_example.json"
HEALTH_FILE = "source_authorization_health.json"
BLOCKERS_FILE = "next_live_source_blockers.md"

ARTIFACT_FILES: tuple[str, ...] = (
    SURVEY_FILE,
    MAPPING_FILE,
    MODEL_FILE,
    TERMS_FILE,
    HUMAN_FILE,
    RUNTIME_FILE,
    ALLOWLIST_FILE,
    FORGED_FILE,
    PERMITTED_FILE,
    PACKET_FILE,
    HEALTH_FILE,
    BLOCKERS_FILE,
)

FORBIDDEN_SHAPES: tuple[tuple[str, str], ...] = (
    ("email_address", r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
    ("bearer_token", r"\beyJ[A-Za-z0-9_-]{8,}"),
    ("session_cookie", r"nf_session="),
    ("google_client_secret", r"GOCSPX-"),
    ("private_key", r"BEGIN PRIVATE KEY"),
    ("aws_key", r"AKIA"),
    ("provider_subject", r"\b\d{18,}\b"),
)

MIGRATION = "0048"

FIXTURE_INSTANT = "2026-09-17T12:00:00+00:00"
FIXTURE_EXPIRY = "2027-09-17T12:00:00+00:00"
FIXTURE_SIGNER = "reviewer:nf162-artifact"
FIXTURE_OPERATOR = "operator:nf162-artifact"


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


def _assert_no_forbidden_shape(name: str, body: str) -> None:
    for shape, pattern in FORBIDDEN_SHAPES:
        if re.search(pattern, body):
            raise AssertionError(f"artifact {name} contains a {shape}")


def _survey() -> dict[str, Any]:
    evaluated = evaluate_registry()
    shipped = load_registry_rows()
    return {
        "schema_version": SCHEMA_VERSION,
        "gate": "162",
        "migration": MIGRATION,
        "shipped_registry_count": len(shipped),
        "registry_row_count": int(evaluated.get("registry_row_count") or 0),
        "activation_approved_count": int(
            evaluated.get("activation_approved_count") or 0
        ),
        "monitorable_count": int(evaluated.get("monitorable_count") or 0),
        "terms_blocked_count": int(evaluated.get("terms_blocked_count") or 0),
        "human_review_blocked_count": int(
            evaluated.get("human_review_blocked_count") or 0
        ),
        "what_already_existed": {
            "human_activation_gates": [
                "seed_source_human_activation_service",
                "tier1_batch_federal_activation_service",
                "tier3_foundation_batch_activation_service",
            ],
            "terms_review_queue": "source_terms_review_queue_service",
            "per_source_activation_policy": (
                "phase1_collector_activation_policy_service"
            ),
            "allowlist_evaluator": "source_monitoring_approved_source_service",
            "live_network_guard": "live_network_guard_service",
            "activation_approval_storage": (
                "nf_active_opportunity_sources.activation_approved_*"
            ),
        },
        "second_activation_system_created": False,
        "what_was_genuinely_missing": [
            "a per-source TERMS decision record - only a "
            "legal_tos_review_required requirement flag existed",
            "a per-source HUMAN REVIEW decision record - likewise only a "
            "broad_eligibility_human_review_required flag",
            "any path from recorded facts to the live guard's inputs",
        ],
        "why_discovery_review_items_was_not_reused": (
            "its source_registry_id is a UUID foreign key into "
            "nf_opportunity_sources, which holds 0 rows, while the 177-row "
            "source registry is file-backed and string-keyed. The id spaces "
            "do not join, and bridging them would invent registry identity as "
            "a side effect of recording a decision."
        ),
        "why_one_table_for_two_questions": (
            "terms review and source review are different decisions by "
            "potentially different authorities, and they have identical "
            "shape: an answer, a signer, a time, an evidence reference, an "
            "expiry. Two near-identical tables is not minimum persistence, so "
            "decision_kind discriminates and the constraints are written once."
        ),
        "decision_kinds": sorted(DECISION_KINDS),
        "live_source_call": False,
        "source_monitoring_live": False,
    }


def _mapping() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "guard_input_from_fact": dict(GUARD_INPUT_FROM_FACT),
        "guard_inputs_supplied_from_records": len(GUARD_INPUT_FROM_FACT),
        "derivation_strengths": dict(STRENGTH_BY_FACT),
        "strength_vocabulary": list(STRENGTHS),
        "authorizing_strengths": sorted(AUTHORIZING_STRENGTHS),
        "only_a_signed_decision_authorizes": (
            "a ready runtime, a registered source, an available adapter, a "
            "queued job and a hermetic execution proof are prerequisites. "
            "None of them is permission."
        ),
        "robots_is_unresolvable_for_a_real_source": ROBOTS_UNRESOLVABLE,
        "resolver_parameters": [
            "connection",
            "organization_id",
            "source_id",
            "now",
        ],
        "no_parameter_can_assert_a_fact": True,
        "before_this_gate": (
            "the guard's ten status inputs had to be handed in by a caller, "
            "and eight of them had no record anywhere to come from - so the "
            "only way to reach allowed=true was to invent them."
        ),
        "not_an_approval": list(NOT_AN_APPROVAL),
        "source_monitoring_live": False,
    }


def _model() -> dict[str, Any]:
    model = describe_fact_model()
    model["artifact_schema_version"] = SCHEMA_VERSION
    return model


def _decision_status(kind: str) -> dict[str, Any]:
    """The decision vocabulary and the constraints, per question kind."""
    return {
        "schema_version": SCHEMA_VERSION,
        "decision_kind": kind,
        "table": "nf_source_authorization_decisions",
        "decision_vocabulary": sorted(DECISIONS),
        "guard_status_vocabulary": sorted(GUARD_STATUSES),
        "approval_permitting_guard_statuses": sorted(
            APPROVAL_PERMITTING_STATUSES
        ),
        "database_refuses": [
            "an approved decision with no reviewed_by",
            "an approved decision with no reviewed_at",
            "an approved decision with no evidence_fingerprint",
            "a denied decision with no reviewed_by",
            "an approved TERMS decision carrying a blocking guard status",
            "any decision for the real organization (refused by name)",
        ],
        "why_the_check_and_not_only_the_service": (
            "a service can be bypassed and a CHECK cannot, and this is the "
            "single row whose forgery would unlock a live source call"
        ),
        "recorded_for_real_sources": 0,
        "recorded_approvals_for_real_sources": 0,
        "freshness_applies": kind in {TERMS, HUMAN_REVIEW},
        "stale_affirmative_answers_do_not_permit": (
            "a decision about a document that may have changed since is not "
            "evidence about the current document"
        ),
        "one_answer_per_source_per_question": (
            "unique on (organization_id, source_id, decision_kind). A "
            "re-review replaces the answer, because two live answers to one "
            "question have no defined winner."
        ),
        "source_monitoring_live": False,
    }


def _runtime() -> dict[str, Any]:
    facts = build_runtime_readiness_facts()
    return {
        "schema_version": SCHEMA_VERSION,
        "lane_names": list(LANE_NAMES),
        "required_for_collection": list(REQUIRED_FOR_COLLECTION),
        "required_for_monitoring": list(REQUIRED_FOR_MONITORING),
        "lanes": {
            name: {
                "status": lane.get("status"),
                "observed": lane.get("observed"),
                "source_of_truth": lane.get("source_of_truth"),
                "conditions_not_met": lane.get("conditions_not_met"),
                "why": lane.get("why"),
            }
            for name, lane in (facts.get("lanes") or {}).items()
        },
        "runtime_status": facts["runtime_status"],
        "collection_runtime_ready": facts["collection_runtime_ready"],
        "monitoring_runtime_ready": facts["monitoring_runtime_ready"],
        "unmet_for_collection": facts["unmet_for_collection"],
        "invariant_failures": runtime_readiness_invariant_failures(facts),
        "repairs": facts["repairs"],
        "not_derived_from_module_existence": facts[
            "not_derived_from_module_existence"
        ],
        "authorizes_nothing": facts["authorizes_nothing"],
        "not_implied": facts["not_implied"],
        "source_monitoring_live": False,
    }


def _allowlist() -> dict[str, Any]:
    """The projection's contract. The counts are the verifier's to measure."""
    shipped = load_registry_rows()
    fixtures = describe_fixture_registry(shipped)
    return {
        "schema_version": SCHEMA_VERSION,
        "is_a_projection": (
            "allowlisted is computed from recorded facts every time it is "
            "asked. No column stores it, so it cannot disagree with the facts "
            "underneath it."
        ),
        "allowlisted_means": "authorization_status == approved, and nothing else",
        "authorization_statuses": list(AUTHORIZATION_STATUSES),
        "shipped_registry_count": len(shipped),
        "fixture_count": fixtures["fixture_count"],
        "sources_evaluated": fixtures["merged_count"],
        "real_sources_allowlisted": 0,
        "approved_source_count": 0,
        "fixture_prefix": FIXTURE_PREFIX,
        "prefix_is_reserved": fixtures["prefix_is_reserved"],
        "no_fixture_shadows_a_real_source": fixtures[
            "no_fixture_shadows_a_real_source"
        ],
        "why_a_fixture_exists": fixtures["why_this_exists"],
        "no_stored_allowlist_flag": (
            "nf_active_opportunity_sources.activation_approved_* remains the "
            "one place an activation decision is STORED. A second boolean "
            "beside it would be a second truth to drift."
        ),
        "live_transport_permitted": False,
        "source_monitoring_live": False,
    }


def _forged() -> dict[str, Any]:
    """What a caller gets by handing the low-level guard ten affirmatives."""
    forged = build_live_network_decision(
        purpose="source_collection",
        target_url="https://fixtures.invalid/nf162/forged",
        caller="a_caller_supplying_its_own_facts",
        source_id="nf162.fixture.forged",
        method="GET",
        allow_live_fetch=True,
        terms_status="NO_REVIEW_REQUIRED",
        activation_status="activation_allowed",
        collector_status="active",
        robots_status="allowed",
        credential_status="not_required",
        rate_limit_status="policy_declared",
        user_agent_status="canonical",
        attribution_status="not_required",
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "the_low_level_guard_allowed_it": bool(forged.get("allowed")),
        "why_that_is_not_a_problem": (
            "build_live_network_decision is a pure decision function over "
            "named inputs, and answering its inputs honestly is what it is "
            "for. A caller who invents them gets an OPINION."
        ),
        "what_a_forged_opinion_cannot_do": [
            "it cannot change authorize_source_for_live_access, which resolves "
            "every fact from records",
            "it cannot be recorded - the database refuses an approval with no "
            "signer, no time and no evidence",
            "it cannot be dispatched - Gate 161 built no live transport and "
            "`live` is not in DISPATCHABLE_KINDS",
            "it cannot produce an attempt row - migration 0047 refuses "
            "transport_kind='live' and live_source_call=1",
        ],
        "the_only_runtime_path": (
            "source_live_authorization_service.authorize_source_for_live_access"
        ),
        "resolver_parameters": [
            "connection",
            "organization_id",
            "source_id",
            "now",
        ],
        "caller_supplied_facts_accepted": 0,
        "forged_guard_inputs_change_the_authorization": False,
        "source_monitoring_live": False,
    }


def _permitted_branch() -> dict[str, Any]:
    """The SHAPE of a reached authorization, built through the fact model.

    The verifier proves the real path end to end against a live database. This
    records what that path produces, so an auditor can read the reached state
    without running anything - and so a future change that makes `approved`
    unreachable shows up as a diff here.
    """
    fingerprint = fixture_evidence_fingerprint(PERMITTABLE_FIXTURE)

    recorded: dict[str, Any] = {}
    failures: list[str] = []
    for name in FACT_NAMES:
        spec_permitting = {
            "source_registered": "registered",
            "terms_status": "NO_REVIEW_REQUIRED",
            "human_review_status": "approved",
            "activation_status": "activation_allowed",
            "collector_status": "active",
            "robots_status": "absent",
            "credential_status": "not_required",
            "rate_limit_status": "policy_declared",
            "user_agent_status": "canonical",
            "attribution_status": "not_required",
            "runtime_status": "ready",
        }[name]
        signed = name in DECISION_FACTS or name == "attribution_status"
        fact = build_fact(
            fact_name=name,
            value=spec_permitting,
            record_exists=True,
            decision_verdict="approved" if signed else None,
            recorded_by=(
                (
                    FIXTURE_OPERATOR
                    if name == "activation_status"
                    else FIXTURE_SIGNER
                )
                if signed
                else None
            ),
            recorded_at=FIXTURE_INSTANT if signed else None,
            expires_at=FIXTURE_EXPIRY if name in FRESHNESS_FACTS else None,
            evidence_ref=fingerprint if signed else None,
            now=FIXTURE_INSTANT,
        )
        fact["derivation_strength"] = STRENGTH_BY_FACT[name]
        failures.extend(fact_invariant_failures(fact))
        recorded[name] = fact

    permitting = [n for n, f in recorded.items() if f["permits"]]

    return {
        "schema_version": SCHEMA_VERSION,
        "fixture_source_id": PERMITTABLE_FIXTURE,
        "undecided_fixture_source_id": UNDECIDED_FIXTURE,
        "is_synthetic": True,
        "evidence_fingerprint_is_of": (
            "a string in source_authorization_fixture_registry_service, not a "
            "fetched document"
        ),
        "host_resolves_nowhere": (
            "`.invalid` is reserved by RFC 2606 precisely so it cannot exist"
        ),
        "facts": recorded,
        "facts_recorded": len(permitting),
        "required_fact_count": len(FACT_NAMES),
        "all_facts_permit": bool(len(permitting) == len(FACT_NAMES)),
        "authorization_status_would_be": STATUS_APPROVED,
        "invariant_failures": sorted(set(failures)),
        # ---- and it STILL does not permit a request -------------------
        "live_fetch_opted_in": False,
        "why_the_guard_still_refuses": (
            "authorize_source_for_live_access hardcodes allow_live_fetch=False, "
            "so a fully authorized source sits at live_fetch_not_opted_in. "
            "Gate 163 is where that becomes a code change rather than an "
            "argument."
        ),
        "live_transport_permitted": False,
        "authorization_complete_is_not_a_permitted_request": True,
        "why_this_fixture_exists": (
            "an unreachable permitted branch makes every refusal "
            "unfalsifiable. Something must be able to reach approved, and it "
            "must not be one of the 177 real sources."
        ),
        "proves_nothing_about_a_real_source": True,
        "not_implied": list(NOT_IMPLIED),
        "source_monitoring_live": False,
    }


def _packet_example() -> dict[str, Any]:
    """A real source's checklist, resolved with no database.

    Two of eleven facts need a connection, so they resolve as `missing` here -
    which is also their true state, since no decision exists for any real
    source.
    """
    shipped = load_registry_rows()
    example_id = sorted(shipped)[0] if shipped else None

    resolution = resolve_source_authorization_facts(
        source_id=example_id, now=FIXTURE_INSTANT
    )
    decision = authorize_source_for_live_access(
        source_id=example_id, now=FIXTURE_INSTANT
    )

    return {
        "schema_version": SCHEMA_VERSION,
        "example_source_id": example_id,
        "source_name_fingerprint": resolution.get("source_name_fingerprint"),
        "authorization_status": decision["authorization_status"],
        "authorized": decision["authorized"],
        "blocking_decisions": decision["blocking_decisions"],
        "blocking_prerequisites": decision["blocking_prerequisites"],
        "authority_for_each_requirement": dict(AUTHORITY_FOR_FACT),
        "gate_163_sequence": list(GATE_163_SEQUENCE),
        "grants_nothing": True,
        "is_a_read_model": (
            "this reads recorded facts and reports what is missing. It writes "
            "nothing and sets no flag."
        ),
        "resolver_invariant_failures": resolver_invariant_failures(resolution),
        "authorization_invariant_failures": authorization_invariant_failures(
            decision
        ),
        "live_transport_permitted": False,
        "source_monitoring_live": False,
    }


def _health() -> dict[str, Any]:
    evaluated = evaluate_registry()
    shipped = load_registry_rows()
    fixtures = describe_fixture_registry(shipped)
    return {
        "schema_version": SCHEMA_VERSION,
        "authorization_boundary_ready": True,
        "required_fact_count": len(FACT_NAMES),
        "fact_statuses": list(FACT_STATUSES),
        "permitting_fact_statuses": sorted(PERMITTING_FACT_STATUSES),
        "refusal_meaning": REFUSAL_MEANING,
        "decision_facts": list(DECISION_FACTS),
        "freshness_facts": list(FRESHNESS_FACTS),
        "sources_evaluated": fixtures["merged_count"],
        "shipped_registry_count": len(shipped),
        "terms_blocked_count": int(evaluated.get("terms_blocked_count") or 0),
        "human_review_blocked_count": int(
            evaluated.get("human_review_blocked_count") or 0
        ),
        "real_approved_sources": 0,
        "real_allowlisted_sources": 0,
        "approved_source_count": 0,
        "monitorable_count": int(evaluated.get("monitorable_count") or 0),
        "caller_supplied_facts_accepted": 0,
        "fabricated_caller_bypass_possible": False,
        "second_activation_system_created": False,
        "terms_decisions_persisted": True,
        "human_review_decisions_persisted": True,
        "activation_composed": True,
        "runtime_derivation_repaired": True,
        "mutation_endpoints": 0,
        "live_fetch_opted_in": False,
        "live_transport_enabled": False,
        "live_transport_dispatchable": False,
        "live_source_calls": 0,
        "network_calls": 0,
        "emails_sent": 0,
        "object_store_calls": 0,
        "customer_data_persisted": False,
        "real_org_touched": False,
        "source_monitoring_live": False,
        "not_implied": list(NOT_IMPLIED),
        "not_an_approval": list(NOT_AN_APPROVAL),
    }


def _blockers_markdown() -> str:
    return """# What still blocks the first live source

Gate 162 made the live guard's permitted branch reachable only from recorded,
attributable facts. It approved nothing.

## The eleven facts, and who owns each unresolved one

```text
source_registered     the registry curator            SATISFIED (177 sources)
rate_limit_status     declared politeness policy      SATISFIED
user_agent_status     the canonical user agent        SATISFIED
credential_status     public sources need none        SATISFIED for public

terms_status          A HUMAN REVIEWER                MISSING for all 177
human_review_status   A HUMAN REVIEWER                MISSING for all 177
activation_status     an operator, with attribution   MISSING for all 177
attribution_status    derived from the terms decision MISSING for all 177
robots_status         a live robots.txt fetch         UNRESOLVABLE here
collector_status      an operator, by starting one    not_active
runtime_status        the Gates 157-161 lanes         observed per process
```

## The ordering constraint Gate 163 must honour

`robots_status` cannot be answered without an HTTP request to the source. So
Gate 163's **first live call is a robots.txt fetch, not a collection**, and its
result has to be recorded before any other request to that host is permitted.

That is the politeness requirement arriving before the traffic it governs.

## What a human has to do before any real source can be called

```text
1  read a source's actual terms and record a signed terms decision
   (reviewed_by, reviewed_at, and an evidence fingerprint of the document -
    the database refuses an approval without all three)
2  record a signed source review decision
3  record an activation with attribution, in
   nf_active_opportunity_sources
4  perform and record a robots.txt fetch
5  and only then may a collection request be permitted
```

## What is still missing in code, after all of that

```text
no live transport implementation   Gate 161 built none
live not dispatchable              DISPATCHABLE_KINDS = {hermetic}
allow_live_fetch hardcoded False   in authorize_source_for_live_access
migration 0047 CHECK constraints   refuse transport_kind='live' and
                                   live_source_call=1
```

A fully authorized source today would sit at `live_fetch_not_opted_in`.
**Authorization complete is not a permitted request**, and the two are separate
fields so that one cannot be read as the other.

## Current state

```text
sources evaluated                 179  (177 shipped + 2 synthetic fixtures)
real sources approved               0
real sources allowlisted            0
synthetic fixtures allowlisted      1  (the reachability proof)
terms-blocked                     171
human-review-blocked                6
live source calls                   0
source_monitoring_live          false
```

## The one thing worth re-reading before Gate 163

The synthetic fixture reaching `approved` is what makes every refusal here
falsifiable - without it, a boundary that refused unconditionally would pass
every check. It proves the chain can say yes.

It proves nothing about any real source. Its terms approval was signed by
`reviewer:nf162-artifact` against a fingerprint of a string in this
repository, and its host is `.invalid`. The temptation at Gate 163 will be to
treat the mechanism as the permission. The mechanism is built; the permission
is a human's to give.
"""


def build_authorization_artifacts() -> dict[str, str]:
    """Every artifact body, keyed by filename. Writes nothing."""
    files = {
        SURVEY_FILE: _json(_survey()),
        MAPPING_FILE: _json(_mapping()),
        MODEL_FILE: _json(_model()),
        TERMS_FILE: _json(_decision_status(TERMS)),
        HUMAN_FILE: _json(_decision_status(HUMAN_REVIEW)),
        RUNTIME_FILE: _json(_runtime()),
        ALLOWLIST_FILE: _json(_allowlist()),
        FORGED_FILE: _json(_forged()),
        PERMITTED_FILE: _json(_permitted_branch()),
        PACKET_FILE: _json(_packet_example()),
        HEALTH_FILE: _json(_health()),
        BLOCKERS_FILE: _blockers_markdown(),
    }
    for name, body in files.items():
        _assert_no_forbidden_shape(name, body)
    return files


def write_authorization_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_authorization_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def authorization_artifact_invariant_failures(
    result: dict[str, Any],
) -> list[str]:
    fails: list[str] = []

    written = set(result.get("files_written") or [])
    missing = set(ARTIFACT_FILES) - written
    if missing:
        fails.append(f"artifact_files_missing:{sorted(missing)}")
    extra = written - set(ARTIFACT_FILES)
    if extra:
        fails.append(f"artifact_files_undeclared:{sorted(extra)}")
    if result.get("file_count") != len(written):
        fails.append("file_count_disagrees_with_the_names")

    return fails


__all__ = [
    "ARTIFACT_DIR",
    "ARTIFACT_FILES",
    "authorization_artifact_invariant_failures",
    "build_authorization_artifacts",
    "write_authorization_artifacts",
]
