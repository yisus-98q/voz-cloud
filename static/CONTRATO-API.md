# Contrato de API — Voz Cloud (interfaz ↔ backend)

La interfaz (`static/`) ya está terminada. **OpenCode solo debe implementar estas rutas** en el backend FastAPI.
Cada ruta que responda pasa sola de `DEMO` a `EN VIVO` en el panel «Conexión con el backend». No hay que tocar HTML, CSS ni JS.

## Servir la interfaz

```python
# app/main.py (al final del archivo, después de las rutas)
from fastapi.staticfiles import StaticFiles
app.mount("/", StaticFiles(directory="static", html=True), name="ui")
```

Abrir `http://127.0.0.1:8000/`. Si la interfaz se sirve desde otro puerto, usar `?api=http://127.0.0.1:8000` y activar CORS en FastAPI (`CORSMiddleware`, `allow_origins=["*"]`).

## Convenciones

- JSON UTF-8. Tiempos (`ts`) en milisegundos desde epoch (también se acepta en segundos).
- Niveles: `INFO`, `SUCCESS`, `WARNING`, `ERROR`, `ACTION`.
- Estados de agente: `idle`, `working`, `done`, `failed`, `waiting`.
- Estados de salud: `ok`, `warn`, `fail`.
- La interfaz espera respuesta en menos de 2,5 s; si no, la ruta se marca `DEMO`.

## Rutas

| # | Método y ruta | Fase | Respuesta |
|---|---------------|------|-----------|
| 1 | `GET /health` | 2 | `{"ts":1760000000000,"checks":[{"name":"Piper (TTS)","status":"ok","detail":"Voz cargada","latency_ms":120}]}` |
| 2 | `GET /health/report` | 2 | Texto plano (`text/plain`) con fecha, estado de cada componente y últimos 20 eventos |
| 3 | `GET /status` | 1 | `{"queue":2,"dropped":0,"muted":false,"max":8,"current":{"text":"Error: agente 1. 3 pruebas fallidas"} \| null,"mic":false}` |
| 4 | `POST /mute/{true\|false}` | 1 | `{"muted":true}` |
| 5 | `GET /agents` | 4 | `{"agents":[{"id":"a1","name":"Agente 1","role":"Pruebas","state":"working","last":"Ejecutando pruebas","ts":1760000000000}]}` |
| 6 | `GET /events?since={id}` | 3 | `{"events":[{"id":15,"ts":1760000000000,"agent":"Agente 1","level":"ERROR","text":"3 pruebas fallidas"}]}` — solo eventos con `id` mayor a `since` |
| 7 | `GET /config` | 3 | `{"levels":["SUCCESS","WARNING","ERROR","ACTION"],"quiet_start":"22:00","quiet_end":"07:00","dedupe_s":30,"queue_max":8,"queue_age_s":60}` |
| 8 | `PUT /config` | 3 | Recibe el mismo objeto de `GET /config`; devuelve el objeto guardado |
| 9 | `POST /voice/command` | 5 | Recibe `{"text":"Voz Cloud, cómo va el proyecto"}`; devuelve un *item de voz* (ver abajo) |
| 10 | `GET /voice/feed?since={id}` | 5 | `{"items":[ item de voz, ... ]}` — lo que el STT escuchó por micrófono |
| 11 | `POST /voice/confirm` | 5 | Recibe `{"id":"c1","accept":true}`; devuelve un item de voz con la respuesta final |
| 12 | `POST /stt/{on\|off}` | 5 | `{"listening":true}` |

### Item de voz

```json
{
  "id": 7,
  "ts": 1760000000000,
  "heard": "Voz Cloud, reintentar pruebas",
  "reply": "Necesito tu confirmación.",
  "confirm": { "id": "c1", "text": "¿Confirmas reintentar las pruebas del Agente 1?", "timeout_s": 8 }
}
```

`confirm` es `null` cuando no hace falta confirmar. La interfaz muestra el modal con cuenta atrás y llama a `POST /voice/confirm`.
Todo comando (escrito o hablado) debe aparecer también en `/voice/feed` con el mismo `id`; la interfaz descarta ids repetidos.

## Qué conecta cada parte (guía para OpenCode)

| Parte del panel | Rutas | Se conecta con |
|-----------------|-------|----------------|
| Centro de salud | 1, 2 | `app/health.py` (checks de OpenCode, Piper, STT, supervisor, servidor) |
| Cola de voz | 3, 4 | `SpeechQueue` (`size()`, `dropped`, `muted`, `current`) |
| Agentes | 5 | Registro de agentes alimentado por el clasificador |
| Eventos | 6 | Historial de eventos (lista en memoria o SQLite `events.db`) |
| Configuración | 7, 8 | `config.json` leído por clasificador, deduplicador y cola |
| Control por voz | 9, 10, 11, 12 | `stt.py`, `intents.py` y lista blanca de acciones |

## Acciones autorizadas por voz (lista blanca)

Solo `reintentar pruebas`, `pausar agente N`, `abrir terminal N`. Cualquier otra se responde con «No tengo esa acción autorizada». Toda acción que cambie algo exige confirmación (`confirm`) y caduca a los 8 s.
