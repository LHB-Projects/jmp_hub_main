"""
catering/dialogs.py — Dark-themed dialogs for the Catering Checklists page.

  ItemDialog  — add / edit one item (checklist item or library item)
  ItemPicker  — tick any number of items from the library onto a checklist
"""
import tkinter as tk
from tkinter import ttk, messagebox

from config import (BG, ENTRY, ACCENT, ACCENT2, BORDER,
                    FG, FG_DIM, FG_MUTE,
                    FONT_H2, FONT_BODY, FONT_BODY_B, FONT_SMALL, FONT_BTN)
from catering.store import ITEM_FIELDS, LIBRARY_FIELDS, item_key

BOX_OFF, BOX_ON, BOX_SOME = "☐", "☑", "▣"

_BTN_KINDS = {
    "primary":   (ACCENT,    ACCENT2,   "white"),
    "secondary": (ENTRY,     BORDER,    FG),
    "success":   ("#1e4d1e", "#2a6a2a", "white"),
    "danger":    ("#4a1d1d", "#6b2626", "#fca5a5"),
}


def button(parent, text, command, kind="secondary", **kw):
    """Flat hub-style button."""
    bg, active, fg = _BTN_KINDS[kind]
    opts = dict(bg=bg, fg=fg, activebackground=active, activeforeground=fg,
                font=FONT_BTN, relief="flat", bd=0, highlightthickness=0, padx=12, pady=7,
                cursor="hand2", command=command)
    opts.update(kw)
    return tk.Button(parent, text=text, **opts)


def entry(parent, var, width=30):
    return tk.Entry(parent, textvariable=var, width=width, bg=ENTRY, fg=FG,
                    insertbackground=FG, relief="flat", font=FONT_BODY,
                    highlightthickness=1, highlightbackground=BORDER,
                    highlightcolor=ACCENT)


def _dialog_base(win, parent, title):
    win.title(title)
    win.configure(bg=BG)
    win.transient(parent.winfo_toplevel())


class _TextDialog(tk.Toplevel):
    def __init__(self, parent, title, prompt, initial=""):
        super().__init__(parent)
        _dialog_base(self, parent, title)
        self.resizable(False, False)
        self.result = None
        frm = tk.Frame(self, bg=BG, padx=18, pady=16)
        frm.pack(fill="both", expand=True)
        tk.Label(frm, text=title, font=FONT_H2, bg=BG, fg=FG).pack(anchor="w")
        tk.Label(frm, text=prompt, font=FONT_SMALL, bg=BG, fg=FG_DIM).pack(anchor="w", pady=(4, 8))
        self.var = tk.StringVar(value=initial)
        ent = entry(frm, self.var, width=44)
        ent.pack(fill="x", ipady=3)
        ent.select_range(0, "end")
        btns = tk.Frame(frm, bg=BG)
        btns.pack(fill="x", pady=(14, 0))
        button(btns, "Cancel", self.destroy).pack(side="right")
        button(btns, "OK", self.ok, kind="primary").pack(side="right", padx=8)
        self.bind("<Return>", lambda e: self.ok())
        self.bind("<Escape>", lambda e: self.destroy())
        ent.focus_set()
        self.grab_set()
        self.wait_window()

    def ok(self):
        self.result = self.var.get().strip() or None
        self.destroy()


def ask_string(parent, title, prompt, initial=""):
    """Dark replacement for simpledialog.askstring. Returns stripped text or None."""
    return _TextDialog(parent, title, prompt, initial).result


class ItemDialog(tk.Toplevel):
    """Add / edit dialog for one item. Sets self.result to a dict on OK."""

    def __init__(self, parent, categories, item=None, fields=ITEM_FIELDS, title=None):
        super().__init__(parent)
        _dialog_base(self, parent, title or ("Edit Item" if item else "Add Item"))
        self.resizable(False, False)
        self.result = None
        item = item or {"category": categories[0] if categories else ""}

        frm = tk.Frame(self, bg=BG, padx=18, pady=16)
        frm.pack(fill="both", expand=True)
        tk.Label(frm, text=self.title(), font=FONT_H2, bg=BG, fg=FG
                 ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))

        self.vars = {}
        focus = None
        for r, (key, label) in enumerate(fields, start=1):
            tk.Label(frm, text=label, font=FONT_SMALL, bg=BG, fg=FG_DIM
                     ).grid(row=r, column=0, sticky="w", pady=4, padx=(0, 12))
            var = tk.StringVar(value=item.get(key, ""))
            if key == "category":
                w = ttk.Combobox(frm, textvariable=var, values=categories, width=36,
                                 style="Cat.TCombobox", font=FONT_BODY)
            else:
                w = entry(frm, var, width=40)
            w.grid(row=r, column=1, pady=4, ipady=3, sticky="ew")
            self.vars[key] = var
            if key == "item":
                focus = w

        btns = tk.Frame(frm, bg=BG)
        btns.grid(row=len(fields) + 1, column=0, columnspan=2, pady=(14, 0), sticky="e")
        button(btns, "Cancel", self.destroy).pack(side="right")
        button(btns, "Save", self.ok, kind="primary").pack(side="right", padx=8)
        self.bind("<Return>", lambda e: self.ok())
        self.bind("<Escape>", lambda e: self.destroy())
        if focus is not None:
            focus.focus_set()
        self.grab_set()
        self.wait_window()

    def ok(self):
        vals = {k: v.get().strip() for k, v in self.vars.items()}
        if not vals["item"] or not vals["category"]:
            messagebox.showwarning("Missing info", "Category and Item are required.", parent=self)
            return
        self.result = vals
        self.destroy()


class ItemPicker(tk.Toplevel):
    """Check off any number of items from the library.

    self.result is the set of chosen item keys on Apply (None on Cancel).
    Library edits are saved immediately via on_change; self.renamed maps
    old item keys to their edited library entry so checklists can follow along.
    """

    def __init__(self, parent, catalog, chosen_keys, on_change):
        super().__init__(parent)
        _dialog_base(self, parent, "Add / Remove Items")
        self.geometry("640x680")
        self.minsize(500, 440)
        self.catalog   = catalog
        self.on_change = on_change
        self.checked   = set(chosen_keys)
        self.renamed   = {}
        self.result    = None
        self.rows      = {}

        frm = tk.Frame(self, bg=BG, padx=16, pady=14)
        frm.pack(fill="both", expand=True)

        tk.Label(frm, text="Item Library", font=FONT_H2, bg=BG, fg=FG).pack(anchor="w")
        tk.Label(frm, text="Click items or whole categories to put them on this checklist.",
                 font=FONT_SMALL, bg=BG, fg=FG_DIM).pack(anchor="w", pady=(2, 10))

        top = tk.Frame(frm, bg=BG)
        top.pack(fill="x")
        tk.Label(top, text="Search", font=FONT_SMALL, bg=BG, fg=FG_DIM).pack(side="left")
        self.filter_var = tk.StringVar()
        ent = entry(top, self.filter_var)
        ent.pack(side="left", fill="x", expand=True, padx=8, ipady=3)
        self.filter_var.trace_add("write", lambda *a: self.refresh())
        self.count_lbl = tk.Label(top, font=FONT_BODY_B, bg=BG, fg=ACCENT, width=12, anchor="e")
        self.count_lbl.pack(side="right")

        wrap = tk.Frame(frm, bg=BG)
        wrap.pack(fill="both", expand=True, pady=10)
        self.tree = ttk.Treeview(wrap, columns=("qty",), show="tree headings",
                                 selectmode="browse", style="Cat.Treeview")
        self.tree.heading("#0", text="Item")
        self.tree.heading("qty", text="Default Qty")
        self.tree.column("#0", width=400)
        self.tree.column("qty", width=120, anchor="center")
        self.tree.tag_configure("cat", font=FONT_BODY_B, background=ENTRY, foreground=FG)
        sb = ttk.Scrollbar(wrap, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<Button-1>", self.on_click)
        self.tree.bind("<space>", lambda e: self.toggle_selected())

        lib = tk.Frame(frm, bg=BG)
        lib.pack(fill="x")
        button(lib, "Select All", lambda: self.set_visible(True)).pack(side="left")
        button(lib, "Clear All", lambda: self.set_visible(False)).pack(side="left", padx=6)
        button(lib, "Delete", self.delete_lib_item, kind="danger").pack(side="right")
        button(lib, "Edit", self.edit_lib_item).pack(side="right", padx=6)
        button(lib, "+ New Library Item", self.new_lib_item).pack(side="right")

        tk.Frame(frm, bg=BORDER, height=1).pack(fill="x", pady=12)
        bottom = tk.Frame(frm, bg=BG)
        bottom.pack(fill="x")
        tk.Label(bottom, text="Edits to the library save immediately.",
                 font=FONT_SMALL, bg=BG, fg=FG_MUTE).pack(side="left")
        button(bottom, "Cancel", self.destroy).pack(side="right")
        button(bottom, "Apply", self.apply, kind="primary").pack(side="right", padx=8)
        self.bind("<Return>", lambda e: self.apply())
        self.bind("<Escape>", lambda e: self.destroy())

        self.refresh()
        ent.focus_set()
        self.grab_set()
        self.wait_window()

    def categories(self):
        return list(dict.fromkeys(c["category"] for c in self.catalog))

    def refresh(self):
        sel = self.tree.selection()
        open_state = {self.tree.item(i, "text")[3:]: self.tree.item(i, "open")
                      for i in self.tree.get_children()}
        self.tree.delete(*self.tree.get_children())
        self.rows = {}
        q = self.filter_var.get().strip().lower()
        groups = {}
        for idx, c in enumerate(self.catalog):
            if q and q not in c["item"].lower():
                continue
            groups.setdefault(c["category"], []).append(idx)
        for g, (cat, idxs) in enumerate(groups.items()):
            n_on = sum(item_key(self.catalog[i]) in self.checked for i in idxs)
            box = BOX_ON if n_on == len(idxs) else BOX_SOME if n_on else BOX_OFF
            gid = self.tree.insert("", "end", iid=f"g{g}", text=f"{box}  {cat}", tags=("cat",),
                                   values=(f"{n_on}/{len(idxs)}",),
                                   open=True if q else open_state.get(cat, True))
            self.rows[gid] = idxs
            for i in idxs:
                c = self.catalog[i]
                box = BOX_ON if item_key(c) in self.checked else BOX_OFF
                self.tree.insert(gid, "end", iid=f"c{i}", text=f"{box}  {c['item']}", values=(c["qty"],))
                self.rows[f"c{i}"] = [i]
        if sel and self.tree.exists(sel[0]):
            self.tree.selection_set(sel[0])
            self.tree.see(sel[0])
        self.count_lbl.config(text=f"{len(self.checked)} selected")

    def toggle(self, row):
        keys = [item_key(self.catalog[i]) for i in self.rows[row]]
        if all(k in self.checked for k in keys):
            self.checked.difference_update(keys)
        else:
            self.checked.update(keys)
        self.refresh()

    def on_click(self, event):
        if "indicator" in self.tree.identify_element(event.x, event.y):
            return  # let the expand/collapse arrow work normally
        row = self.tree.identify_row(event.y)
        if row:
            self.tree.selection_set(row)
            self.toggle(row)
            return "break"

    def toggle_selected(self):
        sel = self.tree.selection()
        if sel:
            self.toggle(sel[0])
        return "break"

    def set_visible(self, on):
        keys = {item_key(self.catalog[int(r[1:])]) for r in self.rows if r.startswith("c")}
        if on:
            self.checked |= keys
        else:
            self.checked -= keys
        self.refresh()

    def selected_lib_index(self):
        sel = self.tree.selection()
        if sel and sel[0].startswith("c"):
            return int(sel[0][1:])
        messagebox.showinfo("Select an item", "Click an item in the list first.", parent=self)
        return None

    def _is_duplicate(self, vals, skip=None):
        return any(item_key(c) == item_key(vals) for n, c in enumerate(self.catalog) if n != skip)

    def new_lib_item(self):
        d = ItemDialog(self, self.categories(), fields=LIBRARY_FIELDS, title="New Library Item")
        self.grab_set()
        if not d.result:
            return
        if self._is_duplicate(d.result):
            messagebox.showwarning("Already exists", "That item is already in the library.", parent=self)
            return
        new = {"category": d.result["category"], "item": d.result["item"], "qty": d.result["qty"]}
        idx = max((n for n, c in enumerate(self.catalog) if c["category"] == new["category"]),
                  default=len(self.catalog) - 1)
        self.catalog.insert(idx + 1, new)
        self.checked.add(item_key(new))
        self.on_change()
        self.filter_var.set("")
        self.refresh()

    def edit_lib_item(self):
        idx = self.selected_lib_index()
        if idx is None:
            return
        c = self.catalog[idx]
        d = ItemDialog(self, self.categories(), c, fields=LIBRARY_FIELDS, title="Edit Library Item")
        self.grab_set()
        if not d.result:
            return
        if self._is_duplicate(d.result, skip=idx):
            messagebox.showwarning("Already exists", "That item is already in the library.", parent=self)
            return
        old = item_key(c)
        c.update(d.result)
        if item_key(c) != old:
            self.renamed[old] = c
            if old in self.checked:
                self.checked.discard(old)
                self.checked.add(item_key(c))
        self.on_change()
        self.refresh()

    def delete_lib_item(self):
        idx = self.selected_lib_index()
        if idx is None:
            return
        c = self.catalog[idx]
        if not messagebox.askyesno("Delete from Library",
                                   f"Remove '{c['item']}' from the item library?\n\n"
                                   "It will also come off this checklist when you Apply.", parent=self):
            return
        del self.catalog[idx]
        self.checked.discard(item_key(c))
        self.on_change()
        self.refresh()

    def apply(self):
        self.result = set(self.checked)
        self.destroy()
