"""JPG 渲染器（Linux 版本）：透過 LibreOffice headless 將 EMF 頁面轉為 PNG，再以 Pillow 縮放為 A4 JPG。"""
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

# LibreOffice headless 轉檔逾時（秒）
_LO_TIMEOUT = 120


class JpgRenderError(Exception):
    """JPG 渲染失敗。"""


def _find_libreoffice() -> str:
    """尋找 LibreOffice 執行檔路徑。"""
    for name in ("libreoffice", "soffice"):
        path = shutil.which(name)
        if path:
            return path
    raise JpgRenderError(
        "找不到 LibreOffice。請安裝：sudo apt install libreoffice（Debian/Ubuntu）"
        "或 sudo dnf install libreoffice（Fedora）"
    )


def _render_page(emf: bytes, dpi: int, lo_cmd: str) -> Image.Image:
    """將單一 EMF 頁面渲染為 PIL Image（RGB），固定以 A4 尺寸輸出。"""
    target_w = max(1, round(A4_WIDTH_MM  * dpi / 25.4))
    target_h = max(1, round(A4_HEIGHT_MM * dpi / 25.4))

    with tempfile.TemporaryDirectory() as _tmp:
        tmpdir = Path(_tmp)
        emf_path = tmpdir / "page.emf"
        emf_path.write_bytes(emf)

        try:
            result = subprocess.run(
                [lo_cmd, "--headless", "--convert-to", "png",
                 "--outdir", str(tmpdir), str(emf_path)],
                capture_output=True, text=True, timeout=_LO_TIMEOUT,
            )
        except subprocess.TimeoutExpired as e:
            raise JpgRenderError(f"LibreOffice 轉換逾時（{_LO_TIMEOUT}s）") from e

        png_path = tmpdir / "page.png"
        if not png_path.exists():
            raise JpgRenderError(
                f"LibreOffice 轉換失敗（return code={result.returncode}）：\n"
                f"stdout: {result.stdout}\nstderr: {result.stderr}"
            )

        # 載入 PNG 並縮放為 A4 目標尺寸（LANCZOS 高品質縮放）
        with Image.open(png_path) as img:
            rgb = img.convert("RGB")
            resized = rgb.resize((target_w, target_h), Image.LANCZOS)
            return resized.copy()


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

    base = Path(output_base)
    if base.suffix.lower() == ".jpg":
        base = base.with_suffix("")

    output_paths: list[Path] = []

    if len(pages) == 1:
        out_path = base.with_suffix(".jpg")
        img = _render_page(pages[0], dpi, lo_cmd)
        img.save(out_path, "JPEG", quality=quality, dpi=(dpi, dpi))
        output_paths.append(out_path)
    else:
        for idx, emf in enumerate(pages, start=1):
            out_path = base.parent / f"{base.stem}_{idx}.jpg"
            img = _render_page(emf, dpi, lo_cmd)
            img.save(out_path, "JPEG", quality=quality, dpi=(dpi, dpi))
            output_paths.append(out_path)

    return output_paths
