' Chay bot Zalo nick phu (zalo_bot.py dang) KHONG hien cua so den. Lich Windows "Bot Zalo dang deal" goi file nay theo zalo_hours.
' 24/10: ghi ca loi khoi dong (python khong chay, loi import...) vao %LOCALAPPDATA%\zalo_bot\chay_lich.txt de biet vi sao lich khong dang.
Set sh = CreateObject("WScript.Shell")
dir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
lf = """%LOCALAPPDATA%\zalo_bot\chay_lich.txt"""
sh.Run "cmd /c set PYTHONIOENCODING=utf-8& echo ===== %date% %time% >> " & lf & " & python zalo_bot.py dang >> " & lf & " 2>&1", 0, True
