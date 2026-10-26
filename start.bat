@echo off
cd D:\voz-cloud
python -m uvicorn app.main:app --host 127.0.0.1 --port 8080 > server.log 2>&1
echo Server started, exit code: %errorlevel%