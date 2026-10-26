from app.main import es_mensaje_conversacional, classify, Level

tests = [
    ("hola", "Spanish greeting"),
    ("hola, ¿cómo estás?", "Spanish greeting with continuation"),
    ("reintentar pruebas", "Technical command"),
    ("XD", "Emoticon"),
    ("sí", "Affirmation"),
    ("no", "Negation"),
    ("ok", "Okay"),
    ("dale", "Let/go ahead"),
    ("¿Qué puedes hacer?", "Question"),
    ("passed all tests", "Technical success"),
]

print("Testing es_mensaje_conversacional:")
print("=" * 60)
for text, desc in tests:
    result = es_mensaje_conversacional(text)
    status = "PASS" if result else "FAIL"
    print(f'{status} "{text}" ({desc:30s}) -> {result}')

print("=" * 60)
PYEOF