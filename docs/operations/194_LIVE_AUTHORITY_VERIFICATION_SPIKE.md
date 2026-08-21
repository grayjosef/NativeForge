# Live Authority Verification Spike (Gate 14 / Block 33)

## Status

* Authority source registry: **complete**
* Federal live/read-only spike: **dry-run only** (no credentials / no approved network client)
* State authority profiles: **Top-15 complete**; none live-verified
* Authority claim resolver: **complete**; submit authority remains **false**

## Hard claim boundary

| Claim | Gate 14 value |
|-------|---------------|
| SAM/UEI live checked | false |
| SAM/UEI verified | false |
| EBiz POC live checked | false |
| EBiz POC verified | false |
| AOR live checked | false |
| AOR verified | false |
| State authority verified | false |
| Submit authority | false |
| Login live | false |

Self-attestation cannot unlock federal submission authority.

## Integration requirements (before any live_verified claim)

1. Approved read-only SAM.gov entity lookup client
2. Approved Grants.gov role/workspace read path (if any)
3. Secret storage for API tokens (not in git)
4. No-mutation guarantee + rate limits + audit logging
5. Owner approval before any live network verification
