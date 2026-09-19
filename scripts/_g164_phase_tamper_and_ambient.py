"""Gate 164D + 164G: tamper refusals, and the ambient secret guard.

Two families of negative proof:

164D  corrupt a copy of the evidence, and require the refusal
164G  vary developer-machine state, and require canonical output not to move

## The real evidence is never touched

Every tamper case runs against a COPY of the database file. The Gate 163
collection is read-only here, and the copy is deleted afterwards. A tamper
test that mutated the real row and relied on a rollback would be one crashed
process away from destroying the thing this gate exists to protect.

## The control comes first

A copy with nothing changed must still verify. Without it, every refusal below
could be "it is a copy" rather than "the bytes were altered" - the same
control the Gate 164 lane-drop proofs needed.

Makes no network request: sockets are replaced with one that raises for the
whole run.
"""

from __future__ import annotations

import json
import os
import pathlib
import shutil
import socket
import sys
import tempfile
import uuid

import sqlalchemy as sa

sys.path.insert(0, "src")
sys.path.insert(0, ".")

REPO = pathlib.Path(__file__).resolve().parents[1]
DEMO = uuid.UUID("bbbbbbbb-cccc-dddd-eeee-ffffffffffff")
SOURCE = "nf-seed-2026-api-grants-gov-search2"
JOB = "gate163-first-live-collection"

out: dict[str, object] = {}
detail: list[str] = []

network_attempts = {"count": 0}
_REAL_SOCKET = socket.socket


def _refuse_socket(*args, **kwargs):  # noqa: ANN002, ANN003
    network_attempts["count"] += 1
    raise RuntimeError("a socket was attempted during the tamper phase")


socket.socket = _refuse_socket  # type: ignore[assignment]

try:
    from nativeforge.lib.settings import get_settings
    from nativeforge.services.live_collection_audit_service import (
        audit_invariant_failures,
        build_live_collection_audit,
    )
    from nativeforge.services.source_raw_payload_replay_service import (
        replay_payload,
    )

    url = get_settings().database_url
    prefix = "sqlite+pysqlite:///"
    source_db = pathlib.Path(url[len(prefix) :]).resolve()

    def on_a_copy(mutate_sql: str | None, params: dict | None = None) -> dict:
        """Replay + audit against a throwaway copy, optionally corrupted.

        A tamper the SCHEMA refuses is the strongest possible refusal - the
        corruption cannot exist at rest - so it is reported as
        `refused_by_the_database` rather than raised. An earlier version let
        that exception escape, and one constraint doing its job took every
        later proof in this phase down with it.
        """
        with tempfile.TemporaryDirectory() as directory:
            copy = pathlib.Path(directory) / "evidence.db"
            shutil.copy2(source_db, copy)
            engine = sa.create_engine(f"{prefix}{copy}")
            try:
                if mutate_sql:
                    try:
                        with engine.begin() as connection:
                            connection.execute(sa.text(mutate_sql), params or {})
                    except Exception as exc:  # noqa: BLE001 - the refusal IS the result
                        return {
                            "refused_by_the_database": True,
                            "refusal": type(exc).__name__,
                            "hash_verified": False,
                            "replayable": False,
                            "audit_complete": False,
                            "audit_invariants": [],
                            "missing": [],
                            "sections": {},
                        }
                with engine.connect() as connection:
                    attempt_id = connection.execute(
                        sa.text(
                            "SELECT attempt_id FROM "
                            "nf_source_collection_raw_payloads WHERE job_id = :j"
                        ),
                        {"j": JOB},
                    ).scalar()
                    replay = (
                        {}
                        if attempt_id is None
                        else replay_payload(
                            connection=connection,
                            organization_id=DEMO,
                            attempt_id=str(attempt_id),
                        )
                    )
                    audit = build_live_collection_audit(
                        connection=connection, organization_id=DEMO, job_id=JOB
                    )
                return {
                    "hash_verified": bool(replay.get("hash_verified")),
                    "replayable": bool(replay.get("replayable")),
                    "audit_complete": bool(audit.get("audit_chain_complete")),
                    "audit_invariants": audit_invariant_failures(audit),
                    "missing": list(audit.get("missing_sections") or []),
                    "sections": audit.get("sections") or {},
                }
            finally:
                engine.dispose()

    # ---- the control -------------------------------------------------
    clean = on_a_copy(None)
    out["an_untouched_copy_still_verifies"] = bool(
        clean["hash_verified"] and clean["replayable"] and clean["audit_complete"]
    )
    if not out["an_untouched_copy_still_verifies"]:
        detail.append(f"the untouched copy failed: {clean}")

    # ---- 164D: one corruption at a time -------------------------------
    changed_bytes = on_a_copy(
        "UPDATE nf_source_collection_raw_payloads SET body_bytes = :b "
        "WHERE job_id = :j",
        {"b": b"tampered", "j": JOB},
    )
    out["changed_raw_bytes_are_refused"] = not changed_bytes["hash_verified"]

    changed_hash = on_a_copy(
        "UPDATE nf_source_collection_raw_payloads SET payload_sha256 = :h "
        "WHERE job_id = :j",
        {"h": "0" * 64, "j": JOB},
    )
    out["a_changed_payload_hash_is_refused"] = not changed_hash["hash_verified"]

    changed_source = on_a_copy(
        "UPDATE nf_source_collection_raw_payloads SET source_id = :s WHERE job_id = :j",
        {"s": "nf-seed-2026-fed-001", "j": JOB},
    )
    out["a_changed_source_id_breaks_the_audit"] = bool(
        not changed_source["audit_complete"]
        or changed_source["sections"].get("execution", {}).get("authorized_source_id")
        != "nf-seed-2026-fed-001"
    )

    # Migration 0050:
    #   CHECK (transport_kind <> 'live' OR authorized_source_id IS NOT NULL)
    # so stripping the authorization from a live attempt cannot be written at
    # all. The strongest of the refusals here: the corrupt state has no
    # representation at rest, rather than being detected after the fact.
    changed_auth = on_a_copy(
        "UPDATE nf_source_collection_execution_attempts "
        "SET authorized_source_id = NULL WHERE source_id = :s",
        {"s": SOURCE},
    )
    out["a_stripped_authorized_source_id_is_refused"] = bool(
        changed_auth.get("refused_by_the_database")
        or changed_auth["sections"].get("execution", {}).get("authorized_source_id")
        is None
    )
    out["stripping_the_authorization_is_refused_by_the_schema"] = bool(
        changed_auth.get("refused_by_the_database")
    )

    changed_authority = on_a_copy(
        "UPDATE nf_source_collection_raw_payloads "
        "SET source_url_fingerprint = :f WHERE job_id = :j",
        {"f": "9" * 64, "j": JOB},
    )
    out["a_changed_request_authority_is_refused"] = not (
        changed_authority["sections"]
        .get("request", {})
        .get("fingerprint_matches_declared_endpoint")
    )

    no_proof = on_a_copy(
        "DELETE FROM nf_source_collection_execution_attempts WHERE source_id = :s",
        {"s": SOURCE},
    )
    out["a_missing_execution_proof_breaks_the_chain"] = bool(
        not no_proof["audit_complete"] and "execution" in no_proof["missing"]
    )

    # A proof that no longer matches the payload it names.
    mismatched = on_a_copy(
        "UPDATE nf_source_collection_execution_attempts "
        "SET raw_payload_sha256 = :h WHERE source_id = :s",
        {"h": "1" * 64, "s": SOURCE},
    )
    out["a_proof_that_names_other_bytes_is_refused"] = bool(
        "a_proof_that_does_not_match_the_payload_it_names"
        in mismatched["audit_invariants"]
    )

    # ---- an inferred HTTP status must be refused ----------------------
    #
    # The one tamper that looks like a fix. Backfilling 200 because the body
    # says errorcode 0 would make the audit claim a transport fact nobody
    # measured, so the invariant must catch the INCONSISTENT shape.
    from nativeforge.services.live_collection_audit_service import (
        audit_invariant_failures as invariants,
    )

    fabricated = {
        "schema_version": "nf_live_collection_audit_v1",
        "audit_chain_complete": True,
        "missing_sections": [],
        "is_a_second_ledger": False,
        "sections": {
            name: {} for name in ("source", "authorization", "request", "execution")
        },
    }
    fabricated["sections"]["normalization"] = {}
    fabricated["sections"]["response"] = {
        "http_status": 200,
        "http_status_known": False,
    }
    out["a_backfilled_http_status_is_refused"] = bool(
        "a_present_http_status_was_marked_unknown" in invariants(fabricated)
    )

    unexplained = json.loads(json.dumps(fabricated))
    unexplained["sections"]["response"] = {
        "http_status": None,
        "http_status_known": False,
    }
    out["an_unexplained_absent_status_is_refused"] = bool(
        "an_absent_http_status_was_not_explained" in invariants(unexplained)
    )

    # ---- 164G: the ambient secret guard -------------------------------
    from nativeforge.lib.settings import auth_environment_presence
    from nativeforge.services.canonical_artifact_build_context_service import (
        AmbientStateRefused,
        build_context_invariant_failures,
        canonical_build,
        environment_scoped_build,
        in_canonical_build,
    )

    out["canonical_is_not_the_default"] = not in_canonical_build()

    try:
        with canonical_build(reason="gate164 guard") as context:
            auth_environment_presence()
        out["canonical_refuses_ambient_secret_state"] = False
        detail.append("a canonical build read ambient auth state without raising")
    except AmbientStateRefused as refused:
        out["canonical_refuses_ambient_secret_state"] = True
        out["refused_reader"] = refused.reader

    out["the_flag_is_restored_after_a_refusal"] = not in_canonical_build()

    with canonical_build(reason="gate164 guard") as context:
        out["a_canonical_context_declares_itself"] = (
            context["scope"] == "canonical"
            and context["ambient_secret_state"] == "refused"
        )
        detail.extend(build_context_invariant_failures(context))
        # An EXPLICIT environ is an input, not an ambient read.
        explicit = auth_environment_presence({"OIDC_ISSUER": "supplied"})
        out["an_explicit_environ_is_still_an_input"] = bool(explicit.get("OIDC_ISSUER"))

    with environment_scoped_build(reason="describes one deployment") as context:
        out["environment_scoped_permits_what_it_exists_to_read"] = bool(
            auth_environment_presence() is not None
        )
        detail.extend(build_context_invariant_failures(context))
        out["an_environment_scoped_context_declares_itself"] = (
            context["scope"] == "environment_scoped"
        )

    # A build context that claims canonical while permitting ambient reads.
    out["a_contradictory_context_is_refused"] = bool(
        build_context_invariant_failures(
            {
                "schema_version": "nf_canonical_artifact_build_context_v1",
                "scope": "canonical",
                "ambient_secret_state": "permitted",
            }
        )
    )

    # ---- no secret VALUE anywhere in the audit ------------------------
    with sa.create_engine(url).connect() as connection:
        real_audit = build_live_collection_audit(
            connection=connection, organization_id=DEMO, job_id=JOB
        )
    serialized = json.dumps(real_audit, default=str)

    # The values to look for are the ones SETTINGS holds, not the ones the
    # shell exports. Gate 163's near-miss came from the repo `.env`, and
    # nothing from it is exported - so an `os.environ` scan finds zero
    # candidates and passes without checking anything. A proof with nothing to
    # look for is not a proof.
    secret_values: list[str] = []
    try:
        settings = get_settings()
        for holder in (
            settings.oidc_client_secret,
            settings.nf_session_signing_key,
        ):
            value = str(holder.get_secret_value() or "").strip()
            if len(value) >= 8:
                secret_values.append(value)
        for plain in (
            settings.oidc_issuer,
            settings.oidc_client_id,
            settings.oidc_audience,
        ):
            value = str(plain or "").strip()
            if len(value) >= 8:
                secret_values.append(value)
    except Exception as exc:  # noqa: BLE001
        detail.append(f"settings_secret_read:{type(exc).__name__}")

    # Membership only. No value is printed, logged or recorded anywhere.
    leaked = [value for value in secret_values if value in serialized]
    out["no_settings_secret_value_appears_in_the_audit"] = not leaked
    out["settings_secret_values_checked"] = len(secret_values)
    out["the_secret_scan_had_something_to_look_for"] = len(secret_values) > 0
    if leaked:
        # Count only. Naming which one would put it in the output.
        detail.append(f"{len(leaked)} configured secret value(s) appear in the audit")

    # And the exported environment too, for completeness.
    env_values = [
        value
        for key, value in os.environ.items()
        if any(
            word in key.upper()
            for word in ("SECRET", "TOKEN", "KEY", "PASSWORD", "CLIENT_ID")
        )
        and len(str(value).strip()) >= 8
    ]
    out["no_environment_secret_value_appears_in_the_audit"] = not [
        value for value in env_values if str(value) in serialized
    ]
    out["environment_secret_values_checked"] = len(env_values)

    # And nothing that looks like a credential field name carries a value.
    out["the_audit_carries_no_credential_fields"] = not any(
        word in serialized.lower()
        for word in ('"client_secret"', '"signing_key"', '"access_token"')
    )
except Exception as exc:  # noqa: BLE001 - the phase reports rather than raises
    detail.append(f"phase_error:{type(exc).__name__}:{exc}")
finally:
    socket.socket = _REAL_SOCKET  # type: ignore[assignment]

out["network_attempts_during_this_phase"] = network_attempts["count"]
out["no_network_during_tamper_and_guard"] = network_attempts["count"] == 0

for key in (
    "an_untouched_copy_still_verifies",
    "changed_raw_bytes_are_refused",
    "a_changed_payload_hash_is_refused",
    "a_changed_source_id_breaks_the_audit",
    "a_stripped_authorized_source_id_is_refused",
    "stripping_the_authorization_is_refused_by_the_schema",
    "a_changed_request_authority_is_refused",
    "a_missing_execution_proof_breaks_the_chain",
    "a_proof_that_names_other_bytes_is_refused",
    "a_backfilled_http_status_is_refused",
    "an_unexplained_absent_status_is_refused",
    "canonical_is_not_the_default",
    "canonical_refuses_ambient_secret_state",
    "the_flag_is_restored_after_a_refusal",
    "a_canonical_context_declares_itself",
    "an_explicit_environ_is_still_an_input",
    "environment_scoped_permits_what_it_exists_to_read",
    "an_environment_scoped_context_declares_itself",
    "a_contradictory_context_is_refused",
    "no_environment_secret_value_appears_in_the_audit",
    "no_settings_secret_value_appears_in_the_audit",
    "the_secret_scan_had_something_to_look_for",
    "the_audit_carries_no_credential_fields",
    "no_network_during_tamper_and_guard",
):
    out.setdefault(key, False)

# The real evidence must be exactly as it was.
out["detail"] = "; ".join(sorted(set(detail))) if detail else None
print(json.dumps(out, sort_keys=True))
