@echo off
:: ============================================
::  VOZ CLOUD - Iniciar todo el sistema
:: ============================================
:: Este script inicia:
:: 1. Servidor de Voz Cloud (puerto 8000)
:: 2. Abre el panel web en el navegador
:: 3. Muestra instrucciones de uso
:: ============================================

cd /d "D:\voz-cloud"

:: Verificar que el entorno virtual existe
if not exist ".venv\Scripts\python.exe" (
    echo [ERROR] No se encuentra el entorno virtual.
    echo Ejecuta primero:
    echo   cd D:\voz-cloud
    echo   python -m venv .venv
    echo   .venv\Scripts\pip install -r requirements.txt
    pause
    exit /b 1
)

:: Verificar que Piper esté instalado
if not exist "C:\piper\piper\piper.exe" (
    echo [AVISO] Piper no esta instalado en C:\piper\piper\piper.exe
    echo La voz no funcionara hasta que lo instales.
)

:: Iniciar el servidor
echo.
echo "========================================"
echo "  Iniciando Voz Cloud..."
echo "========================================"
echo.

set PIPER_EXE=C:\piper\piper\piper.exe
set PIPER_MODEL=C:\piper\piper\es_ES-davefx-medium.onnx

start /b .venv\Scripts\python.exe -m uvicorn app.main:app --port 8000 > server.log 2>&1

:: Esperar hasta 30 segundos: el modelo de voz puede hacer que el primer inicio tarde.
set /a intentos=0
:ESPERAR_SERVIDOR
curl.exe -s -f -o nul http://127.0.0.1:8000/health >nul 2>&1
if not errorlevel 1 goto SERVIDOR_LISTO
set /a intentos+=1
if %intentos% geq 30 (
    echo [ERROR] El servidor no arranco correctamente.
    echo Revisa server.log para mas detalles.
    pause
    exit /b 1
)
timeout /t 1 /nobreak >nul
goto ESPERAR_SERVIDOR

:SERVIDOR_LISTO

echo [OK] Servidor de Voz Cloud en linea en http://127.0.0.1:8000

:: Abrir el panel web
echo [INFO] Abriendo panel web...
start http://127.0.0.1:8000/

echo.
echo "========================================"
echo "  Voz Cloud esta listo!"
echo "========================================"
echo.
echo  Panel web: http://127.0.0.1:8000/
echo.
echo  Comandos utiles:
echo    python tools\orquestar.py --status
echo    python tools\orquestar.py --dispatch "agente-1" "dir C:\"
echo    python tools\orquestar.py --dispatch-all "pytest"
echo    python tools\orquestar.py --commands
echo.
echo  Integrar CMD:
echo    tu_comando.exe 2>&1 ^| python tools\pipe.py "nombre-agente"
echo.
echo  Microfono:
echo    curl -X POST http://127.0.0.1:8000/stt/on
echo    curl -X POST http://127.0.0.1:8000/stt/off
echo.
echo  Presiona Ctrl+C para detener el servidor.
echo "========================================"
echo.

:: Mantener el script corriendo
pause
