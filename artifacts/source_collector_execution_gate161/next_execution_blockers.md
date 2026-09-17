# What still blocks a live source call

Gate 161 built the envelope. Four things refuse a live call, independently, and
none of them takes caller input.

## The four stops

```text
1  the execution policy          refuses transport_kind=live
2  the transport boundary        refuses it again, on its own
3  DISPATCHABLE_KINDS            contains only `hermetic`
4  migration 0047                CHECK (transport_kind = 'hermetic')
                                 CHECK (live_source_call = 0)
```

Stop 1 is the only one a caller can influence, and Gate 94B's guard CAN be
satisfied by a caller who supplies every status - which is by design, because
Gate 162 will do exactly that, deliberately. The remaining three take no input
at all. A caller who talks their way past the guard still finds that nothing
can dispatch, and that the database will not hold the row.

## What is genuinely missing

```text
no live transport implementation    nothing in this repo can open a socket
                                    for a source request
zero approved sources               177 known, 171 terms-blocked,
                                    6 human-review-blocked, 0 approved
no source terms approval            a human decides, not a timer
no activation                       Gate 162 owns it
```

## What Gate 161 does NOT unlock

- It does not approve a source. The registry is full and approves nothing.
- It does not make monitoring live. `source_monitoring_live` stays false.
- It does not complete a real-source job. Gate 158's `transition_job` still has
  no execution-proof parameter and this gate does not add one.
- It does not mean a source responded. A hermetic proof says the path works.

## Owners

```text
Gate 162   activation and the allowlist
Gate 163   the first approved live source
a human    source terms, before either
```

## The one thing worth re-reading before Gate 162

A hermetic execution produces a real execution proof, and that proof is
correct: the bytes really were transported, persisted and verified. The
temptation at Gate 162 will be to treat that proof as evidence a source can be
called. It is not. It is evidence the envelope works, which is why the proof
carries `proves_the_envelope_works` and `proves_a_source_responded` as two
fields that cannot be read as one.
