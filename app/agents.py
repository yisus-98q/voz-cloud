"""Registro de agentes — Fase 4.

Estados: idle, working, done, failed, waiting.
Alimentado por el clasificador (nivel ERROR -> failed, ACTION -> waiting, etc.)
"""
import threading
import time


ROLES_DEFAULT = {
    "a1": ("Agente 1", "Pruebas"),
    "a2": ("Agente 2", "Correcciones"),
    "a3": ("Agente 3", "Funciones"),
    "a4": ("Agente 4", "Seguridad"),
}


class AgentRegistry:
    def __init__(self):
        self.agents = {}
        self._lock = threading.Lock()
        for aid, (name, role) in ROLES_DEFAULT.items():
            self.agents[aid] = {
                "id": aid,
                "name": name,
                "role": role,
                "state": "idle",
                "last": "Esperando tarea",
                "ts": time.time(),
            }

    def upsert(self, agent_id, name=None, role=None):
        with self._lock:
            if agent_id not in self.agents:
                self.agents[agent_id] = {
                    "id": agent_id,
                    "name": name or agent_id,
                    "role": role or "Desconocido",
                    "state": "idle",
                    "last": "Conectado",
                    "ts": time.time(),
                }
            if name:
                self.agents[agent_id]["name"] = name
            if role:
                self.agents[agent_id]["role"] = role
            return self.agents[agent_id]

    def update_state(self, agent_id, state, last=None):
        with self._lock:
            if agent_id in self.agents:
                self.agents[agent_id]["state"] = state
                if last:
                    self.agents[agent_id]["last"] = last
                self.agents[agent_id]["ts"] = time.time()
                return self.agents[agent_id]
            return None

    def list(self):
        with self._lock:
            now = time.time()
            result = []
            for a in self.agents.values():
                a2 = dict(a)
                if a2["state"] not in ("waiting", "failed") and now - a2["ts"] > 20:
                    a2["state"] = "idle"
                    a2["last"] = "Ocioso"
                result.append(a2)
            return result

    def get(self, agent_id):
        with self._lock:
            return dict(self.agents.get(agent_id, {}))


agent_registry = AgentRegistry()
