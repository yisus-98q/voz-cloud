"""Control por voz — Fase 4-5.

Intérprete de comandos simples con confirmación obligatoria para acciones.
Lista blanca: reintentar pruebas, pausar agente N, abrir terminal N.
Además, comprende preguntas sobre el estado del proyecto, resúmenes y
preferencias almacenadas en memoria SQLite persistente.
"""
import re
import threading
import time

from .classifier import classify
from .dedupe import Deduper
from .aggregator import Aggregator
from .speech_queue import queue as speech_queue
from .events_store import event_store
from .agents import agent_registry
from . import memory_store as ms

_pending = {}  # id_confirm -> (callback, ts)
_lock = threading.Lock()


ROLES_ES = {
    "Pruebas": "el agente de pruebas",
    "Correcciones": "el agente de correcciones",
    "Funciones": "el agente de funciones",
    "Seguridad": "el agente de seguridad",
}


def _nombre_agente(agent_id):
    a = agent_registry.get(agent_id)
    if not a:
        return agent_id
    role = a.get("role", "")
    return ROLES_ES.get(role, "el agente " + str(a.get("name", agent_id)))


def interpretar(texto):
    """Devuelve (respuesta, confirm_item|None, accion_ejecutar|None)."""
    t = texto.strip().lower().replace("¿", "").replace("?", "").replace("¡", "").replace("!", "")

    # Quitar palabra de activación
    t = re.sub(r"^voz\s*cloud[\s,:.-]*", "", t).strip()

    if not t:
        return "Te escucho. Di un comando después de «Voz Cloud».", None, None

    # Silenciar / activar
    if re.search(r"silencio|c[aá]llate", t):
        speech_queue.muted = True
        return "Voz silenciada.", None, None
    if re.search(r"habla otra vez|activa la voz|quita el silencio", t):
        speech_queue.muted = False
        return "Voz activada.", None, None

    # Resumen general con memoria contextual
    if re.search(r"c[aó]mo va|estado del proyecto|progreso", t):
        return _estado_proyecto(), None, None

    # Resumen de agentes
    if re.search(r"resumen de agentes|qué hacen los agentes", t):
        return _resumen_agentes(), None, None

    # Preferencias del usuario
    if re.search(r"preferencia|configuración|config", t):
        return _preferencias(), None, None

    # Tareas recientes
    if re.search(r"tareas pendientes|tareas en curso|qué tareas", t):
        return _tareas_pendientes(), None, None

    # Repetir último evento
    if re.search(r"repite", t):
        evs = event_store.list(0, 10)
        if not evs:
            return "No hay nada que repetir.", None, None
        ultimo = evs[-1]
        return "Repito: " + ultimo["text"], None, None

    # Qué pasó con agente N
    m = re.search(r"qu[eé] pas[oó] con (?:el |la )?agente (\d)", t)
    if m:
        ag = agent_registry.get("a" + m[1])
        if ag:
            return ag["name"] + " (" + ag["role"] + "): " + ag["last"], None, None
        return "No existe ese agente.", None, None

    # Reintentar pruebas
    if re.search(r"reintentar pruebas", t):
        c = _ask_confirm("¿Confirmas reintentar las pruebas del Agente 1?", lambda: _reintentar_pruebas())
        return "Necesito tu confirmación.", c, None

    # Pausar agente N
    m = re.search(r"pausar agente (\d)", t)
    if m:
        ag = agent_registry.get("a" + m[1])
        if not ag:
            return "No existe ese agente.", None, None
        c = _ask_confirm("¿Confirmas pausar a " + ag["name"] + "?", lambda: _pausar_agente("a" + m[1]))
        return "Necesito tu confirmación.", c, None

    # Abrir terminal N
    m = re.search(r"abrir terminal (\d)", t)
    if m:
        ag = agent_registry.get("a" + m[1])
        if not ag:
            return "No existe ese agente.", None, None
        c = _ask_confirm("¿Confirmas abrir la terminal de " + ag["name"] + "?", lambda: "Abriendo terminal de " + ag["name"] + ".")
        return "Necesito tu confirmación.", c, None

    return "No tengo esa acción autorizada.", None, None


def _estado_proyecto():
    """Devuelve un estado resumido del proyecto usando memoria SQLite y agentes."""
    tasks = ms.get_tasks()
    events = ms.get_last_events(limit=20)
    agents = agent_registry.list()

    # Contar estados de agentes
    w = [a for a in agents if a["state"] == "waiting"]
    f = [a for a in agents if a["state"] == "failed"]
    d = [a for a in agents if a["state"] == "done"]
    k = [a for a in agents if a["state"] == "working"]

    parts = []
    if w:
        parts.append("Atención: " + " y ".join(a["name"] for a in w) + " necesita intervención")
    if f:
        parts.append(" y ".join(a["name"] for a in f) + " falló")
    if d:
        parts.append(" y ".join(a["name"] for a in d) + " terminó")
    if k:
        parts.append(str(len(k)) + " agente(s) trabajando")

    base = ". ".join(parts) or "Todo en calma"

    # Añadir información de tareas recientes de SQLite si hay
    recent_tasks = [t for t in tasks if t["state"] in ("working", "waiting")][:5]
    if recent_tasks:
        base += ". Tareas recientes: " + "; ".join(
            t["task_name"] + " (" + t["state"] + ")" for t in recent_tasks
        )

    return base + "."


def _resumen_agentes():
    """Devuelve un resumen de los agentes actuales."""
    agents = agent_registry.list()
    w = [a for a in agents if a["state"] == "waiting"]
    f = [a for a in agents if a["state"] == "failed"]
    d = [a for a in agents if a["state"] == "done"]
    k = [a for a in agents if a["state"] == "working"]

    parts = []
    if w:
        parts.append("Atención: " + " y ".join(a["name"] for a in w) + " necesita intervención")
    if f:
        parts.append(" y ".join(a["name"] for a in f) + " falló")
    if d:
        parts.append(" y ".join(a["name"] for a in d) + " terminó")
    if k:
        parts.append(str(len(k)) + " agente(s) trabajando")

    return ". ".join(parts) or "Todo en calma." + "."


def _preferencias():
    """Recupera preferencias del usuario desde memoria SQLite."""
    try:
        levels = ms.get_preference("levels", "")
        if levels:
            return "Tus niveles preferidos son: " + levels
        return "No hay preferencias de nivel guardadas."
    except Exception:
        return "No puedo acceder a las preferencias ahora."


def _tareas_pendientes():
    """Devuelve tareas que están working o waiting desde la memoria SQLite."""
    try:
        tasks = ms.get_tasks(state="working")
        waiting = ms.get_tasks(state="waiting")
        all_tasks = tasks + waiting
        if not all_tasks:
            return "No hay tareas pendientes en este momento."
        parts = []
        for t in all_tasks[:5]:
            parts.append(t["task_name"] + " (" + t["state"] + ")" if t["task_name"] else t["state"])
        return "Tareas recientes: " + "; ".join(parts) + "."
    except Exception:
        return "No puedo recuperar las tareas ahora."


def confirmar(id: str, accept: bool):
    """Procesa la confirmación de un comando de voz."""
    if accept:
        return f"Comando confirmado (ID: {id})"
    else:
        return f"Comando cancelado (ID: {id})"