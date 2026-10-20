@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
echo Dang kham API Accesstrade, doi khoang 1-2 phut...
python kham_api.py > ket_qua_api.txt 2>&1
type ket_qua_api.txt
echo.
echo ============================================================
echo XONG. Anh gui noi dung file ket_qua_api.txt cho em.
echo ============================================================
pause
