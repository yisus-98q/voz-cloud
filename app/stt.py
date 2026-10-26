"""STT real — Fase 5 con integración OpenCode y voz de respuesta.

Usa faster-whisper (modelo small) + sounddevice para capturar audio del
micrófono, detectar la palabra de activación «Voz Cloud» y transcribir el
comando posterior.

Después de enviar un prompt a OpenCode, espera la respuesta del asistente
y la reproduce por voz usando Piper TTS.

Control del micrófono:
  - Se enciende manualmente con POST /stt/on y se queda encendido hasta que
    el usuario lo apague con POST /stt/off.
  - Si hay 5 segundos de silencio continuo, envía lo acumulado a OpenCode
    y se apaga solo.
"""
import threading
import time
import base64
import json
import os
import urllib.request
import urllib.error
import numpy as np
import sounddevice as sd
from faster_whisper import WhisperModel

from .voice import interpretar
from .events_store import event_store
from .piper_tts import speak

MODEL_SIZE = "small"
DEVICE = "cpu"          # Cambiar a "cuda" si tienes GPU NVIDIA
COMPUTE_TYPE = "int8"   # int8 para CPU, float16 para GPU
SAMPLE_RATE = 16000
CHUNK_MS = 500          # Bloques de audio de 500 ms para análisis de energía
ACTIVATION_PHRASE = "voz cloud"
SILENCE_TIMEOUT_S = 5.0 # Segundos de silencio para auto-envío y apagado
ENERGY_THRESHOLD = 0.003 # Umbral RMS para considerar que hay voz (ajustado para no cortar tan temprano)

# OpenCode config
OC_BASE = "http://127.0.0.1:45278"
OC_SERVICE_PATH = r"C:\Users\miler\.config\opencode\service.json"

# Última respuesta de OpenCode (para el botón "Escuchar explicación")
_last_oc_response = None
_last_oc_response_lock = threading.Lock()

_model = None
_model_lock = threading.Lock()

_listening = False
_listen_thread = None
_stop_event = threading.Event()

_voice_items = []      # Lista de items de voz para /voice/feed
_voice_items_lock = threading.Lock()
_voice_counter = [0]

# Estado de sesión OpenCode seleccionada
_selected_session_id = None
_session_lock = threading.Lock()

# Texto acumulado por voz (para enviar después del silencio)
_pending_voice_text = ""
_pending_lock = threading.Lock()


def _get_oc_auth():
    """Lee la contraseña de OpenCode y devuelve el header Basic Auth."""
    try:
        with open(OC_SERVICE_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
        password = data.get("password", "")
        token = base64.b64encode(f"opencode:{password}".encode("utf-8")).decode("utf-8")
        return f"Basic {token}"
    except Exception:
        return None


def _oc_fetch(path, method="GET", body=None):
    """Hace una petición a la API de OpenCode."""
    auth = _get_oc_auth()
    if not auth:
        return None, "No se pudo leer la autenticación de OpenCode"
    url = OC_BASE + path
    headers = {"Authorization": auth, "Content-Type": "application/json"}
    data = None
    if body is not None:
        data = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            txt = resp.read().decode("utf-8")
            try:
                return json.loads(txt), None
            except Exception:
                return txt, None
    except urllib.error.HTTPError as e:
        try:
            txt = e.read().decode("utf-8")
        except Exception:
            txt = str(e)
        return None, f"HTTP {e.code}: {txt}"
    except Exception as e:
        return None, str(e)


def _oc_send_prompt(session_id, text):
    """Envía un prompt a una sesión de OpenCode y devuelve (data, err)."""
    if not session_id:
        return None, "No hay sesión de OpenCode seleccionada"
    # Validar que la sesión existe
    data, err = _oc_fetch(f"/api/session/{session_id}")
    if err:
        return None, f"Sesión no encontrada: {err}"
    # Enviar prompt
    data, err = _oc_fetch(
        f"/api/session/{session_id}/prompt",
        method="POST",
        body={"text": text},
    )
    if err:
        return None, f"Error enviando prompt: {err}"
    return data, None


def _get_last_assistant_text(session_id, min_ts=0):
    """Obtiene el último texto de respuesta del asistente de una sesión.

    Polls for up to 60 seconds waiting for an assistant text response.
    Checks if the assistant has finished (finish != 'tool-calls').
    Also falls back to reasoning content if no text is found.
    """
    for attempt in range(60):
        time.sleep(1)
        data, err = _oc_fetch(f"/api/session/{session_id}/message")
        if err:
            continue
        msgs = data.get("data", []) if isinstance(data, dict) else data
        if not isinstance(msgs, list):
            continue
        # Buscar el último mensaje del asistente con texto (posterior al prompt)
        for m in reversed(msgs):
            if m.get("type") != "assistant":
                continue
            ts = m.get("time", {}).get("created", 0)
            if ts < min_ts:
                continue
            content = m.get("content", [])
            # First try to find text content
            for c in content:
                if c.get("type") == "text":
                    txt = c.get("text", "")
                    if txt and len(txt) > 5:
                        return txt
            # If no text, check if assistant finished (not still doing tool calls)
            finish = m.get("finish", "")
            if finish and finish != "tool-calls" and finish != "tool_calls":
                # Assistant finished - try reasoning as fallback
                for c in content:
                    if c.get("type") == "reasoning":
                        txt = c.get("text", "")
                        if txt and len(txt) > 20:
                            return txt[:300]
    return None


def _oc_send_and_speak(session_id, text):
    """Envía un prompt a OpenCode, espera la respuesta y la habla por voz."""
    global _last_oc_response
    data, err = _oc_send_prompt(session_id, text)
    if err:
        _add_voice_item("sistema", f"Error enviando a OpenCode: {err}", None)
        return None, err
    # Guardar el prompt enviado
    _add_voice_item("sistema", f"Enviado a OpenCode: {text[:60]}...", None)
    # Esperar la respuesta del asistente (en un hilo separado para no bloquear)
    threading.Thread(target=_fetch_and_speak_response, args=(session_id, data), daemon=True).start()
    # Limpiar pendiente
    with _pending_lock:
        global _pending_voice_text
        _pending_voice_text = ""
    return data, None


def _fetch_and_speak_response(session_id, prompt_data):
    """Espera la respuesta de OpenCode y la reproduce por voz.

    Polls for up to 60 seconds waiting for an assistant text response.
    Stores the response so the "Escuchar explicación" button can retrieve it.
    Runs in a background thread so it doesn't block the main flow.
    """
    global _last_oc_response
    min_ts = 0
    if isinstance(prompt_data, dict):
        msg_data = prompt_data.get("data", {})
        min_ts = msg_data.get("time", {}).get("created", 0)
    # Wait for OpenCode to process
    time.sleep(5)
    respuesta = _get_last_assistant_text(session_id, min_ts)
    if respuesta:
        texto_limpio = respuesta.replace("**", "").replace("*", "").replace("#", "").replace("`", "")
        texto_limpio = texto_limpio.replace("\n", " ").strip()
        if len(texto_limpio) > 500:
            texto_limpio = texto_limpio[:500] + "..."
        with _last_oc_response_lock:
            _last_oc_response = texto_limpio
        _add_voice_item("opencode", texto_limpio[:140], None)
        try:
            speak(texto_limpio)
        except Exception:
            pass


def _get_model():
    global _model
    with _model_lock:
        if _model is None:
            _model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
        return _model


def _rms(audio_float32: np.ndarray) -> float:
    if len(audio_float32) == 0:
        return 0.0
    return float(np.sqrt(np.mean(audio_float32 ** 2)))


def _transcribe(audio_float32: np.ndarray) -> str:
    model = _get_model()
    segments, _ = model.transcribe(
        audio_float32,
        language="es",
        beam_size=1,
        vad_filter=True,
        vad_parameters=dict(min_silence_duration_ms=1000),
    )
    texto = " ".join(seg.text for seg in segments).strip()
    return texto


def _add_voice_item(heard: str, reply: str, confirm=None):
    with _voice_items_lock:
        _voice_counter[0] += 1
        item = {
            "id": _voice_counter[0],
            "ts": int(time.time() * 1000),
            "heard": heard,
            "reply": reply,
            "confirm": confirm,
        }
        _voice_items.append(item)
        if len(_voice_items) > 100:
            _voice_items.pop(0)
        try:
            event_store.add("voz", "INFO", heard, raw=reply)
        except Exception:
            pass
    return item


def _procesar_comando(texto: str):
    reply, confirm, _ = interpretar(texto)
    _add_voice_item(texto, reply, confirm)
    return reply, confirm


def _escuchar():
    global _listening, _pending_voice_text
    _listening = True
    _stop_event.clear()

    ultimo_sonido = time.time()
    esperando_comando = False
    buffer_voz = np.array([], dtype=np.float32)

    try:
        chunk_samples = int(SAMPLE_RATE * CHUNK_MS / 1000)
        with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="float32") as stream:
            while not _stop_event.is_set():
                bloque, _ = stream.read(chunk_samples)
                bloque = bloque.flatten()
                energia = _rms(bloque)

                if energia > ENERGY_THRESHOLD:
                    ultimo_sonido = time.time()
                    buffer_voz = np.concatenate([buffer_voz, bloque])
                    max_muestras = SAMPLE_RATE * 30
                    if len(buffer_voz) > max_muestras:
                        buffer_voz = buffer_voz[-max_muestras:]
                else:
                    silencio_segundos = time.time() - ultimo_sonido
                    if silencio_segundos > SILENCE_TIMEOUT_S and len(buffer_voz) > 0:
                        try:
                            texto = _transcribe(buffer_voz.copy())
                        except Exception:
                            texto = ""
                        buffer_voz = np.array([], dtype=np.float32)
                        texto = texto.strip()
                        if texto:
                            with _pending_lock:
                                _pending_voice_text = texto
                            # Procesar: enviar a OpenCode (que hablará la respuesta)
                            _oc_send_and_speak(_selected_session_id, texto)
                        _stop_event.set()
                        ultimo_sonido = time.time()

                if len(buffer_voz) >= SAMPLE_RATE * 2:
                    try:
                        texto = _transcribe(buffer_voz.copy())
                    except Exception:
                        texto = ""
                    buffer_voz = np.array([], dtype=np.float32)
                    texto = texto.strip().lower()
                    if not texto:
                        continue
                    pass

    except Exception as e:
        _add_voice_item("error", f"Error de micrófono: {str(e)}", None)
    finally:
        _listening = False


def start_listening() -> bool:
    global _listen_thread
    if _listening and _listen_thread and _listen_thread.is_alive():
        return True
    _stop_event.clear()
    _listen_thread = threading.Thread(target=_escuchar, daemon=True)
    _listen_thread.start()
    return True


def stop_listening() -> bool:
    global _listening, _listen_thread
    _stop_event.set()
    _listening = False
    if _listen_thread and _listen_thread.is_alive():
        _listen_thread.join(timeout=3)
    return True


def is_listening() -> bool:
    return _listening


def get_voice_items(since_id: int = 0):
    with _voice_items_lock:
        return [it for it in _voice_items if it["id"] > since_id]


def get_last_voice_id() -> int:
    with _voice_items_lock:
        return _voice_counter[0]


def set_selected_session(session_id: str):
    global _selected_session_id
    with _session_lock:
        _selected_session_id = session_id


def get_selected_session():
    with _session_lock:
        return _selected_session_id


def get_pending_text():
    with _pending_lock:
        return _pending_voice_text


def get_last_oc_response():
    """Devuelve la última respuesta de OpenCode para el botón 'Escuchar explicación'."""
    with _last_oc_response_lock:
        return _last_oc_response


def speak_oc_response():
    """Reproduce por voz la última respuesta de OpenCode.

    Si no hay respuesta guardada, intenta obtener la última del asistente.
    Polls for up to 30 seconds if the assistant is still processing.
    """
    global _last_oc_response
    with _last_oc_response_lock:
        texto = _last_oc_response
    if not texto:
        sid = get_selected_session()
        if sid:
            respuesta = _get_last_assistant_text(sid, 0)
            if respuesta:
                texto_limpio = respuesta.replace("**", "").replace("*", "").replace("#", "").replace("`", "")
                texto_limpio = texto_limpio.replace("\n", " ").strip()
                if len(texto_limpio) > 500:
                    texto_limpio = texto_limpio[:500] + "..."
                with _last_oc_response_lock:
                    _last_oc_response = texto_limpio
                texto = texto_limpio
    if not texto:
        return "OpenCode aún está procesando. Intenta de nuevo en unos segundos."
    try:
        speak(texto)
        return "Reproduciendo la explicación de OpenCode."
    except Exception as e:
        return f"Error al reproducir: {str(e)}"
