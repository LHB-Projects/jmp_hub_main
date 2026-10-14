"""
api/reports.py — Data aggregation and crunching.
Pure functions — no API calls, no GUI. Takes raw order/labor data and
returns clean, structured results that pages can display or export.
"""


def aggregate_mix(orders: list, server_guid: str = None) -> list:
    """
    Aggregates order selections into a product-mix summary.

    Args:
        orders:      Raw order list from fetch_all_orders().
        server_guid: If provided, only include orders for that server.

    Returns:
        List of dicts sorted by net sales descending:
        [{"menuItemName": str, "quantitySold": int, "netSalesAmount": float}, ...]
    """
    mix = {}
    for order in orders:
        if server_guid and (order.get("server") or {}).get("guid") != server_guid:
            continue
        for check in order.get("checks", []):
            for sel in check.get("selections", []):
                if sel.get("voidDate") or sel.get("voided"):
                    continue
                name  = (sel.get("displayName")
                         or (sel.get("item") or {}).get("name")
                         or "Unknown")
                qty   = sel.get("quantity", 1) or 1
                price = float(sel.get("price", 0) or 0) * qty
                if name not in mix:
                    mix[name] = {"quantitySold": 0, "netSalesAmount": 0.0}
                mix[name]["quantitySold"]   += qty
                mix[name]["netSalesAmount"] += price

    rows = [{"menuItemName": k, **v} for k, v in mix.items()]
    rows.sort(key=lambda r: r["netSalesAmount"], reverse=True)
    return rows


def aggregate_labor(time_entries: list, emp_map: dict, job_map: dict) -> list:
    """
    Aggregate time entries into a per-employee labor summary.

    Args:
        time_entries: Raw list from fetch_time_entries().
        emp_map:      {employee_guid: display_name}
        job_map:      {job_guid: job_title}

    Returns:
        List of dicts sorted by total hours descending:
        [
          {
            "guid":            str,
            "name":            str,
            "jobTitle":        str,
            "regularHours":    float,
            "overtimeHours":   float,
            "totalHours":      float,
            "hourlyWage":      float,
            "regularPay":      float,
            "overtimePay":     float,
            "totalPay":        float,
            "declaredTips":    float,
            "nonCashTips":     float,
            "totalTips":       float,
            "shifts":          int,
          },
          ...
        ]
    """
    summary = {}   # keyed by (emp_guid, job_guid)

    for entry in time_entries:
        if entry.get("deleted"):
            continue

        emp_ref = entry.get("employeeReference") or {}
        job_ref = entry.get("jobReference") or {}
        emp_guid = emp_ref.get("guid", "")
        job_guid = job_ref.get("guid", "")

        key = (emp_guid, job_guid)
        if key not in summary:
            summary[key] = {
                "guid":          emp_guid,
                "name":          emp_map.get(emp_guid, "Unknown"),
                "jobTitle":      job_map.get(job_guid, "Unknown"),
                "regularHours":  0.0,
                "overtimeHours": 0.0,
                "totalHours":    0.0,
                "hourlyWage":    float(entry.get("hourlyWage") or 0),
                "regularPay":    0.0,
                "overtimePay":   0.0,
                "totalPay":      0.0,
                "declaredTips":  0.0,
                "nonCashTips":   0.0,
                "totalTips":     0.0,
                "shifts":        0,
            }

        wage = float(entry.get("hourlyWage") or 0)
        reg  = float(entry.get("regularHours")  or 0)
        ot   = float(entry.get("overtimeHours") or 0)

        summary[key]["regularHours"]  += reg
        summary[key]["overtimeHours"] += ot
        summary[key]["totalHours"]    += reg + ot
        summary[key]["regularPay"]    += reg * wage
        summary[key]["overtimePay"]   += ot  * wage * 1.5
        summary[key]["totalPay"]      += (reg * wage) + (ot * wage * 1.5)
        summary[key]["declaredTips"]  += float(entry.get("declaredCashTips") or 0)
        summary[key]["nonCashTips"]   += float(entry.get("nonCashTips")      or 0)
        summary[key]["totalTips"]     += (float(entry.get("declaredCashTips") or 0)
                                        + float(entry.get("nonCashTips")      or 0))
        summary[key]["shifts"]        += 1

        # Keep the wage from the latest entry (in case it changed)
        if wage:
            summary[key]["hourlyWage"] = wage

    rows = list(summary.values())
    rows.sort(key=lambda r: r["totalHours"], reverse=True)
    return rows


def calculate_nightly_summary(orders: list) -> dict:
    """
    Stub — compute high-level nightly numbers from orders.
    Will be implemented when the Notes page is built.

    Returns:
        {
          "netSales": float,
          "covers": int,
          "avgCheck": float,
          "totalVoids": float,
          "totalDiscounts": float,
        }
    """
    # TODO: implement when notes page is ready
    raise NotImplementedError("calculate_nightly_summary is not yet implemented.")
