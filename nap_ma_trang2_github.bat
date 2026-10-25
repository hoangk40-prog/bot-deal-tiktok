@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PATH=%LOCALAPPDATA%\Programs\ghcli\bin;%PATH%
rem 25/10: dua ma Trang 2 "Cuoi Moi Ngay Sale Hoi" (config.local.json fb_page2_*) len GitHub Secret FB_PAGE2_ID / FB_PAGE2_TOKEN. Khong hien ma.
gh auth status >nul 2>&1
if errorlevel 1 (
  echo  Can dang nhap GitHub 1 lan: chep MA 8 KY TU ben duoi, bam Enter de mo trinh duyet, dan ma roi bam Authorize.
  echo.
  gh auth login --hostname github.com --git-protocol https --web --scopes workflow
)
python -c "import json;print(json.load(open('config.local.json',encoding='utf-8'))['fb_page2_id'],end='')" | gh secret set FB_PAGE2_ID -R hoangk40-prog/bot-deal-tiktok
if errorlevel 1 goto loi
python -c "import json;print(json.load(open('config.local.json',encoding='utf-8'))['fb_page2_token'],end='')" | gh secret set FB_PAGE2_TOKEN -R hoangk40-prog/bot-deal-tiktok
if errorlevel 1 goto loi
echo.
echo  DA DUA MA TRANG 2 LEN GITHUB. Bao Claude "xong".
goto het
:loi
echo.
echo  LOI: chua dua duoc ma len GitHub. Chup dong loi gui Claude.
:het
echo  Bam phim bat ky de dong.
pause >nul
