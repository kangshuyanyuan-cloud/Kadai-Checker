Set ws = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")
currentDir = fso.GetParentFolderName(WScript.ScriptFullName)

pythonExe = "C:\Users\Owner\AppData\Local\Programs\Python\Python312\pythonw.exe"
scriptPath = currentDir & "\restore_window.py"

' Run the python script silently
ws.Run Chr(34) & pythonExe & Chr(34) & " " & Chr(34) & scriptPath & Chr(34), 0, False
