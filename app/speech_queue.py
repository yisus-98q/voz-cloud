import threading
import time
from .events import Event, Level
from .events_store import event_store
from .agents import agent_registry


class _Current:
    """Wrapper del evento actual con timestamp para el health check."""
    def __init__(self):
        self.ev = None
        self.ts = None

    @property
    def text(self):
        if self.ev:
            return SpeechQueue.say(self.ev)
        return None

    @property
    def level(self):
        return self.ev.level if self.ev else None

    def set(self, ev):
        self.ev = ev
        self.ts = time.time()
        # Registrar en el almacén de eventos
        try:
            event_store.add(ev.agent, ev.level.name, ev.text, ev.raw)
        except Exception:
            pass
        # Actualizar estado del agente según el nivel
        try:
            if ev.level == Level.ERROR:
                agent_registry.update_state(ev.agent, "failed", ev.text[:80])
            elif ev.level == Level.ACTION:
                agent_registry.update_state(ev.agent, "waiting", ev.text[:80])
            elif ev.level == Level.SUCCESS:
                agent_registry.update_state(ev.agent, "done", ev.text[:80])
            else:
                agent_registry.update_state(ev.agent, "working", ev.text[:80])
        except Exception:
            pass

    def clear(self):
        self.ev = None
        self.ts = None


class SpeechQueue:
    def __init__(self, speak, max_size=8, max_age=60.0):
        self.speak = speak
        self.max_size = max_size
        self.max_age = max_age
        self.items: list[Event] = []
        self.cv = threading.Condition()
        self.muted = False
        self.current = _Current()
        self.dropped = 0
        threading.Thread(target=self._worker, daemon=True).start()

    def put(self, ev: Event):
        with self.cv:
            self.items.append(ev)
            while len(self.items) > self.max_size:
                victim = min(self.items, key=lambda e: (e.level, e.ts))
                self.items.remove(victim)
                self.dropped += 1
            self.cv.notify()

    def _next(self) -> Event:
        with self.cv:
            while True:
                now = time.time()
                before = len(self.items)
                self.items = [
                    e
                    for e in self.items
                    if e.level == Level.ACTION or now - e.ts < self.max_age
                ]
                self.dropped += before - len(self.items)
                if self.items and not self.muted:
                    ev = max(self.items, key=lambda e: (e.level, -e.ts))
                    self.items.remove(ev)
                    return ev
                self.cv.wait(timeout=1.0)

    def _worker(self):
        while True:
            ev = self._next()
            self.current.set(ev)
            try:
                self.speak(self.say(ev))
            except Exception:
                pass
            self.current.clear()

    @staticmethod
    def say(ev: Event) -> str:
        names = {
            Level.ACTION: "Atención",
            Level.ERROR: "Error",
            Level.WARNING: "Advertencia",
            Level.SUCCESS: "Listo",
            Level.INFO: "",
        }
        return f"{names[ev.level]}: {ev.agent}. {ev.text}".strip()

    def size(self):
        with self.cv:
            return len(self.items)


from .piper_tts import speak

queue = SpeechQueue(speak)

