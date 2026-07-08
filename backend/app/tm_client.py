import asyncio
import logging
import random
import time

import httpx

from .config import settings

log = logging.getLogger(__name__)

# Browser-ish headers for the image CDN; the scraper API itself doesn't care.
CDN_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
    ),
}


class TMError(Exception):
    """Base error talking to transfermarkt-api."""


class TMNotFound(TMError):
    pass


class TMUnavailable(TMError):
    pass


class _Gate:
    """Serializes requests so at least `interval` seconds pass between them."""

    def __init__(self, interval: float):
        self.interval = interval
        self._lock = asyncio.Lock()
        self._next_at = 0.0

    async def wait(self) -> None:
        async with self._lock:
            now = time.monotonic()
            delay = self._next_at - now
            if delay > 0:
                await asyncio.sleep(delay)
            self._next_at = max(now, self._next_at) + self.interval


class TMClient:
    """Rate-limited client for the self-hosted transfermarkt-api and its image CDN."""

    def __init__(self) -> None:
        # generous timeout: the scraper occasionally stalls when transfermarkt.de is slow
        self._api = httpx.AsyncClient(base_url=settings.tm_api_base_url, timeout=90)
        self._cdn = httpx.AsyncClient(timeout=30, headers=CDN_HEADERS, follow_redirects=True)
        self._api_gate = _Gate(settings.tm_min_request_interval)
        self._cdn_gate = _Gate(settings.tm_cdn_min_request_interval)

    async def close(self) -> None:
        await self._api.aclose()
        await self._cdn.aclose()

    async def get(self, path: str, params: dict | None = None) -> dict:
        last = "unknown"
        for attempt in range(3):
            await self._api_gate.wait()
            try:
                r = await self._api.get(path, params=params)
            except httpx.HTTPError as exc:
                last = f"network error: {exc}"
            else:
                if r.status_code == 404:
                    raise TMNotFound(path)
                if r.status_code == 429 or r.status_code >= 500:
                    last = f"HTTP {r.status_code}"
                elif r.status_code >= 400:
                    raise TMError(f"{path}: HTTP {r.status_code}")
                else:
                    return r.json()
            log.warning("tm request failed (%s), attempt %d: %s", path, attempt + 1, last)
            await asyncio.sleep(2**attempt * 2 + random.random())
        raise TMUnavailable(f"{path}: {last}")

    async def get_image(self, url: str) -> bytes | None:
        """Fetch an image from the transfermarkt CDN. None if unavailable."""
        await self._cdn_gate.wait()
        try:
            r = await self._cdn.get(url)
        except httpx.HTTPError as exc:
            log.warning("cdn fetch failed %s: %s", url, exc)
            return None
        if r.status_code != 200 or not r.content:
            return None
        if not r.headers.get("content-type", "").startswith("image/"):
            return None
        return r.content
