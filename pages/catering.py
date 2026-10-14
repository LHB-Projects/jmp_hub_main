"""
pages/catering.py — Catering Checklists page.

Build, save, check off and print equipment checklists for off-site events.
  • Left panel   — saved checklists (new / duplicate / rename / delete)
  • Right panel  — event details, items grouped by category, Packed / Loaded checks
  • Item library — shared list of equipment that any checklist can pull from

Everything saves automatically to data/catering_data.json.
"""
import copy
import tempfile
import webbrowser
from pathlib import Path

import tkinter as tk
from tkinter import ttk, messagebox, filedialog

from config import (BG, CARD, ENTRY, ACCENT, BORDER,
                    FG, FG_DIM, FG_MUTE, SUCCESS,
                    FONT_TITLE, FONT_BODY, FONT_BODY_B, FONT_SMALL, FONT_BTN)
from catering.store import (META_FIELDS, load_data, save_data, make_item, blank_list,
                            item_key, insert_grouped, safe_filename)
from catering.output import build_print_html, write_xlsx
from catering.dialogs import (ItemDialog, ItemPicker, ask_string, button, entry,
                              BOX_ON, BOX_OFF)

STRIPE = "#1f252e"


class CateringPage(tk.Frame):
    def __init__(self, parent, hub):
        super().__init__(parent, bg=BG)
        self._hub     = hub
        self._loading = False
        self.data     = load_data()
        self._build_styles()
        self._build()
        self.refresh_lists()
        self.show_list()

    @property
    def cur(self):
        return self.data["lists"][self.data["current"]]

    # ── Styles ────────────────────────────────────────────────────────────────
    def _build_styles(self):
        s = ttk.Style(self)
        s.configure("Cat.Treeview", background=CARD, foreground=FG, fieldbackground=CARD,
                    rowheight=30, font=FONT_BODY, borderwidth=0)
        s.configure("Cat.Treeview.Heading", background=ACCENT, foreground="white",
                    font=FONT_BTN, relief="flat")
        s.map("Cat.Treeview", background=[("selected", "#3a2a22")],
              foreground=[("selected", FG)])
        s.map("Cat.Treeview.Heading", background=[("active", ACCENT)])
        s.configure("Cat.Horizontal.TProgressbar", troughcolor=ENTRY, background=SUCCESS,
                    bordercolor=BORDER, lightcolor=SUCCESS, darkcolor=SUCCESS)
        s.configure("Cat.TCombobox", fieldbackground=ENTRY, background=ENTRY,
                    foreground=FG, arrowcolor=FG, bordercolor=BORDER)
        s.map("Cat.TCombobox", fieldbackground=[("readonly", ENTRY)],
              foreground=[("readonly", FG)])
        top = self.winfo_toplevel()
        top.option_add("*TCombobox*Listbox.background", ENTRY)
        top.option_add("*TCombobox*Listbox.foreground", FG)
        top.option_add("*TCombobox*Listbox.selectBackground", ACCENT)
        top.option_add("*TCombobox*Listbox.font", FONT_BODY)

    # ── Build UI ──────────────────────────────────────────────────────────────
    def _build(self):
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        hdr = tk.Frame(self, bg=BG)
        hdr.grid(row=0, column=0, sticky="ew", padx=24, pady=(20, 14))
        tk.Label(hdr, text="Catering Checklists", font=FONT_TITLE, bg=BG, fg=FG).pack(side="left")
        tk.Frame(hdr, bg=BORDER, width=1).pack(side="left", fill="y", padx=16)
        tk.Label(hdr, text="Pack & load equipment lists for off-site events",
                 font=FONT_BODY, bg=BG, fg=FG_DIM).pack(side="left")

        content = tk.Frame(self, bg=BG)
        content.grid(row=1, column=0, sticky="nsew", padx=24, pady=(0, 16))
        content.columnconfigure(1, weight=1)
        content.rowconfigure(0, weight=1)

        self._build_lists_panel(content)
        self._build_main_panel(content)

    def _build_lists_panel(self, parent):
        side = tk.Frame(parent, bg=CARD, highlightthickness=1, highlightbackground=BORDER, width=210)
        side.grid(row=0, column=0, sticky="ns", padx=(0, 16))
        side.grid_propagate(False)
        side.pack_propagate(False)

        tk.Label(side, text="SAVED CHECKLISTS", font=("Segoe UI Semibold", 8),
                 bg=CARD, fg=FG_MUTE).pack(anchor="w", padx=14, pady=(14, 6))

        self.lists_box = tk.Listbox(side, activestyle="none", exportselection=False,
                                    font=FONT_BODY, bg=CARD, fg=FG_DIM, bd=0,
                                    relief="flat", highlightthickness=0,
                                    selectbackground=ACCENT, selectforeground="white")
        self.lists_box.pack(fill="both", expand=True, padx=8)
        self.lists_box.bind("<<ListboxSelect>>", self.on_list_select)
        self.lists_box.bind("<Double-1>", lambda e: self.rename_list())

        btns = tk.Frame(side, bg=CARD)
        btns.pack(fill="x", padx=10, pady=12)
        btns.columnconfigure((0, 1), weight=1)
        button(btns, "+ New", self.new_list, kind="primary", padx=6
               ).grid(row=0, column=0, sticky="ew", padx=(0, 3), pady=3)
        button(btns, "Duplicate", self.duplicate_list, padx=6
               ).grid(row=0, column=1, sticky="ew", padx=(3, 0), pady=3)
        button(btns, "Rename", self.rename_list, padx=6
               ).grid(row=1, column=0, sticky="ew", padx=(0, 3), pady=3)
        button(btns, "Delete", self.delete_list, kind="danger", padx=6
               ).grid(row=1, column=1, sticky="ew", padx=(3, 0), pady=3)

    def _build_main_panel(self, parent):
        main = tk.Frame(parent, bg=BG)
        main.grid(row=0, column=1, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(4, weight=1)

        # Checklist name
        self.name_lbl = tk.Label(main, font=("Segoe UI Semibold", 16), bg=BG, fg=FG, anchor="w")
        self.name_lbl.grid(row=0, column=0, sticky="ew")

        # Event details
        info = tk.Frame(main, bg=CARD, highlightthickness=1, highlightbackground=BORDER)
        info.grid(row=1, column=0, sticky="ew", pady=(8, 10))
        self.field_vars = {}
        for key, label in META_FIELDS:
            tk.Label(info, text=label.upper(), font=("Segoe UI Semibold", 8),
                     bg=CARD, fg=FG_MUTE).pack(side="left", padx=(14, 6), pady=10)
            var = tk.StringVar()
            entry(info, var, width={"location": 26}.get(key, 14)).pack(side="left", ipady=3)
            var.trace_add("write", lambda *a, k=key: self._set_field(k))
            self.field_vars[key] = var

        # Action bar
        bar = tk.Frame(main, bg=BG)
        bar.grid(row=2, column=0, sticky="ew")
        button(bar, "+  Add / Remove Items", self.pick_items, kind="primary").pack(side="left")
        button(bar, "Edit", self.edit_item).pack(side="left", padx=(6, 0))
        button(bar, "Remove", self.delete_item).pack(side="left", padx=(6, 0))
        button(bar, "Reset Checks", self.reset_checks).pack(side="left", padx=(6, 0))
        button(bar, "🖨  Print", self.print_list, kind="primary").pack(side="right")
        button(bar, "⬇  Excel", self.export_xlsx, kind="success").pack(side="right", padx=(0, 6))

        # Progress
        prog = tk.Frame(main, bg=BG)
        prog.grid(row=3, column=0, sticky="ew", pady=(12, 8))
        self.progress_lbl = tk.Label(prog, font=FONT_BODY_B, bg=BG, fg=FG_DIM)
        self.progress_lbl.pack(side="left")
        self.progress = ttk.Progressbar(prog, length=260, mode="determinate",
                                        style="Cat.Horizontal.TProgressbar")
        self.progress.pack(side="right")

        # Items table
        wrap = tk.Frame(main, bg=BG)
        wrap.grid(row=4, column=0, sticky="nsew")
        cols = ("qty", "packed", "loaded", "notes")
        self.tree = ttk.Treeview(wrap, columns=cols, show="tree headings",
                                 selectmode="browse", style="Cat.Treeview")
        self.tree.heading("#0", text="Item")
        self.tree.heading("qty", text="Qty Needed")
        self.tree.heading("packed", text="Packed")
        self.tree.heading("loaded", text="Loaded")
        self.tree.heading("notes", text="Notes")
        self.tree.column("#0", width=280)
        self.tree.column("qty", width=110, anchor="center")
        self.tree.column("packed", width=80, anchor="center")
        self.tree.column("loaded", width=80, anchor="center")
        self.tree.column("notes", width=240)
        self.tree.tag_configure("cat", font=FONT_BODY_B, background=ENTRY, foreground=ACCENT)
        self.tree.tag_configure("stripe", background=STRIPE)
        self.tree.tag_configure("done", foreground=SUCCESS)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.tree.bind("<Button-1>", self.on_click)
        self.tree.bind("<Double-1>", lambda e: self.edit_item())
        self.tree.bind("<Delete>", lambda e: self.delete_item())

        tk.Label(main, text="Click a Packed / Loaded box to check it off  •  Double-click an item to "
                            "edit qty & notes  •  Double-click a checklist to rename",
                 font=FONT_SMALL, bg=BG, fg=FG_MUTE, anchor="w"
                 ).grid(row=5, column=0, sticky="ew", pady=(8, 0))

    # ── Display ───────────────────────────────────────────────────────────────
    def refresh_lists(self):
        self.lists_box.delete(0, "end")
        for lst in self.data["lists"]:
            self.lists_box.insert("end", f"  {lst['name']}")
        self.lists_box.selection_set(self.data["current"])
        self.lists_box.see(self.data["current"])

    def show_list(self):
        lst = self.cur
        self.name_lbl.config(text=lst["name"])
        self._loading = True
        for key, var in self.field_vars.items():
            var.set(lst.get(key, ""))
        self._loading = False
        self.refresh()

    def refresh(self):
        items = self.cur["items"]
        open_state = {self.tree.item(i, "text"): self.tree.item(i, "open")
                      for i in self.tree.get_children()}
        self.tree.delete(*self.tree.get_children())
        cats = {}
        for idx, it in enumerate(items):
            cat = it["category"]
            if cat not in cats:
                cats[cat] = self.tree.insert("", "end", iid=f"g{len(cats)}", text=cat, tags=("cat",),
                                             open=open_state.get(cat, True))
            tags = ("done",) if it["packed"] and it["loaded"] else ()
            if len(self.tree.get_children(cats[cat])) % 2:
                tags += ("stripe",)
            self.tree.insert(cats[cat], "end", iid=f"i{idx}", text=it["item"], tags=tags,
                             values=(it["qty"], BOX_ON if it["packed"] else BOX_OFF,
                                     BOX_ON if it["loaded"] else BOX_OFF, it["notes"]))
        total  = len(items)
        packed = sum(i["packed"] for i in items)
        loaded = sum(i["loaded"] for i in items)
        self.progress_lbl.config(
            text=f"{total} items    •    Packed {packed}/{total}    •    Loaded {loaded}/{total}",
            fg=SUCCESS if total and loaded == total else FG_DIM)
        self.progress["value"] = (loaded / total * 100) if total else 0

    # ── Helpers ───────────────────────────────────────────────────────────────
    def save(self):
        try:
            save_data(self.data)
        except OSError as ex:
            messagebox.showerror("Couldn't save", f"Catering data wasn't saved:\n{ex}")

    def _set_field(self, key):
        if self._loading:
            return
        self.cur[key] = self.field_vars[key].get()
        self.save()

    def categories(self):
        return list(dict.fromkeys([c["category"] for c in self.data["catalog"]] +
                                  [i["category"] for i in self.cur["items"]]))

    def selected_index(self):
        sel = self.tree.selection()
        if sel and sel[0].startswith("i"):
            return int(sel[0][1:])
        return None

    def sync_catalog(self, lst):
        """Make sure every item on the checklist also exists in the library."""
        known = {item_key(c) for c in self.data["catalog"]}
        for it in lst["items"]:
            if item_key(it) not in known:
                self.data["catalog"].append({"category": it["category"], "item": it["item"], "qty": it["qty"]})
                known.add(item_key(it))

    def ask_name(self, title, prompt, initial="", renaming=False):
        name = ask_string(self, title, prompt, initial)
        if name and any(l["name"].lower() == name.lower() for l in self.data["lists"]
                        if not (renaming and l is self.cur)):
            messagebox.showwarning("Name taken", f"There's already a checklist called '{name}'.")
            return None
        return name

    # ── Checklist management ──────────────────────────────────────────────────
    def on_list_select(self, event=None):
        sel = self.lists_box.curselection()
        if sel and sel[0] != self.data["current"]:
            self.data["current"] = sel[0]
            self.save()
            self.show_list()

    def _add_list(self, lst):
        self.data["lists"].insert(self.data["current"] + 1, lst)
        self.data["current"] += 1
        self.save()
        self.refresh_lists()
        self.show_list()

    def new_list(self):
        name = self.ask_name("New Checklist", "Name for the new checklist (e.g. Smith Wedding):")
        if name:
            self._add_list(blank_list(name))
            self.pick_items()

    def duplicate_list(self):
        name = self.ask_name("Duplicate Checklist", "Name for the copy:", f"{self.cur['name']} (copy)")
        if not name:
            return
        lst = copy.deepcopy(self.cur)
        lst["name"] = name
        for it in lst["items"]:
            it["packed"] = it["loaded"] = False
        self._add_list(lst)

    def rename_list(self):
        name = self.ask_name("Rename Checklist", "New name:", self.cur["name"], renaming=True)
        if name:
            self.cur["name"] = name
            self.save()
            self.refresh_lists()
            self.show_list()

    def delete_list(self):
        if len(self.data["lists"]) == 1:
            messagebox.showinfo("Delete", "You need at least one checklist. Create another one first.")
            return
        if not messagebox.askyesno("Delete Checklist", f"Permanently delete '{self.cur['name']}'?"):
            return
        del self.data["lists"][self.data["current"]]
        self.data["current"] = max(0, self.data["current"] - 1)
        self.save()
        self.refresh_lists()
        self.show_list()

    # ── Item actions ──────────────────────────────────────────────────────────
    def on_click(self, event):
        row = self.tree.identify_row(event.y)
        col = self.tree.identify_column(event.x)
        if not row.startswith("i") or col not in ("#2", "#3"):
            return
        it = self.cur["items"][int(row[1:])]
        key = "packed" if col == "#2" else "loaded"
        it[key] = not it[key]
        if key == "loaded" and it["loaded"]:
            it["packed"] = True  # loaded implies packed
        self.save()
        self.refresh()
        self.tree.selection_set(row)
        return "break"

    def pick_items(self):
        lst = self.cur
        self.sync_catalog(lst)
        p = ItemPicker(self, self.data["catalog"], {item_key(i) for i in lst["items"]}, self.save)
        # follow any renames made in the library
        for it in lst["items"]:
            new = p.renamed.get(item_key(it))
            if new:
                it["category"], it["item"] = new["category"], new["item"]
        if p.result is not None:
            have = {item_key(i) for i in lst["items"]}
            lst["items"] = [it for it in lst["items"] if item_key(it) in p.result]
            for c in self.data["catalog"]:
                if item_key(c) in p.result and item_key(c) not in have:
                    insert_grouped(lst["items"], make_item(c["category"], c["item"], c["qty"]))
        self.save()
        self.refresh()

    def edit_item(self):
        idx = self.selected_index()
        if idx is None:
            return
        it = self.cur["items"][idx]
        d = ItemDialog(self, self.categories(), it)
        if d.result:
            it.update(d.result)
            self.save()
            self.refresh()
            self.tree.selection_set(f"i{idx}")

    def delete_item(self):
        idx = self.selected_index()
        if idx is None:
            return
        name = self.cur["items"][idx]["item"]
        if messagebox.askyesno("Remove", f"Remove '{name}' from this checklist?"):
            del self.cur["items"][idx]
            self.save()
            self.refresh()

    def reset_checks(self):
        if messagebox.askyesno("Reset Checks", f"Clear all Packed/Loaded checks on '{self.cur['name']}'?"):
            for it in self.cur["items"]:
                it["packed"] = it["loaded"] = False
            self.save()
            self.refresh()

    # ── Output ────────────────────────────────────────────────────────────────
    def export_xlsx(self):
        lst = self.cur
        path = filedialog.asksaveasfilename(defaultextension=".xlsx",
                                            initialfile=f"{safe_filename(lst['name'])}.xlsx",
                                            filetypes=[("Excel", "*.xlsx")])
        if not path:
            return
        try:
            write_xlsx(lst, path)
        except ImportError:
            messagebox.showerror("Missing package", "Run:  pip install openpyxl")
            return
        except PermissionError:
            messagebox.showerror("Can't save", "That file is open in Excel. Close it and try again.")
            return
        messagebox.showinfo("Exported", f"Saved to:\n{path}")

    def print_list(self):
        """Build a formatted print page and open it in the browser's print dialog."""
        path = Path(tempfile.gettempdir()) / f"Checklist - {safe_filename(self.cur['name'])}.html"
        path.write_text(build_print_html(self.cur), encoding="utf-8")
        try:
            webbrowser.open(path.as_uri())
        except Exception as ex:
            messagebox.showerror("Print failed", f"Couldn't open the print preview:\n{ex}")

    # ── Hub hook ──────────────────────────────────────────────────────────────
    def on_show(self):
        pass
