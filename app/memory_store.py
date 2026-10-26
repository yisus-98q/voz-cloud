"""Memoria persistente en SQLite para Voz Cloud — Fase 3.

Gestiona el historial de eventos, tareas, comandos, preferencias y
resúmenes de conversación en una base de datos SQLite local.

La base de datos se guarda en: data/voz_cloud.db (ruta estable, independiente
del directorio de trabajo). Todas las conexiones usan row_factory para
devolver diccionados y tienen timeouts cortos para evitar bloqueos.
"""

import sqlite3
import os
import time
import threading
from datetime import datetime, timezone

# Ruta de la base de datos — carpeta local persistente
DB_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data")
DB_PATH = os.path.abspath(os.path.join(DB_DIR, "voz_cloud.db"))

# Lock para operaciones concurrentes de escritura
_db_lock = threading.Lock()

# --- Helpers internos ---

def _connect():
    """Devuelve una conexión a la base de datos con row_factory y timeout."""
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    return conn


def _ensure_conn():
    """Crea la carpeta y la base de datos si no existen."""
    os.makedirs(DB_DIR, exist_ok=True)
    conn = _connect()
    _create_tables(conn)
    conn.close()


def _create_tables(conn):
    """Crea todas las tablas si no existen. Usa una sola transacción."""
    cursor = conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA synchronous=NORMAL")
    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            level TEXT NOT NULL,
            agent TEXT,
            type TEXT,
            description TEXT,
            raw TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_events_agent ON events(agent, ts);
        CREATE INDEX IF NOT EXISTS idx_events_level ON events(level, ts);

        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            agent_id TEXT NOT NULL,
            task_name TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'idle',
            started_at INTEGER,
            updated_at INTEGER,
            completed_at INTEGER,
            result TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_tasks_agent ON tasks(agent_id, state);
        CREATE INDEX IF NOT EXISTS idx_tasks_state ON tasks(state);

        CREATE TABLE IF NOT EXISTS commands (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            origin TEXT,
            text TEXT NOT NULL,
            state TEXT NOT NULL DEFAULT 'pending',
            result TEXT
        );
        CREATE INDEX IF NOT EXISTS idx_commands_origin ON commands(origin);

        CREATE TABLE IF NOT EXISTS preferences (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at INTEGER NOT NULL DEFAULT (CAST((strftime('%s','now')) AS INTEGER))
        );

        CREATE TABLE IF NOT EXISTS conversation_summaries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts INTEGER NOT NULL,
            summary TEXT,
            metadata TEXT
        );
    """)
    conn.commit()


# --- Inicialización automática al importar ---

_ensure_conn()


# --- Eventos ---

def add_event(agent: str, level: str, description: str, raw: str = None, event_type: str = None):
    """Inserta un nuevo evento. Retorna el id asignado."""
    with _db_lock:
        conn = _connect()
        try:
            ts = int(time.time() * 1000)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO events (ts, level, agent, type, description, raw) VALUES (?, ?, ?, ?, ?, ?)",
                (ts, level, agent, event_type, description, raw),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()


def get_events(since_id: int = 0, limit: int = 200, agent: str = None, level: str = None):
    """Obtiene eventos paginados y opcionalmente filtrados."""
    with _db_lock:
        conn = _connect()
        try:
            cursor = conn.cursor()
            query = "SELECT id, ts, level, agent, type, description, raw FROM events WHERE id > ?"
            params = [since_id]
            if agent:
                query += " AND agent = ?"
                params.append(agent)
            if level:
                query += " AND level = ?"
                params.append(level)
            query += " ORDER BY id DESC LIMIT ?"
            params.append(limit)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            # Invertir para orden cronológico ascendente
            rows = list(reversed(rows))
            return [dict(r) for r in rows]
        finally:
            conn.close()


def get_last_events(limit: int = 20):
    """Obtiene los últimos eventos (usado por el reporte de salud)."""
    with _db_lock:
        conn = _connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, ts, level, agent, type, description, raw FROM events ORDER BY id DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
            return [dict(r) for r in reversed(rows)]
        finally:
            conn.close()


# --- Tareas ---

def upsert_task(agent_id: str, task_name: str, state: str, result: str = None):
    """Actualiza o inserta el estado actual de una tarea."""
    with _db_lock:
        conn = _connect()
        try:
            now = int(time.time())
            cursor = conn.cursor()
            # Buscar si ya existe una tarea activa para este agente
            cursor.execute(
                "SELECT id, started_at FROM tasks WHERE agent_id = ? AND state != 'done' AND state != 'failed'",
                (agent_id,),
            )
            row = cursor.fetchone()
            if row:
                # Actualizar existente
                cursor.execute(
                    "UPDATE tasks SET state = ?, updated_at = ?, result = ?, completed_at = ? WHERE id = ?",
                    (state, now, result, now if state in ('done', 'failed') else None, row[0]),
                )
            else:
                # Insertar nueva
                cursor.execute(
                    "INSERT INTO tasks (agent_id, task_name, state, started_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                    (agent_id, task_name, state, now, now),
                )
            conn.commit()
        finally:
            conn.close()


def get_tasks(agent_id: str = None, state: str = None):
    """Obtiene tareas, opcionalmente filtradas por agente o estado."""
    with _db_lock:
        conn = _connect()
        try:
            cursor = conn.cursor()
            query = "SELECT id, agent_id, task_name, state, started_at, updated_at, completed_at, result FROM tasks WHERE 1=1"
            params = []
            if agent_id:
                query += " AND agent_id = ?"
                params.append(agent_id)
            if state:
                query += " AND state = ?"
                params.append(state)
            query += " ORDER BY updated_at DESC"
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


def get_interrupted_tasks():
    """Devuelve tareas que estaban working o waiting al cerrar el programa."""
    with _db_lock:
        conn = _connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, agent_id, task_name, state, started_at, updated_at, result "
                "FROM tasks WHERE state IN ('working', 'waiting') AND completed_at IS NULL"
            )
            rows = cursor.fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()


# --- Comandos ---

def add_command(origin: str, text: str, state: str = "pending", result: str = None):
    """Inserta un nuevo comando. Retorna el id asignado."""
    with _db_lock:
        conn = _connect()
        try:
            ts = int(time.time() * 1000)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO commands (ts, origin, text, state, result) VALUES (?, ?, ?, ?, ?)",
                (ts, origin, text, state, result),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()


def get_commands(origin: str = None, limit: int = 100):
    """Obtiene comandos, opcionalmente filtrados por origen."""
    with _db_lock:
        conn = _connect()
        try:
            cursor = conn.cursor()
            query = "SELECT id, ts, origin, text, state, result FROM commands WHERE 1=1"
            params = []
            if origin:
                query += " AND origin = ?"
                params.append(origin)
            query += " ORDER BY ts DESC LIMIT ?"
            params.append(limit)
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [dict(r) for r in reversed(rows)]
        finally:
            conn.close()


# --- Preferencias ---

def get_preference(key: str, default: str = None):
    """Obtiene una preferencia por clave."""
    with _db_lock:
        conn = _connect()
        try:
            cursor = conn.cursor()
            cursor.execute("SELECT value FROM preferences WHERE key = ?", (key,))
            row = cursor.fetchone()
            return row["value"] if row else default
        finally:
            conn.close()


def set_preference(key: str, value: str):
    """Establece o actualiza una preferencia."""
    with _db_lock:
        conn = _connect()
        try:
            now = int(time.time())
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO preferences (key, value, updated_at) VALUES (?, ?, ?) "
                "ON CONFLICT(key) DO UPDATE SET value = ?, updated_at = ?",
                (key, value, now, value, now),
            )
            conn.commit()
        finally:
            conn.close()


# --- Resúmenes de conversación ---

def add_conversation_summary(summary: str, metadata: str = None):
    """Almacena un resumen de conversación."""
    with _db_lock:
        conn = _connect()
        try:
            ts = int(time.time() * 1000)
            meta_json = metadata if metadata is None else __import__("json").dumps(metadata)
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO conversation_summaries (ts, summary, metadata) VALUES (?, ?, ?)",
                (ts, summary, meta_json),
            )
            conn.commit()
            return cursor.lastrowid
        finally:
            conn.close()


def get_recent_summaries(limit: int = 10):
    """Obtiene los resúmenes de conversación más recientes."""
    with _db_lock:
        conn = _connect()
        try:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT id, ts, summary, metadata FROM conversation_summaries ORDER BY ts DESC LIMIT ?",
                (limit,),
            )
            rows = cursor.fetchall()
            results = []
            for r in reversed(rows):
                entry = dict(r)
                try:
                    entry["metadata"] = __import__("json").loads(entry["metadata"]) if entry.get("metadata") else None
                except Exception:
                    entry["metadata"] = None
                results.append(entry)
            return results
        finally:
            conn.close()


# --- Recuperación al iniciar ---

def load_persistent_state():
    """Carga el historial persistente al iniciar la aplicación.

    Identifica tareas que estaban working o waiting cuando se cerró
    el programa y las marca como interrumpidas.
    """
    with _db_lock:
        conn = _connect()
        try:
            # Marcar tareas working/waiting sin completar_at como interrumpidas
            now = int(time.time())
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE tasks SET state = 'interrupted', updated_at = ?, result = 'Sesión terminada inesperadamente' "
                "WHERE state IN ('working', 'waiting') AND completed_at IS NULL",
                (now,),
            )
            conn.commit()

            # Recuperar último estado de tareas para display
            cursor.execute(
                "SELECT agent_id, task_name, state, started_at, updated_at, result "
                "FROM tasks ORDER BY updated_at DESC LIMIT 20"
            )
            tasks = [dict(r) for r in cursor.fetchall()]

            # Recuperar últimos eventos
            cursor.execute(
                "SELECT id, ts, level, agent, type, description, raw FROM events ORDER BY id DESC LIMIT 50"
            )
            events = [dict(r) for r in cursor.fetchall()]

            # Recuperar preferencias
            cursor.execute("SELECT key, value FROM preferences")
            preferences = {row["key"]: row["value"] for row in cursor.fetchall()}

            # Recuperar comandos recientes
            cursor.execute(
                "SELECT id, ts, origin, text, state, result FROM commands ORDER BY ts DESC LIMIT 20"
            )
            commands = [dict(r) for r in cursor.fetchall()]

            return {
                "tasks": tasks,
                "events": events,
                "preferences": preferences,
                "commands": commands,
            }
        finally:
            conn.close()


# --- Exportación y limpieza ---

def export_data(format_type: str = "json"):
    """Exporta los datos registrados en el formato especificado."""
    with _db_lock:
        conn = _connect()
        try:
            cursor = conn.cursor()
            if format_type == "json":
                # Events
                cursor.execute("SELECT id, ts, level, agent, type, description, raw FROM events ORDER BY id")
                events = [dict(r) for r in cursor.fetchall()]
                # Tasks
                cursor.execute("SELECT id, agent_id, task_name, state, started_at, updated_at, completed_at, result FROM tasks ORDER BY id")
                tasks = [dict(r) for r in cursor.fetchall()]
                # Commands
                cursor.execute("SELECT id, ts, origin, text, state, result FROM commands ORDER BY id")
                commands = [dict(r) for r in cursor.fetchall()]
                # Preferences
                cursor.execute("SELECT key, value FROM preferences")
                preferences = dict(cursor.fetchall())
                # Conversation summaries
                cursor.execute("SELECT id, ts, summary, metadata FROM conversation_summaries ORDER BY id")
                summaries = [dict(r) for r in cursor.fetchall()]
                return {
                    "db_path": DB_PATH,
                    "events": events,
                    "tasks": tasks,
                    "commands": commands,
                    "preferences": preferences,
                    "conversation_summaries": summaries,
                    "exported_at": int(time.time() * 1000),
                }
            else:
                return {"error": f"Formato '{format_type}' no soportado. Use 'json'."}
        finally:
            conn.close()


def clear_all_data(confirm: bool = False):
    """Limpia todos los datos de la base de datos. Requiere confirmación explícita."""
    if not confirm:
        return {"error": "Limpieza cancelada: falta confirmación explícita"}
    with _db_lock:
        conn = _connect()
        try:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM events")
            cursor.execute("DELETE FROM tasks")
            cursor.execute("DELETE FROM commands")
            cursor.execute("DELETE FROM conversation_summaries")
            cursor.execute("DELETE FROM preferences")
            conn.commit()
            return {"status": "ok", "message": "Todos los datos han sido limpiados"}
        finally:
            conn.close()