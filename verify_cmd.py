import subprocess, time, json, urllib.request, urllib.error

# Start server (if not already running)
proc = subprocess.Popen(
    ['python', '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8080'],
    cwd='D:\\voz-cloud',
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
time.sleep(3)

# Test commands
base = 'http://127.0.0.1:8080'
tests = [
    ('cuánto avanza el proyecto', {'text': 'cuánto avanza el proyecto'}),
    ('reintentar pruebas', {'command': 'reintentar pruebas'}),
    ('resumen de agentes', {'text': 'resumen de agentes'}),
]

print("Probar endpoint POST /command:")
print("=" * 50)
for text, data in tests:
    try:
        post_data = json.dumps(data).encode()
        req = urllib.request.Request(base + '/command', data=post_data, headers={'Content-Type': 'application/json'})
        r = urllib.request.urlopen(req, timeout=5)
        result = json.loads(r.read())
        print(f'texto: "{text}"')
        print(f'  status: {r.status}')
        print(f'  response: {result.get("response", result.get("reply", result.get("message", "N/A")))}')
        print()
    except Exception as e:
        print(f'texto: "{text}"')
        print(f'  Error: {e}')
        print()

# Kill server
proc.terminate()
try:
    proc.wait(timeout=3)
except:
    proc.kill()
print("Servidor detenido")