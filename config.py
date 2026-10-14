"""
config.py — All credentials, API settings, and app-wide constants.
Change values here; nothing else in the codebase should hardcode these.
"""

# ── Toast API credentials ──────────────────────────────────────────────────────
CLIENT_ID       = "2lCEWYplYU3XnaaQQcjAFcQcPU8fiIfW"
CLIENT_SECRET   = "ERHI8D1WsgpPkCz2-HlpyhK8-UQ4yxYDHVt8i4FnQyRXaMcaDD7RgDgRyxoJuAzP"
RESTAURANT_GUID = "869615fc-f042-495c-9ab0-2d5b45295023"
BASE_URL        = "https://ws-api.toasttab.com"

# ── Employee display rules ─────────────────────────────────────────────────────
# Only employees with at least one of these job titles will appear in the UI
INCLUDED_JOB_TITLES = {"server", "bartender"}

# Employees whose full name (lowercase) should always be hidden
EXCLUDED_NAMES = {
    "pdr 1", "pdr 2", "pdr 3", "john doe",
}

# ── Paths ──────────────────────────────────────────────────────────────────────
import os
ROOT_DIR       = os.path.dirname(os.path.abspath(__file__))
DATA_DIR       = os.path.join(ROOT_DIR, "data")
CACHE_FILE     = os.path.join(DATA_DIR, "employee_cache.json")

# Catering Checklists — hub copy of the data, plus the old standalone app's file
# (copied over automatically the first time the Catering page opens)
CATERING_FILE        = os.path.join(DATA_DIR, "catering_data.json")
LEGACY_CATERING_FILE = os.path.join(os.path.dirname(ROOT_DIR), "Catering App", "catering_data.json")

# IANA timezone name for the restaurant — used to build correct API date ranges
RESTAURANT_TZ = "America/New_York"

# Path to the JMP Sales Tracker workbook (used by Nightly Notes page)
TRACKER_PATH = r"C:\Users\lhbro\OneDrive\Documents\JMP Sales Tracker 2026 UPDATED.xlsx"

# Item names (lowercase) to always exclude from the Top Sellers list.
# Add any event charges, room buyouts, or non-menu items here.
TOP_SELLERS_BLOCKLIST = {
    "captain's",
}

# Minimum quantity sold for an item to appear in Top Sellers.
# Filters out one-off event charges that would otherwise dominate the list.
TOP_SELLERS_MIN_QTY = 2

# ── Nightly Notes / Labor classification ───────────────────────────────────────
# Orders closed before this hour (24h) count as "lunch"; at/after = "dinner"
LUNCH_CUTOFF_HOUR = 16   # 4:00 PM

# Job title keywords that classify an employee as BOH (Culinary).
# Anything not matching is treated as FOH (Hospitality).
BOH_JOB_KEYWORDS = {
    "cook", "chef", "dishwasher", "dish", "prep", "kitchen",
    "culinary", "baker", "line", "expo", "expeditor",
}

# ── UI design tokens ───────────────────────────────────────────────────────────
ACCENT   = "#f05123"
ACCENT2  = "#c73e10"
BG       = "#0e1116"
SIDEBAR  = "#15191f"
CARD     = "#1a1f27"
ENTRY    = "#252b35"
BORDER   = "#2a313c"
FG       = "#e8eaed"
FG_DIM   = "#9aa0a6"
FG_MUTE  = "#6b7280"
SUCCESS  = "#4ade80"
WARNING  = "#fbbf24"
INFO     = "#60a5fa"

FONT_TITLE  = ("Segoe UI Semibold", 20)
FONT_H2     = ("Segoe UI Semibold", 13)
FONT_BODY   = ("Segoe UI", 10)
FONT_BODY_B = ("Segoe UI Semibold", 10)
FONT_SMALL  = ("Segoe UI", 9)
FONT_BTN    = ("Segoe UI Semibold", 10)
FONT_SIDE   = ("Segoe UI", 10)
FONT_SIDE_B = ("Segoe UI Semibold", 10)
FONT_MONO   = ("Segoe UI Semibold", 11)

SIDEBAR_W = 230
