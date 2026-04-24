"""JPG 渲染器：將 EMF 頁面透過 GDI HALFTONE 渲染至記憶體點陣圖，再以 Pillow 輸出高品質 JPG。"""
from __future__ import annotations
import ctypes
import struct
from ctypes import windll, byref, c_void_p, Structure, sizeof, c_int, c_bool
from ctypes.wintypes import DWORD, LONG, WORD, RECT, POINT, BOOL
from pathlib import Path

from PIL import Image

# ── GDI 常數 ──────────────────────────────────────────────────────────────────
WHITE_BRUSH = 0       # GetStockObject(0) 回傳白色筆刷
BI_RGB = 0            # 不壓縮的 DIB
HALFTONE = 4          # SetStretchBltMode HALFTONE 模式
DIB_RGB_COLORS = 0    # CreateDIBSection 顏色表用 RGB 值

DEFAULT_DPI = 200

# A4 標準尺寸（mm）
A4_WIDTH_MM  = 210.0
A4_HEIGHT_MM = 297.0

# ── 修正 64 位元 GDI 函式簽章（避免 handle 截斷問題） ──────────────────────────
# 在 64 位元 Windows 上，HANDLE 為 8 bytes，ctypes 預設 restype = c_int（4 bytes）
# 會導致 handle 值截斷，造成後續 GDI 呼叫失敗。
import ctypes as _ct
_gdi32 = windll.gdi32
_user32 = windll.user32

# 回傳 HANDLE 的函式：一律設 restype = c_void_p
_gdi32.CreateCompatibleDC.restype       = c_void_p
_gdi32.CreateDIBSection.restype         = c_void_p
_gdi32.SelectObject.restype             = c_void_p
_gdi32.GetStockObject.restype           = c_void_p
_gdi32.SetEnhMetaFileBits.restype       = c_void_p
_gdi32.SetEnhMetaFileBits.argtypes      = [_ct.c_uint, _ct.c_char_p]
_user32.GetDC.restype                   = c_void_p
_user32.GetDC.argtypes                  = [_ct.c_void_p]

# 回傳 BOOL 的函式
_gdi32.PlayEnhMetaFile.restype          = BOOL
_gdi32.DeleteEnhMetaFile.restype        = BOOL
_gdi32.DeleteObject.restype             = BOOL
_gdi32.DeleteDC.restype                 = BOOL
_gdi32.SetStretchBltMode.restype        = c_int
_gdi32.SetBrushOrgEx.restype            = BOOL
_user32.FillRect.restype                = c_int
_user32.ReleaseDC.restype               = c_int

# 設定接受 HANDLE 參數的函式 argtypes，避免 64 位元溢位
# CreateCompatibleDC(HDC hdc)
_gdi32.CreateCompatibleDC.argtypes      = [c_void_p]
# CreateDIBSection(HDC hdc, BITMAPINFO*, UINT, VOID**, HANDLE, DWORD)
_gdi32.CreateDIBSection.argtypes        = [c_void_p, _ct.c_void_p, _ct.c_uint,
                                            _ct.POINTER(c_void_p), c_void_p, _ct.c_ulong]
# PlayEnhMetaFile(HDC hdc, HENHMETAFILE hemf, const RECT *lprect)
_gdi32.PlayEnhMetaFile.argtypes         = [c_void_p, c_void_p, _ct.POINTER(RECT)]
# DeleteEnhMetaFile(HENHMETAFILE hemf)
_gdi32.DeleteEnhMetaFile.argtypes       = [c_void_p]
# SelectObject(HDC hdc, HGDIOBJ h)
_gdi32.SelectObject.argtypes            = [c_void_p, c_void_p]
# DeleteObject(HGDIOBJ ho)
_gdi32.DeleteObject.argtypes            = [c_void_p]
# DeleteDC(HDC hdc)
_gdi32.DeleteDC.argtypes               = [c_void_p]
# SetStretchBltMode(HDC hdc, int mode)
_gdi32.SetStretchBltMode.argtypes       = [c_void_p, _ct.c_int]
# SetBrushOrgEx(HDC hdc, int x, int y, POINT *lppt)
_gdi32.SetBrushOrgEx.argtypes          = [c_void_p, _ct.c_int, _ct.c_int, _ct.POINTER(POINT)]
# FillRect(HDC hdc, const RECT *lprc, HBRUSH hbr)
_user32.FillRect.argtypes              = [c_void_p, _ct.POINTER(RECT), c_void_p]
# ReleaseDC(HWND hWnd, HDC hDC)
_user32.ReleaseDC.argtypes             = [c_void_p, c_void_p]


# ── BITMAPINFO 結構 ────────────────────────────────────────────────────────────
class _BITMAPINFOHEADER(Structure):
    """Windows BITMAPINFOHEADER 結構。"""
    _fields_ = [
        ("biSize",          DWORD),
        ("biWidth",         LONG),
        ("biHeight",        LONG),
        ("biPlanes",        WORD),
        ("biBitCount",      WORD),
        ("biCompression",   DWORD),
        ("biSizeImage",     DWORD),
        ("biXPelsPerMeter", LONG),
        ("biYPelsPerMeter", LONG),
        ("biClrUsed",       DWORD),
        ("biClrImportant",  DWORD),
    ]


class _BITMAPINFO(Structure):
    """Windows BITMAPINFO 結構（含 3 個 RGBQUAD 佔位欄，供 24bpp 使用）。"""
    _fields_ = [
        ("bmiHeader", _BITMAPINFOHEADER),
        ("bmiColors", DWORD * 3),
    ]


# ── 例外類別 ───────────────────────────────────────────────────────────────────
class JpgRenderError(Exception):
    """JPG 渲染失敗。"""


# ── 內部工具函式 ───────────────────────────────────────────────────────────────
def _emf_frame_rect(emf_bytes: bytes) -> tuple[int, int, int, int]:
    """從 EMF header 讀 rclFrame（單位 0.01 mm），回傳 (left, top, right, bottom)。"""
    return struct.unpack_from("<iiii", emf_bytes, 24)


def _render_page(emf: bytes, dpi: int) -> Image.Image:
    """將單一 EMF 頁面渲染為 PIL Image（RGB）。"""
    # 固定以 A4 尺寸輸出（rclFrame 常含非標準值，直接指定 A4 確保比例正確）
    width_px  = max(1, round(A4_WIDTH_MM  * dpi / 25.4))
    height_px = max(1, round(A4_HEIGHT_MM * dpi / 25.4))

    # 3. 建立記憶體 DC（與螢幕 DC 相容）
    screen_dc = _user32.GetDC(0)
    if not screen_dc:
        raise JpgRenderError("GetDC(0) 失敗，無法取得螢幕 DC")
    try:
        mem_dc = _gdi32.CreateCompatibleDC(screen_dc)
        if not mem_dc:
            raise JpgRenderError("CreateCompatibleDC 失敗")
    finally:
        _user32.ReleaseDC(0, screen_dc)

    try:
        # 4. 建立 24bpp 上到下排列的 DIBSection
        bmi = _BITMAPINFO()
        bmi.bmiHeader.biSize        = sizeof(_BITMAPINFOHEADER)  # 注意：不是 sizeof(_BITMAPINFO)
        bmi.bmiHeader.biWidth       = width_px
        bmi.bmiHeader.biHeight      = -height_px   # 負值 = 上到下排列（top-down）
        bmi.bmiHeader.biPlanes      = 1
        bmi.bmiHeader.biBitCount    = 24
        bmi.bmiHeader.biCompression = BI_RGB

        bits_ptr = c_void_p()
        hbmp = _gdi32.CreateDIBSection(
            mem_dc, byref(bmi), DIB_RGB_COLORS,
            byref(bits_ptr), None, 0,
        )
        if not hbmp:
            raise JpgRenderError("CreateDIBSection 失敗")

        old_bmp = None
        try:
            # 5. 將 DIB 選入記憶體 DC
            old_bmp = _gdi32.SelectObject(mem_dc, hbmp)
            # 注意：SelectObject 回傳先前物件，新建 DC 初始含預設點陣圖，回傳應為非 None
            if not old_bmp:
                raise JpgRenderError("SelectObject 失敗")

            # 6. 填白色背景
            rect = RECT(0, 0, width_px, height_px)
            white_brush = _gdi32.GetStockObject(WHITE_BRUSH)
            _user32.FillRect(mem_dc, byref(rect), white_brush)

            # 7. 設定 HALFTONE 插值模式（PlayEnhMetaFile 縮放時使用）
            _gdi32.SetStretchBltMode(mem_dc, HALFTONE)
            pt = POINT()
            _gdi32.SetBrushOrgEx(mem_dc, 0, 0, byref(pt))  # HALFTONE 必要步驟

            # 8. 載入並播放 EMF
            hemf = _gdi32.SetEnhMetaFileBits(len(emf), emf)
            if not hemf:
                raise JpgRenderError("SetEnhMetaFileBits 失敗，無法載入 EMF 頁面")
            try:
                ok = _gdi32.PlayEnhMetaFile(mem_dc, hemf, byref(rect))
                if not ok:
                    raise JpgRenderError("PlayEnhMetaFile 失敗")
            finally:
                _gdi32.DeleteEnhMetaFile(hemf)

            # 9. 從 bits_ptr 直接讀取 BGR 像素資料並轉為 PIL Image
            # 24bpp 每列的位元組數須對齊 4 位元組邊界
            stride = ((width_px * 24 + 31) // 32) * 4
            total_bytes = stride * height_px

            raw_bytes = (ctypes.c_ubyte * total_bytes).from_address(bits_ptr.value)
            img = Image.frombuffer(
                "RGB",
                (width_px, height_px),
                bytes(raw_bytes),
                "raw", "BGR", stride, 1,
            )
            # 10. 複製一份確保 GDI 物件釋放後仍可存取像素資料
            img = img.copy()

        finally:
            # 11. 釋放 GDI 物件（只有在 SelectObject 成功後才需要還原）
            if old_bmp:
                _gdi32.SelectObject(mem_dc, old_bmp)
            _gdi32.DeleteObject(hbmp)

    finally:
        _gdi32.DeleteDC(mem_dc)

    return img


# ── 公開介面 ───────────────────────────────────────────────────────────────────
def render_jpg(
    pages: list[bytes],
    output_base: str | Path,
    dpi: int = DEFAULT_DPI,
    quality: int = 95,
) -> list[Path]:
    """將 EMF 頁面清單渲染為高解析度 JPG 檔案。

    單頁：<output_base>.jpg  （若 output_base 已有 .jpg 副檔名則沿用）
    多頁：<output_base>_1.jpg, <output_base>_2.jpg, ...
    回傳產生的 JPG 路徑清單（依頁序）。
    """
    if not pages:
        raise JpgRenderError("沒有頁面可渲染")

    base = Path(output_base)
    # 統一去除 .jpg 副檔名，方便後續重新加上
    if base.suffix.lower() == ".jpg":
        base = base.with_suffix("")

    output_paths: list[Path] = []

    if len(pages) == 1:
        # 單頁：<stem>.jpg
        out_path = base.with_suffix(".jpg")
        img = _render_page(pages[0], dpi)
        img.save(out_path, "JPEG", quality=quality, dpi=(dpi, dpi))
        output_paths.append(out_path)
    else:
        # 多頁：<stem>_1.jpg, <stem>_2.jpg, ...
        for idx, emf in enumerate(pages, start=1):
            out_path = base.parent / f"{base.stem}_{idx}.jpg"
            img = _render_page(emf, dpi)
            img.save(out_path, "JPEG", quality=quality, dpi=(dpi, dpi))
            output_paths.append(out_path)

    return output_paths
