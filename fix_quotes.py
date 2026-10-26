#!/usr/bin/env python
import re

# Read the file
with open('app/main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Fix the triple quotes that have extra backslashes
# Pattern: \\""" should be just """
content = content.replace('\\\\\\"\\\\\\"\\\\\\"', '"""')

# Also fix any remaining \\" to just " inside docstrings, but not in other contexts
# Let's be more careful: replace only the specific problematic pattern

# Write back
with open('app/main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Fixed triple quotes")