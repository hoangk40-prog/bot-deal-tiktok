@echo off
chcp 65001 >nul
cd /d "%~dp0"
set PATH=%LOCALAPPDATA%\Programs\ghcli\bin;%PATH%
rem Dua khoa Gemini (khoa da luu trong Xuong Video, cung Google Drive) len GitHub Secret GEMINI_API_KEY de bot Telegram
rem va Trang Facebook viet loi chao hang bang AI. Khong hien khoa len man hinh.
gh auth status >nul 2>&1
if errorlevel 1 (
  echo  Can dang nhap GitHub 1 lan: chep MA 8 KY TU ben duoi, bam Enter de mo trinh duyet, dan ma roi bam Authorize.
  echo.
  gh auth login --hostname github.com --git-protocol https --web --scopes workflow
)
python -c "import auto_deals as a;k=a.gemini_key();print(k,end='') if k else exit(1)" | gh secret set GEMINI_API_KEY -R hoangk40-prog/bot-deal-tiktok
if errorlevel 1 (
  echo.
  echo  LOI: chua dua duoc khoa len GitHub. Chup dong loi gui Claude.
) else (
  echo.
  echo  DA DUA KHOA GEMINI LEN GITHUB.
)
echo  Bam phim bat ky de dong.
pause >nul
