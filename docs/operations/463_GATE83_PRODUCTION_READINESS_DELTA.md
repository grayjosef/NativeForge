# 463 — Gate 83: Production readiness delta

Gates 79–82 built real capability. Gate 83 is the first that a customer can
see.

## Demo surface: now

| | Before | After |
| --- | --- | --- |
| Exclusion shown to a customer | nowhere | `sc-demo-negative-intelligence` section |
| Evidence quote on screen | never | the cited sentence, quoted |
| Answer changes by applicant class | invisible | both tiers rendered, contrast stated |
| Why an excluded opportunity is listed | unexplained | stated on the page |
| Provenance beside a claim | none | span, hash, artifact type, extraction method |
| Synthetic / no-live-coverage labels | scattered | rendered above the rows |

The section renders the excluded class **first**, because the negative answer is
the one a customer cannot get anywhere else.

## Backend / demo payload: now

| | Before | After |
| --- | --- | --- |
| Assembler surfaces | ~60 | 61 (`negative_intelligence`) |
| Quote origin | n/a | produced by the Gate 82 pipeline, not authored |
| Claim enforcement | generation-time | unchanged — bridge raises on invariant failure |
| Backend route | none | **still none**, deliberately (doc 462) |

`build_sc_demo_negative_intelligence_surface()` runs the real ingestion pipeline
over `tests/fixtures/nofo_artifacts/synthetic_notice.html`. Two tests keep the
screen honest: every quoted word must appear in the fixture, and the committed
demo JSON must equal the freshly built surface.

That the excluding sentence reaches the screen is also live proof of Gate 82C —
the fixture plants a `<script>` string, an HTML comment and a hidden `<div>` all
claiming state-recognized tribes are eligible, and none of them reaches the
quote.

## Live source coverage: now

**Unchanged. Zero.**

```text
Live SC source coverage:   NONE
Live federal coverage:     NONE
Sources monitored:         0
Notices fetched:           0
Real notices parsed:       0
SC coverage complete:      NOT CLAIMED
65% improvement:           NOT CLAIMED
```

The displayed notice is a committed synthetic fixture that says so on its first
line. The exclusion is a true statement about that text, not about any real
programme.

## Native customer value

For the first time, the product *shows* the thing it was built to say:

1. This opportunity is Native-relevant.
2. Relevance does not decide who may apply.
3. For a **state-recognized tribe**, the notice text appears to exclude you —
   here is the sentence, its span, and the hash of the document it came from.
4. For the **Catawba Nation**, the same notice names you as eligible.
5. The excluded opportunity stays on your screen, because knowing a programme
   has ruled you out is worth more than never finding it.
6. A human on your team confirms it against the primary notice. Nothing here is
   a legal determination.

That is one document producing two correct and different answers for two
customers in the same state, with the evidence attached — and until this gate,
none of it was visible to anyone but a test runner.

## Owner-blocked

- **Robots/terms review** for the Gate 78R sources. Still the gate on ever
  showing a real notice here.
- **Primary-source verification.** Everything on this surface is synthetic. The
  Gate 78R eligibility strings remain `eligibility_verified: false`.
- **A PDF parser decision** (carried from Gate 82) — licence and supply-chain
  implications make it an owner call.
- Real `OIDC_*` credentials, managed Postgres, migration 0028, backup/restore,
  pen test.
- **Wording review before any customer sees this.** The copy avoids legal
  claims and a test guards the phrasing, but "likely excluded" language shown to
  a tribal grant office deserves human sign-off, not only an automated check.

## Engineering-blocked

- **Demo payload determinism.** Two consecutive builds of the bridge payload
  differ — generated ids, nonces and timestamps across ~60 pre-existing
  surfaces. Pre-existing, not introduced here, and out of scope for this gate,
  but it means a demo-payload diff cannot be reviewed and the committed artifact
  is not reproducible from its inputs. The Gate 83 surface itself is
  deterministic and a test pins that. Recommended follow-up: thread a seed or
  fixed clock through the assemblers. Recorded in doc 462.
- Real notices on this surface — blocked behind the fetch layer, which is
  blocked behind terms review.
- Threading `applicant_class` from a customer org profile, so the surface shows
  *your* class rather than a demo pair (carried from Gate 79B).
- Scheduler (Gate 80) — still correctly blocked; zero sources terms-cleared.

## Controlled customer pilot delta

**None.**

```text
Controlled customer pilot: NO_GO
Production rollout:        NO_GO
Customer login live:       NO
Production storage live:   NO
Customer persistence:      NO
Pen-test passed:           NO
```

What genuinely changed: four gates of capability stopped being invisible. What
has not changed: every word on the new surface describes a synthetic fixture,
and no real notice has ever reached it.
