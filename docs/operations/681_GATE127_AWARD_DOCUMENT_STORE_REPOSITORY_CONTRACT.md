# 681 — Gate 127: the award document store repository contract

What `nf_award_documents` is, what may enter it, and what it refuses.

## The table

```text
migration           0035_nf_award_documents        head 0034 -> 0035
columns             31
CHECK constraints   16
indexes              4
foreign keys         6
RLS policy           nf_award_documents_org_demo_scope     PostgreSQL only
rows                 0
document bytes       0
```

The RLS predicate is the one twenty-two other tables carry, unchanged:

```sql
organization_id = current_setting('app.current_org_id', true)::uuid
AND is_demo = current_setting('app.current_org_is_demo', true)::boolean
```

## What this is, and what it is not

```text
this        metadata about a Tribe's compliance documents
not this    the documents
```

No column holds bytes. No function opens a file. No import reaches an object
store SDK. Three tests assert it structurally: one checks the column names, one
parses the module for forbidden calls and imports, and one checks the signature
of `prepare_document_write` for any way to hand it a document.

```text
sha256_digest   64 hex characters describing a file never opened here
content_length  how many bytes it has, according to whoever said so
content_type    what kind of file it is, according to the same
object_key      where it would be, if there were anywhere
```

`content_verified` is a constant `False`. Verifying a digest means reading
bytes.

## The name this module does not have

The repository is `award_document_store_repository_service`, and deliberately
**not** `award_document_store_service`. Two probes watched for that exact name:

```text
spine     DOCUMENT_STORAGE: _module_importable("...award_document_store_service")
readiness document_storage_live = _module_importable("...same...")
```

Creating a file with that name — even an empty one — would have flipped
`DOCUMENT_STORAGE` true, cleared the last unmet prerequisite on
`award_requirements_persistence` and `proof_audit_persistence`, and let
`operational_awarded_recommended` go true. With zero bytes stored anywhere.

Both probes are gone. Doc 683 records what replaced them.

## Four identifiers, one authority, at least one relationship

```text
organization_id       UUID, FK organizations CASCADE, the RLS anchor
awarded_grant_id      UUID, FK nf_awarded_grants CASCADE, nullable
award_requirement_id  UUID, FK nf_award_requirements CASCADE, nullable
proof_event_id        UUID, FK ..._proof_events CASCADE, nullable
```

All three relationships optional, because an award-level document that no
requirement has claimed yet is ordinary. At least one required
(`ck_..._needs_a_relationship`), because a document attached to nothing is a
file in a drawer nobody can find.

All three join `FORBIDDEN_ANCHOR_NAMES` alongside `tenant_id`,
`customer_org_id` and `organization_profile_id`. Reaching the organization
through whichever of three joins happened to be populated would make this
table's policy depend on three other tables' policies **and on which one a
caller filled in**. Each is refused under its own named reason.

## object_key is refused unless a store exists

```text
object_store_configured false  ->  object_key, object_bucket and
                                   object_store_provider must all be absent
object_store_configured true   ->  a key may name a location
```

Four CHECK constraints enforce it, and `object_store_configured` is **bridged
from Gate 96's `detect_body_store_mode()`**, never accepted from a caller. It
reports `unconfigured`, so every document this repository can currently write is
a reference and nothing more.

A key with no store is a path into nothing, and downstream it reads as "the file
is at this location".

`document_status = 'stored'` needs both the flag and the key
(`ck_..._stored_needs_a_location`), because `stored` is the one status that
asserts bytes exist somewhere.

## The nine operations

```text
prepare_document_write            decides; touches no database
create_award_document             one INSERT, if prepare permits it
get_award_document                one row, anchored on organization_id
list_documents_for_award          one award's documents
list_documents_for_requirement    one requirement's
list_documents_for_proof_event    one proof event's
list_documents_for_organization   every document, across every relationship
archive_award_document            an UPDATE. Never a DELETE
validate_document_persistence     is what is stored fit to act on?
```

No operation returns a document's contents, because there are no contents to
return. The listings report `stored_count` and `metadata_only_count` separately:
what is retrievable is not the same as what is described.

## Legal hold refuses archive

```text
ck_nf_award_documents_legal_hold_refuses_archive
archive_award_document -> blocked_reasons: ["legal_hold_refuses_archive"]
```

Both, because a lawyer saying a document must not move is not a preference this
repository may weigh against tidiness, and archiving is the only lifecycle
operation this table has.

## customer_visible defaults false

Never derived — not from upload status, not from a digest, not from the document
being the Tribe's own. `visibility_inferred_from_upload` is a constant `False`
with an invariant behind it, and
`ck_..._visible_needs_established_facts` refuses visibility on an unestablished
`fact_status`.

A default of true shows a draft to the wrong person exactly once.

## The sixteen CHECK constraints

```text
kind / status / source / retention_class / fact_status   5 vocabularies
title_not_blank
needs_a_relationship
object_key_needs_a_configured_store
bucket_needs_a_configured_store
provider_needs_a_configured_store
version_needs_a_key
stored_needs_a_location
content_length_not_negative
digest_is_sha256_shaped
legal_hold_refuses_archive
visible_needs_established_facts
```

The Core `sa.Table` restates all sixteen. Gate 119C shipped a Core table with
the columns and none of the constraints; two tests compare the definitions by
name.

## Vocabularies bridged, and vocabularies added

```text
bridged   RETENTION_CLASSES  from raw_payload_store_contract_service
                             (retain_7_days .. retain_indefinite)
          FACT_STATUSES      from tenant_beta_profile_service
          object store mode  from raw_payload_body_store_contract_service
added     DOCUMENT_KINDS     13 values. Nothing existing describes a Tribe's
                             own filing
          DOCUMENT_STATUSES   7 values
          DOCUMENT_SOURCES    7 values
```

`vocabulary_invariant_failures()` refuses a retention set that has forked from
Gate 96's, and refuses `object_store_configured` disagreeing with the body-store
mode it is derived from.

## Archive, never delete

`rows_deleted` is a constant `0` and there is no DELETE path — asserted by
parsing the module, because Gate 123 found a substring search matching the
sentence that explains the absence.

## What a production write requires

```text
customer_auth_live              false
verified_operational_binding    false
```

The guard lists `write_document_library_item` in `LABEL_BOUND_OPERATIONS` for a
reason specific to this table: a document is filed against an award, a
requirement or a proof event, any of which may be the only relationship present,
and which tenant it belongs to is reachable only through the award's binding. It
is also the row that later names a bucket and a key.

```text
rows in the application database      0
production document records created   0
document bytes written                0
object store calls                    0
```

## What this gate did not build

**The object store.** `detect_body_store_mode()` reports `unconfigured` and
Gate 127 did not change that. The bytes still have nowhere to go, which is why
`document_storage_live` and the spine's `DOCUMENT_STORAGE` prerequisite both
stay false.
