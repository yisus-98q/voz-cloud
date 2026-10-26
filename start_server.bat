@echo off
cd D:\voz-cloud
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 --no-reload