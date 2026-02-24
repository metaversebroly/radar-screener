"""
Telegram alert notifications for RADAR screener.
"""
import logging
import os
from datetime import datetime

import httpx

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

logger = logging.getLogger(__name__)


def send_telegram_alert(alert: dict) -> bool:
    """
    Send a price drop alert to Telegram.
    alert: dict with product_name, alert_price, median_price, discount_pct, slug
    Returns True on success, False on failure.
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured")
        return False

    product_name = alert.get("product_name", "Unknown")
    alert_price = alert.get("alert_price", 0)
    median_price = alert.get("median_price", 0)
    discount_pct = alert.get("discount_pct", 0)
    slug = alert.get("slug", "")

    message = (
        "🚨 *TROU D'AIR DÉTECTÉ*\n\n"
        f"📦 *{product_name}*\n\n"
        f"💰 Prix actuel : *${alert_price:.2f}*\n"
        f"📊 Prix de référence : ${median_price:.2f}\n"
        f"📉 Discount : *-{discount_pct:.1f}%*\n\n"
        f"👉 [Acheter sur StockX](https://stockx.com/{slug})"
    )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            logger.info("Telegram alert sent for %s", product_name)
            return True
    except httpx.HTTPError as e:
        logger.error("Failed to send Telegram alert: %s", e)
        return False


def send_telegram_scan_summary(scanned_at: str, products: list[dict], dips_found: int) -> bool:
    """
    Send scan summary to Telegram when no price movement (or always).
    products: list of {name, slug}
    """
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured")
        return False

    try:
        dt = datetime.fromisoformat(scanned_at.replace("Z", "+00:00"))
        date_str = dt.strftime("%d/%m/%Y %H:%M")
    except Exception:
        date_str = scanned_at

    if dips_found > 0:
        header = f"📊 *Scan du {date_str}*\n\n✅ {dips_found} trou(s) d'air détecté(s)"
    else:
        header = f"📊 *Scan du {date_str}*\n\n➖ Pas de mouvement de prix"

    lines = []
    for p in products:
        name = p.get("name", p.get("slug", "?"))
        slug = p.get("slug", "")
        lines.append(f"• {name}\n  👉 [StockX](https://stockx.com/{slug})")

    message = header + "\n\n" + "\n\n".join(lines)

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    }

    try:
        with httpx.Client(timeout=10.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            logger.info("Telegram scan summary sent")
            return True
    except httpx.HTTPError as e:
        logger.error("Failed to send Telegram scan summary: %s", e)
        return False
