"""Gate 142F: is digest delivery ready to rehearse? Measured, not declared.

## Two flags, and the whole gate is about keeping them apart

```text
email_delivery_readiness   can this system render a digest, validate a
                           recipient, record an intent and audit it?
                           TRUE for controlled_dev_demo.

email_delivery             does mail actually reach anybody?
                           FALSE, and nothing here can make it true.
```

Readiness is about the code. Delivery is about a provider, a decision and a
mailbox. Collapsing them is how a deployment starts mailing people the day
somebody pastes an API key into an environment file, and it is the same
separation Gate 141 made between `hermetic_fake_verified` and
`production_verified`.

An invariant fails if a passing dry run ever sets `email_delivery`.

## What readiness requires

```text
the digest renders into a deliverable shape
at least one recipient validates
an intent is recorded, org-anchored, with an audit event
the send-disabled blocker is explicit and named
no address is stored anywhere
no provider is contacted
tenant_digest_operational is true      there is nothing to deliver otherwise
customer_persistence_live is true
```

## What it explicitly does not require

```text
a configured provider           a rehearsal needs none, and requiring one
                                would make the readiness lane unreachable on
                                every deployment that has not chosen a vendor
send activation                 that is the thing readiness is NOT
a real recipient                a fixture recipient at a .invalid domain
                                proves the validation path
```

Both stated as fields rather than implied by their absence. An unsatisfiable
conjunct makes every "not ready" above it unfalsifiable — Gate 134F removed
exactly that from the customer-auth chain.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "nf_email_delivery_readiness_v1"

DELIVERY_ROUTE_MODULE = "src/nativeforge/api/digest_delivery_routes.py"

REQUIRED_DEPENDENCY = "require_demo_org_session"

CONTROLLED_SCOPE = "controlled_dev_demo"

SCOPE_NONE = "none"
SCOPE_CONTROLLED = CONTROLLED_SCOPE
SCOPE_PRODUCTION = "production"

READINESS_SCOPES: tuple[str, ...] = (SCOPE_NONE, SCOPE_CONTROLLED, SCOPE_PRODUCTION)

#: Modules that must exist and must import no mail library. `smtplib` ships
#: with Python, so "not installed" is not a guarantee available here the way it
#: was for boto3 in Gate 141 - the guarantee is that nothing imports it.
DELIVERY_MODULES: tuple[str, ...] = (
    "src/nativeforge/services/digest_delivery_renderer_service.py",
    "src/nativeforge/services/digest_recipient_validation_service.py",
    "src/nativeforge/services/digest_delivery_dry_run_queue_service.py",
    "src/nativeforge/services/email_provider_configuration_preflight_service.py",
)

MAIL_LIBRARIES: frozenset[str] = frozenset(
    {
        "smtplib",
        "email",
        "aiosmtplib",
        "sendgrid",
        "mailgun",
        "postmarker",
        "boto3",
        "httpx",
        "requests",
        "aiohttp",
        "socket",
        "urllib",
        "urllib3",
        "http",
    }
)

#: Claims this module never makes.
NOT_APPROVED: tuple[str, ...] = (
    "email_delivery",
    "production_email_delivery",
    "send_activation",
    "real_recipient_delivery",
    "provider_activation",
    "unsubscribe_handling",
    "bounce_handling",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def detect_delivery_route_module(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Does the delivery route module exist, and is it session-wired?

    ``repo_root`` is injectable so the absent branch is reachable without
    deleting a file. Parsed for `Depends(require_demo_org_session)` rather than
    searched as a substring: this campaign has found twelve probes reporting on
    a name instead of a capability.
    """
    root = repo_root if repo_root is not None else _repo_root()
    path = root / DELIVERY_ROUTE_MODULE
    if not path.is_file():
        return {
            "route_module": DELIVERY_ROUTE_MODULE,
            "route_module_available": False,
            "session_wired": False,
            "sends_no_email": True,
            "blocked_reasons": ["route_module_does_not_exist"],
        }

    body = path.read_text(encoding="utf-8", errors="replace")
    blocked: list[str] = []

    session_wired = bool(re.search(rf"Depends\(\s*{REQUIRED_DEPENDENCY}\s*\)", body))
    if not session_wired:
        blocked.append("route_module_does_not_depend_on_a_session_org_context")

    sends_no_email = not re.search(r"\bsend_message\b|\bsendmail\b|\bSMTP\b", body)
    if not sends_no_email:
        blocked.append("route_module_looks_like_it_sends_email")

    return _json_safe(
        {
            "route_module": DELIVERY_ROUTE_MODULE,
            "route_module_available": True,
            "session_wired": session_wired,
            "sends_no_email": sends_no_email,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def detect_mail_library_imports(*, repo_root: Path | None = None) -> dict[str, Any]:
    """Does any delivery module import something that could send mail?

    Parsed with `ast`, because a docstring naming `smtplib` is not an import
    and a probe that could not tell the difference would report on prose.
    """
    import ast

    root = repo_root if repo_root is not None else _repo_root()
    findings: dict[str, list[str]] = {}
    missing: list[str] = []

    for relative in DELIVERY_MODULES:
        path = root / relative
        if not path.is_file():
            missing.append(relative)
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        except SyntaxError:
            findings[relative] = ["module_does_not_parse"]
            continue
        imported: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(a.name.split(".")[0] for a in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                imported.add(node.module.split(".")[0])
        found = sorted(imported & MAIL_LIBRARIES)
        if found:
            findings[relative] = found

    return _json_safe(
        {
            "modules_checked": list(DELIVERY_MODULES),
            "modules_missing": sorted(missing),
            "mail_library_imports": findings,
            "any_mail_library_imported": bool(findings),
            "mail_libraries_watched": sorted(MAIL_LIBRARIES),
        }
    )


def build_email_delivery_readiness(
    *,
    preflight: dict[str, Any] | None = None,
    render_proof: dict[str, Any] | None = None,
    recipient_proof: dict[str, Any] | None = None,
    queue_proof: dict[str, Any] | None = None,
    audit_proof: dict[str, Any] | None = None,
    route_smoke: dict[str, Any] | None = None,
    tenant_digest_operational: bool | None = None,
    customer_persistence_live: bool | None = None,
    repo_root: Path | None = None,
) -> dict[str, Any]:
    """Is delivery ready to rehearse? Contacts nothing and sends nothing."""
    from nativeforge.services.email_provider_configuration_preflight_service import (
        build_email_provider_preflight,
        email_preflight_invariant_failures,
    )

    render = render_proof or {}
    recipients = recipient_proof or {}
    queue = queue_proof or {}
    audit = audit_proof or {}
    smoke = route_smoke or {}

    dry_run_passed = bool(
        render.get("deliverable")
        and recipients.get("deliverable_count")
        and queue.get("rows_written")
    )
    flight = (
        preflight
        if preflight is not None
        else build_email_provider_preflight(dry_run_passed=dry_run_passed)
    )

    module = detect_delivery_route_module(repo_root=repo_root)
    imports = detect_mail_library_imports(repo_root=repo_root)

    blocked: list[str] = []
    blocked.extend(f"route_module:{r}" for r in module["blocked_reasons"])
    blocked.extend(f"preflight:{r}" for r in email_preflight_invariant_failures(flight))

    if imports["any_mail_library_imported"]:
        blocked.append(
            "a_delivery_module_imports_a_mail_library:"
            + ",".join(sorted(imports["mail_library_imports"]))
        )
    if imports["modules_missing"]:
        blocked.append(
            "delivery_module_missing:" + ",".join(imports["modules_missing"])
        )

    # -- the four things a rehearsal has to prove ---------------------------
    render_ok = bool(render.get("deliverable"))
    recipients_ok = int(recipients.get("deliverable_count") or 0) > 0
    queue_ok = int(queue.get("rows_written") or 0) > 0
    audit_ok = bool(audit.get("audit_event_recorded"))
    blocker_explicit = bool(queue.get("blocked_reason"))

    if not render:
        blocked.append("no_render_proof_was_supplied")
    elif not render_ok:
        blocked.append("the_digest_did_not_render_into_a_deliverable_shape")
    if not recipients:
        blocked.append("no_recipient_proof_was_supplied")
    elif not recipients_ok:
        blocked.append("no_recipient_validated")
    if not queue:
        blocked.append("no_delivery_intent_was_recorded")
    elif not queue_ok:
        blocked.append("the_delivery_intent_was_not_written")
    if not audit:
        blocked.append("no_audit_proof_was_supplied")
    elif not audit_ok:
        blocked.append("no_audit_event_names_the_intent")
    if queue and not blocker_explicit:
        blocked.append("the_send_disabled_blocker_was_not_named")

    # -- what must not have happened ----------------------------------------
    addresses_stored = bool(
        queue.get("addresses_stored") or recipients.get("addresses_stored")
    )
    provider_contacted = bool(
        flight.get("provider_contacted")
        or queue.get("provider_contacted")
        or render.get("provider_contacted")
    )
    emails_sent = (
        int(flight.get("emails_sent") or 0)
        + int(queue.get("emails_sent") or 0)
        + int(render.get("emails_sent") or 0)
    )
    if addresses_stored:
        blocked.append("a_recipient_address_was_stored")
    if provider_contacted:
        blocked.append("a_provider_was_contacted")
    if emails_sent:
        blocked.append(f"email_was_sent:{emails_sent}")

    # -- the lanes this gate may not regress --------------------------------
    digest_live = (
        bool(tenant_digest_operational)
        if tenant_digest_operational is not None
        else False
    )
    persistence_live = (
        bool(customer_persistence_live)
        if customer_persistence_live is not None
        else False
    )
    if not digest_live:
        blocked.append("tenant_digest_is_not_operational")
    if not persistence_live:
        blocked.append("customer_persistence_is_not_live")

    if smoke:
        for name in (
            "delivery_routes_operational",
            "unauthenticated_refused",
            "cross_org_refused",
        ):
            if not smoke.get(name):
                blocked.append(f"smoke_did_not_prove:{name}")
        blocked.extend(f"smoke:{r}" for r in smoke.get("blocked_reasons") or [])

    readiness = bool(
        module["route_module_available"]
        and module["session_wired"]
        and module["sends_no_email"]
        and render_ok
        and recipients_ok
        and queue_ok
        and audit_ok
        and blocker_explicit
        and digest_live
        and persistence_live
        and not blocked
    )

    # `email_delivery` comes from the preflight and nowhere else. A second
    # answer to one question is the shape Gate 114 spent a gate collapsing.
    email_delivery = bool(flight.get("email_delivery"))

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "email_delivery_readiness": readiness,
            "email_delivery": email_delivery,
            "scope": SCOPE_CONTROLLED if readiness else SCOPE_NONE,
            "scopes": list(READINESS_SCOPES),
            "preflight_state": flight.get("state"),
            "provider_configured": bool(flight.get("provider_configured")),
            "send_activated": bool(flight.get("send_activated")),
            "digest_renders_for_delivery": render_ok,
            "recipient_validation_works": recipients_ok,
            "delivery_intent_recorded": queue_ok,
            "delivery_audit_event_created": audit_ok,
            "send_disabled_blocker": queue.get("blocked_reason"),
            "send_disabled_blocker_explicit": blocker_explicit,
            "tenant_digest_operational": digest_live,
            "customer_persistence_live": persistence_live,
            "route_module": module,
            "mail_library_imports": imports,
            # Named as fields, not implied. Requiring either would make the
            # readiness lane unreachable on every deployment without a vendor.
            "provider_required_for_readiness": False,
            "send_activation_required_for_readiness": False,
            "real_recipient_required_for_readiness": False,
            # Constants. No branch sets any of them.
            "provider_contacted": False,
            "emails_sent": 0,
            "send_attempted": False,
            "recipient_addresses_stored": False,
            "recipient_addresses_reported": False,
            "production_email_delivery": False,
            "customer_auth_live": False,
            "real_organization_touched": False,
            "not_approved": list(NOT_APPROVED),
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def delivery_readiness_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of an email delivery readiness result."""
    fails: list[str] = []

    scope = result.get("scope")
    if scope not in READINESS_SCOPES:
        fails.append(f"scope_not_recognised:{scope}")

    if result.get("email_delivery_readiness"):
        if scope != SCOPE_CONTROLLED:
            fails.append(f"ready_outside_the_scope:{scope}")
        for field in (
            "digest_renders_for_delivery",
            "recipient_validation_works",
            "delivery_intent_recorded",
            "delivery_audit_event_created",
            "send_disabled_blocker_explicit",
            "tenant_digest_operational",
            "customer_persistence_live",
        ):
            if not result.get(field):
                fails.append(f"ready_without:{field}")
        if result.get("blocked_reasons"):
            fails.append("ready_alongside_blockers")

    # The load-bearing separation of the whole gate.
    if result.get("email_delivery_readiness") and result.get("email_delivery"):
        if not result.get("send_activated"):
            fails.append("a_rehearsal_activated_email_delivery")
    if result.get("email_delivery") and not result.get("send_activated"):
        fails.append("email_delivery_without_send_activation")

    for field in (
        "provider_contacted",
        "send_attempted",
        "recipient_addresses_stored",
        "recipient_addresses_reported",
        "production_email_delivery",
        "customer_auth_live",
        "real_organization_touched",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")
    if result.get("emails_sent"):
        fails.append("nonzero:emails_sent")

    if result.get("provider_required_for_readiness"):
        fails.append("a_provider_was_required_for_a_rehearsal")
    if result.get("send_activation_required_for_readiness"):
        fails.append("send_activation_was_required_for_a_rehearsal")
    if result.get("real_recipient_required_for_readiness"):
        fails.append("a_real_recipient_was_required_for_a_rehearsal")

    imports = result.get("mail_library_imports") or {}
    if imports.get("any_mail_library_imported"):
        fails.append("a_delivery_module_imports_a_mail_library")

    missing = set(NOT_APPROVED) - set(result.get("not_approved") or [])
    if missing:
        fails.append(f"not_approved_list_lost_entries:{sorted(missing)}")

    if not result.get("email_delivery_readiness") and not result.get("blocked_reasons"):
        fails.append("not_ready_and_nothing_blocked_it")

    return fails
