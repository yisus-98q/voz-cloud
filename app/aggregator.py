import threading
from .events import Event, Level


class Aggregator:
    def __init__(self, queue, quiet=2.0):
        self.queue = queue
        self.quiet = quiet
        self.buf: dict[str, list[Event]] = {}
        self.timers: dict[str, threading.Timer] = {}
        self.lock = threading.Lock()

    def add(self, ev: Event):
        if ev.level >= Level.ERROR:
            self.queue.put(ev)
            return
        with self.lock:
            self.buf.setdefault(ev.agent, []).append(ev)
            if t := self.timers.get(ev.agent):
                t.cancel()
            t = threading.Timer(self.quiet, self._flush, args=(ev.agent,))
            self.timers[ev.agent] = t
            t.start()

    def _flush(self, agent: str):
        with self.lock:
            evs = self.buf.pop(agent, [])
            self.timers.pop(agent, None)
        if not evs:
            return
        top = max(evs, key=lambda e: (e.level, e.ts))
        if len(evs) > 1:
            top = Event(
                agent,
                top.level,
                f"{top.text}. Más {len(evs)-1} avisos",
                top.raw,
            )
        self.queue.put(top)
