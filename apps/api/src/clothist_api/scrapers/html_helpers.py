"""Generic HTML / structured-data helpers — reserved for Phase 3 sources
(H&M, Uniqlo, Zara) that need JSON-LD parsing or Next.js __NEXT_DATA__
extraction. Shopify storefronts use the JSON `/products.json` endpoint and
don't need this code.

Originally lived in `scrapers/base.py` under the H&M-first PROJECT_PLAN.md.
Moved here when `base.py` was rewritten around the Shopify pivot in
plans/scraping/senior_dev_v2.md.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Iterator
from dataclasses import dataclass
from typing import Any

import httpx
from selectolax.parser import HTMLParser
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from clothist_api.settings import get_settings

logger = logging.getLogger(__name__)


class ScrapeError(Exception):
    pass


class BlockedError(ScrapeError):
    """The retailer blocked the request (403, captcha, etc.)."""


@dataclass(slots=True)
class FetchedPage:
    url: str
    html: str
    status: int


class RetailerClient:
    """Shared HTTP client with retailer-friendly defaults. Used by Phase 3
    HTML-scraping adapters (JSON-LD on H&M/Uniqlo/Zara PDPs).
    """

    def __init__(self, *, base_headers: dict[str, str] | None = None) -> None:
        settings = get_settings()
        self._rate_limit = settings.scraper_rate_limit_seconds
        self._client = httpx.AsyncClient(
            timeout=settings.scraper_request_timeout,
            follow_redirects=True,
            headers={
                "User-Agent": settings.scraper_user_agent,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
                **(base_headers or {}),
            },
        )

    async def __aenter__(self) -> RetailerClient:
        return self

    async def __aexit__(self, *_: object) -> None:
        await self._client.aclose()

    @retry(
        retry=retry_if_exception_type(httpx.TransportError),
        stop=stop_after_attempt(3),
        wait=wait_exponential(min=1, max=10),
        reraise=True,
    )
    async def fetch(self, url: str) -> FetchedPage:
        logger.debug("GET %s", url)
        resp = await self._client.get(url)
        if resp.status_code in (403, 429):
            raise BlockedError(
                f"Retailer blocked request to {url} (status {resp.status_code}). "
                "Consider a Playwright fallback or rotating IP/user-agent."
            )
        resp.raise_for_status()
        await asyncio.sleep(self._rate_limit)
        return FetchedPage(url=str(resp.url), html=resp.text, status=resp.status_code)


def iter_jsonld(html: str) -> Iterator[dict[str, Any]]:
    """Yield every JSON-LD object embedded in the page (flattened if @graph used)."""
    tree = HTMLParser(html)
    for node in tree.css('script[type="application/ld+json"]'):
        raw = node.text(strip=False)
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        if isinstance(data, list):
            for item in data:
                if isinstance(item, dict):
                    yield item
        elif isinstance(data, dict):
            if "@graph" in data and isinstance(data["@graph"], list):
                for item in data["@graph"]:
                    if isinstance(item, dict):
                        yield item
            else:
                yield data


def get_next_data(html: str) -> dict[str, Any] | None:
    """Return parsed __NEXT_DATA__ JSON, or None if not present."""
    tree = HTMLParser(html)
    node = tree.css_first('script#__NEXT_DATA__')
    if node is None:
        return None
    raw = node.text(strip=False)
    if not raw:
        return None
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return None
