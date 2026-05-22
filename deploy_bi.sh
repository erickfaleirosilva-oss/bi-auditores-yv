#!/bin/bash
# deploy_bi.sh — Sincroniza Google Sheets → data.json → GitHub Pages
#
# Uso manual:  bash deploy_bi.sh
# Agendado:    via G4 OS scheduler (diário)

set -e

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOG="$DIR/deploy.log"

log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*" | tee -a "$LOG"; }

log "=== Iniciando deploy BI Auditores ==="

# 1. Atualizar data.json via Google Sheets
cd "$DIR"
log "Rodando sync_google_sheets.py..."
python3 sync_google_sheets.py >> "$LOG" 2>&1

# 2. Embutir data.json no index.html (inline __DATA_INLINE__)
log "Embutindo data.json no index.html..."
python3 "$DIR/embed_data.py"

# 3. Commitar e fazer push para GitHub Pages
log "Commitando para GitHub Pages..."
cd "$DIR"
git add data.json index.html
git commit -m "sync: atualização automática $(date '+%Y-%m-%d %H:%M')" || {
    log "Nada para commitar — dados já estão atualizados."
    exit 0
}
git push origin main

log "✓ Deploy concluído — BI Auditores atualizado."
