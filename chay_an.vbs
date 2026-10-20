' Chay chay_that.bat che do "lich" ma KHONG hien cua so den. Lich Windows "San Deal TikTok" goi file nay moi gio.
Set sh = CreateObject("WScript.Shell")
dir = CreateObject("Scripting.FileSystemObject").GetParentFolderName(WScript.ScriptFullName)
sh.CurrentDirectory = dir
sh.Run "cmd /c """ & dir & "\chay_that.bat"" lich", 0, True
