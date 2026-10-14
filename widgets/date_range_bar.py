"""
widgets/date_range_bar.py — Reusable date-range selector strip.
Drop this into any page that needs Yesterday / This Week / Custom etc.

Usage:
    bar = DateRangeBar(parent_frame)
    bar.pack(fill="x")
    ...
    start, end = bar.get_range()   # raises ValueError if nothing selected
"""
import tkinter as tk
from datetime import date, timedelta, datetime
from zoneinfo import ZoneInfo
from config import (CARD, ENTRY, ACCENT, FG, FG_DIM, FG_MUTE,
                    FONT_BODY, FONT_BODY_B, FONT_SMALL, RESTAURANT_TZ)
from widgets.calendar_picker import CalendarPicker

_tz = ZoneInfo(RESTAURANT_TZ)


def _to_local(d: date, end=False) -> datetime:
    """Return a timezone-aware datetime at the start or end of `d` in restaurant local time."""
    h, m, s = (23, 59, 59) if end else (0, 0, 0)
    return datetime(d.year, d.month, d.day, h, m, s, tzinfo=_tz)

def range_yesterday():
    d = date.today() - timedelta(days=1);  return _to_local(d), _to_local(d, end=True)
def range_this_week():
    t = date.today();  s = t - timedelta(days=t.weekday());  return _to_local(s), _to_local(t, end=True)
def range_last_week():
    t = date.today();  s = t - timedelta(days=t.weekday() + 7);  return _to_local(s), _to_local(s + timedelta(days=6), end=True)
def range_this_month():
    t = date.today();  return _to_local(t.replace(day=1)), _to_local(t, end=True)


class DateRangeBar(tk.Frame):
    def __init__(self, parent, on_change=None, **kw):
        super().__init__(parent, bg=CARD, **kw)
        self._on_change    = on_change
        self._active_range = None
        self._custom_from  = date.today() - timedelta(days=1)
        self._custom_to    = date.today() - timedelta(days=1)
        self._preset_btns  = {}
        self._build()

    def _build(self):
        tk.Label(self, text="Date Range", font=FONT_BODY_B, bg=CARD, fg=FG
                 ).grid(row=0, column=0, columnspan=6, sticky="w", padx=16, pady=(12, 6))

        presets = [("Yesterday", range_yesterday), ("This Week",  range_this_week),
                   ("Last Week", range_last_week),  ("This Month", range_this_month)]
        for i, (lbl, fn) in enumerate(presets):
            b = tk.Button(self, text=lbl, bg=ENTRY, fg=FG,
                          activebackground=ACCENT, activeforeground="white",
                          relief="flat", padx=8, pady=6, cursor="hand2",
                          command=lambda f=fn, l=lbl: self._preset(f, l))
            b.grid(row=1, column=i, padx=(16 if i == 0 else 4, 4), pady=(0, 4), sticky="ew")
            self.columnconfigure(i, weight=1)
            self._preset_btns[lbl] = b

        self._custom_btn = tk.Button(self, text="Custom", bg=ENTRY, fg=FG,
                                     activebackground=ACCENT, activeforeground="white",
                                     relief="flat", padx=8, pady=6, cursor="hand2",
                                     command=self._toggle_custom)
        self._custom_btn.grid(row=1, column=4, padx=(4, 16), pady=(0, 4), sticky="ew")
        self.columnconfigure(4, weight=1)

        self._custom_frame = tk.Frame(self, bg=CARD)
        self._custom_frame.grid(row=2, column=0, columnspan=5, sticky="w", padx=16, pady=(4, 0))
        self._custom_frame.grid_remove()

        tk.Label(self._custom_frame, text="From:", bg=CARD, fg=FG_MUTE,
                 font=FONT_SMALL).grid(row=0, column=0)
        self._from_lbl = tk.Label(self._custom_frame, bg=ENTRY, fg=FG,
                                   font=FONT_BODY, padx=10, pady=4, cursor="hand2", width=12)
        self._from_lbl.grid(row=0, column=1, padx=(6, 16))
        self._from_lbl.bind("<Button-1>", lambda e: self._open_cal("from"))

        tk.Label(self._custom_frame, text="To:", bg=CARD, fg=FG_MUTE,
                 font=FONT_SMALL).grid(row=0, column=2)
        self._to_lbl = tk.Label(self._custom_frame, bg=ENTRY, fg=FG,
                                 font=FONT_BODY, padx=10, pady=4, cursor="hand2", width=12)
        self._to_lbl.grid(row=0, column=3, padx=(6, 0))
        self._to_lbl.bind("<Button-1>", lambda e: self._open_cal("to"))
        self._refresh_labels()

        self._range_lbl = tk.Label(self, text="No range selected", font=FONT_SMALL,
                                    bg=CARD, fg=FG_MUTE, anchor="w")
        self._range_lbl.grid(row=3, column=0, columnspan=5, sticky="w", padx=16, pady=(6, 12))

    def _preset(self, fn, label):
        self._custom_frame.grid_remove()
        self._custom_btn.configure(bg=ENTRY, fg=FG)
        for l, b in self._preset_btns.items():
            b.configure(bg=ACCENT if l == label else ENTRY,
                        fg="white" if l == label else FG)
        s, e = fn()
        self._active_range = (s, e)
        self._range_lbl.config(
            text=f"{s.strftime('%b %d, %Y')}  →  {e.strftime('%b %d, %Y')}")
        if self._on_change:
            self._on_change(s, e)

    def _toggle_custom(self):
        if self._custom_frame.winfo_viewable():
            self._custom_frame.grid_remove()
            self._custom_btn.configure(bg=ENTRY, fg=FG)
        else:
            for b in self._preset_btns.values():
                b.configure(bg=ENTRY, fg=FG)
            self._custom_frame.grid()
            self._custom_btn.configure(bg=ACCENT, fg="white")
            self._active_range = None
            self._range_lbl.config(text="Pick start & end dates above")

    def _open_cal(self, which):
        init = self._custom_from if which == "from" else self._custom_to
        def on_sel(d):
            if which == "from":  self._custom_from = d
            else:                self._custom_to   = d
            self._refresh_labels()
        CalendarPicker(self.winfo_toplevel(), "Select Date", init, on_sel)

    def _refresh_labels(self):
        self._from_lbl.config(text=self._custom_from.strftime("%b %d, %Y"))
        self._to_lbl.config(  text=self._custom_to.strftime(  "%b %d, %Y"))

    def get_range(self):
        """Returns (start_dt, end_dt). Raises ValueError if nothing selected."""
        if self._custom_frame.winfo_viewable():
            if self._custom_from > self._custom_to:
                raise ValueError("'From' date must be before 'To' date.")
            return _to_local(self._custom_from), _to_local(self._custom_to, end=True)
        if self._active_range:
            return self._active_range
        raise ValueError("Please select a date range first.")
