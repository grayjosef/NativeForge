# 475 — Gate 84C-A: Full-suite failure survey

Gate 84B ran the whole suite with no `-k` for the first time:

```text
4 failed, 7114 passed, 51 skipped   in 35:31
```

All four fail **alone** as well, so none is order-dependent. Every one is a
deterministic failure the recurring scoped `-k` never selected.

## The four

### 1. `test_five_fit_dimensions`

`tests/test_sprint197_eligibility_fit_assessment_dimension_vocabulary.py:17`

```text
assert len(FIT_DIMENSIONS) == 5
AssertionError: assert 6 == 5
  where 6 = len(('eligibility_fit', 'recognition_tier_fit', 'relevance_fit',
                 'geography_fit', 'program_fit', 'capacity_fit'))
```

**Stale assertion, not a defect.** `recognition_tier_fit` was added by commit
`526f9ce` ("SC: recognition-tier eligibility gate + pilot fixture loader") — the
federally-recognized vs state-recognized split the entire Native eligibility
model rests on. The dimension is correct; the count assertion was never updated.

**Corrected assertion:** pin the exact tuple by name. Strictly stronger than the
count it replaces — it fails on a removal, a rename, a reorder *or* an
unreviewed addition.

### 2. `test_incomplete_profile_blocked_readiness`

`tests/test_sprint222_matching_readiness_readiness_evaluator.py:38`

```text
assert result["readiness_label"] in {READINESS_BLOCKED,
                                     READINESS_NOT_READY_ELIGIBILITY_UNCERTAIN}
AssertionError: assert 'not_ready_missing_documents' in
                       {'blocked', 'not_ready_eligibility_uncertain'}
```

**Stale assertion, not a defect.** The readiness vocabulary later gained
`not_ready_missing_documents`, and for this fixture that is a *more* precise
answer than the generic block: the profile is missing documents, not of
uncertain eligibility. The evaluator improved; the test did not follow.

**Corrected assertion:** assert the exact label, plus that it is inside
`READINESS_LABELS` and outside the proceed set, plus `final_eligibility is
False`. Tightened rather than loosened to "any not_ready".

### 3 & 4. The two Gate 37 port tests

`tests/test_sprint4202_gate37_production_grade_hardening.py:77` and `:95`

```text
test_5175_collision_blocks_serve   OSError: [Errno 98] Address already in use
test_verifier_fail_when_server_down DistNotReady: port 5175 already in use
```

**Environment-incompatible, not a defect.** Both require port 5175 to be free.
`nativeforge-demo-preview.service` owns `127.0.0.1:5175` by design, and stopping
it to satisfy a test is forbidden by this gate's hard rules — rightly, since the
demo being up is the product state everything else verifies against.

They would pass in CI with the port free, which is presumably where they last
did.

**Corrected approach:** neither test is about the number 5175. Test 3 is about
*collision detection*, which `require_preview_port_free(host, port)` already
accepts parameters for — so it runs against an ephemeral port. Test 4 is about
*the verifier failing when the server it checks is down*, which is expressible
by pointing the verifier at an ephemeral port nobody serves; it takes the base
URL as a positional argument.

A companion test pins `PREVIEW_PORT == 5175` so the real default is still
asserted somewhere.

## A fifth, found while fixing these

`test_verifier_pass_when_stamped_server_up` in the same file has the same
defect: it calls `require_preview_port_free()` and then starts its own preview
on 5175. It did not appear in the Gate 84B failure list only because it
`pytest.skip`s when `frontend/dist` is unstamped, and dist was unstamped during
that run.

Once dist is stamped — which it is after any gate's validation — it fails the
same way. Fixed by verifying against the already-running stamped preview when
5175 is busy, and starting one only when the port is free. Works in both
environments and stops no service.

## Why the scoped `-k` missed all of them

The recurring expression is a keyword list grown by accretion, one gate at a
time. None of `fit_dimension`, `readiness` or `gate37` was ever in it:

```text
collected by the full suite      7172
selected by the gate expression  6436  (89%)
unselected                        736
```

Four of the six known-fragile tests sat in that 736. The regression number every
gate reported was a property of the selection, not of the suite.

## Nature summary

| Test | Kind | Fails alone |
| --- | --- | --- |
| `test_five_fit_dimensions` | stale count assertion | yes |
| `test_incomplete_profile_blocked_readiness` | stale enum assertion | yes |
| `test_5175_collision_blocks_serve` | environment-incompatible | yes |
| `test_verifier_fail_when_server_down` | environment-incompatible | yes |
| `test_verifier_pass_when_stamped_server_up` | environment-incompatible | yes (once dist is stamped) |

No product defect among them. No product behaviour was changed to satisfy any
of them.
