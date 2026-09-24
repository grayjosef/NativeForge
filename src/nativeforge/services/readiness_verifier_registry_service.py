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
        "source_authority",
        lane="source_authority_data_derived",
        kind=KIND_READINESS,
        gate="166",
        blocking=True,
        depends_on=(
            "source_authorization_boundary",
            "live_collection_audit_replay",
        ),
        note=(
            "source authorization stopped being a source-code allowlist. "
            "AUTHORIZED_SOURCE_IDS - one frozenset naming Grants.gov - is "
            "gone, and authority derives from the signed rows in "
            "nf_source_authorization_decisions and "
            "nf_active_opportunity_sources that already existed; migration "
            "0048 makes an unsigned approved decision unwritable, so the "
            "constant was restating a database guarantee where nobody could "
            "audit it. Proven by negative control, because one positive case "
            "cannot tell enforcement from deletion: the SAME source id with "
            "its opt-in withdrawn is refused, and a DIFFERENT id that appears "
            "nowhere in the codebase reaches live_opted_in on its records "
            "alone - which is the factory unlock. A real catalog row "
            "(nf-seed-2026-fed-001) refuses at state 'registered', so "
            "presence in the CSV is not authorization. retired is evaluated "
            "before the ladder and wins outright, because a disabled source "
            "with four signed decisions is disabled. Fleet facts are hoisted "
            "into an explicitly-scoped ContextVar: Gate 165 measured ~70% of "
            "a 332ms authorization as fleet-wide work with no source_id, "
            "recomputed per source, and a sweep now computes each fleet fact "
            "exactly ONCE - 2 computations at 10, 100, 1,000 and 5,000 "
            "sources, 5,000 evaluated in 175ms, 9,998 computations avoided. "
            "It is not a cache: with no scope open every call computes, and a "
            "scope opened for another organization is bypassed rather than "
            "answered from. The genericity scan classifies by AST node - a "
            "publisher named inside an adapter-keyed descriptor is the "
            "architecture working, an import or a branch is a leak - and "
            "found a real one: the generic resolver verified every source's "
            "attribution against the verbatim Grants.gov notice, so source "
            "#2's correct notice would have been rejected and no signed "
            "decision could have fixed it. generic_layer_leaks=0. The "
            "authorized source count is REPORTED, never asserted: a verifier "
            "requiring 1 would have to be edited to permit what this gate "
            "was built to allow."
        ),
    ),
    _verifier(
        "canonical_opportunity_store",
        lane="canonical_graph_ready",
        kind=KIND_READINESS,
        gate="167",
        blocking=True,
        depends_on=(
            "source_authority",
            "live_collection_audit_replay",
            "source_raw_payload_persistence",
        ),
        note=(
            "the substrate stopped merely proving where a byte came from. The "
            "Gate 163 payload is replayed from the store, parsed by the "
            "adapter's declared parser and persisted as a canonical "
            "opportunity - L1:OBJA2026172662|synopsis, ten provenance rows, "
            "every one naming the payload sha256. Four tables, because "
            "CanonicalOpportunity, SourceObservation, OpportunityVersion and "
            "FieldProvenance are four different things; nf_grant_sparks is "
            "what collapsing them looks like, 50 columns per organization. "
            "NONE of the four carries organization_id, which the verifier "
            "reads from the live schema rather than trusting a comment: the "
            "other fifteen opportunity-shaped tables are tenant-scoped, and a "
            "shared federal opportunity stored per tenant multiplies the "
            "world by the customer count. Evidence is required at write time "
            "rather than audited after - CHECK(length(raw_payload_sha256) = "
            "64) means a field value tracing to nothing has no representation "
            "at rest - and CHECK(identity_layer <> 'L4' OR is_provisional = "
            "1) makes fuzzy identity unable to present itself as settled. "
            "Every identifier is DERIVED from evidence, so replaying the same "
            "payload writes nothing and a full rebuild inside a copied "
            "database reproduces the identical canonical, version, "
            "observation and all ten provenance ids. Two sources disagreeing "
            "about a deadline produces two provenance rows sharing a conflict "
            "group and no winner; the disputed value does not become "
            "canonical by arriving second. Forecast and synopsis stay "
            "distinct canonical rows - merging them would destroy the "
            "forecasted-to-posted transition - joined by "
            "opportunity_number_group. 5,000 opportunities and 7,508 "
            "observations in a throwaway copy: every probed lookup uses an "
            "index at 0.06-0.17ms, and writes are 14.7/second at 49 SQL "
            "statements per observation, which is REPORTED as the gate's main "
            "limitation rather than dressed up. The canonical opportunity "
            "count is reported, never asserted."
        ),
    ),
    _verifier(
        "canonical_write_scale",
        lane="canonical_write_path_ready",
        kind=KIND_READINESS,
        gate="168",
        blocking=True,
        depends_on=("canonical_opportunity_store",),
        note=(
            "Gate 167's writer was correct at 49 SQL statements per "
            "observation. Profiling attributed 41 of them to provenance: a "
            "probe, a demote, a conflict read and an insert, once per field, "
            "per observation - 4.1 statements per field. The batch writer "
            "folds that into RESOLVE / DECIDE / APPLY: set queries for "
            "everything the chunk could collide with, the decisions made in "
            "memory in deterministic order because version lineage is a "
            "chain a set operation cannot order, then bulk inserts. A first "
            "observation is now 11 statements, an idempotent replay 4, and "
            "statements per field fell to 0.3. At 50,000 observations the "
            "path issues 1.16 statements each - essentially constant, which "
            "is the O(observations) target measured rather than asserted. "
            "Nothing in the evidence model changed: same provenance row per "
            "field, same payload hash, same conflict metadata, and the Gate "
            "167 verifier's semantics are re-proven after the rewrite. "
            "record_observation now delegates to the batch path with a batch "
            "of one, so there is one write path rather than two that drift. "
            "Atomicity is proven across six failure shapes including a real "
            "mid-chunk interruption - the first version of that test patched "
            "a function the fixture never called and reported a clean "
            "rollback of nothing. Memory is bounded by the batch, not the "
            "input: the API consumes an iterable and per-record reporting is "
            "opt-out, which took peak memory at 50,000 from 713MB to 103MB. "
            "Every technique is DATABASE_AGNOSTIC - no PRAGMA, no ON "
            "CONFLICT, no RETURNING - because derived primary keys mean no "
            "round trip is needed to learn a key. SQLite serializes writers, "
            "so concurrency is proven under interleaving and NOT under real "
            "row-level contention, which is reported UNKNOWN. Throughput "
            "numbers are INFO: pinning one would make a slower machine a "
            "test failure."
        ),
    ),
    _verifier(
        "cross_source_identity",
        lane="identity_resolution_ready",
        kind=KIND_READINESS,
        gate="169",
        blocking=True,
        depends_on=("canonical_opportunity_store", "canonical_write_scale"),
        note=(
            "the graph can now tell when many sources describe one "
            "opportunity, and refuse when they merely look alike. Twelve "
            "decision cases, each asserted individually because a summary "
            "boolean would let one regression hide behind eleven passes. The "
            "strongest guard is the simplest: two different published "
            "opportunity numbers mean two different solicitations, which "
            "refuses same-agency, same-program and same-deadline lookalikes "
            "before any title comparison runs. Annual recurrences are the "
            "trap - FY26 and FY27 share their title almost word for word - so "
            "the fiscal year is extracted BEFORE comparison and a year "
            "difference converts any same-title finding into RECURRENCE_OF, a "
            "real relationship and explicitly not a merge. A merge is a "
            "SAME_AS ROW, never a rewrite: both opportunities keep every "
            "observation, version and provenance row, so reversing an "
            "incorrect merge is deleting a row and the counts are identical "
            "before, during and after - reversibility is structural rather "
            "than a feature. Migration 0054 makes a fuzzy SAME_AS nobody "
            "reviewed unrepresentable at rest, and the attempt is proven "
            "refused. Candidate generation is an indexed key lookup, and the "
            "keys that generate candidates are restricted to the selective "
            "ones: funder_and_period measured 25/125/201 candidates at "
            "1k/5k/10k and title_band 4/20/40, so both are written for "
            "reporting but never walked per observation. That costs recall on "
            "the weakest L4 shape and the trade is named rather than hidden. "
            "Mean candidates then stay flat at 1.1/1.1/1.6 across a 10x "
            "graph at 2 SQL statements per lookup. Cross-source identity "
            "costs exactly one statement per NEW opportunity - 11 to 12 - not "
            "one per field or per observation."
        ),
    ),
    _verifier(
        "change_intelligence",
        lane="change_intelligence_ready",
        kind=KIND_READINESS,
        gate="170",
        blocking=True,
        depends_on=("canonical_opportunity_store", "cross_source_identity"),
        note=(
            "the graph can now say what changed, how much it matters and which "
            "source proves it. No second diff: Gate 168's comparison stays the "
            "only comparison, and this types what it found. Direction is the "
            "point - DEADLINE_SHORTENED is CRITICAL and DEADLINE_EXTENDED is "
            "MATERIAL, because a Tribe that planned around the old date needs "
            "the first immediately and the second can wait for a digest; one "
            "DEADLINE_CHANGED type would force both into the same alert and "
            "guarantee one is wrong. Every classification carries the named "
            "rule that produced it, and migration 0055 refuses to store a "
            "non-UNKNOWN materiality without one: CRITICAL is not reviewable, "
            "CRITICAL because deadline_shortened is. The asymmetries are "
            "deliberate - losing eligibility outranks gaining it, losing a "
            "document outranks adding one. A first sighting is NON_MATERIAL, "
            "because firing an amendment alert on discovery is the wrong "
            "signal to the wrong audience. Corroboration is AGREEMENT, not a "
            "repeated transition: two sources never share a version pair "
            "(their record ids differ) and with a shared version chain the "
            "second source to see a change produces no diff at all, so a "
            "source carrying the new value confirms the change - one event "
            "with a count of two rather than one alert per source. Conflicts "
            "are a row with a duration: first_detected_at is never rewritten, "
            "so 'these sources have disagreed for eleven days' is answerable, "
            "and resolving one field leaves another contested. The unchanged "
            "case is the one that matters at fleet scale: 0.016 statements per "
            "observation and 1830/sec against 1.53 and 443/sec for changed. "
            "50,001 observations, 111,009 events, every lookup index-backed "
            "between 0.11 and 0.23ms. The first cut of corroboration issued "
            "one UPDATE per event - 4,291 statements in a 1,500-observation "
            "chunk - which put Gate 168's per-field N+1 back and drove "
            "statements per observation from 1.16 to 4.03. Nothing in this "
            "gate's own validation caught it: Gate 168's no_per_field_select "
            "check did, in the back-to-back battery. Batched, it is three "
            "statements, and change intelligence now costs about 0.01 "
            "statements per observation. Throughput is a different story and "
            "is not restored - 559/sec to 256/sec at 50k, 30.9x over the Gate "
            "167 baseline where Gate 168 reported ~86x - because every "
            "observation now also writes about six indexed change-event rows "
            "and two blocking-key rows. How much of that is rows and how much "
            "is machine variance is UNKNOWN and is not attributed. Rebuild "
            "from evidence reproduces identical event "
            "ids, types, materiality and shapes; Gate 169's human identity "
            "decisions replay from storage rather than being recomputed. The "
            "customer read model is an allowlist - a denylist is a list of "
            "things somebody remembered - and withholds the rule NAME while "
            "showing the explanation. Nothing is delivered: notifications_sent "
            "is 0 and delivery is not built in this gate."
        ),
    ),
    _verifier(
        # The script path is DERIVED from this name, and Gate 171 names the
        # file, so the entry matches the file rather than the file being
        # renamed to suit a registry convention.
        "real_multisource_gate171",
        lane="real_multisource_ready",
        kind=KIND_READINESS,
        gate="171",
        blocking=True,
        depends_on=(
            "canonical_opportunity_store",
            "cross_source_identity",
            "change_intelligence",
        ),
        note=(
            "three heterogeneous REAL source families now flow through one "
            "fabric: Grants.gov's structured API, a BIA HTML program page and "
            "the Federal Register JSON API. Five live requests total, all "
            "operator-approved, and none after the live phase. 21 real "
            "observations - 1 document, 20 API - all NEW_CANONICAL, with "
            "independent field provenance per source (10 / 4 / 8 fields) and "
            "135 FIRST_OBSERVED change events, because a first sighting is "
            "not an amendment. REAL_OVERLAP_OBSERVED is FALSE and was not "
            "hunted: convergence, conflicts and corroboration stay "
            "structurally proven on source-shaped fixtures, and will be "
            "observed naturally as the fleet grows. The identity LAYER is "
            "chosen from what a source publishes - the API source is L1, the "
            "program page is L4 provisional - which is how this gate found "
            "the defect that matters. Gate 167's unique index on "
            "(normalized_opportunity_number, doc_type) permitted exactly ONE "
            "provisional opportunity in the entire graph, because every L4 "
            "row stores an empty number and doc_type 'unknown'. The real BIA "
            "page took the slot and the next document-shaped record was an "
            "IntegrityError that rolled back its whole batch. Migration 0056 "
            "makes the index partial so uniqueness applies to a PUBLISHED "
            "identity; L1's guarantee is unchanged and provisional records "
            "still cannot machine-settle. Replay from persisted bytes "
            "reproduces identical hashes, identities and provenance with the "
            "graph unchanged and zero network. BIA's robots response BODY was "
            "not retained - status, byte count, sha256 and verdict are on "
            "file - so its health is degraded with the gap NAMED rather than "
            "hidden behind an authorized boolean. Generic layers stay "
            "source-blind: 0 leaks, 0 identity branches, scanner proven "
            "falsifiable. Mixed-fleet scale, all three shapes interleaved: "
            "6,000 attempted, 6,000 LANDED, 0 rolled back, 1.04 statements "
            "per landed observation at 443/sec - landed counts are asserted "
            "because this gate reported 3,490/sec for a run where every batch "
            "rolled back and nothing was written."
        ),
    ),
    _verifier(
        # The script path is DERIVED from this name, and Gate 172 names the
        # file, so the entry matches the file rather than the file being
        # renamed to suit a registry convention.
        "source_fleet_health_gate172",
        lane="source_fleet_operations_ready",
        kind=KIND_READINESS,
        gate="172",
        blocking=True,
        depends_on=(
            "real_multisource_gate171",
            "source_scheduler_runtime",
            "source_worker_runtime",
            "collection_job_store",
        ),
        note=(
            "the operating system for the source fleet. Three sources can be "
            "watched by a person; five thousand cannot, and a fleet that size "
            "does not fail loudly - it fails in one dimension, on one source, "
            "while the dashboard stays green. A source's state is DERIVED "
            "from eleven independent dimensions, each owned by exactly one "
            "layer, and degrading any one leaves the other ten untouched, "
            "because which part is broken is the only thing an operator "
            "needs. Unmeasured defaults to UNKNOWN rather than healthy, and "
            "operator intent outranks measurement: a disabled source with "
            "eleven failed dimensions is DISABLED, and a source that asked us "
            "to slow down is RATE_LIMITED, not FAILING. The defect this gate "
            "existed to find: the read model could not tell an authorization "
            "REFUSED from an authorization not yet measured, so a revoked "
            "source classified as FAILING with transport still permitted - a "
            "source we had been told to stop collecting from, still allowed "
            "to collect. Three answers, not two. Five success levels, because "
            "a 200 is not intelligence and collapsing them is how a source "
            "that has silently returned nothing for six weeks keeps reporting "
            "itself healthy; freshness comes from five distinct timestamps "
            "against this source's own cadence, where never-collected is not "
            "stale, an unscheduled cadence carries no SLA, and a punctual "
            "source can still be stale. Breaking schema drift asks for a "
            "human - an adapter is never rewritten automatically, because a "
            "parser that silently adapts to an unreviewed change writes "
            "plausible wrong records into the canonical store, which is worse "
            "than a stopped source because it is trusted. Migration 0058 adds "
            "durable operations events and operator alerts with a CHECK that "
            "makes an event which is not a transition unrepresentable: three "
            "identical sweeps write ONE event and advance a counter, and "
            "DEGRADED, UNKNOWN and RETIRED never page anyone. Proven at 5,000 "
            "sources - population 50x, sweep time 33x, statements per source "
            "FALLING with scale because fleet globals are hoisted once per "
            "sweep. The access-path rule is selectivity-aware on purpose: "
            "sources_due returns the whole population so a scan is correct "
            "there, named as an exemption rather than quietly dropped, and "
            "every selective query is index-backed at 100, 1,000 and 5,000. "
            "Zero network requests, asserted by counting refused sockets; no "
            "sources added, no activations, nothing delivered. Gate 171's "
            "root cause remains UNKNOWN - this gate re-measures the "
            "regression and does not claim the cause was found. Four of its "
            "permanent regressions test the INSTRUMENTS, because four "
            "measurements here were wrong while the system was right: the "
            "failure matrix went green without exercising a branch, the "
            "fairness simulation could not show starvation, and the index "
            "audit omitted organization_id and compared str(UUID) against a "
            "column stored as 32 hex characters, returning zero rows while "
            "printing query plans."
        ),
    ),
    _verifier(
        # The script path is DERIVED from this name, and Gate 173 names the
        # file, so the entry matches the file rather than the file being
        # renamed to suit a registry convention.
        "native_relevance_gate173",
        lane="native_relevance_ready",
        kind=KIND_READINESS,
        gate="173",
        blocking=True,
        depends_on=(
            "source_fleet_health_gate172",
            "real_multisource_gate171",
            "canonical_opportunity_store",
            "cross_source_identity",
        ),
        note=(
            "Native relevance stops being a keyword search. The product "
            "principle this gate enforces is that a highly Native-relevant "
            "opportunity frequently uses no Native language at all: a "
            "Grants.gov record coded 99 UNRESTRICTED says nothing and is open "
            "to every Tribe in the country, and a broadband program open to "
            "'units of general local government and Indian tribes' says the "
            "word once, in a list, on page 14 of an attachment. Twelve of the "
            "thirteen candidate signals never look at a word - applicant "
            "codes, general-government eligibility, geography, beneficiaries, "
            "statutory authority, prior awards, program history, sector, "
            "source context and document evidence. The survey found the fact "
            "that decided the gate's shape: a real Stage 6 relevance stack "
            "already existed - eight labels, a deterministic evaluator, "
            "confidence bands, review triggers, two guards - and NOT ONE of "
            "its ten modules could reach a canonical opportunity. All of it "
            "sees fixture dictionaries. So this gate binds relevance to the "
            "Gate 167 graph rather than building a second engine, reusing the "
            "applicant-code classifier that already knew an absent code is "
            "not a negative finding. Eight relevance classes, never collapsed "
            "into one score, because a score cannot be reviewed: durable "
            "truth is classification plus evidence plus reason plus "
            "uncertainty. Twelve evidence types, each bound to the payload "
            "sha256 it was read from - a human assertion may have no payload "
            "because a person is the origin, and nothing else may. UNCERTAIN "
            "is a real answer that routes to a person, not a soft "
            "NOT_RELEVANT, and NOT_CANDIDATE is a FINDING that has to be "
            "earned: with no signal and no stated eligibility the answer is "
            "UNKNOWN, because 'we have not looked' and 'we looked and it is "
            "not relevant' are different facts. An inference cannot drop an "
            "opportunity at the high-recall stage, where a false negative is "
            "unrecoverable. The 27-row adversarial corpus - 9 hard negatives "
            "including Indian River County, native prairie species, and a "
            "Tribal grantee named only in a background paragraph - feeds RAW "
            "INPUTS into the real classifier and states no answers; it caught "
            "three defects on its first run, including a "
            "BROADLY_ELIGIBLE_NATIVE_RELEVANT class that was unreachable from "
            "the entity-class ambiguity that defines it. Candidate recall is "
            "1.0 with zero false negatives at the irreversible stage, and "
            "because a corpus written beside its model proves only internal "
            "consistency, what is ASSERTED is falsifiability: a keyword-only "
            "baseline scores 0.52 on the same rows against the real model's "
            "1.0. Projecting the 22 real canonical opportunities through the "
            "layer puts ZERO of them in the applicant band, because the real "
            "graph carries no eligibility field at all - that is reported as "
            "the finding it is, and it is what Gates 174 and 175 exist to "
            "change. Coverage models publishers by family and state and "
            "REFUSES to claim completeness because the denominator is "
            "unknown; a discovered publisher stops at "
            "DISCOVERED_PENDING_REVIEW and migration 0059 makes it "
            "structurally impossible for one to already have a source "
            "attached, keeping the Gate 162-171 authorization boundary "
            "intact. Relevance is GLOBAL: classifier calls are identical at 1 "
            "tenant and at 50, measured, so there is no opportunity-by-tenant "
            "sweep. 100,000 opportunities classify in 7.1s with per-"
            "opportunity cost flat, 50,000 rows write in 6 statements, and "
            "every selective query is index-backed. The genericity scan was "
            "extended from 16 files to 22 so that generic_layer_source_leaks "
            "= 0 actually covers the relevance engine, which is where a "
            "source-specific branch would do the most damage."
        ),
    ),
    _verifier(
        "eligibility_gate174",
        lane="eligibility_intelligence_ready",
        kind=KIND_READINESS,
        gate="174",
        blocking=True,
        depends_on=(
            "native_relevance_gate173",
            "source_fleet_health_gate172",
            "canonical_opportunity_store",
        ),
        note=(
            "eligibility stops being a boolean. The question an operator "
            "actually has is who can apply, under what conditions, what "
            "disqualifies them and what is unknown, and True/False carries "
            "none of it: True hides a matching-funds condition nobody can "
            "meet, False hides that the only blocker is a UEI that takes a "
            "week. So eligibility is a set of typed requirements - fifteen "
            "kinds - and a six-valued result. The survey found the same shape "
            "Gate 173 did, one layer deeper: a real Stage 7 stack exists, and "
            "not one module can reach a canonical opportunity. Worse, it "
            "consumes the STAGE 6 relevance preview, which Gate 173 "
            "established is itself unwired, so the whole eligibility-to-"
            "relevance chain floats free of the graph. The survey's own first "
            "run hid that: a `native_relevance_` prefix marker matched four "
            "Stage 7 modules importing the OLD unwired stack and reported "
            "them as spine-wired, because a naming convention is not a "
            "capability. Negative requirements are first class - a model "
            "storing only who MAY apply represents 'tribal governments are "
            "not eligible' as the ABSENCE of a tribal class from a list, "
            "byte-identical to 'nobody wrote the list down', and migration "
            "0060 gives a disqualifier its own polarity column so those are "
            "different rows. An exclusion ENDS the question rather than being "
            "outvoted: five satisfied requirements do not beat one "
            "disqualifier, and the CHECK makes an ELIGIBLE row with an "
            "applied exclusion unrepresentable. A failed STRUCTURAL "
            "requirement is INELIGIBLE and a failed ADDRESSABLE one is "
            "CONDITIONAL, because not being a Tribe cannot be fixed before "
            "the deadline and a missing registration can - collapsing them "
            "throws away the only actionable half of the answer. Entity "
            "classes are deny-by-default: naming 'Indian tribes' names a "
            "tribal government and NOT a tribal college, an enterprise or a "
            "Native nonprofit, because telling a Tribe otherwise costs them a "
            "cycle and their standing with the funder; only the source's own "
            "grouping language expands, and the lookup tolerates the spacing "
            "a source actually writes, which it did not at first. The "
            "organisation profile is three-valued and versioned from its "
            "content - UNANSWERED is never a no, and a match names the "
            "profile version it used, so yesterday's CONDITIONALLY_ELIGIBLE "
            "becomes an answer about a superseded profile rather than a wrong "
            "one. Gate 174 cannot verify authority: VERIFIED_BY_AUTHORITY is "
            "reserved for Gate 177 and the invariant refuses a profile that "
            "produces it here. The sixteen-row corpus feeds raw requirements "
            "and raw profiles into the real engine with zero false positives "
            "and zero false negatives, and because a corpus written beside "
            "its engine proves only internal consistency, what is ASSERTED is "
            "falsifiability: five planted breakages are each caught and a "
            "naive entity-class-blind engine scores 0.31 against the real "
            "engine's 1.0. 174K is measured, not claimed - the same "
            "opportunity normalizes ONCE at one tenant and at fifty while "
            "matches scale 1 to 50, and 2,000 normalizations serve 40,000 "
            "matches across 20 tenants, a 20x saving. Two tenants get "
            "DIFFERENT answers on the same opportunity, which is the point of "
            "separating global parsing from the per-tenant match. 50,000 "
            "opportunities evaluate with per-opportunity cost flat, 40,000 "
            "rows write in 2 statements, and every selective query is "
            "index-backed. The 0060 CHECK caught this gate's own scale "
            "fixture, which claimed CONDITIONALLY_ELIGIBLE on 20,000 rows "
            "while naming no condition."
        ),
    ),
    _verifier(
        "document_intelligence_gate175",
        lane="document_intelligence_ready",
        kind=KIND_READINESS,
        gate="175",
        blocking=True,
        depends_on=(
            "eligibility_gate174",
            "native_relevance_gate173",
            "source_fleet_health_gate172",
        ),
        note=(
            "the landing page is not the authoritative answer, and this gate "
            "stops NativeForge assuming it is. Eligibility lives on page 14 of "
            "an attachment, the match requirement lives in Appendix C, and the "
            "FAQ published a month later is what the programme officer will "
            "cite. The survey established the gap in one measurement: "
            "no_table_binds_a_document_to_a_canonical_opportunity. "
            "nf_award_documents exists and holds 876 ARCHIVED rows of "
            "financial_report and award_letter hanging off awarded_grant_id - "
            "post-award compliance artifacts, a different lifecycle stage, and "
            "filing a funder's eligibility language against a grant nobody has "
            "won would conflate the two permanently. So migration 0061 adds "
            "documents, facts and conflicts bound to the canonical "
            "opportunity. The rule the gate exists for is that a document we "
            "could not READ must never read as a document with nothing in it: "
            "UNSUPPORTED and PARTIAL can never carry absence_is_meaningful, "
            "because a scanned PDF reporting 'no requirements found' is "
            "byte-identical to a NOFO that genuinely imposes none. Identity is "
            "the CONTENT hash, so the same URL serving changed bytes is a new "
            "version and the same bytes at a second URL is the same document - "
            "an agency's mirror is not an amendment. Conflicts are "
            "REPRESENTED, never silently resolved: an amendment supersedes and "
            "the predecessor is retained, a notice outranks a landing-page "
            "summary, an FAQ CLARIFIES without erasing - both values survive "
            "and the pair goes to review - and anything else is UNRESOLVED and "
            "asks for a human. The CHECK makes a winner under a "
            "non-selecting rule unrepresentable. Every fact carries the "
            "document, the page and the funder's own quoted words, so a "
            "citation can be shown to anybody who disputes it; a citation past "
            "the document's last page is refused. Eight planted breakages are "
            "each caught by their SPECIFIC detector rather than by any failure "
            "at all - the cycle fixture uses equal ordinals so the ordinal "
            "rule cannot explain the result on its own. 10,000 opportunities "
            "carrying 60,000 documents and 120,000 facts process with "
            "per-opportunity cost flat, 65,000 rows write in 3 statements, and "
            "every selective query is index-backed. No document is downloaded: "
            "every byte is a synthetic fixture and the socket count is zero. "
            "The integrated 173-175 proof closes the chain on four cases, "
            "including the one the whole block exists for - a title with no "
            "Native word whose eligibility is on page 14, whose match "
            "requirement is in an appendix, and whose deadline moved by "
            "amendment - which a keyword filter never sees, a landing-page "
            "pipeline cannot answer, and a boolean eligibility model cannot "
            "express."
        ),
    ),
    _verifier(
        "early_signal_gate176",
        lane="early_signal_intelligence_ready",
        kind=KIND_READINESS,
        gate="176",
        blocking=True,
        depends_on=(
            "document_intelligence_gate175",
            "eligibility_gate174",
            "native_relevance_gate173",
            "source_fleet_health_gate172",
        ),
        note=(
            "by the time a NOFO is published, a Tribe with one grant writer "
            "has already lost weeks it did not have. This gate builds the two "
            "halves of seeing sooner: forward signals, which notice funding "
            "before the solicitation, and backward error detection, which "
            "notices what we missed after the award. The forward half is "
            "thirteen typed signal types across an eight-state lifecycle, and "
            "the load-bearing property is that a signal is EVIDENCE and never "
            "an opportunity: creates_opportunity and "
            "auto_onboarding_permitted are false on every row, in the Python "
            "and again as CHECK constraints in 0062, because a budget line "
            "that quietly became a funding opportunity would be a fabrication "
            "presented to a government. Linking requires an opportunity that "
            "ALREADY EXISTS; a link to an absent one is refused rather than "
            "created. Correlation PROPOSES - corroborates, likely precursor, "
            "possible same programme - and merges nothing; two traces that "
            "share only a funder reach UNRESOLVED rather than a convenient "
            "answer. The backward half starts from a measurement that is "
            "asserted FALSE and must stay false: "
            "real_award_evidence_available_for_miss_detection. All 2,757 "
            "award rows are Gate 138 demo fixtures on the protected demo "
            "organisation, none carries a source_opportunity_id, and the "
            "detector therefore has nothing real to detect against. Counting "
            "them would have reported 2,757 coverage failures made entirely "
            "of test data, so a miss carries the provenance of its award and "
            "the scorecard counts REAL and DEMO separately - enforced in the "
            "schema, where award_is_demo_fixture and "
            "counts_toward_real_metrics cannot both be true. The scorecard "
            "refuses to report a coverage PERCENTAGE at all: the denominator "
            "- how much Native-relevant funding exists - is unknown and this "
            "system has no way to learn it, so a percentage would be a number "
            "we made up and it would be believed. Recurrence rests on a "
            "decisive identity basis - assistance listing, programme number, "
            "stable path, authority - and never on title similarity, because "
            "a cadence derived from a name collision is worse than no "
            "cadence; a renamed programme keeps its history, a lookalike gets "
            "UNKNOWN and a review flag. Below three observed cycles nothing "
            "is forecast, in the model and again as a CHECK, because one "
            "observation plus an assumption looks exactly like intelligence "
            "until the year it is wrong. An absence signal cites the "
            "recurrence history that justifies it - absence has no payload "
            "bytes, and without that reference the gate's own evidence "
            "invariant refused it, which is how the defect was found. "
            "Twenty-one adversarial cases run against the real services, each "
            "pinning its own clock so the corpus cannot rot the way Gate "
            "172's verifier did; its recall and precision stay INFO, because "
            "they measure the cases we thought of and not the world. Ten "
            "self-health detectors each fire on a fixture broken in their OWN "
            "way and fire ALONE - the zero-history fixture had to be "
            "narrowed, because breaking two things at once proves neither. "
            "Eight access paths are index-backed at 120,000 historical "
            "instances, and the open-queue path exposed a real defect: an "
            "unordered LIMIT made a table scan genuinely optimal, so the "
            "QUERY was wrong, not the plan - a triage queue nobody can order "
            "is not a queue. The scan detector itself was wrong too, reading "
            "an ordered index walk as a full scan, and now proves it can "
            "still fire against a control query nothing can serve."
        ),
    ),
    _verifier(
        "tribal_onboarding_gate177",
        lane="tribal_onboarding_ready",
        kind=KIND_READINESS,
        gate="177",
        blocking=True,
        depends_on=(
            "early_signal_gate176",
            "document_intelligence_gate175",
            "eligibility_gate174",
        ),
        note=(
            "identity verified is not affiliation verified is not authority "
            "verified, and the survey found them collapsed: "
            "nf_authority_proof_records governed authority through a single "
            "`state` column naming two of the three dimensions, so verified "
            "could not say verified AS WHAT. That is not a modelling "
            "preference. A person with a working @tribe.gov mailbox has "
            "proven control of a mailbox; it says nothing about whether the "
            "Council has authorised them to establish a tenant, invite staff "
            "and represent a sovereign government to funders, and a system "
            "with one boolean will let an intern speak for a nation while "
            "looking, from the inside, exactly like success. So three states "
            "live in three columns, graded by three functions, and "
            "may_administer_tenant requires all three independently - with "
            "0063 making authority over SELF_ASSERTED affiliation "
            "unrepresentable rather than merely discouraged. Evidence is "
            "typed and plural because 574 federally recognised Tribes do not "
            "share one governance structure: demanding a council resolution "
            "would exclude organisations that never issue one, and accepting "
            "a matching email domain would accept anyone who can register a "
            "lookalike. ORGANIZATION_EMAIL_DOMAIN and OFFICIAL_TRIBAL_WEBSITE "
            "are therefore absent from ESTABLISHES_AUTHORITY in the model and "
            "refused by CHECK in the schema. Authority that nobody signed for "
            "cannot be stored. Evidence records a REFERENCE, never bytes and "
            "never a credential, and a field that looks like a secret is "
            "refused. The first four customers are onboarded by named "
            "controlling-company staff with a stated reason and an audit "
            "event, and no customer identity is hardcoded anywhere. "
            "CONTROLLING_COMPANY_ADMIN is not the top of the customer ladder, "
            "it is a different ladder: ASSIGNABLE_BY never lists a customer "
            "role as able to confer it, so there is no sequence of legitimate "
            "actions that reaches it, proven through three separate routes - "
            "the action, an invitation, and the function itself. Tenancy is "
            "checked BEFORE privilege, so a genuine administrator of one "
            "Tribe is refused at another before their role is even consulted. "
            "An unauthorised invitation is refused at ISSUE rather than "
            "filtered at acceptance, so it never exists to sit in somebody's "
            "inbox. Revocation removes authority and nothing else: not the "
            "organisation, not the historical work, not the audit trail, and "
            "not ordinary membership unless that is asked for separately. "
            "Organisations describe themselves in their own words, so phrase "
            "resolution keeps RECOGNIZED, AMBIGUOUS, LOOKUP_MISS and "
            "EXPLICITLY_EMPTY distinct - a Tribe writing 'language "
            "revitalization' must never be treated as though they left the "
            "field blank, and an ambiguous phrase keeps its candidates rather "
            "than discarding what we knew. A personal dashboard override "
            "deep-copies before merging and returns proof the organisation "
            "default is byte-identical afterwards, because 'we do not mutate' "
            "is exactly the kind of claim that quietly stops being true; the "
            "override table has no branding columns at all, so one person's "
            "taste has nowhere to become the Tribe's identity. Nine "
            "self-health detectors each fire on their OWN breakage and fire "
            "ALONE - the revoked-authority detector had to be rewritten "
            "because it asked may_administer_tenant and then re-read the "
            "fields that function already applies, so it could only ever "
            "agree with what it was checking; it now compares the revocation "
            "log against the grant row and catches the partial write. The "
            "measurement this gate turns on is FALSE and must stay false: "
            "real_organization_has_an_authorized_admin. The real organisation "
            "has zero active members and zero authority grants, so "
            "'organisation has no authorised administrator' is adversarial "
            "case 11 AND the live state of the real tenant."
        ),
    ),
    _verifier(
        "commercial_entitlements_gate178",
        lane="commercial_entitlements_ready",
        kind=KIND_READINESS,
        gate="178",
        blocking=True,
        depends_on=(
            "tribal_onboarding_gate177",
            "early_signal_gate176",
        ),
        note=(
            "this gate encodes an approved commercial model and designs "
            "nothing: a persistent organisational licence at $32,999 with the "
            "first twelve months of maintenance included, $4,999 a year "
            "after, benefits frozen when maintenance goes delinquent, the "
            "licence lost after three CONTINUOUS years, and relicensing at "
            "the current price with historical unpaid maintenance forgiven. "
            "docs/operations/570 carries different figures and says of itself "
            "that they are the operator's drafts recorded verbatim as drafts; "
            "the survey asserts none of them reached the code. The load-"
            "bearing separation is three states that most of the time agree "
            "and come apart exactly when it matters: LICENCE state, "
            "MAINTENANCE state and BENEFIT ACCESS. A delinquent organisation "
            "with a live 14-day extension has a held licence, a lapsed term "
            "and full benefits simultaneously, and a single is_active flag "
            "cannot say that - so a system with one will either deny a "
            "customer the extension somebody granted them or quietly forget "
            "they owe money. An extension therefore changes BENEFIT ACCESS "
            "and nothing else: it does not move the paid-through date, reduce "
            "the delinquency count, or pause the three-year clock, and the "
            "extension row RECORDS the delinquency it did not cure, enforced "
            "by a CHECK that refuses an extension claiming the customer was "
            "current. Getting that wrong generously is worse than getting it "
            "wrong harshly, because it is invisible until somebody reconciles "
            "and sends a Tribe a bill nobody told them was accruing. Expiry "
            "is strictly greater than 1095 days, so the boundary day itself "
            "still holds the licence, and the schema refuses an expired row "
            "at or below it - taking a licence away early is the most "
            "expensive arithmetic error this system can make. Frozen is not "
            "deleted and expired is not deleted: authentication, identity, "
            "account and licence status, history, the renewal path and "
            "EXPORT_OWN_DATA remain available in every state including years "
            "after expiry, because the difference between 'your workflows are "
            "paused' and 'we have your data' is the difference between a "
            "vendor and a hostage-taker. The ledger is append-only and "
            "relicensing appends a forgiveness event naming the amount - "
            "forgiven with no figure is not a record, it is a shrug - while "
            "every delinquency event stays exactly where it is, because "
            "forgiving a debt is a decision about what is owed and not a "
            "claim that it never existed. Corrections are events, never "
            "edits. No customer role, including ORG_SUPER_ADMIN, may forgive "
            "debt, move a paid-through date, grant an extension, correct the "
            "ledger or relicense itself, though every role may always SEE its "
            "own standing. Money is integer cents throughout and time is "
            "always supplied, never read from a clock, because 178E names "
            "clock fixture ambiguity as a reason a licence must not expire. "
            "Twenty adversarial cases run against the real services, each "
            "pinning its own clock, including the same instant written three "
            "ways. Nine self-health detectors each fire on their OWN breakage "
            "and fire ALONE, and the ledger-disagreement detector compares "
            "two INDEPENDENT sources - the served entitlement against a fresh "
            "derivation - rather than asking the same function twice, which "
            "is the mistake Gate 177 had to repair. Eight read paths are "
            "index-backed across 5,000 organisations, 30,000 ledger events "
            "and 8,000 extensions, with fleet questions answered from the "
            "materialised summary rather than by replaying thousands of "
            "histories; the zero-row rule caught a scale fixture whose "
            "maintenance terms all ended after the cutoff, making the "
            "expiring-maintenance queue return nothing and look beautifully "
            "indexed. No money moved, no invoice was raised, and the exact "
            "legal wording remains with counsel."
        ),
    ),
    _verifier(
        "customer_scale_gate179",
        lane="customer_experience_ready",
        kind=KIND_READINESS,
        gate="179",
        blocking=True,
        depends_on=(
            "commercial_entitlements_gate178",
            "tribal_onboarding_gate177",
            "early_signal_gate176",
        ),
        note=(
            "the survey found the thing this gate exists to fix: "
            "buyer_feed_depends_on_hand_made_sparks was TRUE, "
            "api_imports_canonical_intelligence was FALSE, and "
            "canonical_opportunity_store_service - the spine of gates 167 "
            "through 175 - had no importer at all. Nine gates of proven "
            "intelligence and not one of them reached a buyer; seven "
            "customer-facing route modules referenced demo fixtures instead. "
            "A workspace built on hand-made sparks demonstrates beautifully "
            "and tells you nothing about whether the intelligence works. So "
            "recommendations are now assembled from the canonical record and "
            "a recommendation with no canonical_id is refused by two "
            "independent invariants. Every recommendation must answer four "
            "questions - why Native-relevant, why eligible or uncertain, what "
            "evidence, what remains unknown - and a decisive relevance claim "
            "citing no evidence is refused, as is a CONDITIONAL eligibility "
            "that does not NAME its condition and an APPEARS_INELIGIBLE that "
            "does not name its blocker. UNKNOWN survives to the surface: "
            "ELIGIBILITY_UNCERTAIN and NOT_ASSESSED are distinct, and "
            "uncertainty that failed to reach known_unknowns is a failure, "
            "because a system that hides its uncertainty is not more useful, "
            "it is more confident about the wrong things. Ordering is a named "
            "criterion the customer can change, never an opaque score. "
            "Watch, dismiss and pursue are durable decisions naming an actor "
            "and a time - the survey found 457 watchlist rows and 124 "
            "suppressions recording neither - with history appended rather "
            "than overwritten, every state reversible, and dismissal scoped "
            "to ONE tenant: a dismissal that deleted intelligence would let "
            "one person's tidy-up remove a funding opportunity from every "
            "Tribe in the product. Customer and operator capabilities are "
            "disjoint SETS rather than a UI convention, and the refusal walks "
            "the whole payload, so an internal field cannot reach a customer "
            "by being nested inside a serialiser somebody forgot to filter. "
            "The 1,000-source rehearsal runs 1,200 synthetic sources across "
            "twelve publisher kinds and nine health states, refuses to "
            "collect from 666 of them on state, and distributes leases fairly "
            "across 24 workers. The catastrophe 179J names is measured rather "
            "than assumed absent: opportunity x tenant x document would be "
            "30,000,000 units, the actual work is 180,000, and global "
            "intelligence is computed once per opportunity rather than once "
            "per tenant - a 166x difference that looks fine in development "
            "with four tenants. Five customer read paths are index-backed "
            "across 10,000 decisions, and the zero-row rule caught a fixture "
            "that never produced the org+opportunity pair the read-path "
            "contract names. Two things this gate reports rather than claims: "
            "claims_real_thousand_source_coverage is FALSE - NativeForge "
            "monitors 40 real sources and 3 active ones, and this is "
            "architecture rehearsal - and postgres_concurrency_status is "
            "UNKNOWN_NOT_MEASURED, because SQLite proves single-writer "
            "serialisation and index selection and proves nothing about "
            "Postgres row-level locking. The demo story runs only on the "
            "protected demo organisation, refuses the real one in every "
            "spelling, and is byte-deterministic. The UX smoke checklist for "
            "Claude Design arrives with every result NOT_YET_WALKED, because "
            "Claude Code has not navigated a UI and a checklist pre-marked "
            "PASS would answer the question it exists to ask."
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
