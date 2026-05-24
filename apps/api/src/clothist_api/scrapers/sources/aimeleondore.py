"""Aimé Leon Dore adapter — uses internal `dev-product-type-{men|women}` tag
convention. Falls back to title text mining (matching `enrich_seed.py`'s
gender inference) when no tag is present.
"""
from __future__ import annotations

import re

from clothist_api.scrapers.base import IngestCounters, ShopifyAdapter
from clothist_api.scrapers.normalize import Gender, normalize_gender

_GENDER_TAG = re.compile(r"^\s*dev-product-type-(\w+)\s*$", re.IGNORECASE)
_TITLE_GENDER = re.compile(
    r"\b(men'?s|mens|women'?s|womens|ladies'?|girls?|boys?)\b",
    re.IGNORECASE,
)


class AimeLeonDoreAdapter(ShopifyAdapter):
    base_url = "https://www.aimeleondore.com"
    retailer_slug = "ald"
    currency = "USD"
    image_hostname = "cdn.shopify.com"
    assume_gender = None
    throttle_seconds = 1.5

    def gender_for(self, raw: dict, *, counters: IngestCounters) -> Gender:
        for t in raw.get("tags") or []:
            m = _GENDER_TAG.match(t)
            if m:
                g = normalize_gender(m.group(1))
                if g:
                    return g
        # Title text mining fallback
        title = raw.get("title") or ""
        m = _TITLE_GENDER.search(title)
        if m:
            g = normalize_gender(m.group(0))
            if g:
                counters.gender_inferred_from_fallback += 1
                return g
        return super().gender_for(raw, counters=counters)
