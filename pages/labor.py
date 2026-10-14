"""
pages/labor.py — Labor Summary page.
Shows hours, wages, tips, and overtime per employee for any date range.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import requests

from config import (BG, CARD, ENTRY, ACCENT, ACCENT2, BORDER,
                    FG, FG_DIM, FG_MUTE,
                    FONT_TITLE, FONT_H2, FONT_BODY, FONT_BODY_B, FONT_SMALL, FONT_BTN)
from state import state
from api.auth import get_token
from api.labor import fetch_time_entries
from api.employees import fetch_jobs
from api.reports import aggregate_labor
from export.excel import save_labor_summary
from widgets.date_range_bar import DateRangeBar
from widgets.data_table import make_table

# Columns shown in the main table
TABLE_COLS = [
    ("name",     "Employee",     180, "w"),
    ("job",      "Job",          110, "w"),
    ("reg_hrs",  "Reg Hrs",       75, "center"),
    ("ot_hrs",   "OT Hrs",        70, "center"),
    ("tot_hrs",  "Total Hrs",     80, "center"),
    ("wage",     "Wage",          70, "e"),
    ("tot_pay",  "Est. Pay",      90, "e"),
    ("tot_tips", "Total Tips",    90, "e"),
]

# Map column id → row dict key (for sorting)
COL_SORT_KEY = {
    "name":     "name",
    "job":      "jobTitle",
    "reg_hrs":  "regularHours",
    "ot_hrs":   "overtimeHours",
    "tot_hrs":  "totalHours",
    "wage":     "hourlyWage",
    "tot_pay":  "totalPay",
    "tot_tips": "totalTips",
}

# Stat card definitions: (label, row_key, format)
STAT_CARDS = [
    ("Total Hours",    "totalHours",    "{:.1f} hrs"),
    ("Regular Hours",  "regularHours",  "{:.1f} hrs"),
    ("Overtime Hours", "overtimeHours", "{:.1f} hrs"),
    ("Est. Labor Cost","totalPay",      "${:,.2f}"),
    ("Total Tips",     "totalTips",     "${:,.2f}"),
    ("Avg Hrs/Shift",  None,            None),   # computed specially
]


class LaborPage(tk.Frame):
    def __init__(self, parent, hub):
        super().__init__(parent, bg=BG)
        self._hub      = hub
        self._rows     = []
        self._start_dt = None
        self._end_dt   = None
        self._sort_col = None
        self._sort_rev = False
        self._build()

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # Page header
        hdr = tk.Frame(self, bg=BG)
        hdr.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
        tk.Label(hdr, text="Labor Summary", font=FONT_TITLE, bg=BG, fg=FG).pack(side="left")
        tk.Frame(hdr, bg=BORDER, width=1).pack(side="left", fill="y", padx=16)
        tk.Label(hdr, text="Hours, wages, tips & overtime by employee",
                 font=FONT_BODY, bg=BG, fg=FG_DIM).pack(side="left")

        # Controls row
        ctrl_wrap = tk.Frame(self, bg=BG)
        ctrl_wrap.grid(row=1, column=0, sticky="ew", padx=24, pady=(14, 0))
        ctrl_wrap.columnconfigure(0, weight=1)

        self._date_bar = DateRangeBar(ctrl_wrap)
        self._date_bar.grid(row=0, column=0, sticky="ew", pady=(0, 10))

        btn_row = tk.Frame(ctrl_wrap, bg=BG)
        btn_row.grid(row=1, column=0, sticky="w", pady=(0, 12))

        self._pull_btn = tk.Button(btn_row, text="▶  Pull Labor Data",
                                    bg=ACCENT, fg="white",
                                    activebackground=ACCENT2,
                                    font=FONT_BTN, relief="flat",
                                    padx=20, pady=9, cursor="hand2",
                                    command=self._pull)
        self._pull_btn.pack(side="left")

        self._export_btn = tk.Button(btn_row, text="⬇  Export to Excel",
                                      bg="#1e4d1e", fg="white",
                                      activebackground="#2a6a2a",
                                      font=FONT_BTN, relief="flat",
                                      padx=14, pady=9, cursor="hand2",
                                      command=self._export)
        # shown after pull

        self._status_var = tk.StringVar(value="Ready")
        tk.Label(btn_row, textvariable=self._status_var, bg=BG, fg=FG_MUTE,
                 font=FONT_SMALL).pack(side="left", padx=(14, 0))

        # Main content: stat cards on left, table on right
        content = tk.Frame(self, bg=BG)
        content.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 16))
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        self._build_stat_panel(content)
        self._build_table_panel(content)

    def _build_stat_panel(self, parent):
        """Left column of summary stat cards."""
        panel = tk.Frame(parent, bg=BG, width=170)
        panel.grid(row=0, column=0, sticky="nsew", padx=(0, 12))
        panel.grid_propagate(False)

        tk.Label(panel, text="SUMMARY", font=("Segoe UI Semibold", 8),
                 bg=BG, fg=FG_MUTE).pack(anchor="w", pady=(0, 6))

        self._stat_labels = {}
        for label, key, fmt in STAT_CARDS:
            card = tk.Frame(panel, bg=CARD, highlightthickness=1,
                            highlightbackground=BORDER)
            card.pack(fill="x", pady=4)
            tk.Label(card, text=label, font=FONT_SMALL, bg=CARD,
                     fg=FG_MUTE).pack(anchor="w", padx=12, pady=(8, 2))
            val_lbl = tk.Label(card, text="—", font=FONT_H2, bg=CARD, fg=FG)
            val_lbl.pack(anchor="w", padx=12, pady=(0, 8))
            self._stat_labels[label] = val_lbl

        # OT legend
        ot_card = tk.Frame(panel, bg="#3a2a00", highlightthickness=1,
                           highlightbackground="#7a5a00")
        ot_card.pack(fill="x", pady=(12, 0))
        tk.Label(ot_card, text="🟡  Overtime rows highlighted",
                 font=FONT_SMALL, bg="#3a2a00", fg="#fbbf24",
                 wraplength=148, justify="left").pack(padx=10, pady=8)

    def _build_table_panel(self, parent):
        """Right: treeview table + per-row detail strip."""
        right = tk.Frame(parent, bg=BG)
        right.grid(row=0, column=1, sticky="nsew")
        right.columnconfigure(0, weight=1)
        right.rowconfigure(1, weight=1)

        tk.Label(right, text="By Employee", font=FONT_BODY_B,
                 bg=BG, fg=FG).grid(row=0, column=0, sticky="w", pady=(0, 6))

        tbl_frame, self._tree = make_table(right, "T.Treeview", TABLE_COLS)
        tbl_frame.grid(row=1, column=0, sticky="nsew")

        # Wire sortable column headings
        for col_id, heading, _, __ in TABLE_COLS:
            self._tree.heading(col_id, text=heading,
                               command=lambda c=col_id: self._sort_by(c))

        # OT tag — highlight row yellow if overtime > 0
        self._tree.tag_configure("ot", background="#3a2f00", foreground="#fbbf24")

        # Click a row → show detail strip
        self._tree.bind("<<TreeviewSelect>>", self._on_select)

        # Detail strip below table
        self._detail = tk.Frame(right, bg=CARD, highlightthickness=1,
                                highlightbackground=BORDER)
        self._detail.grid(row=2, column=0, sticky="ew", pady=(8, 0))
        self._detail_var = tk.StringVar(value="Click a row to see full detail")
        tk.Label(self._detail, textvariable=self._detail_var, bg=CARD,
                 fg=FG_DIM, font=FONT_SMALL, anchor="w",
                 wraplength=900, justify="left").pack(
            anchor="w", padx=14, pady=10)

    # ── Pull ──────────────────────────────────────────────────────────────────
    def _pull(self):
        try:
            start, end = self._date_bar.get_range()
        except ValueError as e:
            messagebox.showwarning("Date", str(e));  return

        self._start_dt = start
        self._end_dt   = end
        self._pull_btn.configure(state="disabled", text="Pulling…")
        self._export_btn.pack_forget()
        self._tree.delete(*self._tree.get_children())
        self._clear_stats()
        self._detail_var.set("Click a row to see full detail")

        def cb(msg):
            self.after(0, lambda m=msg: self._status_var.set(m))

        def worker():
            try:
                token = state.token or get_token()
                cb("Fetching time entries…")
                entries = fetch_time_entries(token, start, end)

                cb("Fetching job titles…")
                job_map = fetch_jobs(token)

                cb("Aggregating…")
                # Build employee name map from shared state
                emp_map = {}
                for emp in state.employees:
                    guid  = emp.get("guid", "")
                    first = emp.get("chosenName") or emp.get("firstName", "")
                    last  = emp.get("lastName", "")
                    emp_map[guid] = f"{first} {last}".strip() or guid

                rows = aggregate_labor(entries, emp_map, job_map)
                self.after(0, lambda: self._display(rows))
            except requests.HTTPError as e:
                msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                self.after(0, lambda: self._err(msg))
            except Exception as e:
                self.after(0, lambda: self._err(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _display(self, rows):
        self._rows = rows
        self._tree.delete(*self._tree.get_children())

        for row in rows:
            ot_flag = row["overtimeHours"] > 0
            values  = (
                row["name"],
                row["jobTitle"],
                f"{row['regularHours']:.2f}",
                f"{row['overtimeHours']:.2f}",
                f"{row['totalHours']:.2f}",
                f"${row['hourlyWage']:.2f}",
                f"${row['totalPay']:.2f}",
                f"${row['totalTips']:.2f}",
            )
            self._tree.insert("", "end", values=values,
                              tags=("ot",) if ot_flag else ())

        self._update_stats(rows)
        n   = len(rows)
        ot  = sum(1 for r in rows if r["overtimeHours"] > 0)
        msg = f"Done — {n} employee record{'s' if n != 1 else ''}"
        if ot:
            msg += f"  •  ⚠ {ot} with overtime"
        self._status_var.set(msg)
        self._pull_btn.configure(state="normal", text="▶  Pull Labor Data")
        self._export_btn.pack(side="left", padx=(10, 0))

    def _sort_by(self, col_id):
        """Sort table by col_id; toggle direction on repeated clicks."""
        if self._sort_col == col_id:
            self._sort_rev = not self._sort_rev
        else:
            self._sort_col = col_id
            self._sort_rev = False

        key = COL_SORT_KEY.get(col_id, col_id)
        self._rows.sort(key=lambda r: (r[key] or "").lower()
                        if isinstance(r[key], str) else r[key],
                        reverse=self._sort_rev)

        # Update heading arrows
        arrow = " ▲" if not self._sort_rev else " ▼"
        for cid, heading, _, __ in TABLE_COLS:
            self._tree.heading(cid, text=heading + (arrow if cid == col_id else ""))

        # Repopulate rows (preserve OT tags)
        self._tree.delete(*self._tree.get_children())
        for row in self._rows:
            ot_flag = row["overtimeHours"] > 0
            values  = (
                row["name"],
                row["jobTitle"],
                f"{row['regularHours']:.2f}",
                f"{row['overtimeHours']:.2f}",
                f"{row['totalHours']:.2f}",
                f"${row['hourlyWage']:.2f}",
                f"${row['totalPay']:.2f}",
                f"${row['totalTips']:.2f}",
            )
            self._tree.insert("", "end", values=values,
                              tags=("ot",) if ot_flag else ())

    def _update_stats(self, rows):
        totals = {k: sum(r[k] for r in rows)
                  for k in ("totalHours", "regularHours", "overtimeHours",
                             "totalPay", "totalTips")}
        total_shifts = sum(r["shifts"] for r in rows)

        for label, key, fmt in STAT_CARDS:
            lbl = self._stat_labels[label]
            if key is None:  # Avg Hrs/Shift
                avg = totals["totalHours"] / total_shifts if total_shifts else 0
                lbl.config(text=f"{avg:.2f} hrs")
            else:
                lbl.config(text=fmt.format(totals[key]))

        # Color OT stat red if > 0
        ot_lbl = self._stat_labels["Overtime Hours"]
        ot_lbl.config(fg="#fbbf24" if totals["overtimeHours"] > 0 else FG)

    def _clear_stats(self):
        for lbl in self._stat_labels.values():
            lbl.config(text="—", fg=FG)

    def _on_select(self, _event):
        sel = self._tree.selection()
        if not sel:
            return
        idx   = self._tree.index(sel[0])
        if idx >= len(self._rows):
            return
        row   = self._rows[idx]
        parts = [
            f"Employee: {row['name']}",
            f"Job: {row['jobTitle']}",
            f"Shifts: {row['shifts']}",
            f"Reg Hrs: {row['regularHours']:.2f}",
            f"OT Hrs: {row['overtimeHours']:.2f}  {'⚠ OVERTIME' if row['overtimeHours'] > 0 else ''}",
            f"Total Hrs: {row['totalHours']:.2f}",
            f"Wage: ${row['hourlyWage']:.2f}/hr",
            f"Reg Pay: ${row['regularPay']:.2f}",
            f"OT Pay: ${row['overtimePay']:.2f}",
            f"Est. Total Pay: ${row['totalPay']:.2f}",
            f"Cash Tips: ${row['declaredTips']:.2f}",
            f"Non-Cash Tips: ${row['nonCashTips']:.2f}",
            f"Total Tips: ${row['totalTips']:.2f}",
        ]
        self._detail_var.set("    |    ".join(parts))

    def _err(self, msg):
        self._status_var.set(f"Error: {msg}")
        self._pull_btn.configure(state="normal", text="▶  Pull Labor Data")
        messagebox.showerror("Error", msg)

    # ── Export ────────────────────────────────────────────────────────────────
    def _export(self):
        if not self._rows:
            return
        folder = filedialog.askdirectory(title="Choose export folder")
        if not folder:
            return
        try:
            fname = save_labor_summary(
                self._rows, self._start_dt, self._end_dt, folder)
            messagebox.showinfo("Saved", f"Saved to:\n{folder}\\{fname}")
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def on_show(self):
        pass
