"""Attribution notices for the Gate 171 adapters.

Gate 166I made the required notice resolvable by `adapter_key` rather than
imported from one publisher's module, and said the test of that would be the
day a second source declared its own. This is that day, and the shape it
predicted is the shape that worked: a contract row plus a module, and no edit
to the generic resolver.

One module serves both adapters because the verifier resolves the required
text through three named constants, and two adapters can each have their own
set. Splitting them into two files would duplicate the builder for no gain.

## Declaring is not satisfying

A notice declared here is the text the publisher is owed. Whether it was
actually recorded on a customer-visible surface is verified
character-for-character against what the activation stored - one edited
character and the fact returns to `missing`.
"""

from __future__ import annotations

import json
from typing import Any

SCHEMA_VERSION = "nf_gate171_attribution_v1"

# ---- source #2: BIA program page -----------------------------------

BIA_ATTRIBUTION_TEXT = (
    "Source: Bureau of Indian Affairs, U.S. Department of the Interior"
)
BIA_MANIFEST_BLOCK_KEY = "source_attribution"
BIA_MANIFEST_NOTICE_KEY = "bia_program_page_notice"

# ---- source #3: Federal Register documents -------------------------

FEDERAL_REGISTER_ATTRIBUTION_TEXT = (
    "Source: Office of the Federal Register, National Archives and "
    "Records Administration"
)
FEDERAL_REGISTER_MANIFEST_BLOCK_KEY = "source_attribution"
FEDERAL_REGISTER_MANIFEST_NOTICE_KEY = "federal_register_notice"


def _json_safe(value: Any) -> Any:
    return json.loads(json.dumps(value, default=str, sort_keys=True))


def _build(
    *,
    required_text: str,
    block_key: str,
    notice_key: str,
    trust_manifest: Any = None,
    rendered_ui_text: Any = None,
    surfaces_present: list[Any] | None = None,
) -> dict[str, Any]:
    """Verbatim comparison, and nothing cleverer.

    No normalisation, no case folding, no whitespace collapsing. A notice that
    needs to be normalised before it matches is a notice that was edited, and
    the whole point of a verbatim requirement is that editing it is visible.
    """
    manifest = trust_manifest if isinstance(trust_manifest, dict) else {}
    block = manifest.get(block_key)
    recorded = block.get(notice_key) if isinstance(block, dict) else None

    matches = isinstance(recorded, str) and recorded == required_text
    surfaces = [str(s) for s in (surfaces_present or [])]
    # `service_constant` alone is not customer visible. A constant in the
    # codebase is not a notice anybody reading the product can see.
    customer_visible = matches and "runtime_payload" in surfaces

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            # A member of ATTRIBUTION_STATUSES. `present_verbatim` reads the
            # same to a human and is not in the vocabulary, so it normalised
            # to `unknown` - a verified notice reported as an unanswered
            # question, which is exactly the failure a vocabulary exists to
            # prevent and exactly the one it caught.
            "attribution_status": "present_and_verbatim" if matches else "missing",
            "attribution_is_customer_visible": bool(customer_visible),
            "notice_matches_verbatim": bool(matches),
            "surfaces_present": sorted(set(surfaces)),
            "required_text_length": len(required_text),
            "recorded_text_length": len(recorded) if isinstance(recorded, str) else 0,
            "rendered_ui_text_checked": rendered_ui_text is not None,
        }
    )


def build_bia_attribution_contract(
    *,
    trust_manifest: Any = None,
    rendered_ui_text: Any = None,
    surfaces_present: list[Any] | None = None,
) -> dict[str, Any]:
    return _build(
        required_text=BIA_ATTRIBUTION_TEXT,
        block_key=BIA_MANIFEST_BLOCK_KEY,
        notice_key=BIA_MANIFEST_NOTICE_KEY,
        trust_manifest=trust_manifest,
        rendered_ui_text=rendered_ui_text,
        surfaces_present=surfaces_present,
    )


def build_federal_register_attribution_contract(
    *,
    trust_manifest: Any = None,
    rendered_ui_text: Any = None,
    surfaces_present: list[Any] | None = None,
) -> dict[str, Any]:
    return _build(
        required_text=FEDERAL_REGISTER_ATTRIBUTION_TEXT,
        block_key=FEDERAL_REGISTER_MANIFEST_BLOCK_KEY,
        notice_key=FEDERAL_REGISTER_MANIFEST_NOTICE_KEY,
        trust_manifest=trust_manifest,
        rendered_ui_text=rendered_ui_text,
        surfaces_present=surfaces_present,
    )
