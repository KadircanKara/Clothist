"""Per-store Shopify adapters.

Add a new source by:
  1. Creating `{slug}.py` that subclasses `ShopifyAdapter`.
  2. Registering it in the SOURCES dict below.
  3. Adding a fixture for tests/test_scrapers_sources.py.
"""
from __future__ import annotations

from clothist_api.scrapers.base import ShopifyAdapter

from .aimeleondore import AimeLeonDoreAdapter
from .allbirds import AllbirdsAdapter
from .kith import KithAdapter
from .princess_polly_us import PrincessPollyUsAdapter
from .rothys import RothysAdapter

SOURCES: dict[str, type[ShopifyAdapter]] = {
    "allbirds": AllbirdsAdapter,
    "ald": AimeLeonDoreAdapter,
    "rothys": RothysAdapter,
    "princess_polly_us": PrincessPollyUsAdapter,
    "kith": KithAdapter,
}

__all__ = ["SOURCES"]
