"""
catering/store.py — Data model and persistence for Catering Checklists.

Everything (all checklists + the item library) lives in data/catering_data.json.
On first run, data is copied over from the old standalone Catering App if found.
"""
import json
import os

from config import DATA_DIR, CATERING_FILE, LEGACY_CATERING_FILE

# Starting item library: (category, item, default qty)
DEFAULT_ITEMS = [
    ("Hot Food Service", "Chafing Dishes", ""),
    ("Hot Food Service", "Steam Pans", ""),
    ("Hot Food Service", "Steam Pan Lids", ""),
    ("Hot Food Service", "Steam Pan Dividers", ""),
    ("Hot Food Service", "Steam Pan Stands", ""),
    ("Hot Food Service", "Sterno Fuel", ""),
    ("Hot Food Service", "Lighter", ""),
    ("Hot Food Service", "Portable Hotbox", ""),
    ("Hot Food Service", "Coffee Equipment (Carafe)", ""),
    ("Serving Utensils", "Serving Spoons", ""),
    ("Serving Utensils", "Serving Tongs", ""),
    ("Serving Utensils", "Small Ladles", ""),
    ("Serving Utensils", "Large Ladles", ""),
    ("Tabletop & Place Settings", "Tablecloths / Linens", ""),
    ("Tabletop & Place Settings", "Disposable Plates", ""),
    ("Tabletop & Place Settings", "Bowls", ""),
    ("Tabletop & Place Settings", "Disposable Glassware / Cups", ""),
    ("Tabletop & Place Settings", "Flatware Sets (Gold)", ""),
    ("Tabletop & Place Settings", "Knives", ""),
    ("Tabletop & Place Settings", "Forks", ""),
    ("Tabletop & Place Settings", "Spoons", ""),
    ("Tabletop & Place Settings", "Napkins", ""),
    ("Tabletop & Place Settings", "Straws", ""),
    ("Tabletop & Place Settings", "Placards", ""),
    ("Beverage & Cooling", "Ice", ""),
    ("Beverage & Cooling", "Ice Scoop", ""),
    ("Beverage & Cooling", "Coolers", ""),
    ("Beverage & Cooling", "Drink Dispensers", ""),
    ("Beverage & Cooling", "Cold Box", ""),
    ("Beverage & Cooling", "Gallon Water", ""),
    ("Beverage & Cooling", "Sweeteners", ""),
    ("Beverage & Cooling", "Lemons", ""),
    ("Cleanup & Sanitation", "Kitchen Towels", ""),
    ("Cleanup & Sanitation", "Trash Bags", ""),
    ("Cleanup & Sanitation", "Sanitizer Buckets", ""),
    ("Cleanup & Sanitation", "Quat Sanitizer", ""),
    ("Site & Logistics", "Dolly", ""),
    ("Site & Logistics", "Aprons", ""),
]

META_FIELDS    = [("date", "Date"), ("location", "Location"), ("guests", "Guests")]
ITEM_FIELDS    = [("category", "Category"), ("item", "Item"), ("qty", "Qty Needed"), ("notes", "Notes")]
LIBRARY_FIELDS = [("category", "Category"), ("item", "Item"), ("qty", "Default Qty")]


def make_item(cat, name, qty, notes=""):
    return {"category": cat, "item": name, "qty": qty, "notes": notes,
            "packed": False, "loaded": False}


def blank_list(name):
    return {"name": name, "date": "", "location": "", "guests": "", "items": []}


def item_key(d):
    """Identity of an item, used to match checklist items against the library."""
    return (d["category"].strip().lower(), d["item"].strip().lower())


def insert_grouped(items, new):
    """Insert after the last item of the same category to keep groups together."""
    idx = max((n for n, i in enumerate(items) if i["category"] == new["category"]),
              default=len(items) - 1)
    items.insert(idx + 1, new)


def safe_filename(name):
    return "".join(ch if ch.isalnum() or ch in " -_" else "_" for ch in name).strip() or "Checklist"


def _read(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def load_data():
    """Load hub catering data, migrating from the standalone app on first run."""
    data = {}
    if os.path.exists(CATERING_FILE):
        data = _read(CATERING_FILE)
    elif os.path.exists(LEGACY_CATERING_FILE):
        data = _read(LEGACY_CATERING_FILE)

    data.setdefault("catalog", [{"category": c, "item": n, "qty": q} for c, n, q in DEFAULT_ITEMS])
    if not data.get("lists"):
        lst = blank_list("Standard Event")
        lst["items"] = [make_item(c, n, q) for c, n, q in DEFAULT_ITEMS]
        data["lists"] = [lst]

    # Fill in any fields missing from older files
    for lst in data["lists"]:
        for key, _ in META_FIELDS:
            lst.setdefault(key, "")
        for it in lst.setdefault("items", []):
            it.setdefault("qty", "")
            it.setdefault("notes", "")
            it.setdefault("packed", False)
            it.setdefault("loaded", False)

    data["current"] = min(max(data.get("current", 0), 0), len(data["lists"]) - 1)
    if not os.path.exists(CATERING_FILE):
        save_data(data)
    return data


def save_data(data):
    os.makedirs(DATA_DIR, exist_ok=True)
    tmp = CATERING_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    os.replace(tmp, CATERING_FILE)  # never leaves a half-written file behind
