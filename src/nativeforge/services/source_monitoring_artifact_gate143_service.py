"""Gate 143H: what source monitoring preflight proved, as committed files.

Deterministic and hermetic: every measurement here reads files and classifies
rows. No socket is opened, no source is fetched, no robots.txt is read, no DNS
is resolved and no collector is started.

Every artifact is scanned for credential-shaped markers before it is returned.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.services.source_collector_configuration_preflight_service import (
    ATTRIBUTION_NEEDING_VERBATIM,
    LIVE_CAPABLE_PAYLOAD_POLICIES,
    REQUIRED_CONFIG_KEYS,
    build_collector_preflight,
    collector_preflight_invariant_failures,
)
from nativeforge.services.source_collector_configuration_preflight_service import (
    PREFLIGHT_STATES as COLLECTOR_STATES,
)
from nativeforge.services.source_monitoring_approved_source_service import (
    CREDENTIAL_REQUIRED_DOMAINS,
    EVALUATION_STATES,
    FIXTURE_SOURCE_PREFIX,
    HUMAN_REVIEW_DOMAINS,
    allowlist_invariant_failures,
    evaluate_registry,
    evaluate_source,
)
from nativeforge.services.source_monitoring_readiness_service import (
    MONITORING_MODULES,
    NOT_APPROVED,
    READINESS_ROUTE_MODULE,
    build_source_monitoring_readiness,
    detect_network_imports,
    detect_readiness_route_module,
    source_monitoring_readiness_invariant_failures,
)

SCHEMA_VERSION = "nf_source_monitoring_gate143_artifact_v1"

ARTIFACT_DIR = "artifacts/source_monitoring_gate143"

ARTIFACT_FILES: tuple[str, ...] = (
    "source_monitoring_survey.json",
    "approved_source_allowlist_smoke.json",
    "collector_configuration_preflight.json",
    "source_terms_review_blockers.json",
    "no_live_source_call_guard.json",
    "source_monitoring_preflight_readiness.json",
    "source_monitoring_live_status.json",
    "next_source_activation_blockers.md",
)

#: A real federal registry row, used as the worked example throughout.
EXAMPLE_SOURCE = "nf-seed-2026-fed-001"
#: A grants.gov row, whose terms page served no policy text.
GRANTS_GOV_SOURCE = "nf-seed-2026-fed-013"
FIXTURE_SOURCE = f"{FIXTURE_SOURCE_PREFIX}gate143"

REAL_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

#: A dry-run collector, fully declared.
DRY_RUN_COLLECTOR: dict[str, Any] = {
    "source_id": EXAMPLE_SOURCE,
    "fetch_mode": "dry_run",
    "rate_limit_policy": "polite_default",
    "attribution_requirement": "not_required",
    "user_agent_policy": "nativeforge_canonical",
    "raw_payload_storage_policy": "local_dev_ignored",
    "activation_approval": True,
}

#: What a completed terms review would look like. Supplied only here, so the
#: permitted branch is reachable in an artifact without anything in runtime
#: gaining a review nobody performed.
REVIEWED = {EXAMPLE_SOURCE: "NO_REVIEW_REQUIRED"}

CREDENTIAL_FIELDS: tuple[str, ...] = (
    "api_key",
    "apikey",
    "secret",
    "token",
    "cookie",
    "session_cookie_value",
    "provider_subject",
    "client_secret",
)

FORBIDDEN_MARKERS: tuple[str, ...] = (
    "set-cookie:",
    "GOCSPX-",
    "BEGIN PRIVATE KEY",
    "eyJ",
    "nf_session=",
    "AKIA",
    "api_key=",
    "Bearer ",
)


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def _low(value: Any) -> str:
    return str(bool(value)).lower()


def build_source_monitoring_artifacts() -> dict[str, str]:
    """Every file, as text. Same input, same bytes, every time. Fetches nothing."""
    from nativeforge.services.hermetic_network_enforcement_service import (
        enforcement_invariant_failures,
        scan_for_network_call_sites,
    )
    from nativeforge.services.source_scheduler_readiness_service import (
        build_scheduler_readiness,
    )
    from nativeforge.services.source_terms_review_queue_service import (
        build_terms_review_queue,
        queue_invariant_failures,
    )

    evaluation = evaluate_registry()
    scan = scan_for_network_call_sites()
    scheduler = build_scheduler_readiness()
    terms_queue = build_terms_review_queue()
    module = detect_readiness_route_module()
    imports = detect_network_imports()

    collector = build_collector_preflight(
        config=DRY_RUN_COLLECTOR,
        terms_statuses=REVIEWED,
        activation_approvals=[EXAMPLE_SOURCE],
    )
    readiness = build_source_monitoring_readiness(
        registry_evaluation=evaluation,
        collector_preflight=collector,
        chokepoint_scan=scan,
        watchlist_can_name_sources=True,
        tenant_digest_operational=True,
    )

    # The worked cases, each driven for real rather than described.
    cases = {
        "registry_row_unreviewed": evaluate_source(source_id=EXAMPLE_SOURCE),
        "grants_gov_human_review_only": evaluate_source(source_id=GRANTS_GOV_SOURCE),
        "unknown_source_id": evaluate_source(source_id="nf-seed-9999-not-real"),
        "fixture_outside_a_test": evaluate_source(source_id=FIXTURE_SOURCE),
        "fixture_in_a_test": evaluate_source(
            source_id=FIXTURE_SOURCE, allow_fixture=True
        ),
        "reviewed_and_approved": evaluate_source(
            source_id=EXAMPLE_SOURCE,
            terms_statuses=REVIEWED,
            activation_approvals=[EXAMPLE_SOURCE],
        ),
        "approved_but_review_says_no": evaluate_source(
            source_id=EXAMPLE_SOURCE,
            terms_statuses={EXAMPLE_SOURCE: "TERMS_REVIEW_REQUIRED"},
            activation_approvals=[EXAMPLE_SOURCE],
        ),
        # A SAM.gov-shaped row. The shipped registry has none, and inventing one
        # in the registry would be fabricating a source - so it is supplied
        # here, to this call only, to exercise the credential rule.
        "credential_required": evaluate_source(
            source_id="nf-seed-sam-probe",
            registry={
                "nf-seed-sam-probe": {
                    "seed_id": "nf-seed-sam-probe",
                    "canonical_source_id": "nf:source:nf-seed-sam-probe",
                    "source_name": "SAM.gov probe row (not in the shipped registry)",
                    "source_url": "https://sam.gov/",
                    "access_posture_hint": "public",
                    "resolver_url_status": "resolved",
                    "source_health_status": "healthy",
                }
            },
        ),
    }

    collector_cases = {
        "dry_run_reviewed": collector,
        "live_without_approval": build_collector_preflight(
            config={
                **DRY_RUN_COLLECTOR,
                "fetch_mode": "live_fetch",
                "activation_approval": False,
            },
            terms_statuses=REVIEWED,
            activation_approvals=[EXAMPLE_SOURCE],
        ),
        "live_without_a_payload_store": build_collector_preflight(
            config={**DRY_RUN_COLLECTOR, "fetch_mode": "live_fetch"},
            terms_statuses=REVIEWED,
            activation_approvals=[EXAMPLE_SOURCE],
        ),
        "live_fully_configured": build_collector_preflight(
            config={
                **DRY_RUN_COLLECTOR,
                "fetch_mode": "live_fetch",
                "raw_payload_storage_policy": "s3_compatible_configured",
            },
            terms_statuses=REVIEWED,
            activation_approvals=[EXAMPLE_SOURCE],
        ),
        "attribution_required_without_verbatim": build_collector_preflight(
            config={
                **DRY_RUN_COLLECTOR,
                "attribution_requirement": "attribution_required",
            },
            terms_statuses=REVIEWED,
            activation_approvals=[EXAMPLE_SOURCE],
        ),
        "incomplete_configuration": build_collector_preflight(
            config={"source_id": EXAMPLE_SOURCE},
            terms_statuses=REVIEWED,
            activation_approvals=[EXAMPLE_SOURCE],
        ),
    }

    files: dict[str, str] = {}

    files["source_monitoring_survey.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "gate": "143",
            "why_source_monitoring_live_is_false": (
                "source_scheduler_readiness_service derives it from four "
                "conjuncts - runtime mode, background worker, periodic trigger, "
                "persistent backend - and five components are absent"
            ),
            "scheduler_runtime_mode": scheduler.get("runtime_mode"),
            "scheduler_runtime_executes_jobs": bool(
                scheduler.get("runtime_executes_jobs")
            ),
            "scheduler_components_missing": list(
                scheduler.get("components_missing") or []
            ),
            "registry_row_count": evaluation["registry_row_count"],
            "registry_has_a_terms_column": False,
            "registry_has_no_terms_column_so": (
                "every unreviewed row is UNKNOWN, and live_network_guard_service "
                "already classifies UNKNOWN as blocking - deny by default falls "
                "out of the data rather than being imposed on it"
            ),
            "evaluation_states": list(EVALUATION_STATES),
            "by_state": evaluation["by_state"],
            "human_review_domains": sorted(HUMAN_REVIEW_DOMAINS),
            "credential_required_domains": sorted(CREDENTIAL_REQUIRED_DOMAINS),
            "domains_matched_by_suffix_not_exact_host": True,
            "domains_matched_by_suffix_because": (
                "the registry has 128 distinct hosts across 177 rows; "
                "simpler.grants.gov, www.grants.gov and grants.gov are one "
                "publisher, and an exact-match list missed four rows"
            ),
            "sam_gov_rows_in_the_registry": 0,
            "monitoring_modules": list(MONITORING_MODULES),
            "readiness_route_module": module,
            "network_imports": imports,
            "no_network_library_imported": not imports["any_network_library_imported"],
            "urllib_parse_is_not_a_network_client": True,
            "real_organization_route_built": False,
            "real_organization_route_not_built_because": (
                f"it would create a route to {REAL_ORGANIZATION_ID} that nobody "
                "has authorized"
            ),
        }
    )

    files["approved_source_allowlist_smoke.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "registry_row_count": evaluation["registry_row_count"],
            "evaluated_count": evaluation["evaluated_count"],
            "by_state": evaluation["by_state"],
            "monitorable_count": evaluation["monitorable_count"],
            "monitorable_source_ids": evaluation["monitorable_source_ids"],
            "states": list(EVALUATION_STATES),
            "cases": {
                name: {
                    "source_id": case["source_id"],
                    "state": case["state"],
                    "monitorable": case["monitorable"],
                    "registry_known": case["registry_known"],
                    "terms_status": case["terms_status"],
                    "human_review_required": case["human_review_required"],
                    "credential_required": case["credential_required"],
                    "activation_approved": case["activation_approved"],
                    "blocked_reasons": case["blocked_reasons"],
                    "invariant_failures": allowlist_invariant_failures(case),
                }
                for name, case in cases.items()
            },
            "an_approval_never_clears_a_blocker": (
                cases["approved_but_review_says_no"]["monitorable"] is False
            ),
            "a_fixture_is_never_monitorable": (
                cases["fixture_in_a_test"]["monitorable"] is False
            ),
            "fetch_performed": False,
            "robots_fetched": False,
            "dns_resolved": False,
            "network_calls": int(evaluation["network_calls"]),
            "invariant_failures": allowlist_invariant_failures(evaluation),
        }
    )

    files["collector_configuration_preflight.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "required_config_keys": list(REQUIRED_CONFIG_KEYS),
            "states": list(COLLECTOR_STATES),
            "live_capable_payload_policies": sorted(LIVE_CAPABLE_PAYLOAD_POLICIES),
            "attribution_needing_verbatim": sorted(ATTRIBUTION_NEEDING_VERBATIM),
            "cases": {
                name: {
                    "state": case["state"],
                    "collector_may_run_live": case["collector_may_run_live"],
                    "fetch_mode": case["fetch_mode"],
                    "source_permitted": case["source_permitted"],
                    "activation_approval": case["activation_approval"],
                    "raw_payload_storage_policy": case["raw_payload_storage_policy"],
                    "missing_config_keys": case["missing_config_keys"],
                    "blocked_reasons": case["blocked_reasons"],
                    "invariant_failures": collector_preflight_invariant_failures(case),
                }
                for name, case in collector_cases.items()
            },
            "configuration_is_not_activation": True,
            "live_fetch_is_a_request_not_a_permission": True,
            "api_key_values_reported": False,
            "collector_activated": False,
            "fetch_performed": False,
            "network_calls": 0,
        }
    )

    files["source_terms_review_blockers.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "queue_length": terms_queue["queue_length"],
            "pending_count": terms_queue["pending_count"],
            "approved_count": terms_queue["approved_count"],
            "automation_blocked_count": terms_queue["automation_blocked_count"],
            "credential_required_count": terms_queue["credential_required_count"],
            "by_risk_type": terms_queue["by_risk_type"],
            "items": [
                {
                    "review_item_id": item["review_item_id"],
                    "source_id": item["source_id"],
                    "risk_type": item["risk_type"],
                    "review_status": item["review_status"],
                    "automation_blocked": item["automation_blocked"],
                    "human_review_only": item["human_review_only"],
                    "credential_required": item["credential_required"],
                    "priority": item["priority"],
                }
                for item in terms_queue["items"]
            ],
            "terms_review_bypassed": False,
            "human_review_bypassed": False,
            "sources_activated": terms_queue["sources_activated"],
            "fetch_performed": terms_queue["fetch_performed"],
            "invariant_failures": queue_invariant_failures(terms_queue),
        }
    )

    files["no_live_source_call_guard.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "chokepoint_clean": bool(scan.get("clean")),
            "files_scanned": int(scan.get("files_scanned") or 0),
            "unapproved_call_sites": int(scan.get("unapproved_count") or 0),
            "finding_count": int(scan.get("finding_count") or 0),
            "monitoring_modules_checked": list(MONITORING_MODULES),
            "network_imports": imports["network_imports"],
            "any_network_library_imported": imports["any_network_library_imported"],
            "network_libraries_watched": imports["network_libraries_watched"],
            "urllib_parse_is_inert": True,
            "urllib_request_is_not": True,
            "distinction_owned_by": "hermetic_network_enforcement_service",
            "collector_activated": False,
            "source_monitoring_live": bool(scheduler.get("source_monitoring_live")),
            "runtime_mode": scheduler.get("runtime_mode"),
            "sources_cleared_for_collection": evaluation["monitorable_count"],
            "this_guard_made_network_calls": 0,
            "invariant_failures": enforcement_invariant_failures(scan),
        }
    )

    files["source_monitoring_preflight_readiness.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "source_monitoring_preflight_ready": readiness[
                "source_monitoring_preflight_ready"
            ],
            "source_monitoring_live": readiness["source_monitoring_live"],
            "scope": readiness["scope"],
            "scopes": list(readiness["scopes"]),
            "registry_loaded": readiness["registry_loaded"],
            "registry_row_count": readiness["registry_row_count"],
            "every_row_classified": readiness["every_row_classified"],
            "collector_preflight_state": readiness["collector_preflight_state"],
            "chokepoint_clean": readiness["chokepoint_clean"],
            "chokepoint_files_scanned": readiness["chokepoint_files_scanned"],
            "watchlist_can_name_sources": readiness["watchlist_can_name_sources"],
            "tenant_digest_operational": readiness["tenant_digest_operational"],
            "monitorable_source_required_for_readiness": readiness[
                "monitorable_source_required_for_readiness"
            ],
            "collector_required_for_readiness": readiness[
                "collector_required_for_readiness"
            ],
            "scheduler_runtime_required_for_readiness": readiness[
                "scheduler_runtime_required_for_readiness"
            ],
            "live_source_access_required_for_readiness": readiness[
                "live_source_access_required_for_readiness"
            ],
            "route_module": readiness["route_module"],
            "not_approved": list(NOT_APPROVED),
            "invariant_failures": source_monitoring_readiness_invariant_failures(
                readiness
            ),
            "blocked_reasons": readiness["blocked_reasons"],
        }
    )

    files["source_monitoring_live_status.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "source_monitoring_live": bool(scheduler.get("source_monitoring_live")),
            "derived_by": "source_scheduler_readiness_service",
            "derived_from": [
                "runtime_mode in LIVE_RUNTIME_MODES",
                "background_worker_available",
                "periodic_trigger_available",
                "persistent_backend_live",
            ],
            "runtime_mode": scheduler.get("runtime_mode"),
            "runtime_executes_jobs": bool(scheduler.get("runtime_executes_jobs")),
            "background_worker_available": bool(
                scheduler.get("background_worker_available")
            ),
            "persistent_backend_live": bool(scheduler.get("persistent_backend_live")),
            "components_missing": list(scheduler.get("components_missing") or []),
            "ready_to_start_monitoring": bool(
                scheduler.get("ready_to_start_monitoring")
            ),
            "collectors_activated": 0,
            "live_source_calls": 0,
            "live_source_coverage": False,
            "production_source_monitoring": False,
            "sources_cleared_for_collection": evaluation["monitorable_count"],
            "improvement_claims": [],
        }
    )

    files["next_source_activation_blockers.md"] = _next_blockers(
        readiness, evaluation, scheduler, terms_queue, scan
    )

    for name, body in files.items():
        lowered = body.lower()
        for marker in FORBIDDEN_MARKERS:
            if marker.lower() in lowered:
                raise AssertionError(f"forbidden marker {marker!r} in {name}")
        for field in CREDENTIAL_FIELDS:
            if re.search(rf'"{re.escape(field)}"\s*:\s*"[^"]', lowered):
                raise AssertionError(f"field {field!r} carries a value in {name}")

    return files


def _next_blockers(
    readiness: dict[str, Any],
    evaluation: dict[str, Any],
    scheduler: dict[str, Any],
    terms_queue: dict[str, Any],
    scan: dict[str, Any],
) -> str:
    by_state = evaluation["by_state"]
    source_blockers = "\n".join(
        f"  {b['blocker']} x{b['count']}"
        for b in readiness["activation_blockers"]
        if "scheduler" not in b["blocker"]
    )
    chokepoint_summary = (
        f"{int(scan.get('files_scanned') or 0)} files scanned, "
        f"{int(scan.get('unapproved_count') or 0)} unapproved call sites"
    )
    ready = str(readiness["source_monitoring_preflight_ready"]).upper()
    live = str(readiness["source_monitoring_live"]).upper()
    components = "\n".join(
        f"  {name}" for name in (scheduler.get("components_missing") or [])
    )
    items = "\n".join(
        f"  {item['source_id']:28s} {item['risk_type']}"
        for item in terms_queue["items"]
    )
    return f"""# Gate 143 — what live source monitoring still does not reach

## Where this stands

```text
source_monitoring_preflight_ready   {ready}
source_monitoring_live              {live}
scope                               {readiness["scope"]}
registry rows classified            {evaluation["registry_row_count"]}
sources cleared for collection      {evaluation["monitorable_count"]}
```

Every one of the 177 registry rows can be evaluated, and the system can say
exactly what blocks each. **None of them was fetched.**

## Preflight is not monitoring

```text
source_monitoring_preflight_ready   can this system evaluate every source and
                                    prove no live call path is active?   TRUE
source_monitoring_live              is anything actually being checked?  FALSE
```

`source_monitoring_live` is not answered by this gate at all. It is read from
`source_scheduler_readiness_service`, which derives it from four conjuncts and
reports false because five components are absent. An invariant fails if a
passing preflight ever sets it.

## Why every source is blocked

```text
terms_blocked           {by_state.get("terms_blocked", 0):>4}
human_review_blocked    {by_state.get("human_review_blocked", 0):>4}
api_key_missing         {by_state.get("api_key_missing", 0):>4}
registry_known          {by_state.get("registry_known", 0):>4}
activation_approved     {by_state.get("activation_approved", 0):>4}
```

The registry has **no terms column**. It carries a url, a tier, an adapter key,
an access posture, a health status and a resolver status — and nothing about
what any publisher's terms of use say. So an unreviewed row is `UNKNOWN`, and
`live_network_guard_service` already puts `UNKNOWN` in `TERMS_BLOCKING`.

Deny by default is not a rule imposed on the registry here. It is what the
registry actually supports.

## The terms review queue

```text
{items}
```

The four SPA items are worth reading carefully: those terms pages are
client-rendered and served **no policy text**. That is not "the terms allow
this" and not "the terms forbid this" — nobody could read them, which is
precisely why a human has to.

## What a completed review would change

The permitted branch is reachable and was exercised:

```text
a recorded terms review alone      -> registry_known, no approval
an activation approval alone       -> terms_blocked, still
both                               -> activation_approved, monitorable
a review that came back
  TERMS_REVIEW_REQUIRED + approval -> terms_blocked. An approval never
                                      clears a blocker.
```

## What activation would still require

```text
a terms review per source
{source_blockers}

a scheduler that can run something:
{components}

and per source, at fetch time, everything live_network_guard_service already
requires: robots status, credential status, rate limit policy, the canonical
user agent, and verbatim attribution where the publisher requires it.
```

## What is NOT the blocker

```text
the registry            177 rows load and every one is classified
the allowlist           six states, each with a different owner and fix
the collector preflight seven declared policies, each checked
the choke point         {chokepoint_summary}
the watchlist           can name a registry source, since Gate 140
a network library       not needed to prove any of it, and not imported
```

## Nothing was called and nothing started

```text
live source calls                 0
robots.txt fetches                0
DNS resolutions                   0
collectors activated              0
sources cleared for collection    {evaluation["monitorable_count"]}
network calls by the evaluation   {int(evaluation["network_calls"])}
scheduler runtime mode            {scheduler.get("runtime_mode")}
runtime executes jobs             {_low(scheduler.get("runtime_executes_jobs"))}
```

## Still false, and not touched

```text
source_monitoring_live         false
live_source_coverage           false
production_source_monitoring   false
email_delivery                 false
object_store_configured        false
document_body_storage_ready    false
customer_auth_live             false
verified_operational_binding   false
production_rollout             false
controlled_customer_pilot      false
```
"""


def write_source_monitoring_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_source_monitoring_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def source_monitoring_artifact_invariant_failures(
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
    if READINESS_ROUTE_MODULE not in json.dumps(detect_readiness_route_module()):
        fails.append("route_module_name_drifted")

    return fails
