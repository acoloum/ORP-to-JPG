#!/usr/bin/env bash
# Linux 打包腳本：使用 PyInstaller 產生單一執行檔
set -euo pipefail

if [[ ! -x ".venv/bin/python" ]]; then
    echo "錯誤：找不到虛擬環境，請先執行 python3 -m venv .venv 並安裝依賴"
    exit 1
fi

# 檢查 LibreOffice 是否已安裝（執行階段依賴）
if ! command -v libreoffice >/dev/null 2>&1 && ! command -v soffice >/dev/null 2>&1; then
    echo "警告：系統未安裝 LibreOffice，打包完成後執行時將無法轉檔"
    echo "請安裝：sudo apt install libreoffice"
fi

rm -rf dist build

PY=".venv/bin/python"

"$PY" -m PyInstaller --noconfirm --onefile \
    --name "qrp2jpg" \
    --collect-all tkinterdnd2 \
    src/main.py

if [[ ! -f "dist/qrp2jpg" ]]; then
    echo "打包失敗：dist/qrp2jpg 未產生"
    exit 1
fi

echo
echo "打包完成：dist/qrp2jpg"
echo "執行前請確認系統已安裝 LibreOffice"
