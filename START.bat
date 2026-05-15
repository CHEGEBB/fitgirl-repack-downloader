@echo off
title FitGirl Repack Downloader
color 0A

echo ============================================
echo   FitGirl Repack Downloader
echo   github.com/brianchege
echo ============================================
echo.

python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo Python not found! Install from python.org and tick "Add to PATH"
    start https://www.python.org/downloads/
    pause & exit
)

echo Installing dependencies...
pip install requests beautifulsoup4 -q

echo Launching...
python main.py
