@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Mo Zalo Web cua BOT. Dung dien thoai cam NICK ZALO PHU de quet ma QR.
python zalo_bot.py dang_nhap
pause
