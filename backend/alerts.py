"""
Telegram alert notifications for RADAR screener.
"""
import logging
import os
from datetime import datetime

import httpx

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")


def _get_chat_ids() -> list[str]:
    """Support multiple chat IDs: comma-separated in TELEGRAM_CHAT_ID."""
    raw = os.getenv("TELEGRAM_CHAT_ID", "")
    return [x.strip() for x in raw.split(",") if x.strip()]

logger = logging.getLogger(__name__)


def _send_to_telegram(payload: dict) -> bool:
    """Send message to all configured chat IDs."""
    chat_ids = _get_chat_ids()
    if not TELEGRAM_BOT_TOKEN or not chat_ids:
        logger.error("TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured")
        return False

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    success = True
    for cid in chat_ids:
        try:
            with httpx.Client(timeout=10.0) as client:
                r = client.post(url, json={**payload, "chat_id": cid})
                r.raise_for_status()
        except httpx.HTTPError as e:
            logger.error("Failed to send to chat %s: %s", cid, e)
            success = False
    return success


def send_telegram_alert(alert: dict) -> bool:
    """
    Send a price drop alert to Telegram (to all chat IDs).
    """
    product_name = alert.get("product_name", "Unknown")
    alert_price = alert.get("alert_price", 0)
    median_price = alert.get("median_price", 0)
    discount_pct = alert.get("discount_pct", 0)
    slug = alert.get("slug", "")

    currency = os.getenv("RETAILED_CURRENCY", "EUR")
    symbol = "€" if currency == "EUR" else "$"

    message = (
        "🚨 *TROU D'AIR DÉTECTÉ*\n\n"
        f"📦 *{product_name}*\n\n"
        f"💰 Prix actuel : *{symbol}{alert_price:.2f}*\n"
        f"📊 Prix de référence : {symbol}{median_price:.2f}\n"
        f"📉 Discount : *-{discount_pct:.1f}%*\n\n"
        f"👉 [Acheter sur StockX](https://stockx.com/{slug})"
    )

    return _send_to_telegram({
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    })


def send_telegram_scan_summary(scanned_at: str, products: list[dict], dips_found: int) -> bool:
    """
    Send scan summary to Telegram when no price movement (to all chat IDs).
    products: list of {name, slug}
    """
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

    return _send_to_telegram({
        "text": message,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True,
    })
