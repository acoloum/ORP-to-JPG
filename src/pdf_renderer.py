"""PDF 渲染器：透過 Microsoft Print to PDF 輸出向量 PDF。"""
from __future__ import annotations
from pathlib import Path
import win32print

PDF_PRINTER_NAME = "Microsoft Print to PDF"


class PdfRenderError(Exception):
    """PDF 渲染失敗。"""


def is_pdf_printer_available() -> bool:
    """檢查 Microsoft Print to PDF 是否已安裝且啟用。"""
    flags = win32print.PRINTER_ENUM_LOCAL | win32print.PRINTER_ENUM_CONNECTIONS
    for _flags, _desc, name, _comment in win32print.EnumPrinters(flags):
        if name == PDF_PRINTER_NAME:
            return True
    return False
