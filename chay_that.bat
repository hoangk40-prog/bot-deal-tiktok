@echo off
rem Chay that: lay san pham, gui Telegram. Lich Windows goi file nay luc 11h va 19h.
rem Bam dup tay = gui ngay (bo qua khung gio). Nhat ky luu o nhat_ky.txt.
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
if /i not "%~1"=="lich" set FORCE=true
echo ===== %date% %time% ===== >> nhat_ky.txt
python auto_deals.py >> nhat_ky.txt 2>&1
if /i not "%~1"=="lich" (
  powershell -NoProfile -Command "Get-Content -Encoding UTF8 nhat_ky.txt -Tail 15"
  pause
)
