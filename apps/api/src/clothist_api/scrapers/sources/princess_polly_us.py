"""Princess Polly US adapter — predominantly women's fast fashion; historically
runs occasional men's capsules. Tag/title scan first, fall back to
`assume_gender = "women"` (structural override, not a silent hardcode).
"""
from __future__ import annotations

import re

from clothist_api.scrapers.base import IngestCounters, ShopifyAdapter
from clothist_api.scrapers.normalize import Gender, normalize_gender

_MENS_HINT = re.compile(r"\bmen'?s?\b|\bunisex\b", re.IGNORECASE)


class PrincessPollyUsAdapter(ShopifyAdapter):
    base_url = "https://us.princesspolly.com"
    retailer_slug = "princess_polly_us"
    currency = "USD"
    image_hostname = "cdn.shopify.com"
    assume_gender = "women"
    throttle_seconds = 1.5

    def gender_for(self, raw: dict, *, counters: IngestCounters) -> Gender:
        # Tags + title scan for men's/unisex; otherwise the brand-as-signal
        # fallback kicks in via assume_gender.
        for t in raw.get("tags") or []:
            if _MENS_HINT.search(t):
                g = normalize_gender(t)
                if g:
                    return g
        title = raw.get("title") or ""
        m = _MENS_HINT.search(title)
        if m:
            g = normalize_gender(m.group(0))
            if g:
                counters.gender_inferred_from_fallback += 1
                return g
        return super().gender_for(raw, counters=counters)
