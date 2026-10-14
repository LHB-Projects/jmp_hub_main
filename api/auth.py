"""
api/auth.py — Toast authentication.
"""
import requests
from config import BASE_URL, CLIENT_ID, CLIENT_SECRET


def get_token() -> str:
    """Exchange client credentials for a Toast bearer token."""
    resp = requests.post(
        f"{BASE_URL}/authentication/v1/authentication/login",
        json={
            "clientId":       CLIENT_ID,
            "clientSecret":   CLIENT_SECRET,
            "userAccessType": "TOAST_MACHINE_CLIENT",
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["token"]["accessToken"]
