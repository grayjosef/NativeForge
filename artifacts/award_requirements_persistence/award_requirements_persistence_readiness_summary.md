# Award requirements persistence readiness (Gate 125)

## What moved

```text
table                      nf_award_requirements (migration 0033)
columns                    32
repository operations      7
demo fixture cases         14
storable fixture cases     7
cases a calendar could use 9
```

Gate 108 built the requirement model, the calendar and the proof audit
and had nowhere to put a row. Gate 124 gave awards a table. This is the
other half.

## What did not move

```text
award requirements operational    false
operational awarded tracking      false
operational awarded recommended   false
document storage                  false
proof audit persistence           false
customer auth live                false
verified operational binding      false
production award requirements     0
production proof records          0
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

> NativeForge tracks your reporting deadlines.

It does not. Two tables exist, two repositories address them, and every
production write is refused because nobody can be authenticated as the
tenant a requirement would bind to. A deadline is the half somebody is
actually held to, and the promise that a missed one will be caught
needs a running system with a real award in it.

## The three boundaries this gate had to preserve

```text
projected burden   what a NOFO suggests will be required if you win
active obligation  what this award requires, now
unsupported        what a document nobody could read appeared to say
```

All three derive from `requirement_source` and none is an input. Gate
108 wrote that derivation; this gate persists it and refuses the
contradiction in the database.

Fixture cases recording a projection: 1.
Fixture cases that became an obligation: 0.

## An estimate is not a deadline

`DATE_CALCULABLE_STATUSES` is `verified` and `calculated`. An estimated
date is stored, shown as estimated, and never counted down to — and
neither is a date claimed by a document nobody could read.

## A reference is not a document

`proof_document_ref` holds a reference and there is no store behind it.
`document_storage_available` is false, `proof_audit_persistence_available`
is false, and a reference supplied without a store is refused by name.
