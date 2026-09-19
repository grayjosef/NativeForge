"""Gate 154D: the 27 recurring verifiers, what each is for, and what it owes.

## Two result vocabularies, and conflating them breaks the registry forever

```text
PASS / BLOCKED      a readiness lane. BLOCKED names what stops it.
PASS / FAIL         a stack or repository check. FAIL is a defect.
PASS / FAIL / SKIP  needs infrastructure that does not exist yet.
```

`scripts/verify_nativeforge_backup_restore.sh` is the third kind. It returns
`SKIP` because no managed PostgreSQL instance exists, and that is the CORRECT
answer, not a problem to be reported. A registry that expected `PASS` from
everything would report the production backup harness as broken forever, and an
operator would learn to ignore it.

So every entry carries `expected_result`, and Gate 154's health model reads a
result against it rather than against a universal `PASS`.

## Gate 61/65 and Gate 153 are different lanes and stay different

```text
backup_restore             production_backup     SKIP, needs a provider
backup_restore_readiness   operational_durability PASS, runs today
```

Gate 153 built the second and did not move the first. They are adjacent in a
sorted listing and answer opposite questions, which is exactly how a reader
conflates them, so each entry says what the other is.

## This module runs nothing

No `subprocess`, no shell, no import of anything that shells out. It is a
deterministic description of what exists on disk. Something else decides
whether to run a verifier and reports what it said.

A registry that ran its own contents would turn a health read into a
forty-minute test suite, and a route into a remote code execution surface.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_readiness_verifier_registry_v1"

CONTROLLED_SCOPE = "controlled_dev_demo"

SCRIPT_DIR = "scripts"

#: What a verifier is expected to return when everything is correct.
EXPECT_PASS = "PASS"
EXPECT_SKIP = "SKIP"

#: What kind of question the verifier asks.
KIND_READINESS = "readiness_lane"
KIND_STACK = "stack_or_deployment"
KIND_REPO = "repository_hygiene"
KIND_PRODUCTION = "production_infrastructure"


def _verifier(
    name: str,
    *,
    lane: str,
    kind: str,
    gate: str,
    blocking: bool,
    expected: str = EXPECT_PASS,
    controlled_dev_demo_only: bool = True,
    production: bool = False,
    depends_on: tuple[str, ...] = (),
    note: str = "",
) -> dict[str, Any]:
    return {
        "verifier": name,
        "script": f"{SCRIPT_DIR}/verify_nativeforge_{name}.sh",
        "lane": lane,
        "kind": kind,
        "gate": gate,
        "blocking": blocking,
        "expected_result": expected,
        "controlled_dev_demo_only": controlled_dev_demo_only,
        "production": production,
        "depends_on": list(depends_on),
        "note": note,
    }


#: Every recurring verifier. Ordered by the lane it serves, not alphabetically,
#: because alphabetical order is what puts the two backup harnesses together.
VERIFIERS: tuple[dict[str, Any], ...] = (
    # ---- stack and deployment -------------------------------------------
    _verifier(
        "demo_live_stack",
        lane="live_stack",
        kind=KIND_STACK,
        gate="129",
        blocking=True,
        note="nothing else is meaningful if the stack is down",
    ),
    _verifier(
        "demo_deployment",
        lane="public_edge",
        kind=KIND_STACK,
        gate="36B",
        blocking=True,
        depends_on=("demo_live_stack",),
        note=(
            "run with --strict-public. It checks the build stamp TAG exists; it "
            "does not compare the stamped sha to HEAD, so a stamp from an older "
            "commit passes here - see the frontend_stamp component of the "
            "Gate 154 health model"
        ),
    ),
    _verifier(
        "oidc_mode_b",
        lane="auth_configuration",
        kind=KIND_STACK,
        gate="130",
        blocking=False,
    ),
    # ---- operational lanes ----------------------------------------------
    _verifier(
        "customer_auth_live",
        lane="customer_auth_live",
        kind=KIND_READINESS,
        gate="135",
        blocking=False,
        note="the lane is false; a human has to sign in as themselves",
    ),
    _verifier(
        "customer_persistence_live",
        lane="customer_persistence_live",
        kind=KIND_READINESS,
        gate="138",
        blocking=True,
    ),
    _verifier(
        "awarded_operational_tracking",
        lane="awarded_operational_tracking",
        kind=KIND_READINESS,
        gate="139",
        blocking=True,
        depends_on=("customer_persistence_live",),
    ),
    _verifier(
        "tenant_digest_operational",
        lane="tenant_digest_operational",
        kind=KIND_READINESS,
        gate="140",
        blocking=True,
    ),
    _verifier(
        "document_storage_readiness",
        lane="document_metadata_operational",
        kind=KIND_READINESS,
        gate="141",
        blocking=True,
        note="metadata only; no object store is configured and none is contacted",
    ),
    _verifier(
        "email_delivery_readiness",
        lane="email_delivery_readiness",
        kind=KIND_READINESS,
        gate="142",
        blocking=True,
        note="readiness, not delivery. email_delivery stays false",
    ),
    _verifier(
        "source_monitoring_preflight",
        lane="source_monitoring_preflight_ready",
        kind=KIND_READINESS,
        gate="143",
        blocking=True,
        note="preflight only. source_monitoring_live stays false",
    ),
    _verifier(
        "no_live_source_calls",
        lane="no_live_source_calls",
        kind=KIND_REPO,
        gate="143",
        blocking=True,
        note="a chokepoint scan; proves no code path can reach a live source",
    ),
    _verifier(
        "beta_onboarding_cockpit",
        lane="beta_onboarding_cockpit",
        kind=KIND_READINESS,
        gate="144",
        blocking=True,
        depends_on=("customer_persistence_live", "tenant_digest_operational"),
    ),
    _verifier(
        "controlled_beta_readiness",
        lane="controlled_beta_readiness",
        kind=KIND_READINESS,
        gate="145",
        blocking=True,
        depends_on=("beta_onboarding_cockpit",),
    ),
    _verifier(
        "customer_auth_second_person_event",
        lane="customer_auth_second_person_readiness",
        kind=KIND_READINESS,
        gate="146",
        blocking=True,
        note="readiness for an event only a second person can cause",
    ),
    _verifier(
        "verified_binding_approval_boundary",
        lane="verified_binding_approval_boundary",
        kind=KIND_READINESS,
        gate="147",
        blocking=True,
        note="verified_operational_binding stays false; it needs a signature",
    ),
    _verifier(
        "customer_data_boundary",
        lane="customer_data_write_guard_ready",
        kind=KIND_READINESS,
        gate="148",
        blocking=True,
    ),
    _verifier(
        "controlled_customer_pilot_activation_package",
        lane="pilot_activation_package_ready",
        kind=KIND_READINESS,
        gate="149",
        blocking=True,
        note=(
            "the package is ready; the pilot is NOT activated and no activation "
            "mechanism exists"
        ),
    ),
    _verifier(
        "customer_beta_reassessment",
        lane="customer_beta_reassessment",
        kind=KIND_READINESS,
        gate="150",
        blocking=True,
        depends_on=("controlled_beta_readiness",),
    ),
    # ---- operational durability, Gates 151-154 --------------------------
    _verifier(
        "tenant_digest_persistence",
        lane="tenant_digest_persistence_live",
        kind=KIND_READINESS,
        gate="151",
        blocking=True,
        depends_on=("tenant_digest_operational",),
    ),
    _verifier(
        "audit_replay_readiness",
        lane="audit_replay_ready",
        kind=KIND_READINESS,
        gate="152",
        blocking=True,
        depends_on=("tenant_digest_persistence",),
        note="legacy evidence gaps are REPORTED here, never backfilled",
    ),
    _verifier(
        "backup_restore_readiness",
        lane="operational_backup_restore_ready",
        kind=KIND_READINESS,
        gate="153",
        blocking=True,
        depends_on=("audit_replay_readiness",),
        note=(
            "the DATA path: export controlled dev/demo state, restore it into an "
            "isolated database, re-run the Gate 152 replay. NOT the production "
            "backup harness - that is `backup_restore`, which returns SKIP"
        ),
    ),
    _verifier(
        "operational_health_runbook",
        lane="operational_health_ready",
        kind=KIND_READINESS,
        gate="154",
        blocking=True,
        depends_on=("backup_restore_readiness",),
        note="this registry's own verifier",
    ),
    _verifier(
        "source_scheduler_runtime",
        lane="scheduler_runtime_ready",
        kind=KIND_READINESS,
        gate="156",
        blocking=True,
        depends_on=("no_live_source_calls", "source_monitoring_preflight"),
        note=(
            "a scheduler that evaluates every registry source and refuses "
            "every one. It does NOT clear "
            "`scheduler_component_absent:scheduler_runtime`, which is find_spec "
            "over eight third-party packages: installing one would clear the "
            "blocker without computing a single due date. "
            "source_monitoring_live stays false."
        ),
    ),
    _verifier(
        "source_worker_runtime",
        lane="worker_runtime_ready",
        kind=KIND_READINESS,
        gate="157",
        blocking=True,
        depends_on=("no_live_source_calls", "source_scheduler_runtime"),
        note=(
            "a worker that claims a job with an expiring lease, classifies why "
            "it refuses, and retries only genuine transient failures. It does "
            "NOT clear `scheduler_component_absent:background_worker`, which "
            "looks for a nativeforge.workers module or a console entry point; "
            "this gate adds a script. source_monitoring_live stays false."
        ),
    ),
    _verifier(
        "collection_job_store",
        lane="collection_job_store_ready",
        kind=KIND_READINESS,
        gate="158",
        blocking=True,
        depends_on=(
            "no_live_source_calls",
            "source_scheduler_runtime",
            "source_worker_runtime",
        ),
        note=(
            "queued collection work that survives a restart, proven by a "
            "SECOND python process reading rows the first committed and then "
            "exited. Enqueue is idempotent on a deterministic job id plus a "
            "unique index, so five cycles over three sources leave three rows. "
            "A transition to `completed` is refused by the repository - which "
            "has no execution proof parameter - and again by the database, "
            "checked with the repository bypassed. This verifier is what the "
            "health ROUTE defers to: proving durability needs a commit and a "
            "reconnect, so the route reports that lane red and names this "
            "script. source_monitoring_live stays false."
        ),
    ),
    _verifier(
        "source_orchestration_runtime",
        lane="orchestration_runtime_ready",
        kind=KIND_READINESS,
        gate="159",
        blocking=True,
        depends_on=(
            "no_live_source_calls",
            "source_scheduler_runtime",
            "source_worker_runtime",
            "collection_job_store",
        ),
        note=(
            "a loop that wakes on a cadence, takes exactly one slot at a time, "
            "and recovers the slots it missed while it was down. Cycle "
            "identity is deterministic over (version, cadence, slot) and is "
            "NOT Gate 158's job id. Ownership is atomic on a unique index: a "
            "live owner cannot be stolen from, an expired one is reclaimable, "
            "and a crashed slot reads as UNFINISHED rather than served - "
            "without which the reclaim path is unreachable, which is the "
            "defect this gate found in its own first draft. Catch-up is "
            "bounded and the dropped count is reported. The systemd unit is "
            "written and deliberately NOT enabled. source_monitoring_live "
            "stays false, and the cycle table's CHECK constraints refuse any "
            "row claiming a completion, a collector or a live call."
        ),
    ),
    _verifier(
        "source_authorization_boundary",
        lane="authorization_boundary_ready",
        kind=KIND_READINESS,
        gate="162",
        blocking=True,
        depends_on=(
            "no_live_source_calls",
            "source_scheduler_runtime",
            "source_worker_runtime",
            "collection_job_store",
            "source_orchestration_runtime",
            "source_raw_payload_persistence",
            "source_collector_execution_envelope",
        ),
        note=(
            "the live network guard's permitted branch, made reachable ONLY "
            "from recorded, attributable facts. Before this gate its ten "
            "status inputs had to be handed in by a caller, and eight of them "
            "had no record anywhere to come from - so the only way to reach "
            "allowed=true was to invent them. Gate 134F's rule was that an "
            "unreachable permitted branch makes a refusal unfalsifiable; the "
            "converse is worse, because a permitted branch reachable only by "
            "fabrication makes an approval unaccountable. Eleven facts now "
            "resolve from records through a resolver whose four parameters "
            "cannot assert anything, and a fact can fail in five "
            "distinguishable ways - denied, needs_review, missing, unknown, "
            "stale - because nobody decided and somebody decided against are "
            "opposite problems with the same effect on permission. Only a "
            "signed decision authorizes: a ready runtime, a registered "
            "source, an available adapter, a queued job and a hermetic "
            "execution proof are prerequisites and none is permission. Terms "
            "and source review persist in ONE table discriminated by "
            "decision_kind, because both are a human's answer with the same "
            "shape; activation composes nf_active_opportunity_sources rather "
            "than adding a second approval column; and no second activation "
            "system was created. The database refuses an approval without a "
            "signer, a time and an evidence fingerprint. A SYNTHETIC fixture "
            "under a reserved prefix reaches authorized=true with all eleven "
            "facts recorded, which is what makes every refusal falsifiable - "
            "and it still sits at live_fetch_not_opted_in, because "
            "authorization complete is not a permitted request. 177 real "
            "sources resolve, 171 terms-blocked, 6 human-review-blocked, 0 "
            "approved, 0 allowlisted. Four GET routes, zero mutation "
            "endpoints, no route that accepts a fact. live_source_calls stays "
            "0 and source_monitoring_live stays false."
        ),
    ),
    _verifier(
        "live_collection_audit_replay",
        lane="live_collection_audit_ready",
        kind=KIND_READINESS,
        gate="164",
        blocking=True,
        depends_on=(
            "source_authorization_boundary",
            "source_raw_payload_persistence",
            "source_collector_execution_envelope",
        ),
        note=(
            "the first real live collection, replayed from persisted evidence "
            "alone. A FRESH connection with the pool disposed - a pooled "
            "connection outlives close(), and reusing one would be the "
            "process-memory shortcut a restart proof exists to exclude - "
            "recovers 11131 exact bytes, recomputes the hash, and re-derives "
            "the normalized opportunity from those bytes. No network: every "
            "phase replaces socket.socket with one that raises and counts "
            "attempts, so zero is measured rather than read off the code. "
            "The audit COMPOSES six sections from rows that already exist "
            "rather than writing a second ledger, because two accounts of one "
            "event can disagree and the one that disagreed would not announce "
            "itself. Tampering runs against COPIES of the database file; "
            "migration 0050 means a stripped authorized_source_id has no "
            "representation at rest, which is stronger than detecting it. "
            "health_status is healthy_with_known_evidence_gap: the HTTP "
            "transport status was never captured because the Gate 163 runner "
            "read the wrong result field, and it is NOT backfilled from the "
            "application errorcode - a gap must be named or `known gap` "
            "becomes a way to pass while hiding anything. Canonical artifact "
            "generation refuses ambient credential-backed reads at "
            "auth_environment_overlay, the function that turns credential "
            "presence into a fact, so a developer .env cannot change a byte "
            "of committed evidence; the context is a ContextVar rather than "
            "thread-local because all 57 route modules are sync and run in a "
            "REUSED anyio worker threadpool. 71 artifact writers classified, "
            "0 unclassified, 0 unmeasured. The authorized collection count is "
            "REPORTED, never required to be 1: a second authorized source "
            "must raise it without failing this gate."
        ),
    ),
    _verifier(
        "source_collector_execution_envelope",
        lane="collector_execution_envelope_ready",
        kind=KIND_READINESS,
        gate="161",
        blocking=True,
        depends_on=(
            "no_live_source_calls",
            "source_scheduler_runtime",
            "source_worker_runtime",
            "collection_job_store",
            "source_orchestration_runtime",
            "source_raw_payload_persistence",
        ),
        note=(
            "the first gate whose code could in principle make an outbound "
            "source request, and it does not. The envelope composes "
            "orchestration, job, policy, request construction, transport "
            "boundary, Gate 160's payload store and an execution proof, "
            "against a REGISTERED FIXTURE. Live is refused four independent "
            "times - by the policy, by the transport boundary, by "
            "DISPATCHABLE_KINDS, and by migration 0047's CHECK constraints - "
            "and none of the four takes caller input, so a caller who "
            "satisfies the guard still reaches three further stops. The exact "
            "response bytes are hashed before any decoding. An attempt row is "
            "written for EVERY outcome including refusals, because a refusal "
            "and a timeout produce no payload and would otherwise leave no "
            "record they happened. A malformed body is persisted and is NOT a "
            "failure: parsing is a later gate's problem and discarding the "
            "bytes would lose the only copy. The proof defines seven "
            "requirements, each read from a record rather than passed as a "
            "verdict, and reports proves_the_envelope_works and "
            "proves_a_source_responded as two separate fields - a 404 "
            "satisfies all seven and completes nothing. The Gate 157 worker "
            "gained an OPT-IN hermetic handler behind seven conditions, each "
            "of which is exercised alone; the default handler is unchanged. "
            "No envelope module imports a network module, proved by parsing "
            "imports rather than by searching text, and the scan is shown to "
            "FAIL on an injected import. No route takes a URL - not as a "
            "parameter, not as a default, not as an allowlist - so there is no "
            "address a caller can name. jobs_completed, collectors_invoked, "
            "live_source_calls and network_calls stay 0, approved_source_count "
            "stays 0 against a registry of 177 KNOWN sources, and "
            "source_monitoring_live stays false."
        ),
    ),
    _verifier(
        "source_raw_payload_persistence",
        lane="raw_payload_persistence_ready",
        kind=KIND_READINESS,
        gate="160",
        blocking=True,
        depends_on=(
            "no_live_source_calls",
            "source_scheduler_runtime",
            "source_worker_runtime",
            "collection_job_store",
            "source_orchestration_runtime",
        ),
        note=(
            "a durable, size-capped, hash-verified landing zone for response "
            "bytes in controlled_dev_demo. Exact bytes round-trip, including "
            "non-UTF-8 bodies; the hash is verified on write AND on readback; "
            "a tampered body fails replay and NO bytes are returned. A retry "
            "is a separate attempt, so attempt 2 never overwrites attempt 1's "
            "evidence, and the same attempt offering different bytes is "
            "refused with both hashes named. Response headers are kept by an "
            "ALLOWLIST of header names - Authorization, Cookie, Set-Cookie and "
            "X-API-Key are refused, and so is any header nobody has "
            "classified. The URL is never stored, only a sha256 fingerprint, "
            "because query strings carry api keys. object_store_configured is "
            "measured from Gate 97C's own config and stays false: this lane is "
            "the dev/demo spine, NOT production raw payload storage. A stored "
            "payload is not a fetched payload, no execution proof is created, "
            "and source_monitoring_live stays false."
        ),
    ),
    _verifier(
        "operational_durability_reassessment",
        lane="operational_durability_reassessment",
        kind=KIND_READINESS,
        gate="155",
        blocking=True,
        depends_on=(
            "tenant_digest_persistence",
            "audit_replay_readiness",
            "backup_restore_readiness",
            "operational_health_runbook",
        ),
        note=(
            "the Gates 151-155 close. It RUNS the four block verifiers and the "
            "Gate 61/65 production backup harness rather than assuming their "
            "results, because a closeout that reported the block green while "
            "one of its own gates had regressed would be the whole failure "
            "mode of a closeout gate"
        ),
    ),
    # ---- repository hygiene ---------------------------------------------
    _verifier(
        "test_selection_coverage",
        lane="test_selection_coverage",
        kind=KIND_REPO,
        gate="coverage guard",
        blocking=True,
        note="each gate must extend GATE_K keywords and its critical node ids",
    ),
    _verifier(
        "demo_payload_determinism",
        lane="demo_payload_determinism",
        kind=KIND_REPO,
        gate="determinism guard",
        blocking=True,
        note="regenerate artifacts with the suite's environment before running",
    ),
    _verifier(
        "fixture_cleanliness",
        lane="fixture_cleanliness",
        kind=KIND_REPO,
        gate="fixture guard",
        blocking=True,
        note=(
            "readiness verifiers write fixture rows into the dev database. Row "
            "counts and legacy gap counts MOVE between runs; that is residue, "
            "not drift in a lane"
        ),
    ),
    _verifier(
        "rls_isolation",
        lane="rls_isolation",
        kind=KIND_REPO,
        gate="64",
        blocking=True,
    ),
    # ---- production infrastructure: expected to SKIP ---------------------
    _verifier(
        "postgres_rls",
        lane="production_postgres_rls",
        kind=KIND_PRODUCTION,
        gate="64",
        blocking=False,
        expected=EXPECT_SKIP,
        controlled_dev_demo_only=False,
        production=True,
        note="needs a managed PostgreSQL instance; SKIP is the correct answer",
    ),
    _verifier(
        "backup_restore",
        lane="production_backup_ready",
        kind=KIND_PRODUCTION,
        gate="61/65",
        blocking=False,
        expected=EXPECT_SKIP,
        controlled_dev_demo_only=False,
        production=True,
        note=(
            "the INFRASTRUCTURE path: pg_dump, PITR, an executed provider "
            "restore. Needs a managed instance, so SKIP is the correct answer "
            "and a PASS here would be a surprise. NOT Gate 153's "
            "`backup_restore_readiness`, which is the data path and returns PASS"
        ),
    ),
)

#: The pair a reader is most likely to conflate, named explicitly so a test can
#: assert they stay distinct.
BACKUP_LANE_SEPARATION: dict[str, Any] = {
    "production_harness": "backup_restore",
    "production_lane": "production_backup_ready",
    "production_expected_result": EXPECT_SKIP,
    "operational_harness": "backup_restore_readiness",
    "operational_lane": "operational_backup_restore_ready",
    "operational_expected_result": EXPECT_PASS,
    "why_they_are_different": (
        "one asks whether a provider can dump and restore a database and cannot "
        "run without a managed instance; the other asks whether this system can "
        "export its own controlled dev/demo state, reload it elsewhere and still "
        "pass the Gate 152 replay, and runs today"
    ),
    "gate_153_did_not_move_the_production_harness": True,
}


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def build_verifier_registry() -> dict[str, Any]:
    """The registry. Deterministic, and runs nothing."""
    entries = [dict(entry) for entry in VERIFIERS]
    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_SCOPE,
            "verifiers": entries,
            "verifier_count": len(entries),
            "verifier_names": sorted(entry["verifier"] for entry in entries),
            "blocking_count": sum(1 for entry in entries if entry["blocking"]),
            "expected_skip": sorted(
                entry["verifier"]
                for entry in entries
                if entry["expected_result"] == EXPECT_SKIP
            ),
            "production_verifiers": sorted(
                entry["verifier"] for entry in entries if entry["production"]
            ),
            "by_kind": {
                kind: sorted(
                    entry["verifier"] for entry in entries if entry["kind"] == kind
                )
                for kind in (KIND_READINESS, KIND_STACK, KIND_REPO, KIND_PRODUCTION)
            },
            "backup_lane_separation": dict(BACKUP_LANE_SEPARATION),
            "expected_result_is_per_verifier": (
                "a SKIP from the Gate 61/65 production backup harness is correct; "
                "a SKIP from a readiness verifier would be a finding. A registry "
                "that expected PASS from everything would report the production "
                "harness as broken forever"
            ),
            # Constants. A registry describes; it does not execute.
            "executes_verifiers": False,
            "shell_executed": False,
            "external_call_made": False,
        }
    )


def expected_result_for(name: str) -> str:
    """What this verifier is supposed to return. `PASS` for anything unknown."""
    for entry in VERIFIERS:
        if entry["verifier"] == str(name):
            return str(entry["expected_result"])
    return EXPECT_PASS


def verifier_expectations() -> dict[str, str]:
    """Every verifier's expected result, for the health model to read against."""
    return {
        str(entry["verifier"]): str(entry["expected_result"]) for entry in VERIFIERS
    }


def registry_invariant_failures(registry: dict[str, Any]) -> list[str]:
    """Refuse a registry that lost an entry, or merged the two backup lanes."""
    fails: list[str] = []

    entries = registry.get("verifiers") or []
    names = [entry.get("verifier") for entry in entries]

    if registry.get("verifier_count") != len(entries):
        fails.append("verifier_count_disagrees")
    if len(names) != len(set(names)):
        fails.append("a_verifier_is_listed_twice")

    for entry in entries:
        if not entry.get("lane"):
            fails.append(f"verifier_without_a_lane:{entry.get('verifier')}")
        if not entry.get("script", "").startswith(f"{SCRIPT_DIR}/"):
            fails.append(f"verifier_without_a_script_path:{entry.get('verifier')}")
        if entry.get("expected_result") not in (EXPECT_PASS, EXPECT_SKIP):
            fails.append(f"expected_result_outside_vocabulary:{entry.get('verifier')}")
        for dependency in entry.get("depends_on") or []:
            if dependency not in names:
                fails.append(
                    f"depends_on_a_verifier_not_in_the_registry:"
                    f"{entry.get('verifier')}->{dependency}"
                )

    # The separation that must survive every future edit.
    separation = registry.get("backup_lane_separation") or {}
    production = separation.get("production_harness")
    operational = separation.get("operational_harness")
    if production == operational:
        fails.append("the_two_backup_harnesses_were_merged")
    if separation.get("production_expected_result") != EXPECT_SKIP:
        fails.append("production_backup_harness_no_longer_expects_skip")
    if separation.get("operational_expected_result") != EXPECT_PASS:
        fails.append("operational_backup_harness_no_longer_expects_pass")

    by_name = {entry.get("verifier"): entry for entry in entries}
    if by_name.get("backup_restore", {}).get("expected_result") != EXPECT_SKIP:
        fails.append("gate_61_65_backup_harness_expects_something_other_than_skip")
    if by_name.get("backup_restore", {}).get("lane") == by_name.get(
        "backup_restore_readiness", {}
    ).get("lane"):
        fails.append("the_two_backup_verifiers_share_a_lane")

    if registry.get("executes_verifiers") or registry.get("shell_executed"):
        fails.append("registry_claimed_to_have_executed_something")

    return sorted(set(fails))
