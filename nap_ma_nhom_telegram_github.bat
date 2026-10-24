@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PATH=%LOCALAPPDATA%\Programs\ghcli\bin;%PATH%
rem Dua ma 2 nhom Telegram (BAO CAO KIEM TIEN + SAN PHAM WIN) trong config.local.json len GitHub Secret
rem TELEGRAM_REPORT_CHAT_ID + TELEGRAM_WIN_CHAT_ID. 24/10: bao cao 23/10 loi "chat not found" vi secret tren GitHub sai ma nhom.
gh auth status >nul 2>&1
if errorlevel 1 (
  echo  Can dang nhap GitHub 1 lan: chep MA 8 KY TU ben duoi, bam Enter de mo trinh duyet, dan ma roi bam Authorize.
  echo.
  gh auth login --hostname github.com --git-protocol https --web --scopes workflow
)
python -c "import json;v=str(json.load(open('config.local.json',encoding='utf-8')).get('telegram_report_chat_id','')).strip();print(v,end='') if v else exit(1)" | gh secret set TELEGRAM_REPORT_CHAT_ID -R hoangk40-prog/bot-deal-tiktok
if errorlevel 1 goto loi
python -c "import json;v=str(json.load(open('config.local.json',encoding='utf-8')).get('telegram_win_chat_id','')).strip();print(v,end='') if v else exit(1)" | gh secret set TELEGRAM_WIN_CHAT_ID -R hoangk40-prog/bot-deal-tiktok
if errorlevel 1 goto loi
echo.
echo  DA DUA MA 2 NHOM TELEGRAM LEN GITHUB.
goto het
:loi
echo.
echo  LOI: chua dua duoc ma len GitHub. Chup dong loi gui Claude.
:het
echo  Bam phim bat ky de dong.
pause >nul
