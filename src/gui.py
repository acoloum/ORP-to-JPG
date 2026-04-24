"""tkinter GUI。"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        root.title("QRP 轉 PDF 工具")
        root.geometry("600x500")
        root.resizable(False, False)

        # 主容器
        main = ttk.Frame(root, padding=12)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="QRP 轉 PDF 工具",
                  font=("Microsoft JhengHei", 14, "bold")).pack(anchor="w")
        ttk.Label(main, text="(施工中)").pack(anchor="w", pady=8)


def run() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()
