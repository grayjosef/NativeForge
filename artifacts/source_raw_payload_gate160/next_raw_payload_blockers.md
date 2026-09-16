# Next: what still stands between a landing zone and a collection

Gate 160 built the raw payload spine. Bytes land, hash, verify, replay and carry
their provenance. None of them came from anywhere - every one was handed in by a
caller.

## What is now true

```text
exact bytes persist                   including non-UTF-8 bodies
the hash is verified twice            on write, and again on readback
a tampered body fails replay          and NO bytes are returned
a retry is separate evidence          attempt 2 never overwrites attempt 1
the same attempt cannot change bytes  refused, with both hashes named
credential headers cannot be stored   allowlist by header name
the URL is never stored               only a sha256 fingerprint
oversize bodies are refused           1 MiB, by the service AND the database
archive keeps a payload readable      nothing deletes
```

## What still blocks a collection

```text
1  a collector envelope      Gate 161. No code can fetch anything.
2  source allowlist boundary Gate 162. Zero sources are approved, and this is
                             where approval gets defined.
3  source terms              a HUMAN must read them. 171 sources.
4  human review              a HUMAN must look at each source.
```

Item 1 is the last purely-engineering blocker before the allowlist boundary.
Items 3 and 4 are not engineering, and a working landing zone does not make them
so - it means that when a human finally clears them, there is somewhere for the
first response to land that has already been proven.

## Two things this gate deliberately did not do

**It did not configure an object store.** Gate 97C's S3 body store is built,
content-addressed and hash-verifying, and it has no bucket. Adding a second
abstraction to claim one exists would have produced two stores, one of them
fake. `object_store_configured` is measured from Gate 97C's own config and stays
`false`.

**It did not define an execution proof.** Gate 158 left `completed` unreachable
because the gate that defines what an execution proof IS has not been written.
A stored payload is not one: these bytes were supplied, and a row proves the
spine works rather than that a source was contacted.

Defining it is the moment "a job finished" becomes a claim this system can make,
and it should cost a gate of its own. Gate 161 is the obvious candidate, since a
collector that actually fetched something would be the first thing with standing
to make that claim - but it should be a deliberate decision in that gate rather
than a corner of it.

## What the spine now makes askable

```text
what exactly did this source return       replay, byte-identical
did it change between attempts            two attempts, two hashes
which attempt produced this               attempt -> job -> source
has anything been altered since           the readback hash says so
how much evidence is stored               total_bytes, distinct_hashes
```

The last two are the ones that matter for an audit. Until this gate, neither
question had an answer, because there was nothing to ask it about.
