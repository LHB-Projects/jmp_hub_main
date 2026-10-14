"""
pages/notes.py — Nightly Notes & Sales Tracker page.

Workflow:
  1. Pick a date (defaults to yesterday)
  2. ▶ Pull from Toast  — fills sales, labor actuals, covers, top sellers
  3. Fill manual fields  — LY sales, projected, scheduled labor, narratives
  4. 💾 Save to Tracker — writes actuals to the correct cell in the Excel workbook
  5. 📋 Copy Email      — formats and copies the nightly recap to clipboard
"""
import tkinter as tk
from tkinter import messagebox
import threading
import datetime
import requests

from zoneinfo import ZoneInfo

from config import (BG, CARD, ENTRY, ACCENT, ACCENT2, BORDER,
                    FG, FG_DIM, FG_MUTE,
                    FONT_TITLE, FONT_H2, FONT_BODY, FONT_BODY_B,
                    FONT_SMALL, FONT_BTN,
                    TRACKER_PATH, RESTAURANT_TZ)
from state import state
from api.auth import get_token
from api.orders import fetch_all_orders
from api.labor import fetch_time_entries
from api.employees import fetch_jobs
from api.notes import aggregate_day_sales, classify_labor, top_sellers_text
from api.reports import aggregate_labor
from export.excel import write_day_to_tracker
from widgets.calendar_picker import CalendarPicker


class NotesPage(tk.Frame):
    def __init__(self, parent, hub):
        super().__init__(parent, bg=BG)
        self._hub          = hub
        self._report_date  = datetime.date.today() - datetime.timedelta(days=1)
        self._tracker_path = TRACKER_PATH
        self._build()

    # ── Utility helpers ───────────────────────────────────────────────────────
    def _pf(self, v) -> float:
        """Parse a StringVar (or plain str) to float, stripping $, commas, +."""
        s = v.get() if hasattr(v, "get") else str(v)
        try:
            return float(
                s.replace("$", "").replace(",", "").replace("+", "").strip() or "0"
            )
        except ValueError:
            return 0.0

    def _fmt_money(self, val: float) -> str:
        return f"${val:,.2f}"

    def _fmt_pct(self, val: float) -> str:
        return f"{val:.1f}%"

    # ── Widget factories ──────────────────────────────────────────────────────
    def _scrollable(self, parent, col, padx=(0, 0)):
        """
        Create a Canvas-backed scrollable frame in parent at grid column `col`.
        Returns (outer_frame, inner_frame).
        """
        outer = tk.Frame(parent, bg=BG)
        outer.grid(row=0, column=col, sticky="nsew", padx=padx)
        outer.rowconfigure(0, weight=1)
        outer.columnconfigure(0, weight=1)

        canvas = tk.Canvas(outer, bg=BG, highlightthickness=0)
        sb = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        sb.grid(row=0, column=1, sticky="ns")
        canvas.grid(row=0, column=0, sticky="nsew")

        inner = tk.Frame(canvas, bg=BG)
        wid   = canvas.create_window((0, 0), window=inner, anchor="nw")

        canvas.bind("<Configure>",
                    lambda e: canvas.itemconfig(wid, width=e.width))
        inner.bind("<Configure>",
                   lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        def _mw(e):
            canvas.yview_scroll(int(-1 * (e.delta / 120)), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _mw))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        inner.columnconfigure(0, weight=1)
        return outer, inner

    def _sec(self, parent, title):
        """Orange section header bar."""
        tk.Label(parent, text=title, font=FONT_BODY_B, bg=ACCENT, fg="white",
                 anchor="w", padx=12, pady=6).pack(fill="x", pady=(10, 0))

    def _sub(self, parent, title):
        """Subdued sub-header label."""
        tk.Label(parent, text=title, font=FONT_SMALL, bg=BG, fg=ACCENT,
                 anchor="w", padx=14).pack(fill="x", pady=(6, 2))

    def _sep(self, parent):
        tk.Frame(parent, bg=BORDER, height=1).pack(fill="x", padx=12, pady=4)

    def _field(self, parent, label, prefix="", auto=False, calc=False):
        """
        One labeled row: [label | AUTO?] [ $? | entry-or-label ]
        Returns a StringVar bound to the value widget.
        auto=True  → tinted ENTRY bg, shows AUTO badge
        calc=True  → read-only Label (computed value, not user-editable)
        """
        var   = tk.StringVar()
        frame = tk.Frame(parent, bg=CARD, highlightthickness=1,
                         highlightbackground=BORDER)
        frame.pack(fill="x", pady=1)

        # Fixed-width label column
        lbl_f = tk.Frame(frame, bg=CARD, width=150)
        lbl_f.pack(side="left")
        lbl_f.pack_propagate(False)
        tk.Label(lbl_f, text=label, font=FONT_SMALL, bg=CARD,
                 fg=FG_DIM, anchor="w").pack(side="left", padx=(10, 2), pady=7)
        if auto:
            tk.Label(lbl_f, text="AUTO", font=("Segoe UI Semibold", 7),
                     bg=ACCENT, fg="white", padx=3, pady=1
                     ).pack(side="right", padx=(0, 4))

        # Value column
        val_f = tk.Frame(frame, bg=CARD)
        val_f.pack(side="left", fill="x", expand=True, padx=(0, 10))
        if prefix:
            tk.Label(val_f, text=prefix, font=FONT_BODY,
                     bg=CARD, fg=FG_MUTE).pack(side="left")

        if calc:
            tk.Label(val_f, textvariable=var, font=FONT_BODY_B,
                     bg=CARD, fg=FG, anchor="w", width=16
                     ).pack(side="left", pady=5)
        elif auto:
            tk.Entry(val_f, textvariable=var, bg="#1a2535", fg=FG,
                     insertbackground=FG, relief="flat",
                     font=FONT_BODY, width=16
                     ).pack(side="left", pady=5)
        else:
            tk.Entry(val_f, textvariable=var, bg=ENTRY, fg=FG,
                     insertbackground=FG, relief="flat",
                     font=FONT_BODY, width=16
                     ).pack(side="left", pady=5)
        return var

    def _textarea(self, parent, title, height=4, badge=None):
        """Titled text area. Returns the Text widget."""
        wrap = tk.Frame(parent, bg=BG)
        wrap.pack(fill="x", pady=(8, 2))

        hdr = tk.Frame(wrap, bg=ACCENT)
        hdr.pack(fill="x")
        tk.Label(hdr, text=title, font=FONT_BODY_B, bg=ACCENT, fg="white",
                 anchor="w", padx=12, pady=5).pack(side="left")
        if badge:
            tk.Label(hdr, text=badge, font=("Segoe UI Semibold", 7),
                     bg="white", fg=ACCENT, padx=5, pady=2
                     ).pack(side="left", padx=4)

        card = tk.Frame(wrap, bg=CARD, highlightthickness=1,
                        highlightbackground=BORDER)
        card.pack(fill="x")
        txt = tk.Text(card, bg=CARD, fg=FG, insertbackground=FG,
                      relief="flat", font=FONT_BODY, height=height,
                      padx=10, pady=8, wrap="word")
        txt.pack(fill="x")
        return txt

    # ── Build ─────────────────────────────────────────────────────────────────
    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # ── Header ──
        hdr = tk.Frame(self, bg=BG)
        hdr.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 0))
        tk.Label(hdr, text="Nightly Notes", font=FONT_TITLE,
                 bg=BG, fg=FG).pack(side="left")
        tk.Frame(hdr, bg=BORDER, width=1).pack(side="left", fill="y", padx=16)
        tk.Label(hdr, text="Sales summary, labor overview & nightly email",
                 font=FONT_BODY, bg=BG, fg=FG_DIM).pack(side="left")

        # ── Controls ──
        ctrl = tk.Frame(self, bg=BG)
        ctrl.grid(row=1, column=0, sticky="ew", padx=24, pady=(14, 0))

        tk.Label(ctrl, text="Date:", font=FONT_BODY,
                 bg=BG, fg=FG_DIM).pack(side="left")
        self._date_var = tk.StringVar(
            value=self._report_date.strftime("%A, %B %d, %Y"))
        tk.Button(ctrl, textvariable=self._date_var,
                  bg=ENTRY, fg=FG, font=FONT_BODY_B,
                  relief="flat", padx=14, pady=7, cursor="hand2",
                  command=self._pick_date
                  ).pack(side="left", padx=(6, 0))
        tk.Button(ctrl, text="Yesterday",
                  bg=ENTRY, fg=FG_DIM, font=FONT_SMALL,
                  relief="flat", padx=8, pady=6, cursor="hand2",
                  command=lambda: self._set_date(
                      datetime.date.today() - datetime.timedelta(days=1))
                  ).pack(side="left", padx=(6, 0))

        self._pull_btn = tk.Button(
            ctrl, text="▶  Pull from Toast",
            bg=ACCENT, fg="white", activebackground=ACCENT2,
            font=FONT_BTN, relief="flat", padx=20, pady=7,
            cursor="hand2", command=self._pull)
        self._pull_btn.pack(side="left", padx=(16, 0))

        tk.Button(ctrl, text="💾  Save to Tracker",
                  bg="#1e4d1e", fg="white", activebackground="#2a6a2a",
                  font=FONT_BTN, relief="flat", padx=14, pady=7,
                  cursor="hand2", command=self._save_to_tracker
                  ).pack(side="left", padx=(8, 0))

        tk.Button(ctrl, text="📋  Copy Email",
                  bg="#1a3a5c", fg="white", activebackground="#254d7a",
                  font=FONT_BTN, relief="flat", padx=14, pady=7,
                  cursor="hand2", command=self._copy_email
                  ).pack(side="left", padx=(8, 0))

        self._status_var = tk.StringVar(value="Ready — select a date and pull")
        tk.Label(ctrl, textvariable=self._status_var, bg=BG, fg=FG_MUTE,
                 font=FONT_SMALL).pack(side="left", padx=(14, 0))

        # ── Main content ──
        content = tk.Frame(self, bg=BG)
        content.grid(row=2, column=0, sticky="nsew", padx=24, pady=(12, 16))
        content.columnconfigure(0, minsize=390)
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        self._build_left(content)
        self._build_right(content)

    # ── Left panel: structured numeric fields ─────────────────────────────────
    def _build_left(self, parent):
        outer, inner = self._scrollable(parent, col=0, padx=(0, 12))
        outer.configure(width=390)
        outer.grid_propagate(False)

        # ── SALES ──
        self._sec(inner, "💰  SALES")
        self._lunch_v   = self._field(inner, "Lunch Sales",     "$", auto=True)
        self._dinner_v  = self._field(inner, "Dinner Sales",    "$", auto=True)
        self._net_v     = self._field(inner, "Total Net Sales",  "$", calc=True)
        self._sep(inner)
        self._ly_v      = self._field(inner, "LY Sales",         "$")
        self._updown_v  = self._field(inner, "Up / Down",        "$", calc=True)
        self._proj_v    = self._field(inner, "Projected Sales",  "$")
        self._vs_proj_v = self._field(inner, "vs Projected",     "$", calc=True)

        for v in (self._lunch_v, self._dinner_v, self._ly_v, self._proj_v):
            v.trace_add("write", lambda *_: self._recalc_sales())

        # ── LABOR ──
        self._sec(inner, "⏱  LABOR")
        self._sub(inner, "FOH  (Hospitality)")
        self._foh_sched_hrs_v = self._field(inner, "Sched Hours")
        self._foh_sched_pay_v = self._field(inner, "Sched $",       "$")
        self._foh_act_hrs_v   = self._field(inner, "Actual Hours",       auto=True)
        self._foh_act_pay_v   = self._field(inner, "Actual $",      "$", auto=True)
        self._foh_labor_pct_v = self._field(inner, "Labor %",       "%", calc=True)
        self._foh_proj_pct_v  = self._field(inner, "Proj Labor %",  "%", calc=True)

        self._sep(inner)
        self._sub(inner, "BOH  (Culinary)")
        self._boh_sched_hrs_v = self._field(inner, "Sched Hours")
        self._boh_sched_pay_v = self._field(inner, "Sched $",       "$")
        self._boh_act_hrs_v   = self._field(inner, "Actual Hours",       auto=True)
        self._boh_act_pay_v   = self._field(inner, "Actual $",      "$", auto=True)
        self._boh_labor_pct_v = self._field(inner, "Labor %",       "%", calc=True)
        self._boh_proj_pct_v  = self._field(inner, "Proj Labor %",  "%", calc=True)

        self._sep(inner)
        self._tot_labor_pct_v = self._field(inner, "Total Labor %", "%", calc=True)

        labor_vars = (
            self._foh_sched_hrs_v, self._foh_sched_pay_v,
            self._foh_act_hrs_v,   self._foh_act_pay_v,
            self._boh_sched_hrs_v, self._boh_sched_pay_v,
            self._boh_act_hrs_v,   self._boh_act_pay_v,
        )
        for v in labor_vars:
            v.trace_add("write", lambda *_: self._recalc_labor())

        # ── GUEST METRICS ──
        self._sec(inner, "👥  GUEST METRICS")
        self._covers_v = self._field(inner, "Covers",          auto=True)
        self._tables_v = self._field(inner, "Tables Served")
        self._avg_v    = self._field(inner, "Avg Per Guest", "$", calc=True)

        self._covers_v.trace_add("write", lambda *_: self._recalc_guest())

    # ── Right panel: narrative text areas ─────────────────────────────────────
    def _build_right(self, parent):
        _, inner = self._scrollable(parent, col=1)

        self._bar_txt      = self._textarea(inner, "🍸  Bar Operations",     height=4)
        self._kitchen_txt  = self._textarea(inner, "🍳  Kitchen Operations",  height=4)
        self._sellers_txt  = self._textarea(inner, "🏆  Top Sellers",         height=15,
                                            badge="AUTO")
        self._specials_txt = self._textarea(inner, "⭐  Daily Specials",      height=3)

        # Water Sales — two inline counters
        w_wrap = tk.Frame(inner, bg=BG)
        w_wrap.pack(fill="x", pady=(8, 2))
        wh = tk.Frame(w_wrap, bg=ACCENT)
        wh.pack(fill="x")
        tk.Label(wh, text="💧  Water Sales", font=FONT_BODY_B,
                 bg=ACCENT, fg="white", anchor="w", padx=12, pady=5).pack(side="left")
        wcard = tk.Frame(w_wrap, bg=CARD, highlightthickness=1,
                         highlightbackground=BORDER)
        wcard.pack(fill="x")

        tk.Label(wcard, text="San Pellegrino:", font=FONT_SMALL,
                 bg=CARD, fg=FG_DIM
                 ).grid(row=0, column=0, padx=(14, 6), pady=10, sticky="w")
        self._sp_var = tk.StringVar()
        tk.Entry(wcard, textvariable=self._sp_var, bg=ENTRY, fg=FG,
                 insertbackground=FG, relief="flat", font=FONT_BODY, width=10
                 ).grid(row=0, column=1, sticky="w", pady=10)
        tk.Label(wcard, text="Acqua Panna:", font=FONT_SMALL,
                 bg=CARD, fg=FG_DIM
                 ).grid(row=0, column=2, padx=(24, 6), pady=10, sticky="w")
        self._ap_var = tk.StringVar()
        tk.Entry(wcard, textvariable=self._ap_var, bg=ENTRY, fg=FG,
                 insertbackground=FG, relief="flat", font=FONT_BODY, width=10
                 ).grid(row=0, column=3, sticky="w", pady=10)

        self._notes_txt = self._textarea(inner, "📝  Notes", height=3)

    # ── Date helpers ──────────────────────────────────────────────────────────
    def _pick_date(self):
        CalendarPicker(self, "Select Report Date",
                       self._report_date, self._set_date)

    def _set_date(self, d: datetime.date):
        self._report_date = d
        self._date_var.set(d.strftime("%A, %B %d, %Y"))

    # ── Live recalculation ────────────────────────────────────────────────────
    def _recalc_sales(self):
        lunch  = self._pf(self._lunch_v)
        dinner = self._pf(self._dinner_v)
        net    = lunch + dinner
        ly     = self._pf(self._ly_v)
        proj   = self._pf(self._proj_v)

        self._net_v.set(f"{net:,.2f}" if net else "")

        if ly:
            ud = net - ly
            self._updown_v.set(f"{'+' if ud >= 0 else ''}{ud:,.2f}")
        else:
            self._updown_v.set("—")

        if proj:
            vp = net - proj
            self._vs_proj_v.set(f"{'+' if vp >= 0 else ''}{vp:,.2f}")
        else:
            self._vs_proj_v.set("—")

        self._recalc_labor()
        self._recalc_guest()

    def _recalc_labor(self):
        net         = self._pf(self._net_v)
        foh_act_pay = self._pf(self._foh_act_pay_v)
        boh_act_pay = self._pf(self._boh_act_pay_v)
        foh_sch_pay = self._pf(self._foh_sched_pay_v)
        boh_sch_pay = self._pf(self._boh_sched_pay_v)

        def _pct(pay):
            return f"{pay / net * 100:.2f}%" if net else "—"

        self._foh_labor_pct_v.set(_pct(foh_act_pay))
        self._boh_labor_pct_v.set(_pct(boh_act_pay))
        self._tot_labor_pct_v.set(_pct(foh_act_pay + boh_act_pay))
        self._foh_proj_pct_v.set(_pct(foh_sch_pay))
        self._boh_proj_pct_v.set(_pct(boh_sch_pay))

    def _recalc_guest(self):
        covers = self._pf(self._covers_v)
        net    = self._pf(self._net_v)
        self._avg_v.set(f"{net / covers:,.2f}" if covers else "—")

    # ── Pull from Toast ───────────────────────────────────────────────────────
    def _pull(self):
        self._pull_btn.configure(state="disabled", text="Pulling…")
        d     = self._report_date
        tz    = ZoneInfo(RESTAURANT_TZ)
        start = datetime.datetime(d.year, d.month, d.day,  0,  0,  0, tzinfo=tz)
        end   = datetime.datetime(d.year, d.month, d.day, 23, 59, 59, tzinfo=tz)

        def cb(msg):
            self.after(0, lambda m=msg: self._status_var.set(m))

        def worker():
            try:
                token = state.token or get_token()

                cb("Fetching orders…")
                orders = fetch_all_orders(token, start, end, status_cb=cb)

                cb("Fetching time entries…")
                entries = fetch_time_entries(token, start, end)

                cb("Fetching job map…")
                job_map = fetch_jobs(token)

                cb("Aggregating…")
                sales = aggregate_day_sales(orders)

                emp_map = {}
                for emp in state.employees:
                    g     = emp.get("guid", "")
                    first = emp.get("chosenName") or emp.get("firstName", "")
                    last  = emp.get("lastName", "")
                    emp_map[g] = f"{first} {last}".strip() or g

                labor_rows = aggregate_labor(entries, emp_map, job_map)
                labor      = classify_labor(labor_rows)
                sellers    = top_sellers_text(orders)

                self.after(0, lambda: self._populate(sales, labor, sellers))
            except requests.HTTPError as e:
                msg = f"HTTP {e.response.status_code}: {e.response.text[:200]}"
                self.after(0, lambda: self._err(msg))
            except Exception as e:
                self.after(0, lambda: self._err(str(e)))

        threading.Thread(target=worker, daemon=True).start()

    def _populate(self, sales, labor, sellers):
        self._lunch_v.set(f"{sales['lunchSales']:.2f}")
        self._dinner_v.set(f"{sales['dinnerSales']:.2f}")
        self._covers_v.set(str(sales["covers"]))
        self._foh_act_hrs_v.set(f"{labor['fohHours']:.2f}")
        self._foh_act_pay_v.set(f"{labor['fohPay']:.2f}")
        self._boh_act_hrs_v.set(f"{labor['bohHours']:.2f}")
        self._boh_act_pay_v.set(f"{labor['bohPay']:.2f}")

        self._sellers_txt.delete("1.0", "end")
        self._sellers_txt.insert("1.0", sellers)

        d = self._report_date
        self._status_var.set(
            f"✓ Pulled {d.strftime('%A, %B %d')}  •  "
            f"{sales['covers']} covers  •  "
            f"net ${sales['netSales']:,.2f}"
        )
        self._pull_btn.configure(state="normal", text="▶  Pull from Toast")

    def _err(self, msg):
        self._status_var.set(f"Error: {msg}")
        self._pull_btn.configure(state="normal", text="▶  Pull from Toast")
        messagebox.showerror("Pull Error", msg)

    # ── Save to Tracker ───────────────────────────────────────────────────────
    def _save_to_tracker(self):
        def fv(v):
            val = self._pf(v)
            return round(val, 2) if val else None

        data = {
            "lunchSales":     fv(self._lunch_v),
            "dinnerSales":    fv(self._dinner_v),
            "fohActualHours": fv(self._foh_act_hrs_v),
            "fohActualPay":   fv(self._foh_act_pay_v),
            "bohActualHours": fv(self._boh_act_hrs_v),
            "bohActualPay":   fv(self._boh_act_pay_v),
            "fohSchedHours":  fv(self._foh_sched_hrs_v),
            "bohSchedHours":  fv(self._boh_sched_hrs_v),
            "fohSchedPay":    fv(self._foh_sched_pay_v),
            "bohSchedPay":    fv(self._boh_sched_pay_v),
            "lyDinnerSales":  fv(self._ly_v),
            "projDinner":     fv(self._proj_v),
            "notes":          self._notes_txt.get("1.0", "end-1c") or None,
        }

        try:
            write_day_to_tracker(self._report_date, data, self._tracker_path)
            messagebox.showinfo(
                "Saved ✓",
                f"Data written to tracker for "
                f"{self._report_date.strftime('%A, %B %d, %Y')}."
            )
        except Exception as e:
            messagebox.showerror("Save Error", str(e))

    # ── Copy Email ────────────────────────────────────────────────────────────
    def _copy_email(self):
        d = self._report_date

        # Sales block
        net_raw  = self._pf(self._net_v)
        ly_raw   = self._pf(self._ly_v)
        ud_raw   = net_raw - ly_raw if ly_raw else None
        net_str  = f"${net_raw:,.2f}" if net_raw else "—"
        ly_str   = f"${ly_raw:,.2f}" if ly_raw else "—"
        ud_str   = (f"{'+'if ud_raw >= 0 else ''}${abs(ud_raw):,.2f}"
                    if ud_raw is not None else "—")

        # Labor block
        foh_pct  = self._foh_labor_pct_v.get() or "—"
        boh_pct  = self._boh_labor_pct_v.get() or "—"
        tot_pct  = self._tot_labor_pct_v.get()  or "—"
        foh_proj = self._foh_proj_pct_v.get()   or "—"
        boh_proj = self._boh_proj_pct_v.get()   or "—"

        # Guest block
        covers   = self._covers_v.get() or "—"
        tables   = self._tables_v.get() or "—"
        avg_raw  = self._pf(self._avg_v)
        avg_str  = f"${avg_raw:,.2f}" if avg_raw else "—"

        # Narrative blocks
        bar_ops  = self._bar_txt.get("1.0", "end-1c")     or "(nothing to report)"
        kitchen  = self._kitchen_txt.get("1.0", "end-1c") or "(nothing to report)"
        sellers  = self._sellers_txt.get("1.0", "end-1c") or "(no data)"
        specials = self._specials_txt.get("1.0", "end-1c")or "(none)"
        notes_   = self._notes_txt.get("1.0", "end-1c")
        sp       = self._sp_var.get() or "—"
        ap       = self._ap_var.get() or "—"

        email = (
            f"Nightly Report — {d.strftime('%A, %B %d, %Y')}\n\n"
            f"Sales Numbers\n"
            f"Current Year Sales (CY): {net_str}\n"
            f"Last Year Sales (LY): {ly_str}\n"
            f"UP/DOWN: {ud_str}\n"
            f"\n\n"
            f"Labor Overview\n"
            f"FOH Labor Percentage: {foh_pct} (Projected: {foh_proj})\n"
            f"BOH Labor Percentage: {boh_pct} (Projected: {boh_proj})\n"
            f"Total Labor Percentage: {tot_pct}\n"
            f"\n\n"
            f"Guest Experience & Dining Room Metrics\n"
            f"Total Tables Served: {tables}\n"
            f"Covers: {covers}\n"
            f"Overall Guest Count: {covers}\n"
            f"Average Per Guest: {avg_str}\n"
            f"\n\n"
            f"Bar Operations\n"
            f"{bar_ops}\n"
            f"\n\n"
            f"Kitchen Operations\n"
            f"{kitchen}\n"
            f"\n\n"
            f"Top Sellers\n"
            f"{sellers}\n"
            f"\n\n"
            f"Daily Specials\n"
            f"{specials}\n"
            f"\n\n"
            f"Water Sales\n"
            f"San Pellegrino - {sp}\n"
            f"Acqua Panna - {ap}\n"
        )

        if notes_:
            email += f"\n\nNotes\n{notes_}\n"

        email += (
            "\n\n"
            "Best regards,\n\n"
            "Lucas Browne\n"
            "Assistant General Manager\n"
            "J Michael's Prime\n"
            "770-213-4058"
        )

        self.clipboard_clear()
        self.clipboard_append(email)
        self._status_var.set(
            "✓ Email copied to clipboard — paste directly into Outlook or Gmail")

    def on_show(self):
        pass
