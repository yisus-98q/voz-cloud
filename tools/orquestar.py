"""Orquestador de comandos para Voz Cloud.

Permite enviar comandos a agentes específicos y recibir resultados.
Los agentes se comunican entre sí a través del orquestador.

Uso:
  python orquestar.py --status                    # Ver estado de todos los agentes
  python orquestar.py --dispatch "agente-1" "dir C:\"  # Enviar comando a un agente
  python orquestar.py --dispatch-all "pytest"      # Enviar a todos los agentes
  python orquestar.py --commands                   # Ver historial de comandos
  python orquestar.py --listen                     # Modo escucha continua
"""
import argparse
import json
import time
import urllib.request
import urllib.error
import subprocess
import sys

VOZ_URL = "http://127.0.0.1:8000"


def api_call(method, path, body=None):
    url = VOZ_URL + path
    data = None
    headers = {"Content-Type": "application/json"}
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode("utf-8")), None
    except urllib.error.HTTPError as e:
        try:
            return json.loads(e.read().decode("utf-8")), f"HTTP {e.code}"
        except Exception:
            return None, f"HTTP {e.code}"
    except Exception as e:
        return None, str(e)


def cmd_status():
    data, err = api_call("GET", "/orchestrator/status")
    if err:
        print(f"Error: {err}")
        return
    print("=" * 60)
    print("  ESTADO DE AGENTES")
    print("=" * 60)
    for a in data.get("agents", []):
        status_icon = {"idle": "[IDLE]", "working": "[WORK]", "done": "[DONE]", "failed": "[FAIL]", "waiting": "[WAIT]"}.get(a["status"], "[?]")
        print(f"  {status_icon} {a['name']} ({a['role']}) — {a['status']}")
        if a.get("last_result"):
            print(f"     Último: {a['last_result'][:80]}")
    print()
    print(f"  Comandos pendientes: {data.get('pending_commands', 0)}")
    print(f"  Total comandos: {data.get('total_commands', 0)}")
    print("=" * 60)


def cmd_dispatch(agent, command):
    data, err = api_call("POST", "/orchestrator/dispatch", {"agent": agent, "command": command})
    if err:
        print(f"Error: {err}")
        return
    print(f"Comando #{data['command_id']} enviado a {agent}: {command}")
    # Esperar resultado
    print("Esperando resultado...")
    for _ in range(60):
        time.sleep(1)
        cmds, _ = api_call("GET", "/orchestrator/commands")
        if cmds:
            for c in cmds["commands"]:
                if c["id"] == data["command_id"] and c["status"] == "done":
                    print(f"\nResultado:\n{c['result']}")
                    return
    print("Timeout esperando resultado")


def cmd_dispatch_all(command):
    data, err = api_call("POST", "/orchestrator/dispatch-all", {"command": command})
    if err:
        print(f"Error: {err}")
        return
    print(f"Comando enviado a {len(data['dispatched'])} agentes:")
    for agent, cmd_id in data["dispatched"]:
        print(f"  - {agent}: #{cmd_id}")


def cmd_commands():
    data, err = api_call("GET", "/orchestrator/commands")
    if err:
        print(f"Error: {err}")
        return
    print("=" * 60)
    print("  HISTORIAL DE COMANDOS")
    print("=" * 60)
    for c in data.get("commands", []):
        status_icon = {"pending": "⏳", "running": "🔄", "done": "✅"}.get(c["status"], "❓")
        print(f"  {status_icon} #{c['id']} [{c['agent']}] {c['command']}")
        if c.get("result"):
            print(f"     Resultado: {c['result'][:100]}")
    print("=" * 60)


def cmd_listen():
    print("Modo escucha continua. Presiona Ctrl+C para salir.")
    print("Los comandos pendientes se ejecutarán automáticamente.")
    print()
    try:
        while True:
            time.sleep(2)
            cmds, _ = api_call("GET", "/orchestrator/commands")
            if cmds:
                pending = [c for c in cmds["commands"] if c["status"] == "pending"]
                if pending:
                    print(f"[{time.strftime('%H:%M:%S')}] {len(pending)} comandos pendientes...")
    except KeyboardInterrupt:
        print("\nDeteniendo escucha...")


def main():
    parser = argparse.ArgumentParser(description="Orquestador de Voz Cloud")
    parser.add_argument("--status", action="store_true", help="Ver estado de agentes")
    parser.add_argument("--dispatch", nargs=2, metavar=("AGENTE", "COMANDO"), help="Enviar comando a un agente")
    parser.add_argument("--dispatch-all", metavar="COMANDO", help="Enviar comando a todos los agentes")
    parser.add_argument("--commands", action="store_true", help="Ver historial de comandos")
    parser.add_argument("--listen", action="store_true", help="Modo escucha continua")
    args = parser.parse_args()

    if args.status:
        cmd_status()
    elif args.dispatch:
        cmd_dispatch(args.dispatch[0], args.dispatch[1])
    elif args.dispatch_all:
        cmd_dispatch_all(args.dispatch_all)
    elif args.commands:
        cmd_commands()
    elif args.listen:
        cmd_listen()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
