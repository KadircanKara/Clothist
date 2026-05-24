"""Pytest fixtures shared across the suite.

Tests run against a real Postgres (per `plans/senior_dev_v3.md` §6g —
SQLite is not supported because the GENERATED column for `price_usd`
and JSONB operators are Postgres-only). Each integration test that
touches the DB uses a per-test cleanup hook.
"""
from __future__ import annotations

import asyncio
from pathlib import Path

import pytest


@pytest.fixture(scope="session")
def event_loop():
    """Single event loop for the whole test session so async fixtures don't
    bind to a loop that closes between tests."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def fixtures_dir() -> Path:
    return Path(__file__).parent / "fixtures"
