"""Sprint 91: final source activation authorization packet (authorization record only; no execution).

Consumes the Sprint 90 `nf_active_source_activation_source_activation_readiness_decision_packet_v1` artifact and emits a
deterministic authorization packet for a later non-runnable activation handoff gate only. Does not execute plans,
activate sources, create active source rows, author runnable commands, emit command previews, open database sessions,
scrape, ingest, call external URLs or LLMs, write runtime state, or mutate ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_future_execution_plan_finalization_review_packet_service import (
    _extra_mechanical_directive_issues,
)
from nativeforge.services.active_source_activation_preview_execution_plan_draft_review_packet_service import (
    _forbidden_language,
    _iter_string_values,
    _runnable_command_indicators,
    _url_and_shell_operator_issues,
)
from nativeforge.services.active_source_activation_source_activation_readiness_decision_packet_service import (
    ARTIFACT_TYPE as SPRINT90_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_source_activation_readiness_decision_packet_service import (
    ARTIFACT_VERSION as SPRINT90_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_source_activation_readiness_decision_packet_service import (
    EXPLICIT_SPRINT90_OUTPUT_GUARD_KEY as SPRINT90_EXPLICIT_GUARD_FIELD,
)
from nativeforge.services.active_source_activation_source_activation_readiness_decision_packet_service import (
    NEXT_GATE_FINAL_SOURCE_ACTIVATION_AUTHORIZATION_PACKET as SPRINT90_EXPECTED_NEXT_GATE_REQUIRED,
)
from nativeforge.services.active_source_activation_source_activation_readiness_decision_packet_service import (
    SOURCE_ACTIVATION_READINESS_DECISION_APPROVED_STATUS as SPRINT90_DECISION_APPROVED_STATUS,
)
from nativeforge.services.active_source_activation_source_activation_readiness_decision_packet_service import (
    SOURCE_ACTIVATION_READINESS_DECISION_BLOCKED_STATUS as SPRINT90_DECISION_BLOCKED_STATUS,
)

ARTIFACT_TYPE = "nf_active_source_activation_final_source_activation_authorization_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

SPRINT90_PROOF_KEY = "sprint_90_source_activation_readiness_decision_packet_proof"

FINAL_SOURCE_ACTIVATION_AUTHORIZATION_APPROVED_STATUS = (
    "authorized_for_later_non_runnable_activation_handoff_packet"
)
FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS = "blocked_final_source_activation_authorization_packet"

NEXT_GATE_LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_PACKET = "later_non_runnable_activation_handoff_packet"
NEXT_GATE_BLOCKED_UNTIL_FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKERS_RESOLVED = (
    "blocked_until_final_source_activation_authorization_blockers_resolved"
)

EXPLICIT_SPRINT91_OUTPUT_GUARD_KEY = (
    "explicit_preview_only_no_execution_no_activation_no_runnable_plan_"
    "final_source_activation_authorization_only_guardrail"
)

_SPRINT91_GUARD_NOTE = (
    "sprint_91_active_source_activation_final_source_activation_authorization_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_final_source_activation_authorization_only_"
    "source_activation_authorized_false_source_activation_executed_false_source_activation_completed_false_"
    "source_activation_readiness_granted_false_no_execution_performed_no_activation_performed_"
    "no_runnable_command_created_source_activation_authorized_for_later_non_runnable_handoff_documentation_only_"
    "not_live_execution_not_runtime_source_activation_not_command_authoring_no_cli_no_sql_no_urls_"
    "no_scheduler_payloads_stateless_side_effect_free_later_non_runnable_activation_handoff_gate_only_"
    "not_claiming_activation_finished_state_not_documenting_production_runtime_activation_events"
)

_FINAL_AUTH_DISCLAIMER = (
    "This narrative is descriptive documentation only. It is non-runnable, not mechanically actionable, "
    "and anticipates a separate later non-runnable activation handoff packet without prescribing operational steps."
)

_FINAL_AUTHORIZATION_SCOPE_SUMMARY = (
    "Final source activation authorization scope may restate reviewed source identity as documentation categories, "
    "authorization boundaries as audit topics, evidence bundle references as citation placeholders only, provenance "
    "and audit expectations as narrative requirements, monitoring considerations conceptually, rollback considerations "
    "conceptually, and later non-runnable activation handoff requirements for a separate handoff gate. "
    + _FINAL_AUTH_DISCLAIMER
)

_FINAL_AUTHORIZATION_BOUNDARY_SUMMARY = (
    "Final authorization boundaries remain limited to documentation judgment: readiness decision fit for a later "
    "handoff gate, control posture described narratively, provenance expectations, escalation criteria as review "
    "questions, and explicit stop posture without mechanical triggers, host-oriented instruction, or copy-paste "
    "operational steps. "
    + _FINAL_AUTH_DISCLAIMER
)

_FINAL_AUTHORIZATION_EVIDENCE_SUMMARY = (
    "Final authorization evidence expectations are described as categories and citation placeholders for bundle "
    "references, provenance completeness, audit trail sufficiency, monitoring context, and rollback review context. "
    "This section does not prescribe retrieval mechanics, tooling, or repeatable host actions. "
    + _FINAL_AUTH_DISCLAIMER
)

_FINAL_AUTHORIZATION_NON_RUNTIME_SUMMARY = (
    "Sprint 90 produced a descriptive source activation readiness decision packet only. This Sprint 91 final "
    "authorization packet does not authorize live execution, does not activate sources, does not finish activation as "
    "an operational outcome, does not document production activation against live systems, and does not create "
    "runnable commands. "
    + _FINAL_AUTH_DISCLAIMER
)

_LATER_NON_RUNNABLE_HANDOFF_REQUIREMENTS_SUMMARY = (
    "A later non-runnable activation handoff packet must evaluate handoff posture, boundary fit, evidence and "
    "provenance requirements, monitoring considerations, rollback considerations, and whether any future non-runnable "
    "activation documentation may be considered under separate gating. "
    + _FINAL_AUTH_DISCLAIMER
)

_PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK = (
    "This artifact forbids live activation postures, mechanically repeatable instruction sets oriented toward hosts "
    "or shells, data-plane changes, job-style dispatch narratives, outbound retrieval mechanics, and ledger or "
    "database mutations. It remains preview-only final source activation authorization documentation. "
    + _FINAL_AUTH_DISCLAIMER
)

_SPRINT90_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN: frozenset[str] = frozenset(
    {
        "readiness_decision_scope_summary",
        "readiness_decision_boundary_summary",
        "readiness_decision_evidence_summary",
        "readiness_decision_authorization_summary",
        "final_authorization_requirements_summary",
        "readiness_decision_rationale",
        "prohibited_runtime_actions_summary",
        SPRINT90_EXPLICIT_GUARD_FIELD,
    }
)


def _sprint90_input_for_nested_language_scan(pkt: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in pkt.items() if k not in _SPRINT90_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN}


_SPRINT91_ZERO_COUNTS: dict[str, int] = {
    "actual_source_row_create_count": 0,
    "actual_source_row_insert_count": 0,
    "actual_source_row_update_count": 0,
    "actual_source_row_delete_count": 0,
    "actual_activation_count": 0,
    "actual_scrape_count": 0,
    "actual_ingest_count": 0,
    "actual_external_api_call_count": 0,
    "actual_llm_call_count": 0,
    "actual_operator_ledger_action_count": 0,
    "actual_schema_change_count_in_sprint_91": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
    "actual_execution_plan_authoring_count": 0,
    "actual_runnable_execution_plan_create_count": 0,
    "actual_source_activation_readiness_grant_count": 0,
}

_SPRINT91_FALSE_MAY: dict[str, bool] = {
    "may_create_source_rows_now": False,
    "may_insert_source_rows_now": False,
    "may_update_source_rows_now": False,
    "may_delete_source_rows_now": False,
    "may_activate_source_now": False,
    "may_scrape_now": False,
    "may_ingest_now": False,
    "may_call_external_api_now": False,
    "may_call_llm_now": False,
    "may_create_operator_ledger_actions_now": False,
    "may_modify_schema_now": False,
    "may_create_alembic_revision_now": False,
    "may_write_database_now": False,
    "may_open_database_session_now": False,
    "may_execute_activation_now": False,
    "may_execute_fetch_now": False,
    "may_execute_scrape_now": False,
    "may_execute_ingest_now": False,
    "may_author_execution_plan_now": False,
    "may_author_runnable_execution_plan_now": False,
    "may_grant_source_activation_readiness_now": False,
    "may_authorize_source_activation_now": False,
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _source_sprint_90_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "generated_at": None,
            "source_activation_readiness_decision_status": None,
            "source_activation_readiness_decision_approved": None,
            "source_activation_readiness_decision_recorded": None,
            "source_activation_readiness_decision_only": None,
            "final_source_activation_authorization_packet_required": None,
            "next_gate_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "generated_at": pkt.get("generated_at"),
        "source_activation_readiness_decision_status": pkt.get("source_activation_readiness_decision_status"),
        "source_activation_readiness_decision_approved": pkt.get("source_activation_readiness_decision_approved"),
        "source_activation_readiness_decision_recorded": pkt.get("source_activation_readiness_decision_recorded"),
        "source_activation_readiness_decision_only": pkt.get("source_activation_readiness_decision_only"),
        "final_source_activation_authorization_packet_required": pkt.get(
            "final_source_activation_authorization_packet_required"
        ),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _source_activation_readiness_decision_summary(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "source_activation_readiness_decision_status": None,
            "source_activation_readiness_decision_approved": None,
            "source_activation_readiness_decision_recorded": None,
            "source_activation_readiness_decision_only": None,
            "final_source_activation_authorization_packet_required": None,
            "source_activation_readiness_granted": None,
            "source_activation_authorized": None,
            "next_gate_required": None,
        }
    return {
        "source_activation_readiness_decision_status": pkt.get("source_activation_readiness_decision_status"),
        "source_activation_readiness_decision_approved": pkt.get("source_activation_readiness_decision_approved"),
        "source_activation_readiness_decision_recorded": pkt.get("source_activation_readiness_decision_recorded"),
        "source_activation_readiness_decision_only": pkt.get("source_activation_readiness_decision_only"),
        "final_source_activation_authorization_packet_required": pkt.get(
            "final_source_activation_authorization_packet_required"
        ),
        "source_activation_readiness_granted": pkt.get("source_activation_readiness_granted"),
        "source_activation_authorized": pkt.get("source_activation_authorized"),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _actual_may_guardrails_ok(obj: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    for k, v in sorted(obj.items(), key=lambda kv: kv[0]):
        if k.startswith("actual_") and isinstance(v, int) and v != 0:
            reasons.append(f"non_zero_{k}")
        if k.startswith("may_") and v is True:
            reasons.append(f"may_flag_true_{k}")
    return (len(reasons) == 0, reasons)


def _sprint90_explicit_guard_for_sprint91_input_ok(eg: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(eg, str) or not eg.strip():
        reasons.append("sprint_90_explicit_guardrail_missing_or_invalid")
        return (False, reasons)
    egl = eg.lower()
    if "preview_only" not in egl:
        reasons.append("sprint_90_explicit_guardrail_missing_preview_only_assertion")
    if "no_execution" not in egl:
        reasons.append("sprint_90_explicit_guardrail_missing_no_execution_assertion")
    if "no_activation" not in egl:
        reasons.append("sprint_90_explicit_guardrail_missing_no_activation_assertion")
    if "no_runnable_plan" not in egl:
        reasons.append("sprint_90_explicit_guardrail_missing_no_runnable_plan_assertion")
    if "source_activation_readiness_decision_only" not in egl:
        reasons.append("sprint_90_explicit_guardrail_missing_source_activation_readiness_decision_only_assertion")
    if "final_source_activation_authorization_packet_required" not in egl:
        reasons.append(
            "sprint_90_explicit_guardrail_missing_final_source_activation_authorization_packet_required_assertion"
        )
    if "source_activation_readiness_granted_false" not in egl:
        reasons.append("sprint_90_explicit_guardrail_missing_source_activation_readiness_granted_false_assertion")
    if "source_activation_authorized_false" not in egl:
        reasons.append("sprint_90_explicit_guardrail_missing_source_activation_authorized_false_assertion")
    if "no_execution_performed" not in egl:
        reasons.append("sprint_90_explicit_guardrail_missing_no_execution_performed_assertion")
    if "no_activation_performed" not in egl:
        reasons.append("sprint_90_explicit_guardrail_missing_no_activation_performed_assertion")
    if "no_runnable_command_created" not in egl:
        reasons.append("sprint_90_explicit_guardrail_missing_no_runnable_command_created_assertion")
    return (len(reasons) == 0, sorted(set(reasons)))


def _non_empty_str_field_ok(pkt: dict[str, Any], key: str, failure_prefix: str) -> tuple[bool, list[str]]:
    v = pkt.get(key)
    if not isinstance(v, str) or not v.strip():
        return (False, [f"{failure_prefix}_{key}_missing_or_empty"])
    return (True, [])


def _nested_string_language_blockers(root: Any) -> list[str]:
    strings: list[str] = []
    _iter_string_values(root, strings)
    found: list[str] = []
    found.extend(_forbidden_language(root if isinstance(root, dict) else {"_v": root}))
    if isinstance(root, dict):
        found.extend(_runnable_command_indicators(root))
        found.extend(_url_and_shell_operator_issues(strings))
    else:
        found.extend(_runnable_command_indicators({"_v": root}))
        found.extend(_url_and_shell_operator_issues(strings))
    found.extend(_extra_mechanical_directive_issues(strings))
    return sorted(set(found))


def _human_final_source_activation_authorization_blockers(inp: Any) -> list[str]:
    if inp is None:
        return ["human_final_source_activation_authorization_input_missing"]
    if not isinstance(inp, dict):
        return ["human_final_source_activation_authorization_input_not_a_dict"]

    authorized = inp.get("authorized")
    if authorized is not None and not isinstance(authorized, bool):
        return ["human_final_source_activation_authorization_authorized_invalid_type"]

    auth_dec_raw = inp.get("authorization_decision")
    decision_raw = inp.get("decision")

    if auth_dec_raw is not None and not isinstance(auth_dec_raw, str):
        return ["human_final_source_activation_authorization_authorization_decision_invalid_type"]
    if decision_raw is not None and not isinstance(decision_raw, str):
        return ["human_final_source_activation_authorization_decision_invalid_type"]

    auth_dec_norm: str | None = (
        None if auth_dec_raw is None or (isinstance(auth_dec_raw, str) and not auth_dec_raw.strip()) else str(
            auth_dec_raw
        ).strip().lower()
    )
    decision_norm: str | None = (
        None
        if decision_raw is None or (isinstance(decision_raw, str) and not decision_raw.strip())
        else str(decision_raw).strip().lower()
    )

    reject_decisions = ("rejected", "denied", "deny", "reject", "blocked", "not_authorized", "not authorized")

    authorize_bool = authorized is True
    authorize_auth_dec = auth_dec_norm == "authorized"
    authorize_dec = decision_norm == "authorized"

    reject_bool = authorized is False
    reject_auth_dec = auth_dec_norm in reject_decisions if auth_dec_norm else False
    reject_dec = decision_norm in reject_decisions if decision_norm else False

    if auth_dec_norm is not None and auth_dec_norm not in ("authorized", *reject_decisions):
        return ["human_final_source_activation_authorization_unrecognized_authorization_decision_string"]
    if decision_norm is not None and decision_norm not in ("authorized", *reject_decisions):
        return ["human_final_source_activation_authorization_unrecognized_decision_string"]

    if authorize_bool and reject_auth_dec:
        return ["human_final_source_activation_authorization_conflict_bool_and_authorization_decision_string"]
    if authorize_bool and reject_dec:
        return ["human_final_source_activation_authorization_conflict_bool_and_decision_string"]
    if reject_bool and authorize_auth_dec:
        return ["human_final_source_activation_authorization_conflict_bool_and_authorization_decision_string"]
    if reject_bool and authorize_dec:
        return ["human_final_source_activation_authorization_conflict_bool_and_decision_string"]

    explicit_approve = authorize_bool or authorize_auth_dec or authorize_dec
    explicit_reject = reject_bool or reject_auth_dec or reject_dec

    if explicit_approve and explicit_reject:
        return ["human_final_source_activation_authorization_internal_conflict"]

    if not explicit_approve and not explicit_reject:
        return ["human_final_source_activation_authorization_missing_or_unrecognized"]

    if explicit_reject:
        return ["human_final_source_activation_authorization_rejected_or_denied_or_blocked"]

    return []


def _human_input_nested_language_blockers(inp: dict[str, Any] | None) -> list[str]:
    if inp is None or not isinstance(inp, dict):
        return []
    return _nested_string_language_blockers(inp)


def _authorization_rationale_forbidden_blockers(inp: dict[str, Any] | None) -> list[str]:
    if inp is None or not isinstance(inp, dict):
        return []
    found: list[str] = []
    for key in ("authorization_rationale", "rationale"):
        r = inp.get(key)
        if r is None or (isinstance(r, str) and not r.strip()):
            continue
        if not isinstance(r, str):
            found.append(f"human_final_source_activation_authorization_{key}_invalid_type")
            continue
        found.extend(_nested_string_language_blockers({key: r}))
    return sorted(set(found))


def _prohibited_runtime_actions_from_sprint90(pkt: dict[str, Any] | None) -> str:
    if pkt is None or not isinstance(pkt, dict):
        return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK
    pr = pkt.get("prohibited_runtime_actions_summary")
    if isinstance(pr, str) and pr.strip():
        return pr
    return _PROHIBITED_RUNTIME_ACTIONS_SUMMARY_FALLBACK


def _sprint90_failures_for_sprint91(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("sprint_90_source_activation_readiness_decision_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != SPRINT90_ARTIFACT_TYPE:
        failures.append("sprint_90_source_activation_readiness_decision_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT90_ARTIFACT_VERSION:
        failures.append("sprint_90_source_activation_readiness_decision_packet_artifact_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("sprint_90_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("sprint_90_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("sprint_90_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append("sprint_90_no_runnable_plan_guardrail_missing_or_false")

    if pkt.get("source_activation_readiness_decision_only") is not True:
        failures.append("sprint_90_source_activation_readiness_decision_only_guardrail_missing_or_false")

    if pkt.get("final_source_activation_authorization_packet_required") is not True:
        failures.append("sprint_90_final_source_activation_authorization_packet_required_guardrail_missing_or_false")

    if pkt.get("source_activation_readiness_granted") is not False:
        failures.append("sprint_90_source_activation_readiness_granted_not_false")

    if pkt.get("source_activation_authorized") is not False:
        failures.append("sprint_90_source_activation_authorized_not_false")

    ds = pkt.get("source_activation_readiness_decision_status")
    if ds == SPRINT90_DECISION_BLOCKED_STATUS:
        failures.append("sprint_90_source_activation_readiness_decision_packet_blocked")
    elif ds != SPRINT90_DECISION_APPROVED_STATUS:
        if isinstance(ds, str):
            failures.append(f"sprint_90_source_activation_readiness_decision_status_not_approved_for_final_auth:{ds}")
        else:
            failures.append("sprint_90_source_activation_readiness_decision_status_not_approved_for_final_auth")

    if pkt.get("source_activation_readiness_decision_approved") is not True:
        failures.append("sprint_90_source_activation_readiness_decision_approved_not_true")

    if pkt.get("source_activation_readiness_decision_recorded") is not True:
        failures.append("sprint_90_source_activation_readiness_decision_recorded_not_true")

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append("sprint_90_future_activation_execution_plan_execution_allowed_not_false")

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append("sprint_90_future_source_activation_allowed_not_false")

    next_gate = pkt.get("next_gate_required")
    if next_gate != SPRINT90_EXPECTED_NEXT_GATE_REQUIRED:
        if isinstance(next_gate, str):
            failures.append(f"sprint_90_next_gate_required_mismatch:{next_gate}")
        else:
            failures.append("sprint_90_next_gate_required_mismatch")

    for key in (
        "readiness_decision_scope_summary",
        "readiness_decision_boundary_summary",
        "readiness_decision_evidence_summary",
        "readiness_decision_authorization_summary",
        "final_authorization_requirements_summary",
        "readiness_decision_rationale",
        "prohibited_runtime_actions_summary",
    ):
        ok_f, f_reasons = _non_empty_str_field_ok(pkt, key, "sprint_90")
        if not ok_f:
            failures.extend(f_reasons)

    if not isinstance(pkt.get(SPRINT90_PROOF_KEY), dict):
        failures.append("sprint_90_source_activation_readiness_decision_packet_proof_missing_or_invalid")

    if not isinstance(pkt.get("source_activation_readiness_review_summary"), dict):
        failures.append("sprint_90_source_activation_readiness_review_summary_missing_or_invalid")

    eg = pkt.get(SPRINT90_EXPLICIT_GUARD_FIELD)
    ok_eg, eg_reasons = _sprint90_explicit_guard_for_sprint91_input_ok(eg)
    if not ok_eg:
        failures.extend(eg_reasons)

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_nested_string_language_blockers(_sprint90_input_for_nested_language_scan(pkt)))
    return sorted(set(failures))


def build_active_source_activation_final_source_activation_authorization_packet(
    *,
    source_activation_readiness_decision_packet_artifact: dict[str, Any] | None = None,
    human_final_source_activation_authorization_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = (
        source_activation_readiness_decision_packet_artifact
        if isinstance(source_activation_readiness_decision_packet_artifact, dict)
        else None
    )

    sprint90_blockers = _sprint90_failures_for_sprint91(pkt)
    human_blockers = _human_final_source_activation_authorization_blockers(
        human_final_source_activation_authorization_input
    )
    human_nested = _human_input_nested_language_blockers(
        human_final_source_activation_authorization_input
        if isinstance(human_final_source_activation_authorization_input, dict)
        else None
    )
    rationale_blockers = _authorization_rationale_forbidden_blockers(
        human_final_source_activation_authorization_input
        if isinstance(human_final_source_activation_authorization_input, dict)
        else None
    )

    all_blockers = sorted(set(sprint90_blockers + human_blockers + human_nested + rationale_blockers))
    approved_outcome = len(all_blockers) == 0

    if approved_outcome:
        auth_status = FINAL_SOURCE_ACTIVATION_AUTHORIZATION_APPROVED_STATUS
        next_gate = NEXT_GATE_LATER_NON_RUNNABLE_ACTIVATION_HANDOFF_PACKET
        auth_recorded = True
        auth_approved = True
        handoff_ok = True
        blockers_out: list[str] = []
    else:
        auth_status = FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKED_STATUS
        next_gate = NEXT_GATE_BLOCKED_UNTIL_FINAL_SOURCE_ACTIVATION_AUTHORIZATION_BLOCKERS_RESOLVED
        auth_recorded = False
        auth_approved = False
        handoff_ok = False
        blockers_out = list(all_blockers)

    proof = {
        "sprint_91_final_source_activation_authorization_packet_is_stateless": True,
        "sprint_91_final_source_activation_authorization_packet_is_side_effect_free": True,
        "sprint_91_final_source_activation_authorization_packet_does_not_execute_plans": True,
        "sprint_91_final_source_activation_authorization_packet_does_not_activate_sources": True,
        "sprint_91_final_source_activation_authorization_packet_does_not_create_active_source_rows": True,
        "sprint_91_final_source_activation_authorization_packet_does_not_open_database_sessions": True,
        "sprint_91_final_source_activation_authorization_packet_does_not_authorize_live_execution": True,
        "sprint_91_final_source_activation_authorization_packet_does_not_complete_source_activation": True,
        "sprint_91_consumes_sprint_90_source_activation_readiness_decision_packet_only": True,
    }

    rationale_out = ""
    if approved_outcome and isinstance(human_final_source_activation_authorization_input, dict):
        r0 = human_final_source_activation_authorization_input.get("authorization_rationale")
        if isinstance(r0, str):
            rationale_out = r0
        else:
            r1 = human_final_source_activation_authorization_input.get("rationale")
            rationale_out = r1 if isinstance(r1, str) else ""

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "source_sprint_90_source_activation_readiness_decision_packet_reference": _source_sprint_90_reference(pkt),
        "final_source_activation_authorization_status": auth_status,
        "final_source_activation_authorization_recorded": auth_recorded,
        "final_source_activation_authorization_approved": auth_approved,
        "final_source_activation_authorization_only": True,
        "source_activation_authorized_for_later_non_runnable_handoff": handoff_ok,
        "source_activation_authorized": False,
        "source_activation_executed": False,
        "source_activation_completed": False,
        "source_activation_readiness_granted": False,
        "future_activation_execution_plan_execution_allowed": False,
        "future_source_activation_allowed": False,
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        EXPLICIT_SPRINT91_OUTPUT_GUARD_KEY: _SPRINT91_GUARD_NOTE,
        "final_source_activation_authorization_blockers": blockers_out,
        "final_authorization_scope_summary": _FINAL_AUTHORIZATION_SCOPE_SUMMARY,
        "final_authorization_boundary_summary": _FINAL_AUTHORIZATION_BOUNDARY_SUMMARY,
        "final_authorization_evidence_summary": _FINAL_AUTHORIZATION_EVIDENCE_SUMMARY,
        "final_authorization_non_runtime_summary": _FINAL_AUTHORIZATION_NON_RUNTIME_SUMMARY,
        "later_non_runnable_handoff_requirements_summary": _LATER_NON_RUNNABLE_HANDOFF_REQUIREMENTS_SUMMARY,
        "final_authorization_rationale": rationale_out,
        "prohibited_runtime_actions_summary": _prohibited_runtime_actions_from_sprint90(pkt),
        "sprint_91_final_source_activation_authorization_packet_proof": proof,
        "source_activation_readiness_decision_summary": _source_activation_readiness_decision_summary(pkt),
        "next_gate_required": next_gate,
    }
    out.update(_SPRINT91_ZERO_COUNTS)
    out.update(_SPRINT91_FALSE_MAY)

    hid = (
        human_final_source_activation_authorization_input.get("operator_identifier")
        if isinstance(human_final_source_activation_authorization_input, dict)
        else None
    )
    if approved_outcome and isinstance(hid, str) and hid.strip():
        if not _nested_string_language_blockers(
            {"human_final_source_activation_authorization_operator_identifier": hid}
        ):
            out["human_final_source_activation_authorization_operator_identifier"] = hid

    return _json_safe(out)
