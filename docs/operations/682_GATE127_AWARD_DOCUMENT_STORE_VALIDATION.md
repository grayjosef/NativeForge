# 682 — Gate 127: award document store validation

What makes a stored document reference fit to act on, and the four defects found
while building it.

## Metadata is not content

```text
sha256_digest   64 hex characters describing a file this service never opened
content_length  how many bytes that file has, according to whoever said so
content_type    what kind of file it is, according to the same
object_key      where it would be, if there were anywhere
```

Every one is a claim somebody made. None is evidence the document exists.
`content_verified` is a constant `False` and `content_inferred_from_metadata` is
another: verifying a digest means reading bytes, and this service reads none.

## One detector for one question

`detect_object_store_configured()` does not answer "is object storage
configured". It asks:

```python
return bool(detect_body_store_mode() in PRODUCTION_CAPABLE_MODES)
```

Gate 96 built that detector for raw source payloads. An award document is a
different corpus — what a Tribe filed, rather than what NativeForge fetched —
but "is object storage configured" is not a per-corpus question, and writing a
second answer to it is what Gate 114 spent a whole gate collapsing.

`vocabulary_invariant_failures()` refuses the two disagreeing.

## Four things a document does not imply

```text
a reference is not a document       nothing has been read
a document is not a submission      somebody has to file it
a document is not an accepted proof a funder has to accept it
a document is not customer-visible  somebody has to decide that
```

`customer_visible` is the quiet one. It is never derived — not from upload
status, not from a digest, not from the document being the Tribe's own. The
default is false, the constant `visibility_inferred_from_upload` is false, and
the database refuses visibility on an unestablished `fact_status`.

A default of true shows a draft to the wrong person exactly once.

## The four defects

### 1. A refusal too strict to leave the ordinary case reachable

The first version refused any row carrying a digest with no stored bytes:

```python
if digest and metadata_only:
    refused_claims.append("digest_recorded_for_a_document_with_no_stored_bytes")
```

But a Tribe handing over a file and its SHA-256 is exactly the ordinary case,
and it is how you would later verify the file once there is somewhere to verify
it against. Refusing it made the ordinary metadata-plus-digest row permanently
un-storable and put `document_ready_for_reference` out of reach for it.

What is dangerous is not recording the digest; it is a reader taking it for
verification. So the state is derived and reported —
`digest_is_unverified` — and `content_verified` stays a constant `False` with an
invariant behind it.

### 2. An invariant that fired on ordinary bad input

```python
if result.get("object_key") and not result.get("object_store_configured"):
    failures.append("an_object_key_survived_without_a_configured_store")
```

Both fields are echoed input. A caller supplying a key with no store is bad
input, already named in `blocked_reasons`, and the invariant fired on it — the
validation-rule-misnamed shape Gate 124D shipped three of and Gate 126 found
five more of.

Guarded on `storable` now, which bad input can never reach. The guard is Gate
126's refinement of Gate 125's rule: an invariant may read an echoed field when
the guard makes it unreachable by bad input, because comparing what the caller
said against what the service derived is the only way to catch the two drifting
apart.

### 3. A scanner that refused its own output

The artifact capability scan compared every occurrence of
`object_store_configured` against reality, and every `object_key_present`
against its store. Two of its own payloads tripped it:

```text
a_stored_document_with_a_store_injected   the only place a stored document is
                                          demonstrated at all
object_key_without_a_store                a row showing a refusal
```

Gate 121 spent two attempts on this exact mistake with a leak scanner, and Gates
124H and 126H each narrowed a scan for it. Narrowed again here, with the rule
stated rather than the check dropped:

```text
a flatly-false capability   refused anywhere
a measured capability       compared against reality on summary claims only;
                            a case row injecting a store is a demonstration
a key with no store         refused on rows presented as acceptable, permitted
                            on rows that name why they were refused
```

Without the middle rule the injected branch becomes untestable, which is worse
than the scan being slightly wider.

### 4. A test that grepped for a name its own docstring contained

`test_no_probe_names_that_module_any_more` checked
`"award_document_store_service" not in source`, and matched the docstring
explaining the removal. The seventh substring-versus-meaning false positive in
this campaign, and the third one inside a test written to catch that very class.

Parsed now: no string literal in a call argument may name the trap module. The
prose assertion stays, so the test would catch a real reintroduction rather than
the account of one.

## The validation matrix

Fourteen cases, written to `award_document_store_validation_matrix.csv`. It
includes `a_stored_document_with_a_store_injected` alongside the refusals, so
the permitted branch appears in a durable artifact and not only in a test.

## The artifact scans

```text
1  by field name  anything named like real award or tenant data, plus object
                  store credentials
2  by inference   any result claiming an inference this campaign prohibits
3  by capability  any payload whose capability claim disagrees with reality
4  by removal     any payload saying a record went away or a store was reached
5  by content     any payload that looks like it contains a document
```

The fifth is this gate's, and it is the first time it has been needed: this is
the first lane whose subject is a file. A compliance artifact carrying base64, a
data URI, or a `content` field would be a Tribe's document committed to a git
repository, and being a fixture would not make that acceptable.

Two checks, because a document can arrive under an innocent key:

```text
by field name   content, body, bytes, base64, attachment, ...
by value shape  a data: URI, or 512+ characters of base64 alphabet
```
