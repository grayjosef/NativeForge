# Proof audit persistence readiness (Gate 126)

## What moved

```text
table                      nf_award_requirement_proof_events (migration 0034)
columns                    26
repository operations      8
capability lanes           9
demo fixture cases         14
storable fixture cases     5
```

Gate 108 built the proof/audit contract and had nowhere to put an
event. Gate 124 gave awards a table, Gate 125 gave requirements one,
and this is the third: what was filed, and what happened to it.

## What did not move

```text
proof audit operational           false
operational awarded tracking      false
operational awarded recommended   false
document storage                  false
customer auth live                false
verified operational binding      false
production proof records          0
rows deleted                      0
```

## Why the lane is still not operational

- `no_customer_auth_so_nobody_owns_the_row`

## What operational tracking still needs

- `operational_component_missing:customer_persistence_live`
- `operational_component_missing:document_storage_live`
- `operational_component_missing:requirement_extraction_live`
- `operational_component_missing:ui_available`
- `operational_component_missing:verified_operational_identity_binding`

## The sentence to refuse

> NativeForge keeps your compliance evidence.

It does not. Three tables exist and every production write is refused
because nobody can be authenticated as the tenant a filing would bind
to. `proof_document_ref` names a document and there is no store behind
it, so the evidence itself is still wherever the Tribe put it.

## What is retained, and why that is the point

```text
rejected    the proof reference stays on the row
superseded  the prior event stays, and the new one points back
archived    the row stays and leaves the active view
deleted     nothing. There is no delete path
```

A rejection that erased what was filed would make 'we rejected it'
indistinguishable from 'nothing was ever filed'. A supersession that
replaced the prior row would erase what was believed before the
correction. Both are opposite facts about the same Tribe, and both are
what a funder's auditor asks about.

## The vocabulary this gate extended

```text
bridged from Gate 108   ['attach_proof', 'mark_accepted', 'mark_rejected', 'mark_submitted', 'mark_waived', 'unknown']
added by Gate 126       ['audit_note_added', 'proof_needs_review', 'proof_requested', 'proof_superseded']
```

Gate 108's six actions all still map. An invariant refuses a vocabulary
that has dropped one, so the extension cannot become a replacement.
