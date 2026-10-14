"""
state.py — Shared application state passed between pages.
Holds the API token and employee list so every module can
access them without redundant API calls.
"""


class AppState:
    token: str     = None   # Toast bearer token (refreshed as needed)
    employees: list = []    # Fully annotated employee list from cache or API


# Single global instance imported by all pages and the hub
state = AppState()
