#!/usr/bin/env bash
# backup-to-drive.sh — зеркалирование handoff/state/sessions в локально-синкнутую
# Google Drive папку. Cross-platform: rsync на macOS/Linux, robocopy на Windows
# (Git Bash / MSYS / Cygwin).
#
# Запускается из DoD задачи: см. CLAUDE.md "Когда задача готова" п.5.5.
# См. также handoff/README.md секцию "Локальный backup handoff".

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

# Определяем backend и дефолтный путь Drive-папки по ОС.
# Переопределяется через env BB_DRIVE_BACKUP (любая ОС).
case "${OSTYPE:-}" in
    darwin*)
        : "${BB_DRIVE_BACKUP:=/Users/nmetluk/Library/CloudStorage/GoogleDrive-nm@pinspb.ru/Мой диск/Claude projects/Betting Bot backup}"
        BACKEND=rsync
        ;;
    linux*)
        # На Linux обычно Drive подключают через rclone mount или gdrive3 — путь индивидуален,
        # обязательно задавать BB_DRIVE_BACKUP вручную.
        : "${BB_DRIVE_BACKUP:=}"
        BACKEND=rsync
        ;;
    msys*|cygwin*|win32)
        : "${BB_DRIVE_BACKUP:=G:/Мой диск/Claude projects/Betting Bot backup}"
        BACKEND=robocopy
        ;;
    *)
        echo "❌ Неподдерживаемая ОС: ${OSTYPE:-unknown}" >&2
        echo "Поддерживаются: macOS (darwin), Linux, Windows (msys/cygwin)." >&2
        exit 1
        ;;
esac

if [ -z "$BB_DRIVE_BACKUP" ]; then
    echo "❌ BB_DRIVE_BACKUP не задан и нет дефолта для этой ОС." >&2
    echo "Задай явно: export BB_DRIVE_BACKUP=\"/path/to/Betting Bot backup\"" >&2
    exit 1
fi

DRIVE_BACKUP="$BB_DRIVE_BACKUP"

if [ ! -d "$DRIVE_BACKUP" ]; then
    echo "❌ Drive backup directory not found: $DRIVE_BACKUP" >&2
    echo "" >&2
    echo "Проверь:" >&2
    echo "  - Google Drive File Stream запущен и подмонтирован?" >&2
    echo "  - Путь существует физически (ls/dir или открой в Finder/Explorer)?" >&2
    echo "  - Если путь другой — переопредели через BB_DRIVE_BACKUP env." >&2
    exit 1
fi

echo "→ backup destination: $DRIVE_BACKUP"
echo "→ backend: $BACKEND"
echo ""

if [ "$BACKEND" = "rsync" ]; then
    echo "→ handoff/  (полное зеркало, кроме .draft/)"
    rsync -a --delete \
        --exclude='.draft/' \
        "$REPO_ROOT/handoff/" "$DRIVE_BACKUP/handoff/"

    echo "→ state/  (только *.md)"
    mkdir -p "$DRIVE_BACKUP/state"
    rsync -a --delete \
        --include='*.md' --exclude='*' \
        "$REPO_ROOT/state/" "$DRIVE_BACKUP/state/"

    echo "→ sessions/  (полное зеркало)"
    rsync -a --delete \
        "$REPO_ROOT/sessions/" "$DRIVE_BACKUP/sessions/"

elif [ "$BACKEND" = "robocopy" ]; then
    # robocopy ожидает Windows-style пути и считает exit-code <8 как success.
    DRIVE_WIN="$(echo "$DRIVE_BACKUP" | sed 's|/|\\|g')"
    REPO_WIN="$(echo "$REPO_ROOT" | sed 's|/|\\|g')"

    # /MIR = mirror (включает /E и /PURGE — последний удаляет лишнее в destination,
    # эквивалент rsync --delete). Без /PURGE backup не вычистил бы старый мусор.
    echo "→ handoff/  (полное зеркало, кроме .draft/)"
    robocopy "$REPO_WIN\\handoff" "$DRIVE_WIN\\handoff" /MIR /XD ".draft" /NFL /NDL /NJH /NJS || [ $? -lt 8 ]

    echo "→ state/  (только *.md)"
    robocopy "$REPO_WIN\\state" "$DRIVE_WIN\\state" "*.md" /MIR /NFL /NDL /NJH /NJS || [ $? -lt 8 ]

    echo "→ sessions/  (полное зеркало)"
    robocopy "$REPO_WIN\\sessions" "$DRIVE_WIN\\sessions" /MIR /NFL /NDL /NJH /NJS || [ $? -lt 8 ]
fi

if [ -f "$REPO_ROOT/memory-export.md" ]; then
    echo "→ memory-export.md"
    cp "$REPO_ROOT/memory-export.md" "$DRIVE_BACKUP/"
fi

# CLAUDE.md и README.md cowork может читать через git/GitHub — в backup не льём
# (чтобы не плодить две версии "источника правды").

echo ""
echo "✓ Backup готов: $DRIVE_BACKUP"
echo "  Drive File Stream синкнет в облаке в фоне (1–60 сек)."
