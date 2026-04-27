#!/usr/bin/env bash
# 在 Linux 桌面與應用程式選單建立 QRP 轉 JPG 工具的啟動圖示
set -euo pipefail

# ── 解析專案根目錄（本腳本所在目錄）─────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
EXEC_PATH="$SCRIPT_DIR/dist/qrp2jpg"

# ── 前置檢查 ────────────────────────────────────────────────────────────────────
if [[ ! -x "$EXEC_PATH" ]]; then
    echo "錯誤：找不到執行檔 $EXEC_PATH"
    echo "請先在專案根目錄執行 ./build.sh 完成打包"
    exit 1
fi

# ── 桌面資料夾偵測（中文/英文 locale 皆支援，並參考 XDG 設定）──────────────────
detect_desktop_dir() {
    if command -v xdg-user-dir >/dev/null 2>&1; then
        local d
        d="$(xdg-user-dir DESKTOP)"
        if [[ -n "$d" && -d "$d" ]]; then
            echo "$d"
            return
        fi
    fi
    for candidate in "$HOME/Desktop" "$HOME/桌面"; do
        if [[ -d "$candidate" ]]; then
            echo "$candidate"
            return
        fi
    done
    echo "$HOME/Desktop"
}

DESKTOP_DIR="$(detect_desktop_dir)"
APPS_DIR="$HOME/.local/share/applications"
mkdir -p "$APPS_DIR" "$DESKTOP_DIR"

# ── 圖示路徑（若專案內無 icon.png 則使用系統內建圖示名稱）────────────────────────
if [[ -f "$SCRIPT_DIR/icon.png" ]]; then
    ICON_VALUE="$SCRIPT_DIR/icon.png"
else
    ICON_VALUE="image-x-generic"
fi

# ── 產生 .desktop 內容 ─────────────────────────────────────────────────────────
DESKTOP_FILE_NAME="qrp2jpg.desktop"
TMP_DESKTOP="$(mktemp)"
cat > "$TMP_DESKTOP" <<EOF
[Desktop Entry]
Type=Application
Version=1.0
Name=QRP 轉 JPG 工具
Name[en]=QRP to JPG Converter
Comment=將 QRP 拉伸報告轉換為 JPG 圖檔
Comment[en]=Convert QRP tensile reports to JPG images
Exec=$EXEC_PATH
Icon=$ICON_VALUE
Terminal=false
Categories=Utility;Office;Graphics;
StartupNotify=true
EOF

# ── 安裝到桌面 ──────────────────────────────────────────────────────────────────
DESKTOP_TARGET="$DESKTOP_DIR/$DESKTOP_FILE_NAME"
install -m 755 "$TMP_DESKTOP" "$DESKTOP_TARGET"

# GNOME (Ubuntu 22.04+) 需要將桌面 .desktop 標記為信任才會顯示為應用程式圖示
if command -v gio >/dev/null 2>&1; then
    gio set "$DESKTOP_TARGET" metadata::trusted true 2>/dev/null || true
fi

# ── 安裝到應用程式選單 ──────────────────────────────────────────────────────────
APPS_TARGET="$APPS_DIR/$DESKTOP_FILE_NAME"
install -m 644 "$TMP_DESKTOP" "$APPS_TARGET"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi

rm -f "$TMP_DESKTOP"

# ── 完成提示 ────────────────────────────────────────────────────────────────────
echo "✓ 桌面圖示已建立：$DESKTOP_TARGET"
echo "✓ 應用程式選單項目已建立：$APPS_TARGET"
echo
echo "若桌面圖示顯示為文件而非可執行圖示，請在桌面圖示上按右鍵選擇「允許啟動」"
echo "（GNOME / Ubuntu 22.04+ 首次需手動信任）"
