import subprocess, sys, time, json, urllib.request, urllib.error

# Change to project directory
import os
os.chdir('D:\\voz-cloud')

# Start server
proc = subprocess.Popen(
    [sys.executable, '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8080'],
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)

# Wait for startup
time.sleep(3)

base = 'http://127.0.0.1:8080'
results = []

def test(name, method, url, data=None):
    try:
        if data:
            post_data = json.dumps(data).encode('utf-8')
            req = urllib.request.Request(url, data=post_data, headers={'Content-Type': 'application/json'})
            r = urllib.request.urlopen(req, timeout=5)
            print(f"{name}: {r.status} {json.loads(r.read())}")
        else:
            r = urllib.request.urlopen(url, timeout=5)
            print(f"{name}: {r.status} {json.loads(r.read())}")
    except Exception as e:
        print(f"{name} Error: {e}")

# Test endpoints
test("/health", "GET", base + '/health')
test("/status", "GET", base + '/status')
test("/agents", "GET", base + '/agents')
test("/command", "POST", base + '/command', {'text': 'cuánto avanza el proyecto'})

# Wait a moment
time.sleep(1)

# Stop server
proc.terminate()
try:
    proc.wait(timeout=5)
except:
    proc.kill()
print("Server stopped")