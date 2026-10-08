import os
import re

color_map = {
    # Dark mode backgrounds -> Light mode backgrounds
    "'#060a12'": "'var(--cm-bg-base)'",
    "'#070b14'": "'var(--cm-bg-base)'",
    "'#090d16'": "'var(--cm-bg-surface)'",
    "'#0d1526'": "'var(--cm-bg-surface)'",
    "'#121d33'": "'var(--cm-bg-surface-hover)'",
    "'#161f30'": "'var(--cm-bg-elevated)'",
    "'#162238'": "'var(--cm-bg-elevated)'",
    
    # Borders
    "'#1e293b'": "'var(--cm-border-subtle)'",
    "'#2a384f'": "'var(--cm-border-default)'",
    "'#3b4d6b'": "'var(--cm-border-strong)'",

    # Text Colors
    "'#f8fafc'": "'var(--cm-text-primary)'",
    "'#e2e8f0'": "'var(--cm-text-primary)'",
    "'#cbd5e1'": "'var(--cm-text-secondary)'",
    "'#94a3b8'": "'var(--cm-text-secondary)'",
    "'#64748b'": "'var(--cm-text-muted)'",
    
    # Brand/Accent colors
    "'#00d4ff'": "'var(--cm-accent)'",
    "'#38bdf8'": "'var(--cm-accent)'",
    "'#0ea5e9'": "'var(--cm-accent-hover)'",
    
    # Status colors
    "'#ef4444'": "'var(--cm-critical)'",
    "'#10b981'": "'var(--cm-success)'",
    "'#f59e0b'": "'var(--cm-warning)'",
    "'#6366f1'": "'var(--cm-info)'",
    "'#818cf8'": "'var(--cm-info)'",
}

def process_file(filepath):
    with open(filepath, 'r') as f:
        content = f.read()
        
    original = content
    for old_color, new_color in color_map.items():
        # case insensitive replacement
        content = re.sub(old_color, new_color, content, flags=re.IGNORECASE)
        # replace hex values with double quotes if any
        content = re.sub(old_color.replace("'", '"'), new_color.replace("'", '"'), content, flags=re.IGNORECASE)
        
    if content != original:
        with open(filepath, 'w') as f:
            f.write(content)
        print(f"Updated {filepath}")

for root, _, files in os.walk('src'):
    for file in files:
        if file.endswith(('.tsx', '.ts')):
            process_file(os.path.join(root, file))
