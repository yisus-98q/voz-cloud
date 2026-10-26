from dataclasses import dataclass, field
from enum import IntEnum
import time


class Level(IntEnum):
    INFO = 0
    SUCCESS = 1
    WARNING = 2
    ERROR = 3
    ACTION = 4  # requiere intervención


@dataclass
class Event:
    agent: str
    level: Level
    text: str
    raw: str
    ts: float = field(default_factory=time.time)
