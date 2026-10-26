from app.main import stt_mod
import inspect

functions = [
    'get_selected_session',
    '_oc_fetch',
    '_oc_send_and_speak',
    'speak_oc_response',
    'get_last_oc_response',
]

for func_name in functions:
    try:
        func = getattr(stt_mod, func_name)
        print(f"\n=== {func_name} ===")
        print(f"  Tipo: {type(func)}")
        # Intentar obtener firma
        try:
            sig = inspect.signature(func)
            print(f"  Firma: {sig}")
        except:
            print("  Firma: No disponible")
        
        # Intentar ver docstring
        doc = func.__doc__
        if doc:
            print(f"  Docstring: {doc[:400]}")
        else:
            print("  Docstring: None")
    except AttributeError as e:
        print(f"\n=== {func_name} ===")
        print(f"  ERROR: {e}")

# Also check some other useful functions
print("\n\n=== Additional functions ===")
additional = ['_selected_session_id', 'set_selected_session', 'speak']
for func_name in additional:
    try:
        func = getattr(stt_mod, func_name)
        print(f"\n=== {func_name} ===")
        print(f"  Tipo: {type(func)}")
        try:
            sig = inspect.signature(func)
            print(f"  Firma: {sig}")
        except:
            print("  Firma: No disponible")
        doc = func.__doc__
        if doc:
            print(f"  Docstring: {doc[:300]}")
        else:
            print("  Docstring: None")
    except AttributeError as e:
        print(f"\n=== {func_name} ===")
        print(f"  ERROR: {e}")