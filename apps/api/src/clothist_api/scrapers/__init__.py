"""Scrapers for real product data (Shopify storefronts in Phase 1).

The public surface is `ShopifyAdapter` (base class for all per-store
adapters) and the `SOURCES` registry in `scrapers.sources`. Legacy HTML /
JSON-LD helpers for Phase-3 sources live in `scrapers.html_helpers`.
"""
from clothist_api.scrapers.base import IngestCounters, ScraperContext, ShopifyAdapter

__all__ = ["IngestCounters", "ScraperContext", "ShopifyAdapter"]
