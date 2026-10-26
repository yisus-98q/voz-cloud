#!/usr/bin/env python
"""Inspección de app/main.py - Flujo /command (solo lectura)."""

import sys
import re

sys.path.insert(0, 'D:\\voz-cloud')

def read_file_range(path, start, end):
    """Read lines from file 1-indexed."""
    with open(path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
        # Convert to 1-indexed and strip line numbers from output
        return [line.rstrip() for i, line in enumerate(lines, 1) if start <= i <= end]

print("=" * 70)
print("INSPECCIÓN DE APP/MAIN.PY - FLUJO /COMMAND")
print("=" * 70)

# Leer main.py completa
with open('D:\\voz-cloud\\app\\main.py', 'r', encoding='utf-8') as f:
    all_lines = f.readlines()

# Encontrar la función command()
print("\n--- 1. ENDPOINT /command ---")
for i, line in enumerate(all_lines, 1):
    if 'def command' in line and i < 120:
        # Print from here until next top-level def or class
        print(f"\nLínea {i}: {line.rstrip()}")
        # Print following lines until we hit another def at same indentation
        for j in range(i+1, min(i+30, len(all_lines))):
            if all_lines[j] and not all_lines[j][0].isspace() and 'def ' in all_lines[j]:
                break
            print(f"  {j}: {all_lines[j].rstrip()}")

print("\n--- 2. FUNCION classify() ---")
# Ya la vimos en classifier.py, pero buscar referencias en main.py
for i, line in enumerate(all_lines, 1):
    if 'from .classifier import' in line or 'from . import classifier' in line:
        print(f"Línea {i}: {line.rstrip()}")

print("\n--- 3. Integraciones: OpenCode, Piper, etc. ---")
for i, line in enumerate(all_lines, 1):
    # Buscar referencias a funciones conocidas
    lower = line.lower()
    if any(kw in lower for kw in ['open', 'piper', 'speak', 'confirm', 'voice', 'stt', 'event', 'ms_add']):
        # Filtrar líneas que son realmente llamadas a funciones, no solo comentarios
        if 'from .' in line or line.strip().startswith(('@', '"""', "'''")):
            pass  # Skip decorators and docstrings
        else:
            print(f"Línea {i}: {line.rstrip()}")

print("\n--- 4. Eventos y historial ---")
for i, line in enumerate(all_lines, 1):
    lower = line.lower()
    if 'ms_add_event' in line or 'event_store' in line or 'add_event' in line:
        print(f"Línea {i}: {line.rstrip()}")

print("\n--- 5. Niveles y respuestas ---")
for i, line in enumerate(all_lines, 1):
    if 'ev.level.name' in line or 'response' in line.lower() or 'return {' in line:
        print(f"Línea {i}: {line.rstrip()}")

print("\n" + "=" * 70)
print("FIN DE INSPECCIÓN")
print("=" * 70)