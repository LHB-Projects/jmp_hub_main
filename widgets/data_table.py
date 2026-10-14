"""
widgets/data_table.py — Reusable scrollable Treeview table.

Usage:
    frame, tree = make_table(
        parent,
        style_name="T.Treeview",
        columns=[
            ("item", "Menu Item", 340, "w"),
            ("qty",  "Qty Sold",   90, "center"),
            ("net",  "Net Sales", 120, "e"),
        ]
    )
    frame.pack(fill="both", expand=True)
    tree.insert("", "end", values=("Ribeye", 12, "$480.00"))
"""
import tkinter as tk
from tkinter import ttk
from config import BG


def make_table(parent, style_name: str, columns: list) -> tuple:
    """
    Args:
        parent:      Parent widget.
        style_name:  ttk style name (e.g. "T.Treeview").
        columns:     List of (column_id, heading_text, width, anchor).

    Returns:
        (frame, tree) — pack/grid the frame; insert rows into tree.
    """
    frame = tk.Frame(parent, bg=BG)
    ids   = [c[0] for c in columns]

    tree = ttk.Treeview(frame, columns=ids, show="headings",
                         height=16, style=style_name)
    for cid, heading, width, anchor in columns:
        tree.heading(cid, text=heading)
        tree.column(cid, width=width, anchor=anchor)

    sb = ttk.Scrollbar(frame, orient="vertical", command=tree.yview)
    tree.configure(yscrollcommand=sb.set)
    tree.pack(side="left", fill="both", expand=True)
    sb.pack(side="right", fill="y")

    return frame, tree
