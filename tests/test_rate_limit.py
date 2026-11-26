"""Unit tests for the proactive client-side rate limiter."""

import asyncio
import time

import pytest

from legifrance_mcp.src.rate_limit import rate_limit


class TestRateLimit:
    async def test_allows_calls_up_to_the_limit_without_delay(self):
        @rate_limit(calls=3, period=10.0)
        async def fn():
            return "ok"

        start = time.monotonic()
        results = [await fn() for _ in range(3)]
        elapsed = time.monotonic() - start

        assert results == ["ok", "ok", "ok"]
        assert elapsed < 0.5

    async def test_delays_calls_beyond_the_limit_until_the_window_clears(self):
        @rate_limit(calls=2, period=0.2)
        async def fn():
            return "ok"

        start = time.monotonic()
        await fn()
        await fn()
        await fn()  # third call within the same 0.2s window must wait
        elapsed = time.monotonic() - start

        assert elapsed >= 0.2

    async def test_independent_limiters_do_not_share_state(self):
        @rate_limit(calls=1, period=10.0)
        async def fn_a():
            return "a"

        @rate_limit(calls=1, period=10.0)
        async def fn_b():
            return "b"

        start = time.monotonic()
        await fn_a()
        await fn_b()
        elapsed = time.monotonic() - start

        # fn_b has its own limiter, so it isn't throttled by fn_a's call.
        assert elapsed < 0.5

    async def test_preserves_return_value_and_propagates_exceptions(self):
        @rate_limit(calls=5, period=1.0)
        async def fn(x):
            if x < 0:
                raise ValueError("negative")
            return x * 2

        assert await fn(3) == 6
        with pytest.raises(ValueError, match="negative"):
            await fn(-1)

    async def test_concurrent_calls_are_serialized_through_the_window(self):
        @rate_limit(calls=1, period=0.2)
        async def fn():
            return time.monotonic()

        start = time.monotonic()
        results = await asyncio.gather(fn(), fn(), fn())
        elapsed = time.monotonic() - start

        assert len(results) == 3
        assert elapsed >= 0.4  # 3 calls at 1/0.2s each take >= 2 full windows
