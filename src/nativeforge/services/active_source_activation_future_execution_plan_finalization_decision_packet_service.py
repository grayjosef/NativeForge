"""Sprint 82: future execution plan finalization decision packet (decision record only; no execution).

Consumes the Sprint 81 `nf_active_source_activation_future_execution_plan_finalization_review_packet_v1` artifact and
emits a deterministic packet recording a human decision for advancing to a final documentation-only execution packet
gate only. Does not execute plans, activate sources, create active source rows, author runnable commands, emit
command previews, open database sessions, scrape, ingest, call external URLs or LLMs, write runtime state, or mutate
ledgers.
"""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.active_source_activation_future_execution_plan_finalization_review_packet_service import (
    ARTIFACT_TYPE as SPRINT81_REVIEW_ARTIFACT_TYPE,
)
from nativeforge.services.active_source_activation_future_execution_plan_finalization_review_packet_service import (
    ARTIFACT_VERSION as SPRINT81_REVIEW_ARTIFACT_VERSION,
)
from nativeforge.services.active_source_activation_future_execution_plan_finalization_review_packet_service import (
    EXPLICIT_SPRINT81_OUTPUT_GUARD_KEY as SPRINT81_REVIEW_EXPLICIT_GUARD_FIELD,
)
from nativeforge.services.active_source_activation_future_execution_plan_finalization_review_packet_service import (
    FUTURE_EXEC_PLAN_FINALIZATION_REVIEW_BLOCKED as SPRINT81_REVIEW_BLOCKED,
)
from nativeforge.services.active_source_activation_future_execution_plan_finalization_review_packet_service import (
    FUTURE_EXEC_PLAN_FINALIZATION_REVIEW_READY as SPRINT81_REVIEW_READY,
)
from nativeforge.services.active_source_activation_future_execution_plan_finalization_review_packet_service import (
    NEXT_GATE_FUTURE_EXEC_PLAN_FINALIZATION_DECISION_PACKET as SPRINT81_EXPECTED_NEXT_GATE_REQUIRED,
)
from nativeforge.services.active_source_activation_future_execution_plan_finalization_review_packet_service import (
    _extra_mechanical_directive_issues,
)
from nativeforge.services.active_source_activation_preview_execution_plan_draft_review_packet_service import (
    _forbidden_language,
    _iter_string_values,
    _runnable_command_indicators,
    _url_and_shell_operator_issues,
)

ARTIFACT_TYPE = "nf_active_source_activation_future_execution_plan_finalization_decision_packet_v1"
ARTIFACT_VERSION = 1
PACKET_VERSION = "v1"
DETERMINISTIC_GENERATED_AT = "1970-01-01T00:00:00Z"

SPRINT81_PROOF_KEY = "sprint_81_future_execution_plan_finalization_review_packet_proof"

FUTURE_EXEC_PLAN_FINALIZATION_DECISION_APPROVED = (
    "approved_for_final_non_runnable_execution_plan_packet"
)
FUTURE_EXEC_PLAN_FINALIZATION_DECISION_BLOCKED = "blocked_future_execution_plan_finalization_decision_packet"

NEXT_GATE_FINAL_NON_RUNNABLE_EXECUTION_PLAN_PACKET = "final_non_runnable_execution_plan_packet"
NEXT_GATE_BLOCKED_UNTIL_DECISION_BLOCKERS_RESOLVED = "blocked_until_decision_blockers_resolved"

EXPLICIT_SPRINT82_OUTPUT_GUARD_KEY = (
    "explicit_preview_only_no_execution_no_activation_no_runnable_plan_"
    "execution_plan_finalization_decision_only_guardrail"
)

_SPRINT82_DECISION_GUARD_NOTE = (
    "sprint_82_active_source_activation_future_execution_plan_finalization_decision_packet_preview_only_"
    "no_execution_no_activation_no_runnable_plan_execution_plan_finalization_decision_only_"
    "final_non_runnable_execution_plan_packet_required_"
    "no_execution_performed_no_activation_performed_no_runnable_command_created_"
    "documentation_only_not_live_execution_not_source_activation_not_command_authoring_"
    "no_cli_no_sql_no_urls_no_scheduler_payloads_stateless_side_effect_free_"
    "finalization_decision_record_only_next_gate_final_non_runnable_execution_plan_packet"
)

_FINALIZATION_DECISION_DISCLAIMER = (
    "This narrative is descriptive documentation only. It is non-runnable, not mechanically actionable, "
    "and anticipates a separate final documentation-only execution packet without prescribing operational steps."
)

_FINALIZATION_DECISION_SCOPE_SUMMARY = (
    "A future final documentation-only execution packet should consolidate final source identity, approved scope "
    "as documentation categories, evidence bundle references as citation placeholders, provenance and audit "
    "expectations, monitoring and rollback considerations expressed conceptually, and a complete human "
    "authorization trail suitable for later review. "
    + _FINALIZATION_DECISION_DISCLAIMER
)

_FINALIZATION_DECISION_BOUNDARY_SUMMARY = (
    "Finalization decision boundaries remain limited to human-judgment topics for the upcoming packet: lane fit, "
    "control posture described narratively, escalation criteria as review questions, and explicit stop posture "
    "without mechanical triggers or host-oriented instruction. "
    + _FINALIZATION_DECISION_DISCLAIMER
)

_PROHIBITED_RUNTIME_ACTIONS_SUMMARY = (
    "This artifact forbids live activation postures, mechanically repeatable instruction sets oriented toward "
    "hosts or shells, data-plane changes, job-style dispatch narratives, outbound retrieval mechanics, and "
    "ledger or database mutations. It remains preview-only decision documentation. "
    + _FINALIZATION_DECISION_DISCLAIMER
)

_SPRINT81_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN: frozenset[str] = frozenset(
    {
        "finalization_review_scope_summary",
        "finalization_review_boundary_summary",
        "prohibited_runtime_actions_summary",
        SPRINT81_REVIEW_EXPLICIT_GUARD_FIELD,
    }
)


def _sprint81_input_for_nested_language_scan(pkt: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in pkt.items() if k not in _SPRINT81_NARRATIVE_KEYS_EXCLUDED_FROM_INPUT_LANGUAGE_SCAN}


_SPRINT82_ZERO_COUNTS: dict[str, int] = {
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
    "actual_schema_change_count_in_sprint_82": 0,
    "actual_alembic_revision_create_count": 0,
    "actual_database_write_count": 0,
    "actual_database_session_open_count": 0,
    "actual_command_execution_count": 0,
    "actual_execution_plan_authoring_count": 0,
    "actual_runnable_execution_plan_create_count": 0,
}

_SPRINT82_FALSE_MAY: dict[str, bool] = {
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
}


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _source_sprint_81_reference(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "artifact_type": None,
            "version": None,
            "artifact_version": None,
            "generated_at": None,
            "future_execution_plan_finalization_review_status": None,
            "future_execution_plan_finalization_review_ready": None,
            "future_execution_plan_finalization_decision_required": None,
            "next_gate_required": None,
        }
    return {
        "artifact_type": pkt.get("artifact_type"),
        "version": pkt.get("version"),
        "artifact_version": pkt.get("artifact_version"),
        "generated_at": pkt.get("generated_at"),
        "future_execution_plan_finalization_review_status": pkt.get(
            "future_execution_plan_finalization_review_status"
        ),
        "future_execution_plan_finalization_review_ready": pkt.get(
            "future_execution_plan_finalization_review_ready"
        ),
        "future_execution_plan_finalization_decision_required": pkt.get(
            "future_execution_plan_finalization_decision_required"
        ),
        "next_gate_required": pkt.get("next_gate_required"),
    }


def _source_finalization_review_summary(pkt: dict[str, Any] | None) -> dict[str, Any]:
    if pkt is None or not isinstance(pkt, dict):
        return {
            "future_execution_plan_finalization_review_status": None,
            "future_execution_plan_finalization_review_ready": None,
            "execution_plan_finalization_review_only": None,
            "future_execution_plan_finalization_decision_required": None,
            "next_gate_required": None,
        }
    return {
        "future_execution_plan_finalization_review_status": pkt.get(
            "future_execution_plan_finalization_review_status"
        ),
        "future_execution_plan_finalization_review_ready": pkt.get(
            "future_execution_plan_finalization_review_ready"
        ),
        "execution_plan_finalization_review_only": pkt.get("execution_plan_finalization_review_only"),
        "future_execution_plan_finalization_decision_required": pkt.get(
            "future_execution_plan_finalization_decision_required"
        ),
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


def _sprint81_explicit_guard_for_sprint82_input_ok(eg: Any) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    if not isinstance(eg, str) or not eg.strip():
        reasons.append("sprint_81_explicit_guardrail_missing_or_invalid")
        return (False, reasons)
    egl = eg.lower()
    if "preview_only" not in egl:
        reasons.append("sprint_81_explicit_guardrail_missing_preview_only_assertion")
    if "no_execution_no_activation_no_runnable_plan" not in egl:
        reasons.append(
            "sprint_81_explicit_guardrail_missing_no_execution_no_activation_no_runnable_plan_triplet_assertion"
        )
    if "execution_plan_finalization_review_only" not in egl:
        reasons.append("sprint_81_explicit_guardrail_missing_execution_plan_finalization_review_only_assertion")
    if "future_execution_plan_finalization_decision_required" not in egl:
        reasons.append(
            "sprint_81_explicit_guardrail_missing_future_execution_plan_finalization_decision_required_assertion"
        )
    if "no_execution_performed" not in egl:
        reasons.append("sprint_81_explicit_guardrail_missing_no_execution_performed_assertion")
    if "no_activation_performed" not in egl:
        reasons.append("sprint_81_explicit_guardrail_missing_no_activation_performed_assertion")
    if "no_runnable_command_created" not in egl:
        reasons.append("sprint_81_explicit_guardrail_missing_no_runnable_command_created_assertion")
    return (len(reasons) == 0, sorted(set(reasons)))


def _non_empty_str_field_ok(pkt: dict[str, Any], key: str) -> tuple[bool, list[str]]:
    v = pkt.get(key)
    if not isinstance(v, str) or not v.strip():
        return (False, [f"sprint_81_{key}_missing_or_empty"])
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


def _human_future_execution_plan_finalization_decision_blockers(inp: Any) -> list[str]:
    if inp is None:
        return ["human_future_execution_plan_finalization_decision_input_missing"]
    if not isinstance(inp, dict):
        return ["human_future_execution_plan_finalization_decision_input_not_a_dict"]

    approved = inp.get("approved")
    decision_raw = inp.get("decision")

    if approved is not None and not isinstance(approved, bool):
        return ["human_future_execution_plan_finalization_decision_approved_invalid_type"]

    if decision_raw is None or (isinstance(decision_raw, str) and not decision_raw.strip()):
        decision_norm: str | None = None
    elif not isinstance(decision_raw, str):
        return ["human_future_execution_plan_finalization_decision_invalid_type"]
    else:
        decision_norm = decision_raw.strip().lower()

    if decision_norm is not None and decision_norm not in ("approved", "rejected", "denied", "deny", "reject"):
        return ["human_future_execution_plan_finalization_decision_unrecognized_decision_string"]

    approve_bool = approved is True
    approve_str = decision_norm == "approved"
    reject_bool = approved is False
    reject_str = decision_norm in ("rejected", "denied", "deny", "reject")

    if approve_bool and reject_str:
        return ["human_future_execution_plan_finalization_decision_conflict_bool_and_string"]
    if reject_bool and approve_str:
        return ["human_future_execution_plan_finalization_decision_conflict_bool_and_string"]

    explicit_approve = approve_bool or approve_str
    explicit_reject = reject_bool or reject_str

    if explicit_approve and explicit_reject:
        return ["human_future_execution_plan_finalization_decision_internal_conflict"]

    if not explicit_approve and not explicit_reject:
        return ["human_future_execution_plan_finalization_decision_missing_or_unrecognized"]

    if explicit_reject:
        return ["human_future_execution_plan_finalization_decision_rejected_or_denied"]

    rationale = inp.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        return ["human_future_execution_plan_finalization_decision_rationale_missing_or_empty"]

    return []


def _human_fields_language_blockers(inp: dict[str, Any] | None) -> list[str]:
    if inp is None or not isinstance(inp, dict):
        return []
    payload: dict[str, Any] = {}
    r = inp.get("rationale")
    if isinstance(r, str):
        payload["human_future_execution_plan_finalization_decision_rationale"] = r
    oid = inp.get("operator_identifier")
    if isinstance(oid, str):
        payload["human_future_execution_plan_finalization_operator_identifier"] = oid
    if not payload:
        return []
    return _nested_string_language_blockers(payload)


def _human_decision_summary(
    *,
    inp: dict[str, Any] | None,
    human_blockers: list[str],
) -> dict[str, Any]:
    if inp is None or not isinstance(inp, dict):
        return {
            "human_decision_input_present": False,
            "human_explicit_approve_signal": False,
            "human_explicit_reject_signal": False,
            "human_decision_blockers_count": len(human_blockers),
        }
    approved = inp.get("approved")
    decision_raw = inp.get("decision")
    decision_norm = None
    if isinstance(decision_raw, str) and decision_raw.strip():
        decision_norm = decision_raw.strip().lower()
    approve_bool = approved is True
    approve_str = decision_norm == "approved"
    reject_bool = approved is False
    reject_str = decision_norm in ("rejected", "denied", "deny", "reject") if decision_norm else False
    return {
        "human_decision_input_present": True,
        "human_explicit_approve_signal": bool(approve_bool or approve_str),
        "human_explicit_reject_signal": bool(reject_bool or reject_str),
        "human_decision_blockers_count": len(human_blockers),
    }


def _sprint81_readiness_failures_for_sprint82(pkt: dict[str, Any] | None) -> list[str]:
    failures: list[str] = []
    if pkt is None or not isinstance(pkt, dict):
        failures.append("sprint_81_future_execution_plan_finalization_review_packet_missing_or_not_a_dict")
        return sorted(set(failures))

    if pkt.get("artifact_type") != SPRINT81_REVIEW_ARTIFACT_TYPE:
        failures.append("sprint_81_future_execution_plan_finalization_review_packet_artifact_type_mismatch")

    if pkt.get("artifact_version") != SPRINT81_REVIEW_ARTIFACT_VERSION:
        failures.append("sprint_81_future_execution_plan_finalization_review_packet_artifact_version_invalid")

    if pkt.get("preview_only") is not True:
        failures.append("sprint_81_preview_only_guardrail_missing_or_false")

    if pkt.get("no_execution") is not True:
        failures.append("sprint_81_no_execution_guardrail_missing_or_false")

    if pkt.get("no_activation") is not True:
        failures.append("sprint_81_no_activation_guardrail_missing_or_false")

    if pkt.get("no_runnable_plan") is not True:
        failures.append("sprint_81_no_runnable_plan_guardrail_missing_or_false")

    if pkt.get("execution_plan_finalization_review_only") is not True:
        failures.append("sprint_81_execution_plan_finalization_review_only_guardrail_missing_or_false")

    if pkt.get("future_execution_plan_finalization_decision_required") is not True:
        failures.append("sprint_81_future_execution_plan_finalization_decision_required_guardrail_missing_or_false")

    rs = pkt.get("future_execution_plan_finalization_review_status")
    if rs == SPRINT81_REVIEW_BLOCKED:
        failures.append("sprint_81_future_execution_plan_finalization_review_status_blocked")
    elif rs != SPRINT81_REVIEW_READY:
        if isinstance(rs, str):
            failures.append(f"sprint_81_future_execution_plan_finalization_review_status_not_ready:{rs}")
        else:
            failures.append("sprint_81_future_execution_plan_finalization_review_status_not_ready")

    if pkt.get("future_execution_plan_finalization_review_ready") is not True:
        failures.append("sprint_81_future_execution_plan_finalization_review_ready_not_true")

    if pkt.get("future_activation_execution_plan_execution_allowed") is not False:
        failures.append("sprint_81_future_activation_execution_plan_execution_allowed_not_false")

    if pkt.get("future_source_activation_allowed") is not False:
        failures.append("sprint_81_future_source_activation_allowed_not_false")

    ng = pkt.get("next_gate_required")
    if ng != SPRINT81_EXPECTED_NEXT_GATE_REQUIRED:
        if isinstance(ng, str):
            failures.append(f"sprint_81_next_gate_required_mismatch:{ng}")
        else:
            failures.append("sprint_81_next_gate_required_mismatch")

    for key in ("finalization_review_scope_summary", "finalization_review_boundary_summary"):
        ok_f, f_reasons = _non_empty_str_field_ok(pkt, key)
        if not ok_f:
            failures.extend(f_reasons)

    ok_p, p_reasons = _non_empty_str_field_ok(pkt, "prohibited_runtime_actions_summary")
    if not ok_p:
        failures.extend(p_reasons)

    if not isinstance(pkt.get(SPRINT81_PROOF_KEY), dict):
        failures.append("sprint_81_future_execution_plan_finalization_review_packet_proof_missing_or_invalid")

    if not isinstance(pkt.get("source_non_runnable_execution_planning_summary"), dict):
        failures.append("sprint_81_source_non_runnable_execution_planning_summary_missing_or_invalid")

    eg = pkt.get(SPRINT81_REVIEW_EXPLICIT_GUARD_FIELD)
    ok_eg, eg_reasons = _sprint81_explicit_guard_for_sprint82_input_ok(eg)
    if not ok_eg:
        failures.extend(eg_reasons)

    ok_am, am_reasons = _actual_may_guardrails_ok(pkt)
    if not ok_am:
        failures.extend(am_reasons)

    failures.extend(_nested_string_language_blockers(_sprint81_input_for_nested_language_scan(pkt)))
    return sorted(set(failures))


def build_active_source_activation_future_execution_plan_finalization_decision_packet(
    *,
    future_execution_plan_finalization_review_packet_artifact: dict[str, Any] | None = None,
    human_future_execution_plan_finalization_decision_input: dict[str, Any] | None = None,
) -> dict[str, Any]:
    pkt = (
        future_execution_plan_finalization_review_packet_artifact
        if isinstance(future_execution_plan_finalization_review_packet_artifact, dict)
        else None
    )

    readiness = _sprint81_readiness_failures_for_sprint82(pkt)
    human_decision_blockers = _human_future_execution_plan_finalization_decision_blockers(
        human_future_execution_plan_finalization_decision_input
    )
    human_lang = _human_fields_language_blockers(
        human_future_execution_plan_finalization_decision_input
        if isinstance(human_future_execution_plan_finalization_decision_input, dict)
        else None
    )

    all_blockers = sorted(set(readiness + human_decision_blockers + human_lang))
    approved_outcome = len(all_blockers) == 0

    if approved_outcome:
        decision_status = FUTURE_EXEC_PLAN_FINALIZATION_DECISION_APPROVED
        next_gate = NEXT_GATE_FINAL_NON_RUNNABLE_EXECUTION_PLAN_PACKET
        decision_approved = True
        final_packet_required = True
        decision_blockers: list[str] = []
    else:
        decision_status = FUTURE_EXEC_PLAN_FINALIZATION_DECISION_BLOCKED
        next_gate = NEXT_GATE_BLOCKED_UNTIL_DECISION_BLOCKERS_RESOLVED
        decision_approved = False
        final_packet_required = False
        decision_blockers = list(all_blockers)

    proof = {
        "sprint_82_future_execution_plan_finalization_decision_packet_is_stateless": True,
        "sprint_82_future_execution_plan_finalization_decision_packet_is_side_effect_free": True,
        "sprint_82_future_execution_plan_finalization_decision_packet_does_not_execute_plans": True,
        "sprint_82_future_execution_plan_finalization_decision_packet_does_not_activate_sources": True,
        "sprint_82_future_execution_plan_finalization_decision_packet_does_not_create_active_source_rows": True,
        "sprint_82_future_execution_plan_finalization_decision_packet_does_not_open_database_sessions": True,
        "sprint_82_consumes_sprint_81_future_execution_plan_finalization_review_packet_only": True,
    }

    human_summary = _human_decision_summary(
        inp=human_future_execution_plan_finalization_decision_input
        if isinstance(human_future_execution_plan_finalization_decision_input, dict)
        else None,
        human_blockers=list(sorted(set(human_decision_blockers + human_lang))),
    )

    out: dict[str, Any] = {
        "artifact_type": ARTIFACT_TYPE,
        "artifact_version": ARTIFACT_VERSION,
        "version": PACKET_VERSION,
        "generated_at": DETERMINISTIC_GENERATED_AT,
        "source_sprint_81_future_execution_plan_finalization_review_packet_reference": _source_sprint_81_reference(
            pkt
        ),
        "future_execution_plan_finalization_decision_status": decision_status,
        "future_execution_plan_finalization_decision_approved": decision_approved,
        "final_non_runnable_execution_plan_packet_required": final_packet_required,
        "future_activation_execution_plan_execution_allowed": False,
        "future_source_activation_allowed": False,
        "preview_only": True,
        "no_execution": True,
        "no_activation": True,
        "no_runnable_plan": True,
        "execution_plan_finalization_decision_only": True,
        "next_gate_required": next_gate,
        EXPLICIT_SPRINT82_OUTPUT_GUARD_KEY: _SPRINT82_DECISION_GUARD_NOTE,
        "decision_blockers": decision_blockers,
        "human_decision_summary": human_summary,
        "finalization_decision_scope_summary": _FINALIZATION_DECISION_SCOPE_SUMMARY,
        "finalization_decision_boundary_summary": _FINALIZATION_DECISION_BOUNDARY_SUMMARY,
        "prohibited_runtime_actions_summary": _PROHIBITED_RUNTIME_ACTIONS_SUMMARY,
        "source_finalization_review_summary": _source_finalization_review_summary(pkt),
        "sprint_82_future_execution_plan_finalization_decision_packet_proof": proof,
    }
    out.update(_SPRINT82_ZERO_COUNTS)
    out.update(_SPRINT82_FALSE_MAY)

    hid = (
        human_future_execution_plan_finalization_decision_input.get("operator_identifier")
        if isinstance(human_future_execution_plan_finalization_decision_input, dict)
        else None
    )
    if approved_outcome and isinstance(hid, str) and hid.strip():
        if not _nested_string_language_blockers({"human_future_execution_plan_finalization_operator_identifier": hid}):
            out["human_future_execution_plan_finalization_operator_identifier"] = hid

    hnotes = (
        human_future_execution_plan_finalization_decision_input.get("rationale")
        if isinstance(human_future_execution_plan_finalization_decision_input, dict)
        else None
    )
    if approved_outcome and isinstance(hnotes, str) and hnotes.strip():
        if not _nested_string_language_blockers(
            {"human_future_execution_plan_finalization_decision_rationale": hnotes}
        ):
            out["human_future_execution_plan_finalization_decision_rationale"] = hnotes

    return _json_safe(out)
