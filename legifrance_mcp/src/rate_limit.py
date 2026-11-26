"""Proactive client-side rate limiting for PISTE-backed tool calls.

PISTE enforces its own per-application quotas (not configurable, not
negotiable): every Légifrance endpoint is throttled to 2 requests/second
and 25,000 requests/day, under a looser 20 requests/second and 1,000,000
requests/day account-wide ceiling. Judilibre only has the looser pair: 20
requests/second and 1,000,000 requests/day. The per-second numbers are
the ones that matter for an interactively-used MCP server; the daily caps
are tracked by PISTE itself and surface as 429s (which pylegifrance's own
client already retries with exponential backoff) long before a normal
session could approach them.
"""

import asyncio
import time
from functools import wraps
from typing import Any, Callable, TypeVar

F = TypeVar("F", bound=Callable[..., Any])

# PISTE's published per-second quotas (see module docstring).
LEGIFRANCE_CALLS_PER_SECOND = 2
JUDILIBRE_CALLS_PER_SECOND = 20


def rate_limit(calls: int, period: float) -> Callable[[F], F]:
    """Limits an async function to at most `calls` invocations per `period` seconds.

    Uses a sliding-window call log (not a fixed-window reset) so a burst
    can't occur right at a window boundary. Each decorated function gets
    its own independent window; concurrent callers are serialized through
    an asyncio.Lock so the check-then-record step itself can't race.
    """

    def decorator(func: F) -> F:
        call_times: list[float] = []
        lock = asyncio.Lock()

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            async with lock:
                while True:
                    now = time.monotonic()
                    call_times[:] = [t for t in call_times if now - t < period]
                    if len(call_times) < calls:
                        call_times.append(now)
                        break
                    await asyncio.sleep(period - (now - call_times[0]))
            return await func(*args, **kwargs)

        return wrapper  # type: ignore[return-value]

    return decorator


def legifrance_rate_limit(func: F) -> F:
    """Rate limit for tools backed by the Légifrance API (2 req/s)."""
    return rate_limit(calls=LEGIFRANCE_CALLS_PER_SECOND, period=1.0)(func)


def judilibre_rate_limit(func: F) -> F:
    """Rate limit for tools backed by the Judilibre API (20 req/s)."""
    return rate_limit(calls=JUDILIBRE_CALLS_PER_SECOND, period=1.0)(func)
