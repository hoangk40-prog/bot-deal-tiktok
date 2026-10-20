@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
set DRY_RUN=1
set FORCE=true
echo Dang chay thu, doi khoang 1 phut...
echo.
python auto_deals.py > ket_qua.txt 2>&1
type ket_qua.txt
echo.
echo ============================================================
echo XONG. Ket qua da luu trong file ket_qua.txt (cung thu muc).
echo Anh gui noi dung file ket_qua.txt cho em.
echo ============================================================
pause
