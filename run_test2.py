import subprocess, time, json, urllib.request, urllib.error

# Start server
proc = subprocess.Popen(
    ['python', '-m', 'uvicorn', 'app.main:app', '--host', '127.0.0.1', '--port', '8080'],
    cwd='D:\\voz-cloud',
    stdout=subprocess.PIPE, stderr=subprocess.PIPE
)
time.sleep(3)

# Test commands
base = 'http://127.0.0.1:8080'
tests = [
    ('cuánto avanza el proyecto', '/command', {'text': 'cuánto avanza el proyecto'}),
    ('reintentar pruebas', '/command', {'command': 'reintentar pruebas'}),
    ('estado del proyecto', '/command', {'text': 'estado del proyecto'}),
    ('resumen de agentes', '/command', {'text': 'resumen de agentes'}),
]

for text, ep, data in tests:
    try:
        post_data = json.dumps(data).encode()
        req = urllib.request.Request(base + ep, data=post_data, headers={'Content-Type': 'application/json'})
        r = urllib.request.urlopen(req, timeout=5)
        result = json.loads(r.read())
        print(f'"{text}": {r.status} - {str(result)[:150]}')
    except Exception as e:
        print(f'"{text}": Error - {e}')

# Wait a bit then kill
time.sleep(2)
proc.terminate()
try:
    proc.wait(timeout=3)
except:
    proc.kill()
print('Done')