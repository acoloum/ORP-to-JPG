"""PDF 渲染器：透過 Microsoft Print to PDF 輸出向量 PDF。"""
from __future__ import annotations
from pathlib import Path
import struct
from ctypes import windll, byref
from ctypes.wintypes import RECT
import win32print
import win32ui
import win32gui

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


def _hemf_from_bytes(emf_bytes: bytes) -> int:
    """用 SetEnhMetaFileBits 從記憶體建立 HEMF。"""
    hemf = windll.gdi32.SetEnhMetaFileBits(len(emf_bytes), emf_bytes)
    if not hemf:
        raise PdfRenderError("無法載入 EMF 頁面（SetEnhMetaFileBits 失敗）")
    return hemf


def _emf_frame_rect(emf_bytes: bytes) -> tuple[int, int, int, int]:
    """從 EMF header 讀 rclFrame（單位 0.01 mm），回傳 (left, top, right, bottom)。"""
    return struct.unpack_from("<iiii", emf_bytes, 24)


def render_pdf(pages: list[bytes], output_path: str | Path,
               doc_name: str = "Report") -> None:
    """把 EMF 頁面清單寫成向量 PDF。

    使用 Microsoft Print to PDF，透過 StartDoc 指定輸出路徑以避開「另存新檔」對話框。
    """
    if not pages:
        raise PdfRenderError("沒有頁面可渲染")
    if not is_pdf_printer_available():
        raise PdfRenderError(f"找不到印表機：{PDF_PRINTER_NAME}")

    output_str = str(Path(output_path))
    hdc_raw = win32gui.CreateDC("WINSPOOL", PDF_PRINTER_NAME, None)
    dc = win32ui.CreateDCFromHandle(hdc_raw)
    try:
        # DOCINFO：第一欄 = 文件名稱，第二欄 = 輸出檔路徑（此為 pywin32 慣例）
        dc.StartDoc(doc_name, output_str)
        try:
            for emf in pages:
                dc.StartPage()
                hemf = _hemf_from_bytes(emf)
                try:
                    # 取印表機可列印區（裝置單位）
                    hdc_handle = dc.GetSafeHdc()
                    HORZRES, VERTRES = 8, 10
                    width = windll.gdi32.GetDeviceCaps(hdc_handle, HORZRES)
                    height = windll.gdi32.GetDeviceCaps(hdc_handle, VERTRES)
                    rect = RECT(0, 0, width, height)
                    ok = windll.gdi32.PlayEnhMetaFile(hdc_handle, hemf, byref(rect))
                    if not ok:
                        raise PdfRenderError("PlayEnhMetaFile 失敗")
                finally:
                    windll.gdi32.DeleteEnhMetaFile(hemf)
                dc.EndPage()
            dc.EndDoc()
        except Exception:
            try:
                dc.AbortDoc()
            except Exception:
                pass
            raise
    finally:
        dc.DeleteDC()
