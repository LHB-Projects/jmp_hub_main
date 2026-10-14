"""
api/orders.py — Fetch orders from the Toast Orders API.
"""
import requests
from config import BASE_URL, RESTAURANT_GUID


def _iso(dt) -> str:
    """
    Format a datetime for the Toast API.
    Required format: yyyy-MM-dd'T'HH:mm:ss.SSSZ  (e.g. 2026-06-08T00:00:00.000-0400)
    %z gives the offset without a colon (+0400 / -0400) which is what Toast expects.
    """
    if dt.tzinfo is not None:
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000%z")
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000+0000")


def fetch_all_orders(token: str, start_dt, end_dt, status_cb=None) -> list:
    """
    Pages through /orders/v2/ordersBulk for the given date range.
    Pass timezone-aware datetimes (e.g. localised to America/New_York) so
    Toast interprets the window in the restaurant's local time.
    Calls status_cb(message) on each page if provided.
    Returns a flat list of all order dicts.
    """
    headers = {
        "Authorization":                f"Bearer {token}",
        "Toast-Restaurant-External-ID": RESTAURANT_GUID,
    }
    params_base = {
        "startDate": _iso(start_dt),
        "endDate":   _iso(end_dt),
        "pageSize":  100,
    }

    all_orders, page = [], 1
    while True:
        if status_cb:
            status_cb(f"Fetching orders… page {page}")
        resp = requests.get(
            f"{BASE_URL}/orders/v2/ordersBulk",
            headers=headers,
            params={**params_base, "page": page},
            timeout=60,
        )
        resp.raise_for_status()
        batch = resp.json()
        if not batch:
            break
        all_orders.extend(batch)
        if len(batch) < 100:
            break
        page += 1

    return all_orders
