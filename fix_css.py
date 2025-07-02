#!/usr/bin/env python3
"""Fix CSS issues in BasePanel.py"""

import re

# Read the file
with open('claude_code_morph/panels/BasePanel.py', 'r') as f:
    content = f.read()

# Replace problematic CSS properties
replacements = [
    ('border-radius: \\d+;', ''),  # Remove border-radius
    ('text-style: normal;', 'text-style: none;'),  # Fix text-style normal
    ('transition: opacity 200ms ease-in-out;', ''),  # Remove transition
    ('z-index: 10;', ''),  # Remove z-index
    ('white-space: pre;', ''),  # Remove white-space
    ('animation: fadeIn 300ms ease-in;', 'opacity: 1;'),  # Replace animation with opacity
    ('animation: fadeOut 300ms ease-out;', 'opacity: 0;'),  # Replace animation with opacity
]

for pattern, replacement in replacements:
    content = re.sub(pattern, replacement, content)

# Write back
with open('claude_code_morph/panels/BasePanel.py', 'w') as f:
    f.write(content)

print("CSS fixes applied successfully!")