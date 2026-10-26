from app.main import stt_mod
import inspect

print("=== get_selected_session ===")
func = stt_mod.get_selected_session
sig = inspect.signature(func)
print(f"Firma: {sig}")
doc = func.__doc__
print(f"Docstring: {doc}")
print(f"Retorno: {func()}")

print("\n=== _oc_fetch ===")
func = stt_mod._oc_fetch
sig = inspect.signature(func)
print(f"Firma: {sig}")
doc = func.__doc__
print(f"Docstring: {doc[:300]}")

print("\n=== _oc_send_and_speak ===")
func = stt_mod._oc_send_and_speak
sig = inspect.signature(func)
print(f"Firma: {sig}")
doc = func.__doc__
print(f"Docstring: {doc[:400]}")

print("\n=== speak_oc_response ===")
func = stt_mod.speak_oc_response
sig = inspect.signature(func)
print(f"Firma: {sig}")
doc = func.__doc__
print(f"Docstring: {doc[:300]}")

print("\n=== get_last_oc_response ===")
func = stt_mod.get_last_oc_response
sig = inspect.signature(func)
print(f"Firma: {sig}")
doc = func.__doc__
print(f"Docstring: {doc[:300]}")