# 452 — Gate 81D: Amendment / version detector contract

`src/nativeforge/services/nofo_amendment_detector_service.py`
Schema `nf_nofo_amendment_detector_v1`.

Decides what *kind* of notice a document is, and emits the evidence
`opportunity_freshness_service` needs to decide whether the opportunity is still
current.

## Two axes, deliberately not merged

```text
notice status   what happened to this document
freshness       is this grant still open
```

They overlap at `amended` and `superseded` and diverge everywhere else. Gate 76D
already owns freshness and owns it well; this module does not re-answer any of
its questions.

## Statuses

```text
original  amended  corrected  supplemented  extended
cancelled  withdrawn  superseded  unknown
```

`CURRENT_NOTICE_STATUSES` is `{original, amended, corrected, supplemented,
extended}`. `NON_CURRENT_NOTICE_STATUSES` is derived by difference, so a status
added later is non-current until someone deliberately includes it.

`VISIBLE_NOTICE_STATUSES` is all nine.

### Precedence

Most consequential wins:

```text
cancelled > withdrawn > superseded > extended > corrected > supplemented > amended
```

A cancelled notice that was also amended is **cancelled**. Reporting it as
amended would put a dead programme back in front of a customer.

## Projection onto freshness

```text
original      -> None        (no opinion; dates decide, which is correct)
amended       -> amended
corrected     -> amended     lossy
supplemented  -> amended     lossy
extended      -> amended
cancelled     -> expired     lossy
withdrawn     -> expired     lossy
superseded    -> superseded
unknown       -> unknown
```

Freshness has no word for "cancelled". Nothing expired — the funder pulled it —
but both are non-current, so `expired` is the closest honest landing. The loss
is recorded (`projection_lossy`) and surfaced as a reason rather than hidden.
This is the same canonical-plus-projection shape Gate 79B used for funding
lanes.

Two invariants hold the line:

- a projection must stay inside `FRESHNESS_STATES`;
- **no non-current status may project onto a state in `CURRENT_STATES`.**

## Evidence requirements

`EVIDENCE_REQUIRED_STATUSES` = `{amended, corrected, supplemented, extended,
cancelled, withdrawn}`.

A status in that set with no cited quote falls back to `unknown` — not to the
status we suspected. A notice we merely suspect was amended is a notice we have
not read. Every piece of status evidence must carry a valid span and non-empty
quote, checked by invariant.

When the Gate 81B extraction is supplied, cues found inside a detected
`amendment` section are preferred over the same word in a summary paragraph, and
the reason records which happened.

## Deadline extension

`extended` emits `extension_evidence` in the kinds
`opportunity_freshness_service` already accepts —
`amendment_notice_url` when a notice URL exists, otherwise
`operator_verified_extension`. An invariant rejects any kind outside
`EXTENSION_EVIDENCE_KINDS`, and rejects extension evidence attached to a
non-extended notice.

Version labels are read from `Amendment No. 2`, `Version 3`, `Revision 1`, `v2`.
A caller-declared version always wins over a parsed one.

## Cancelled and withdrawn

They do not disappear. `visible` is `True` for every status and an invariant
fails any result that hides one. A cancelled notice is often the most useful
thing we can show a customer — *this programme will not be awarded, stop
planning around it* — and a grant that vanishes looks like a grant we never
found.

`is_current_notice` is `False`, and an invariant fails any cancelled or
withdrawn notice reported as current.

## Supersession

Delegated to `opportunity_freshness_service.evaluate_supersession`, which
already requires same source, funder and title **plus** evidence from
`SUPERSESSION_EVIDENCE_KINDS`. This module contributes the evidence it read out
of the notice; it does not re-decide lineage.

Agencies re-post similar programmes annually. Treating a new fiscal year's NOFO
as superseding last year's would erase a record that is still the correct
reference for an in-flight application.

The older notice always remains visible, marked `superseded`, which is not in
`CURRENT_STATES`.

## Why no live coverage is claimed

Nothing here fetches. `live_fetch_performed`, `amendment_asserted_without_evidence`
and `cancelled_notice_hidden` are hardcoded `False` and invariant-checked.

## What still needs primary-source verification

Cue phrase lists are conservative and English-only, and they have been exercised
against synthetic fixtures only. Real amendment notices vary far more. Anything
unrecognised yields `original` or `unknown` with a reason — never a confident
wrong answer — but a real corpus will be needed before this can be trusted
unattended.
