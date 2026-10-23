@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo Dat lich Windows "Bot Zalo dang deal": 9h, 12h, 17h, 20h moi ngay (bot tu lech 0-8 phut).
powershell -NoProfile -Command "$vbs = Join-Path (Get-Location) 'zalo_an.vbs'; $act = New-ScheduledTaskAction -Execute 'wscript.exe' -Argument ('\"' + $vbs + '\"'); $tr = @('09:00','12:00','17:00','20:00') | ForEach-Object { New-ScheduledTaskTrigger -Daily -At $_ }; $set = New-ScheduledTaskSettingsSet -ExecutionTimeLimit (New-TimeSpan -Minutes 30) -MultipleInstances IgnoreNew; Register-ScheduledTask -TaskName 'Bot Zalo dang deal' -Action $act -Trigger $tr -Settings $set -Description 'Nick Zalo phu dang 4 deal vao nhom (zalo_bot.py). Tat: Disable task nay.' -Force | Out-Null; Get-ScheduledTask 'Bot Zalo dang deal' | Select-Object TaskName,State | Format-Table"
echo.
echo Xong. Muon tat: mo Task Scheduler, tim "Bot Zalo dang deal" -^> Disable.
pause
