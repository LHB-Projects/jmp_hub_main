"""
main.py — Entry point for the J. Michael's Prime Manager Hub.
Run this file to launch the app:  python main.py
"""
import tkinter as tk
from tkinter import ttk
import threading

from config import (BG, SIDEBAR, CARD, ENTRY, ACCENT, ACCENT2, BORDER,
                    FG, FG_DIM, FG_MUTE,
                    FONT_BODY, FONT_BODY_B, FONT_SMALL, FONT_BTN,
                    FONT_SIDE, FONT_SIDE_B, FONT_MONO,
                    SIDEBAR_W)
from state import state
from api.auth import get_token
from api.employees import fetch_jobs, fetch_employees
from cache.employee_cache import load, save, cache_timestamp
from pages.product_mix import ProductMixPage
from pages.labor import LaborPage
from pages.notes import NotesPage
from pages.catering import CateringPage

# Sidebar navigation items: (page_key, monogram, display_title)
NAV_ITEMS = [
    ("product_mix", "PM", "Product Mix"),
    ("labor",       "LB", "Labor Summary"),
    ("notes",       "NW", "Nightly & Weekly Notes"),
    ("catering",    "CT", "Catering Checklists"),
]


class HubApp(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("J. Michael's Prime  —  Manager Hub")
        self.geometry("1280x780")
        self.minsize(1000, 640)
        self.configure(bg=BG)

        self._active_page = None
        self._nav_widgets = {}
        self._pages       = {}

        self._build_styles()
        self._build_layout()
        self._select("product_mix", animate=False)
        self.after(300, self._load_employees)

    # ── Styles ────────────────────────────────────────────────────────────────
    def _build_styles(self):
        s = ttk.Style(self)
        s.theme_use("clam")
        s.configure("T.Treeview", background=CARD, foreground=FG,
                    fieldbackground=CARD, rowheight=24, font=FONT_BODY)
        s.configure("T.Treeview.Heading", background=ACCENT, foreground="white",
                    font=FONT_BTN, relief="flat")
        s.map("T.Treeview", background=[("selected", ACCENT)])
        s.configure("TNotebook", background=BG, borderwidth=0)
        s.configure("TNotebook.Tab", background=ENTRY, foreground=FG,
                    padding=[12, 6], font=FONT_BODY)
        s.map("TNotebook.Tab",
              background=[("selected", ACCENT)],
              foreground=[("selected", "white")])

    # ── Layout ────────────────────────────────────────────────────────────────
    def _build_layout(self):
        self._sidebar = tk.Frame(self, bg=SIDEBAR, width=SIDEBAR_W)
        self._sidebar.pack(side="left", fill="y")
        self._sidebar.pack_propagate(False)

        tk.Frame(self, bg=BORDER, width=1).pack(side="left", fill="y")

        self._content = tk.Frame(self, bg=BG)
        self._content.pack(side="left", fill="both", expand=True)

        self._build_sidebar()
        self._build_pages()

    def _build_sidebar(self):
        sb = self._sidebar

        # Brand
        brand = tk.Frame(sb, bg=SIDEBAR)
        brand.pack(fill="x", padx=20, pady=(24, 0))
        tk.Label(brand, text="J. MICHAEL'S", font=("Segoe UI Semibold", 13),
                 bg=SIDEBAR, fg=FG).pack(anchor="w")
        tk.Label(brand, text="PRIME", font=("Segoe UI Black", 18),
                 bg=SIDEBAR, fg=ACCENT).pack(anchor="w")
        tk.Frame(sb, bg=ACCENT, height=2, width=60).pack(anchor="w", padx=20, pady=(6, 0))
        tk.Label(sb, text="MANAGER  HUB", font=("Segoe UI Semibold", 8),
                 bg=SIDEBAR, fg=FG_MUTE).pack(anchor="w", padx=20, pady=(4, 16))

        tk.Frame(sb, bg=BORDER, height=1).pack(fill="x", padx=16, pady=(0, 8))
        tk.Label(sb, text="MODULES", font=("Segoe UI Semibold", 8),
                 bg=SIDEBAR, fg=FG_MUTE).pack(anchor="w", padx=20, pady=(8, 4))

        for key, mono, title in NAV_ITEMS:
            self._nav_widgets[key] = self._make_nav_btn(sb, key, mono, title)

        tk.Frame(sb, bg=SIDEBAR).pack(fill="both", expand=True)
        tk.Frame(sb, bg=BORDER, height=1).pack(fill="x", padx=16)
        foot = tk.Frame(sb, bg=SIDEBAR)
        foot.pack(fill="x", padx=20, pady=12)
        tk.Label(foot, text="Internal Use Only", font=FONT_SMALL,
                 bg=SIDEBAR, fg=FG_MUTE).pack(anchor="w")
        tk.Label(foot, text="© J. Michael's Prime", font=FONT_SMALL,
                 bg=SIDEBAR, fg=FG_MUTE).pack(anchor="w")

    def _make_nav_btn(self, parent, key, mono, title):
        wrapper = tk.Frame(parent, bg=SIDEBAR, cursor="hand2")
        wrapper.pack(fill="x", padx=8, pady=2)
        wrapper.columnconfigure(2, weight=1)

        stripe = tk.Frame(wrapper, bg=SIDEBAR, width=3)
        stripe.grid(row=0, column=0, sticky="ns")

        badge = tk.Label(wrapper, text=mono, bg=ENTRY, fg=ACCENT,
                         font=FONT_MONO, width=2, height=1, padx=2, pady=2)
        badge.grid(row=0, column=1, padx=(10, 10), pady=8)

        label = tk.Label(wrapper, text=title, bg=SIDEBAR, fg=FG_DIM,
                         font=FONT_SIDE, anchor="w")
        label.grid(row=0, column=2, sticky="ew", padx=(0, 10), pady=8)

        def enter(e):
            if self._active_page != key:
                wrapper.configure(bg=CARD)
                label.configure(bg=CARD, fg=FG)

        def leave(e):
            if self._active_page != key:
                wrapper.configure(bg=SIDEBAR)
                label.configure(bg=SIDEBAR, fg=FG_DIM)

        def click(e):
            self._select(key)

        for w in (wrapper, stripe, badge, label):
            w.bind("<Enter>", enter)
            w.bind("<Leave>", leave)
            w.bind("<Button-1>", click)

        return {"wrapper": wrapper, "stripe": stripe, "badge": badge, "label": label}

    def _select(self, key, animate=True):
        self._active_page = key
        for k, parts in self._nav_widgets.items():
            active = (k == key)
            parts["wrapper"].configure(bg=CARD if active else SIDEBAR)
            parts["stripe"].configure(bg=ACCENT if active else SIDEBAR)
            parts["badge"].configure(bg=ACCENT if active else ENTRY,
                                     fg="black" if active else ACCENT)
            parts["label"].configure(bg=CARD if active else SIDEBAR,
                                     fg=FG if active else FG_DIM,
                                     font=FONT_SIDE_B if active else FONT_SIDE)
        for k, page in self._pages.items():
            if k == key:
                page.tkraise()
                page.on_show()

    # ── Pages ─────────────────────────────────────────────────────────────────
    def _build_pages(self):
        page_classes = {
            "product_mix": ProductMixPage,
            "labor":       LaborPage,
            "notes":       NotesPage,
            "catering":    CateringPage,
        }
        for key, _, __ in NAV_ITEMS:
            page = page_classes[key](self._content, hub=self)
            page.place(relx=0, rely=0, relwidth=1, relheight=1)
            self._pages[key] = page

    # ── Employee loading (shared across all pages) ────────────────────────────
    def _load_employees(self):
        cached = load()
        if cached:
            state.employees = cached["employees"]
            ts = cache_timestamp(cached.get("cached_at", ""))
            self._push_employees(cache_ts=ts)
            threading.Thread(target=self._background_auth, daemon=True).start()
        else:
            self._fetch_from_api()

    def _background_auth(self):
        try:
            state.token = get_token()
        except Exception:
            pass

    def refresh_employees(self):
        """Called by any page's ⟳ Refresh button."""
        self._pages["product_mix"]._emp_status.config(text="Refreshing…")
        self._fetch_from_api()

    def _fetch_from_api(self):
        def worker():
            try:
                token = get_token()
                state.token = token
                job_map   = fetch_jobs(token)
                employees = fetch_employees(token, job_map)
                state.employees = employees
                save(employees)
                self.after(0, lambda: self._push_employees(from_api=True))
            except Exception as ex:
                self.after(0, lambda: self._pages["product_mix"]._emp_status.config(
                    text=f"Error: {ex}"))
        threading.Thread(target=worker, daemon=True).start()

    def _push_employees(self, cache_ts: str = "", from_api: bool = False):
        ts = "" if from_api else cache_ts
        self._pages["product_mix"].populate_employees(state.employees, cache_ts=ts)
        # Add other pages here as they gain employee lists


if __name__ == "__main__":
    HubApp().mainloop()
