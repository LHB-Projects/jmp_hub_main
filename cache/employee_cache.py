"""
cache/employee_cache.py — Save and load the employee list to/from disk.
Avoids hitting the Toast API on every app launch.
"""
import json
import os
from datetime import datetime
from config import CACHE_FILE, DATA_DIR


def load() -> dict | None:
    """
    Returns cached data dict or None if no cache exists.
    Dict shape: {"cached_at": ISO string, "employees": [...]}
    jobTitles lists are converted back to sets on load.
    """
    try:
        if os.path.exists(CACHE_FILE):
            with open(CACHE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            for emp in data.get("employees", []):
                emp["jobTitles"] = set(emp.get("jobTitles", []))
            return data
    except Exception:
        pass
    return None


def save(employees: list) -> None:
    """
    Serialize the employee list to disk.
    Sets are converted to lists for JSON compatibility.
    """
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        serializable = [
            {**emp, "jobTitles": list(emp.get("jobTitles", set()))}
            for emp in employees
        ]
        with open(CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "cached_at": datetime.now().isoformat(),
                "employees": serializable,
            }, f, indent=2)
    except Exception:
        pass


def cache_timestamp(cached_at: str) -> str:
    """Format the cached_at ISO string into a human-readable label."""
    try:
        return datetime.fromisoformat(cached_at).strftime("%b %d  %I:%M %p")
    except Exception:
        return cached_at[:16]
