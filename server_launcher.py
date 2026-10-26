@echo off
cd D:\voz-cloud
title Voz Cloud Server
:loop
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 >nul 2>&1
echo Server intentando iniciar...
ping -n 3 127.0.0.1 >nul
echo.
echo Probando endpoints...
python test_endpoints.py
echo.
echo Reintentando en 5 segundos...
ping -n 5 127.0.0.1 >nul
goto loop