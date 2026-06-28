@echo off
echo.
echo ========================================
echo  Health Trend Dashboard - Setup
echo ========================================
echo.

python --version
if errorlevel 1 (
    echo [ERROR] Python not found.
    echo Please install Python from python.org first.
    echo Make sure to check "Add Python to PATH" during install.
    pause
    exit /b 1
)

echo.
echo Installing required packages...
echo.

pip install requests==2.31.0
pip install pytrends==4.9.2
pip install beautifulsoup4==4.12.3
pip install lxml==5.1.0

echo.
echo ========================================
echo  Done! Next: open src/config.py
echo  and enter your Naver API keys.
echo ========================================
echo.
pause
