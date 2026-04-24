"""進入點：啟動時檢查 PDF 印表機，無則提示退出。"""
import tkinter as tk
from tkinter import messagebox
from src.gui import run
from src.pdf_renderer import is_pdf_printer_available, PDF_PRINTER_NAME


def main() -> None:
    if not is_pdf_printer_available():
        # 先以隱藏 root 顯示錯誤
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror(
            "缺少必要印表機",
            f"找不到「{PDF_PRINTER_NAME}」。\n\n"
            "請至「控制台 > 程式和功能 > 開啟或關閉 Windows 功能」"
            f"啟用「{PDF_PRINTER_NAME}」後再執行本程式。",
        )
        root.destroy()
        return
    run()


if __name__ == "__main__":
    main()
