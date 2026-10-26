@echo off
:: ============================================
::  CMD + VOZ CLOUD - Orquestador Automático
:: ============================================
:: Uso: cmd_voz.bat "comando a ejecutar" "nombre-agente"
:: Ejemplo: cmd_voz.bat "dir C:\" "agente-dir"
:: ============================================

set VOZ_URL=http://127.0.0.1:8000

if "%~1"=="" (
    echo.
    echo USO: cmd_voz.bat "comando" "nombre-agente"
    echo.
    echo Ejemplos:
    echo   cmd_voz.bat "dir C:\" "agente-dir"
    echo   cmd_voz.bat "ping 127.0.0.1 -n 3" "agente-red"
    echo   cmd_voz.bat "opencode" "opencode"
    echo.
    exit /b 0
)

set CMD_TO_RUN=%~1
set AGENT_NAME=%~2
if "%AGENT_NAME%"=="" set AGENT_NAME=cmd-agente

:: Verificar que Voz Cloud esté arriba
curl -s -o nul -w "%%{http_code}" %VOZ_URL%/health > nul 2>&1
if %errorlevel% neq 0 (
    echo [ERROR] Voz Cloud no esta corriendo en %VOZ_URL%
    echo Ejecuta: cd D:\voz-cloud && .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000
    exit /b 1
)

echo [ORQUESTADOR] Ejecutando: %CMD_TO_RUN%
echo [ORQUESTADOR] Agente: %AGENT_NAME%
echo.

:: Ejecutar el comando y capturar salida
%CMD_TO_RUN% 2>&1 | python D:\voz-cloud\tools\pipe.py "%AGENT_NAME%"

echo.
echo [ORQUESTADOR] Comando completado.
echo.