' Chay bot Zalo nick phu (zalo_bot.py dang) KHONG hien cua so den. Lich Windows "Bot Zalo dang deal" goi file nay 9h/12h/17h/20h.
Set sh = CreateObject("WScript.Shell")
dir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
sh.Run "cmd /c python zalo_bot.py dang", 0, True
