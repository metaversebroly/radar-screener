"""
APScheduler for periodic price scanning.
"""
import asyncio
import logging
import os
from datetime import datetime
from statistics import median

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

from alerts import send_telegram_alert
from database import (
    get_all_products,
    get_price_history_30d,
    get_recent_alerts_for_product,
    insert_alert,
    insert_price_history,
)
from retailed import rate_limited_get_lowest_ask

DEFAULT_DIP_THRESHOLD = float(os.getenv("DIP_THRESHOLD", "15"))
ANTI_SPAM_HOURS = 6

logger = logging.getLogger(__name__)
scheduler = BackgroundScheduler()
def _compute_median(prices: list[dict]) -> float | None:
    """Compute median from list of price dicts."""
    values = [float(p["price"]) for p in prices if p.get("price") is not None]
    if not values:
        return None
    return median(values)


async def _scan_product(product: dict) -> tuple[bool, bool]:
    """
    Scan a single product: fetch price, save to history, check for dip, send alert if needed.
    Returns (price_updated, alert_sent).
    """
    product_id = product["id"]
    slug = product["slug"]
    name = product.get("name", slug)

    price = await rate_limited_get_lowest_ask(slug)
    if price is None:
        return False, False

    insert_price_history(product_id, price)

    history = get_price_history_30d(product_id)
    median_price = _compute_median(history)
    if median_price is None or median_price <= 0:
        return True, False

    discount_pct = (median_price - price) / median_price * 100

    threshold = float(product.get("dip_threshold") or DEFAULT_DIP_THRESHOLD)
    if discount_pct >= threshold:
        recent = get_recent_alerts_for_product(product_id, ANTI_SPAM_HOURS)
        if not recent:
            alert_data = {
                "product_id": product_id,
                "product_name": name,
                "slug": slug,
                "alert_price": price,
                "median_price": median_price,
                "discount_pct": discount_pct,
            }
            insert_alert(
                product_id=product_id,
                product_name=name,
                slug=slug,
                alert_price=price,
                median_price=median_price,
                discount_pct=discount_pct,
            )
            send_telegram_alert(alert_data)
            return True, True

    return True, False


def scan_all_products() -> dict:
    """
    Scan all products: fetch prices, save history, detect dips, send alerts.
    Returns {scanned: N, dips_found: M}.
    """
    products = get_all_products()
    if not products:
        logger.info("No products to scan")
        return {"scanned": 0, "dips_found": 0}

    async def _run():
        scanned = 0
        dips_found = 0
        for product in products:
            updated, alerted = await _scan_product(product)
            if updated:
                scanned += 1
            if alerted:
                dips_found += 1
        return scanned, dips_found

    scanned, dips_found = asyncio.run(_run())
    logger.info("Scan complete: %d products scanned, %d dips found", scanned, dips_found)
    return {"scanned": scanned, "dips_found": dips_found}


def get_next_scan_time() -> datetime | None:
    """Return next scheduled scan time."""
    job = scheduler.get_job("scan")
    return job.next_run_time if job else None


def start_scheduler():
    """Start APScheduler with 6-hour interval and run initial scan."""
    scheduler.add_job(
        scan_all_products,
        trigger=IntervalTrigger(hours=6),
        id="scan",
        next_run_time=datetime.utcnow(),
    )
    scheduler.start()
    logger.info("Scheduler started, first scan triggered")
