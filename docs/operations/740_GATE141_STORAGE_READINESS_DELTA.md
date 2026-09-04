# 740 — Gate 141: the storage readiness delta

## What changed

```text
                                    before Gate 141   after Gate 141
document_metadata_operational       not derived       true (derived)
document_body_storage_ready         false (constant)  false (derived)
object_store_configured at routes   false (constant)  false (derived)
object_store_configured in refusal  false (constant)  false (derived)
body storage route                  did not exist     exists, refuses by name
body storage readiness route        did not exist     exists, names what is missing
object storage preflight            did not exist     five states
put/get/head/delete adapter         did not exist     two, one inert
in-memory fake adapter              only in a test    in src/, shared by the
                                                      artifact and the tests
```

Every "false" above is still false. What changed is that it is now **measured**:
configure a bucket tomorrow and the routes, the refusal and the readiness
roll-up will all say so, which none of them would have done before.

## What did not change, and was checked

```text
login_live                     true
customer_persistence_live      true
awarded_operational_tracking   true
tenant_digest_operational      true
customer_auth_live             false
verified_operational_binding   false
source_monitoring_live         false
email_delivery                 false
object_store_configured        false
production_storage             false
production_rollout             false
controlled_customer_pilot      false
```

## Was the object store contacted?

No, and it is a property of the dependency set rather than a claim about one
run:

```text
boto3 / botocore / minio / s3fs / aioboto3 importable   False
pyproject.toml / uv.lock reference any of them          no
three storage modules parsed with ast for imports       no network library
external object store contacted                         false
network calls to object storage                         0
```

## Were credentials required?

No. The whole test suite and both verifiers run with all five object storage
settings **absent**, which is the point: a lane whose tests need a credential is
a lane whose refusals nobody can check.

## Were credentials printed or committed?

No. Key **names** reach every report and no value does. The preflight tests
construct a settings object carrying `https://storage.invalid` and
`a-real-looking-bucket`, then assert neither string appears in the serialised
result. An invariant scans the whole result for `http://`, `https://`, `AKIA`,
`aws_secret` and `-----BEGIN`.

Every artifact is scanned for those markers plus the two synthetic fixture
bodies, so a body byte reaching a committed file would fail the build rather
than ship.

## Were body bytes written?

```text
body bytes sent by the smoke              0
body bytes written externally             0
documents stored with an object_key       0
documents claiming a configured store     0
real customer files read                  0
real customer files hashed               0
```

The hermetic proof stores 61 synthetic bytes into a Python dict and deletes
them. Nothing was read from disk, and the only bytes that existed were a literal
in the source.

## Was real customer data written?

No. Every row is `demo_fixture`-labelled, in the demo organization
`bbbbbbbb-cccc-dddd-eeee-ffffffffffff`. The real organization
`aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee` was not addressed by any route and
appears once in the artifacts, named as the organization no route reaches.

The verifier leaves nothing behind:

```text
live Gate 141 fixture awards   0
live documents                 0
documents with an object key    0
persistence rows left live      0
```

## Did production storage change?

No. `production_storage` is false in the preflight, the adapter proof, the
readiness service, both new routes and every artifact, and no branch anywhere in
this gate sets it.

## What activation would require later

```text
1. five settings with real values          absent today, named by key
2. an injected S3-shaped client            no SDK present; this gate added none
                                           and uv.lock is untouched
3. an owner decision                       production_storage_owner_decision_service
                                           exists and was not invoked
4. an external verifier, allowed AND passed by a person. `production_verified`
   cannot be produced from configuration alone.
5. secret scanning before promotion        already named in REQUIRED_GUARANTEES
```

Only after all five may `object_store_configured` become true, and even then
`production_storage` is a separate decision this gate does not touch.

## What is NOT the blocker

```text
the metadata lane      operational, proved by calling the routes
the adapter            written, bounded, and proved hermetically
the refusals           explicit, named, and reachable
the database           already CHECKs object_key IS NULL OR object_store_configured
an SDK                 not needed to prove any of the above
customer_auth_live     gates PRODUCTION writes; every row here is fixture-labelled
```

## Defects found and fixed

Two, both by running the thing rather than reading it:

```text
refuse_if_blocked reads `rows_written`, a REPOSITORY's word. An adapter says
`stored`, so a successful put read as a refusal with an empty reason list -
the bytes were in the fake and the caller got a 422 saying nothing.

The smoke's award archive posted no JSON body. The route declares a required
ArchiveBody, so it 422'd, the fixture award stayed live, and the second run
bailed on a unique index - which read as a flaky cross-org check rather than
as the re-runnability bug it was. Same defect Gate 138 found with a fixed
persistence seed; the award number is now fresh per run.
```

## Next gate

Gate 142. The remaining lanes are, in the order their blockers unblock:

```text
customer_auth_live             blocked on invite_binding_passed — a second real
                               person accepting a real invite (Gate 136)
verified_operational_binding   Gate 137's two-part owner decision
source_monitoring_live         a collector activated under the existing gates,
                               which is what would give the digest live
                               candidates instead of fixture snapshots
email_delivery                 no service exists; a weekly digest nobody
                               receives is not a weekly digest
digest persistence             no nf_tenant_digest_records; a digest that cannot
                               be re-read cannot be audited after a missed
                               deadline
object_store_configured        the five settings and the owner decision above
```
