@echo off
setlocal
set PY=.venv\Scripts\python.exe

%PY% -m PyInstaller --noconfirm --onefile --windowed ^
    --name "QRP轉PDF工具" ^
    --collect-all tkinterdnd2 ^
    src\main.py

echo.
echo 打包完成：dist\QRP轉PDF工具.exe
endlocal
