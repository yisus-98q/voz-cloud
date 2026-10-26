import re, time


class Deduper:
    def __init__(self, ttl: float = 30.0):
        self.ttl = ttl
        self.seen: dict[str, float] = {}

    @staticmethod
    def key(agent: str, text: str) -> str:
        return agent + "|" + re.sub(r"\d+", "#", text.lower())

    def allow(self, agent: str, text: str) -> bool:
        now = time.time()
        self.seen = {k: t for k, t in self.seen.items() if now - t < self.ttl}
        k = self.key(agent, text)
        if k in self.seen:
            return False
        self.seen[k] = now
        return True
