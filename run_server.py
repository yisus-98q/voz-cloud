import subprocess, sys, time, os, json, urllib.request, urllib.error

os.chdir('D:\\voz-cloud')

# Start server - run in background with nohup equivalent
proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8080'],
    stdout=open('server.log', 'w'), 
    stderr=open('server_error.log', 'w'),
    creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, 'CREATE_NEW_CONSOLE') else 0
)

# Wait for startup
time.sleep(3)

# Check if process is alive
if proc.poll() is not None:
    print("ERROR: Server process died immediately")
    with open('server.log') as f:
        print(f"Server log: {f.read()}")
    with open('server_error.log') as f:
        print(f"Server error: {f.read()}")
    sys.exit(1)

print(f"Server PID: {proc.pid}")

base = 'http://127.0.0.1:8080'
print(f"\nTesting endpoints at {base}:\n")

# Test endpoints
endpoints = [
    ("GET /health", "GET", f"{base}/health"),
    ("GET /status", "GET", f"{base}/status"),
    ("GET /agents", "GET", f"{base}/agents"),
    ("POST /command", "POST", f"{base}/command", {"text": "cuánto avanza el proyecto"}),
]

for ep in endpoints:
    name = ep[0]
    method = ep[1]
    url = ep[2]
    data = ep[3] if len(ep) > 3 else None
    
    try:
        if data:
            post_data = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(url, data=post_data, headers={'Content-Type': 'application/json'})
            r = urllib.request.urlopen(req, timeout=5)
            result = json.loads(r.read())
        else:
            r = urllib.request.urlopen(url, timeout=5)
            result = json.loads(r.read())
        print(f"  ✅ {name}: {r.status} - {str(result)[:100]}")
    except Exception as e:
        print(f"  ❌ {name}: Error - {e}")

print("\nServidor corriendo. Presiona Ctrl+C para detenerlo.\n")

# Keep alive
try:
    while True:
        time.sleep(5)
        # Verify server still alive
        if proc.poll() is not None:
            print("⚠️ Server process died unexpectedly")
            break
except KeyboardInterrupt:
    print("\nDeteniendo servidor...")
    proc.terminate()
    proc.wait(timeout=5)
    print("Servidor detenido")