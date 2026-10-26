"""Almacenamiento de eventos en memoria con IDs autoincrementales — Fase 3."""
import time


class EventStore:
    def __init__(self):
        self.events = []
        self._next_id = 1
        self._lock = __import__("threading").Lock()

    def add(self, agent, level, text, raw=None):
        with self._lock:
            ev = {
                "id": self._next_id,
                "ts": int(time.time() * 1000),
                "agent": agent,
                "level": level,
                "text": text,
                "raw": raw or text,
            }
            self._next_id += 1
            self.events.append(ev)
            if len(self.events) > 1000:
                self.events = self.events[-1000:]
            return ev

    def list(self, since_id=0, limit=200):
        with self._lock:
            result = [e for e in self.events if e["id"] > since_id]
            return result[-limit:]

    def last_id(self):
        with self._lock:
            return self.events[-1]["id"] if self.events else 0


event_store = EventStore()
