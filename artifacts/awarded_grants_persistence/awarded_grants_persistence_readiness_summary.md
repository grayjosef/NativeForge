# Awarded grants persistence readiness (Gate 124)

## What moved

```text
table                      nf_awarded_grants (migration 0032)
columns                    27
repository operations      6
demo fixture cases         11
storable fixture cases     4
```

Nine award services and roughly 3,800 lines of contract had nowhere to
put a row. They have one now.

## What did not move

```text
awarded grants lane operational   false
operational awarded tracking      false
customer auth live                false
verified operational binding      false
award requirements write path     false
production awarded grants created 0
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

> NativeForge tracks your awarded grants.

It does not. A table exists, a repository addresses it, and every
production write is refused because nobody can be authenticated as the
tenant an award would bind to. An award is a real obligation to a real
funder; the gap between storing one and tracking one is a promise that
a missed deadline will be caught, and nothing here makes that promise.

## The separation this gate had to preserve

```text
projected burden   what a NOFO suggests will be required if you win
active obligation  what this award requires, now
```

Gate 91 stamped every projection `is_active_obligation: False`. Gate
124 keeps `active_obligation_status` in its own column, derives it from
this award's own extraction status, and establishes it only when the
claim, established facts, a capable extraction and a live award all
hold. Fixture cases establishing an obligation: 0.
