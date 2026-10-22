@echo off
chcp 65001 >nul
cd /d "%~dp0"
rem Chep ID Trang / ma Trang Facebook (tu config.local.json) vao bo nho tam de dan vao GitHub Secrets. Khong hien ma len man hinh.
python -c "import json;print(json.load(open('config.local.json',encoding='utf-8'))['fb_page_id'],end='')" | clip
echo Da chep FB_PAGE_ID. Dan vao GitHub (Ctrl+V) roi bam phim bat ky de chep tiep FB_PAGE_TOKEN...
pause >nul
python -c "import json;print(json.load(open('config.local.json',encoding='utf-8'))['fb_page_token'],end='')" | clip
echo Da chep FB_PAGE_TOKEN. Dan vao GitHub (Ctrl+V). Bam phim bat ky de dong.
pause >nul
echo off | clip
