Set ws = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
batPath = fso.GetParentFolderName(WScript.ScriptFullName) & "\run_checker.bat"
ws.Run Chr(34) & batPath & Chr(34), 1, False