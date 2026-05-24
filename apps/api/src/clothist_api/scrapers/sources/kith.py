"""Kith adapter — multi-vendor streetwear/sneaker reseller. `vendor` field
spans Nike, Adidas, New Balance, Asics, in-house Kith ("Kith Women",
"Kith Men", "Kith Kids"), etc.

Gender extraction order (most→least specific):
  1. `kith::audience` namespaced tag (when present).
  2. `vendor` field — Kith brands by gender ("Kith Women" → women).
  3. Title prefix — industry-standard `WMNS` / `MNS` markers used by
     Nike, Jordan, adidas, HOKA, etc. on women's/men's SKUs.
  4. `product_type` prefix (`Mens Shorts` → men).
  5. Base-class fallback (unisex).
"""
from __future__ import annotations

import re

from clothist_api.scrapers.base import IngestCounters, ShopifyAdapter
from clothist_api.scrapers.normalize import Gender, normalize_gender

_AUDIENCE_TAG = re.compile(r"^\s*kith::audience\s*=>\s*(\w+)\s*$", re.IGNORECASE)
_VENDOR_GENDER = re.compile(r"\b(women|men|kids)\b", re.IGNORECASE)
_TITLE_PREFIX = re.compile(r"\b(WMNS|MNS|Women'?s?|Men'?s?)\b")
_PT_GENDER = re.compile(r"\b(men'?s?|women'?s?|mens|womens|kids|unisex)\b", re.IGNORECASE)


class KithAdapter(ShopifyAdapter):
    base_url = "https://kith.com"
    retailer_slug = "kith"
    currency = "USD"
    image_hostname = "cdn.shopify.com"
    assume_gender = None  # too-mixed; default to "unisex" via base impl
    throttle_seconds = 1.5

    def gender_for(self, raw: dict, *, counters: IngestCounters) -> Gender:
        # 1. Explicit kith::audience tag
        for t in raw.get("tags") or []:
            m = _AUDIENCE_TAG.match(t)
            if m:
                g = normalize_gender(m.group(1))
                if g:
                    return g
        # 2. Kith sub-brand vendor (Kith Women, Kith Men, Kith Kids, …)
        vendor = raw.get("vendor") or ""
        if vendor.lower().startswith("kith "):
            m = _VENDOR_GENDER.search(vendor)
            if m and m.group(1).lower() != "kids":
                g = normalize_gender(m.group(1))
                if g:
                    return g
        # 3. Title prefix — Nike/Jordan/adidas "WMNS"/"Mens"
        title = raw.get("title") or ""
        m = _TITLE_PREFIX.search(title)
        if m:
            g = normalize_gender(m.group(1))
            if g:
                counters.gender_inferred_from_fallback += 1
                return g
        # 4. product_type prefix
        product_type = raw.get("product_type") or ""
        m = _PT_GENDER.search(product_type)
        if m:
            g = normalize_gender(m.group(0))
            if g:
                counters.gender_inferred_from_fallback += 1
                return g
        # 5. Base-class fallback (currently → unisex)
        return super().gender_for(raw, counters=counters)
