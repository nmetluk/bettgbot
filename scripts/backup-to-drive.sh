#!/usr/bin/env bash
# backup-to-drive.sh — зеркалирование handoff/state/sessions в локально-синкнутую
# Google Drive папку (Windows через robocopy).
#
# Запускается из DoD задачи: см. CLAUDE.md "Когда задача готова" п.5.5.
# См. также handoff/README.md секцию "Локальный backup handoff".

set -euo pipefail

DRIVE_BACKUP="${BB_DRIVE_BACKUP:-G:/Мой диск/Claude projects/Betting Bot backup}"
REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

if [ ! -d "$DRIVE_BACKUP" ]; then
    echo "❌ Drive backup directory not found: $DRIVE_BACKUP" >&2
    echo "" >&2
    echo "Проверь:" >&2
    echo "  - Google Drive File Stream запущен и подмонтирован?" >&2
    echo "  - Путь существует физически (ls -la в Finder)?" >&2
    echo "  - Если путь другой — переопредели через BB_DRIVE_BACKUP env." >&2
    exit 1
fi

# Конвертация путей для Windows
DRIVE_WIN="$(echo "$DRIVE_BACKUP" | sed 's|/|\\|g')"
REPO_WIN="$(echo "$REPO_ROOT" | sed 's|/|\\|g')"

echo "→ handoff/  (полное зеркало, кроме .draft/)"
robocopy "$REPO_WIN\\handoff" "$DRIVE_WIN\\handoff" /E /XD ".draft" /NFL /NDL /NJH /NJS || true

echo "→ state/  (только *.md)"
robocopy "$REPO_WIN\\state" "$DRIVE_WIN\\state" "*.md" /E /NFL /NDL /NJH /NJS || true

echo "→ sessions/  (полное зеркало)"
robocopy "$REPO_WIN\\sessions" "$DRIVE_WIN\\sessions" /E /NFL /NDL /NJH /NJS || true

if [ -f "$REPO_ROOT/memory-export.md" ]; then
    echo "→ memory-export.md"
    cp "$REPO_ROOT/memory-export.md" "$DRIVE_BACKUP/"
fi

# CLAUDE.md и README.md cowork может читать через git/GitHub — в backup не льём
# (чтобы не плодить две версии "источника правды").

echo ""
echo "✓ Backup готов: $DRIVE_BACKUP"
echo "  Drive File Stream синкнет в облаке в фоне (1–60 сек)."
