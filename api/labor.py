"""
api/labor.py — Fetch labor / time-entry data from the Toast Labor API.
"""
import requests
from config import BASE_URL, RESTAURANT_GUID


def _iso(dt) -> str:
    """Toast requires yyyy-MM-dd'T'HH:mm:ss.SSSZ — %z gives offset without colon."""
    if dt.tzinfo is not None:
        return dt.strftime("%Y-%m-%dT%H:%M:%S.000%z")
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000+0000")


def fetch_time_entries(token: str, start_dt, end_dt) -> list:
    """
    Returns all time entries (clock-in / clock-out records) for the date range.
    Pass timezone-aware datetimes so the window aligns with the restaurant's
    local business day rather than UTC.
    Endpoint: GET /labor/v1/timeEntries
    """
    headers = {
        "Authorization":                f"Bearer {token}",
        "Toast-Restaurant-External-ID": RESTAURANT_GUID,
    }
    params = {
        "startDate": _iso(start_dt),
        "endDate":   _iso(end_dt),
    }
    resp = requests.get(
        f"{BASE_URL}/labor/v1/timeEntries",
        headers=headers,
        params=params,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()
