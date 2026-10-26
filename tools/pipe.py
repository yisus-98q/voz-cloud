import sys
import requests

agent = sys.argv[1] if len(sys.argv) > 1 else "agente1"
URL = "http://127.0.0.1:8000/ingest"

for line in sys.stdin:
    sys.stdout.write(line)
    sys.stdout.flush()
    try:
        requests.post(URL, json={"agent": agent, "line": line}, timeout=0.5)
    except requests.RequestException:
        pass
