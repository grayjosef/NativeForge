# 478 — Gate 84C-D: Gate 37 port isolation contract

`tests/test_sprint4202_gate37_production_grade_hardening.py`
`src/nativeforge/services/gate37_production_grade_hardening_service.py`

## The conflict

Three Gate 37 tests required `127.0.0.1:5175` to be free.
`nativeforge-demo-preview.service` owns that port by design, and this gate's
hard rules forbid stopping it. That is the right rule: the demo being up is the
product state the strict-public verifier, the Playwright smoke and the browser
checks all measure against.

So the tests could only pass on a machine where the product was not running.

## What the tests are actually about

None of the three is about the number 5175:

| Test | Real property |
| --- | --- |
| `test_busy_preview_port_blocks_serve` | a listener on the preview port blocks serving |
| `test_verifier_fail_when_server_down` | the verifier fails when the server it checks is down |
| `test_verifier_pass_when_stamped_server_up` | the verifier passes against a stamped, running preview |

Each is expressible without touching 5175.

## The fixes

**Collision detection — ephemeral port.** `require_preview_port_free(host, port)`
already accepted both parameters, so **no product change was needed**. The test
binds port 0, reads the assigned port, asserts the check raises while the socket
is open and passes once it is closed.

**Verifier-fails-when-down — ephemeral base URL.** `verify_nativeforge_demo_deployment.sh`
takes the base URL as a positional argument, so the test points it at an
ephemeral port nobody is serving and asserts `RESULT=FAIL`. It also asserts
`loopback_home_200 status=FAIL` appears, so a pass for the wrong reason is
caught.

**Verifier-passes-when-up — use the running server.** When 5175 is busy a
stamped preview is already serving, so the test verifies against it and returns.
It starts its own preview only when the port is free. Works on a developer
machine with the service running and in CI without it, and stops nothing.

## What is still pinned

Dropping 5175 from those tests would have lost the assertion that the product
serves on that port at all, so a companion test states it directly:

```python
def test_preview_port_default_is_5175() -> None:
    assert PREVIEW_PORT == 5175
    assert PREVIEW_HOST == "127.0.0.1"
```

`test_loopback_only_contract` continues to assert the serve script contains
`--host 127.0.0.1`, `--port 5175`, `--strictPort`, and does not bind `0.0.0.0`.
Loopback-only behaviour is unchanged and unweakened.

## What was not done

```text
preview service stopped        no
tests skipped or xfailed       no
5175 requirement kept          no - it was the defect
listener assertion weakened    no - it runs against a real socket, on another port
product behaviour changed      no - the helper already took host and port
```

## The fifth test

`test_verifier_pass_when_stamped_server_up` was not in the Gate 84B failure list
because it `pytest.skip`s when `frontend/dist` is unstamped, and dist happened to
be unstamped during that run. After any gate's stamped build it fails the same
way as the other two. It is fixed here rather than left to surface later.
