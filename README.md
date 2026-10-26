# Voz Cloud

Panel de desarrollo inteligente que **escucha, entiende y comunica por voz** lo que ocurre en tus terminales mientras trabajas con OpenCode y tus agentes de programación.

No lee cada línea: filtra lo importante y te avisa con frases cortas, por ejemplo:

> «Agente 2 terminó la corrección. Las pruebas pasaron. El agente 4 encontró dos advertencias de seguridad».
> «Atención: el agente 1 detectó tres pruebas fallidas. Revisa la terminal correspondiente».

## Componentes

- **OpenCode / agentes:** generan la salida de las terminales.
- **Piper (TTS):** habla los avisos.
- **STT:** reconoce tu voz (Fase 5).
- **Supervisor:** cola de voz con prioridad.
- **Servidor (FastAPI):** recibe, clasifica y encola los eventos.

## Fases de desarrollo

| Fase | Nombre | Objetivo |
|------|--------|----------|
| 1 | Estabilidad | Evitar repeticiones y controlar la cola de Piper |
| 2 | Centro de salud | Estado real de cada componente y diagnóstico copiable |
| 3 | Notificaciones inteligentes | Clasificar: info, éxito, advertencia, error, intervención |
| 4 | Coordinación de agentes | Identificar terminales, resumir y priorizar avisos |
| 5 | Control por voz | Consultar el estado y ejecutar acciones autorizadas |

## Instalación (PowerShell, Windows)

```powershell
cd voz-cloud
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Descarga Piper para Windows desde `github.com/rhasspy/piper/releases` y una voz en español (`.onnx` y `.json`) desde `huggingface.co/rhasspy/piper-voices`. Guárdalo todo en `C:\piper\`.

Variables opcionales:

```powershell
$env:PIPER_EXE="C:\piper\piper.exe"
$env:PIPER_MODEL="C:\piper\es_ES-davefx-medium.onnx"
```

## Estructura

```
voz-cloud/
├─ app/
│  ├─ __init__.py
│  ├─ events.py
│  ├─ classifier.py
│  ├─ dedupe.py
│  ├─ speech_queue.py
│  ├─ piper_tts.py
│  ├─ aggregator.py
│  └─ main.py
├─ tools/pipe.py
├─ requirements.txt
└─ README.md
```

## Ejecutar el servidor

```powershell
uvicorn app.main:app --port 8000
```

## Enviar líneas de terminal desde PowerShell

```powershell
$u="http://127.0.0.1:8000/ingest"
# 1. Éxito -> debe decir "Listo: agente 2..."
Invoke-RestMethod $u -Method Post -ContentType "application/json" -Body '{"agent":"agente 2","line":"All tests passed"}'
# 2. Duplicado -> duplicate=true y NO habla
Invoke-RestMethod $u -Method Post -ContentType "application/json" -Body '{"agent":"agente 2","line":"All tests passed"}'
# 3. Error -> habla de inmediato
Invoke-RestMethod $u -Method Post -ContentType "application/json" -Body '{"agent":"agente 1","line":"3 tests failed"}'
# 4. Falso positivo -> ignored
Invoke-RestMethod $u -Method Post -ContentType "application/json" -Body '{"agent":"agente 1","line":"0 failed, 12 passed"}'
# 5. Estado
Invoke-RestMethod http://127.0.0.1:8000/status
```

## Usar tools/pipe.py entre OpenCode y la pantalla

```powershell
opencode ... 2>&1 | python tools\pipe.py "agente 1"
```

## Criterios de aceptación (Fase 1)

- [ ] Una línea repetida no se habla dos veces en 30 s.
- [ ] Un error pasa por delante de un éxito en la cola.
- [ ] Con más de 8 avisos pendientes se descartan los menos graves y sube `dropped`.
- [ ] `/mute/true` silencia sin perder las intervenciones pendientes.
