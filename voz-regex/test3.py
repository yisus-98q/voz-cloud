import re

# Test the problematic characters
text = 'qu paso con agente 1'

# Test [ée] 
pattern_e = re.compile(r"(?i)qu[ée] pas", re.IGNORECASE)
m = pattern_e.search(text)
print('qu[ée] pas match:', m.group() if m else 'None')

# Test [oó]
pattern_o = re.compile(r"(?i)pas[oó] con", re.IGNORECASE)
m = pattern_o.search(text)
print('pas[oó] con match:', m.group() if m else 'None')

# Test combined
pattern_full = re.compile(r"(?i)qu[ée] pas[oó] con", re.IGNORECASE)
m = pattern_full.search(text)
print('qu[ée] pas[oó] con match:', m.group() if m else 'None')
PYEOF