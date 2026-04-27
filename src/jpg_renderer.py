"""JPG 渲染器（Linux 版本）：LibreOffice EMF→PDF → pdftoppm PDF→PNG @ 目標 DPI → Pillow 輸出 JPG。

關鍵：先以 LibreOffice 將 EMF 轉為 PDF（保留向量），再用 pdftoppm 直接以目標 DPI
光柵化。避免「先以低 DPI 轉 PNG 再放大」造成的模糊。
"""
from __future__ import annotations
import shutil
import subprocess
import tempfile
from pathlib import Path

from PIL import Image

DEFAULT_DPI = 200

# A4 標準尺寸（mm）
A4_WIDTH_MM  = 210.0
A4_HEIGHT_MM = 297.0

# 子程序逾時（秒）
_LO_TIMEOUT = 120
_PDFTOPPM_TIMEOUT = 60


class JpgRenderError(Exception):
    """JPG 渲染失敗。"""


def _find_libreoffice() -> str:
    """尋找 LibreOffice 執行檔路徑。"""
    for name in ("libreoffice", "soffice"):
        path = shutil.which(name)
        if path:
            return path
    raise JpgRenderError(
        "找不到 LibreOffice。請安裝：sudo apt install libreoffice"
    )


def _find_pdftoppm() -> str:
    """尋找 pdftoppm 執行檔路徑（poppler-utils）。"""
    path = shutil.which("pdftoppm")
    if path:
        return path
    raise JpgRenderError(
        "找不到 pdftoppm。請安裝：sudo apt install poppler-utils"
    )


def _emf_to_pdf(emf: bytes, tmpdir: Path, lo_cmd: str) -> Path:
    """以 LibreOffice 將 EMF 轉為 PDF（向量保留）。"""
    emf_path = tmpdir / "page.emf"
    emf_path.write_bytes(emf)

    try:
        result = subprocess.run(
            [lo_cmd, "--headless", "--convert-to", "pdf",
             "--outdir", str(tmpdir), str(emf_path)],
            capture_output=True, text=True, timeout=_LO_TIMEOUT,
        )
    except subprocess.TimeoutExpired as e:
        raise JpgRenderError(f"LibreOffice 轉 PDF 逾時（{_LO_TIMEOUT}s）") from e

    pdf_path = tmpdir / "page.pdf"
    if not pdf_path.exists():
        raise JpgRenderError(
            f"LibreOffice EMF→PDF 轉換失敗（return code={result.returncode}）：\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return pdf_path


def _pdf_to_png(pdf_path: Path, dpi: int, tmpdir: Path, pdftoppm_cmd: str) -> Path:
    """以 pdftoppm 將 PDF 第一頁以指定 DPI 光柵化為 PNG。"""
    out_prefix = tmpdir / "rendered"
    try:
        result = subprocess.run(
            [pdftoppm_cmd, "-png", "-r", str(dpi), "-f", "1", "-l", "1",
             str(pdf_path), str(out_prefix)],
            capture_output=True, text=True, timeout=_PDFTOPPM_TIMEOUT,
        )
    except subprocess.TimeoutExpired as e:
        raise JpgRenderError(f"pdftoppm 逾時（{_PDFTOPPM_TIMEOUT}s）") from e

    # pdftoppm 輸出檔名為 <prefix>-1.png 或 <prefix>-01.png（依總頁數位數）
    candidates = sorted(tmpdir.glob("rendered-*.png"))
    if not candidates:
        raise JpgRenderError(
            f"pdftoppm 未產生 PNG（return code={result.returncode}）：\n"
            f"stdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return candidates[0]


def _render_page(emf: bytes, dpi: int, lo_cmd: str, pdftoppm_cmd: str) -> Image.Image:
    """將單一 EMF 頁面渲染為 PIL Image（RGB），固定以 A4 尺寸輸出。"""
    target_w = max(1, round(A4_WIDTH_MM  * dpi / 25.4))
    target_h = max(1, round(A4_HEIGHT_MM * dpi / 25.4))

    with tempfile.TemporaryDirectory() as _tmp:
        tmpdir = Path(_tmp)
        pdf_path = _emf_to_pdf(emf, tmpdir, lo_cmd)
        png_path = _pdf_to_png(pdf_path, dpi, tmpdir, pdftoppm_cmd)

        with Image.open(png_path) as img:
            rgb = img.convert("RGB")
            # 若 pdftoppm 輸出尺寸非 A4（PDF 紙張尺寸不一定是 A4），統一縮放成 A4
            if rgb.size != (target_w, target_h):
                rgb = rgb.resize((target_w, target_h), Image.LANCZOS)
            return rgb.copy()


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

    lo_cmd = _find_libreoffice()
    pdftoppm_cmd = _find_pdftoppm()

    base = Path(output_base)
    if base.suffix.lower() == ".jpg":
        base = base.with_suffix("")

    output_paths: list[Path] = []

    if len(pages) == 1:
        out_path = base.with_suffix(".jpg")
        img = _render_page(pages[0], dpi, lo_cmd, pdftoppm_cmd)
        img.save(out_path, "JPEG", quality=quality, dpi=(dpi, dpi))
        output_paths.append(out_path)
    else:
        for idx, emf in enumerate(pages, start=1):
            out_path = base.parent / f"{base.stem}_{idx}.jpg"
            img = _render_page(emf, dpi, lo_cmd, pdftoppm_cmd)
            img.save(out_path, "JPEG", quality=quality, dpi=(dpi, dpi))
            output_paths.append(out_path)

    return output_paths
