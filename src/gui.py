"""tkinter GUI。"""
from __future__ import annotations
from typing import Callable
import queue
import threading
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinterdnd2 import TkinterDnD, DND_FILES
from pathlib import Path
from src.converter import (
    OutputMode, ConflictPolicy, ConflictDecision, ConflictAction,
    ProgressEvent, BatchSummary,
    convert_batch,
)


class ConflictDialog(tk.Toplevel):
    """衝突對話框：modal，回傳 ConflictDecision。"""

    def __init__(self, parent: tk.Tk, conflict_path: Path) -> None:
        super().__init__(parent)
        self.title("檔案已存在")
        self.resizable(False, False)
        self.transient(parent)
        self.grab_set()
        self.result: ConflictDecision | None = None

        frm = ttk.Frame(self, padding=12)
        frm.pack()
        ttk.Label(frm, text=f"已有檔案：{conflict_path}",
                  wraplength=400).pack(anchor="w", pady=4)

        self.apply_all = tk.BooleanVar(value=False)
        ttk.Checkbutton(frm, text="套用到後續所有衝突",
                        variable=self.apply_all).pack(anchor="w", pady=4)

        btn_row = ttk.Frame(frm)
        btn_row.pack(pady=6)
        for text, action in [
            ("覆蓋", ConflictAction.OVERWRITE),
            ("跳過", ConflictAction.SKIP),
            ("自動加編號", ConflictAction.RENAME),
            ("取消", ConflictAction.CANCEL),
        ]:
            ttk.Button(
                btn_row, text=text,
                command=lambda a=action: self._choose(a),
            ).pack(side="left", padx=2)

        self.protocol("WM_DELETE_WINDOW", lambda: self._choose(ConflictAction.CANCEL))
        parent.wait_window(self)

    def _choose(self, action: ConflictAction) -> None:
        self.result = ConflictDecision(action=action, apply_to_all=self.apply_all.get())
        self.destroy()


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

        # ---- 開始按鈕 ----
        self.start_btn = ttk.Button(main, text="開始轉檔", command=self._start)
        self.start_btn.pack(pady=10)

        # ---- 進度 ----
        self.progress = ttk.Progressbar(main, mode="determinate", length=560)
        self.progress.pack()
        self.status_label = ttk.Label(main, text="")
        self.status_label.pack(anchor="w", pady=2)

        # ---- Worker 通訊 ----
        self._ui_queue: queue.Queue = queue.Queue()
        self._conflict_response: queue.Queue = queue.Queue()
        self._apply_all_action: ConflictAction | None = None
        self._cancel_event = None
        self._worker_thread = None
        self.root.after(100, self._poll_queue)

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

    def _start(self) -> None:
        """驗證輸入、建立 worker 執行緒並啟動批次轉檔。"""
        self._apply_all_action = None
        if not self.files:
            messagebox.showwarning("無檔案", "請先選取要轉換的 QRP 檔")
            return
        mode = OutputMode(self.output_mode.get())
        custom = None
        if mode == OutputMode.CUSTOM:
            txt = self.custom_dir_var.get().strip()
            if not txt:
                messagebox.showwarning("未指定", "請選擇輸出資料夾")
                return
            custom = Path(txt)
        policy = ConflictPolicy(self.conflict_policy.get())

        self.start_btn.config(state="disabled", text="轉檔中...")
        self.progress.config(maximum=len(self.files), value=0)
        self._cancel_event = threading.Event()
        self._worker_thread = threading.Thread(
            target=self._run_batch,
            args=(list(self.files), mode, custom, policy, self._cancel_event),
            daemon=True,
        )
        self._worker_thread.start()

    def _run_batch(self, files, mode, custom, policy, cancel_event) -> None:
        """Worker 執行緒：呼叫 convert_batch 並透過 queue 回傳進度。"""
        def progress(event: ProgressEvent) -> None:
            self._ui_queue.put(("progress", event))

        def conflict_cb(path: Path) -> ConflictDecision:
            # 若已選擇 apply_to_all，直接回傳不再跳對話框
            if self._apply_all_action is not None:
                return ConflictDecision(action=self._apply_all_action,
                                        apply_to_all=True)
            self._ui_queue.put(("conflict", path))
            decision: ConflictDecision = self._conflict_response.get()
            if decision.apply_to_all:
                self._apply_all_action = decision.action
            return decision

        try:
            summary = convert_batch(
                sources=files, output_mode=mode,
                custom_output_dir=custom,
                conflict_policy=policy,
                conflict_callback=conflict_cb,
                progress_callback=progress,
                cancel_event=cancel_event,
            )
            self._ui_queue.put(("done", summary))
        except Exception as e:
            self._ui_queue.put(("error", str(e)))

    def _poll_queue(self) -> None:
        """每 100ms 輪詢 UI 訊息佇列，處理 worker 發來的事件。"""
        try:
            while True:
                kind, payload = self._ui_queue.get_nowait()
                if kind == "progress":
                    self._handle_progress(payload)
                elif kind == "done":
                    self._handle_done(payload)
                elif kind == "error":
                    messagebox.showerror("錯誤", payload)
                    self._reset_ui()
                elif kind == "conflict":
                    dlg = ConflictDialog(self.root, payload)
                    decision = dlg.result or ConflictDecision(
                        action=ConflictAction.CANCEL,
                    )
                    self._conflict_response.put(decision)
        except queue.Empty:
            pass
        try:
            self.root.after(100, self._poll_queue)
        except tk.TclError:
            pass  # 視窗已銷毀，停止輪詢

    def _handle_progress(self, event: ProgressEvent) -> None:
        """更新進度列與狀態標籤。"""
        if event.kind == "file_start":
            self.status_label.config(text=f"正在轉換 {event.source.name}...")
        elif event.kind == "file_done":
            self.progress.config(value=event.index + 1)

    def _handle_done(self, summary: BatchSummary) -> None:
        """轉檔完成後重置 UI 並顯示簡易摘要（Task 16 會替換為完整對話框）。"""
        self._reset_ui()
        # Task 16 會替換為完整摘要對話框
        messagebox.showinfo(
            "完成",
            f"成功：{summary.success_count}\n"
            f"跳過：{summary.skipped_count}\n"
            f"失敗：{summary.failed_count}",
        )

    def _reset_ui(self) -> None:
        """重置 UI 到可操作狀態。"""
        self.start_btn.config(state="normal", text="開始轉檔")
        self.status_label.config(text="")


def run() -> None:
    root = TkinterDnD.Tk()
    App(root)
    root.mainloop()
