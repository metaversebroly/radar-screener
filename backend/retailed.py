"""
Retailed.io API client for StockX price scraping.
"""
import asyncio
import logging
import os
from typing import Any

import httpx

RETAILED_API_KEY = os.getenv("RETAILED_API_KEY")
RETAILED_CURRENCY = os.getenv("RETAILED_CURRENCY", "EUR")
RETAILED_COUNTRY = os.getenv("RETAILED_COUNTRY", "FR")
RATE_LIMIT_DELAY = 2  # seconds between requests

logger = logging.getLogger(__name__)


async def get_product_full(slug: str) -> dict | None:
    """
    Fetch full product data from Retailed.io (price, image, name).
    Returns None on error.
    """
    if not RETAILED_API_KEY:
        logger.error("RETAILED_API_KEY not configured")
        return None

    url = "https://app.retailed.io/api/v1/scraper/stockx/product"
    params = {"query": slug, "currency": RETAILED_CURRENCY, "country": RETAILED_COUNTRY}
    headers = {"x-api-key": RETAILED_API_KEY}

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(url, params=params, headers=headers)

            if response.status_code == 429:
                logger.warning("Retailed.io rate limit (429) for slug=%s", slug)
                return None

            if response.status_code == 404:
                logger.warning("Product not found (404) for slug=%s", slug)
                return None

            response.raise_for_status()
            data: dict[str, Any] = response.json()

            market = data.get("market") or {}
            bids = market.get("bids") or {}
            lowest_ask = bids.get("lowest_ask") or data.get("lowestAsk")
            if lowest_ask is None:
                logger.warning("No lowest_ask in response for slug=%s", slug)
                return None

            image_url = data.get("image") or data.get("thumbnail") or data.get("small_image") or ""
            name = data.get("name") or " ".join(w.capitalize() for w in slug.split("-"))

            return {
                "price": float(lowest_ask),
                "image_url": image_url if image_url else None,
                "name": name,
            }

    except httpx.TimeoutException:
        logger.error("Timeout fetching price for slug=%s", slug)
        return None
    except httpx.HTTPError as e:
        logger.error("HTTP error for slug=%s: %s", slug, e)
        return None
    except (ValueError, KeyError) as e:
        logger.error("Invalid response for slug=%s: %s", slug, e)
        return None


async def get_lowest_ask(slug: str) -> float | None:
    """Fetch only the lowest ask price. For backward compatibility."""
    data = await get_product_full(slug)
    return data["price"] if data else None


async def rate_limited_get_product_full(slug: str) -> dict | None:
    """Wrapper that enforces 2 second delay between product requests."""
    result = await get_product_full(slug)
    await asyncio.sleep(RATE_LIMIT_DELAY)
    return result


async def rate_limited_get_lowest_ask(slug: str) -> float | None:
    """Backward compat: returns only price."""
    data = await rate_limited_get_product_full(slug)
    return data["price"] if data else None
