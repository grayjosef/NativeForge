"""Gate 164: the build context cannot leak between execution contexts.

The first draft used `threading.local()`. That is correct only if work never
moves between threads and threads are never shared between tasks, and neither
holds here: every FastAPI endpoint in this app is `def` rather than
`async def` - 57 route modules, zero `async def` - so Starlette runs them in
anyio's worker THREADPOOL, and those workers are reused across requests.

`ContextVar` is correct under both models, so both are exercised:

```text
threads      a pooled worker running a canonical build must not change what
             another pooled worker sees - and a worker REUSED afterwards must
             not inherit the flag
asyncio      concurrent tasks share one thread, which is precisely where
             thread-local storage would have leaked
```

Makes no network request.
"""

from __future__ import annotations

import asyncio
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, "src")
sys.path.insert(0, ".")

from nativeforge.services.canonical_artifact_build_context_service import (  # noqa: E402
    AmbientStateRefused,
    canonical_build,
    environment_scoped_build,
    in_canonical_build,
)

out: dict[str, object] = {}
detail: list[str] = []

# ---- 1. exceptions restore the prior state ------------------------------
out["default_is_not_canonical"] = not in_canonical_build()
try:
    with canonical_build(reason="raises"):
        raise RuntimeError("something failed inside a canonical build")
except RuntimeError:
    pass
out["an_exception_restores_the_prior_state"] = not in_canonical_build()

# ---- 2. nesting restores to the ENCLOSING state, not the default --------
with canonical_build(reason="outer"):
    outer = in_canonical_build()
    with environment_scoped_build(reason="inner"):
        inner = in_canonical_build()
    restored_to_enclosing = in_canonical_build()
out["nesting_restores_to_the_enclosing_state"] = bool(
    outer and not inner and restored_to_enclosing
)
out["environment_scoped_does_not_leak_after_exit"] = not in_canonical_build()

# A canonical build nested in an environment-scoped one, the other way round.
with environment_scoped_build(reason="outer env"):
    env_outer = in_canonical_build()
    with canonical_build(reason="inner canonical"):
        canonical_inner = in_canonical_build()
    env_restored = in_canonical_build()
out["nesting_works_in_both_directions"] = bool(
    not env_outer and canonical_inner and not env_restored
)

# ---- 3. threads: one worker's canonical build is invisible to another ---
barrier = threading.Barrier(2, timeout=10)
observations: dict[str, bool] = {}


def canonical_worker() -> None:
    with canonical_build(reason="thread A"):
        barrier.wait()  # hold the context open while B looks
        observations["A_sees_canonical"] = in_canonical_build()
        barrier.wait()


def observer_worker() -> None:
    barrier.wait()
    observations["B_sees_canonical"] = in_canonical_build()
    barrier.wait()


a = threading.Thread(target=canonical_worker)
b = threading.Thread(target=observer_worker)
a.start()
b.start()
a.join(timeout=15)
b.join(timeout=15)

out["a_canonical_thread_sees_its_own_context"] = bool(
    observations.get("A_sees_canonical")
)
out["another_thread_is_unaffected"] = not observations.get("B_sees_canonical", True)

# ---- 4. a REUSED pooled worker must not inherit the flag ---------------
#
# The specific failure thread-local storage would have produced: FastAPI's
# threadpool reuses workers across requests, so a flag left set by one request
# would be inherited by the next one that landed on the same thread.
with ThreadPoolExecutor(max_workers=1) as pool:

    def enter_and_leave() -> tuple[bool, int]:
        with canonical_build(reason="pooled request 1"):
            inside = in_canonical_build()
        return inside, threading.get_ident()

    def just_look() -> tuple[bool, int]:
        return in_canonical_build(), threading.get_ident()

    first_inside, first_thread = pool.submit(enter_and_leave).result(timeout=15)
    second_sees, second_thread = pool.submit(just_look).result(timeout=15)

out["the_pooled_worker_entered_a_canonical_build"] = bool(first_inside)
out["the_same_worker_was_reused"] = first_thread == second_thread
out["a_reused_pooled_worker_does_not_inherit_the_flag"] = not second_sees
if first_thread != second_thread:
    detail.append("the pool did not reuse the worker, so inheritance was not exercised")


# ---- 5. asyncio: concurrent tasks sharing one thread -------------------
async def canonical_task() -> bool:
    with canonical_build(reason="task A"):
        await asyncio.sleep(0.05)  # yield, so the other task runs meanwhile
        return in_canonical_build()


async def plain_task() -> bool:
    await asyncio.sleep(0.01)
    seen = in_canonical_build()
    await asyncio.sleep(0.05)
    return seen or in_canonical_build()


async def both() -> tuple[bool, bool]:
    return await asyncio.gather(canonical_task(), plain_task())  # type: ignore[return-value]


task_a, task_b = asyncio.run(both())
out["a_canonical_task_sees_its_own_context"] = bool(task_a)
out["a_concurrent_task_on_the_same_thread_is_unaffected"] = not task_b


# ---- 6. parallel canonical and environment-scoped cannot cross ---------
def refusal_under_canonical() -> bool:
    from nativeforge.lib.settings import auth_environment_presence

    with canonical_build(reason="parallel canonical"):
        try:
            auth_environment_presence()
            return False
        except AmbientStateRefused:
            return True


def permitted_under_environment_scope() -> bool:
    from nativeforge.lib.settings import auth_environment_presence

    with environment_scoped_build(reason="parallel env"):
        try:
            return auth_environment_presence() is not None
        except AmbientStateRefused:
            return False


with ThreadPoolExecutor(max_workers=4) as pool:
    futures = [
        pool.submit(
            refusal_under_canonical
            if index % 2 == 0
            else permitted_under_environment_scope
        )
        for index in range(8)
    ]
    results = [future.result(timeout=20) for future in futures]

out["parallel_canonical_and_environment_scoped_do_not_cross"] = all(results)
out["parallel_runs"] = len(results)
if not all(results):
    detail.append(f"{results.count(False)} of {len(results)} parallel runs crossed")

# ---- and the state is clean at the end ---------------------------------
out["the_context_is_clean_at_the_end"] = not in_canonical_build()

for key in (
    "default_is_not_canonical",
    "an_exception_restores_the_prior_state",
    "nesting_restores_to_the_enclosing_state",
    "environment_scoped_does_not_leak_after_exit",
    "nesting_works_in_both_directions",
    "a_canonical_thread_sees_its_own_context",
    "another_thread_is_unaffected",
    "the_pooled_worker_entered_a_canonical_build",
    "the_same_worker_was_reused",
    "a_reused_pooled_worker_does_not_inherit_the_flag",
    "a_canonical_task_sees_its_own_context",
    "a_concurrent_task_on_the_same_thread_is_unaffected",
    "parallel_canonical_and_environment_scoped_do_not_cross",
    "the_context_is_clean_at_the_end",
):
    out.setdefault(key, False)

out["detail"] = "; ".join(sorted(set(detail))) if detail else None
print(json.dumps(out, sort_keys=True))
