"""
pages/product_mix.py — Product Mix report page.
"""
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import requests

from config import (BG, CARD, ENTRY, ACCENT, ACCENT2, BORDER,
                    FG, FG_DIM, FG_MUTE,
                    FONT_TITLE, FONT_BODY, FONT_BODY_B, FONT_SMALL, FONT_BTN,
                    INCLUDED_JOB_TITLES, EXCLUDED_NAMES)
from state import state
from api.auth import get_token
from api.orders import fetch_all_orders
from api.reports import aggregate_mix
from export.excel import save_product_mix
from widgets.date_range_bar import DateRangeBar
from widgets.data_table import make_table


class ProductMixPage(tk.Frame):
    def __init__(self, parent, hub):
        super().__init__(parent, bg=BG)
        self._hub         = hub
        self._emp_vars    = {}   # guid -> (BoolVar, name, titles)
        self._result_tabs = {}
        self._start_dt    = None
        self._build()

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        self._build_emp_sidebar()
        self._build_right_panel()

    def _build_emp_sidebar(self):
        sb = tk.Frame(self, bg=CARD, width=210)
        sb.grid(row=0, column=0, sticky="nsew")
        sb.grid_propagate(False)

        tk.Label(sb, text="Employees", font=FONT_BODY_B, bg=CARD, fg=FG
                 ).pack(anchor="w", padx=12, pady=(12, 4))

        btn_row = tk.Frame(sb, bg=CARD)
        btn_row.pack(fill="x", padx=8, pady=(0, 4))
        for lbl, cmd in [("All", self._sel_all), ("None", self._sel_none),
                          ("Servers", self._sel_servers), ("Bartenders", self._sel_bars)]:
            tk.Button(btn_row, text=lbl, bg=ENTRY, fg=FG, relief="flat",
                      padx=4, pady=2, cursor="hand2", font=("Segoe UI", 8),
                      command=cmd).pack(side="left", padx=(0, 3))

        list_outer = tk.Frame(sb, bg=CARD)
        list_outer.pack(fill="both", expand=True, padx=4, pady=(0, 4))

        self._emp_scroll = ttk.Scrollbar(list_outer, orient="vertical")
        self._emp_scroll.pack(side="right", fill="y")
        self._emp_canvas = tk.Canvas(list_outer, bg=CARD, highlightthickness=0,
                                      yscrollcommand=self._emp_scroll.set)
        self._emp_canvas.pack(side="left", fill="both", expand=True)
        self._emp_scroll.config(command=self._emp_canvas.yview)

        self._emp_frame = tk.Frame(self._emp_canvas, bg=CARD)
        self._emp_win   = self._emp_canvas.create_window(
            (0, 0), window=self._emp_frame, anchor="nw")
        self._emp_frame.bind("<Configure>",
            lambda e: self._emp_canvas.configure(
                scrollregion=self._emp_canvas.bbox("all")))
        self._emp_canvas.bind("<Configure>",
            lambda e: self._emp_canvas.itemconfig(self._emp_win, width=e.width))
        self._emp_canvas.bind("<Enter>",
            lambda e: self._emp_canvas.bind_all("<MouseWheel>",
                lambda ev: self._emp_canvas.yview_scroll(
                    int(-1 * (ev.delta / 120)), "units")))
        self._emp_canvas.bind("<Leave>",
            lambda e: self._emp_canvas.unbind_all("<MouseWheel>"))

        foot = tk.Frame(sb, bg=CARD)
        foot.pack(fill="x", padx=8, pady=(0, 8))
        self._emp_status = tk.Label(foot, text="Loading…", bg=CARD,
                                     fg=FG_MUTE, font=("Segoe UI", 8, "italic"))
        self._emp_status.pack(side="left")
        tk.Button(foot, text="⟳ Refresh", bg=ENTRY, fg=FG_MUTE, relief="flat",
                  padx=5, pady=2, font=("Segoe UI", 8), cursor="hand2",
                  command=self._hub.refresh_employees).pack(side="right")

    def _build_right_panel(self):
        right = tk.Frame(self, bg=BG)
        right.grid(row=0, column=1, sticky="nsew", padx=16, pady=16)
        right.columnconfigure(0, weight=1)
        right.rowconfigure(3, weight=1)

        # Page header
        hdr = tk.Frame(right, bg=BG)
        hdr.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        tk.Label(hdr, text="Product Mix Reports", font=FONT_TITLE, bg=BG, fg=FG
                 ).pack(side="left")
        tk.Frame(hdr, bg=BORDER, width=1).pack(side="left", fill="y", padx=16)
        tk.Label(hdr, text="Sales by menu item, per server or bartender",
                 font=FONT_BODY, bg=BG, fg=FG_DIM).pack(side="left")

        # Date bar
        self._date_bar = DateRangeBar(right)
        self._date_bar.grid(row=1, column=0, sticky="ew", pady=(0, 12))

        # Controls
        ctrl = tk.Frame(right, bg=BG)
        ctrl.grid(row=2, column=0, sticky="w", pady=(0, 8))
        self._pull_btn = tk.Button(ctrl, text="▶  Pull Report", bg=ACCENT, fg="white",
                                    activebackground=ACCENT2, font=FONT_BTN,
                                    relief="flat", padx=20, pady=9,
                                    cursor="hand2", command=self._pull)
        self._pull_btn.pack(side="left")
        self._export_btn = tk.Button(ctrl, text="⬇  Export to Excel",
                                      bg="#1e4d1e", fg="white",
                                      activebackground="#2a6a2a", font=FONT_BTN,
                                      relief="flat", padx=14, pady=9,
                                      cursor="hand2", command=self._export)
        self._status_var = tk.StringVar(value="Ready")
        tk.Label(ctrl, textvariable=self._status_var, bg=BG, fg=FG_MUTE,
                 font=FONT_SMALL).pack(side="left", padx=(14, 0))

        # Results notebook
        self._notebook = ttk.Notebook(right, style="TNotebook")
        self._notebook.grid(row=3, column=0, sticky="nsew", pady=(8, 0))

        self._totals_var = tk.StringVar(value="")
        tk.Label(right, textvariable=self._totals_var, bg=BG, fg=FG,
                 font=FONT_BODY_B, anchor="e").grid(row=4, column=0, sticky="ew")

    # ── Employee list ─────────────────────────────────────────────────────────
    def populate_employees(self, employees: list, cache_ts: str = ""):
        for w in self._emp_frame.winfo_children():
            w.destroy()
        self._emp_vars = {}

        for emp in employees:
            guid   = emp.get("guid", "")
            first  = emp.get("chosenName") or emp.get("firstName", "")
            last   = emp.get("lastName", "")
            name   = f"{first} {last}".strip() or guid
            titles = emp.get("jobTitles", set())

            if not (titles & INCLUDED_JOB_TITLES):
                continue
            if name.lower() in EXCLUDED_NAMES:
                continue

            var = tk.BooleanVar(value=True)
            self._emp_vars[guid] = (var, name, titles)

            row_f = tk.Frame(self._emp_frame, bg=CARD)
            row_f.pack(fill="x", padx=4, pady=1)
            tk.Checkbutton(row_f, text=name, variable=var, bg=CARD, fg=FG,
                           selectcolor=ENTRY, activebackground=CARD,
                           anchor="w", font=("Segoe UI", 9),
                           cursor="hand2").pack(side="left", fill="x", expand=True)
            badge = ("S+B" if "server" in titles and "bartender" in titles
                     else "SRV" if "server" in titles
                     else "BAR" if "bartender" in titles else "")
            if badge:
                tk.Label(row_f, text=badge, bg=ENTRY, fg=FG_MUTE,
                         font=("Segoe UI", 7), padx=3
                         ).pack(side="right", padx=(0, 4))

        count = len(self._emp_vars)
        ts    = f"  •  cached {cache_ts}" if cache_ts else "  (live)"
        self._emp_status.config(text=f"{count} staff{ts}")
        self._status_var.set("Ready")

    def _sel_all(self):
        for v, _, __ in self._emp_vars.values():  v.set(True)
    def _sel_none(self):
        for v, _, __ in self._emp_vars.values():  v.set(False)
    def _sel_servers(self):
        for v, _, t in self._emp_vars.values():   v.set("server" in t)
    def _sel_bars(self):
        for v, _, t in self._emp_vars.values():   v.set("bartender" in t)
    def _selected(self):
        return [(g, n) for g, (v, n, _) in self._emp_vars.items() if v.get()]

    # ── Pull ──────────────────────────────────────────────────────────────────
    def _pull(self):
        try:
            start, end = self._date_bar.get_range()
        except ValueError as e:
            messagebox.showwarning("Date", str(e));  return

        sel = self._selected()
        self._pull_btn.configure(state="disabled", text="Pulling…")
        self._export_btn.pack_forget()
        self._totals_var.set("")
        for tab in self._notebook.tabs():
            self._notebook.forget(tab)
        self._result_tabs = {}

        def cb(msg):
            self.after(0, lambda m=msg: self._status_var.set(m))

        def worker():
            try:
                token  = state.token or get_token()
                orders = fetch_all_orders(token, start, end, status_cb=cb)
                self.after(0, lambda: self._build_tabs(orders, sel, start))
            except requests.HTTPError as e:
                msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                self.after(0, lambda: self._err(msg))
            except Exception as e:
                self.after(0, lambda: self._err(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _build_tabs(self, orders, sel, start_dt):
        self._start_dt = start_dt
        cols = [("item","Menu Item",340,"w"), ("qty","Qty Sold",90,"center"),
                ("net","Net Sales",120,"e")]
        tabs = [("All", None, aggregate_mix(orders))]
        for guid, name in sel:
            tabs.append((name, guid, aggregate_mix(orders, server_guid=guid)))

        grand_qty = grand_net = 0
        for label, _, rows in tabs:
            frame, tree = make_table(self._notebook, "T.Treeview", cols)
            for row in rows:
                tree.insert("", "end", values=(
                    row["menuItemName"], row["quantitySold"],
                    f"${row['netSalesAmount']:,.2f}"))
            self._notebook.add(frame, text=f"  {label}  ")
            self._result_tabs[label] = rows
            if label == "All":
                grand_qty = sum(r["quantitySold"] for r in rows)
                grand_net = sum(r["netSalesAmount"] for r in rows)

        self._totals_var.set(
            f"All:   {grand_qty} items sold   ${grand_net:,.2f} net sales")
        self._status_var.set(
            f"Done — {len(orders)} orders, {len(sel)} employee(s)")
        self._pull_btn.configure(state="normal", text="▶  Pull Report")
        self._export_btn.pack(side="left", padx=(10, 0))

    def _err(self, msg):
        self._status_var.set(f"Error: {msg}")
        self._pull_btn.configure(state="normal", text="▶  Pull Report")
        messagebox.showerror("Error", msg)

    def _export(self):
        if not self._result_tabs:
            return
        folder = filedialog.askdirectory(title="Choose export folder")
        if not folder:
            return
        try:
            saved = save_product_mix(self._result_tabs, self._start_dt, folder)
            messagebox.showinfo("Saved",
                f"Saved {len(saved)} file(s) to:\n{folder}\n\n" + "\n".join(saved))
        except Exception as e:
            messagebox.showerror("Export Error", str(e))

    def on_show(self):
        """Called by the hub when this page becomes active."""
        pass
