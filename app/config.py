"""Configuración persistente — Fase 3."""
import json
import os
import threading

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "config.json")
CONFIG_PATH = os.path.abspath(CONFIG_PATH)

DEFAULT = {
    "levels": ["SUCCESS", "WARNING", "ERROR", "ACTION"],
    "quiet_start": "22:00",
    "quiet_end": "07:00",
    "dedupe_s": 30,
    "queue_max": 8,
    "queue_age_s": 60,
}

_lock = threading.Lock()


def load():
    if os.path.exists(CONFIG_PATH):
        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            return {**DEFAULT, **data}
        except Exception:
            pass
    return dict(DEFAULT)


def save(cfg):
    with _lock:
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    return dict(cfg)


config = load()
