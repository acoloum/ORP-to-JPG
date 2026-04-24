"""tkinter GUI。"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from pathlib import Path


class App:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.files: list[Path] = []

        root.title("QRP 轉 PDF 工具")
        root.geometry("600x500")
        root.resizable(False, False)

        main = ttk.Frame(root, padding=12)
        main.pack(fill="both", expand=True)

        ttk.Label(main, text="來源檔案",
                  font=("Microsoft JhengHei", 10, "bold")).pack(anchor="w")

        btn_row = ttk.Frame(main)
        btn_row.pack(anchor="w", pady=4)
        ttk.Button(btn_row, text="選檔", command=self._pick_files).pack(side="left")
        ttk.Button(btn_row, text="選資料夾",
                   command=self._pick_folder).pack(side="left", padx=4)
        ttk.Button(btn_row, text="清空",
                   command=self._clear_files).pack(side="left", padx=4)
        ttk.Button(btn_row, text="移除選取",
                   command=self._remove_selected).pack(side="left")

        list_frame = ttk.Frame(main)
        list_frame.pack(fill="both", expand=True, pady=4)
        self.listbox = tk.Listbox(list_frame, selectmode="extended", height=8)
        self.listbox.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(list_frame, command=self.listbox.yview)
        scroll.pack(side="right", fill="y")
        self.listbox.config(yscrollcommand=scroll.set)

        self.count_label = ttk.Label(main, text="已選取：0 個檔案")
        self.count_label.pack(anchor="w")

    def _pick_files(self) -> None:
        """開啟檔案對話框，讓使用者選取 QRP 檔案。"""
        paths = filedialog.askopenfilenames(
            title="選擇 QRP 檔案",
            filetypes=[("QRP 檔", "*.QRP *.qrp"), ("所有檔案", "*.*")],
        )
        self._add_files([Path(p) for p in paths])

    def _pick_folder(self) -> None:
        """開啟資料夾對話框，掃描該資料夾內的 QRP 檔案。"""
        folder = filedialog.askdirectory(title="選擇包含 QRP 檔的資料夾")
        if not folder:
            return
        found = sorted(Path(folder).glob("*.QRP")) + sorted(Path(folder).glob("*.qrp"))
        if not found:
            messagebox.showinfo("找不到 QRP 檔", "該資料夾內沒有 .QRP 檔")
            return
        self._add_files(found)

    def _add_files(self, paths: list[Path]) -> None:
        """將新檔案加入清單（防止重複）。"""
        existing = set(self.files)
        for p in paths:
            if p not in existing:
                self.files.append(p)
        self._refresh_list()

    def _clear_files(self) -> None:
        """清空所有已選取的檔案。"""
        self.files.clear()
        self._refresh_list()

    def _remove_selected(self) -> None:
        """移除 Listbox 中被選取的項目（逆序刪除避免索引位移）。"""
        selected = sorted(self.listbox.curselection(), reverse=True)
        for i in selected:
            del self.files[i]
        self._refresh_list()

    def _refresh_list(self) -> None:
        """同步更新 Listbox 顯示內容與檔案計數標籤。"""
        self.listbox.delete(0, "end")
        for f in self.files:
            self.listbox.insert("end", f.name)
        self.count_label.config(text=f"已選取：{len(self.files)} 個檔案")


def run() -> None:
    root = tk.Tk()
    App(root)
    root.mainloop()
