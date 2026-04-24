"""測試 jpg_renderer 模組。"""
from __future__ import annotations
import struct
from pathlib import Path

import pytest
from PIL import Image

from src.jpg_renderer import render_jpg, JpgRenderError, DEFAULT_DPI
from src.qrp_parser import parse_qrp


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
    assert all(p.stat().st_size > 50_000 for p in out), "JPG 檔案過小，可能渲染失敗"
