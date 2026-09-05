"""Gate 142C: render a digest into a deliverable shape, and send it nowhere.

## What "deliverable shape" means

A subject line, a plain-text body, a content hash and a byte length. That is
what a provider would be handed. Producing it proves the digest can *become* an
email, which is a different and smaller claim than that an email was sent.

```text
subject      one line, bounded, never a mailbox
body         plain text. No HTML, because an HTML digest needs a template, a
             sanitiser and a link-tracking decision, and none of those are this
             gate's question.
render_hash  sha256 of the body. Two runs of the same digest render the same
             bytes, which is what makes "already recorded" answerable.
```

## Nothing in the render is a promise

Every uncertainty the digest carried survives into the text. An item whose
eligibility is `unknown` says so in the body; an unverified deadline is written
as unverified. A digest that rounded an `unknown` up to a date on its way into
an email would be the fabrication the whole eligibility contract exists to
prevent, and an email is the worst place for it because it is the copy the
tenant keeps.

## No recipient appears in a render

The renderer takes a digest and returns text. It has no recipient parameter,
so a mailbox cannot end up in a subject line, a greeting, or a body — and the
delivery queue that stores this render stores a hash of it, not the text.

## Sent nowhere

No smtplib, no socket, no HTTP client, no provider. The body is a string that
is returned, hashed and measured. A test parses this module for imports.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

SCHEMA_VERSION = "nf_digest_delivery_renderer_v1"

#: A subject line is a header. Providers truncate around here and a longer one
#: is a line nobody reads the end of.
MAX_SUBJECT_LENGTH = 160

#: A digest body that needs more than this is a digest that needed a link.
MAX_BODY_BYTES = 256 * 1024

#: Items written out in full. Beyond this the body says how many more there
#: are rather than growing without bound - a hundred-item email is a report
#: nobody finishes.
MAX_RENDERED_ITEMS = 25

#: Statuses that mean nobody established the fact. They must survive the
#: render, in words, rather than being dropped or rounded.
UNRESOLVED_STATUSES: frozenset[str] = frozenset(
    {"unknown", "needs_human_review", "unsupported"}
)

#: What every render carries. Declared so a test can assert a real render
#: against it rather than against a reader's memory.
RENDER_FIELDS: tuple[str, ...] = (
    "subject_line",
    "body_text",
    "body_render_hash",
    "body_byte_length",
    "items_total",
    "items_visible",
    "items_rendered",
    "items_with_unresolved_eligibility",
    "items_with_unverified_deadlines",
    "cadence",
    "digest_period_key",
    "deliverable",
)

#: Words a digest email may never contain. Each is a claim this system cannot
#: support, and an email is the copy a tenant keeps.
FORBIDDEN_CLAIMS: tuple[str, ...] = (
    "you are eligible",
    "you are not eligible",
    "guaranteed",
    "you will receive",
    "apply now",
    "act now",
    "deadline confirmed",
)


def _json_safe(x: Any) -> Any:
    json.dumps(x)
    return x


def body_render_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def digest_period_key(*, cadence: Any, period_start: Any, period_end: Any) -> str:
    """The handle that makes "already recorded for this period" answerable.

    Built from the cadence and the period rather than from a timestamp, so two
    renders of the same week's digest agree - which is what the delivery
    queue's unique index needs in order to stop a tenant being recorded twice
    for one digest.
    """
    return "|".join(
        (
            str(cadence or "unknown").strip().lower(),
            str(period_start or "unknown").strip(),
            str(period_end or "unknown").strip(),
        )
    )


def _verb(count: int) -> str:
    """ "1 needs" and "2 need". This is the copy a tenant keeps."""
    return "needs" if count == 1 else "need"


def _have(count: int) -> str:
    return "has" if count == 1 else "have"


def _item_line(item: dict[str, Any]) -> str:
    """One item, with its uncertainty intact."""
    title = str(item.get("title") or "untitled opportunity").strip()
    source = str(item.get("source") or "unknown source").strip()

    eligibility = str(item.get("eligibility_status") or "unknown")
    if eligibility in UNRESOLVED_STATUSES:
        eligibility_text = f"eligibility {eligibility.replace('_', ' ')}"
    else:
        eligibility_text = f"eligibility {eligibility}"

    if item.get("due_date_verified") and item.get("due_date"):
        due_text = f"due {item['due_date']}"
    elif item.get("due_date"):
        # A date nobody verified is written as one nobody verified.
        due_text = f"due {item['due_date']} (not verified)"
    else:
        due_text = "no verified deadline"

    action = str(item.get("recommended_action") or "review").replace("_", " ")

    lines = [
        f"- {title}",
        f"    source: {source}",
        f"    {eligibility_text}; {due_text}",
        f"    next step: {action}",
    ]
    blockers = [str(b) for b in (item.get("blockers") or [])]
    if blockers:
        lines.append(f"    needs review: {', '.join(sorted(blockers))}")
    return "\n".join(lines)


def render_digest_for_delivery(
    *, digest: dict[str, Any] | None = None, organization_label: Any = None
) -> dict[str, Any]:
    """Render one digest into the shape a provider would be handed.

    Takes no recipient. A mailbox cannot reach a subject line or a body from
    here because there is no parameter carrying one.
    """
    preview = digest or {}
    blocked: list[str] = []

    items = list(preview.get("items") or [])
    items_total = int(preview.get("items_total") or 0)
    items_visible = int(preview.get("items_visible") or len(items))
    cadence = str(preview.get("cadence") or "unknown").strip().lower()

    if preview.get("blocked_reasons"):
        # A digest that was refused has no content to render, and rendering
        # one anyway would produce an email about nothing.
        blocked.append("digest_was_not_produced")
    if not items:
        blocked.append("digest_has_no_items_to_render")

    period_key = digest_period_key(
        cadence=cadence,
        period_start=preview.get("period_start"),
        period_end=preview.get("period_end"),
    )

    label = str(organization_label or "your organization").strip()
    unresolved = int(preview.get("items_with_unresolved_eligibility") or 0)
    unverified = int(preview.get("items_with_unverified_deadlines") or 0)

    subject = f"{cadence.capitalize()} grant digest: {items_visible} matched"
    if len(subject) > MAX_SUBJECT_LENGTH:
        subject = subject[:MAX_SUBJECT_LENGTH]

    rendered = items[:MAX_RENDERED_ITEMS]
    sections: list[str] = [
        f"{cadence.capitalize()} matched-notice digest for {label}.",
        "",
        (
            f"{items_visible} of {items_total} matched notices are shown. "
            f"{unresolved} {_verb(unresolved)} a human to settle eligibility "
            f"and {unverified} {_have(unverified)} no verified deadline."
        ),
        "",
    ]
    sections.extend(_item_line(item) for item in rendered)
    if len(items) > MAX_RENDERED_ITEMS:
        sections.append("")
        sections.append(
            f"{len(items) - MAX_RENDERED_ITEMS} further matched notices are not "
            "listed here."
        )

    suppressed = int(preview.get("items_suppressed") or 0)
    if suppressed:
        # A tenant is told something was withheld. A digest that silently
        # dropped items would be a digest nobody could audit.
        sections.extend(
            [
                "",
                f"{suppressed} notice(s) are hidden because a pursuit is under "
                "way. Nothing was deleted.",
            ]
        )

    sections.extend(
        [
            "",
            "This digest is assembled from recorded snapshots, not from live "
            "checks of any funder's site. Verify every deadline against the "
            "notice before relying on it.",
        ]
    )
    caveats = [str(c) for c in (preview.get("caveats") or [])]
    if caveats:
        sections.append("")
        sections.append("Known limitations of this digest:")
        sections.extend(f"  - {caveat}" for caveat in sorted(caveats))

    body = "\n".join(sections)
    body_bytes = body.encode("utf-8")
    if len(body_bytes) > MAX_BODY_BYTES:
        blocked.append("rendered_body_exceeds_the_maximum")

    lowered = body.lower()
    for claim in FORBIDDEN_CLAIMS:
        if claim in lowered:
            blocked.append(f"rendered_body_makes_a_forbidden_claim:{claim}")

    return _json_safe(
        {
            "schema_version": SCHEMA_VERSION,
            "subject_line": subject,
            "body_text": body,
            "body_render_hash": body_render_hash(body),
            "body_byte_length": len(body_bytes),
            "items_total": items_total,
            "items_visible": items_visible,
            "items_rendered": len(rendered),
            "items_with_unresolved_eligibility": unresolved,
            "items_with_unverified_deadlines": unverified,
            "items_suppressed": suppressed,
            "cadence": cadence,
            "digest_period_key": period_key,
            "deliverable": not blocked,
            "max_subject_length": MAX_SUBJECT_LENGTH,
            "max_body_bytes": MAX_BODY_BYTES,
            "max_rendered_items": MAX_RENDERED_ITEMS,
            # Constants. Rendering is not delivering.
            "recipient_in_render": False,
            "html_rendered": False,
            "tracking_pixels": 0,
            "links_rewritten": 0,
            "provider_contacted": False,
            "emails_sent": 0,
            "send_attempted": False,
            "blocked_reasons": sorted(set(blocked)),
        }
    )


def render_invariant_failures(result: dict[str, Any]) -> list[str]:
    """What must never be true of a render."""
    fails: list[str] = []

    missing = [field for field in RENDER_FIELDS if field not in result]
    if missing:
        fails.append(f"render_missing_fields:{missing}")

    for field in (
        "recipient_in_render",
        "html_rendered",
        "provider_contacted",
        "send_attempted",
    ):
        if result.get(field):
            fails.append(f"claimed:{field}")
    for field in ("emails_sent", "tracking_pixels", "links_rewritten"):
        if result.get(field):
            fails.append(f"nonzero:{field}")

    body = str(result.get("body_text") or "")
    if body:
        if result.get("body_render_hash") != body_render_hash(body):
            fails.append("render_hash_does_not_match_the_body")
        if result.get("body_byte_length") != len(body.encode("utf-8")):
            fails.append("byte_length_does_not_match_the_body")
        lowered = body.lower()
        for claim in FORBIDDEN_CLAIMS:
            if claim in lowered and result.get("deliverable"):
                fails.append(f"deliverable_body_makes_a_forbidden_claim:{claim}")
        # A mailbox in a body is a recipient in a render.
        if "@" in body:
            fails.append("rendered_body_contains_an_address_shaped_string")

    if len(str(result.get("subject_line") or "")) > MAX_SUBJECT_LENGTH:
        fails.append("subject_line_over_the_maximum")

    if result.get("deliverable") and result.get("blocked_reasons"):
        fails.append("deliverable_alongside_blockers")
    if not result.get("deliverable") and not result.get("blocked_reasons"):
        fails.append("not_deliverable_and_nothing_blocked_it")

    # The counts must add up the way the digest's own invariant requires.
    total = int(result.get("items_total") or 0)
    visible = int(result.get("items_visible") or 0)
    suppressed = int(result.get("items_suppressed") or 0)
    if total and visible + suppressed != total:
        fails.append(f"items_do_not_add_up:{visible}+{suppressed}!={total}")

    return fails
