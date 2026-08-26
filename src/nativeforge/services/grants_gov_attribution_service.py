"""Grants.gov attribution contract (Gate 93C).

The Grants.gov API terms require, verbatim:

    All services, which utilize or access the API, should display the following
    notice prominently within the application.

The notice is a **product precondition**, not a collector implementation
detail. A collector that fetches correctly and a UI that shows the results
without the notice is still non-compliant, so the check lives at the surface
where customers see data, not inside the fetch path.

## Verbatim means verbatim

``ATTRIBUTION_TEXT`` is compared with ``==``. Not normalized whitespace, not
case-folded, not "contains". A paraphrase that means the same thing is a
different string and fails, because the terms name a notice rather than an
idea. ``verify_attribution_text`` reports *how* a candidate differs so a
reviewer sees whether someone reflowed it or rewrote it.

## Docs are not a runtime surface

Gate 92 put this string in a Python constant and three markdown files. That
satisfied nothing: ``grep -ri "endorsed or certified" frontend/`` returned
nothing, so no customer could ever have seen it.

So ``ATTRIBUTION_SURFACES`` distinguishes where a string lives:

``runtime_payload``   in a response a customer's browser receives
``rendered_ui``       drawn on screen
``service_constant``  a Python constant
``documentation``     a markdown file

Only the first two count. ``attribution_is_customer_visible`` requires at least
one of them, and an invariant fails a contract that claims satisfaction from a
constant or a doc alone.

## The seam this wires to

``trust_surface_service.build_trust_manifest`` is a deterministic policy payload
served at ``/trust`` and rendered by ``TrustCenterCard``. It already carries
``submission_policy`` and ``ai_training_policy``; ``source_attribution`` belongs
beside them. This service reads that manifest and verifies the notice survived -
it does not build the manifest, so the check cannot pass by construction.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_grants_gov_attribution_v1"

# Verbatim, from the Grants.gov API Terms & Conditions. Compared with ==.
ATTRIBUTION_TEXT = (
    "This product uses the Grants.gov API but is not endorsed or certified by "
    "the U.S. Department of Health and Human Services."
)

# The manifest key the notice must appear under, and the block that holds it.
MANIFEST_BLOCK_KEY = "source_attribution"
MANIFEST_NOTICE_KEY = "grants_gov_notice"

ATTRIBUTION_SURFACES = frozenset(
    {"runtime_payload", "rendered_ui", "service_constant", "documentation"}
)

# Only these two put the notice in front of a customer. Derived affirmatively:
# the set of surfaces that count is named, never computed by removing the ones
# that do not.
CUSTOMER_VISIBLE_SURFACES = frozenset({"runtime_payload", "rendered_ui"})

VERIFICATION_RESULTS = frozenset(
    {"present_and_verbatim", "missing", "altered", "paraphrased", "unknown"}
)

# Sources whose output may not reach a customer without the notice.
GRANTS_GOV_SOURCE_IDS = frozenset(
    {
        "GRANTS-GOV-EXTRACT",
        "GRANTS-GOV-SEARCH2",
        "grants_gov_daily_extract",
        "grants_gov_search2_fetch",
    }
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def verify_attribution_text(candidate: Any) -> dict[str, Any]:
    """Compare a candidate against the required notice, and say how it differs."""
    if candidate is None:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "result": "missing",
                "matches_verbatim": False,
                "candidate_present": False,
                "difference": "no attribution string supplied",
                "fabricated": False,
            }
        )

    text = str(candidate)
    if text == ATTRIBUTION_TEXT:
        return _json_safe(
            {
                "schema_version": SCHEMA_VERSION,
                "result": "present_and_verbatim",
                "matches_verbatim": True,
                "candidate_present": True,
                "difference": None,
                "fabricated": False,
            }
        )

    if not text.strip():
        result, difference = "missing", "attribution string is empty"
    elif " ".join(text.split()) == " ".join(ATTRIBUTION_TEXT.split()):
        # Same words, different whitespace. Still not the required notice, but
        # a reviewer should know it was reflowed rather than rewritten.
        result, difference = "altered", "whitespace differs from the required notice"
    elif text.casefold() == ATTRIBUTION_TEXT.casefold():
        result, difference = "altered", "casing differs from the required notice"
    elif "grants.gov" in text.casefold():
        result, difference = (
            "paraphrased",
            "mentions Grants.gov but is not the required notice",
        )
    else:
        result, difference = "altered", "does not match the required notice"

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "result": result,
            "matches_verbatim": False,
            "candidate_present": True,
            "difference": difference,
            "fabricated": False,
        }
    )


def extract_attribution_from_manifest(manifest: Any) -> Any:
    """Pull the notice out of a trust manifest, or None. Reads only."""
    if not isinstance(manifest, dict):
        return None
    block = manifest.get(MANIFEST_BLOCK_KEY)
    if not isinstance(block, dict):
        return None
    return block.get(MANIFEST_NOTICE_KEY)


def build_attribution_contract(
    *,
    trust_manifest: Any = None,
    rendered_ui_text: Any = None,
    surfaces_present: list[Any] | None = None,
) -> dict[str, Any]:
    """Whether the notice is present, verbatim, and customer-visible."""
    from_manifest = extract_attribution_from_manifest(trust_manifest)
    manifest_check = verify_attribution_text(from_manifest)

    ui_check = (
        verify_attribution_text(rendered_ui_text)
        if rendered_ui_text is not None
        else None
    )

    declared = {
        str(s).strip()
        for s in (surfaces_present or [])
        if str(s).strip() in ATTRIBUTION_SURFACES
    }
    # A surface is only credited when the string on it actually verified.
    verified_surfaces: set[str] = set()
    if manifest_check["matches_verbatim"]:
        verified_surfaces.add("runtime_payload")
    if ui_check is not None and ui_check["matches_verbatim"]:
        verified_surfaces.add("rendered_ui")
    verified_surfaces |= declared & {"service_constant", "documentation"}

    customer_visible = bool(verified_surfaces & CUSTOMER_VISIBLE_SURFACES)

    if manifest_check["matches_verbatim"] or (
        ui_check is not None and ui_check["matches_verbatim"]
    ):
        status = "present_and_verbatim"
    elif manifest_check["result"] == "missing" and ui_check is None:
        status = "missing"
    else:
        status = (
            ui_check["result"]
            if ui_check is not None and ui_check["result"] != "missing"
            else manifest_check["result"]
        )

    blocked: list[str] = []
    if not customer_visible:
        blocked.append("attribution_not_customer_visible")
    if status != "present_and_verbatim":
        blocked.append(f"attribution_{status}")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "required_text": ATTRIBUTION_TEXT,
            "attribution_status": status,
            "manifest_check": manifest_check,
            "rendered_ui_check": ui_check,
            "surfaces_verified": sorted(verified_surfaces),
            "customer_visible_surfaces": sorted(
                verified_surfaces & CUSTOMER_VISIBLE_SURFACES
            ),
            "attribution_is_customer_visible": customer_visible,
            "attribution_satisfied": status == "present_and_verbatim"
            and customer_visible,
            "blocked_reasons": blocked,
            "gated_source_ids": sorted(GRANTS_GOV_SOURCE_IDS),
            "fabricated": False,
        }
    )


def grants_gov_output_may_be_customer_visible(
    *, source_id: Any, attribution_contract: dict[str, Any]
) -> dict[str, Any]:
    """May this source's output reach a customer? Grants.gov needs the notice."""
    sid = str(source_id) if source_id is not None else ""
    requires = sid in GRANTS_GOV_SOURCE_IDS
    satisfied = bool(attribution_contract.get("attribution_satisfied"))

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "source_id": sid,
            "attribution_required": requires,
            "attribution_satisfied": satisfied,
            "may_surface_customer_data": (not requires) or satisfied,
            "blocked_reasons": (
                [] if (not requires) or satisfied else ["grants_gov_attribution_absent"]
            ),
            "fabricated": False,
        }
    )


def attribution_invariant_failures(contract: dict[str, Any]) -> list[str]:
    fails: list[str] = []

    if contract.get("schema_version") != SCHEMA_VERSION:
        fails.append("schema_version_mismatch")
    if contract.get("fabricated") is not False:
        fails.append("fabricated_must_be_false")

    # The required text must survive verbatim inside the contract itself.
    if contract.get("required_text") != ATTRIBUTION_TEXT:
        fails.append("required_attribution_text_altered")

    status = contract.get("attribution_status")
    if status not in VERIFICATION_RESULTS:
        fails.append("attribution_status_out_of_vocabulary")

    for surface in contract.get("surfaces_verified") or []:
        if surface not in ATTRIBUTION_SURFACES:
            fails.append(f"attribution_surface_out_of_vocabulary:{surface}")

    # Docs and constants are not customer-visible surfaces.
    visible = set(contract.get("customer_visible_surfaces") or [])
    if visible - CUSTOMER_VISIBLE_SURFACES:
        fails.append("non_customer_surface_counted_as_visible")
    if contract.get("attribution_is_customer_visible") != bool(visible):
        fails.append("customer_visibility_disagrees_with_surfaces")

    # Satisfaction requires verbatim AND customer-visible, both.
    satisfied = contract.get("attribution_satisfied")
    if satisfied and status != "present_and_verbatim":
        fails.append("attribution_satisfied_without_verbatim_text")
    if satisfied and not contract.get("attribution_is_customer_visible"):
        fails.append("attribution_satisfied_from_a_non_customer_surface")
    if not satisfied and not contract.get("blocked_reasons"):
        fails.append("attribution_unsatisfied_without_a_reason")

    return fails
