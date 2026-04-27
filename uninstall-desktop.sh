#!/usr/bin/env bash
# 移除桌面與應用程式選單的 QRP 轉 JPG 工具啟動圖示
set -euo pipefail

DESKTOP_FILE_NAME="qrp2jpg.desktop"
APPS_DIR="$HOME/.local/share/applications"

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

removed=0
for target in "$DESKTOP_DIR/$DESKTOP_FILE_NAME" "$APPS_DIR/$DESKTOP_FILE_NAME"; do
    if [[ -f "$target" ]]; then
        rm -f "$target"
        echo "✓ 已移除：$target"
        removed=1
    fi
done

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "$APPS_DIR" 2>/dev/null || true
fi

if [[ $removed -eq 0 ]]; then
    echo "未找到任何已安裝的圖示"
fi
