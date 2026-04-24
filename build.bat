@echo off
setlocal

if not exist ".venv\Scripts\python.exe" (
    echo 錯誤：找不到虛擬環境，請先執行 python -m venv .venv 並安裝依賴
    exit /b 1
)

if exist "dist" rmdir /s /q dist
if exist "build" rmdir /s /q build

set PY=.venv\Scripts\python.exe

%PY% -m PyInstaller --noconfirm --onefile --windowed ^
    --name "QRP轉PDF工具" ^
    --collect-all tkinterdnd2 ^
    src\main.py

if not exist "dist\QRP轉PDF工具.exe" (
    echo 打包失敗：dist\QRP轉PDF工具.exe 未產生
    exit /b 1
)

echo.
echo 打包完成：dist\QRP轉PDF工具.exe
endlocal
