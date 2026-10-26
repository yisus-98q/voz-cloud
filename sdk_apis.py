#!/usr/bin/env python
"""SDK API endpoints for Voz Cloud - to be integrated into app/main.py"""
import os

# Read current main.py
with open('app/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# New SDK API endpoints - using raw strings and careful formatting
# Insert before the static file serving section
sdk_endpoints =r'''

# ==================== SDK API Endpoints ====================

# Global: health()
@app.get("/api/global/health")
def api_global_health():
    """Check server health and version."""
    from . import health as health_mod
    try:
        result = health_mod.check_health()
    except Exception:
        result = {"healthy": True, "version": "0.1.0"}
    return {"healthy": result.get("healthy", True), "version": result.get("version", "0.1.0")}

# App: agents()
@app.get("/api/app/agents")
def api_app_agents():
    """List all available agents."""
    from .agents import agent_registry
    agents = agent_registry.get_all()
    result = []
    for a in agents:
        result.append({
            "id": a.id,
            "name": a.name,
            "state": a.state.value if hasattr(a.state, 'value') else a.state,
            "type": a.type if hasattr(a, 'type') else "unknown"
        })
    return {"agents": result}

# Project: list()
@app.get("/api/project/list")
def api_project_list():
    """List all projects."""
    from . import config as config_obj
    config_data = config_obj.load()
    return {"projects": config_data.get("projects", [])}

# Config: get()
@app.get("/api/config")
def api_config_get():
    """Get config info."""
    from . import config as config_obj
    config_data = config_obj.load()
    return {"config": config_data}

# Config: providers()
@app.get("/api/config/providers")
def api_config_providers():
    """List providers and default models."""
    from . import config as config_obj
    providers_data = config_obj.providers()
    return {"providers": providers_data.get("providers", []), "default": providers_data.get("default", {})}

# Auth: set()
@app.post("/api/auth/set")
def api_auth_set(body: dict):
    """Set authentication credentials."""
    from . import auth as auth_mod
    result = auth_mod.set_credentials(body)
    return {"result": result}

# Events: subscribe (Server-Sent Events)
@app.get("/api/events/stream")
def api_events_stream():
    """Server-sent events stream."""
    from .events_store import event_store
    import asyncio

    async def event_generator():
        last_id = 0
        while True:
            events = event_store.get_recent_since(last_id)
            for event in events:
                yield f"data: {event.json()}\n\n"
            await asyncio.sleep(1)

    from fastapi.responses import StreamingResponse
    return StreamingResponse(event_generator(), media_type="text/event-stream")

# Find: text search
@app.post("/api/find/text")
def api_find_text(body: dict):
    """Search for text in files."""
    import os as os_mod
    import re
    query = body.get("query", "")
    path = body.get("path", ".")
    results = []

    try:
        for root, dirs, files in os_mod.walk(path):
            for name in files:
                filepath = os_mod.join(root, name)
                try:
                    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                        file_content = f.read()
                        if query in file_content:
                            matches = [{"line": i+1, "text": line.strip()}
                                       for i, line in enumerate(file_content.split('\n'))
                                       if query in line]
                            results.append({"path": filepath, "matches": matches})
                except Exception:
                    continue
    except Exception:
        pass

    return {"results": results}

# Find: files
@app.post("/api/find/files")
def api_find_files(body: dict):
    """Find files and directories by name."""
    import os as os_mod
    query = body.get("query", "")
    path = body.get("path", ".")
    directory_only = body.get("dirs", "false") == "false"

    results = []

    try:
        for root, dirs, files in os_mod.walk(path):
            items = dirs if directory_only else files + dirs
            for name in items:
                if query.lower() in name.lower():
                    results.append(os_mod.join(root, name))
    except Exception:
        pass

    return {"results": results}

# Path: get
@app.get("/api/path/get")
def api_path_get():
    """Get current path."""
    import os as os_mod
    return {"path": os_mod.getcwd()}

'''

# Find the position to insert: after orchestrator_commands, before "# ==================== Servir interfaz estática"
insert_marker = "# ==================== Servir interfaz estática ===================="
insert_pos = content.find(insert_marker)

if insert_pos >= 0:
    # Insert the SDK endpoints
    new_content = content[:insert_pos] + sdk_endpoints + content[insert_pos:]
    
    # Write back
    with open('app/main.py', 'w', encoding='utf-8') as f:
        f.write(new_content)
    print("SDK API endpoints added successfully")
else:
    print("Could not find insertion marker in main.py")
    print("Looking for:", repr(insert_marker))