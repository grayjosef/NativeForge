"""Gate 145F: the controlled beta decision, as committed files.

Deterministic and hermetic. Every measurement reads services that contact
nothing; no pilot is activated, no approval is granted, no capability flag
changes, and every artifact is scanned before it is returned.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from nativeforge.services.controlled_beta_readiness_decision_service import (
    CONFLATIONS,
    CONTROLLED_CUSTOMER_BETA,
    CUSTOMER_BETA_CONDITIONS,
    GO,
    HUMAN_APPROVALS,
    INTERNAL_DEMO_BETA,
    INTERNAL_DEMO_CONDITIONS,
    INTERNAL_DEMO_MUST_BE_FALSE,
    LIMITED_GO,
    NO_GO,
    PRODUCTION_ROLLOUT,
    SCOPES,
    TECHNICAL_BLOCKERS,
    UNSAFE_CLAIMS,
    build_controlled_beta_decision,
    decision_invariant_failures,
)

SCHEMA_VERSION = "nf_controlled_beta_gate145_artifact_v1"

ARTIFACT_DIR = "artifacts/controlled_beta_readiness_gate145"

ARTIFACT_FILES: tuple[str, ...] = (
    "controlled_beta_readiness_survey.json",
    "controlled_beta_decision_matrix.json",
    "internal_demo_beta_decision.json",
    "controlled_customer_beta_decision.json",
    "production_rollout_decision.json",
    "unsafe_claims_to_avoid.json",
    "human_approval_checklist.json",
    "technical_blockers_remaining.json",
    "next_block_after_gate145.md",
)

DEMO_ORGANIZATION_ID = "bbbbbbbb-cccc-dddd-eeee-ffffffffffff"
REAL_ORGANIZATION_ID = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

#: Every lane the full verifier battery proves. This is what the campaign
#: actually established across Gates 136-144.
FULL_BATTERY: dict[str, bool] = {
    "login_live": True,
    "customer_persistence_live": True,
    "awarded_operational_tracking": True,
    "tenant_digest_operational": True,
    "document_metadata_operational": True,
    "email_delivery_readiness": True,
    "source_monitoring_preflight_ready": True,
    "beta_onboarding_cockpit_route_live": True,
}

#: The gates that produced each operational lane, so a reader can find the
#: evidence rather than take this file's word for it.
LANE_PROVENANCE: dict[str, str] = {
    "login_live": "Gate 133",
    "customer_persistence_live": "Gate 138",
    "awarded_operational_tracking": "Gate 139",
    "tenant_digest_operational": "Gate 140",
    "document_metadata_operational": "Gate 141",
    "email_delivery_readiness": "Gate 142",
    "source_monitoring_preflight_ready": "Gate 143",
    "beta_onboarding_cockpit_route_live": "Gate 144",
}

CREDENTIAL_FIELDS: tuple[str, ...] = (
    "api_key",
    "secret",
    "token",
    "cookie",
    "session_cookie_value",
    "provider_subject",
    "client_secret",
    "code_verifier",
)

FORBIDDEN_MARKERS: tuple[str, ...] = (
    "set-cookie:",
    "GOCSPX-",
    "BEGIN PRIVATE KEY",
    "eyJ",
    "nf_session=",
    "AKIA",
    "65%",
)

#: The one file that lists prohibited claims by design, and is therefore exempt
#: from the marker scan. An inventory of what may not be said is not a saying
#: of it - the first version of this guard read "a 65% improvement in anything"
#: in the do-not-say list as a 65% claim.
#:
#: An exemption nobody checks is a hole, so `_assert_prohibitions_recorded`
#: requires the inventory to actually carry the prohibition.
CLAIM_INVENTORY_FILE = "unsafe_claims_to_avoid.json"

#: Markers whose PRESENCE in the inventory is required, because the inventory
#: exists to record that they are forbidden.
REQUIRED_IN_THE_INVENTORY: tuple[str, ...] = ("65%",)


def _assert_prohibitions_recorded(body: str) -> None:
    """The do-not-say list must actually say what must not be said."""
    lowered = body.lower()
    for marker in REQUIRED_IN_THE_INVENTORY:
        if marker.lower() not in lowered:
            raise AssertionError(
                f"the unsafe-claim inventory no longer records {marker!r}"
            )


ADDRESS_SHAPE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _dump(obj: Any) -> str:
    return json.dumps(obj, indent=2, sort_keys=True) + "\n"


def build_controlled_beta_artifacts() -> dict[str, str]:
    """Every file, as text. Same input, same bytes, every time."""
    decision = build_controlled_beta_decision(**FULL_BATTERY)
    unaided = build_controlled_beta_decision()

    demo = decision["by_scope"][INTERNAL_DEMO_BETA]
    customer = decision["by_scope"][CONTROLLED_CUSTOMER_BETA]
    production = decision["by_scope"][PRODUCTION_ROLLOUT]
    measured = decision["measured_capabilities"]

    files: dict[str, str] = {}

    files["controlled_beta_readiness_survey.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "gate": "145",
            "question": "can NativeForge enter a controlled customer beta now?",
            "answer": {
                INTERNAL_DEMO_BETA: decision["internal_demo_beta"],
                CONTROLLED_CUSTOMER_BETA: decision["controlled_customer_beta"],
                PRODUCTION_ROLLOUT: decision["production_rollout"],
            },
            "operational_lanes": sorted(FULL_BATTERY),
            "lane_provenance": dict(LANE_PROVENANCE),
            "measured_capabilities": measured,
            "what_is_operational": sorted(FULL_BATTERY),
            "what_is_readiness_only": [
                "email_delivery_readiness",
                "source_monitoring_preflight_ready",
                "document_metadata_operational",
            ],
            "what_is_preview_only": ["tenant_digest"],
            "what_is_blocked": ["source_monitoring_live"],
            "what_requires_human_approval": [
                "customer_auth_live",
                "verified_operational_binding",
            ],
            "what_is_explicitly_not_production": [
                "controlled_customer_pilot",
                "production_rollout",
            ],
            "demo_organization": DEMO_ORGANIZATION_ID,
            "real_organization_touched": False,
            "real_organization_not_touched_because": (
                f"{REAL_ORGANIZATION_ID} was never authorized, and no route in "
                "this campaign reaches it"
            ),
            "improvement_claims": [],
        }
    )

    files["controlled_beta_decision_matrix.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "scopes": list(SCOPES),
            "by_scope": decision["by_scope"],
            "internal_demo_beta": decision["internal_demo_beta"],
            "controlled_customer_beta": decision["controlled_customer_beta"],
            "production_rollout": decision["production_rollout"],
            "with_no_evidence_supplied": {
                INTERNAL_DEMO_BETA: unaided["internal_demo_beta"],
                CONTROLLED_CUSTOMER_BETA: unaided["controlled_customer_beta"],
                PRODUCTION_ROLLOUT: unaided["production_rollout"],
            },
            "unaided_is_never_more_permissive": (
                unaided["internal_demo_beta"] != GO
                and unaided["production_rollout"] == NO_GO
            ),
            "conflations": decision["conflations"],
            "conflation_count": len(CONFLATIONS),
            "invariant_failures": decision_invariant_failures(decision),
        }
    )

    files["internal_demo_beta_decision.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": INTERNAL_DEMO_BETA,
            "decision": demo["decision"],
            "summary": demo["summary"],
            "required_conditions": list(INTERNAL_DEMO_CONDITIONS),
            "conditions_met": demo["conditions_met"],
            "conditions_missing": demo["conditions_missing"],
            "must_be_false": list(INTERNAL_DEMO_MUST_BE_FALSE),
            "all_must_be_false_are_false": not [
                name for name in INTERNAL_DEMO_MUST_BE_FALSE if measured.get(name)
            ],
            "constraints": demo["constraints"],
            "blockers": demo["blockers"],
            "lane_provenance": dict(LANE_PROVENANCE),
        }
    )

    files["controlled_customer_beta_decision.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": CONTROLLED_CUSTOMER_BETA,
            "decision": customer["decision"],
            "summary": customer["summary"],
            "required_conditions": list(CUSTOMER_BETA_CONDITIONS),
            "conditions_met": customer["conditions_met"],
            "conditions_missing": customer["conditions_missing"],
            "constraints": customer["constraints"],
            "blockers": customer["blockers"],
            "is_unconditional_go": customer["decision"] == GO,
            "cannot_be_unconditional_go_because": (
                "customer_auth_live is false; no second real person has accepted "
                "an invite, and Gate 136 refused to fake one"
            ),
            "what_limited_go_permits": [
                "the demo organization, with fixture-labelled rows",
                "an operator walking a customer through the product",
            ],
            "what_limited_go_does_not_permit": [
                "a real customer signing in",
                "writing real customer data",
                "sending any email",
                "monitoring any live source",
                "storing any document bytes",
            ],
            "customer_auth_live": measured["customer_auth_live"],
            "verified_operational_binding": measured["verified_operational_binding"],
        }
    )

    files["production_rollout_decision.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "scope": PRODUCTION_ROLLOUT,
            "decision": production["decision"],
            "decision_is_always": NO_GO,
            "summary": production["summary"],
            "blockers": production["blockers"],
            "constraints": production["constraints"],
            "no_branch_returns_anything_else": True,
            "why": (
                "production is not the sum of the technical gates; it is those "
                "gates and somebody saying yes, and a service that could compute "
                "its way to GO would have mistaken one for the other"
            ),
            "production_approved": decision["production_approved"],
            "controlled_customer_pilot_activated": decision[
                "controlled_customer_pilot_activated"
            ],
        }
    )

    files["unsafe_claims_to_avoid.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "unsafe_claims": list(UNSAFE_CLAIMS),
            "unsafe_claim_count": len(UNSAFE_CLAIMS),
            "each_paired_with_a_true_statement": all(
                claim.get("true_statement") for claim in UNSAFE_CLAIMS
            ),
            "conflations": list(CONFLATIONS),
            "conflation_count": len(CONFLATIONS),
            "why_these_matter": (
                "each is something somebody could reasonably say after reading a "
                "green cockpit, and each is false today"
            ),
            "improvement_claims": [],
        }
    )

    files["human_approval_checklist.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "human_approvals": list(HUMAN_APPROVALS),
            "approval_count": len(HUMAN_APPROVALS),
            "none_is_automatable": True,
            "each_names_an_owner": all(a.get("owner") for a in HUMAN_APPROVALS),
            "each_says_why_not_automatable": all(
                a.get("why_not_automatable") for a in HUMAN_APPROVALS
            ),
            "approvals_granted_by_this_gate": 0,
        }
    )

    files["technical_blockers_remaining.json"] = _dump(
        {
            "schema_version": SCHEMA_VERSION,
            "technical_blockers": list(TECHNICAL_BLOCKERS),
            "blocker_count": len(TECHNICAL_BLOCKERS),
            "separated_from_human_approvals_because": (
                "an operator reading a blocker needs to know whether to write "
                "code or to make a decision"
            ),
            "each_names_what_it_blocks": all(
                b.get("blocks") for b in TECHNICAL_BLOCKERS
            ),
        }
    )

    files["next_block_after_gate145.md"] = _next_block(decision)

    for name, body in files.items():
        lowered = body.lower()
        if name == CLAIM_INVENTORY_FILE:
            # The inventory names the prohibitions; it does not make them.
            _assert_prohibitions_recorded(body)
        else:
            for marker in FORBIDDEN_MARKERS:
                if marker.lower() in lowered:
                    raise AssertionError(f"forbidden marker {marker!r} in {name}")
        for field in CREDENTIAL_FIELDS:
            if re.search(rf'"{re.escape(field)}"\s*:\s*"[^"]', lowered):
                raise AssertionError(f"field {field!r} carries a value in {name}")
        if ADDRESS_SHAPE.search(body):
            raise AssertionError(f"an address-shaped string reached {name}")

    return files


def _next_block(decision: dict[str, Any]) -> str:
    customer = decision["by_scope"][CONTROLLED_CUSTOMER_BETA]
    approvals = "\n".join(
        f"  {a['approval']:52s} -> {a['unlocks']}" for a in HUMAN_APPROVALS
    )
    technical = "\n".join(
        f"  {b['blocker']:44s} -> {b['blocks']}" for b in TECHNICAL_BLOCKERS
    )
    blockers = "\n".join(f"  {b}" for b in customer["blockers"])
    return f"""# Gate 145 — the answer, and what comes next

## The question

Can NativeForge enter a controlled customer beta now?

```text
internal / demo beta        {decision["internal_demo_beta"]}
controlled customer beta    {decision["controlled_customer_beta"]}
production rollout          {decision["production_rollout"]}
```

## Internal / demo beta: {decision["internal_demo_beta"]}

Every lane an internal operator needs is proved, by its own verifier, in the
demo organization, with fixture-labelled rows — and every capability flag that
would make that a lie is honestly false.

An operator can sign in, keep a tenant profile, record awarded grants and their
requirements and proof events and document references, preview a weekly digest,
suppress an item into a pursuit with an audit trail, rehearse a digest delivery,
evaluate all 177 registry sources, and read a cockpit that says exactly what all
of that does and does not mean.

## Controlled customer beta: {decision["controlled_customer_beta"]}

Not because the software is unfinished. Because of this:

```text
{blockers}
```

Two are decisions a person makes and one is a boundary nobody has written. No
code change moves any of them, which is why they are listed as approvals rather
than as work.

**What LIMITED GO permits:** an operator walking a customer through the product,
in the demo organization, with fixture rows.

**What it does not:** a real customer signing in, real customer data, any email,
any live source, any stored document bytes.

## Production rollout: NO_GO

No branch in the decision service returns anything else. Production is not the
sum of the technical gates; it is those gates **and** somebody saying yes.

## The five things that must never be conflated

```text
email_delivery_readiness          is not  email_delivery
source_monitoring_preflight_ready is not  source_monitoring_live
document_metadata_operational     is not  document_body_storage_ready
customer_persistence_live         is not  customer_auth_live
the demo organization             is not  a customer organization
```

Each pair reads as the same thing to anyone who has not followed the gates, and
each is the difference between a true statement and a false one. Gates 141, 142,
143 and 138 exist in large part to keep them apart.

## Approvals somebody has to give

```text
{approvals}
```

## Work a later gate can do

```text
{technical}
```

## Recommended next block

**Gate 146–150: the customer identity block.** Everything else waits on it.

```text
146   the second-person invite, end to end, with a real person
      unlocks customer_auth_live, which four scopes are waiting on
147   the verified operational binding decision, recorded
148   a consent and data boundary model
      Gate 142 named this gap and deliberately did not fill it
149   digest persistence
      delivery intents are stored and name a digest nobody kept; a digest that
      cannot be re-read cannot be audited after a missed deadline
150   the controlled customer beta re-decision, with 146-149 established
```

The alternative orderings are worse. Activating email or object storage first
would give a customer nobody can sign in as a digest nobody consented to
receive; starting the terms reviews first is weeks of human work that unlocks a
source lane the customer cannot see yet.

## What this gate changed

Nothing. No lane's value moved, no capability was activated, no approval was
granted, and no pilot was started. It answered a question.
"""


def write_controlled_beta_artifacts(*, repo_root: Any = None) -> dict[str, Any]:
    """Write every file under ``ARTIFACT_DIR``, relative to ``repo_root``."""
    root = Path(repo_root) if repo_root is not None else Path()
    directory = root / ARTIFACT_DIR
    directory.mkdir(parents=True, exist_ok=True)

    files = build_controlled_beta_artifacts()
    for name, body in files.items():
        (directory / name).write_text(body, encoding="utf-8")

    return {
        "schema_version": SCHEMA_VERSION,
        "directory": str(directory),
        "files_written": sorted(files),
        "file_count": len(files),
    }


def controlled_beta_artifact_invariant_failures(
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

    return fails


#: Re-exported so tests and the verifier name one set of verdicts.
DECISION_VALUES: tuple[str, ...] = (GO, LIMITED_GO, NO_GO)
