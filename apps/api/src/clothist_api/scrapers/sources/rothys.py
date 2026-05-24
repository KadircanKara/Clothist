"""Rothy's adapter — primarily women's footwear, with occasional men's
capsules. Tag-scan first (looking for `category-mens` or similar), then fall
back to `assume_gender = "women"`.
"""
from __future__ import annotations

import re

from clothist_api.scrapers.base import IngestCounters, ShopifyAdapter
from clothist_api.scrapers.normalize import Gender

_MENS_TAG = re.compile(r"\b(men|men's|mens|category-mens)\b", re.IGNORECASE)


class RothysAdapter(ShopifyAdapter):
    base_url = "https://rothys.com"
    retailer_slug = "rothys"
    currency = "USD"
    image_hostname = "cdn.shopify.com"
    assume_gender = "women"  # default — overridden by explicit men's tag
    throttle_seconds = 1.5

    def gender_for(self, raw: dict, *, counters: IngestCounters) -> Gender:
        tags = raw.get("tags") or []
        for t in tags:
            if _MENS_TAG.search(t):
                return "men"
        title = raw.get("title") or ""
        if _MENS_TAG.search(title):
            return "men"
        # No men's signal — fall back to assume_gender via base impl.
        return super().gender_for(raw, counters=counters)
