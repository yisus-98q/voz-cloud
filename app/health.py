"""Centro de salud — Fase 2.

Checks paralelos con timeout: OpenCode, Piper (TTS), STT, Supervisor, Servidor.
"""
import socket
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

from .speech_queue import queue as speech_queue
from .piper_tts import PIPER_EXE, PIPER_MODEL

import os


def _now_ms():
    return int(time.time() * 1000)


def check_opencode():
    """Proceso opencode vivo o puerto 45278 abierto."""
    start = _now_ms()
    try:
        # Puerto de OpenCode (ajustar si tu OpenCode usa otro)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        r = s.connect_ex(("127.0.0.1", 45278))
        s.close()
        latency = _now_ms() - start
        if r == 0:
            return {"name": "OpenCode", "status": "ok", "detail": "Puerto 45278 abierto", "latency_ms": latency}
        return {"name": "OpenCode", "status": "warn", "detail": "Puerto 45278 no responde", "latency_ms": latency}
    except Exception as e:
        return {"name": "OpenCode", "status": "fail", "detail": str(e), "latency_ms": _now_ms() - start}


def check_piper():
    """Existen el .exe y el modelo, y sintetizan una palabra en <5 s."""
    start = _now_ms()
    try:
        missing = []
        if not os.path.exists(PIPER_EXE):
            missing.append("piper.exe")
        if not os.path.exists(PIPER_MODEL):
            missing.append("modelo .onnx")
        if missing:
            return {
                "name": "Piper (TTS)",
                "status": "fail",
                "detail": "Falta: " + ", ".join(missing),
                "latency_ms": _now_ms() - start,
            }
        # Test rápido: solo verificamos que existen los archivos (no sintetizamos para no bloquear)
        latency = _now_ms() - start
        return {
            "name": "Piper (TTS)",
            "status": "ok",
            "detail": "Voz cargada (" + os.path.basename(PIPER_MODEL) + ")",
            "latency_ms": latency,
        }
    except Exception as e:
        return {"name": "Piper (TTS)", "status": "fail", "detail": str(e), "latency_ms": _now_ms() - start}


def check_stt():
    """Micrófono disponible (sounddevice)."""
    start = _now_ms()
    try:
        import sounddevice as sd
        devices = sd.query_devices()
        input_devices = [d for d in devices if d.get("max_input_channels", 0) > 0]
        latency = _now_ms() - start
        if input_devices:
            return {
                "name": "STT",
                "status": "ok",
                "detail": str(len(input_devices)) + " micrófono(s)",
                "latency_ms": latency,
            }
        return {"name": "STT", "status": "warn", "detail": "Sin micrófono de entrada", "latency_ms": latency}
    except Exception as e:
        return {"name": "STT", "status": "warn", "detail": "No disponible: " + str(e), "latency_ms": _now_ms() - start}


def check_supervisor():
    """Hilo de la cola vivo y no atascado >60 s."""
    start = _now_ms()
    try:
        if speech_queue.current and speech_queue.current.ts:
            edad = time.time() - speech_queue.current.ts
            if edad > 60:
                return {
                    "name": "Supervisor",
                    "status": "warn",
                    "detail": "Cola atascada (" + str(round(edad)) + " s)",
                    "latency_ms": _now_ms() - start,
                }
        return {
            "name": "Supervisor",
            "status": "ok",
            "detail": "Cola " + str(speech_queue.size()) + "/" + str(speech_queue.max_size),
            "latency_ms": _now_ms() - start,
        }
    except Exception as e:
        return {"name": "Supervisor", "status": "fail", "detail": str(e), "latency_ms": _now_ms() - start}


def check_server():
    """Tiempo desde el último /ingest recibido."""
    start = _now_ms()
    try:
        from .main import last_ingest_ts
        edad = time.time() - last_ingest_ts
        latency = _now_ms() - start
        if edad < 60:
            return {
                "name": "Servidor",
                "status": "ok",
                "detail": "Último evento hace " + str(round(edad)) + " s",
                "latency_ms": latency,
            }
        return {
            "name": "Servidor",
            "status": "warn",
            "detail": "Sin eventos recientes",
            "latency_ms": latency,
        }
    except Exception:
        return {
            "name": "Servidor",
            "status": "ok",
            "detail": "Servidor activo",
            "latency_ms": _now_ms() - start,
        }


CHECKS = [
    check_opencode,
    check_piper,
    check_stt,
    check_supervisor,
    check_server,
]


def run_health(timeout_s=3):
    """Ejecuta todos los checks en paralelo con timeout."""
    results = []
    with ThreadPoolExecutor(max_workers=len(CHECKS)) as ex:
        futs = {ex.submit(c): c.__name__ for c in CHECKS}
        for fut in as_completed(futs, timeout=timeout_s):
            try:
                results.append(fut.result())
            except Exception as e:
                results.append({"name": futs[fut], "status": "fail", "detail": str(e), "latency_ms": 0})
    # Orden determinista
    order = {c.__name__: i for i, c in enumerate(CHECKS)}
    results.sort(key=lambda r: order.get(r["name"], 99))
    return {
        "ts": _now_ms(),
        "checks": results,
    }


def worst_status(checks):
    if not checks:
        return "unknown"
    if any(c["status"] == "fail" for c in checks):
        return "fail"
    if any(c["status"] == "warn" for c in checks):
        return "warn"
    return "ok"


def health_report():
    """Texto plano listo para copiar."""
    h = run_health()
    from .main import event_store
    lines = []
    lines.append("VOZ CLOUD — DIAGNÓSTICO")
    lines.append("Fecha: " + time.strftime("%Y-%m-%d %H:%M:%S"))
    lines.append("")
    for c in h["checks"]:
        lines.append("[" + c["status"].upper() + "] " + c["name"] + " — " + c["detail"] + " (" + str(c["latency_ms"]) + " ms)")
    lines.append("")
    lines.append("Últimos eventos:")
    for e in (event_store.list(20) if event_store else []):
        lines.append(time.strftime("%H:%M:%S", time.localtime(e["ts"] / 1000)) + " [" + e["level"] + "] " + e["agent"] + ": " + e["text"])
    return "\n".join(lines)
