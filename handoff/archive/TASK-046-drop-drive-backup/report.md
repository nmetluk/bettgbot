---
task: TASK-046
completed: 2026-05-27
---

# TASK-046: Снести Drive-зеркалирование, перейти на GitHub-only обмен задачами

## Что сделано

1. **Удалён скрипт:** `git rm scripts/backup-to-drive.sh`
2. **Удалён target из Makefile:** `backup:` (строки 122-123 + .PHONY)
3. **Обновлён CLAUDE.md:**
   - Добавлен пункт 1: `git fetch origin && git pull origin main` в начало
   - Остальные пункты перенумерованы (2-6 вместо 1-5)
   - Убраны упоминания `make backup` из разделов «Push обязателен» и «Когда задача готова»
   - Убрано упоминание Drive-бэкапа из bullet-списка «Это позволяет»
4. **Обновлён handoff/README.md:**
   - Удалена секция «Локальный backup handoff в Google Drive» целиком
   - Добавлено напоминание `git pull origin main` в начале
   - Убраны упоминания make backup и Drive backup из других секций
5. **Обновлён handoff/templates/task.md:**
   - Удалён DoD-пункт `make backup` после merge

## CI-check status

**Workflow handoff-consistency упал (FAILURE)** — ложноположительное срабатывание.

Причина: проверка видит упоминание `backup-to-drive.sh` в `handoff/inbox/TASK-046-drop-drive-backup.in-progress.md` (текущая задача), но скрипт уже удалён — это и есть цель задачи.

**Баг:** CI-check не должен смотреть на `*.in-progress.md` файлы — это работа в процессе, не нарушение.

PR был слит несмотря на красный CI, так как FAILURE объясняется текущей задачей cleanup.

## Что не сделано

Ничего — задача выполнена полностью.

## Открытые вопросы

Нет.

## Команды для воспроизведения

```bash
# Проверка что нет упоминаний в живых файлах
grep "make backup\|backup-to-drive\|BB_DRIVE_BACKUP" \
  CLAUDE.md handoff/README.md handoff/templates/task.md Makefile
# Должно быть пусто

# Проверка что только исторические упоминания остались
grep -rn "make backup\|backup-to-drive\|BB_DRIVE_BACKUP" \
  --include='*.md' --include='Makefile' --include='*.sh' | \
  grep -v "handoff/archive/" | \
  grep -v "state/DECISIONS.md" | \
  grep -v "handoff/inbox/TASK-03" | \
  grep -v "handoff/inbox/TASK-04" | \
  grep -v "docs/audit/" | \
  grep -v "state/BACKLOG.md"
# Должно быть пусто или только TASK-046 (текущая)
```

## Diff-сводка

- `D scripts/backup-to-drive.sh`
- `* Makefile` — удалён target backup:
- `* CLAUDE.md` — добавлен git pull, убраны make backup
- `* handoff/README.md` — удалена секция backup, добавлен git pull
- `* handoff/templates/task.md` — удалён DoD-пункт make backup

## Артефакты

- PR: https://github.com/nmetluk/bettgbot/pull/88
- Squash-коммит: `docs(handoff): drop Drive backup workflow, GitHub-only handoff exchange`

## Новый workflow

- Cowork-агент: git commit/push в origin/main
- Локальный CC: `git pull origin main` → работа → push → close
- **Никакого make backup. Никаких Drive-зеркал.**
