import re

# Test step by step
pattern_full = re.compile(r"(?i)qu[ée] pas[oó] con (?:el |la )?agente \d")

# Test just "qu paso con agente 1"
text = "qu paso con agente 1"

# Test each component
print("Text:", repr(text))
print()

# Test "qu"
m = re.search(r"qu", text, re.IGNORECASE)
print('"qu" match:', m.group() if m else 'None')

# Test " qu" (space + qu)
m = re.search(r" qu", text, re.IGNORECASE)
print('" qu" match:', m.group() if m else 'None')

# Test "qu paso"
m = re.search(r"qu paso", text, re.IGNORECASE)
print('"qu paso" match:', m.group() if m else 'None')

# Test "qu paso con"
m = re.search(r"qu paso con", text, re.IGNORECASE)
print('"qu paso con" match:', m.group() if m else 'None')

# Test "qu paso con agente"
m = re.search(r"qu paso con agente", text, re.IGNORECASE)
print('"qu paso con agente" match:', m.group() if m else 'None')

# Test "qu paso con agente "
m = re.search(r"qu paso con agente ", text, re.IGNORECASE)
print('"qu paso con agente " match:', m.group() if m else 'None')

# Test "qu paso con agente 1"
m = re.search(r"qu paso con agente \d", text, re.IGNORECASE)
print('"qu paso con agente 1" match:', m.group() if m else 'None')
PYEOF