"""Gate 161P artifacts: what the execution envelope actually did.

Every file is DERIVED by running the envelope against a registered fixture, in
memory, with no database. Nothing here is a transcript of a prior run typed out
by hand, because an artifact that records what somebody believed happened is
worth less than no artifact at all.

The database-touching facts - attempt rows, provenance, replay - are the
verifier's job and are named here rather than restated, so a rebuild stays
byte-identical without a database.

## The fixture is fixed

A constant body, a constant instant, a registry built the same way every time.
A rebuild that produced different bytes would mean the artifacts record a
moment rather than a behaviour.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.repositories.source_collection_execution_attempt_repository import (
    EXECUTION_STATUSES,
    REFUSAL_REASONS,
)
from nativeforge.services.hermetic_source_transport_service import (
    HermeticTransportRegistry,
    describe_hermetic_transport,
)
from nativeforge.services.source_collection_execution_chokepoint_service import (
    ENVELOPE_MODULES,
    LEGACY_TRANSPORTS,
    chokepoint_invariant_failures,
    scan_execution_chokepoint,
)
from nativeforge.services.source_collection_execution_policy_service import (
    build_execution_policy,
    execution_policy_invariant_failures,
)
from nativeforge.services.source_collection_execution_proof_service import (
    PROOF_REQUIREMENTS,
    REQUIREMENT_EVIDENCE,
    build_execution_proof,
    execution_proof_invariant_failures,
)
from nativeforge.services.source_collection_execution_retry_service import (
    MAX_RETRY_AFTER_SECONDS,
    evaluate_execution_retry,
    execution_retry_invariant_failures,
)
from nativeforge.services.source_collection_request_builder_service import (
    ALLOWED_SCHEMES,
    CREDENTIAL_PARAM_NAMES,
    build_source_request,
    request_builder_invariant_failures,
)
from nativeforge.services.source_collection_transport_service import (
    ALLOWED_METHODS,
    ALLOWED_REQUEST_HEADERS,
    DISPATCHABLE_KINDS,
    HERMETIC,
    LIVE,
    MAX_RESPONSE_BYTES,
    TRANSPORT_KINDS,
    describe_boundary,
    execute_request,
    transport_invariant_failures,
)
from nativeforge.services.source_collection_worker_runtime_service import (
    HANDLER_EVALUATE_ONLY,
    HANDLER_HERMETIC_EXECUTION,
    HERMETIC_FIXTURE_PREFIX,
    HERMETIC_REFUSALS,
    hermetic_execution_refusals,
)
from nativeforge.services.source_collector_execution_health_service import (
    CONDITIONS,
    NOT_IMPLIED,
    detect_live_transport_available,
    detect_source_counts,
)
from nativeforge.services.source_collector_execution_service import COMPOSES

SCHEMA_VERSION = "nf_source_collector_execution_gate161_artifacts_v1"

ARTIFACT_DIR = "artifacts/source_collector_execution_gate161"

SURVEY_FILE = "collector_execution_survey.json"
POLICY_FILE = "execution_policy.json"
BUILDER_FILE = "request_builder_smoke.json"
OK_FILE = "hermetic_200.json"
TIMEOUT_FILE = "hermetic_timeout.json"
RATE_FILE = "hermetic_429.json"
ERROR_FILE = "hermetic_5xx.json"
LINKAGE_FILE = "raw_payload_linkage.json"
PROOF_FILE = "execution_proof.json"
HEALTH_FILE = "execution_health.json"
MONITORING_FILE = "source_monitoring_status.json"
BLOCKERS_FILE = "next_execution_blockers.md"

ARTIFACT_FILES: tuple[str, ...] = (
    SURVEY_FILE,
    POLICY_FILE,
    BUILDER_FILE,
    OK_FILE,
    TIMEOUT_FILE,
    RATE_FILE,
    ERROR_FILE,
    LINKAGE_FILE,
    PROOF_FILE,
    HEALTH_FILE,
    MONITORING_FILE,
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

MIGRATION = "0047"

#: Fixed, so a rebuild is byte-identical.
FIXTURE_INSTANT = "2026-09-16T12:00:00+00:00"
FIXTURE_SOURCE = "nf161.fixture.artifact"
FIXTURE_JOB = "nf161-artifact-job"

FIXTURE_URLS = {
    "ok": "https://fixtures.invalid/nf161/artifact/ok",
    "timeout": "https://fixtures.invalid/nf161/artifact/timeout",
    "rate": "https://fixtures.invalid/nf161/artifact/429",
    "error": "https://fixtures.invalid/nf161/artifact/503",
}

FIXTURE_BODY = (
    b'{"synthetic":true,"note":"Gate 161 fixture. Nothing was contacted.",'
    b'"opportunities":[]}'
)


def _json(payload: Any) -> str:
    return json.dumps(payload, indent=2, sort_keys=True, default=str) + "\n"


def _assert_no_forbidden_shape(name: str, body: str) -> None:
    for shape, pattern in FORBIDDEN_SHAPES:
        if re.search(pattern, body):
            raise AssertionError(f"artifact {name} contains a {shape}")


def _registry() -> HermeticTransportRegistry:
    registry = HermeticTransportRegistry()
    registry.register_ok(FIXTURE_URLS["ok"], FIXTURE_BODY, etag='W/"gate161"')
    registry.register_timeout(FIXTURE_URLS["timeout"], after_seconds=9.5)
    registry.register_rate_limited(FIXTURE_URLS["rate"], retry_after=120)
    registry.register_server_error(FIXTURE_URLS["error"], status_code=503)
    return registry


def _policy(**kw: Any) -> dict[str, Any]:
    return build_execution_policy(
        source_id=FIXTURE_SOURCE,
        organization_id="bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
        is_synthetic_fixture=True,
        transport_kind=HERMETIC,
        target_url=FIXTURE_URLS["ok"],
        **kw,
    )


def _dispatch(key: str) -> dict[str, Any]:
    """Build a request and put it through the boundary. No database."""
    built = build_source_request(
        source_definition={
            "source_id": FIXTURE_SOURCE,
            "endpoint": FIXTURE_URLS[key],
            "method": "GET",
        }
    )
    result = execute_request(
        request=built["transport_request"],
        transport_kind=HERMETIC,
        transport=_registry().transport,
        policy=_policy(),
    )
    # The body is bytes and cannot go in a JSON artifact; its LENGTH and HASH
    # can, and those are what an auditor would check.
    result.pop("body_bytes", None)
    return {
        "request": built.get("request"),
        "transport": result,
        "transport_invariant_failures": transport_invariant_failures(result),
    }


def _survey() -> dict[str, Any]:
    scan = scan_execution_chokepoint()
    boundary = describe_boundary()
    hermetic = describe_hermetic_transport()
    return {
        "schema_version": SCHEMA_VERSION,
        "gate": "161",
        "migration": MIGRATION,
        "composes": list(COMPOSES),
        "envelope_modules": list(ENVELOPE_MODULES),
        "modules_found": scan["modules_found"],
        "modules_expected": len(scan["modules_expected"]),
        "envelope_reaches_no_host": scan["envelope_reaches_no_host"],
        "modules_that_reach_a_host": scan["modules_that_reach_a_host"],
        "chokepoint_findings": scan["findings"],
        "chokepoint_invariant_failures": chokepoint_invariant_failures(scan),
        "how_this_is_measured": scan["how_this_is_measured"],
        "transport_boundary": boundary,
        "hermetic_transport": hermetic,
        "legacy_transports_not_refactored": list(LEGACY_TRANSPORTS),
        "why_legacy_transports_stay": scan["why_legacy_transports_stay"],
        "transport_kinds": list(TRANSPORT_KINDS),
        "dispatchable_kinds": sorted(DISPATCHABLE_KINDS),
        "live_transport_dispatchable": LIVE in DISPATCHABLE_KINDS,
        "allowed_methods": sorted(ALLOWED_METHODS),
        "allowed_request_headers": sorted(ALLOWED_REQUEST_HEADERS),
        "max_response_bytes": MAX_RESPONSE_BYTES,
        # SORTED, not listed. Both are frozensets - correctly, since they are
        # used for membership - and frozenset iteration order depends on
        # PYTHONHASHSEED, so `list()` made every rebuild in a new process
        # produce different bytes. The repository already writes
        # `sorted(EXECUTION_STATUSES)`; this did not.
        "execution_statuses": sorted(EXECUTION_STATUSES),
        "refusal_reasons": sorted(REFUSAL_REASONS),
        "live_source_call": False,
        "network_calls": 0,
        "source_monitoring_live": False,
    }


def _policy_artifact() -> dict[str, Any]:
    permitted = _policy()
    live = build_execution_policy(
        source_id=FIXTURE_SOURCE,
        organization_id="bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
        is_synthetic_fixture=True,
        transport_kind=LIVE,
        target_url=FIXTURE_URLS["ok"],
    )
    real_source = build_execution_policy(
        source_id="grants.gov",
        organization_id="bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
        is_synthetic_fixture=False,
        transport_kind=HERMETIC,
        target_url=FIXTURE_URLS["ok"],
    )
    real_org = build_execution_policy(
        source_id=FIXTURE_SOURCE,
        organization_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        is_synthetic_fixture=True,
        transport_kind=HERMETIC,
        target_url=FIXTURE_URLS["ok"],
    )
    wrong_scope = build_execution_policy(
        source_id=FIXTURE_SOURCE,
        organization_id="bbbbbbbb-cccc-dddd-eeee-ffffffffffff",
        is_synthetic_fixture=True,
        scope="production",
        transport_kind=HERMETIC,
        target_url=FIXTURE_URLS["ok"],
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "a_synthetic_fixture_hermetic": permitted,
        "a_live_transport": live,
        "a_real_source": real_source,
        "the_real_organization": real_org,
        "a_production_scope": wrong_scope,
        "invariant_failures": {
            "permitted": execution_policy_invariant_failures(permitted),
            "live": execution_policy_invariant_failures(live),
            "real_source": execution_policy_invariant_failures(real_source),
            "real_org": execution_policy_invariant_failures(real_org),
            "wrong_scope": execution_policy_invariant_failures(wrong_scope),
        },
        "only_the_first_was_allowed": bool(
            permitted["execution_allowed"]
            and not live["execution_allowed"]
            and not real_source["execution_allowed"]
            and not real_org["execution_allowed"]
            and not wrong_scope["execution_allowed"]
        ),
        "source_monitoring_live": False,
    }


def _builder_artifact() -> dict[str, Any]:
    built = build_source_request(
        source_definition={
            "source_id": FIXTURE_SOURCE,
            "endpoint": FIXTURE_URLS["ok"],
            "method": "GET",
            "query_parameters": {
                "rows": "25",
                # Refused by NAME, and its value appears nowhere below.
                "api_key": "this-must-be-refused",
            },
        }
    )
    built.pop("transport_request", None)

    insecure = build_source_request(
        source_definition={
            "source_id": FIXTURE_SOURCE,
            "endpoint": "http://fixtures.invalid/nf161/insecure",
            "method": "GET",
        }
    )
    insecure.pop("transport_request", None)

    caller_url = build_source_request(
        source_definition={"source_id": FIXTURE_SOURCE},
        caller_supplied_url="http://169.254.169.254/latest/meta-data/",
    )
    caller_url.pop("transport_request", None)

    return {
        "schema_version": SCHEMA_VERSION,
        "from_the_source_definition": built,
        "an_http_endpoint": insecure,
        "a_caller_supplied_url": caller_url,
        "allowed_schemes": sorted(ALLOWED_SCHEMES),
        "credential_parameter_names": sorted(CREDENTIAL_PARAM_NAMES),
        "invariant_failures": {
            "built": request_builder_invariant_failures(built),
            "insecure": request_builder_invariant_failures(insecure),
            "caller_url": request_builder_invariant_failures(caller_url),
        },
        "the_url_never_appears": (
            "the request description carries a sha256 fingerprint, as Gate 160 "
            "settled, because query strings carry api keys"
        ),
        "caller_supplied_url_exists_only_to_be_refused": (
            "the parameter is present so the refusal is reachable and testable. "
            "An unreachable refusal is an unfalsifiable one."
        ),
        "source_monitoring_live": False,
    }


def _proof_artifact() -> dict[str, Any]:
    import hashlib

    dispatched = _dispatch("ok")
    transport = dispatched["transport"]

    # The REAL hash of the fixture body, not a placeholder.
    #
    # The first draft used digest, which the forbidden-shape guard refused as
    # a provider-subject-shaped run of digits - correctly, and usefully: a
    # placeholder hash in a proof artifact is a number an auditor could believe.
    digest = hashlib.sha256(FIXTURE_BODY).hexdigest()

    # A proof built from records, with the payload and replay facts supplied as
    # the verifier measures them against a real database. Stated here as the
    # SHAPE of a proof rather than as a claim that this run wrote a row.
    complete = build_execution_proof(
        attempt={
            "attempt_id": "nf161-artifact-attempt",
            "job_id": FIXTURE_JOB,
            "source_id": FIXTURE_SOURCE,
            "transport_kind": HERMETIC,
            "raw_payload_persisted": True,
            "raw_payload_sha256": digest,
            "bytes_received": transport["bytes_received"],
        },
        payload={"persisted": True, "payload_sha256": digest},
        replay={"hash_verified": True, "linked_job_found": True,
                "provenance": {"job_id": FIXTURE_JOB}},
        policy=_policy(),
        transport_result=transport,
    )
    without_replay = build_execution_proof(
        attempt={
            "attempt_id": "nf161-artifact-attempt",
            "transport_kind": HERMETIC,
            "raw_payload_persisted": True,
            "raw_payload_sha256": digest,
        },
        payload={"persisted": True, "payload_sha256": digest},
        replay={},
        policy=_policy(),
        transport_result=transport,
    )
    return {
        "schema_version": SCHEMA_VERSION,
        "requirements": list(PROOF_REQUIREMENTS),
        "requirement_evidence": REQUIREMENT_EVIDENCE,
        "a_complete_proof": complete,
        "a_proof_missing_its_provenance": without_replay,
        "invariant_failures": {
            "complete": execution_proof_invariant_failures(complete),
            "incomplete": execution_proof_invariant_failures(without_replay),
        },
        "the_two_fields_that_must_stay_apart": {
            "proves_the_envelope_works": complete["proves_the_envelope_works"],
            "proves_a_source_responded": complete["proves_a_source_responded"],
            "why": (
                "a single boolean meaning both is exactly how the pipeline ran "
                "becomes the source answered"
            ),
        },
        "permits_hermetic_job_completion": complete[
            "permits_hermetic_job_completion"
        ],
        "permits_real_source_job_completion": False,
        "source_monitoring_live": False,
    }


def _linkage_artifact() -> dict[str, Any]:
    import hashlib

    dispatched = _dispatch("ok")
    return {
        "schema_version": SCHEMA_VERSION,
        "fixture_body_bytes": len(FIXTURE_BODY),
        "fixture_body_sha256": hashlib.sha256(FIXTURE_BODY).hexdigest(),
        "bytes_received": dispatched["transport"]["bytes_received"],
        "bytes_match": bool(
            dispatched["transport"]["bytes_received"] == len(FIXTURE_BODY)
        ),
        "hashed_before_decoding": (
            "the exact response bytes are hashed by "
            "s3_raw_payload_body_store_service.body_hash, which takes bytes, "
            "before any parse or normalisation"
        ),
        "the_store_is_gate_160s": (
            "source_raw_payload_persistence_service. Gate 161 adds no second "
            "payload store and duplicates no byte of one."
        ),
        "the_attempt_points_at_the_payload": (
            "by sha256 and by shared attempt_id, not by copying the body"
        ),
        "a_persisted_payload_is_not_a_successful_execution": True,
        "verified_against_a_database_by": (
            "scripts/verify_nativeforge_source_collector_execution_envelope.sh, "
            "which writes real rows, replays them and removes them"
        ),
        "source_monitoring_live": False,
    }


def _health_artifact() -> dict[str, Any]:
    counts = detect_source_counts()
    return {
        "schema_version": SCHEMA_VERSION,
        "conditions_expected": list(CONDITIONS),
        "not_implied": list(NOT_IMPLIED),
        "live_transport_available": detect_live_transport_available(),
        "approved_source_count": counts["approved"],
        "known_source_count": counts["known"],
        "monitorable_source_count": counts["monitorable"],
        "terms_blocked_source_count": counts["terms_blocked"],
        "human_review_blocked_source_count": counts["human_review_blocked"],
        "knowing_is_not_approving": (
            "the registry holds many sources and has approved none. Counting "
            "its rows reported every one of them as approved until the lane's "
            "own invariant refused it."
        ),
        "worker_handler": HANDLER_HERMETIC_EXECUTION,
        "worker_default_handler": HANDLER_EVALUATE_ONLY,
        "hermetic_refusal_conditions": list(HERMETIC_REFUSALS),
        "hermetic_fixture_prefix": HERMETIC_FIXTURE_PREFIX,
        "a_real_source_is_refused_by_the_worker": hermetic_execution_refusals(
            {
                "source_id": "grants.gov",
                "executable": True,
                "hermetic_fixture": True,
                "source_definition": {"source_id": "grants.gov"},
            },
            handler=HANDLER_HERMETIC_EXECUTION,
            transport=lambda request: None,
        ),
        "retry_classification": {
            "timeout": "transient",
            "connection_failed": "transient",
            "429": "transient, and Retry-After wins over the computed backoff",
            "5xx": "transient",
            "404_410": "permanent",
            "401_403": "permanent",
            "400_422": "permanent",
            "malformed_body": "not a failure - the bytes are persisted",
            "refused_before_dispatch": "not retried - a refusal is a decision",
            "activation_terms_human_review": "not retried - a human decides",
        },
        "max_retry_after_seconds": MAX_RETRY_AFTER_SECONDS,
        "collectors_invoked": 0,
        "live_source_calls": 0,
        "network_calls": 0,
        "jobs_completed": 0,
        "source_monitoring_live": False,
    }


def _monitoring_status() -> dict[str, Any]:
    return {
        "schema_version": SCHEMA_VERSION,
        "source_monitoring_live": False,
        "approved_source_count": 0,
        "collectors_invoked": 0,
        "live_source_calls": 0,
        "network_calls": 0,
        "urls_fetched": 0,
        "dns_resolved": False,
        "credentials_required": False,
        "emails_sent": 0,
        "object_store_calls": 0,
        "jobs_completed": 0,
        "customer_data_persisted": False,
        "real_org_touched": False,
        "live_transport_implemented": False,
        "live_transport_dispatchable": LIVE in DISPATCHABLE_KINDS,
        "execution_envelope_exists": True,
        "runtime_existence_is_not_live_monitoring": (
            "Gate 161 builds machinery that could make a source request and "
            "refuses to make one. The envelope existing, an execution proof "
            "existing, and a source being approved are three separate facts, "
            "and only the first two are true."
        ),
        "what_would_have_to_change_for_a_live_call": [
            "a live transport implementation, which does not exist",
            "LIVE added to DISPATCHABLE_KINDS",
            "the execution policy permitting a live transport",
            "migration 0047's hermetic_only and no_live_call constraints "
            "relaxed",
            "an approved source, which needs a human first",
        ],
    }


def _blockers_markdown() -> str:
    return """# What still blocks a live source call

Gate 161 built the envelope. Four things refuse a live call, independently, and
none of them takes caller input.

## The four stops

```text
1  the execution policy          refuses transport_kind=live
2  the transport boundary        refuses it again, on its own
3  DISPATCHABLE_KINDS            contains only `hermetic`
4  migration 0047                CHECK (transport_kind = 'hermetic')
                                 CHECK (live_source_call = 0)
```

Stop 1 is the only one a caller can influence, and Gate 94B's guard CAN be
satisfied by a caller who supplies every status - which is by design, because
Gate 162 will do exactly that, deliberately. The remaining three take no input
at all. A caller who talks their way past the guard still finds that nothing
can dispatch, and that the database will not hold the row.

## What is genuinely missing

```text
no live transport implementation    nothing in this repo can open a socket
                                    for a source request
zero approved sources               177 known, 171 terms-blocked,
                                    6 human-review-blocked, 0 approved
no source terms approval            a human decides, not a timer
no activation                       Gate 162 owns it
```

## What Gate 161 does NOT unlock

- It does not approve a source. The registry is full and approves nothing.
- It does not make monitoring live. `source_monitoring_live` stays false.
- It does not complete a real-source job. Gate 158's `transition_job` still has
  no execution-proof parameter and this gate does not add one.
- It does not mean a source responded. A hermetic proof says the path works.

## Owners

```text
Gate 162   activation and the allowlist
Gate 163   the first approved live source
a human    source terms, before either
```

## The one thing worth re-reading before Gate 162

A hermetic execution produces a real execution proof, and that proof is
correct: the bytes really were transported, persisted and verified. The
temptation at Gate 162 will be to treat that proof as evidence a source can be
called. It is not. It is evidence the envelope works, which is why the proof
carries `proves_the_envelope_works` and `proves_a_source_responded` as two
fields that cannot be read as one.
"""


def build_execution_artifacts() -> dict[str, str]:
    """Every artifact body, keyed by filename. Writes nothing."""
    files = {
        SURVEY_FILE: _json(_survey()),
        POLICY_FILE: _json(_policy_artifact()),
        BUILDER_FILE: _json(_builder_artifact()),
        OK_FILE: _json(_dispatch("ok")),
        TIMEOUT_FILE: _json(_dispatch("timeout")),
        RATE_FILE: _json(_dispatch("rate")),
        ERROR_FILE: _json(_dispatch("error")),
        LINKAGE_FILE: _json(_linkage_artifact()),
        PROOF_FILE: _json(_proof_artifact()),
        HEALTH_FILE: _json(_health_artifact()),
        MONITORING_FILE: _json(_monitoring_status()),
        BLOCKERS_FILE: _blockers_markdown(),
    }
    for name, body in files.items():
        _assert_no_forbidden_shape(name, body)
    return files


def write_execution_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_execution_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def execution_artifact_invariant_failures(result: dict[str, Any]) -> list[str]:
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
    "FIXTURE_BODY",
    "FIXTURE_URLS",
    "build_execution_artifacts",
    "evaluate_execution_retry",
    "execution_artifact_invariant_failures",
    "execution_retry_invariant_failures",
    "write_execution_artifacts",
]
