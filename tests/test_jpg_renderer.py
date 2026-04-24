"""測試 jpg_renderer 模組。"""
from __future__ import annotations
import struct
from pathlib import Path

import pytest
from PIL import Image

from src.jpg_renderer import render_jpg, JpgRenderError, DEFAULT_DPI
from src.qrp_parser import parse_qrp


# ── 最小有效 EMF 組件（用於模擬測試） ──────────────────────────────────────────
def _make_minimal_emf(width_01mm: int = 21000, height_01mm: int = 29700) -> bytes:
    """產生最小有效的 EMF 記憶體物件。

    EMF header 格式：
      offset 0:  DWORD iType = 1 (EMR_HEADER)
      offset 4:  DWORD nSize（含記錄大小）
      offset 8:  RECT rclBounds (16 bytes)
      offset 24: RECT rclFrame (left, top, right, bottom，單位 0.01mm)
      offset 40: DWORD dSignature = 0x464D4520
      offset 44: DWORD nVersion
      offset 48: DWORD nBytes（檔案總大小）
      offset 52: DWORD nRecords
      offset 56: WORD  nHandles
      offset 58: WORD  sReserved
      offset 60: DWORD nDescription
      offset 64: DWORD offDescription
      offset 68: DWORD nPalEntries
      offset 72: SIZEL szlDevice (2 × LONG)
      offset 80: SIZEL szlMillimeters (2 × LONG)
    後面接 EMR_EOF 記錄（iType=14，nSize=20）
    """
    # rclFrame: left=0, top=0, right=width, bottom=height
    emr_header = struct.pack(
        "<IIIIIIIIIIIIII IIIIIIII II II II II II II",
        1,          # iType = EMR_HEADER
        108,        # nSize = header record size
        0, 0, width_01mm, height_01mm,   # rclBounds（4 × int32）
        0, 0, width_01mm, height_01mm,   # rclFrame（4 × int32）
        0x464D4520, # dSignature
        0x00010000, # nVersion
        108 + 20,   # nBytes = header + EOF
        2,          # nRecords
        1,          # nHandles
        0,          # sReserved
        0,          # nDescription
        0,          # offDescription
        0,          # nPalEntries
        1024, 768,  # szlDevice
        270, 203,   # szlMillimeters
    )
    emr_eof = struct.pack("<III IIII",
        14,  # iType = EMR_EOF
        20,  # nSize
        0,   # nPalEntries
        0,   # offPalEntries
        20,  # nSizeLast（= nSize）
    )
    # 補齊 emr_header 至 108 位元組（struct.pack 可能不足）
    emr_header = emr_header[:108].ljust(108, b"\x00")
    return emr_header + emr_eof


# ── 單元測試 ───────────────────────────────────────────────────────────────────

def test_default_dpi_is_200():
    """確認預設 DPI 常數為 200。"""
    assert DEFAULT_DPI == 200


def test_jpg_render_error_is_exception():
    """JpgRenderError 應為 Exception 子類別。"""
    assert issubclass(JpgRenderError, Exception)


def test_render_jpg_empty_raises():
    """空頁面清單應拋出 JpgRenderError。"""
    with pytest.raises(JpgRenderError, match="沒有頁面可渲染"):
        render_jpg([], "dummy_output")


def test_render_jpg_single_page(tmp_path):
    """單頁 EMF 應產生 <output_base>.jpg。"""
    pages = parse_qrp(Path(__file__).resolve().parent.parent / "範例" / "1-1.QRP")
    out = render_jpg(pages, tmp_path / "output")
    assert len(out) == 1
    assert out[0].name == "output.jpg"
    assert out[0].exists()


def test_render_jpg_single_page_with_jpg_suffix(tmp_path):
    """output_base 帶有 .jpg 副檔名時，輸出路徑應相同。"""
    pages = parse_qrp(Path(__file__).resolve().parent.parent / "範例" / "1-1.QRP")
    out = render_jpg(pages, tmp_path / "output.jpg")
    assert len(out) == 1
    assert out[0].name == "output.jpg"
    assert out[0].exists()


def test_render_jpg_output_dimensions_reasonable(tmp_path):
    """輸出 JPG 的解析度應合理（寬高均 >= 500px）。"""
    pages = parse_qrp(Path(__file__).resolve().parent.parent / "範例" / "1-1.QRP")
    out = render_jpg(pages, tmp_path / "size_check")
    img = Image.open(out[0])
    width, height = img.size
    assert width >= 500, f"寬度 {width}px 低於預期"
    assert height >= 500, f"高度 {height}px 低於預期"


def test_render_jpg_file_size_reasonable(tmp_path):
    """輸出 JPG 大小應 > 50 KB（確保非空白頁）。"""
    pages = parse_qrp(Path(__file__).resolve().parent.parent / "範例" / "1-1.QRP")
    out = render_jpg(pages, tmp_path / "filesize_check")
    size = out[0].stat().st_size
    assert size > 50_000, f"JPG 大小 {size:,} bytes，低於 50 KB"


def test_render_jpg_multipage_naming(tmp_path, monkeypatch):
    """多頁輸入應產生 _1.jpg, _2.jpg 命名。"""
    # 使用兩個相同頁面模擬多頁 QRP
    pages = parse_qrp(Path(__file__).resolve().parent.parent / "範例" / "1-1.QRP")
    if len(pages) < 2:
        # 手動複製為兩頁
        pages = pages * 2

    out = render_jpg(pages[:2], tmp_path / "multi")
    assert len(out) == 2
    assert out[0].name == "multi_1.jpg"
    assert out[1].name == "multi_2.jpg"
    assert out[0].exists()
    assert out[1].exists()


def test_render_jpg_multipage_with_suffix_naming(tmp_path):
    """多頁輸入且 output_base 帶 .jpg 時，命名應為 <stem>_1.jpg。"""
    pages = parse_qrp(Path(__file__).resolve().parent.parent / "範例" / "1-1.QRP")
    pages = pages * 2  # 強制兩頁

    out = render_jpg(pages[:2], tmp_path / "multi.jpg")
    assert out[0].name == "multi_1.jpg"
    assert out[1].name == "multi_2.jpg"


def test_render_jpg_is_valid_jpeg(tmp_path):
    """輸出檔案應為有效的 JPEG 格式。"""
    pages = parse_qrp(Path(__file__).resolve().parent.parent / "範例" / "1-1.QRP")
    out = render_jpg(pages, tmp_path / "valid_jpeg")
    # JPEG 檔案以 FF D8 FF 開頭
    header = out[0].read_bytes()[:3]
    assert header == b"\xff\xd8\xff", f"非 JPEG header：{header.hex()}"


# ── 整合測試（使用真實 QRP 檔案） ───────────────────────────────────────────────

def test_integration_render_real_qrp(sample_qrp_path, tmp_path):
    """整合測試：解析真實 QRP 並渲染為 JPG。"""
    pages = parse_qrp(sample_qrp_path)
    assert pages, "parse_qrp 應回傳至少一頁"
    out = render_jpg(pages, tmp_path / "integration_out")
    assert all(p.exists() for p in out)
    assert all(p.stat().st_size > 0 for p in out)
