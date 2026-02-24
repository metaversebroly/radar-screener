"""
RADAR - StockX price screener API.
FastAPI backend for detecting price dips on collectibles.
"""
from dotenv import load_dotenv

load_dotenv()

import logging
import re
from datetime import datetime

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from database import (
    create_product,
    delete_product,
    get_all_products,
    get_product_by_slug,
    get_oldest_price,
    get_price_history_30d,
    get_recent_alerts,
    get_recent_scans,
    insert_price_history,
    update_product_threshold,
)
from retailed import get_lowest_ask
from scheduler import get_next_scan_time, scan_all_products, start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="RADAR Screener API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Extract slug from StockX URL: .../product-name or .../fr/product-name
SLUG_PATTERN = re.compile(r"stockx\.com/(?:[a-z]{2}/)?([a-zA-Z0-9-]+)(?:\?|$|/)")


def _slug_from_url(url: str) -> str | None:
    match = SLUG_PATTERN.search(url)
    return match.group(1) if match else None


def _slug_to_name(slug: str) -> str:
    """Convert slug to display name (e.g. labubu-the-monsters-zimomo -> Labubu The Monsters Zimomo)."""
    return " ".join(word.capitalize() for word in slug.split("-"))


def _compute_median(prices: list[dict]) -> float | None:
    if not prices:
        return None
    values = sorted(float(p["price"]) for p in prices if p.get("price") is not None)
    if not values:
        return None
    n = len(values)
    return (values[n // 2] + values[(n - 1) // 2]) / 2 if n else None


def _enrich_product(product: dict) -> dict:
    """Add last_price, reference_price, discount_pct to product."""
    history = get_price_history_30d(product["id"])
    last_price = float(history[-1]["price"]) if history else None
    reference_price = product.get("reference_price")
    if reference_price is not None:
        reference_price = float(reference_price)
    if reference_price is None:
        reference_price = get_oldest_price(product["id"])

    discount_pct = None
    if last_price is not None and reference_price is not None and reference_price > 0:
        discount_pct = (reference_price - last_price) / reference_price * 100

    return {
        **product,
        "last_price": last_price,
        "reference_price": reference_price,
        "discount_pct": discount_pct,
    }


@app.on_event("startup")
def startup():
    start_scheduler()


@app.post("/products")
def post_products(body: dict):
    """Add a product by StockX URL. Optional: threshold (default 15) = % discount to trigger alert."""
    url = body.get("url")
    if not url or not isinstance(url, str):
        raise HTTPException(400, "Missing or invalid 'url' in body")

    slug = _slug_from_url(url)
    if not slug:
        raise HTTPException(400, "Could not extract product slug from URL")

    existing = get_product_by_slug(slug)

    if existing:
        raise HTTPException(409, f"Product with slug '{slug}' already exists")

    threshold = body.get("threshold")
    if threshold is not None:
        try:
            threshold = float(threshold)
            if threshold < 1 or threshold > 99:
                raise ValueError("Threshold must be between 1 and 99")
        except (TypeError, ValueError):
            raise HTTPException(400, "Invalid threshold (must be 1-99)")
    else:
        threshold = 15

    name = _slug_to_name(slug)
    import asyncio
    price = asyncio.run(get_lowest_ask(slug))
    if price is None:
        raise HTTPException(502, "Impossible de récupérer le prix StockX (Retailed API)")
    product = create_product(slug=slug, name=name, dip_threshold=threshold, reference_price=price)
    insert_price_history(product["id"], price)
    return product


@app.patch("/products/{slug}")
def patch_product_threshold(slug: str, body: dict):
    """Update the alert threshold for a product."""
    threshold = body.get("threshold")
    if threshold is None:
        raise HTTPException(400, "Missing 'threshold' in body")
    try:
        threshold = float(threshold)
        if threshold < 1 or threshold > 99:
            raise ValueError("Threshold must be between 1 and 99")
    except (TypeError, ValueError):
        raise HTTPException(400, "Invalid threshold (must be 1-99)")

    updated = update_product_threshold(slug, threshold)
    if not updated:
        raise HTTPException(404, f"Product '{slug}' not found")
    return {"ok": True}


@app.delete("/products/{slug}")
def delete_products(slug: str):
    """Delete product and its price history."""
    deleted = delete_product(slug)
    if not deleted:
        raise HTTPException(404, f"Product '{slug}' not found")
    return {"ok": True}


@app.get("/products")
def get_products():
    """Get all products with last price, median 30d, discount_pct."""
    products = get_all_products()
    return [_enrich_product(p) for p in products]


@app.get("/alerts")
def get_alerts():
    """Get the 50 most recent alerts."""
    return get_recent_alerts(50)


@app.get("/scans")
def get_scans():
    """Get the 50 most recent scans."""
    return get_recent_scans(50)


@app.post("/scan")
def post_scan():
    """Trigger an immediate scan. Returns {scanned, dips_found}."""
    result = scan_all_products()
    return result


@app.get("/test-telegram")
def test_telegram():
    """Send a test message to Telegram. Returns success/failure."""
    import os
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return {"ok": False, "error": "TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set"}
    try:
        import httpx
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        r = httpx.post(url, json={"chat_id": chat_id, "text": "✅ RADAR — Test réussi ! Le bot est configuré."}, timeout=10)
        r.raise_for_status()
        return {"ok": True, "message": "Message envoyé"}
    except Exception as e:
        return {"ok": False, "error": str(e)}


@app.get("/health")
def get_health():
    """Health check with next scan time."""
    next_scan = get_next_scan_time()
    if next_scan:
        ts = next_scan.isoformat()
        if ts.endswith("+00:00"):
            ts = ts[:-6] + "Z"
        elif "Z" not in ts and "+" not in ts:
            ts = ts + "Z"
    else:
        ts = None
    return {
        "status": "ok",
        "next_scan": ts,
    }
