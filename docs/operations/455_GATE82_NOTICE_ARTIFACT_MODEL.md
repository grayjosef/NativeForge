# 455 — Gate 82B: Notice artifact model

`src/nativeforge/services/notice_artifact_model_service.py`
Schema `nf_notice_artifact_model_v1`.

Describes one primary-notice artifact before any text has been read out of it.

## Supported artifact types

```text
html   pdf   plain_text   markdown   json_recorded_transport   unknown
```

`EXTRACTABLE_TYPES` is derived as `ARTIFACT_TYPES - {"unknown"}`, so a type
added later is unreadable until someone deliberately wires an adapter for it.

Type is resolved from three signals, in increasing authority:

1. **Suffix** (`.html`, `.pdf`, `.md`, `.txt`, `.json`).
2. **Declaration** by the caller. A declaration that disagrees with the suffix
   is recorded as a warning, never silently resolved — a `.pdf` declared as
   `plain_text` is a mislabel or a mistake and both deserve a human.
3. **Magic bytes.** A file starting `%PDF-` is a PDF whatever its name says.
   This matters: reading a PDF as text yields binary noise, and binary noise
   sectioned as prose is exactly the kind of garbage that becomes cited
   eligibility evidence.

## The no-live-fetch rule

`source_url` and `notice_url` are **metadata**. Nothing in this package opens
them. `url_fetch_performed` is hardcoded `False` and invariant-checked.

`is_live_fetch` defaults to `False`. A caller may pass `declared_live_fetch=True`,
but that is a *request*, not a fact: it is only honoured when
`hermetic_test_guard_service.live_network_allowed()` returns true, which it does
not by default. Otherwise the request is refused and recorded as a warning.

An invariant fails any artifact claiming a live fetch while the guard forbids
one, so a forged flag cannot survive the contract. This keeps the Gate 77B
honest-labeling rule true by construction rather than by discipline.

## Recorded fixtures are checked, not believed

`is_recorded_fixture` is decided by
`hermetic_test_guard_service.is_source_controlled(path)` — is this path inside
the committed fixture roots — rather than by caller assertion. A caller claiming
fixture status for a path outside those roots is contradicted by the filesystem.

Live fetch and recorded fixture are mutually exclusive; claiming both blocks,
and an invariant catches it.

## Blocking

```text
unknown_artifact_type       type could not be resolved
missing_local_path          nothing to read
local_path_does_not_exist   path resolved to no file
content_hash_mismatch       supplied hash disagrees with the file
missing_content_hash        only when require_hash=True
```

Anything blocked is not extractable, and an invariant fails a blocked artifact
reported as extractable.

Hash behaviour is context-dependent, as the gate requires: a missing hash
**warns** by default and **blocks** under `require_hash=True`. A supplied hash
that disagrees with the file always blocks — that is a different file from the
one the caller thinks it has.

## What this model never claims

```text
freshness_claimed     False
eligibility_claimed   False
url_fetch_performed   False
```

The model describes a file. Whether the opportunity is open is
`opportunity_freshness_service`, and who may apply is Gate 81C. Neither question
can be answered by looking at a file's metadata, and answering them here would
put an unsupported claim upstream of everything.

`text_extracted` and `text_extraction_method` are present but left `False`/`None`
here — an adapter fills them, because only an adapter knows.

## Why no live coverage is claimed

Nothing fetches. No source is monitored. This model can describe an artifact
somebody already has; it cannot obtain one.
