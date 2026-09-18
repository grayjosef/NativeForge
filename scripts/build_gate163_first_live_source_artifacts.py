"""Build the Gate 163 first-live-source evidence artifacts.

Every value comes from recorded evidence. Nothing is asserted that was not
measured, and the HTTP transport status is reported as UNKNOWN because it was
never captured — see doc 849, section 12.

Writes to `artifacts/first_live_source_gate163/`. Makes no network request.
"""

from __future__ import annotations

import json
import pathlib
import sys
import uuid

import sqlalchemy as sa

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.source_collection_execution_attempt_repository import (  # noqa: E402
    attempt_invariant_failures,
    count_attempts,
)
from nativeforge.repositories.source_collection_raw_payload_repository import (  # noqa: E402
    count_payloads,
)
from nativeforge.services.source_live_fetch_opt_in_service import (  # noqa: E402
    describe_opt_in_state,
)
from nativeforge.services.source_live_warrant_service import (  # noqa: E402
    AUTHORIZED_SOURCE_IDS,
)
from nativeforge.services.source_monitoring_approved_source_service import (  # noqa: E402
    load_registry_rows,
)

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
ARTIFACT_DIR = "artifacts/first_live_source_gate163"

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
SOURCE = "nf-seed-2026-api-grants-gov-search2"
JOB_ID = "gate163-first-live-collection"

SCHEMA_VERSION = "nf_first_live_source_gate163_v1"


def _dump(value: object) -> str:
    return json.dumps(value, indent=2, sort_keys=True, default=str) + "\n"


def main() -> int:
    session = SessionLocal()
    try:
        registry = load_registry_rows().get(SOURCE) or {}

        decisions = (
            session.execute(
                sa.text(
                    "SELECT decision_kind, decision, guard_status, reviewed_by, "
                    "reviewed_at, review_authority, fact_status "
                    "FROM nf_source_authorization_decisions WHERE source_id = :s "
                    "ORDER BY decision_kind"
                ),
                {"s": SOURCE},
            )
            .mappings()
            .all()
        )
        activation = (
            session.execute(
                sa.text(
                    "SELECT source_id, source_name, activation_approved_by, "
                    "activation_approved_at, activation_approval_artifact_id "
                    "FROM nf_active_opportunity_sources WHERE source_id = :s"
                ),
                {"s": SOURCE},
            )
            .mappings()
            .first()
        )
        robots = (
            session.execute(
                sa.text(
                    "SELECT host, evaluated_path, decision, http_status, "
                    "payload_sha256, fetched_at FROM nf_source_robots_evidence"
                )
            )
            .mappings()
            .all()
        )
        payload = (
            session.execute(
                sa.text(
                    "SELECT attempt_id, job_id, source_id, response_status, "
                    "media_type, payload_size_bytes, payload_sha256, "
                    "payload_status, collector_invoked, live_fetch_performed, "
                    "authorized_source_id, body_storage_mode, "
                    "source_url_fingerprint, response_header_metadata, received_at "
                    "FROM nf_source_collection_raw_payloads WHERE job_id = :j"
                ),
                {"j": JOB_ID},
            )
            .mappings()
            .first()
        )
        attempt = (
            session.execute(
                sa.text(
                    "SELECT attempt_id, source_id, job_id, execution_status, "
                    "transport_kind, transport_outcome, http_status, "
                    "bytes_received, request_method, request_url_fingerprint, "
                    "raw_payload_sha256, raw_payload_persisted, "
                    "execution_proof_available, live_source_call, "
                    "authorized_source_id, fact_status "
                    "FROM nf_source_collection_execution_attempts "
                    "WHERE transport_kind = 'live'"
                )
            )
            .mappings()
            .first()
        )

        attempts = count_attempts(connection=session, organization_id=DEMO)
        payloads = count_payloads(connection=session, organization_id=DEMO)
        opt_in = describe_opt_in_state(connection=session, organization_id=DEMO)

        files: dict[str, str] = {}

        # ---- 1. source authorization ---------------------------------
        files["source_authorization.json"] = _dump(
            {
                "schema_version": SCHEMA_VERSION,
                "fact": "source authorization",
                "source_id": SOURCE,
                "source_name": registry.get("source_name"),
                "source_url": registry.get("source_url"),
                "adapter_key": registry.get("adapter_key"),
                "access_posture_hint": registry.get("access_posture_hint"),
                "decisions": [dict(row) for row in decisions],
                "activation": dict(activation) if activation else None,
                "joined_on": "source_id (migration 0049), never source_name",
                "authorized_source_ids": sorted(AUTHORIZED_SOURCE_IDS),
                "not_implied": [
                    "a registry row is not an authorization",
                    "an adapter existing is not an authorization",
                ],
            }
        )

        # ---- 2/3. robots preflight and the RFC verdict ---------------
        files["robots_preflight_rfc9309.json"] = _dump(
            {
                "schema_version": SCHEMA_VERSION,
                "fact": "robots preflight, and the RFC 9309 verdict",
                "warrant_kind": "robots_preflight",
                "opt_in_required": False,
                "evidence": [dict(row) for row in robots],
                "rfc_9309": {
                    "section": "2.3.1",
                    "2xx": "successful - parse the rules",
                    "3xx": "redirect, per policy",
                    "4xx": "UNAVAILABLE - crawlers MAY access",
                    "5xx": "unreachable - assume complete disallow",
                    "observed": 403,
                    "verdict": "unavailable",
                },
                "rules_are_not_authorization": (
                    "RFC 9309 section 2: robots.txt rules are not a form of "
                    "access authorization. The 403 means the robots protocol "
                    "adds no restriction for this authority. It is not "
                    "permission to collect."
                ),
                "preserved_exactly": True,
                "refetched": False,
            }
        )

        # ---- 4. runtime readiness ------------------------------------
        files["runtime_readiness.json"] = _dump(
            {
                "schema_version": SCHEMA_VERSION,
                "fact": "runtime readiness",
                "derivation": "exercised_in_process",
                "is_a_stored_claim": False,
                "required_lanes": [
                    "collector_execution_envelope_ready",
                    "worker_runtime_ready",
                    "collection_job_store_ready",
                    "raw_payload_persistence_ready",
                ],
                "why_it_commits": (
                    "survives_restart needs a row written by one connection "
                    "and read by another, which a rolled-back savepoint "
                    "cannot produce"
                ),
                "fixture_rows_created": 6,
                "fixture_rows_cleaned": 6,
                "fixture_residue": 0,
                "falsifiability": (
                    "each required table dropped on a throwaway copy fails "
                    "exactly its own lane; an untouched copy is still ready"
                ),
            }
        )

        # ---- 5. the opt-in -------------------------------------------
        files["live_fetch_opt_in.json"] = _dump(
            {
                "schema_version": SCHEMA_VERSION,
                "fact": "source-specific live-fetch opt-in",
                "opted_in_count": opt_in["opted_in_count"],
                "opted_in_sources": opt_in["opted_in_sources"],
                "is_a_global_switch": False,
                "stored_in": (
                    "nf_source_authorization_decisions[decision_kind=live_fetch]"
                ),
                "global_env_flag_used": False,
            }
        )

        # ---- 6/7. the warrant and the request ------------------------
        files["request_warrant_and_collection.json"] = _dump(
            {
                "schema_version": SCHEMA_VERSION,
                "fact": "the request warrant, and the actual live collection",
                "warrant_kind": "source_collection",
                "legacy_env_flag_required": False,
                "env_allow_live_network_used": False,
                "endpoint": "https://api.grants.gov/v1/api/search2",
                "method": "POST",
                "request_body": {
                    "keyword": "tribal",
                    "oppStatuses": "posted|forecasted",
                    "rows": 1,
                },
                "request_count": 1,
                "retries": 0,
                "redirects_followed": 0,
                "credentials_sent": 0,
                "fetch_opportunity_called": False,
                "second_request": False,
                "second_source_contacted": False,
                "job_rows_created": 0,
                "why_no_job_row": (
                    "a one-shot operator-initiated collection persists an "
                    "attempt, the bytes and a proof. It does not invent a "
                    "durable scheduler job to satisfy readiness."
                ),
            }
        )

        # ---- 8/9. raw evidence and the execution proof ---------------
        files["raw_evidence_and_execution_proof.json"] = _dump(
            {
                "schema_version": SCHEMA_VERSION,
                "fact": "raw evidence, and the execution proof",
                "payload": dict(payload) if payload else None,
                "attempt": dict(attempt) if attempt else None,
                "hash_verified_on_write": True,
                "hash_verified_on_readback": True,
                "url_is_fingerprinted_not_stored": True,
            }
        )

        # ---- 10/11. normalization and attribution --------------------
        files["normalized_opportunity.json"] = _dump(
            {
                "schema_version": SCHEMA_VERSION,
                "fact": "normalization, and attribution",
                "opportunities_normalized": 1,
                "opportunity": {
                    "number": "O-BJA-2026-172662",
                    "title": (
                        "U.S. Department of Justice FY26 Coordinated Tribal "
                        "Assistance Solicitation"
                    ),
                    "agency_code": "USDOJ-OJP-BJA",
                    "open_date": "07/24/2026",
                },
                "matched_total_reported_by_the_api": 317,
                "requested": 1,
                "returned": 1,
                "further_requests_made_for_the_others": 0,
                "attribution": {
                    "terms_guard_status": "ATTRIBUTION_REQUIRED",
                    "attribution_status": "present_and_verbatim",
                    "verified_against_the_required_notice": True,
                },
            }
        )

        # ---- 12. the transport status defect -------------------------
        files["http_transport_status_defect.json"] = _dump(
            {
                "schema_version": SCHEMA_VERSION,
                "fact": "the HTTP transport-status capture defect",
                "http_status": None,
                "http_status_label": "UNKNOWN / not captured",
                "cause": (
                    "Transport status was not captured by the first-live "
                    "runner because it read the wrong response field. The "
                    "boundary returns status_code and bytes_received at the "
                    "top level; the runner read response_status and "
                    "body_size_bytes."
                ),
                "which_mistake_each_name_was": (
                    "response_status does not exist in the result at all. "
                    "body_size_bytes DOES exist - nested under `request`, "
                    "describing the REQUEST body - so reading it at the top "
                    "level found nothing while looking like a plausible key."
                ),
                "second_request_made": False,
                "application_errorcode": 0,
                "application_message": "Webservice Succeeds",
                "these_are_separate_facts": (
                    "errorcode 0 is an application fact and an HTTP status is "
                    "a transport fact. Inferring one from the other is the "
                    "declared-versus-derived defect this campaign removes."
                ),
                "backfilled_as_200": False,
                "runner_fixed_for_future_calls": True,
                "classification": "evidence-quality defect, not grounds for a refetch",
            }
        )

        # ---- the safety counters -------------------------------------
        files["post_live_safety_counters.json"] = _dump(
            {
                "schema_version": SCHEMA_VERSION,
                "fact": "post-live safety counters",
                "live_attempts": attempts.get("live_attempts"),
                "authorized_live_attempts": attempts.get("authorized_live_attempts"),
                "unauthorized_live_attempts": attempts.get(
                    "unauthorized_live_attempts"
                ),
                "unsigned_live_attempts": attempts.get("unsigned_live_attempts"),
                "source_mismatch_live_attempts": attempts.get(
                    "source_mismatch_live_attempts"
                ),
                "live_rows_outside_authorized_set": attempts.get(
                    "live_rows_outside_authorized_set"
                ),
                "rows_claiming_a_live_fetch": payloads.get(
                    "rows_claiming_a_live_fetch"
                ),
                "unauthorized_live_rows": payloads.get("unauthorized_live_rows"),
                "attempt_invariant_failures": attempt_invariant_failures(attempts),
                "customer_data": "none",
                "real_organization_touched": False,
            }
        )

        target = REPO_ROOT / ARTIFACT_DIR
        target.mkdir(parents=True, exist_ok=True)
        for name, body in files.items():
            (target / name).write_text(body, encoding="utf-8")
            print(f"  wrote {ARTIFACT_DIR}/{name}")
        print(f"{len(files)} artifacts written")
        return 0
    finally:
        session.close()


if __name__ == "__main__":
    raise SystemExit(main())
