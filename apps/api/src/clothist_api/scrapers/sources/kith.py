"""Kith adapter — multi-vendor streetwear/sneaker reseller. `vendor` field
spans Nike, Adidas, New Balance, Asics, in-house Kith, etc. Gender comes
from a `kith::audience` tag when present; falls back to product_type prefix
(`Mens Shorts` → men).
"""
from __future__ import annotations

import re

from clothist_api.scrapers.base import IngestCounters, ShopifyAdapter
from clothist_api.scrapers.normalize import Gender, normalize_gender

_AUDIENCE_TAG = re.compile(r"^\s*kith::audience\s*=>\s*(\w+)\s*$", re.IGNORECASE)
_PT_GENDER = re.compile(r"\b(men'?s?|women'?s?|mens|womens|kids|unisex)\b", re.IGNORECASE)


class KithAdapter(ShopifyAdapter):
    base_url = "https://kith.com"
    retailer_slug = "kith"
    currency = "USD"
    image_hostname = "cdn.shopify.com"
    assume_gender = None  # too-mixed; default to "unisex" via base impl
    throttle_seconds = 1.5

    def gender_for(self, raw: dict, *, counters: IngestCounters) -> Gender:
        for t in raw.get("tags") or []:
            m = _AUDIENCE_TAG.match(t)
            if m:
                g = normalize_gender(m.group(1))
                if g:
                    return g
        product_type = raw.get("product_type") or ""
        m = _PT_GENDER.search(product_type)
        if m:
            g = normalize_gender(m.group(0))
            if g:
                counters.gender_inferred_from_fallback += 1
                return g
        return super().gender_for(raw, counters=counters)
