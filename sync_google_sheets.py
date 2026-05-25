#!/usr/bin/env python3
"""
sync_google_sheets.py — Lê a planilha de auditores do Google Sheets
e regenera o data.json para o BI de Auditores.

Uso:
  python3 sync_google_sheets.py

Pré-requisitos:
  pip install gspread google-auth openpyxl

Configuração:
  1. Coloque o arquivo credentials.json (Service Account Google) nesta pasta
  2. Ajuste SPREADSHEET_ID com o ID do Google Sheets da Camila
  3. Rode o script — ele gera data.json atualizado

Alternativa (planilha pública):
  Se a planilha estiver compartilhada publicamente (modo Leitor para "Qualquer pessoa"),
  o script usa apenas SPREADSHEET_ID sem precisar de credenciais.
"""

import json
import os
import sys
from datetime import datetime
from collections import defaultdict, Counter

# ─── Configuração ─────────────────────────────────────────────────────────────

# ID do Google Sheets — extrair da URL:
# https://docs.google.com/spreadsheets/d/SPREADSHEET_ID/edit
# Substituir pelo ID real após a Camila criar/compartilhar a planilha
SPREADSHEET_ID = '1rNvoycg3S6PdIyVZtfECVEsBTobJXzeX'

# Nome da aba (sheet) onde ficam os dados de auditores
SHEET_NAME = 'Plan1'  # nome da aba (usado só com API key)
# GID da aba — extraído da URL do Google Sheets
SHEET_GID = '1550622683'

# Credenciais (arquivo JSON da Service Account Google)
CREDENTIALS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'credentials.json')

# ─── Saída ────────────────────────────────────────────────────────────────────
OUTPUT_DIR  = os.path.dirname(os.path.abspath(__file__))
OUTPUT_JSON = os.path.join(OUTPUT_DIR, 'data.json')

# ─── Mapeamentos ──────────────────────────────────────────────────────────────
CLIMA_MAP = {'J': 'Segura', 'K': 'Duvidosa', 'L': 'Insegura'}


def norm_empr(e):
    e = str(e).strip().upper()
    if 'CANASTRA' in e:   return 'Canastra'
    if ('RESORT' in e or 'SÃO PEDRO' in e or 'SAO PEDRO' in e) and 'RESORT' in e: return 'São Pedro Resort'
    if 'THERMAS' in e or 'SAO PEDRO' in e or 'SÃO PEDRO' in e: return 'São Pedro Thermas'
    if 'ESSENCE' in e or 'ESSENSE' in e: return 'Essence'
    if 'ALTA VISTA' in e: return 'Alta Vista'
    if 'ATIBAIA' in e:    return 'Atibaia'
    return e.title()


# ─── 1. Ler Google Sheets ─────────────────────────────────────────────────────

# API key pública do Google (Sheets API v4) — criada no projeto YourVacation
# Permite leitura de planilhas compartilhadas publicamente sem OAuth
GOOGLE_API_KEY = 'AIzaSyD-9tSrke72PouQMnMX-a7eZSW0jkFMBWY'


def read_google_sheets():
    """Lê todos os dados da planilha via export CSV público (sem autenticação)."""
    return read_google_sheets_csv()


def read_google_sheets_csv():
    """Lê via export CSV público do Google Sheets (sem API key, sem OAuth)."""
    import requests as req
    import csv
    import io

    url = f'https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}/export?format=csv&gid={SHEET_GID}'
    print(f'Baixando CSV público (gid={SHEET_GID})...')
    resp = req.get(url, timeout=30, allow_redirects=True)
    resp.raise_for_status()

    content = resp.content.decode('utf-8-sig')
    reader = csv.reader(io.StringIO(content))
    all_values = list(reader)
    print(f'{len(all_values)} linhas lidas via CSV export.')
    return all_values


# ─── 2. Processar dados ───────────────────────────────────────────────────────

def process_rows(all_values):
    """Converte linhas brutas do Google Sheets em registros normalizados."""
    rows = []

    for i, row in enumerate(all_values):
        # Pular cabeçalho (linhas 0 e 1)
        if i < 2:
            continue

        # Garantir que a linha tem colunas suficientes
        while len(row) < 15:
            row.append('')

        if not row[0] or str(row[0]).strip() == '':
            continue

        auditor = ' '.join(str(row[0]).strip().upper().split())

        # Data (coluna B = índice 1)
        data_val = str(row[1]).strip() if row[1] else ''
        # Google Sheets retorna datas como string "DD/MM/YYYY" ou "YYYY-MM-DD"
        data_str = _normalize_date(data_val)

        # Cancelamento (coluna L = índice 11)
        cancelamento = str(row[11]).strip() if row[11] else ''

        # Status (coluna M = índice 12)
        status = str(row[12]).strip() if row[12] else ''
        if status == '\xa0': status = ''

        # Clima (coluna O = índice 14)
        clima_raw = str(row[14]).strip() if row[14] else ''
        if clima_raw == '\xa0': clima_raw = ''
        clima = CLIMA_MAP.get(clima_raw, clima_raw)

        # Empreendimento (coluna E = índice 4)
        empr = norm_empr(row[4]) if row[4] else ''

        rows.append({
            'auditor':                   auditor,
            'data':                      data_str,
            'cliente':                   str(row[2]).strip() if row[2] else '',
            'empreendimento':            empr,
            'duvida':                    str(row[5]).strip() if row[5] else '',
            'divergencia':               str(row[6]).strip() if row[6] else '',
            'obs':                       str(row[7]).strip() if row[7] else '',
            'consultor':                 str(row[9]).strip() if row[9] else '',
            'to':                        str(row[10]).strip() if row[10] else '',
            'solicitacao_cancelamento':  cancelamento == 'Solicitação de Cancelamento',
            'status':                    status,
            'pgto_antes':                str(row[13]).strip() if row[13] else '',
            'clima':                     clima,
        })

    return rows


def _normalize_date(d):
    """Normaliza data para YYYY-MM-DD independente do formato de entrada."""
    if not d:
        return ''
    d = d.strip()
    # Formato DD/MM/YYYY
    try:
        return datetime.strptime(d, '%d/%m/%Y').strftime('%Y-%m-%d')
    except ValueError:
        pass
    # Formato DD/MM/YY
    try:
        return datetime.strptime(d, '%d/%m/%y').strftime('%Y-%m-%d')
    except ValueError:
        pass
    # Formato YYYY-MM-DD (já correto)
    if len(d) == 10 and d[4] == '-':
        return d
    # Formato M/D/YYYY (Google às vezes exporta assim)
    try:
        return datetime.strptime(d, '%m/%d/%Y').strftime('%Y-%m-%d')
    except ValueError:
        pass
    # Formato D-Mon-YYYY (ex: 6-Dec-2025) — exportado pelo Google Sheets em inglês
    for fmt in ('%d-%b-%Y', '%d-%B-%Y'):
        try:
            return datetime.strptime(d, fmt).strftime('%Y-%m-%d')
        except ValueError:
            pass
    return d


# ─── 3. Calcular métricas ─────────────────────────────────────────────────────

def calc_stats(rows):
    all_auditors = sorted(set(r['auditor'] for r in rows))
    auditors_stats = {}

    for aud in all_auditors:
        recs = [r for r in rows if r['auditor'] == aud]
        total = len(recs)
        cancelados = [r for r in recs if r['status'] == 'CANCELADO']
        n_cancelados = len(cancelados)
        pct_cancel = round(n_cancelados / total * 100, 1) if total > 0 else 0

        climas_count = Counter(r['clima'] for r in recs if r['clima'] and r['clima'] != '\xa0')
        climas_pct = {}
        total_com_clima = sum(climas_count.values())
        for c, n in climas_count.items():
            climas_pct[c] = {'count': n, 'pct': round(n / total_com_clima * 100, 1)}

        cancel_por_clima = {}
        for clima_tipo in ['Segura', 'Duvidosa', 'Insegura']:
            do_clima = [r for r in recs if r['clima'] == clima_tipo]
            cancel_clima = [r for r in do_clima if r['status'] == 'CANCELADO']
            if do_clima:
                cancel_por_clima[clima_tipo] = {
                    'total': len(do_clima),
                    'cancelados': len(cancel_clima),
                    'pct': round(len(cancel_clima) / len(do_clima) * 100, 1)
                }

        by_empr = defaultdict(list)
        for r in recs:
            by_empr[r['empreendimento']].append(r)

        empr_stats = {}
        for empr, erecs in by_empr.items():
            ec = [r for r in erecs if r['status'] == 'CANCELADO']
            empr_stats[empr] = {
                'total': len(erecs),
                'cancelados': len(ec),
                'pct': round(len(ec) / len(erecs) * 100, 1) if erecs else 0
            }

        by_month = defaultdict(list)
        for r in recs:
            if r['data']:
                try:
                    by_month[r['data'][:7]].append(r)
                except Exception:
                    pass

        month_stats = {}
        for m, mrecs in sorted(by_month.items()):
            mc = [r for r in mrecs if r['status'] == 'CANCELADO']
            month_stats[m] = {
                'total': len(mrecs),
                'cancelados': len(mc),
                'pct': round(len(mc) / len(mrecs) * 100, 1) if mrecs else 0
            }

        auditors_stats[aud] = {
            'total': total,
            'cancelados': n_cancelados,
            'vendas_liquidas': total - n_cancelados,
            'pct_cancelamento': pct_cancel,
            'climas': climas_pct,
            'cancel_por_clima': cancel_por_clima,
            'por_empreendimento': empr_stats,
            'por_mes': month_stats,
        }

    ranking = sorted(all_auditors, key=lambda a: auditors_stats[a]['pct_cancelamento'])

    return {
        'updated_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'total_conferencias': len(rows),
        'auditores': auditors_stats,
        'ranking': ranking,
        'registros': rows,
    }


# ─── 4. Fallback: arquivo local ───────────────────────────────────────────────

def sync_local():
    """Usa o último arquivo Excel baixado manualmente (fallback)."""
    try:
        import openpyxl
    except ImportError:
        print('[ERRO] Instale: pip install openpyxl')
        return None

    local_candidates = [
        os.path.join(OUTPUT_DIR, 'RELATORIO AUDITORES.xlsx'),
        os.path.expanduser('~/Downloads/RELATORIO AUDITORES.xlsx'),
        os.path.expanduser('~/Desktop/RELATORIO AUDITORES.xlsx'),
    ]
    for path in local_candidates:
        if os.path.exists(path):
            print(f'[fallback] Usando arquivo local: {path}')
            wb = openpyxl.load_workbook(path, data_only=True)
            ws = wb.active
            return [list(row) for row in ws.iter_rows(values_only=True)]
    return None


# ─── MAIN ─────────────────────────────────────────────────────────────────────

def main():
    print(f'[{datetime.now().strftime("%Y-%m-%d %H:%M:%S")}] Iniciando sync...')

    all_values = None

    if SPREADSHEET_ID == 'COLE_AQUI_O_ID_DO_GOOGLE_SHEETS':
        print('[AVISO] SPREADSHEET_ID não configurado. Usando arquivo local...')
        all_values = sync_local()
    else:
        try:
            all_values = read_google_sheets()
        except Exception as e:
            print(f'[AVISO] Falha no Google Sheets: {e}')
            print('Tentando arquivo local...')
            all_values = sync_local()

    if not all_values:
        print('[ERRO] Nenhuma fonte disponível.')
        print('  → Configure SPREADSHEET_ID no script, ou')
        print(f'  → Coloque "RELATORIO AUDITORES.xlsx" em: {OUTPUT_DIR}')
        sys.exit(1)

    print('Processando dados...')
    rows = process_rows(all_values)
    print(f'{len(rows)} registros processados.')

    print('Calculando métricas...')
    data = calc_stats(rows)

    print(f'Salvando {OUTPUT_JSON}...')
    with open(OUTPUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f'✓ data.json gerado — {len(rows)} registros, {len(data["auditores"])} auditores')
    for aud in data['ranking']:
        s = data['auditores'][aud]
        print(f'  {aud}: {s["total"]} conf, {s["cancelados"]} cancel, {s["pct_cancelamento"]}%')


if __name__ == '__main__':
    main()
