#!/usr/bin/env python3
"""
embed_data.py — Lê data.json e emite novo index.html com __DATA_INLINE__ atualizado.
Chamado pelo deploy_bi.sh após sync_google_sheets.py gerar o data.json.
"""

import json
import os
import sys

DIR = os.path.dirname(os.path.abspath(__file__))
data_path = os.path.join(DIR, 'data.json')
html_path = os.path.join(DIR, 'index.html')

# Carregar data.json
with open(data_path, 'r', encoding='utf-8') as f:
    data = json.load(f)

data_inline = json.dumps(data, ensure_ascii=False, separators=(',', ':'))

# Carregar index.html linha a linha
with open(html_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Encontrar linha que começa com "window.__DATA_INLINE__ ="
MARKER = 'window.__DATA_INLINE__ ='
new_lines = []
replaced = False
for line in lines:
    if line.strip().startswith(MARKER):
        new_lines.append(f'window.__DATA_INLINE__ = {data_inline};\n')
        replaced = True
    else:
        new_lines.append(line)

if not replaced:
    print('[ERRO] Marcador __DATA_INLINE__ não encontrado no index.html')
    sys.exit(1)

with open(html_path, 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

n_registros = len(data.get('registros', []))
n_auditores = len(data.get('auditores', {}))
updated = data.get('updated_at', '?')
print(f'✓ index.html atualizado — {n_registros} registros, {n_auditores} auditores, atualizado em {updated}')
