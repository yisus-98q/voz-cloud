import re

# Test simpler patterns
pattern1 = re.compile(r"(?i)qu[ée] pas[oó] con (?:el |la )?agente \d")
pattern2 = re.compile(r"qu[ée] pas[oó] con (?:el |la )?agente \d")

texts = [
    'qu paso con agente 1',
    'qu paso con agente 1',
    'qu paso con agente dos',
]

for t in texts:
    m1 = pattern1.search(t)
    m2 = pattern2.search(t)
    print('Text:', repr(t))
    print('  Full pattern match:', m1.group() if m1 else 'None')
    print('  Simple pattern match:', m2.group() if m2 else 'None')
    print()
PYEOF