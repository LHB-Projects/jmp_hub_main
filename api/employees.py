"""
api/employees.py — Fetch employees and jobs from the Toast Labor API.
"""
import requests
from config import BASE_URL, RESTAURANT_GUID


def fetch_jobs(token: str) -> dict:
    """Returns {job_guid: title} for all active jobs."""
    resp = requests.get(
        f"{BASE_URL}/labor/v1/jobs",
        headers={"Authorization": f"Bearer {token}",
                 "Toast-Restaurant-External-ID": RESTAURANT_GUID},
        timeout=30,
    )
    resp.raise_for_status()
    return {j["guid"]: j.get("title", "")
            for j in resp.json() if not j.get("deleted")}


def fetch_employees(token: str, job_map: dict) -> list:
    """
    Returns all active employees, each with a 'jobTitles' set injected.
    Sorted alphabetically by last name, then first name.
    """
    resp = requests.get(
        f"{BASE_URL}/labor/v1/employees",
        headers={"Authorization": f"Bearer {token}",
                 "Toast-Restaurant-External-ID": RESTAURANT_GUID},
        timeout=30,
    )
    resp.raise_for_status()

    employees = []
    for e in resp.json():
        if e.get("deleted"):
            continue
        refs   = e.get("jobReferences") or []
        titles = {
            job_map.get(
                r.get("guid") or r.get("reference", {}).get("guid", ""), ""
            ).lower()
            for r in refs
        }
        e["jobTitles"] = titles
        employees.append(e)

    employees.sort(key=lambda e: (
        (e.get("lastName") or "").lower(),
        ((e.get("chosenName") or e.get("firstName")) or "").lower(),
    ))
    return employees
