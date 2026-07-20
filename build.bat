@echo off
chcp 65001 >nul
echo ============================================
echo   ساخت فایل اجرایی LAN Chat برای ویندوز
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 (
    echo پایتون پیدا نشد. لطفا ابتدا Python 3.9 یا بالاتر را از python.org نصب کنید
    echo و در هنگام نصب گزینه "Add Python to PATH" را فعال کنید.
    pause
    exit /b 1
)

echo [1/3] نصب PyInstaller و Pillow و comtypes ...
pip install --upgrade pyinstaller pillow comtypes

echo.
echo [2/3] ساخت فایل exe ...
pyinstaller --onefile --windowed --name "LanChat by MGH" --hidden-import=comtypes.stream --collect-submodules comtypes main.py

echo.
echo [3/3] پایان.
echo فایل نهایی در پوشه dist\"LanChat by MGH.exe" قرار دارد.
echo این فایل را می‌توانید روی هر کامپیوتر ویندوزی دیگری کپی و اجرا کنید
echo (نیازی به نصب پایتون روی آن سیستم‌ها نیست).
echo.
pause
