"""Orquestador de agentes — Voz Cloud.

Gestiona múltiples agentes que se comunican entre sí y ayudan al usuario.
El orquestador es el coordinador central; los agentes son workers que
ejecutan comandos y reportan resultados.

Uso:
  from app.orchestrator import orchestrator
  orchestrator.register_agent("agente-1", "Pruebas")
  orchestrator.dispatch("agente-1", "pytest tests/")
"""
import threading
import time
import subprocess
import json
import urllib.request
import urllib.error
import base64
import os

from .events_store import event_store
from .agents import agent_registry

# Configuración OpenCode
OC_BASE = "http://127.0.0.1:45278"
OC_SERVICE_PATH = r"C:\Users\miler\.config\opencode\service.json"


class CommandQueue:
    """Cola de comandos para los agentes."""

    def __init__(self):
        self.commands = []  # lista de {id, agent, command, status, result}
        self.lock = threading.Lock()
        self._counter = 0

    def add(self, agent: str, command: str) -> int:
        with self.lock:
            self._counter += 1
            cmd_id = self._counter
            self.commands.append({
                "id": cmd_id,
                "agent": agent,
                "command": command,
                "status": "pending",
                "result": None,
                "ts": time.time(),
            })
            return cmd_id

    def get_pending(self, agent: str = None):
        with self.lock:
            result = [c for c in self.commands if c["status"] == "pending"]
            if agent:
                result = [c for c in result if c["agent"] == agent]
            return result

    def update(self, cmd_id: int, status: str, result=None):
        with self.lock:
            for c in self.commands:
                if c["id"] == cmd_id:
                    c["status"] = status
                    c["result"] = result
                    return True
            return False

    def list_all(self):
        with self.lock:
            return [dict(c) for c in self.commands]


class Orchestrator:
    """Orquestador central de agentes."""

    def __init__(self):
        self.command_queue = CommandQueue()
        self.agents = {}  # id -> {name, role, status, last_command, last_result}
        self.lock = threading.Lock()
        self._running = True
        self._worker_thread = None
        self._start_worker()

    def _start_worker(self):
        self._worker_thread = threading.Thread(target=self._worker_loop, daemon=True)
        self._worker_thread.start()

    def _worker_loop(self):
        """Bucle del orquestador: ejecuta comandos pendientes."""
        while self._running:
            try:
                pending = self.command_queue.get_pending()
                for cmd in pending:
                    self.command_queue.update(cmd["id"], "running")
                    result = self._execute_command(cmd["command"])
                    self.command_queue.update(cmd["id"], "done", result)
                    # Notificar a Voz Cloud
                    self._notify_voz_cloud(cmd["agent"], f"Comando completado: {cmd['command'][:60]}")
                    # Actualizar agente
                    self._update_agent(cmd["agent"], "done", result)
            except Exception as e:
                print(f"[Orquestador] Error: {e}")
            time.sleep(0.5)

    def _execute_command(self, command: str) -> str:
        """Ejecuta un comando en CMD y devuelve el resultado."""
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=120,
                encoding="utf-8",
                errors="replace",
            )
            output = result.stdout + result.stderr
            if not output.strip():
                output = f"(exit code {result.returncode})"
            return output[:2000]  # Limitar tamaño
        except subprocess.TimeoutExpired:
            return "TIMEOUT: El comando tardó más de 120 segundos"
        except Exception as e:
            return f"ERROR: {str(e)}"

    def _get_oc_auth(self):
        """Lee la contraseña de OpenCode."""
        try:
            with open(OC_SERVICE_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            password = data.get("password", "")
            token = base64.b64encode(f"opencode:{password}".encode("utf-8")).decode("utf-8")
            return f"Basic {token}"
        except Exception:
            return None

    def _notify_voz_cloud(self, agent: str, text: str):
        """Envía un evento a Voz Cloud."""
        try:
            import urllib.request
            payload = json.dumps({"agent": agent, "line": text}).encode("utf-8")
            req = urllib.request.Request(
                "http://127.0.0.1:8000/ingest",
                data=payload,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=2)
        except Exception:
            pass

    def _update_agent(self, agent_id: str, status: str, result=None):
        """Actualiza el estado de un agente."""
        with self.lock:
            if agent_id in self.agents:
                self.agents[agent_id]["status"] = status
                self.agents[agent_id]["last_result"] = result
                self.agents[agent_id]["last_activity"] = time.time()
                # También actualizar en agent_registry de Voz Cloud
                try:
                    agent_registry.update_state(agent_id, status, (result or "")[:80])
                except Exception:
                    pass

    def register_agent(self, agent_id: str, name: str, role: str = "Worker"):
        """Registra un nuevo agente en el orquestador."""
        with self.lock:
            self.agents[agent_id] = {
                "id": agent_id,
                "name": name,
                "role": role,
                "status": "idle",
                "last_command": None,
                "last_result": None,
                "last_activity": time.time(),
            }
        # Registrar en Voz Cloud
        try:
            agent_registry.upsert(agent_id, name, role)
        except Exception:
            pass
        self._notify_voz_cloud(agent_id, f"Agente {name} registrado como {role}")
        return self.agents[agent_id]

    def dispatch(self, agent: str, command: str) -> int:
        """Envía un comando a un agente específico."""
        if agent not in self.agents:
            self.register_agent(agent, agent, "Worker")
        cmd_id = self.command_queue.add(agent, command)
        self._update_agent(agent, "working")
        return cmd_id

    def dispatch_all(self, command: str) -> list:
        """Envía un comando a todos los agentes registrados."""
        results = []
        for agent_id in self.agents:
            cmd_id = self.dispatch(agent_id, command)
            results.append((agent_id, cmd_id))
        return results

    def get_status(self):
        """Devuelve el estado completo del orquestador."""
        with self.lock:
            return {
                "agents": [
                    {
                        "id": a["id"],
                        "name": a["name"],
                        "role": a["role"],
                        "status": a["status"],
                        "last_command": a["last_command"],
                        "last_result": (a["last_result"] or "")[:200],
                        "last_activity": a["last_activity"],
                    }
                    for a in self.agents.values()
                ],
                "pending_commands": len(self.command_queue.get_pending()),
                "total_commands": len(self.command_queue.list_all()),
            }

    def stop(self):
        self._running = False
        if self._worker_thread:
            self._worker_thread.join(timeout=3)


# Instancia global del orquestador
orchestrator = Orchestrator()


def auto_register_default_agents():
    """Registra los 4 agentes por defecto."""
    orchestrator.register_agent("a1", "Agente 1", "Pruebas")
    orchestrator.register_agent("a2", "Agente 2", "Correcciones")
    orchestrator.register_agent("a3", "Agente 3", "Funciones")
    orchestrator.register_agent("a4", "Agente 4", "Seguridad")


# Registrar agentes por defecto al importar
auto_register_default_agents()
