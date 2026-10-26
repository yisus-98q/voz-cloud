#!/usr/bin/env python
import os
import subprocess
import time

# Clear any cached app modules from sys.modules
for mod in list(__import__('sys').modules.keys()):
    if mod.startswith('app'):
        del __import__('sys').modules[mod]

# Kill any existing uvicorn processes using tasklist and taskkill
import os
os.system('taskkill /F /IM uvicorn.exe 2>nul')

# Start new uvicorn server
print("Iniciando uvicorn en puerto 8080...")
proc = subprocess.Popen(
    ['python', '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8080'],
    cwd='D:\\voz-cloud',
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

# Wait a moment for server to start
time.sleep(3)

# Check if process is still running
if proc.poll() is None:
    print("Servidor uvicorn iniciado (PID: {})".format(proc.pid))
else:
    stderr = proc.stderr.read().decode('utf-8', errors='replace')
    print("Error al iniciar servidor: {}".format(stderr))