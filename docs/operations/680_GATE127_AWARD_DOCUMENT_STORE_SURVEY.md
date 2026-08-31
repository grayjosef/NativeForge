# 680 — Gate 127A: award document store survey

Read before implementing. Every answer below was measured, not recalled.

## The eleven questions

```text
1  document/proof service contracts   4 document services, none a store
2  document store table/model/repo    none of the three
3  object storage client              yes - for raw payloads, not documents
4  metadata / bytes split             separate, and 0028 already settled the
                                      shape
5  which relationships                all three, all optional, at least one
6  organization_id on the metadata    yes, and this is not redundant
7  migration required                 yes - 0035
8  repository-backed without auth     yes, the Gate 120-126 shape
9  object store stays false           yes, and this gate must not move it
10 API route exists                   no
11 readiness change                   yes, and there is a live trap in the way
```

## The trap: a module name that flips two preconditions

The gate brief asks for `award_document_store_repository_service`. Two existing
probes look for a *different* name:

```text
spine _detect_preconditions()
  DOCUMENT_STORAGE: _module_importable(
      "nativeforge.services.award_document_store_service")

awarded_grants_requirements_readiness_service
  document_storage_live = _module_importable(
      "nativeforge.services.award_document_store_service")
```

Both are **module-existence proxies**. Creating a file called
`award_document_store_service` — even an empty one — flips both to `True`, which
would:

```text
DOCUMENT_STORAGE true   ->  award_requirements_persistence and
                            proof_audit_persistence lose their last unmet
                            prerequisite
                        ->  operational_out_of_sequence clears on both
                        ->  operational_awarded_recommended can go true
document_storage_live   ->  leaves the readiness blocker list
```

All of that with **zero bytes stored anywhere**. Gate 114 named this exact shape
when it found `customer_persistence_live` probing whether
`nativeforge.repositories.awarded_grant` imports — "a module-existence proxy
moving in the unsafe direction". Two of them survived in the document lane.

Gate 126A found the mirror image: a probe naming a module nobody built, so a
real capability stayed invisible. This is the same defect pointed the other way
— a probe that would report a capability nobody built.

**Decisions.** The repository is named `award_document_store_repository_service`,
which is what the brief asks for and is deliberately *not* the name either probe
watches. Both probes are then replaced with derived answers, because the module
name was never the question.

## The distinction this whole gate turns on

```text
document metadata persistence   a table saying which document, for what,
                                filed when, with what digest
document storage                somewhere the bytes actually live
```

Gate 127 builds the first. It does not build the second, and must not report it.

The spine's `DOCUMENT_STORAGE` prerequisite means "evidence has a home" — that
is the *bytes* question, and it is what `award_requirements_persistence` and
`proof_audit_persistence` are waiting on. Flipping it because a metadata table
exists would tell both lanes their evidence has somewhere to go when it does
not.

```text
after Gate 127
  document_store_repository_available   true   metadata has a home
  object_store_configured               false  bytes do not
  DOCUMENT_STORAGE (spine prerequisite) false  unchanged, and correctly so
  document_storage_live (readiness)     false  unchanged
```

## 3. An object store client already exists — for a different corpus

```text
s3_raw_payload_body_store_service          374 lines
raw_payload_body_store_contract_service    350
local_raw_payload_store_service            332
raw_payload_store_contract_service         268
object_storage_signed_url_service
object_storage_assembler_service
```

Measured today:

```text
detect_body_store_mode()            'unconfigured'
BODY_STORE_MODES                    unconfigured, local_dev_ignored,
                                    database_small_payload_only,
                                    s3_compatible_configured
PRODUCTION_CAPABLE_MODES            s3_compatible_configured
mode_is_production_capable(current) False
body_store_configured               False
settings_missing                    5
modules importing boto3/botocore    0
```

These serve **raw source payloads** — what NativeForge fetched from a funder's
site. An award document is the opposite direction: what a Tribe filed. Different
data, different retention, different customer visibility, and one of them is
subject to a legal hold.

But "is object storage configured?" is one question, and it already has an
answer. This gate **bridges** `detect_body_store_mode()` rather than writing a
second detector — three answers to one question is what Gate 114 spent a whole
gate collapsing.

`s3_raw_payload_body_store_service` also carries `PLACEHOLDER_CREDENTIAL_VALUES`
(20 values including `minioadmin` and the AWS documentation keys), which is a
real safety mechanism and is imported rather than restated.

## 4. Metadata and bytes are separate, and 0028 settled the shape

`nf_raw_source_payloads` has 31 columns and stores **no bytes**:

```text
response_body_hash        the digest
response_body_size_bytes  the length
content_type              the type
raw_payload_ref           a reference
```

Same shape here. `sha256_digest`, `content_length`, `content_type` and
`object_key` are metadata *about* a document; the document is not in the row and
is not in this repository.

One difference worth noting: `nf_raw_source_payloads` has **no
`organization_id` and no RLS**, because a fetched public NOFO belongs to nobody.
An award document belongs to exactly one Tribe, so this table has both.

## 1–2. Four document services, none of them a store

```text
grant_document_attachment_inventory_service   what a NOFO has attached
grant_document_text_extraction_service        reading those attachments
eligibility_fit_assessment_documentation_*    a readiness report
active_source_activation_m1_documentation_*   an operator roadmap
```

All pursuit-side or operational. None stores a customer's document.

```text
nf_award_documents                      does not exist
nf_document_library_items               does not exist
repositories/award_documents.py         does not exist
repositories/document_library.py        does not exist
services/award_document_store_service   does not exist
api/award_documents.py                  does not exist
```

## The second naming mismatch: the lane is already there

`document_library_persistence` is lane 6 of 9 and has been since Gate 114:

```text
table      nf_document_library_items      (the brief asks for nf_award_documents)
repo file  document_library.py            (does not exist)
repo mod   (none mapped)
contract   award_document_store_service   (does not exist)
blocked    no_table_declares_this_capability:nf_document_library_items
           no_repository_can_address_this_capability
           no_service_decides_what_may_be_written
           no_customer_auth_so_nobody_owns_the_row
```

So the lane exists under an older name, pointing at a table this gate is not
building. Left alone, building `nf_award_documents` would leave
`document_library_persistence` reporting false forever — the Gate 126A defect
one more time, in a third place.

**Decision.** One lane for one store. The lane id stays
`document_library_persistence` (the spine, the guard and several tests reference
it) and its three mappings are re-pointed at what this gate actually builds. A
tenth lane would be two lanes for one capability, which is worse.

The guard already has `write_document_library_item` mapped to it. It is not
label-bound; this gate adds it, because a document is filed against an award
whose binding nobody has verified.

## 5–6. Three relationships, all optional, and one anchor

```text
organization_id       UUID, FK organizations, the RLS predicate's left side
awarded_grant_id      UUID, FK nf_awarded_grants, nullable
award_requirement_id  UUID, FK nf_award_requirements, nullable
proof_event_id        UUID, FK nf_award_requirement_proof_events, nullable
```

All three nullable, and a CHECK requires at least one. A document with no
relationship is a file in a drawer nobody can find; a document forced to name
all three would refuse the ordinary case of an award-level document that no
requirement has claimed yet.

All three join `FORBIDDEN_ANCHOR_NAMES`. The RLS predicate reads
`organization_id`, so reaching it through a join — or worse, through three
different possible joins depending on which relationship happens to be set —
would make this table's policy depend on three other tables' policies.

## 7. Migration 0035

```text
0035_nf_award_documents    head 0034 -> 0035
```

## Vocabularies to bridge rather than restate

```text
RETENTION_POLICIES   retain_7_days, retain_90_days, retain_1_year,
                     retain_indefinite     raw_payload_store_contract_service
BODY_STORE_MODES     unconfigured, local_dev_ignored,
                     database_small_payload_only, s3_compatible_configured
FACT_STATUSES        verified, tenant_supplied, demo_fixture, unknown,
                     needs_human_review    tenant_beta_profile_service
PLACEHOLDER_CREDENTIAL_VALUES              s3_raw_payload_body_store_service
```

`document_kind` and `document_status` are new — nothing existing describes a
Tribe's own filing — and are named as added rather than bridged, the way Gate
126 named its four new event types.

## 10. No API route

Ten route decorators, none serving an award, a requirement, a proof event or a
document. **Skip it**, for the Gate 120/122/123/124/125/126 reasons plus one
specific to this gate:

```text
1  a read route needs a session to scope by, and /current-user 401s for
   everybody, so the authenticated branch is unreachable and untestable
2  the table will hold zero rows, so the route's only behaviour is
   `no_documents`
3  a document route is the one surface where "serves metadata" and "serves the
   file" are a single character apart in a handler. Building it while there is
   no store behind the metadata means the first version cannot be tested
   against the thing it must never do, and the test that would catch it is the
   one that needs the store to exist
```

## 11. What readiness may say afterwards

```text
document_library lane schema_available      false -> true
document_library lane repository_available  false -> true
document_library lane write_path_available  false -> true
document_library lane operational           false, unchanged
document_store_repository_available         absent -> true
object_store_configured                     false, unchanged
document_storage_live                       false, unchanged
DOCUMENT_STORAGE spine prerequisite         false, unchanged
ready_for_operational_awarded_tracking      false, unchanged
capability lanes with schema                5 -> 6
```

Tests referencing `document_storage` today: gate108 (4), gate110 (2), gate114
(4), gate124 (2), gate125 (14), gate126 (19). The two probes being replaced are
the reason several of those exist, so some will move — and each should move to a
*derived* form rather than a repointed constant, which is the lesson from the
last three gates.

## Implementation constraints carried out of this survey

```text
1  migration 0035 creates nf_award_documents; the bytes are not in it
2  organization_id anchors; awarded_grant_id, award_requirement_id and
   proof_event_id are all refused as anchors, and a CHECK requires at least one
3  object_key is refused unless object_store_configured is true, and
   object_store_configured is bridged from detect_body_store_mode()
4  the repository is NOT named award_document_store_service - that name flips
   two module-existence probes with no bytes stored anywhere
5  both probes are replaced with derived answers; one place answers "is there a
   document store", and it is not a filename
6  metadata is not content: sha256_digest, content_length and content_type
   describe a document this repository has never seen
7  customer_visible defaults false and is never derived from upload status
8  a document's presence never implies an accepted proof
9  legal_hold refuses archive, at the database and in the repository
10 the Core sa.Table restates every CHECK constraint (Gate 119C's defect)
11 archive, never delete
12 production writes require customer_auth_live AND verified operational binding
13 every new conjunct both derived and injectable
14 no object store contacted, no document content written, ever
15 no API route; document why
```
