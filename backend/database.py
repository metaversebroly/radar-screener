"""
Supabase database client and operations for RADAR screener.
Tables: products, price_history, alerts
"""
import os
from datetime import datetime, timedelta
from supabase import create_client, Client

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")

_client: Client | None = None


def get_client() -> Client:
    global _client
    if _client is None:
        if not SUPABASE_URL or not SUPABASE_KEY:
            raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
        _client = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _client


def create_product(slug: str, name: str, dip_threshold: float = 15) -> dict:
    """Insert a new product and return it."""
    client = get_client()
    data = {"slug": slug, "name": name, "dip_threshold": dip_threshold}
    result = client.table("products").insert(data).execute()
    return result.data[0]


def update_product_threshold(slug: str, dip_threshold: float) -> bool:
    """Update dip_threshold for a product."""
    client = get_client()
    result = client.table("products").update({"dip_threshold": dip_threshold}).eq("slug", slug).execute()
    return len(result.data) > 0


def get_product_by_slug(slug: str) -> dict | None:
    """Get product by slug."""
    client = get_client()
    result = client.table("products").select("*").eq("slug", slug).execute()
    return result.data[0] if result.data else None


def get_all_products() -> list[dict]:
    """Get all products."""
    client = get_client()
    result = client.table("products").select("*").order("created_at", desc=True).execute()
    return result.data or []


def delete_product(slug: str) -> bool:
    """Delete product by slug (cascade deletes price_history and alerts)."""
    client = get_client()
    result = client.table("products").delete().eq("slug", slug).execute()
    return len(result.data) > 0


def insert_price_history(product_id: str, price: float) -> dict:
    """Insert a price record."""
    client = get_client()
    data = {"product_id": product_id, "price": price}
    result = client.table("price_history").insert(data).execute()
    return result.data[0]


def get_price_history_30d(product_id: str) -> list[dict]:
    """Get price history for last 30 days."""
    client = get_client()
    since = (datetime.utcnow() - timedelta(days=30)).isoformat()
    result = (
        client.table("price_history")
        .select("price")
        .eq("product_id", product_id)
        .gte("scanned_at", since)
        .order("scanned_at", desc=False)
        .execute()
    )
    return result.data or []


def insert_alert(
    product_id: str,
    product_name: str,
    slug: str,
    alert_price: float,
    median_price: float,
    discount_pct: float,
) -> dict:
    """Insert an alert record."""
    client = get_client()
    data = {
        "product_id": product_id,
        "product_name": product_name,
        "slug": slug,
        "alert_price": alert_price,
        "median_price": median_price,
        "discount_pct": discount_pct,
    }
    result = client.table("alerts").insert(data).execute()
    return result.data[0]


def get_recent_alerts_for_product(product_id: str, hours: int = 6) -> list[dict]:
    """Check if we already sent an alert for this product in the last N hours (anti-spam)."""
    client = get_client()
    since = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    result = (
        client.table("alerts")
        .select("id")
        .eq("product_id", product_id)
        .gte("triggered_at", since)
        .execute()
    )
    return result.data or []


def get_recent_alerts(limit: int = 50) -> list[dict]:
    """Get the N most recent alerts."""
    client = get_client()
    result = (
        client.table("alerts")
        .select("*")
        .order("triggered_at", desc=True)
        .limit(limit)
        .execute()
    )
    return result.data or []
