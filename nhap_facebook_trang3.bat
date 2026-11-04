@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PYTHONIOENCODING=utf-8
rem 04/11: lay ma TRANG 3 (nick moi, app rieng) -> config.local.json fb_page3_*
python luu_facebook.py 3
