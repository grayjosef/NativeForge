# 683 — Gate 127: readiness delta

What creating `nf_award_documents` moved, and the much longer list it did not.

## Moved

```text
alembic head                                   0034      0035
award documents table                          none      nf_award_documents
                                                         31 cols, 16 CHECKs
document store repository                      none      9 operations
document_library lane schema_available         false     true
document_library lane repository_available     false     true
document_library lane write_path_available     false     true
document_library lane read_path_available      false     true
document_metadata_storage_available            absent    true
object_store_configured                        absent    false, and measured
capability lanes with schema                   5         6
capability lanes with a write path             5         6
capability lanes RLS-backed                    5         6
guard operations that are label-bound          6         7
```

The `document_library_persistence` lane has existed since Gate 114 and pointed
at a table nobody built. Its three mappings now point at what this gate built.

## Not moved — and this is the point of the gate

```text
object_store_configured                     false
body_store_mode                             unconfigured
document_storage_live                       false
DOCUMENT_STORAGE spine prerequisite         false
requires_document_storage                   true
customer_auth_live                          false
login_live                                  false
verified_operational_binding                false
customer_persistence_live                   false
capability lanes operational                0
ready_for_operational_awarded_tracking      false
operational_awarded_recommended             false
document store operational                  false
production document records created         0
document bytes written                      0
object store calls                          0
rows in nf_award_documents                  0
```

## The distinction the whole gate turns on

```text
document metadata persistence   a table saying which document, for what,
                                filed when, with what digest
document storage                somewhere the bytes actually live
```

Gate 127 built the first. It did not build the second, and it does not report
it.

The spine's `DOCUMENT_STORAGE` prerequisite means "evidence has a home" — that
is the bytes question, and it is what `award_requirements_persistence` and
`proof_audit_persistence` have been waiting on since Gates 125 and 126. Flipping
it because a metadata table exists would tell both lanes their evidence has
somewhere to go when it does not.

So all three post-award lanes plus this one now report
`operational_out_of_sequence` under forged auth: operable, and not yet due.

## The trap this gate walked past

Two probes answered "is there a document store" by asking whether a module
imports:

```python
# spine
DOCUMENT_STORAGE: _module_importable(
    "nativeforge.services.award_document_store_service")

# readiness
document_storage_live = _module_importable(
    "nativeforge.services.award_document_store_service")
```

The brief asked for `award_document_store_repository_service`. Creating a file
at the *other* name — even an empty one — would have flipped both true, cleared
the last unmet prerequisite on two lanes, and let
`operational_awarded_recommended` go true. With zero bytes stored anywhere.

Gate 114 named this shape when it found `customer_persistence_live` probing
whether a repositories module imports: "a module-existence proxy moving in the
unsafe direction". Two of them survived in the document lane, and they were the
two guarding the most consequential prerequisite left.

**Both replaced with derived answers**, each requiring two real conditions:

```python
def _detect_document_storage() -> bool:
    lane = build_capability("document_library_persistence")
    return bool(lane.get("write_path_available")
                and detect_object_store_configured())
```

```text
metadata has a home   the document lane has a write path   Gate 127 built this
bytes have a home     detect_body_store_mode() is          unconfigured
                      production-capable
```

Gate 126A found the mirror image — a probe naming a module nobody built, so a
real capability stayed invisible. This was the same defect pointed the other
way: a probe that would have reported a capability nobody built.

## One detector for one question

`object_store_configured` is **not** a new detector. It asks Gate 96's:

```python
return bool(detect_body_store_mode() in PRODUCTION_CAPABLE_MODES)
```

That detector serves raw source payloads, and an award document is a different
corpus. But "is object storage configured" is not a per-corpus question, and
three answers to one question is what Gate 114 spent a gate collapsing and Gate
126 hit again with two names for one module.

A vocabulary invariant refuses the two disagreeing, and a readiness invariant
refuses `document_storage_live` without a configured store.

## The lane that already existed under an older name

`document_library_persistence` was lane 6 of 9 from Gate 114 onward, mapped to:

```text
table      nf_document_library_items       never built
repo file  document_library.py             never built
contract   award_document_store_service    never built
```

Left alone, building `nf_award_documents` would have left the lane reporting
false forever — the Gate 126A defect a third time, in a third place.

**Re-pointed rather than duplicated.** A tenth lane would be two lanes for one
capability, which is worse than a lane whose id predates the name its table
ended up with. The id stays because the spine, the guard and several tests
reference it.

## One test repaired, and it was the guard working

The focused regression produced exactly one failure:

```text
test_gate124  test_every_mapped_contract_module_either_imports_or_is_a_known_absence
              AssertionError: document_library_persistence
```

Gate 126 rewrote that test after Gate 124's version enumerated the lanes whose
contract modules import — a list that went stale as soon as a ninth lane
arrived. The replacement asserts the *rule*: a mapped module imports, or its
lane appears in `KNOWN_ABSENT_CONTRACT_LANES` with a reason. It also asserts the
named absences are **still absent**, so the exemption list cannot rot into a
blanket one.

`document_library_persistence` was in that list with the reason "no award
document store has been built". Gate 127 built one, and the test failed on the
next run.

That is the mechanism doing its job rather than a defect: the alternative is an
exemption quietly outliving its reason, which is how a typo later passes as a
planned absence. The repair is one line — the lane leaves the list — and nothing
else in the campaign moved.

Two lanes remain named absences:

```text
source_watchlist_persistence   no tenant source watchlist has been built
beta_onboarding_persistence    no beta onboarding service has been built
```

## Why the lane is still not operational

One reason:

```text
no_customer_auth_so_nobody_owns_the_row
```

Schema, anchor, RLS policy, repository and contract are all present. Auth is
what is left — and separately, the bytes still have nowhere to go, which is what
keeps the lane out of sequence rather than out of build.

## What operational tracking still needs

```text
operational_component_missing:customer_persistence_live
operational_component_missing:document_storage_live
operational_component_missing:requirement_extraction_live
operational_component_missing:ui_available
operational_component_missing:verified_operational_identity_binding
```

`document_storage_live` stays on that list. A document store that holds
descriptions of documents is not a document store.

## The sentence to refuse

> NativeForge stores your compliance documents.

It does not. Four tables exist and this one holds descriptions: a title, a kind,
a digest somebody supplied, and which award or requirement or proof event the
document belongs to. The document is still wherever the Tribe put it.

## What is refused, and why

```text
a key with no store       a path into nothing. Four CHECKs and a named refusal
a document with no owner  at least one of three relationships is required
a visible document on an  showing a Tribe a document nobody has established as
  unestablished fact      theirs is how the wrong file reaches the wrong
                          government
an archive under legal    a lawyer said it must not move
  hold
```

```text
fixture cases                     16
fixture documents stored           0
fixture documents customer-visible 0
fixture document bytes             0
```

## What Gate 127 deliberately did not build

**The object store itself.** `s3_raw_payload_body_store_service` exists for raw
payloads and reports `unconfigured` — five settings missing, no credentials
present, zero modules importing boto3. Configuring it is an environment task
with a real bucket and real credentials behind it, not a code change, and it is
the same class of blocker as customer authentication: nothing in the repository
can move it.

**An API route.** Ten route decorators exist and none serves a document. Three
reasons, the third specific to this gate:

```text
1  a read route needs a session to scope by, and /current-user 401s for
   everybody, so the authenticated branch is unreachable and untestable
2  the table holds zero rows, so the route's only behaviour is `no_documents`
3  a document route is the one surface where "serves metadata" and "serves the
   file" are a single character apart in a handler. Building it while there is
   no store behind the metadata means the first version cannot be tested
   against the thing it must never do, and the test that would catch it is the
   one that needs the store to exist
```
