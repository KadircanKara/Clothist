"""Allbirds adapter — single-brand storefront with rich namespaced tags
(`allbirds::gender => unisex`, `allbirds::hue => grey`, etc.). Tags make
gender and color extraction trivial; we still defer to the base impl when
specific tags are missing.
"""
from __future__ import annotations

import re

from clothist_api.scrapers.base import IngestCounters, ShopifyAdapter
from clothist_api.scrapers.normalize import Gender, normalize_gender

_GENDER_TAG = re.compile(r"^\s*allbirds::gender\s*=>\s*(\w+)\s*$", re.IGNORECASE)


class AllbirdsAdapter(ShopifyAdapter):
    base_url = "https://www.allbirds.com"
    retailer_slug = "allbirds"
    currency = "USD"
    image_hostname = "cdn.shopify.com"
    assume_gender = None  # tags are reliable; no override needed
    throttle_seconds = 1.5

    def gender_for(self, raw: dict, *, counters: IngestCounters) -> Gender:
        for t in raw.get("tags") or []:
            m = _GENDER_TAG.match(t)
            if m:
                g = normalize_gender(m.group(1))
                if g:
                    return g
        # Allbirds occasionally publishes products without the namespaced
        # tag; fall through to base inference.
        return super().gender_for(raw, counters=counters)
