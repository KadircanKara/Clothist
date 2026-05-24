"""Pytest fixtures shared across the suite.

Tests run against a real Postgres (per `plans/senior_dev_v3.md` §6g —
SQLite is not supported because the GENERATED column for `price_usd`
and JSONB operators are Postgres-only).

The module-level `engine` in `clothist_api.db.session` is bound to the
first asyncio event loop that touches it. pytest-asyncio's default
function-scoped loop creates a fresh loop per test, leaving the engine's
pooled connections stranded. We dispose the engine after each async
test so the next test creates fresh connections on the new loop.
"""
from __future__ import annotations

from pathlib import Path

import pytest
import pytest_asyncio


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"


@pytest_asyncio.fixture(autouse=True)
async def _dispose_engine_between_async_tests():
    """Yield, then dispose the engine so the next test gets fresh asyncpg
    connections bound to its own event loop. No-op for sync tests."""
    yield
    from clothist_api.db.session import engine
    await engine.dispose()
