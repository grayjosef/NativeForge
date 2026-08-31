# Award document store persistence readiness (Gate 127)

## What moved

```text
table                      nf_award_documents (migration 0035)
columns                    31
repository operations      9
capability lanes with schema  9 total
demo fixture cases         16
storable fixture cases     5
fixture documents stored   0
```

The `document_library_persistence` lane has existed since Gate 114 and
pointed at a table nobody built. It points at this one now.

## What did not move

```text
object store configured           false
body store mode                   unconfigured
document storage live             false
document store operational        false
requires document storage         true
operational awarded tracking      false
customer auth live                false
production document records       0
document bytes written            0
object store calls                0
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

> NativeForge stores your compliance documents.

It does not. Four tables exist and this one holds descriptions: a
title, a kind, a digest somebody supplied, and which award or
requirement or proof event the document belongs to. The document is
still wherever the Tribe put it.

`detect_body_store_mode()` reports `unconfigured`, so `object_key` is
refused on every row this repository can currently write, and
`document_storage_live` stays in the operational blocker list.

## Metadata is not content

```text
sha256_digest   64 hex characters describing a file never opened here
content_length  how many bytes it has, according to whoever said so
content_type    what kind of file it is, according to the same
object_key      where it would be, if there were anywhere
```

`content_verified` is a constant false. Verifying a digest means
reading bytes, and nothing in this lane reads any.

## What is refused, and why that is the point

```text
a key with no store       a path into nothing
a document with no owner  refused: at least one relationship required
a visible document on an  refused: showing a Tribe a document nobody
  unestablished fact        has established as theirs is how the wrong
                            file reaches the wrong government
archiving under legal     refused: a lawyer said it must not move
  hold
```
