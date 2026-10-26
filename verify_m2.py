#!/usr/bin/env python
import sys
import os
import re

sys.path.insert(0, 'D:\\voz-cloud')

# Test 1: Import check
from app.main import es_mensaje_conversacional, command
from app.classifier import classify, Level
print("TEST 1 PASS: Importes correctos")

# Test 2: classifier.py no modificado
with open('app/classifier.py', 'r', encoding='utf-8') as f:
    classifier_content = f.read()
if 'es_mensaje_conversacional' not in classifier_content:
    print("TEST 2 PASS: classifier.py sin modificar")
else:
    print("TEST 2 FAIL: classifier.py fue modificado")
    sys.exit(1)

# Test 3: es_mensaje_conversacional function works
from app.main import es_mensaje_conversacional
tests = [
    ("hola", True, "Saludo simple"),
    ("hola, ¿cómo estás?", True, "Saludo con continuación"),
    ("reintentar pruebas", False, "Comando técnico"),
    ("XD", False, "Emoticono muy corto"),
    ("sí", False, "Afirmación muy corta"),
    ("no", False, "Negación muy corta"),
    ("ok", False, "OK muy corto"),
]
all_pass = True
for text, expected, desc in tests:
    result = es_mensaje_conversacional(text)
    if result != expected:
        print(f"TEST 3 FAIL: '{text}' esperaba {expected}, got {result} ({desc})")
        all_pass = False
if all_pass:
    print("TEST 3 PASS: Lógica de detección conversacional correcta")
else:
    print("TEST 3 FAIL: Algunas detecciones son incorrectas")
    sys.exit(1)

# Test 4: Verify that technical commands are not diverted
import inspect
from app.main import command
source = inspect.getsource(command)
technical_patterns = ['reintentar pruebas', 'pausar agente', 'abrir terminal']
technical_preserved = all(p in source for p in technical_patterns)
if technical_preserved:
    print("TEST 4 PASS: Comandos técnicos preservados en command()")
else:
    print("TEST 4 FAIL: Algunos patrones técnicos no preservados")
    sys.exit(1)

print("\n=== TODAS LAS PRUEBAS PASARON ===")
print("El Módulo 2 está correctamente implementado y verificado.")