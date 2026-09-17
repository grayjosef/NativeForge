"""Gate 161 verifier phase: the envelope, every outcome.

One process, because these share a transport registry and a job set. Each key
this prints is a fact the shell asserts; a key that cannot be False is a key
worth deleting, so every one of them is derived from something measured.

Rows written here are cleaned up by `_g161_phase_cleanup.py`, which is the
LAST phase of the verifier. Nothing that writes may run after it.
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import UTC, datetime, timedelta

sys.path.insert(0, "src")
sys.path.insert(0, ".")

import sqlalchemy as sa  # noqa: E402
from tests import session_org_helper as soh  # noqa: E402

from nativeforge.db.session import SessionLocal  # noqa: E402
from nativeforge.repositories.source_collection_execution_attempt_repository import (  # noqa: E402,E501
    ATTEMPTS,
    count_attempts,
)
from nativeforge.repositories.source_collection_job_repository import (  # noqa: E402
    enqueue_job,
)
from nativeforge.services.hermetic_source_transport_service import (  # noqa: E402
    HermeticTransportRegistry,
)
from nativeforge.services.source_collection_execution_policy_service import (  # noqa: E402,E501
    build_execution_policy,
)
from nativeforge.services.source_collection_transport_service import (  # noqa: E402
    DISPATCHABLE_KINDS,
    HERMETIC,
    LIVE,
    execute_request,
)
from nativeforge.services.source_collector_execution_service import (  # noqa: E402
    execute_collection,
    execution_invariant_failures,
)
from nativeforge.services.source_raw_payload_replay_service import (  # noqa: E402
    replay_payload,
)

DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
NOW = datetime(2026, 9, 16, 12, 0, tzinfo=UTC)
PREFIX = "nf161-verify-"

BODY = b'{"opportunities":[{"number":"NF-161-V","title":"fixture"}]}'

URLS = {
    "ok": "https://fixtures.invalid/nf161/verify/ok",
    "malformed": "https://fixtures.invalid/nf161/verify/malformed",
    "timeout": "https://fixtures.invalid/nf161/verify/timeout",
    "rate": "https://fixtures.invalid/nf161/verify/429",
    "error": "https://fixtures.invalid/nf161/verify/503",
    "notfound": "https://fixtures.invalid/nf161/verify/404",
    "missing": "https://fixtures.invalid/nf161/verify/unregistered",
}

REG = HermeticTransportRegistry()
REG.register_ok(URLS["ok"], BODY, etag='W/"nf161-verify"')
REG.register_malformed(URLS["malformed"])
REG.register_timeout(URLS["timeout"], after_seconds=9.5)
REG.register_rate_limited(URLS["rate"], retry_after=120)
REG.register_server_error(URLS["error"], status_code=503)
REG.register_not_found(URLS["notfound"])

out: dict[str, object] = {}
detail: list[str] = []
session = SessionLocal()

try:
    soh.ensure_org(DEMO, "demo")
    stamp = uuid.uuid4().hex[:8]
    before = count_attempts(connection=session, organization_id=DEMO)["total"]

    def run(key: str, **kw: object) -> dict:
        source_id = f"nf161.fixture.verify.{key}"
        job_id = f"{PREFIX}{stamp}-{key}"
        enqueue_job(
            connection=session,
            organization_id=DEMO,
            job_id=job_id,
            idempotency_key=job_id,
            source_id=source_id,
            schedule_key=f"{PREFIX}{stamp}",
            scheduled_for=NOW - timedelta(minutes=5),
            now=NOW,
        )
        report = execute_collection(
            connection=session,
            organization_id=kw.pop("organization_id", DEMO),
            job_id=job_id,
            source_definition={
                "source_id": kw.pop("source_id", source_id),
                "endpoint": URLS[key],
                "method": "GET",
            },
            transport=REG.transport,
            now=NOW,
            is_synthetic_fixture=kw.pop("is_synthetic_fixture", True),
            **kw,
        )
        fails = execution_invariant_failures(report)
        if fails:
            detail.append(f"{key}:{fails}")
        return report

    ok = run("ok")
    mal = run("malformed")
    to = run("timeout")
    rate = run("rate")
    err = run("error")
    nf = run("notfound")
    miss = run("missing")

    # ---- 1-3: the bytes ------------------------------------------------
    out["ok_proof_available"] = bool(ok["execution_proof_available"])
    out["ok_bytes_match_exactly"] = bool(ok["bytes_received"] == len(BODY))

    replay = replay_payload(
        connection=session,
        organization_id=DEMO,
        attempt_id=ok["execution_attempt_id"],
    )
    out["ok_hash_verified_on_readback"] = bool(replay.get("hash_verified"))

    # The hash is of the EXACT transported bytes, not of anything decoded.
    # Measured by hashing the fixture body directly and comparing - if the
    # store hashed a decoded or normalised form, these would differ.
    import hashlib

    expected = hashlib.sha256(BODY).hexdigest()
    out["ok_persisted_before_decoding"] = bool(
        ok["raw_payload_sha256"] == expected
    )
    if ok["raw_payload_sha256"] != expected:
        detail.append(f"hash {ok['raw_payload_sha256']} != {expected}")

    # ---- 4-5: what the proof says -------------------------------------
    proof = ok.get("proof") or {}
    out["proof_needs_all_seven"] = bool(
        len(proof.get("requirements_expected") or ()) == 7
        and set(proof.get("requirements") or {})
        == set(proof.get("requirements_expected") or ())
        and all((proof.get("requirements") or {}).values())
    )
    out["proof_denies_a_source_responded"] = bool(
        proof.get("proves_the_envelope_works") is True
        and proof.get("proves_a_source_responded") is False
        and proof.get("permits_real_source_job_completion") is False
    )

    # ---- 6-11: the other outcomes --------------------------------------
    out["not_found_recorded"] = bool(
        nf["http_status"] == 404 and nf["attempt_recorded"]
    )
    # A 404 IS evidenced. The envelope transported real bytes, hashed them and
    # stored them, and "the source says there is nothing there" is a fact worth
    # keeping - so the proof exists.
    out["not_found_is_still_evidenced"] = bool(nf["execution_proof_available"])
    # And it finishes nothing. The job asked for a source to be collected; a
    # 404 means there was nothing to collect.
    out["not_found_does_not_permit_completion"] = bool(
        (nf.get("proof") or {}).get("permits_hermetic_job_completion") is False
        and (nf.get("proof") or {}).get("response_was_usable") is False
    )
    out["timeout_recorded_no_payload"] = bool(
        to["execution_status"] == "transport_failed"
        and to["refusal_reason"] == "transport_timeout"
        and to["raw_payload_sha256"] is None
        and to["attempt_recorded"]
    )
    out["rate_limited_body_persisted"] = bool(
        rate["http_status"] == 429 and rate["raw_payload_sha256"]
    )
    out["server_error_body_persisted"] = bool(
        err["http_status"] == 503 and err["raw_payload_sha256"]
    )
    out["malformed_persisted"] = bool(mal["raw_payload_sha256"])
    out["malformed_is_not_a_failure"] = bool(
        mal["response_received"] and mal["execution_status"] != "transport_failed"
    )
    out["unregistered_is_a_connection_failure"] = bool(
        miss["refusal_reason"] == "transport_connection_failed"
        and miss["http_status"] is None
    )

    # ---- 12: a row for EVERY outcome ------------------------------------
    refused = execute_collection(
        connection=session,
        organization_id=DEMO,
        job_id=f"{PREFIX}{stamp}-refused",
        source_definition={
            "source_id": "grants.gov",
            "endpoint": URLS["ok"],
            "method": "GET",
        },
        transport=REG.transport,
        now=NOW,
        is_synthetic_fixture=False,
    )
    out["real_source_refused_by_policy"] = bool(
        refused["execution_status"] == "refused_by_policy"
        and refused["refusal_reason"] == "not_a_synthetic_fixture"
        and not refused["transport_invoked"]
    )
    after = count_attempts(connection=session, organization_id=DEMO)["total"]
    # Seven executions plus the refusal. Every one of them left a row.
    out["attempt_row_for_every_outcome"] = bool(after - before == 8)
    if after - before != 8:
        detail.append(f"rows {after - before} != 8")

    # ---- 13-14: the database refuses a live row -------------------------
    savepoint = session.begin_nested()
    try:
        session.execute(
            sa.insert(ATTEMPTS).values(
                id=uuid.uuid4(),
                organization_id=DEMO,
                attempt_id=f"{PREFIX}{stamp}-livecall",
                attempt_number=1,
                collector_version="v",
                job_id=f"{PREFIX}{stamp}-livecall",
                source_id="s",
                started_at=NOW,
                execution_status="response_received",
                transport_kind="hermetic",
                refusal_reason="none",
                fact_status="synthetic_fixture",
                live_source_call=True,
            )
        )
        out["db_refuses_a_live_call_row"] = False
        detail.append("a row claiming live_source_call was ACCEPTED")
    except Exception:  # noqa: BLE001 - the refusal is the result
        out["db_refuses_a_live_call_row"] = True
    finally:
        savepoint.rollback()

    savepoint = session.begin_nested()
    try:
        session.execute(
            sa.insert(ATTEMPTS).values(
                id=uuid.uuid4(),
                organization_id=DEMO,
                attempt_id=f"{PREFIX}{stamp}-livekind",
                attempt_number=1,
                collector_version="v",
                job_id=f"{PREFIX}{stamp}-livekind",
                source_id="s",
                started_at=NOW,
                execution_status="response_received",
                transport_kind="live",
                refusal_reason="none",
                fact_status="synthetic_fixture",
            )
        )
        out["db_refuses_a_live_transport_kind"] = False
        detail.append("a row with transport_kind=live was ACCEPTED")
    except Exception:  # noqa: BLE001
        out["db_refuses_a_live_transport_kind"] = True
    finally:
        savepoint.rollback()

    # ---- 15-17: the three code-side refusals, each measured alone --------
    policy = build_execution_policy(
        source_id="nf161.fixture.verify.ok",
        organization_id=DEMO,
        is_synthetic_fixture=True,
        transport_kind=LIVE,
    )
    out["live_refused_by_policy"] = bool(
        not policy["execution_allowed"] and not policy["live_transport_allowed"]
    )

    # The boundary, asked directly with a policy that PERMITS - so what refuses
    # is the boundary itself and not the policy standing in front of it.
    permissive = dict(policy)
    permissive["execution_allowed"] = True
    permissive["live_transport_allowed"] = True
    permissive["hermetic_transport_allowed"] = True
    from nativeforge.services.source_collection_request_builder_service import (
        build_source_request,
    )

    built = build_source_request(
        source_definition={
            "source_id": "nf161.fixture.verify.ok",
            "endpoint": URLS["ok"],
            "method": "GET",
        }
    )
    dispatched = execute_request(
        request=built["transport_request"],
        transport_kind=LIVE,
        transport=REG.transport,
        policy=permissive,
    )
    out["live_refused_by_the_boundary"] = bool(not dispatched["dispatched"])
    if dispatched["dispatched"]:
        detail.append("the boundary dispatched a LIVE request")

    out["live_not_dispatchable"] = bool(
        LIVE not in DISPATCHABLE_KINDS and HERMETIC in DISPATCHABLE_KINDS
    )

    # ---- 18-22: the counters --------------------------------------------
    totals = count_attempts(connection=session, organization_id=DEMO)
    out["counters_all_zero"] = bool(
        totals["live_attempts"] == 0
        and totals["rows_claiming_a_live_call"] == 0
        and ok["collectors_invoked"] == 0
        and ok["live_source_calls"] == 0
        and ok["network_calls"] == 0
        and ok["approved_source_count"] == 0
        and ok["source_monitoring_live"] is False
    )

    session.commit()
except Exception as exc:  # noqa: BLE001 - the phase reports rather than raises
    detail.append(f"phase_error:{type(exc).__name__}:{exc}")
    session.rollback()
finally:
    session.close()

# A key that never appeared is a check that never ran. Default them to False so
# an exception halfway through fails the verifier rather than skipping checks.
for key in (
    "ok_proof_available", "ok_bytes_match_exactly",
    "ok_hash_verified_on_readback", "ok_persisted_before_decoding",
    "malformed_persisted", "malformed_is_not_a_failure",
    "not_found_recorded", "not_found_is_still_evidenced",
    "not_found_does_not_permit_completion",
    "timeout_recorded_no_payload", "rate_limited_body_persisted",
    "server_error_body_persisted", "unregistered_is_a_connection_failure",
    "attempt_row_for_every_outcome", "proof_needs_all_seven",
    "proof_denies_a_source_responded", "real_source_refused_by_policy",
    "live_refused_by_policy", "live_refused_by_the_boundary",
    "live_not_dispatchable", "db_refuses_a_live_call_row",
    "db_refuses_a_live_transport_kind", "counters_all_zero",
):
    out.setdefault(key, False)

out["detail"] = "; ".join(detail) if detail else None
print(json.dumps(out, sort_keys=True))
