"""No-fail claim/governance invariant suite helpers (Gate 06 / Block 17)."""

from __future__ import annotations

import json
from typing import Any

from nativeforge.services.collaboration_dark_flag_service import (
    build_collaboration_dark_flag_contract,
    collaboration_dark_flag_invariant_failures,
)
from nativeforge.services.controlled_drafting_assembler_service import (
    build_controlled_drafting_demo_surface,
    controlled_drafting_demo_surface_invariant_failures,
)
from nativeforge.services.feedback_loop_assembler_service import (
    build_feedback_loop_demo_surface,
    feedback_loop_demo_surface_invariant_failures,
)
from nativeforge.services.forms_attachments_mapper_service import (
    build_forms_attachments_demo_surface,
    forms_attachments_demo_surface_invariant_failures,
)
from nativeforge.services.package_export_preview_assembler_service import (
    build_package_export_preview_demo_surface,
    package_export_preview_demo_surface_invariant_failures,
)
from nativeforge.services.proposal_qa_gate_service import (
    ai_governance_demo_surface_invariant_failures,
    build_ai_governance_demo_surface,
)
from nativeforge.services.sc_monday_demo_bridge_service import (
    bridge_payload_invariant_failures,
    build_sc_customer_demo_bridge_payload,
)

SCHEMA_VERSION = "nf_no_fail_invariant_suite_v1"


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def run_no_fail_invariant_suite() -> dict[str, Any]:
    """Aggregate hard claim boundaries across Gate 03–05 demo surfaces."""
    fails: list[str] = []
    checks: dict[str, Any] = {}

    bridge = build_sc_customer_demo_bridge_payload()
    bf = bridge_payload_invariant_failures(bridge)
    checks["bridge"] = bf
    fails.extend([f"bridge:{x}" for x in bf])

    if bridge.get("final_eligibility_claim_allowed") is not False:
        fails.append("final_eligibility_claim_allowed")

    gov = build_ai_governance_demo_surface()
    gf = ai_governance_demo_surface_invariant_failures(gov)
    checks["ai_governance"] = gf
    fails.extend([f"ai_gov:{x}" for x in gf])
    if gov.get("qa_passed") is True:
        fails.append("qa_passed_true")
    if gov.get("export_allowed") is True:
        fails.append("export_allowed_true")
    if gov.get("submission_allowed") is True:
        fails.append("submission_allowed_true")

    controlled = build_controlled_drafting_demo_surface()
    cf = controlled_drafting_demo_surface_invariant_failures(controlled)
    checks["controlled_drafting"] = cf
    fails.extend([f"controlled:{x}" for x in cf])
    if controlled.get("complete_proposal_claimed") is True:
        fails.append("complete_proposal_claimed")
    if controlled.get("submission_ready_claimed") is True:
        fails.append("controlled_submission_ready")

    export = build_package_export_preview_demo_surface()
    ef = package_export_preview_demo_surface_invariant_failures(export)
    checks["package_export_preview"] = ef
    fails.extend([f"export:{x}" for x in ef])
    if export.get("final_export_claimed") is True:
        fails.append("final_export_claimed")
    if export.get("export_allowed") is True:
        fails.append("export_preview_allowed_true")

    forms = build_forms_attachments_demo_surface()
    ff = forms_attachments_demo_surface_invariant_failures(forms)
    checks["forms_attachments"] = ff
    fails.extend([f"forms:{x}" for x in ff])
    if forms.get("form_completion_claimed") is True:
        fails.append("form_completion_claimed")
    if forms.get("attachment_persistence_claimed") is True:
        fails.append("attachment_persistence_claimed")

    feedback = build_feedback_loop_demo_surface()
    fbf = feedback_loop_demo_surface_invariant_failures(feedback)
    checks["feedback_loop"] = fbf
    fails.extend([f"feedback:{x}" for x in fbf])
    if feedback.get("slack_live_sent_claimed") is True:
        fails.append("slack_live_sent_claimed")
    if feedback.get("persistence_claimed") is True:
        fails.append("feedback_persistence_claimed")

    collab = build_collaboration_dark_flag_contract()
    colf = collaboration_dark_flag_invariant_failures(collab)
    checks["collaboration"] = colf
    fails.extend([f"collab:{x}" for x in colf])

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "campaign_block": 17,
            "overall_status": "PASS" if not fails else "FAIL",
            "fails": fails,
            "checks": checks,
            "invariants_proven": [
                "no_final_eligibility_claim",
                "no_submission_ready_claim",
                "no_complete_proposal_claim",
                "no_final_export_claim",
                "no_form_completion_claim",
                "no_attachment_persistence_claim",
                "export_blocked_while_qa_human_review_incomplete",
                "collaboration_dark_off",
                "slack_sent_not_faked",
                "feedback_persistence_false",
            ],
            "pen_test_passed_claimed": False,
        }
    )
