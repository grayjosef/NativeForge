# 437 — Gate 78E/F: Fixture write-back carry-forward and cleanliness guard

## Correction to Gate 77B

Gate 77B reported **two** latent persist services. **There are three.** My 77B
survey piped its grep through `head -20` and I reported the truncated list as
complete.

Re-surveyed without truncation, by scanning every service that calls
`write_text` for a path built from `fixtures/`:

| Service | Committed fixtures written | 77B status | Now |
| --- | --- | --- | --- |
| `tribal_grant_eligibility_reingest_service` | `nf15_eligibility_reingest_pulls.json` | active, fixed | guarded |
| `scaled_federal_corpus_persist_service` | `la_scaled_federal_grants.json` | latent, reported | **guarded** |
| `tier2_state_corpus_persist_service` | `ta_tier2_state_grants.json`, `ta_mixed_tier13_grants.json` | **missed** | **guarded** |
| `tier3_foundation_corpus_persist_service` | `ta_tier3_foundation_grants.json`, `ta_mixed_tier13_grants.json` | latent, reported | **guarded** |

**Five committed fixtures, not three.** Six write sites in total.

Two details that matter:

- **`ta_mixed_tier13_grants.json` is written by two services.** Both `tier2` and
  `tier3` merge into it.
- **That file also carries the `nf13-real-fed-021` SAMHSA record.** So the row
  Gate 77 nearly lost had two more unguarded write paths than Gate 77B
  identified. The record was never actually damaged through them — those
  services' tests pass `tmp_path` — but the exposure was real and unreported.

## What was patched

All six write sites now route through `resolve_writeback_path` via a new
`guarded_write_text` helper (the text-shaped sibling of `guarded_write_json`,
since these callers append a trailing newline to a serialized payload).

```python
_wb = guarded_write_text(target, json.dumps(artifact, indent=2) + "\n",
                         label="tier2_state_corpus")
target = Path(_wb["path"])
```

Reassigning `target` to the resolved path means the returned `corpus_path`
reports where the write actually landed, so a redirect cannot be mistaken for a
fixture update.

Behaviour is unchanged for legitimate callers: the three services already accept
a `path` parameter and their tests pass `tmp_path`, which is not source-
controlled and therefore not redirected. Those tests still pass.

## Why these were latent rather than active

Each accepts an explicit `path`, and every current test supplies `tmp_path`.
The danger was the **default**: a caller omitting `path` writes committed
evidence. That is exactly what happened with the reingest service in Gate 77,
which had no `path` parameter at all.

Latent is not safe — it is one forgotten keyword argument away from active.

## The outer guard

`scripts/verify_nativeforge_fixture_cleanliness.sh`

The per-service guards protect **known** paths. A future service, or one nobody
surveyed — as `tier2` was not — would slip past them. This script does not care
*how* a fixture changed, only that none did.

```bash
scripts/verify_nativeforge_fixture_cleanliness.sh              # check current state
scripts/verify_nativeforge_fixture_cleanliness.sh --run-suite  # run the suite first
```

Watched directories mirror `SOURCE_CONTROLLED_DIRS` in the guard service, and a
test asserts the two lists agree so the script and the guard cannot drift apart.

It also checks the SAMHSA record **by content**, not just by `git status`:

```text
check=samhsa_evidence_intact            PASS  SM-26-024 / SAMHSA / HHS
check=no_ihs_substitution               PASS
check=no_connection_error_placeholder   PASS
```

Content checks catch the corruption even if someone commits it, which
`git status` would then call clean.

A failing suite is reported but does not mask the cleanliness verdict — a run
that both fails and dirties fixtures should say both.

## Not wired into CI

Deliberately. The gate said not to rely on CI magic that does not exist, and
there is no CI configuration in this repo to hook. The script is runnable now
and is a one-line addition to a pre-push hook or pipeline when one exists;
recorded as engineering-blocked in doc 438.

## Still unreviewed

Five services write under `fixtures/` to demo and artifact paths rather than
corpus evidence:

```text
nm_wa_browser_demo_bridge_service
nm_wa_operator_surfacing_demo_artifact_service
nm_wa_operator_surfacing_demo_render_service
nofo_showcase_intelligence_pack_service
sc_monday_curated_pack_service
```

They are out of scope here because they do not write grant-evidence corpora, but
they do write under a watched directory, so the cleanliness script will catch
them if they ever dirty a tracked file. Worth an explicit look.
