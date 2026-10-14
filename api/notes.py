"""
api/notes.py — Single-day aggregation helpers for the Nightly Notes page.
Pure functions — no API calls, no GUI.
"""
from datetime import datetime
from config import LUNCH_CUTOFF_HOUR, BOH_JOB_KEYWORDS, TOP_SELLERS_BLOCKLIST, TOP_SELLERS_MIN_QTY


def aggregate_day_sales(orders: list,
                        cutoff_hour: int = LUNCH_CUTOFF_HOUR) -> dict:
    """
    Aggregate a list of orders for one day into a sales summary.
    Splits lunch vs. dinner by comparing the order's close hour to cutoff_hour.

    Returns:
        {
          "lunchSales":  float,
          "dinnerSales": float,
          "netSales":    float,
          "covers":      int,
        }
    """
    lunch_sales  = 0.0
    dinner_sales = 0.0
    covers       = 0

    for order in orders:
        # Determine meal period from close / paid / opened timestamp
        closed = (order.get("closedDate")
                  or order.get("paidDate")
                  or order.get("openedDate"))
        is_lunch = False
        if closed:
            try:
                ts = closed.replace("Z", "+00:00")
                dt = datetime.fromisoformat(ts)
                # Convert to local if needed — Toast typically returns UTC
                is_lunch = dt.hour < cutoff_hour
            except Exception:
                pass

        # Sum net sales from non-voided, non-blocklisted selections
        order_net = 0.0
        for check in order.get("checks", []):
            for sel in check.get("selections", []):
                if sel.get("voidDate") or sel.get("voided"):
                    continue
                name = (sel.get("displayName")
                        or (sel.get("item") or {}).get("name")
                        or "").lower()
                if name in TOP_SELLERS_BLOCKLIST:
                    continue
                qty   = float(sel.get("quantity", 1) or 1)
                price = float(sel.get("price", 0) or 0) * qty
                order_net += price

        if is_lunch:
            lunch_sales += order_net
        else:
            dinner_sales += order_net

        covers += int(order.get("numberOfGuests", 0) or 0)

    return {
        "lunchSales":  round(lunch_sales,  2),
        "dinnerSales": round(dinner_sales, 2),
        "netSales":    round(lunch_sales + dinner_sales, 2),
        "covers":      covers,
    }


def classify_labor(labor_rows: list) -> dict:
    """
    Split aggregated labor rows into FOH (Hospitality) and BOH (Culinary)
    based on job title keywords defined in config.BOH_JOB_KEYWORDS.

    Args:
        labor_rows: output of api.reports.aggregate_labor()

    Returns:
        {
          "fohHours": float,
          "fohPay":   float,
          "bohHours": float,
          "bohPay":   float,
        }
    """
    foh = {"hours": 0.0, "pay": 0.0}
    boh = {"hours": 0.0, "pay": 0.0}

    for row in labor_rows:
        title  = (row.get("jobTitle") or "").lower()
        is_boh = any(kw in title for kw in BOH_JOB_KEYWORDS)
        bucket = boh if is_boh else foh
        bucket["hours"] += row.get("totalHours", 0.0)
        bucket["pay"]   += row.get("totalPay",   0.0)

    return {
        "fohHours": round(foh["hours"], 2),
        "fohPay":   round(foh["pay"],   2),
        "bohHours": round(boh["hours"], 2),
        "bohPay":   round(boh["pay"],   2),
    }


def top_sellers_text(orders: list, n: int = 15) -> str:
    """
    Return the top N menu items as a formatted multi-line string
    suitable for pasting into the nightly email.

    Items are excluded if:
      - Their name (lowercase) is in TOP_SELLERS_BLOCKLIST, or
      - Their total quantity sold is below TOP_SELLERS_MIN_QTY.
    """
    from api.reports import aggregate_mix
    all_rows = aggregate_mix(orders)

    filtered = [
        r for r in all_rows
        if r["menuItemName"].lower() not in TOP_SELLERS_BLOCKLIST
        and r["quantitySold"] >= TOP_SELLERS_MIN_QTY
    ]

    rows = filtered[:n]
    if not rows:
        return "(no sales data)"

    lines = []
    for i, row in enumerate(rows, 1):
        lines.append(
            f"{i}. {row['menuItemName']}"
            f"  —  {int(row['quantitySold'])} sold"
            f"  /  ${row['netSalesAmount']:,.2f}"
        )
    return "\n".join(lines)
