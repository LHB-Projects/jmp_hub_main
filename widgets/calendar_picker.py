"""
widgets/calendar_picker.py — Standalone calendar popup (no third-party deps).
Usage:
    CalendarPicker(parent, "Select Date", initial_date, callback_fn)
    callback_fn receives a datetime.date object when a day is clicked.
"""
import tkinter as tk
import calendar
from datetime import date
from config import CARD, ENTRY, ACCENT, FG, FONT_BODY_B


class CalendarPicker(tk.Toplevel):
    def __init__(self, parent, title: str, initial: date, on_select):
        super().__init__(parent)
        self.title(title)
        self.configure(bg=CARD)
        self.resizable(False, False)
        self.grab_set()

        self._on_select = on_select
        self._year      = initial.year
        self._month     = initial.month
        self._selected  = initial

        self._build()
        self._render()

    def _build(self):
        nav = tk.Frame(self, bg=CARD)
        nav.pack(fill="x", padx=10, pady=(10, 4))
        tk.Button(nav, text="◀", bg=ENTRY, fg=FG, relief="flat", width=3,
                  cursor="hand2", command=self._prev).pack(side="left")
        self._header = tk.Label(nav, bg=CARD, fg=FG,
                                font=("Segoe UI Semibold", 11), width=18)
        self._header.pack(side="left", expand=True)
        tk.Button(nav, text="▶", bg=ENTRY, fg=FG, relief="flat", width=3,
                  cursor="hand2", command=self._next).pack(side="right")

        self._gf = tk.Frame(self, bg=CARD)
        self._gf.pack(padx=10, pady=(0, 10))
        for c, d in enumerate(["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]):
            tk.Label(self._gf, text=d, bg=ACCENT, fg="white",
                     font=FONT_BODY_B, width=4, pady=4
                     ).grid(row=0, column=c, padx=1, pady=1)

    def _render(self):
        for w in self._gf.grid_slaves():
            if int(w.grid_info()["row"]) > 0:
                w.destroy()

        self._header.config(
            text=f"{calendar.month_name[self._month]}  {self._year}")

        for r, week in enumerate(calendar.monthcalendar(self._year, self._month), 1):
            for c, day in enumerate(week):
                if day == 0:
                    tk.Label(self._gf, bg=CARD, width=4
                             ).grid(row=r, column=c, padx=1, pady=1)
                    continue
                d   = date(self._year, self._month, day)
                sel = (d == self._selected)
                tk.Button(self._gf, text=str(day), width=4,
                          bg=ACCENT if sel else ENTRY,
                          fg="white" if sel else FG,
                          relief="flat", cursor="hand2",
                          command=lambda dd=d: self._pick(dd)
                          ).grid(row=r, column=c, padx=1, pady=1)

    def _prev(self):
        self._month -= 1
        if self._month == 0:
            self._month, self._year = 12, self._year - 1
        self._render()

    def _next(self):
        self._month += 1
        if self._month == 13:
            self._month, self._year = 1, self._year + 1
        self._render()

    def _pick(self, d: date):
        self._on_select(d)
        self.destroy()
