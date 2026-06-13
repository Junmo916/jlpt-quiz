@echo off
chcp 65001 >nul
echo.
echo  日文背词 — JLPT 10k
echo  ────────────────
echo  1. 桌面版 (Tkinter)
echo  2. Web 版 (移动端 PWA)
echo  3. Android 版 (KivyMD APK)
echo.
set /p choice="请选择 (1/2/3): "
if "%choice%"=="2" (
    python "%~dp0app_run.py" web
) else if "%choice%"=="3" (
    echo.
    echo  推荐方案：推送代码到 GitHub → Actions 自动构建 APK
    echo  本地构建请查看 android\BUILD.md
    echo.
    start notepad "%~dp0android\BUILD.md"
    pause
) else (
    python "%~dp0app_run.py"
)
pause
