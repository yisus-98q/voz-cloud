import re
from .events import Event, Level

ANSI = re.compile(r"\x1b\[[0-9;?]*[A-Za-z]")

RULES = [
    # English patterns
    (Level.ACTION, re.compile(r"(?i)(\[y/n\]|\(y/n\)|press enter|permission|approve|waiting for (input|your)|confirm)")),
    (Level.ERROR, re.compile(r"(?i)(traceback|exception|error:|\bfailed\b|fatal|npm err|modulenotfound|cannot find)")),
    (Level.WARNING, re.compile(r"(?i)(warn|deprecated|vulnerab|security)")),
    (Level.SUCCESS, re.compile(r"(?i)(passed|all tests|completed|build succeeded|\bdone\b|✓)")),
    # Spanish voice commands (from voice.py interpreter)
    (Level.ACTION, re.compile(r"(?i)(reintentar pruebas|pausar agente \d|abrir terminal \d)")),
    (Level.SUCCESS, re.compile(r"(?i)(c[óo]mo (?:va|está) el (?:proyecto||)|estado (?:del |del )proyecto|progreso)")),
    (Level.SUCCESS, re.compile(r"(?i)(resumen (?:de )?agentes|qu[ée] hagan los agentes)")),
    (Level.SUCCESS, re.compile(r"(?i)(preferencia|configuraci[oó]n|config)")),
    (Level.SUCCESS, re.compile(r"(?i)(tareas (?:pendientes|en curso)|qu[ée] tareas)")),
    (Level.SUCCESS, re.compile(r"(?i)repite")),
    (Level.SUCCESS, re.compile(r"(?i)qu[ée] pas[oó] con (?:el |la )?agente \d")),
    # Conversational patterns (LOW priority, after technical and voice commands)
    # These should not trigger system commands, only return conversational intent
    (Level.SUCCESS, re.compile(r"(?i)^hola$|^hello$|^hi$")),          # saludos aislados
    (Level.SUCCESS, re.compile(r"(?i)^hola[^a-záéíóúññ].*|^hello .*|^hi .*")),  # saludos con continuación
    (Level.SUCCESS, re.compile(r"(?i)^jaja$|^jeje$|^xd$|^risas$")),     # risas y emoticonos
    (Level.SUCCESS, re.compile(r"(?i)^sí$|^no$|^ok$|^dale$")),          # afirmaciones/negaciones
    (Level.SUCCESS, re.compile(r"(?i)^(?:hola|hello|hi) ,? .*$")),      # saludos con "cómo estás" etc.
]
FALSE_ERROR = re.compile(r"(?i)\b0 (failed|errors?)\b|no errors")


def clean(line: str) -> str:
    return ANSI.sub("", line).strip()


def classify(agent: str, line: str):
    text = clean(line)
    if len(text) < 4:
        return None
    for level, rx in RULES:
        if rx.search(text):
            if level == Level.ERROR and FALSE_ERROR.search(text):
                continue
            return Event(agent, level, text[:140], line)
    return None  # ruido: no se habla
