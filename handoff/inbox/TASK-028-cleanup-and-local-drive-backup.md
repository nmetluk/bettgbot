# TASK-028 — Cleanup orphan handoff/sessions + смена backup-стратегии handoff на локально-синкнутую Drive-папку

**Размер:** S (1.5–2 часа с тестированием).
**Тип:** infra + workflow (без правок `src/` и `tests/`).
**Blocked-by:** merge PR #78 (TASK-027) — иначе будет rebase-конфликт по `.gitignore` и `Makefile`.
**Parallel-safe:** false.

## Контекст и мотивация

До этой задачи бэкап `handoff/`, `state/`, `sessions/` делался cowork-агентом из десктопного приложения через MCP Google Drive коннектор. На практике это даёт три проблемы:

1. **Лаг между завершением задачи и видимостью на второй машине.** Cowork пишет в Drive только когда у него активна сессия с подключённым коннектором. Если cowork-сессия закрылась раньше, чем владелец её проверил — бэкап старый.
2. **Зависимость от состояния коннектора.** При расхождениях между API и Drive UI получаем дубли (`brief 2.md`, `decisions 2.md` в `sessions/2026-05-24-12-task-025-review/`) или потерянные файлы.
3. **Труднодиагностируемые рассинхроны.** Реальные инциденты — TASK-014 (выполнилась на удалённой машине **раньше**, чем cowork узнал о её публикации) и TASK-027 (отчёт исполнителя не дошёл до cowork-видимости через коннектор; ветку `feature/TASK-027-prod-compose` cowork увидел только после ручного `git fetch` с PAT'ом).

Решение — снять backup с cowork и переложить на исполнителя через **локально-синкнутую Drive-папку**. На macOS Google Drive File Stream монтирует папку в `/Users/<user>/Library/CloudStorage/GoogleDrive-<email>/Мой диск/...`. Запись в эту папку синхронизируется в облако автоматически, без участия MCP. Cowork в своих сессиях видит свежий handoff через Drive (или через `git fetch` с PAT'ом, что теперь основной канал).

## Что сделать

### Часть А — Удалить три orphan-файла

Эти файлы — artefacts межмашинной синхронизации. На `origin` ни в одной ветке их нет (проверено `git log --all -- <path>`). Если у тебя на локальной FS они присутствуют (как untracked или, маловероятно, tracked в какой-то твоей локальной ветке) — удали.

```bash
cd "$(git rev-parse --show-toplevel)"
for f in \
    "handoff/inbox/TASK-026-admin-audit.in-progress.md" \
    "sessions/2026-05-24-12-task-025-review/brief 2.md" \
    "sessions/2026-05-24-12-task-025-review/decisions 2.md"; do
    if [ -f "$f" ]; then
        rm -v "$f"
    else
        echo "(skip — нет: $f)"
    fi
done
```

Происхождение:
- `handoff/inbox/TASK-026-admin-audit.in-progress.md` — забытый `.in-progress` rename от TASK-026, которая давно в archive (см. `handoff/archive/TASK-026-admin-audit/`).
- `... 2.md` — стандартный Drive/Finder Conflict-rename паттерн при одновременной правке одного файла.

### Часть Б — Defensive паттерн в `.gitignore`

Чтобы Finder/Drive duplicates впредь не маячили в `git status`, добавь в конец `.gitignore`:

```
# --- Drive/Finder duplicates ---
# Ловит "brief 2.md", "notes 3.md", "data 2.yml" и т.п.
* [0-9].md
* [0-9].txt
* [0-9].yml
* [0-9].yaml
* [0-9].py
* [0-9].sh
```

Проверка работы:
```bash
touch "test 2.md" && git status --porcelain "test 2.md"  # должно быть пусто
rm "test 2.md"
```

### Часть В — Скрипт `scripts/backup-to-drive.sh`

Создай новый файл `scripts/backup-to-drive.sh` (исполняемый, `chmod +x`):

```bash
#!/usr/bin/env bash
# backup-to-drive.sh — зеркалирование handoff/state/sessions в локально-синкнутую
# Google Drive папку, чтобы cowork-агент (в десктоп-приложении) и параллельный
# второй экземпляр локального CC видели актуальный handoff без задержек.
#
# Запускается из DoD задачи: см. CLAUDE.md "Когда задача готова" п.5.5.
# См. также handoff/README.md секцию "Локальный backup handoff".

set -euo pipefail

DRIVE_BACKUP="${BB_DRIVE_BACKUP:-/Users/nmetluk/Library/CloudStorage/GoogleDrive-nm@pinspb.ru/Мой диск/Claude projects/Betting Bot backup}"
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

if [ -f "$REPO_ROOT/memory-export.md" ]; then
    echo "→ memory-export.md"
    cp "$REPO_ROOT/memory-export.md" "$DRIVE_BACKUP/"
fi

# CLAUDE.md и README.md cowork может читать через git/GitHub — в backup не льём
# (чтобы не плодить две версии "источника правды").

echo ""
echo "✓ Backup готов: $DRIVE_BACKUP"
echo "  Drive File Stream синкнет в облако в фоне (1–60 сек)."
```

### Часть Г — Цель в `Makefile`

Добавь в `.PHONY` цель `backup`, и в конец Makefile блок:

```makefile
backup: ## Зеркалирование handoff/state/sessions в локально-синкнутую Drive-папку (после git pull main)
	@./scripts/backup-to-drive.sh
```

Не забудь добавить `backup` в строку `.PHONY:` сверху Makefile.

### Часть Д — Обновить `handoff/README.md`

Найди существующую секцию **«Зеркало в Google Drive»** (она описывает старый процесс через MCP-коннектор cowork-агента). Замени её на новую секцию:

```markdown
## Локальный backup handoff в Google Drive

Чтобы cowork-агент (в десктоп-приложении) и параллельный второй экземпляр локального CC видели актуальный handoff без задержек, после каждого merge задачи (т.е. сразу после `git checkout main && git pull origin main`) **обязательно** запустить:

```bash
make backup
```

Это вызовет `scripts/backup-to-drive.sh`, который через `rsync -a --delete` зеркалирует:

- `handoff/{inbox,outbox,archive,templates,README.md}` — полностью (кроме `.draft/`)
- `state/*.md`
- `sessions/*/` — полностью
- корневой `memory-export.md` — если есть

в локально-синкнутую Drive-папку `/Users/nmetluk/Library/CloudStorage/GoogleDrive-nm@pinspb.ru/Мой диск/Claude projects/Betting Bot backup/`. Drive File Stream сам синхронизирует это в облако (1–60 сек).

Если путь Drive-папки на твоей машине отличается — экспортируй `BB_DRIVE_BACKUP` env:

```bash
export BB_DRIVE_BACKUP="/path/to/your/drive/Betting Bot backup"
make backup
```

**Чего больше нет.** Раньше cowork-агент копировал то же самое через MCP Google Drive коннектор из десктоп-приложения. Этот путь упразднён — он создавал лаг между merge и видимостью + плодил Drive duplicates. Cowork теперь читает свежий handoff либо через `git fetch` (PAT настроен), либо через ту же Drive-папку.
```

(Если в текущем `handoff/README.md` секция называется по-другому или содержит дополнительные подсекции — адаптируй под существующую структуру; ключевая идея: старое описание про MCP-коннектор удаляется, новое описание про `make backup` появляется.)

### Часть Е — Обновить `CLAUDE.md`

В секции **«Когда задача готова»** между пунктом 5 (синхронизация локальной `main` с `origin/main`) и пунктом 6 (отметка о готовности) вставь новый пункт:

```markdown
5.5. **Сделать `make backup`** — зеркалирование `handoff/`, `state/`, `sessions/` в локально-синкнутую Drive-папку. Без этого шага cowork-агент в следующей сессии может работать со старым handoff. См. [`handoff/README.md`](handoff/README.md) секция «Локальный backup handoff».
```

И в секции **«Push обязателен после каждой задачи»** в подпункте 5 (после merge — sync main) добавь предложение в конец: «И сразу — `make backup`, см. п. 5.5 ниже».

### Часть Ж — Тестирование

1. После всех правок: `make backup` запустить — должно завершиться без ошибок и вывести `✓ Backup готов: …`.
2. В Finder открыть `/Users/nmetluk/Library/CloudStorage/GoogleDrive-nm@pinspb.ru/Мой диск/Claude projects/Betting Bot backup/` — там должны быть три актуальные директории `handoff/`, `state/`, `sessions/` (и опционально `memory-export.md`).
3. `diff -rq handoff/ "/Users/nmetluk/Library/CloudStorage/GoogleDrive-nm@pinspb.ru/Мой диск/Claude projects/Betting Bot backup/handoff/"` — должен молчать (или показать только `.draft/`-разницу, если такая есть).
4. `make help` — должен показывать новую цель `backup` в списке.
5. Проверка defensive паттерна: `touch "fake 2.md" && git status --porcelain "fake 2.md"` — должно быть пусто. Удалить `fake 2.md` после.

## Что НЕ делать

- Не трогать MCP Google Drive коннектор-логику — её в репо нет, это инструмент cowork-агента, не код приложения.
- Не добавлять pre-push hook или post-merge hook автоматизации `make backup` — отложено (нужна осторожность с push'ами правок `.gitignore` или handoff-cleanup'ов, где backup перед мержом бессмыслен).
- Не править `state/DECISIONS.md` — это сделает cowork-агент в pre-task cleanup перед TASK-029. Достаточно в `handoff/outbox/TASK-028-report.md` написать, какое решение зафиксировано (фразу для копирования в DECISIONS).
- Не править `src/`, `tests/`, `infra/`, `docs/` — это вне скоупа.

## DoD

- [ ] Часть А: orphan-файлы удалены (или явно подтверждено в report, что на твоей машине их не было).
- [ ] Часть Б: `.gitignore` обновлён, ручная проверка `touch "test 2.md" && git status --porcelain` показывает пусто.
- [ ] Часть В: `scripts/backup-to-drive.sh` существует, `chmod +x`, проходит проверку `bash -n` (syntax check).
- [ ] Часть Г: `make backup` доступен через `make help`.
- [ ] Часть Д: `handoff/README.md` отражает новый процесс, старая секция про MCP-коннектор удалена.
- [ ] Часть Е: `CLAUDE.md` содержит пункт 5.5 «make backup».
- [ ] Часть Ж: реальный прогон `make backup` успешен, Drive-папка обновилась.
- [ ] Один PR в `main` от ветки `chore/TASK-028-local-drive-backup`.
- [ ] Commit message: `chore(workflow): TASK-028 cleanup orphans + switch handoff backup to local Drive folder`.
- [ ] PR title: `TASK-028: cleanup orphans + локальный Drive backup handoff`.

## Что будет в отчёте `handoff/outbox/TASK-028-report.md`

Стандартный шаблон, плюс **обязательно**:
- Листинг (или скрин-описание) содержимого Drive-папки после `make backup`.
- Фраза для копирования в `state/DECISIONS.md` (одна строка таблицы): что сменили, почему, где подробнее.

## Что после merge

1. Cowork-агент в pre-task cleanup перед TASK-029 добавит запись в `state/DECISIONS.md` и обновит `state/PROJECT_STATUS.md` (отметка о смене backup workflow).
2. С этого момента все следующие задачи в DoD имеют шаг `make backup`.
3. TASK-029 — `pg_dump` cron-бэкап БД (бывший TASK-028 по предыдущей нумерации).
