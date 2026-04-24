"""tkinter GUI。"""
from __future__ import annotations
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
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

        # 輸出位置
        ttk.Label(main, text="輸出位置",
                  font=("Microsoft JhengHei", 10, "bold")).pack(anchor="w", pady=(10, 2))

        self.output_mode = tk.StringVar(value="same")
        ttk.Radiobutton(main, text="與原檔同資料夾", value="same",
                        variable=self.output_mode,
                        command=self._update_output_ui).pack(anchor="w")
        ttk.Radiobutton(main, text="原資料夾下建立 PDF 子資料夾", value="subfolder",
                        variable=self.output_mode,
                        command=self._update_output_ui).pack(anchor="w")

        custom_row = ttk.Frame(main)
        custom_row.pack(anchor="w", fill="x")
        ttk.Radiobutton(custom_row, text="指定資料夾：", value="custom",
                        variable=self.output_mode,
                        command=self._update_output_ui).pack(side="left")
        self.custom_dir_var = tk.StringVar()
        self.custom_dir_entry = ttk.Entry(
            custom_row, textvariable=self.custom_dir_var, state="disabled", width=40,
        )
        self.custom_dir_entry.pack(side="left", padx=4)
        self.browse_btn = ttk.Button(
            custom_row, text="瀏覽...", command=self._browse_output_dir, state="disabled",
        )
        self.browse_btn.pack(side="left")

        # 衝突策略
        ttk.Label(main, text="檔案已存在時",
                  font=("Microsoft JhengHei", 10, "bold")).pack(anchor="w", pady=(10, 2))
        self.conflict_policy = tk.StringVar(value="ask")
        policy_row = ttk.Frame(main)
        policy_row.pack(anchor="w")
        for text, val in [("問我", "ask"), ("覆蓋", "overwrite"),
                          ("跳過", "skip"), ("加編號", "rename")]:
            ttk.Radiobutton(policy_row, text=text, value=val,
                            variable=self.conflict_policy).pack(side="left", padx=2)

        # 拖放支援
        self.listbox.drop_target_register(DND_FILES)
        self.listbox.dnd_bind("<<Drop>>", self._on_drop)

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

    def _on_drop(self, event) -> None:
        # event.data 可能是 "{path1} {path2}" 或空白分隔
        raw = event.data
        # tkinterdnd2 會把含空白的路徑用 {} 括起來
        paths: list[Path] = []
        token = ""
        in_brace = False
        for ch in raw:
            if ch == "{":
                in_brace = True
                token = ""
            elif ch == "}":
                in_brace = False
                if token:
                    paths.append(Path(token))
                    token = ""
            elif ch == " " and not in_brace:
                if token:
                    paths.append(Path(token))
                    token = ""
            else:
                token += ch
        if token:
            paths.append(Path(token))
        qrp = [p for p in paths if p.suffix.lower() == ".qrp" and p.is_file()]
        if not qrp:
            messagebox.showinfo("忽略", "未偵測到 .QRP 檔")
            return
        self._add_files(qrp)

    def _update_output_ui(self) -> None:
        """根據輸出模式選擇，啟用或停用指定資料夾的輸入框與瀏覽按鈕。"""
        is_custom = self.output_mode.get() == "custom"
        state = "normal" if is_custom else "disabled"
        self.custom_dir_entry.config(state=state)
        self.browse_btn.config(state=state)

    def _browse_output_dir(self) -> None:
        """開啟資料夾選取對話框，將結果填入指定資料夾欄位。"""
        folder = filedialog.askdirectory(title="選擇輸出資料夾")
        if folder:
            self.custom_dir_var.set(folder)

    def _refresh_list(self) -> None:
        """同步更新 Listbox 顯示內容與檔案計數標籤。"""
        self.listbox.delete(0, "end")
        for f in self.files:
            self.listbox.insert("end", f.name)
        self.count_label.config(text=f"已選取：{len(self.files)} 個檔案")


def run() -> None:
    root = TkinterDnD.Tk()
    App(root)
    root.mainloop()
