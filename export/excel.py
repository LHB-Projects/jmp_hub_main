"""
export/excel.py — Excel file generation.
All openpyxl logic lives here. Pages call these functions and
pass in the data — no GUI code inside this file.
"""
import os

try:
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment
    EXCEL_OK = True
except ImportError:
    EXCEL_OK = False

HEADER_FILL = None
HEADER_FONT = None
CENTER      = None

if EXCEL_OK:
    HEADER_FILL = PatternFill("solid", fgColor="003366")
    HEADER_FONT = Font(bold=True, color="FFFFFF")
    CENTER      = Alignment(horizontal="center")


def _check():
    if not EXCEL_OK:
        raise ImportError("openpyxl is not installed. Run: pip install openpyxl")


def save_product_mix(result_tabs: dict, start_dt, folder: str) -> list[str]:
    """
    Save one .xlsx per tab (employee) into `folder`.
    Each file has an 'Items' sheet matching the Contest Program format.

    Returns a list of saved filenames.
    """
    _check()
    date_str = start_dt.strftime("%Y-%m-%d")
    saved    = []

    for label, rows in result_tabs.items():
        safe  = label.replace(" ", "_").replace("/", "-")
        fname = os.path.join(folder, f"{safe}_{date_str}.xlsx")

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "Items"

        for col, h in enumerate(["Item", "Qty sold", "Net Sales"], 1):
            cell            = ws.cell(row=1, column=col, value=h)
            cell.fill       = HEADER_FILL
            cell.font       = HEADER_FONT
            cell.alignment  = CENTER

        for row in rows:
            ws.append([
                row.get("menuItemName", "Unknown"),
                row.get("quantitySold", 0),
                round(row.get("netSalesAmount", 0.0), 2),
            ])

        ws.column_dimensions["A"].width = 40
        ws.column_dimensions["B"].width = 12
        ws.column_dimensions["C"].width = 14

        wb.save(fname)
        saved.append(os.path.basename(fname))

    return saved


def save_labor_summary(rows: list, start_dt, end_dt, folder: str) -> str:
    """
    Save the labor summary as a single Excel file with two sheets:
      - 'Summary'  — one row per employee/job with totals
      - 'Detail'   — all individual shifts (if shift data is passed)

    Returns the saved filename.
    """
    _check()

    date_str  = f"{start_dt.strftime('%Y-%m-%d')}_to_{end_dt.strftime('%Y-%m-%d')}"
    fname     = os.path.join(folder, f"Labor_Summary_{date_str}.xlsx")

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "Labor Summary"

    col_headers = [
        "Employee", "Job Title", "Shifts",
        "Regular Hrs", "Overtime Hrs", "Total Hrs",
        "Hourly Wage", "Regular Pay", "Overtime Pay", "Total Pay",
        "Cash Tips", "Non-Cash Tips", "Total Tips",
    ]
    for col, h in enumerate(col_headers, 1):
        cell           = ws.cell(row=1, column=col, value=h)
        cell.fill      = HEADER_FILL
        cell.font      = HEADER_FONT
        cell.alignment = CENTER

    money_fmt = '#,##0.00'
    hours_fmt = '0.00'

    for row in rows:
        r = ws.max_row + 1
        values = [
            row["name"],
            row["jobTitle"],
            row["shifts"],
            row["regularHours"],
            row["overtimeHours"],
            row["totalHours"],
            row["hourlyWage"],
            row["regularPay"],
            row["overtimePay"],
            row["totalPay"],
            row["declaredTips"],
            row["nonCashTips"],
            row["totalTips"],
        ]
        for col, val in enumerate(values, 1):
            cell = ws.cell(row=r, column=col, value=val)
            if col in (4, 5, 6):    # hours
                cell.number_format = hours_fmt
            if col in (7, 8, 9, 10, 11, 12, 13):  # money
                cell.number_format = money_fmt

    # Totals row
    tr = ws.max_row + 1
    ws.cell(row=tr, column=1, value="TOTAL").font = Font(bold=True)
    total_cols = {4: "regularHours", 5: "overtimeHours", 6: "totalHours",
                  8: "regularPay",   9: "overtimePay",   10: "totalPay",
                  11: "declaredTips", 12: "nonCashTips",  13: "totalTips"}
    for col, field in total_cols.items():
        cell = ws.cell(row=tr, column=col,
                       value=round(sum(r[field] for r in rows), 2))
        cell.font = Font(bold=True)
        cell.number_format = hours_fmt if col <= 6 else money_fmt

    # Column widths
    widths = [22, 16, 8, 12, 13, 11, 12, 13, 14, 11, 11, 14, 11]
    for i, w in enumerate(widths, 1):
        ws.column_dimensions[ws.cell(1, i).column_letter].width = w

    # OT highlight — orange fill for any row with overtime > 0
    ot_fill = PatternFill("solid", fgColor="FFF3CD")
    for row_idx in range(2, tr):
        if (ws.cell(row=row_idx, column=5).value or 0) > 0:
            for col in range(1, len(col_headers) + 1):
                ws.cell(row=row_idx, column=col).fill = ot_fill

    wb.save(fname)
    return os.path.basename(fname)


def write_day_to_tracker(report_date, data: dict, tracker_path: str) -> None:
    """
    Write one day's nightly data into the correct cell of the JMP Sales Tracker.

    The tracker has 52 weekly sheets named "M-D-YYYY" (no leading zeros),
    where the date is the Monday of that week.  Columns B–G = Mon–Sat.

    data keys (all optional — None values are skipped):
      lunchSales, dinnerSales,
      fohActualHours, fohActualPay, bohActualHours, bohActualPay,
      fohSchedHours,  fohSchedPay,  bohSchedHours,  bohSchedPay,
      lyLunchSales,   lyDinnerSales,
      projLunch,      projDinner,
      notes
    """
    _check()
    from datetime import timedelta

    weekday = report_date.weekday()   # 0 = Monday … 5 = Saturday, 6 = Sunday
    if weekday == 6:
        raise ValueError("Sunday is not tracked in the Sales Tracker (Mon–Sat only).")

    monday     = report_date - timedelta(days=weekday)
    sheet_name = f"{monday.month}-{monday.day}-{monday.year}"

    wb = openpyxl.load_workbook(tracker_path)
    if sheet_name not in wb.sheetnames:
        available = ", ".join(s for s in wb.sheetnames if s != "Master_2025")[:120]
        raise ValueError(
            f"Sheet '{sheet_name}' not found in tracker.\n"
            f"Available sheets start with: {available}…"
        )

    ws  = wb[sheet_name]
    col = weekday + 2   # Mon→2(B), Tue→3(C), …, Sat→7(G)

    def _set(row, val):
        if val is not None:
            ws.cell(row=row, column=col, value=val)

    _set(24, data.get("lunchSales"))        # Actual Lunch Sales
    _set(25, data.get("dinnerSales"))       # Actual Dinner Sales
    _set(27, data.get("notes") or None)     # Notes
    _set(29, data.get("fohActualHours"))    # Actual FOH Hours
    _set(30, data.get("bohActualHours"))    # Actual BOH Hours
    _set(32, data.get("fohActualPay"))      # Actual FOH Labor $
    _set(33, data.get("bohActualPay"))      # Actual BOH Labor $
    _set(13, data.get("fohSchedHours"))     # Scheduled FOH Hours
    _set(14, data.get("bohSchedHours"))     # Scheduled BOH Hours
    _set(16, data.get("fohSchedPay"))       # Scheduled FOH Labor $
    _set(17, data.get("bohSchedPay"))       # Scheduled BOH Labor $
    _set(5,  data.get("lyLunchSales"))      # LY Lunch Sales
    _set(6,  data.get("lyDinnerSales"))     # LY Dinner Sales
    _set(8,  data.get("projLunch"))         # Projected Lunch $
    _set(9,  data.get("projDinner"))        # Projected Dinner $

    wb.save(tracker_path)


def save_nightly_notes(data: dict, report_date, folder: str) -> str:
    """Stub — kept for backward compat."""
    raise NotImplementedError("save_nightly_notes is not yet implemented.")
