' Ejecuta un comando SIN mostrar ventana (para las tareas programadas)
' Uso: wscript.exe run-hidden.vbs "D:\jaru\rituals\briefing.mjs"
Set sh = CreateObject("WScript.Shell")
cmd = "node """ & WScript.Arguments(0) & """ > """ & WScript.Arguments(0) & ".salida.log"" 2>&1"
sh.Run cmd, 0, False
